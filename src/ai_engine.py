import anthropic
import base64
import json
import re
import logging  # <--- Импорт
from openai import OpenAI
from src.config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
)

# Настройка логгера для этого модуля
logger = logging.getLogger(__name__)

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)

SYSTEM_PROMPT = """
Ты — профессиональный аналитик закупок. Твоя задача — извлечь данные из коммерческого предложения.
Верни СТРОГО валидный JSON. Не пиши никаких вводных слов.
Структура:
{
  "supplier_name": "Название поставщика",
  "items": [
    {"name": "Товар", "quantity": 0, "unit": "ед", "price_per_unit": 0, "currency": "RUB"}
  ]
}
"""

def clean_json_text(text):
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    return text.strip()

def process_content_with_ai(text_content=None, image_data=None, media_type=None):
    # ВАРИАНТ 1: CLAUDE
    if image_data:
        logger.info(f"🖼️ MEDIA DETECTED. Routing to ANTHROPIC ({ANTHROPIC_MODEL})")
        
        messages = []
        b64_image = base64.b64encode(image_data).decode('utf-8')
        
        messages.append({
            "role": "user", 
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type or "image/jpeg", "data": b64_image}
                },
                {"type": "text", "text": text_content if text_content else "Extract data"}
            ]
        })

        try:
            response = anthropic_client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=messages
            )
            raw_text = response.content[0].text
            logger.info("✅ Anthropic response received. Parsing JSON...")
            return json.loads(clean_json_text(raw_text))
            
        except Exception as e:
            logger.error(f"❌ Anthropic Error: {e}", exc_info=True)
            return None

    # ВАРИАНТ 2: DEEPSEEK
    elif text_content:
        logger.info(f"📝 TEXT ONLY. Routing to DEEPSEEK ({DEEPSEEK_MODEL})")
        logger.debug(f"Input text preview: {text_content[:50]}...") # Логгируем начало текста

        try:
            response = deepseek_client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text_content},
                ],
                max_tokens=4000,
                temperature=0.0,
                stream=False
            )
            
            raw_text = response.choices[0].message.content
            logger.info("✅ DeepSeek response received. Parsing JSON...")
            # logger.debug(f"Raw AI response: {raw_text}") # Раскомментируйте для глубокой отладки
            return json.loads(clean_json_text(raw_text))

        except Exception as e:
            logger.error(f"❌ DeepSeek Error: {e}", exc_info=True)
            return None
            
    return None