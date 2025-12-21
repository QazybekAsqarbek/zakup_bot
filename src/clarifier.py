import logging
from typing import Dict, List
from openai import OpenAI
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)


class AutoClarifier:
    """
    Detects missing critical information in quotes and generates
    professional clarification requests to suppliers.
    """
    
    # Required fields by category
    REQUIRED_FIELDS = {
        "all": {
            "price_per_unit": "Цена за единицу",
            "unit": "Единица измерения",
            "quantity": "Количество"
        },
        "строительные материалы": {
            "delivery_date": "Срок поставки",
            "vat_included": "НДС включен",
            "certificate": "Сертификат качества"
        },
        "электроника": {
            "warranty": "Гарантия",
            "origin_country": "Страна производства",
            "delivery_date": "Срок поставки"
        },
        "мебель": {
            "delivery_date": "Срок поставки",
            "assembly_required": "Требуется сборка",
            "warranty": "Гарантия"
        },
        "инструменты": {
            "warranty": "Гарантия",
            "delivery_date": "Срок поставки",
            "service_center": "Сервисный центр"
        },
        "офисные товары": {
            "delivery_date": "Срок поставки",
            "min_order": "Минимальный заказ"
        },
        "расходные материалы": {
            "delivery_date": "Срок поставки",
            "shelf_life": "Срок годности",
            "storage_conditions": "Условия хранения"
        },
        "сантехника": {
            "warranty": "Гарантия",
            "delivery_date": "Срок поставки",
            "installation_included": "Монтаж включен"
        },
        "электрооборудование": {
            "warranty": "Гарантия",
            "certification": "Сертификация",
            "delivery_date": "Срок поставки"
        }
    }
    
    def __init__(self):
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL
        )
    
    def detect_missing_fields(self, quote: Dict, category: str = "общее") -> Dict:
        """
        Detect missing required fields in a quote.
        
        Args:
            quote: Quote document with suppliers
            category: Product category
            
        Returns:
            Dictionary mapping supplier name to list of missing fields
        """
        missing_by_supplier = {}
        
        # Get required fields for this category
        required_fields = self.REQUIRED_FIELDS.get("all", {}).copy()
        if category in self.REQUIRED_FIELDS:
            required_fields.update(self.REQUIRED_FIELDS[category])
        
        suppliers = quote.get("suppliers", [])
        
        for supplier in suppliers:
            supplier_name = supplier.get("name", "Unknown")
            missing_fields = []
            
            items = supplier.get("items", [])
            if not items:
                continue
            
            # Check first item as representative (assuming homogeneous missing data)
            sample_item = items[0]
            
            # Check item-level fields
            for field_key, field_name in required_fields.items():
                if field_key in ["price_per_unit", "unit", "quantity"]:
                    # Check in item
                    if not sample_item.get(field_key):
                        missing_fields.append(field_name)
            
            # Check supplier-level fields
            supplier_level_fields = [
                "delivery_date", "vat_included", "warranty",
                "certificate", "origin_country", "assembly_required",
                "service_center", "min_order", "shelf_life",
                "storage_conditions", "installation_included", "certification"
            ]
            
            for field_key, field_name in required_fields.items():
                if field_key in supplier_level_fields:
                    # Check in supplier data
                    if not supplier.get(field_key):
                        # Also check in item specs
                        if field_key not in sample_item.get("specs", {}):
                            missing_fields.append(field_name)
            
            if missing_fields:
                missing_by_supplier[supplier_name] = missing_fields
        
        return missing_by_supplier
    
    async def generate_clarification_message(self, supplier_name: str, 
                                            missing_fields: List[str],
                                            project_name: str = None) -> str:
        """
        Generate a professional clarification request message.
        
        Args:
            supplier_name: Name of the supplier
            missing_fields: List of missing field names
            project_name: Name of the project (optional)
            
        Returns:
            Formatted clarification message in Russian
        """
        context = f"проекта '{project_name}'" if project_name else "вашего коммерческого предложения"
        
        prompt = f"""Составь профессиональное деловое письмо на русском языке для запроса уточнений у поставщика.

Контекст:
- Поставщик: {supplier_name}
- Проект: {context}
- Отсутствующая информация: {', '.join(missing_fields)}

Требования к письму:
1. Вежливый и профессиональный тон
2. Краткое и по делу
3. Четкий список того, что нужно уточнить
4. Благодарность за сотрудничество

Верни ТОЛЬКО текст письма без лишних пояснений."""

        try:
            response = self.client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            message = response.choices[0].message.content.strip()
            logger.info(f"✅ Generated clarification message for {supplier_name}")
            return message
            
        except Exception as e:
            logger.error(f"❌ Error generating clarification message: {e}")
            
            # Fallback to template
            return self._template_clarification_message(supplier_name, missing_fields)
    
    def _template_clarification_message(self, supplier_name: str, 
                                       missing_fields: List[str]) -> str:
        """
        Fallback template for clarification message.
        """
        message = f"""Уважаемый {supplier_name},

Благодарим за предоставленное коммерческое предложение.

Для принятия решения нам необходимо уточнить следующую информацию:

"""
        for i, field in enumerate(missing_fields, 1):
            message += f"{i}. {field}\n"
        
        message += """
Просим предоставить указанные данные в ближайшее время.

С уважением,
Отдел закупок"""
        
        return message
    
    async def generate_all_clarifications(self, quotes_with_missing: List[Dict],
                                         project_name: str = None) -> List[Dict]:
        """
        Generate clarification messages for all quotes with missing data.
        
        Args:
            quotes_with_missing: List of quote documents with missing_fields
            project_name: Name of the project
            
        Returns:
            List of dictionaries with supplier, missing_fields, and message
        """
        clarifications = []
        
        for quote in quotes_with_missing:
            missing_by_supplier = quote.get("missing_fields", {})
            
            for supplier_name, missing_fields in missing_by_supplier.items():
                if missing_fields:
                    message = await self.generate_clarification_message(
                        supplier_name, missing_fields, project_name
                    )
                    
                    clarifications.append({
                        "quote_id": str(quote.get("_id")),
                        "source_file": quote.get("source_file"),
                        "supplier": supplier_name,
                        "missing_fields": missing_fields,
                        "message": message
                    })
        
        return clarifications


# Global instance
auto_clarifier = AutoClarifier()
