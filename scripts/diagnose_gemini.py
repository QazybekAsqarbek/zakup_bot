#!/usr/bin/env python3
"""
Диагностический скрипт для проверки проблем с Gemini API через OpenRouter.
Проверяет подключение, API ключ, формат запросов и обработку изображений.
"""

import os
import sys
import base64
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import requests
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
OPEN_ROUTER_TOKEN = os.getenv("OPEN_ROUTER_TOKEN")
OPEN_ROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPEN_ROUTER_MODEL = "google/gemini-2.0-flash-001"

def print_section(title):
    """Печатает заголовок секции."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def check_env_variables():
    """Проверка переменных окружения."""
    print_section("1. Проверка переменных окружения")
    
    # Проверка наличия .env файла
    env_file = Path(".env")
    if env_file.exists():
        print(f"✅ Файл .env найден: {env_file.absolute()}")
    else:
        print(f"⚠️ Файл .env не найден в корне проекта")
        print(f"   Создайте файл .env с переменной OPEN_ROUTER_TOKEN")
    
    if not OPEN_ROUTER_TOKEN:
        print("❌ OPEN_ROUTER_TOKEN не установлен!")
        print("   Установите переменную в .env файле или через export")
        print("   Формат в .env: OPEN_ROUTER_TOKEN=your_token_here")
        return False
    
    print(f"✅ OPEN_ROUTER_TOKEN найден (длина: {len(OPEN_ROUTER_TOKEN)} символов)")
    print(f"   Первые 10 символов: {OPEN_ROUTER_TOKEN[:10]}...")
    
    # Проверка формата токена (обычно начинается с sk-)
    if OPEN_ROUTER_TOKEN.startswith("sk-"):
        print("   ✅ Формат токена выглядит корректно (начинается с sk-)")
    else:
        print("   ⚠️ Токен не начинается с 'sk-', проверьте правильность")
    
    return True

def check_network_connectivity():
    """Проверка сетевого подключения."""
    print_section("2. Проверка сетевого подключения")
    
    try:
        response = requests.get("https://openrouter.ai", timeout=10)
        print(f"✅ OpenRouter доступен (статус: {response.status_code})")
        return True
    except requests.exceptions.Timeout:
        print("❌ Таймаут при подключении к OpenRouter")
        print("   Проверьте интернет-соединение")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Ошибка подключения к OpenRouter: {e}")
        print("   Проверьте интернет-соединение и настройки прокси")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

def check_api_key_validity():
    """Проверка валидности API ключа."""
    print_section("3. Проверка валидности API ключа")
    
    try:
        headers = {
            "Authorization": f"Bearer {OPEN_ROUTER_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Простой запрос для проверки ключа
        response = requests.get(
            f"{OPEN_ROUTER_BASE_URL}/models",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ API ключ валиден")
            models = response.json().get("data", [])
            gemini_models = [m for m in models if "gemini" in m.get("id", "").lower()]
            if gemini_models:
                print(f"   Найдено моделей Gemini: {len(gemini_models)}")
                for model in gemini_models[:3]:
                    print(f"   - {model.get('id')}")
            return True
        elif response.status_code == 401:
            print("❌ API ключ невалиден или истек срок действия")
            print(f"   Ответ сервера: {response.text[:200]}")
            return False
        else:
            print(f"⚠️ Неожиданный статус: {response.status_code}")
            print(f"   Ответ: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при проверке API ключа: {e}")
        return False

def test_simple_text_request():
    """Тест простого текстового запроса."""
    print_section("4. Тест простого текстового запроса")
    
    try:
        client = OpenAI(
            api_key=OPEN_ROUTER_TOKEN,
            base_url=OPEN_ROUTER_BASE_URL
        )
        
        print(f"📤 Отправка запроса к модели: {OPEN_ROUTER_MODEL}")
        start_time = time.time()
        
        response = client.chat.completions.create(
            model=OPEN_ROUTER_MODEL,
            messages=[
                {"role": "user", "content": "Скажи 'Привет' одним словом."}
            ],
            max_tokens=10,
            timeout=30.0
        )
        
        elapsed = time.time() - start_time
        content = response.choices[0].message.content
        
        print(f"✅ Запрос успешен (время: {elapsed:.2f}с)")
        print(f"   Ответ: {content}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при текстовом запросе: {e}")
        print(f"   Тип ошибки: {type(e).__name__}")
        if hasattr(e, 'response'):
            print(f"   Статус ответа: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}")
        return False

def create_test_image():
    """Создает простое тестовое изображение (1x1 пиксель PNG)."""
    # Минимальный валидный PNG (1x1 пиксель, прозрачный)
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return png_data

def test_image_request():
    """Тест запроса с изображением."""
    print_section("5. Тест запроса с изображением")
    
    try:
        # Создаем тестовое изображение
        image_data = create_test_image()
        b64_data = base64.b64encode(image_data).decode('utf-8')
        image_url = f"data:image/png;base64,{b64_data}"
        
        print(f"📤 Отправка запроса с изображением (размер: {len(image_data)} байт)")
        print(f"   Base64 длина: {len(b64_data)} символов")
        
        client = OpenAI(
            api_key=OPEN_ROUTER_TOKEN,
            base_url=OPEN_ROUTER_BASE_URL
        )
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    },
                    {"type": "text", "text": "Что на этом изображении? Ответь одним словом."}
                ]
            }
        ]
        
        start_time = time.time()
        
        response = client.chat.completions.create(
            model=OPEN_ROUTER_MODEL,
            messages=messages,
            max_tokens=50,
            timeout=60.0
        )
        
        elapsed = time.time() - start_time
        content = response.choices[0].message.content
        
        print(f"✅ Запрос с изображением успешен (время: {elapsed:.2f}с)")
        print(f"   Ответ: {content}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при запросе с изображением: {e}")
        print(f"   Тип ошибки: {type(e).__name__}")
        
        # Детальная диагностика
        error_str = str(e).lower()
        
        if "connection" in error_str or "connect" in error_str:
            print("\n   🔍 Детали ошибки подключения:")
            print("   - Проверьте интернет-соединение")
            print("   - Проверьте настройки прокси/firewall")
            print("   - Возможно, OpenRouter временно недоступен")
            print("   - Попробуйте: ping openrouter.ai")
        
        if "timeout" in error_str:
            print("\n   🔍 Проблема с таймаутом:")
            print("   - Запрос слишком долгий")
            print("   - Попробуйте уменьшить размер изображения")
            print("   - Увеличьте timeout в ai_engine.py (сейчас 60 сек)")
        
        if "401" in error_str or "unauthorized" in error_str:
            print("\n   🔍 Проблема с авторизацией:")
            print("   - Проверьте правильность API ключа")
            print("   - Проверьте баланс на https://openrouter.ai/")
            print("   - Проверьте, не истек ли срок действия ключа")
        
        if "400" in error_str or "bad request" in error_str:
            print("\n   🔍 Проблема с форматом запроса:")
            print("   - Проверьте формат base64 изображения")
            print("   - Проверьте размер изображения (лимиты API)")
            print("   - Проверьте media_type в запросе")
            print("   - Убедитесь, что изображение не повреждено")
        
        if "rate limit" in error_str or "429" in error_str:
            print("\n   🔍 Проблема с лимитами:")
            print("   - Превышен лимит запросов")
            print("   - Подождите несколько минут")
            print("   - Проверьте план подписки на OpenRouter")
        
        # Вывод полного traceback для отладки
        import traceback
        print("\n   📋 Полный traceback:")
        print("   " + "\n   ".join(traceback.format_exc().split("\n")))
        
        return False

def test_large_image_request():
    """Тест с большим изображением для проверки лимитов."""
    print_section("6. Тест с большим изображением (проверка лимитов)")
    
    try:
        # Создаем большее тестовое изображение (100x100)
        from PIL import Image
        import io
        
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        image_data = img_bytes.getvalue()
        
        b64_data = base64.b64encode(image_data).decode('utf-8')
        image_url = f"data:image/png;base64,{b64_data}"
        
        print(f"📤 Отправка запроса с изображением (размер: {len(image_data)} байт)")
        print(f"   Base64 длина: {len(b64_data)} символов")
        
        if len(b64_data) > 1000000:  # ~1MB
            print("⚠️ Изображение очень большое, может быть отклонено")
        
        client = OpenAI(
            api_key=OPEN_ROUTER_TOKEN,
            base_url=OPEN_ROUTER_BASE_URL
        )
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    },
                    {"type": "text", "text": "Какой цвет на изображении?"}
                ]
            }
        ]
        
        start_time = time.time()
        
        response = client.chat.completions.create(
            model=OPEN_ROUTER_MODEL,
            messages=messages,
            max_tokens=50,
            timeout=60.0
        )
        
        elapsed = time.time() - start_time
        content = response.choices[0].message.content
        
        print(f"✅ Запрос с большим изображением успешен (время: {elapsed:.2f}с)")
        print(f"   Ответ: {content}")
        return True
        
    except ImportError:
        print("⚠️ PIL не установлен, пропускаем тест с большим изображением")
        print("   Установите: pip install Pillow")
        return None
    except Exception as e:
        print(f"❌ Ошибка при запросе с большим изображением: {e}")
        print(f"   Тип ошибки: {type(e).__name__}")
        return False

def check_model_availability():
    """Проверка доступности конкретной модели."""
    print_section("7. Проверка доступности модели Gemini")
    
    try:
        headers = {
            "Authorization": f"Bearer {OPEN_ROUTER_TOKEN}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{OPEN_ROUTER_BASE_URL}/models",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            models = response.json().get("data", [])
            target_model = None
            
            for model in models:
                if model.get("id") == OPEN_ROUTER_MODEL:
                    target_model = model
                    break
            
            if target_model:
                print(f"✅ Модель {OPEN_ROUTER_MODEL} доступна")
                print(f"   Название: {target_model.get('name', 'N/A')}")
                print(f"   Контекст: {target_model.get('context_length', 'N/A')} токенов")
                
                # Проверка поддержки vision
                if target_model.get("supports_vision"):
                    print("   ✅ Поддерживает vision (изображения)")
                else:
                    print("   ⚠️ Может не поддерживать vision")
                
                return True
            else:
                print(f"❌ Модель {OPEN_ROUTER_MODEL} не найдена")
                print("   Доступные модели Gemini:")
                gemini_models = [m for m in models if "gemini" in m.get("id", "").lower()]
                for model in gemini_models[:5]:
                    print(f"   - {model.get('id')}")
                return False
        else:
            print(f"❌ Не удалось получить список моделей: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при проверке модели: {e}")
        return False

def test_real_file(file_path):
    """Тест с реальным файлом изображения."""
    print_section(f"8. Тест с реальным файлом: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"⚠️ Файл не найден: {file_path}")
        print("   Пропускаем тест")
        return None
    
    try:
        with open(file_path, 'rb') as f:
            image_data = f.read()
        
        file_size_mb = len(image_data) / (1024 * 1024)
        print(f"📁 Размер файла: {file_size_mb:.2f} MB")
        
        if file_size_mb > 20:
            print("⚠️ Файл очень большой, может быть отклонен API")
        
        b64_data = base64.b64encode(image_data).decode('utf-8')
        image_url = f"data:image/png;base64,{b64_data}"
        
        print(f"📤 Отправка запроса (base64 длина: {len(b64_data)} символов)")
        
        client = OpenAI(
            api_key=OPEN_ROUTER_TOKEN,
            base_url=OPEN_ROUTER_BASE_URL
        )
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    },
                    {"type": "text", "text": "Опиши это изображение кратко."}
                ]
            }
        ]
        
        start_time = time.time()
        
        response = client.chat.completions.create(
            model=OPEN_ROUTER_MODEL,
            messages=messages,
            max_tokens=100,
            timeout=120.0
        )
        
        elapsed = time.time() - start_time
        content = response.choices[0].message.content
        
        print(f"✅ Запрос успешен (время: {elapsed:.2f}с)")
        print(f"   Ответ: {content[:200]}...")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при обработке файла: {e}")
        print(f"   Тип ошибки: {type(e).__name__}")
        return False

def main():
    """Главная функция диагностики."""
    print("\n" + "=" * 60)
    print("  ДИАГНОСТИКА GEMINI API (OpenRouter)")
    print("=" * 60)
    
    results = {}
    
    # Запускаем все проверки
    results['env'] = check_env_variables()
    if not results['env']:
        print("\n❌ Критическая ошибка: переменные окружения не настроены")
        print("   Создайте .env файл с OPEN_ROUTER_TOKEN")
        return
    
    results['network'] = check_network_connectivity()
    if not results['network']:
        print("\n❌ Критическая ошибка: нет сетевого подключения")
        return
    
    results['api_key'] = check_api_key_validity()
    if not results['api_key']:
        print("\n❌ Критическая ошибка: API ключ невалиден")
        return
    
    results['model'] = check_model_availability()
    
    results['text'] = test_simple_text_request()
    results['image'] = test_image_request()
    
    # Опциональные тесты
    results['large_image'] = test_large_image_request()
    
    # Если передан путь к файлу, тестируем его
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        results['real_file'] = test_real_file(file_path)
    
    # Итоговый отчет
    print_section("ИТОГОВЫЙ ОТЧЕТ")
    
    critical_tests = ['env', 'network', 'api_key']
    optional_tests = ['model', 'text', 'image', 'large_image', 'real_file']
    
    all_critical_ok = all(results.get(test, False) for test in critical_tests)
    
    if all_critical_ok:
        print("✅ Все критические проверки пройдены")
    else:
        print("❌ Некоторые критические проверки не пройдены")
    
    print("\nДетали:")
    for test_name in critical_tests + optional_tests:
        if test_name in results:
            status = results[test_name]
            if status is True:
                print(f"  ✅ {test_name}")
            elif status is False:
                print(f"  ❌ {test_name}")
            else:
                print(f"  ⚠️ {test_name} (пропущен)")
    
    # Рекомендации
    print_section("РЕКОМЕНДАЦИИ")
    
    if not results.get('image', True):
        print("""
🔧 Если запросы с изображениями не работают:

1. Проверьте размер изображения:
   - OpenRouter может иметь лимиты на размер
   - Попробуйте уменьшить изображение перед отправкой

2. Проверьте формат изображения:
   - Поддерживаются: PNG, JPEG, GIF, WebP
   - Убедитесь, что файл не поврежден

3. Проверьте base64 кодирование:
   - Убедитесь, что данные корректно закодированы
   - Проверьте, что media_type правильный

4. Проверьте таймауты:
   - Увеличьте timeout для больших изображений
   - Проверьте сетевую задержку

5. Проверьте логи в ai_engine.py:
   - Включите детальное логирование
   - Проверьте точное сообщение об ошибке
        """)
    
    if not results.get('network', True):
        print("""
🔧 Проблемы с сетью:

1. Проверьте интернет-соединение
2. Проверьте настройки прокси
3. Проверьте firewall/антивирус
4. Попробуйте другой DNS сервер
        """)

if __name__ == "__main__":
    main()

