import logging
import json
import re
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from openai import OpenAI
from rapidfuzz import fuzz, process
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
    
    def _find_similar_group(self, item_name: str, existing_groups: Dict[str, List], 
                           similarity_threshold: float = 50.0) -> Optional[str]:
        """
        Find an existing group that matches the item name with fuzzy matching.
        Uses token_sort_ratio which ignores word order.
        
        Args:
            item_name: Normalized item name to match
            existing_groups: Current groups dictionary
            similarity_threshold: Minimum similarity score (0-100)
            
        Returns:
            Key of matching group, or None if no match found
        """
        if not existing_groups:
            return None
        
        # Use token_sort_ratio - ignores word order, better for product names
        result = process.extractOne(
            item_name, 
            existing_groups.keys(),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=similarity_threshold
        )
        
        if result:
            matched_name, score, _ = result
            logger.debug(f"🔗 Fuzzy match: '{item_name}' → '{matched_name}' (score: {score:.1f})")
            return matched_name
        else:
            # Log best match even if below threshold for debugging
            if existing_groups:
                best_match = process.extractOne(
                    item_name, 
                    existing_groups.keys(),
                    scorer=fuzz.token_sort_ratio
                )
                if best_match:
                    matched_name, score, _ = best_match
                    logger.debug(f"❌ No match: '{item_name}' closest to '{matched_name}' (score: {score:.1f}, threshold: {similarity_threshold})")
        
        return None
    
    def _group_similar_items(self, quotes: List[Dict], use_fuzzy: bool = True, 
                             fuzzy_threshold: float = 50.0) -> Dict[str, List[Dict]]:
        """
        Group items by similar names across all suppliers.
        Uses fuzzy matching to find similar items even with different naming.
        
        Args:
            quotes: List of quote documents
            use_fuzzy: Enable fuzzy matching (default True)
            fuzzy_threshold: Similarity threshold for fuzzy matching (0-100)
        
        Returns:
            Dictionary mapping normalized_name to list of items from different suppliers
        """
        grouped = defaultdict(list)
        all_items_log = []
        fuzzy_matches = []
        
        for quote in quotes:
            source_file = quote.get("source_file", "")
            
            for supplier in quote.get("suppliers", []):
                supplier_name = supplier.get("name", "Unknown")
                
                for item in supplier.get("items", []):
                    original_name = item.get("name", "")
                    normalized_name = self._normalize_item_name(original_name)
                    
                    if not normalized_name:
                        continue
                    
                    item_with_context = item.copy()
                    item_with_context["_supplier"] = supplier_name
                    item_with_context["_source"] = source_file
                    item_with_context["_original_name"] = original_name
                    
                    # Try fuzzy matching with existing groups
                    target_group = normalized_name
                    
                    if use_fuzzy and grouped:
                        similar_group = self._find_similar_group(
                            normalized_name, 
                            grouped, 
                            fuzzy_threshold
                        )
                        if similar_group:
                            target_group = similar_group
                            fuzzy_matches.append(
                                f"  🔗 '{normalized_name}' → '{target_group}'"
                            )
                    
                    grouped[target_group].append(item_with_context)
                    all_items_log.append(f"  [{supplier_name}] {original_name}")
        
        # Log all found items
        logger.info(f"📦 Найдено товаров всего: {len(all_items_log)}")
        for log_entry in all_items_log[:15]:  # Show first 15
            logger.info(log_entry)
        if len(all_items_log) > 15:
            logger.info(f"  ... и еще {len(all_items_log) - 15} товаров")
        
        # Log fuzzy matches
        if fuzzy_matches:
            logger.info(f"🔗 Fuzzy matching нашел {len(fuzzy_matches)} совпадений:")
            for match in fuzzy_matches[:10]:
                logger.info(match)
            if len(fuzzy_matches) > 10:
                logger.info(f"  ... и еще {len(fuzzy_matches) - 10}")
        
        # Log grouping results
        logger.info(f"📊 Уникальных групп товаров: {len(grouped)}")
        for name, items in list(grouped.items())[:10]:
            suppliers = [i['_supplier'] for i in items]
            unique_suppliers = set(suppliers)
            supplier_list = ", ".join(list(unique_suppliers)[:3])
            if len(unique_suppliers) > 3:
                supplier_list += f"... +{len(unique_suppliers) - 3}"
            logger.info(f"  '{name}' → {len(items)} вхождений от {len(unique_suppliers)} поставщиков ({supplier_list})")
        
        # Return all groups with 2+ items (including from same supplier)
        # User wants to see all products in project, not just cross-supplier comparisons
        comparable_groups = {
            name: items for name, items in grouped.items() 
            if len(items) > 1
        }
        
        # Count how many groups have multiple suppliers vs single supplier
        multi_supplier = sum(1 for items in comparable_groups.values() 
                           if len(set(i['_supplier'] for i in items)) > 1)
        single_supplier = len(comparable_groups) - multi_supplier
        
        logger.info(f"✅ Групп для анализа: {len(comparable_groups)} (от разных поставщиков: {multi_supplier}, варианты одного поставщика: {single_supplier})")
        
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
        Main method to compare all quotes in a project with intelligent grouping.
        
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
        
        # Group similar items using fuzzy matching (threshold 40% for better matching)
        grouped_items = self._group_similar_items(quotes, fuzzy_threshold=40.0)
        
        if not grouped_items:
            return {
                "status": "no_matches",
                "message": "Нет товаров для анализа (все товары уникальны)",
                "total_unique_items": sum(
                    len(supplier.get("items", [])) 
                    for quote in quotes 
                    for supplier in quote.get("suppliers", [])
                ),
                "item_comparisons": []
            }
        
        # Compare each group with LLM analysis
        comparisons = []
        total_savings = 0
        
        for item_name, item_group in grouped_items.items():
            unique_suppliers = len(set(item['_supplier'] for item in item_group))
            logger.info(f"🔍 Анализирую '{item_name}' ({len(item_group)} позиций от {unique_suppliers} поставщиков)")
            
            # Try LLM comparison first
            llm_result = await self._compare_item_group_with_llm(item_group, item_name)
            
            if llm_result:
                recommendation = llm_result
            else:
                # Fallback to simple comparison
                recommendation = self._simple_price_comparison(item_group)
            
            # Mark if this is a multi-supplier comparison or single supplier variants
            recommendation["is_multi_supplier"] = unique_suppliers > 1
            recommendation["supplier_count"] = unique_suppliers
            
            # Calculate savings
            prices = [item.get("normalized_price", 0) for item in item_group if item.get("normalized_price")]
            if prices:
                best_price = min(prices)
                worst_price = max(prices)
                savings_per_unit = worst_price - best_price
                avg_quantity = sum(item.get("normalized_quantity", 0) for item in item_group) / len(item_group)
                total_savings_estimate = savings_per_unit * avg_quantity if avg_quantity > 0 else 0
            else:
                savings_per_unit = 0
                total_savings_estimate = 0
            
            comparisons.append({
                "item_name": item_name,
                "suppliers_count": len(item_group),
                "recommendation": recommendation,
                "savings_per_unit": savings_per_unit,
                "total_savings_estimate": total_savings_estimate,
                "all_options": [
                    {
                        "supplier": item.get("_supplier"),
                        "price": item.get("normalized_price"),
                        "unit": item.get("normalized_unit"),
                        "quantity": item.get("normalized_quantity"),
                        "completeness": item.get("completeness_score", 0)
                    }
                    for item in item_group
                ]
            })
            
            if recommendation.get("price_difference_percent", 0) > 0:
                total_savings += recommendation.get("price_difference_percent", 0)
        
        avg_savings = total_savings / len(comparisons) if comparisons else 0
        
        return {
            "status": "success",
            "message": f"Найдено {len(comparisons)} товаров для сравнения",
            "items_compared": len(comparisons),
            "average_savings_percent": round(avg_savings, 1),
            "item_comparisons": comparisons,
            "generated_at": None
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
            Formatted text summary (HTML format)
        """
        if comparison_result.get("status") != "success":
            return comparison_result.get("message", "Нет данных для сравнения")
        
        comparisons = comparison_result.get("item_comparisons", [])
        avg_savings = comparison_result.get("average_savings_percent", 0)
        
        summary = f"""📊 <b>УМНОЕ СРАВНЕНИЕ ПРЕДЛОЖЕНИЙ</b>

Найдено товаров: {len(comparisons)}
Средняя экономия: {avg_savings:.1f}%

"""
        
        # Show detailed analysis for each item group
        summary += "🎯 <b>ДЕТАЛЬНЫЙ АНАЛИЗ:</b>\n\n"
        
        for i, comp in enumerate(comparisons[:10], 1):  # Top 10
            rec = comp["recommendation"]
            item_name = comp["item_name"]
            suppliers_count = comp["suppliers_count"]
            savings_per_unit = comp.get("savings_per_unit", 0)
            total_savings = comp.get("total_savings_estimate", 0)
            is_multi = rec.get("is_multi_supplier", False)
            
            # Shorten item name if too long
            if len(item_name) > 60:
                item_name = item_name[:57] + "..."
            
            # Different icons for multi-supplier vs single supplier
            icon = "🔄" if is_multi else "📦"
            summary += f"<b>{i}. {icon} {item_name}</b>\n"
            
            if is_multi:
                summary += f"📌 Сравнение: {suppliers_count} позиций от {rec.get('supplier_count', 1)} поставщиков\n"
            else:
                summary += f"📌 Варианты от одного поставщика: {suppliers_count} шт\n"
                
            summary += f"🥇 Лучший: {rec.get('recommended_supplier', 'N/A')}\n"
            summary += f"💰 Цена: {rec.get('recommended_price', 0):.2f} {rec.get('price_unit', '')}\n"
            
            if rec.get('price_difference_percent', 0) > 0:
                summary += f"💸 Экономия: {rec.get('price_difference_percent', 0):.1f}%"
                if savings_per_unit > 0:
                    summary += f" ({savings_per_unit:.2f} руб/ед)"
                if total_savings > 100:
                    summary += f"\n   На объем: ~{total_savings:,.0f} руб"
                summary += "\n"
            
            summary += f"📝 {rec.get('reasoning', 'Нет данных')}\n"
            
            # Show all suppliers for this item
            all_opts = comp.get("all_options", [])
            if len(all_opts) > 1:
                summary += "   Альтернативы:\n"
                for opt in sorted(all_opts, key=lambda x: x.get('price', float('inf')))[:3]:
                    if opt['supplier'] != rec.get('recommended_supplier'):
                        summary += f"   • {opt['supplier']}: {opt.get('price', 0):.2f} {opt.get('unit', '')}\n"
            
            summary += "\n"
        
        if len(comparisons) > 10:
            summary += f"... и еще {len(comparisons) - 10} товаров\n"
        
        return summary


# Global instance
quote_comparator = QuoteComparator()
