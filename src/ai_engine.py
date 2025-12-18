import anthropic
import base64
import json
import re
import logging
from openai import OpenAI
from src.config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
)
# Импортируем наш новый конвертер
from src.file_converter import convert_file_to_text 

logger = logging.getLogger(__name__)

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)

SYSTEM_PROMPT = """
Ты — парсер коммерческих предложений. 
Твоя задача — извлечь данные о товарах, ценах и поставщике из предоставленного текста.
Верни ТОЛЬКО JSON объект.
Структура:
{
  "supplier_name": "Название поставщика",
  "items": [
    {"name": "Товар", "quantity": 0, "unit": "ед", "price_per_unit": 0, "currency": "RUB"}
  ]
}
Если данных несколько (разные поставщики), объедини их в один JSON или выбери основного.
"""

def extract_json_from_text(text):
    """Надежный экстрактор JSON."""
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception:
        return None

def process_content_with_ai(text_content=None, image_data=None, filename=None, media_type=None):
    """
    Главный роутер:
    1. Если PDF/Картинка -> Claude Vision.
    2. Если DOCX/XLSX/TXT -> Конвертация в текст -> DeepSeek.
    3. Если просто текст -> DeepSeek.
    """
    
    # --- ВЕТКА 1: CLAUDE VISION (PDF и Картинки) ---
    # Claude нативно поддерживает PDF и основные картинки
    is_claude_native = False
    if media_type == 'application/pdf':
        is_claude_native = True
    elif media_type and media_type.startswith('image/'):
        is_claude_native = True

    if image_data and is_claude_native:
        logger.info(f"🖼️ Native media detected ({media_type}). Routing to CLAUDE.")
        
        b64_data = base64.b64encode(image_data).decode('utf-8')
        content_block = []
        
        content_block.append({
            "type": "document" if media_type == 'application/pdf' else "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64_data
            }
        })
        content_block.append({"type": "text", "text": "Extract data to JSON."})

        try:
            response = anthropic_client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content_block}]
            )
            return extract_json_from_text(response.content[0].text)
        except Exception as e:
            logger.error(f"❌ Claude Error: {e}")
            return None

    # --- ВЕТКА 2: КОНВЕРТАЦИЯ ФАЙЛОВ (Word, Excel, MD...) ---
    converted_text = None
    if image_data and not is_claude_native and filename:
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
        logger.info(f"📝 Text content ready. Routing to DEEPSEEK.")
        try:
            response = deepseek_client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": final_text_input},
                ],
                max_tokens=4000,
                temperature=0.0,
                stream=False
            )
            return extract_json_from_text(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"❌ DeepSeek Error: {e}")
            return None

    logger.warning("⚠️ No processable content found.")
    return None