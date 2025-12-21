import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# AI settings
OPEN_ROUTER_TOKEN = os.getenv("OPEN_ROUTER_TOKEN")
OPEN_ROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPEN_ROUTER_MODEL = "google/gemini-2.0-flash-001"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# Database settings
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "smartprocure"