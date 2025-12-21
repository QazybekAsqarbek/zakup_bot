import logging
import re
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)


class UnitNormalizer:
    """
    Normalizes units of measurement to standard forms for comparison.
    Uses dictionary-based conversion for common units and LLM for complex cases.
    """
    
    # Standard units for each measurement type
    STANDARD_UNITS = {
        "weight": "кг",
        "length": "м",
        "area": "м2",
        "volume": "м3",
        "quantity": "шт",
        "time": "день"
    }
    
    # Conversion factors to standard units
    UNIT_CONVERSIONS = {
        # Weight conversions to kg
        "г": ("кг", 0.001),
        "грамм": ("кг", 0.001),
        "кг": ("кг", 1.0),
        "килограмм": ("кг", 1.0),
        "т": ("кг", 1000.0),
        "тонна": ("кг", 1000.0),
        "мг": ("кг", 0.000001),
        
        # Length conversions to m
        "мм": ("м", 0.001),
        "миллиметр": ("м", 0.001),
        "см": ("м", 0.01),
        "сантиметр": ("м", 0.01),
        "м": ("м", 1.0),
        "метр": ("м", 1.0),
        "км": ("м", 1000.0),
        "километр": ("м", 1000.0),
        
        # Area conversions to m2
        "мм2": ("м2", 0.000001),
        "см2": ("м2", 0.0001),
        "м2": ("м2", 1.0),
        "м²": ("м2", 1.0),
        "кв.м": ("м2", 1.0),
        "кв.м.": ("м2", 1.0),
        "квадратный метр": ("м2", 1.0),
        
        # Volume conversions to m3
        "мл": ("м3", 0.000001),
        "л": ("м3", 0.001),
        "литр": ("м3", 0.001),
        "м3": ("м3", 1.0),
        "м³": ("м3", 1.0),
        "куб.м": ("м3", 1.0),
        "кубический метр": ("м3", 1.0),
        
        # Quantity
        "шт": ("шт", 1.0),
        "штука": ("шт", 1.0),
        "штук": ("шт", 1.0),
        "шт.": ("шт", 1.0),
        "ед": ("шт", 1.0),
        "единица": ("шт", 1.0),
        "пара": ("шт", 2.0),
        "дюжина": ("шт", 12.0),
        
        # Time
        "день": ("день", 1.0),
        "д": ("день", 1.0),
        "дн": ("день", 1.0),
        "дней": ("день", 1.0),
        "неделя": ("день", 7.0),
        "нед": ("день", 7.0),
        "месяц": ("день", 30.0),
        "мес": ("день", 30.0),
        
        # Packaging units (will need LLM for conversion)
        "упаковка": ("упаковка", 1.0),
        "упак": ("упаковка", 1.0),
        "коробка": ("коробка", 1.0),
        "короб": ("коробка", 1.0),
        "паллета": ("паллета", 1.0),
        "поддон": ("паллета", 1.0),
        "рулон": ("рулон", 1.0),
        "мешок": ("мешок", 1.0),
        "пакет": ("пакет", 1.0),
    }
    
    def __init__(self):
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL
        )
    
    def _normalize_unit_string(self, unit: str) -> str:
        """Normalize unit string (lowercase, strip, remove dots)"""
        if not unit:
            return ""
        return unit.lower().strip().rstrip('.')
    
    def _simple_convert(self, quantity: float, unit: str) -> Optional[Tuple[float, str]]:
        """
        Try simple dictionary-based conversion.
        
        Returns:
            (normalized_quantity, normalized_unit) or None if not possible
        """
        normalized_unit = self._normalize_unit_string(unit)
        
        if normalized_unit in self.UNIT_CONVERSIONS:
            target_unit, factor = self.UNIT_CONVERSIONS[normalized_unit]
            normalized_quantity = quantity * factor
            return (normalized_quantity, target_unit)
        
        return None
    
    async def _llm_convert(self, item_name: str, quantity: float, unit: str, price: float) -> Optional[Dict]:
        """
        Use LLM for complex unit conversions (packages, boxes, etc.)
        
        Returns:
            Dictionary with normalized_quantity, normalized_unit, normalized_price
        """
        prompt = f"""Задача: Нормализовать единицы измерения для сравнения цен.

Товар: {item_name}
Количество: {quantity} {unit}
Цена: {price} за {unit}

Инструкции:
1. Если единица измерения - упаковка/коробка/рулон, попробуй определить количество штук внутри из названия товара
2. Переведи в базовую единицу (шт, кг, м, м2, м3)
3. Посчитай цену за единицу

Верни СТРОГО в формате JSON:
{{
  "normalized_quantity": <число>,
  "normalized_unit": "<единица>",
  "normalized_price": <цена за единицу>,
  "confidence": <0-1, насколько уверен в конверсии>
}}

Если невозможно нормализовать, верни confidence: 0 и оригинальные значения."""

        try:
            response = self.client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.0
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON
            import json
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
                
                if result.get("confidence", 0) > 0.3:
                    logger.info(f"✅ LLM conversion successful: {unit} -> {result['normalized_unit']}")
                    return result
                else:
                    logger.warning(f"⚠️ LLM conversion low confidence for {unit}")
                    return None
            
        except Exception as e:
            logger.error(f"❌ LLM conversion error: {e}")
        
        return None
    
    async def normalize_item(self, item: Dict) -> Dict:
        """
        Normalize an item's unit and recalculate price per unit.
        
        Args:
            item: Item dictionary with quantity, unit, price_per_unit
            
        Returns:
            Item with added normalized_quantity, normalized_unit, normalized_price
        """
        quantity = item.get("quantity", 0)
        unit = item.get("unit", "")
        price_per_unit = item.get("price_per_unit", 0)
        item_name = item.get("name", "")
        
        if not unit or not quantity:
            # No normalization possible
            item["normalized_quantity"] = quantity
            item["normalized_unit"] = unit
            item["normalized_price"] = price_per_unit
            return item
        
        # Try simple conversion first
        simple_result = self._simple_convert(quantity, unit)
        
        if simple_result:
            normalized_quantity, normalized_unit = simple_result
            
            # Recalculate price per normalized unit
            if normalized_quantity > 0:
                normalized_price = (price_per_unit * quantity) / normalized_quantity
            else:
                normalized_price = price_per_unit
            
            item["normalized_quantity"] = round(normalized_quantity, 4)
            item["normalized_unit"] = normalized_unit
            item["normalized_price"] = round(normalized_price, 2)
            
            logger.info(f"✅ Simple conversion: {quantity} {unit} -> {item['normalized_quantity']} {normalized_unit}")
            return item
        
        # If simple conversion failed, try LLM for complex units
        complex_units = ["упаковка", "коробка", "рулон", "мешок", "паллета", "поддон", "пакет"]
        normalized_unit_check = self._normalize_unit_string(unit)
        
        if any(cu in normalized_unit_check for cu in complex_units):
            logger.info(f"🤖 Attempting LLM conversion for complex unit: {unit}")
            llm_result = await self._llm_convert(item_name, quantity, unit, price_per_unit)
            
            if llm_result:
                item["normalized_quantity"] = round(llm_result["normalized_quantity"], 4)
                item["normalized_unit"] = llm_result["normalized_unit"]
                item["normalized_price"] = round(llm_result["normalized_price"], 2)
                return item
        
        # If all fails, keep original values
        logger.warning(f"⚠️ Could not normalize unit: {unit}")
        item["normalized_quantity"] = quantity
        item["normalized_unit"] = unit
        item["normalized_price"] = price_per_unit
        
        return item
    
    async def normalize_supplier_items(self, supplier: Dict) -> Dict:
        """
        Normalize all items for a supplier.
        
        Args:
            supplier: Supplier dictionary with items list
            
        Returns:
            Supplier with normalized items
        """
        items = supplier.get("items", [])
        normalized_items = []
        
        for item in items:
            normalized_item = await self.normalize_item(item)
            normalized_items.append(normalized_item)
        
        supplier["items"] = normalized_items
        return supplier
    
    async def normalize_quote(self, suppliers_data: List[Dict]) -> List[Dict]:
        """
        Normalize all suppliers in a quote.
        
        Args:
            suppliers_data: List of supplier dictionaries
            
        Returns:
            List of suppliers with normalized items
        """
        normalized_suppliers = []
        
        for supplier in suppliers_data:
            normalized_supplier = await self.normalize_supplier_items(supplier)
            normalized_suppliers.append(normalized_supplier)
        
        logger.info(f"✅ Normalized {len(normalized_suppliers)} suppliers")
        return normalized_suppliers


# Global instance
unit_normalizer = UnitNormalizer()
