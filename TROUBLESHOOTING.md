# Troubleshooting Guide

## Commands Not Responding

### Issue: `/compare`, `/clarify`, `/analysis` don't respond

**Причина**: Бот не был перезапущен после добавления новых команд.

**Решение**:
```bash
# 1. Остановите бот (Ctrl+C в терминале где он запущен)
# 2. Перезапустите бот
python src/main.py
```

После перезапуска вы должны увидеть в логах:
```
✅ Database connected & Commands set
Bot is running...
```

### Проверка команд в Telegram

После перезапуска:
1. Откройте бот в Telegram
2. Нажмите на кнопку "Меню" (☰) рядом с полем ввода
3. Вы должны увидеть все команды:
   - 🚀 Начало
   - 📁 Новый проект
   - 🏆 Сравнить предложения
   - 📝 Запросить уточнения
   - 📊 Полный анализ
   - 📥 Скачать Excel
   - ❓ Справка

## Common Errors

### 1. "В проекте нет данных для сравнения"

**Причина**: Недостаточно данных для сравнения.

**Требования для сравнения**:
- Минимум 2 файла от разных поставщиков
- Похожие названия товаров в файлах
- Например: "Плитка 50x50" и "плитка керамическая 50x50" будут сгруппированы

**Решение**:
1. Загрузите минимум 2 файла с КП
2. Убедитесь, что есть одинаковые/похожие товары
3. Попробуйте снова `/compare`

### 2. "✅ Все данные полные! Уточнения не требуются"

**Это не ошибка!** Означает, что все обязательные поля заполнены.

Обязательные поля по категориям:
- **Все товары**: цена, единица измерения, количество
- **Стройматериалы**: срок поставки, НДС, сертификат
- **Электроника**: гарантия, страна производства, срок поставки

### 3. MongoDB Connection Error

```
pymongo.errors.ServerSelectionTimeoutError
```

**Решение**:
```bash
# Убедитесь что MongoDB запущен
docker-compose up -d

# Или если локально
mongod

# Проверьте подключение
mongo
```

### 4. API Key Errors

```
anthropic.APIError: Invalid API key
```

**Решение**:
1. Проверьте файл `.env`:
   ```env
   ANTHROPIC_API_KEY=sk-ant-ваш-ключ
   DEEPSEEK_API_KEY=ваш-ключ
   ```
2. Убедитесь, что нет пробелов вокруг ключей
3. Перезапустите бот

### 5. "Ошибка при сохранении"

**Причины**:
- Файл не поддерживается (проверьте формат)
- AI не смог извлечь данные
- Проблемы с MongoDB

**Решение**:
1. Проверьте логи в терминале
2. Убедитесь, что файл содержит структурированные данные
3. Попробуйте другой формат (Excel вместо PDF)

## Debug Mode

Для более подробных логов, измените в `src/main.py`:

```python
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Изменить с INFO на DEBUG
)
```

## Testing Commands Manually

### Test 1: Basic Command Response

```python
# Запустите Python REPL
python

>>> from src.database import db
>>> db.connect()
>>> # Если нет ошибок - MongoDB работает
```

### Test 2: Check Projects

```python
import asyncio
from src.database import db

async def test():
    db.connect()
    projects = await db.get_user_projects(123456)  # ваш user_id
    print(projects)

asyncio.run(test())
```

### Test 3: Check Imports

```python
# Все импорты должны работать без ошибок
from src.category_intelligence import category_intelligence
from src.unit_normalizer import unit_normalizer
from src.clarifier import auto_clarifier
from src.comparator import quote_comparator

print("✅ All imports successful")
```

## Logs Interpretation

### Good Logs (Normal Operation)
```
INFO - 🔥 Connected to MongoDB: smartprocure
INFO - ✅ Database connected & Commands set
INFO - Bot is running...
INFO - 📁 Detected category: строительные материалы
INFO - ✅ Simple conversion: 100 м2 -> 100.0 м2
INFO - ✅ Normalized 1 suppliers
```

### Bad Logs (Errors to Fix)
```
ERROR - ❌ DeepSeek Error: Invalid API key
ERROR - ❌ MongoDB connection failed
ERROR - Compare command error: 'NoneType' object has no attribute 'get'
```

## Performance Issues

### Bot Responds Slowly

**Причины**:
- LLM API медленно отвечает
- Большой файл обрабатывается
- Много товаров для сравнения

**Нормальное время**:
- Парсинг файла: 3-10 секунд
- Сравнение 20 товаров: 5-15 секунд
- Генерация уточнений: 2-5 секунд

### Out of Memory

Если файлы очень большие (>10MB):
```python
# В src/ai_engine.py можно уменьшить max_tokens
response = deepseek_client.chat.completions.create(
    model=DEEPSEEK_MODEL,
    messages=[...],
    max_tokens=2000,  # Уменьшить с 4000
    ...
)
```

## Still Having Issues?

1. **Check Python version**: `python --version` (должен быть 3.10+)
2. **Reinstall dependencies**: `pip install -r requirements.txt --upgrade`
3. **Clear MongoDB data**: 
   ```javascript
   mongo
   use smartprocure
   db.dropDatabase()
   ```
4. **Check Telegram Bot Token**: Убедитесь что бот не заблокирован
5. **Review full logs**: Запустите с DEBUG уровнем логирования

## Quick Health Check

Выполните эту команду для проверки всей системы:

```bash
# Проверка всех компонентов
python -c "
from src.config import TELEGRAM_TOKEN, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, MONGO_URL
from src.database import db
from src.category_intelligence import category_intelligence
from src.unit_normalizer import unit_normalizer
from src.clarifier import auto_clarifier
from src.comparator import quote_comparator

print('✅ Config loaded')
print(f'✅ Telegram token: {TELEGRAM_TOKEN[:10]}...')
print(f'✅ Anthropic key: {ANTHROPIC_API_KEY[:10] if ANTHROPIC_API_KEY else \"NOT SET\"}...')
print(f'✅ DeepSeek key: {DEEPSEEK_API_KEY[:10] if DEEPSEEK_API_KEY else \"NOT SET\"}...')
print(f'✅ MongoDB URL: {MONGO_URL}')
print('✅ All modules imported successfully')
print('\\n🎉 System health check PASSED!')
"
```

Если все ✅, ваша система готова к работе!

## Contact Support

Если проблема не решается:
1. Сохраните логи из терминала
2. Опишите, что делали перед ошибкой
3. Приложите скриншот ошибки
4. Укажите версию Python: `python --version`
