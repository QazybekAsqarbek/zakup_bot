import logging
import json
import re
from typing import Dict, List, Optional
from collections import defaultdict
from openai import OpenAI
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)


class QuoteComparator:
    """
    Compares normalized quotes across suppliers and generates recommendations
    for the best purchasing decisions.
    """
    
    def __init__(self):
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL
        )
    
    def _normalize_item_name(self, name: str) -> str:
        """Normalize item name for comparison (lowercase, remove extra spaces)"""
        if not name:
            return ""
        return re.sub(r'\s+', ' ', name.lower().strip())
    
    def _group_similar_items(self, quotes: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group items by similar names across all suppliers.
        Uses simple name matching (can be enhanced with fuzzy matching).
        
        Returns:
            Dictionary mapping normalized_name to list of items from different suppliers
        """
        grouped = defaultdict(list)
        
        for quote in quotes:
            source_file = quote.get("source_file", "")
            
            for supplier in quote.get("suppliers", []):
                supplier_name = supplier.get("name", "Unknown")
                
                for item in supplier.get("items", []):
                    normalized_name = self._normalize_item_name(item.get("name", ""))
                    
                    if normalized_name:
                        item_with_context = item.copy()
                        item_with_context["_supplier"] = supplier_name
                        item_with_context["_source"] = source_file
                        
                        grouped[normalized_name].append(item_with_context)
        
        # Filter out items that appear only once (nothing to compare)
        comparable_groups = {
            name: items for name, items in grouped.items() 
            if len(items) > 1
        }
        
        return comparable_groups
    
    async def _compare_item_group_with_llm(self, item_group: List[Dict], 
                                           item_name: str) -> Optional[Dict]:
        """
        Use LLM to analyze a group of similar items and recommend the best option.
        
        Args:
            item_group: List of similar items from different suppliers
            item_name: Original item name
            
        Returns:
            Recommendation dictionary with supplier, reasoning, and price comparison
        """
        # Prepare item data for LLM
        items_summary = []
        for i, item in enumerate(item_group, 1):
            summary = {
                "№": i,
                "Поставщик": item.get("_supplier"),
                "Цена (ориг)": f"{item.get('price_per_unit', 0)} {item.get('currency', '')} за {item.get('unit', '')}",
                "Цена (норм)": f"{item.get('normalized_price', 0)} за {item.get('normalized_unit', '')}",
                "Количество": f"{item.get('normalized_quantity', 0)} {item.get('normalized_unit', '')}",
                "Характеристики": item.get("specs", {}),
                "Полнота данных": f"{item.get('completeness_score', 0)*100:.0f}%"
            }
            items_summary.append(summary)
        
        prompt = f"""Проанализируй коммерческие предложения разных поставщиков для товара: "{item_name}"

Данные поставщиков:
{json.dumps(items_summary, ensure_ascii=False, indent=2)}

Задача:
1. Сравни нормализованные цены
2. Оцени полноту данных и характеристики
3. Учти качество предложения (полнота информации важна!)
4. Дай рекомендацию, какого поставщика выбрать

Верни СТРОГО в формате JSON:
{{
  "recommended_supplier": "Название поставщика",
  "recommended_price": <нормализованная цена>,
  "price_unit": "<единица измерения>",
  "price_difference_percent": <% разницы с худшим вариантом>,
  "reasoning": "Краткое объяснение выбора (2-3 предложения)",
  "alternatives": ["Поставщик 2", "Поставщик 3"]
}}

Если все варианты плохие или данных недостаточно, укажи это в reasoning."""

        try:
            response = self.client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,
                temperature=0.2
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
                logger.info(f"✅ LLM recommendation for '{item_name}': {result.get('recommended_supplier')}")
                return result
            
        except Exception as e:
            logger.error(f"❌ LLM comparison error for '{item_name}': {e}")
        
        return None
    
    def _simple_price_comparison(self, item_group: List[Dict]) -> Dict:
        """
        Fallback simple price comparison (lowest normalized price wins).
        """
        # Filter items with valid normalized prices
        valid_items = [
            item for item in item_group 
            if item.get("normalized_price") and item.get("normalized_price") > 0
        ]
        
        if not valid_items:
            return {
                "recommended_supplier": "Данных недостаточно",
                "recommended_price": 0,
                "price_unit": "",
                "price_difference_percent": 0,
                "reasoning": "Отсутствуют нормализованные цены для сравнения",
                "alternatives": []
            }
        
        # Sort by normalized price
        sorted_items = sorted(valid_items, key=lambda x: x.get("normalized_price", float('inf')))
        
        best_item = sorted_items[0]
        worst_item = sorted_items[-1]
        
        best_price = best_item.get("normalized_price", 0)
        worst_price = worst_item.get("normalized_price", 0)
        
        if worst_price > 0:
            price_diff = ((worst_price - best_price) / worst_price) * 100
        else:
            price_diff = 0
        
        return {
            "recommended_supplier": best_item.get("_supplier"),
            "recommended_price": best_price,
            "price_unit": best_item.get("normalized_unit", ""),
            "price_difference_percent": round(price_diff, 1),
            "reasoning": f"Лучшая цена среди {len(valid_items)} предложений",
            "alternatives": [item.get("_supplier") for item in sorted_items[1:3]]
        }
    
    async def compare_project_quotes(self, quotes: List[Dict]) -> Dict:
        """
        Main method to compare all quotes in a project.
        
        Args:
            quotes: List of quote documents from database
            
        Returns:
            Comprehensive comparison result with recommendations
        """
        if not quotes:
            return {
                "status": "empty",
                "message": "Нет цитат для сравнения",
                "item_comparisons": []
            }
        
        # Group similar items
        grouped_items = self._group_similar_items(quotes)
        
        if not grouped_items:
            return {
                "status": "no_matches",
                "message": "Нет совпадающих товаров у разных поставщиков",
                "total_unique_items": sum(
                    len(supplier.get("items", [])) 
                    for quote in quotes 
                    for supplier in quote.get("suppliers", [])
                ),
                "item_comparisons": []
            }
        
        # Compare each group
        comparisons = []
        
        for item_name, item_group in grouped_items.items():
            logger.info(f"🔍 Comparing '{item_name}' ({len(item_group)} options)")
            
            # Try LLM comparison first
            llm_result = await self._compare_item_group_with_llm(item_group, item_name)
            
            if llm_result:
                recommendation = llm_result
            else:
                # Fallback to simple comparison
                recommendation = self._simple_price_comparison(item_group)
            
            comparisons.append({
                "item_name": item_name,
                "suppliers_count": len(item_group),
                "recommendation": recommendation,
                "all_options": [
                    {
                        "supplier": item.get("_supplier"),
                        "price": item.get("normalized_price"),
                        "unit": item.get("normalized_unit"),
                        "completeness": item.get("completeness_score", 0)
                    }
                    for item in item_group
                ]
            })
        
        # Calculate summary statistics
        total_savings = 0
        items_compared = len(comparisons)
        
        for comp in comparisons:
            savings = comp["recommendation"].get("price_difference_percent", 0)
            if savings > 0:
                total_savings += savings
        
        avg_savings = total_savings / items_compared if items_compared > 0 else 0
        
        return {
            "status": "success",
            "message": f"Сравнено {items_compared} товаров",
            "items_compared": items_compared,
            "average_savings_percent": round(avg_savings, 1),
            "item_comparisons": comparisons,
            "generated_at": None  # Will be set by caller
        }
    
    async def generate_recommendation_summary(self, comparison_result: Dict) -> str:
        """
        Generate a human-readable summary of comparison results.
        
        Args:
            comparison_result: Result from compare_project_quotes
            
        Returns:
            Formatted text summary
        """
        if comparison_result.get("status") != "success":
            return comparison_result.get("message", "Нет данных для сравнения")
        
        comparisons = comparison_result.get("item_comparisons", [])
        
        summary = f"""📊 **АНАЛИЗ КОММЕРЧЕСКИХ ПРЕДЛОЖЕНИЙ**

Сравнено товаров: {comparison_result.get('items_compared', 0)}
Средняя экономия: {comparison_result.get('average_savings_percent', 0)}%

"""
        
        # Top recommendations
        summary += "🏆 **РЕКОМЕНДАЦИИ:**\n\n"
        
        for i, comp in enumerate(comparisons[:10], 1):  # Top 10
            rec = comp["recommendation"]
            summary += f"{i}. **{comp['item_name']}**\n"
            summary += f"   Рекомендация: {rec.get('recommended_supplier')}\n"
            summary += f"   Цена: {rec.get('recommended_price')} {rec.get('price_unit')}\n"
            summary += f"   Экономия: {rec.get('price_difference_percent')}%\n"
            summary += f"   Причина: {rec.get('reasoning')}\n\n"
        
        if len(comparisons) > 10:
            summary += f"... и еще {len(comparisons) - 10} товаров\n"
        
        return summary


# Global instance
quote_comparator = QuoteComparator()
