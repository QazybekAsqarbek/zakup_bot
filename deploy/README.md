# Деплой и запуск

Эта папка содержит все файлы, необходимые для деплоя и запуска бота через Docker.

## 📁 Структура

- `Dockerfile` - образ для сборки бота
- `docker-compose.yaml` - для локальной разработки
- `docker-compose.prod.yml` - для продакшн деплоя
- `.github/workflows/deploy.yml` - GitHub Actions workflow для автоматического деплоя

## 🚀 Локальный запуск

### Вариант 1: Из корня проекта (рекомендуется)

```bash
# Из корня проекта
cd /Users/nspeganov/IdeaProjects/zakup_bot

# Запуск в фоне
docker-compose -f deploy/docker-compose.yaml up -d

# Просмотр логов
docker-compose -f deploy/docker-compose.yaml logs -f bot

# Остановка
docker-compose -f deploy/docker-compose.yaml down
```

### Вариант 2: Из папки deploy

```bash
# Перейти в папку deploy
cd deploy

# Запуск в фоне
docker-compose -f docker-compose.yaml up -d

# Просмотр логов
docker-compose -f docker-compose.yaml logs -f bot

# Остановка
docker-compose -f docker-compose.yaml down
```

## 📋 Требования

1. **Файл `.env`** должен находиться в корне проекта (см. `.env.example`)
2. **Docker** и **Docker Compose** должны быть установлены
3. **Порты** должны быть свободны (если используются)

## 🔧 Настройка

### Создание `.env` файла

Если файла `.env` еще нет:

```bash
# Из корня проекта
cp .env.example .env

# Отредактируйте .env и добавьте свои ключи
nano .env  # или используйте любой редактор
```

### Необходимые переменные в `.env`:

```env
TELEGRAM_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_key
DEEPSEEK_API_KEY=your_deepseek_key
MONGO_URL=mongodb://mongo:27017  # для docker-compose
```

## 🐳 Docker Compose команды

### Основные команды

```bash
# Запуск в фоне
docker-compose -f deploy/docker-compose.yaml up -d

# Запуск с просмотром логов
docker-compose -f deploy/docker-compose.yaml up

# Остановка
docker-compose -f deploy/docker-compose.yaml down

# Остановка с удалением volumes (удалит данные MongoDB!)
docker-compose -f deploy/docker-compose.yaml down -v

# Перезапуск
docker-compose -f deploy/docker-compose.yaml restart

# Просмотр логов
docker-compose -f deploy/docker-compose.yaml logs -f bot

# Просмотр статуса
docker-compose -f deploy/docker-compose.yaml ps

# Пересборка образа
docker-compose -f deploy/docker-compose.yaml build --no-cache
```

### Полезные команды

```bash
# Войти в контейнер бота
docker exec -it smart_procure_bot bash

# Просмотр логов MongoDB
docker-compose -f deploy/docker-compose.yaml logs -f mongo

# Очистка неиспользуемых образов
docker system prune -a
```

## 🔍 Проверка работы

После запуска проверьте:

```bash
# Статус контейнеров
docker-compose -f deploy/docker-compose.yaml ps

# Должны быть запущены:
# - smart_procure_bot (статус: Up)
# - smart_procure_mongo (статус: Up)

# Логи бота
docker-compose -f deploy/docker-compose.yaml logs bot | tail -20

# Должны увидеть:
# ✅ Database connected & Commands set
# Bot is running...
```

## 🚨 Решение проблем

### Ошибка: "env file not found"

**Проблема:** `.env` файл не найден

**Решение:**
1. Убедитесь, что `.env` находится в корне проекта (не в `deploy/`)
2. Проверьте путь: `ls -la .env` из корня проекта
3. Если файла нет, скопируйте из примера: `cp .env.example .env`

### Ошибка: "port already in use"

**Проблема:** Порт уже занят другим процессом

**Решение:**
```bash
# Найти процесс, использующий порт
lsof -i :27017  # для MongoDB

# Остановить старые контейнеры
docker-compose -f deploy/docker-compose.yaml down
```

### Контейнер не запускается

**Решение:**
```bash
# Проверить логи
docker-compose -f deploy/docker-compose.yaml logs bot

# Пересобрать образ
docker-compose -f deploy/docker-compose.yaml build --no-cache

# Перезапустить
docker-compose -f deploy/docker-compose.yaml up -d
```

## 📦 Продакшн деплой

Для продакшн деплоя используется `docker-compose.prod.yml`:

```bash
# На сервере
docker-compose -f deploy/docker-compose.prod.yml up -d
```

Этот файл использует готовый образ из registry, а не собирает его локально.

## 🔄 Обновление

После изменений в коде:

```bash
# Пересобрать образ
docker-compose -f deploy/docker-compose.yaml build

# Перезапустить
docker-compose -f deploy/docker-compose.yaml up -d
```

## 📝 Примечания

- Данные MongoDB сохраняются в volume `mongo_data`
- Данные бота сохраняются в папке `data/` в корне проекта
- Все пути в docker-compose файлах настроены относительно корня проекта

