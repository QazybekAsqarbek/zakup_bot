import logging
from typing import Dict, List, Optional
from openai import OpenAI
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

class CategoryIntelligence:
    """
    Manages product category detection and suggests important fields
    for different product categories to enhance data extraction quality.
    """
    
    # Predefined category mappings with important fields
    CATEGORY_MAPPINGS = {
        "строительные материалы": [
            "size", "dimensions", "material", "grade", "class", 
            "manufacturer", "color", "thickness", "density"
        ],
        "электроника": [
            "model", "brand", "warranty", "voltage", "power",
            "frequency", "capacity", "interface", "compatibility"
        ],
        "мебель": [
            "dimensions", "material", "color", "weight_capacity",
            "assembly_required", "style", "finish"
        ],
        "инструменты": [
            "brand", "model", "power", "voltage", "weight",
            "warranty", "accessories_included", "max_capacity"
        ],
        "офисные товары": [
            "brand", "model", "size", "color", "material",
            "capacity", "format"
        ],
        "расходные материалы": [
            "brand", "model", "compatibility", "yield",
            "color", "type", "package_quantity"
        ],
        "сантехника": [
            "material", "size", "connection_type", "pressure_rating",
            "manufacturer", "finish", "mounting_type"
        ],
        "электрооборудование": [
            "voltage", "current", "power", "protection_class",
            "mounting_type", "brand", "certification"
        ]
    }
    
    def __init__(self):
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL
        )
        self._category_cache = {}
    
    async def detect_category(self, items: List[Dict]) -> str:
        """
        Detect the most likely product category based on item names and specs.
        
        Args:
            items: List of items with name and specs
            
        Returns:
            Category name (Russian)
        """
        if not items:
            return "общее"
        
        # Create a sample of item names for analysis
        item_names = [item.get("name", "") for item in items[:10]]  # First 10 items
        sample_text = "\n".join(item_names)
        
        # Check cache
        cache_key = hash(sample_text)
        if cache_key in self._category_cache:
            logger.info(f"✅ Category from cache: {self._category_cache[cache_key]}")
            return self._category_cache[cache_key]
        
        prompt = f"""Определи категорию товаров из этого списка. Верни ТОЛЬКО название категории (одно из):
- строительные материалы
- электроника
- мебель
- инструменты
- офисные товары
- расходные материалы
- сантехника
- электрооборудование
- общее (если не подходит ни одна категория)

Список товаров:
{sample_text}

Ответ (только название категории):"""

        try:
            response = self.client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.0
            )
            
            category = response.choices[0].message.content.strip().lower()
            
            # Validate category
            if category not in self.CATEGORY_MAPPINGS:
                category = "общее"
            
            # Cache result
            self._category_cache[cache_key] = category
            
            logger.info(f"🔍 Detected category: {category}")
            return category
            
        except Exception as e:
            logger.error(f"❌ Category detection error: {e}")
            return "общее"
    
    def suggest_important_fields(self, category: str) -> List[str]:
        """
        Get list of important fields for a given category.
        
        Args:
            category: Product category name
            
        Returns:
            List of important field names
        """
        return self.CATEGORY_MAPPINGS.get(category, [])
    
    async def validate_category_specs(self, item: Dict, category: str) -> Dict:
        """
        Check if item has important specs for its category and calculate completeness.
        
        Args:
            item: Item dictionary with specs
            category: Product category
            
        Returns:
            Dictionary with missing_specs and completeness_score
        """
        important_fields = self.suggest_important_fields(category)
        
        if not important_fields:
            return {
                "missing_specs": [],
                "completeness_score": 1.0,
                "has_specs": []
            }
        
        item_specs = item.get("specs", {})
        spec_keys = set(item_specs.keys())
        important_set = set(important_fields)
        
        # Check which important fields are present
        has_specs = list(important_set.intersection(spec_keys))
        missing_specs = list(important_set - spec_keys)
        
        # Calculate completeness score
        if important_fields:
            completeness_score = len(has_specs) / len(important_fields)
        else:
            completeness_score = 1.0
        
        return {
            "missing_specs": missing_specs,
            "completeness_score": round(completeness_score, 2),
            "has_specs": has_specs
        }
    
    async def enrich_specs_with_category(self, items: List[Dict], category: str) -> List[Dict]:
        """
        Add category-specific validation to items.
        
        Args:
            items: List of items
            category: Product category
            
        Returns:
            Items with added completeness_score
        """
        enriched_items = []
        
        for item in items:
            validation = await self.validate_category_specs(item, category)
            item["completeness_score"] = validation["completeness_score"]
            item["missing_specs"] = validation["missing_specs"]
            enriched_items.append(item)
        
        return enriched_items


# Global instance
category_intelligence = CategoryIntelligence()
