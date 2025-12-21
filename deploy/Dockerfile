FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости системы (нужны для некоторых библиотек)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Запускаем бота как модуль
CMD ["python", "-m", "src.main"]