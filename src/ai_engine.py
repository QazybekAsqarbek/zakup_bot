import base64
import json
import re
import logging
from openai import OpenAI
from src.config import (
    OPEN_ROUTER_TOKEN, OPEN_ROUTER_BASE_URL, OPEN_ROUTER_MODEL,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
)
# Импортируем наш новый конвертер
from src.file_converter import convert_file_to_text 

logger = logging.getLogger(__name__)

openrouter_client = OpenAI(
    api_key=OPEN_ROUTER_TOKEN,
    base_url=OPEN_ROUTER_BASE_URL
)
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)

SYSTEM_PROMPT = """
Ты — AI-ассистент отдела закупок. Твоя задача — извлечь данные из файла (сметы, прайса, КП).
В одном файле может быть несколько поставщиков.

Верни СТРОГО валидный JSON следующей структуры:
[
  {
    "name": "Название Поставщика 1",
    "delivery_date": "срок поставки (если указан)",
    "vat_included": true/false (если указан НДС),
    "warranty": "гарантия (если указана)",
    "items": [
      {
        "name": "Название товара",
        "quantity": 10.0,
        "unit": "м2/шт",
        "price_per_unit": 100.50,
        "total_price": 1005.0,
        "currency": "RUB",
        "specs": {
           "color": "red",
           "size": "60x60",
           "brand": "Kerama",
           "article": "A-100",
           "material": "керамика",
           "manufacturer": "Kerama Marazzi"
        }
      }
    ]
  }
]

ВАЖНЫЕ ИНСТРУКЦИИ:
1. Поле "specs" используй для любых характеристик (размер, артикул, материал, вес, бренд, производитель, модель), которых нет в стандартных полях.
2. ОБЯЗАТЕЛЬНО извлекай характеристики товаров в "specs" - это критично для сравнения!
3. Если указана общая сумма, но не цена за единицу, посчитай: price_per_unit = total_price / quantity
4. Если указана цена за единицу, посчитай: total_price = price_per_unit * quantity
5. Извлекай информацию о сроках поставки, НДС, гарантии на уровне поставщика
6. Если поставщик не указан, назови его "Unknown Supplier".
7. Верни список поставщиков, даже если он один.
8. Будь максимально внимателен к деталям и характеристикам товаров!
"""

def extract_json_from_text(text):
    """Надежный экстрактор JSON."""
    try:
        # Remove markdown code blocks
        text = text.replace("```json", "").replace("```", "").strip()
        
        # Try to find JSON array first (for list of suppliers)
        array_match = re.search(r'\[.*\]', text, re.DOTALL)
        if array_match:
            return json.loads(array_match.group(0))
        
        # Then try to find JSON object
        obj_match = re.search(r'\{.*\}', text, re.DOTALL)
        if obj_match:
            return json.loads(obj_match.group(0))
        
        # Try to parse the whole text as JSON
        return json.loads(text)
    except Exception as e:
        logger.error(f"JSON extraction failed: {e}, text preview: {text[:200]}")
        return None

def process_content_with_ai(text_content=None, image_data=None, filename=None, media_type=None):
    """
    Главный роутер:
    1. Если PDF/Картинка -> Gemini Vision (через OpenRouter).
    2. Если DOCX/XLSX/TXT -> Конвертация в текст -> DeepSeek.
    3. Если просто текст -> DeepSeek.
    """
    
    # --- ВЕТКА 1: GEMINI VISION (PDF и Картинки) ---
    # Gemini через OpenRouter поддерживает PDF и основные картинки
    is_vision_native = False
    if media_type == 'application/pdf':
        is_vision_native = True
    elif media_type and media_type.startswith('image/'):
        is_vision_native = True

    if image_data and is_vision_native:
        logger.info(f"🖼️ Native media detected ({media_type}). Routing to GEMINI.")
        
        b64_data = base64.b64encode(image_data).decode('utf-8')
        
        # Формат для OpenAI-совместимого API (OpenRouter)
        image_url = f"data:{media_type};base64,{b64_data}"
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    },
                    {"type": "text", "text": "Extract data to JSON."}
                ]
            }
        ]

        try:
            response = openrouter_client.chat.completions.create(
                model=OPEN_ROUTER_MODEL,
                messages=messages,
                max_tokens=4000,
                temperature=0.0
            )
            return extract_json_from_text(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"❌ Gemini Error: {e}")
            return None

    # --- ВЕТКА 2: КОНВЕРТАЦИЯ ФАЙЛОВ (Word, Excel, MD...) ---
    converted_text = None
    if image_data and not is_vision_native and filename:
        # Пытаемся превратить файл в текст
        converted_text = convert_file_to_text(image_data, filename)
        if converted_text:
            logger.info(f"📄 File converted to text ({len(converted_text)} chars).")
            # Теперь это просто текст, который пойдет в DeepSeek

    # Объединяем входящий текст с конвертированным
    final_text_input = ""
    if text_content:
        final_text_input += text_content + "\n"
    if converted_text:
        final_text_input += converted_text

    # --- ВЕТКА 3: DEEPSEEK (Только текст) ---
    if final_text_input.strip():
        logger.info(f"📝 Text content ready ({len(final_text_input)} chars). Routing to DEEPSEEK.")
        try:
            logger.info("🤖 Calling DeepSeek API...")
            response = deepseek_client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": final_text_input},
                ],
                max_tokens=4000,
                temperature=0.0,
                stream=False,
                timeout=60.0  # 60 second timeout
            )
            logger.info("✅ DeepSeek response received")
            
            result = extract_json_from_text(response.choices[0].message.content)
            if result:
                logger.info(f"✅ JSON extracted successfully")
                return result
            else:
                logger.error(f"❌ Failed to extract JSON from response: {response.choices[0].message.content[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ DeepSeek Error: {e}", exc_info=True)
            return None

    logger.warning("⚠️ No processable content found.")
    return None