from motor.motor_asyncio import AsyncIOMotorClient
from src.config import MONGO_URL, DB_NAME

class Database:
    client: AsyncIOMotorClient = None
    db = None

    def connect(self):
        """Создаем подключение к Mongo"""
        self.client = AsyncIOMotorClient(MONGO_URL)
        self.db = self.client[DB_NAME]
        print(f"🔥 Connected to MongoDB: {DB_NAME}")

    def close(self):
        if self.client:
            self.client.close()

    # --- Методы работы с данными ---

    async def create_project(self, user_id: int, name: str):
        """Создает новый проект"""
        from datetime import datetime
        project = {
            "user_id": user_id,
            "name": name,
            "created_at": datetime.utcnow()
        }
        result = await self.db.projects.insert_one(project)
        return result.inserted_id

    async def get_user_projects(self, user_id: int):
        """Получает список проектов пользователя"""
        cursor = self.db.projects.find({"user_id": user_id}).sort("created_at", -1)
        return await cursor.to_list(length=100)
    
    async def get_project_by_id(self, project_id):
        from bson import ObjectId
        return await self.db.projects.find_one({"_id": ObjectId(project_id)})

    async def add_quote(self, project_id: str, source_name: str, suppliers_data: list):
        """
        Сохраняет результаты парсинга.
        suppliers_data - это список поставщиков с товарами.
        """
        from datetime import datetime
        from bson import ObjectId
        
        quote_doc = {
            "project_id": ObjectId(project_id),
            "source_file": source_name,
            "created_at": datetime.utcnow(),
            "suppliers": suppliers_data # Гибкая структура: List[Supplier]
        }
        
        await self.db.quotes.insert_one(quote_doc)

    async def get_project_items_flat(self, project_id: str):
        """
        Собирает все товары проекта в плоский список для экспорта.
        """
        from bson import ObjectId
        
        items = []
        # Ищем все загрузки (Quotes) по проекту
        cursor = self.db.quotes.find({"project_id": ObjectId(project_id)})
        
        async for quote in cursor:
            upload_date = quote.get("created_at")
            source = quote.get("source_file")
            
            for supplier in quote.get("suppliers", []):
                supp_name = supplier.get("name", "Unknown")
                
                for item in supplier.get("items", []):
                    # Базовая запись
                    row = {
                        "date": upload_date,
                        "source": source,
                        "supplier": supp_name,
                        "name": item.get("name"),
                        "qty": item.get("quantity"),
                        "unit": item.get("unit"),
                        "price": item.get("price_per_unit"),
                        "currency": item.get("currency"),
                        "total": item.get("total_price"),
                    }
                    
                    # Добавляем динамические характеристики (specs)
                    specs = item.get("specs", {})
                    if specs:
                        for k, v in specs.items():
                            row[f"spec_{k}"] = v
                            
                    items.append(row)
                    
        return items

# Глобальный инстанс
db = Database()