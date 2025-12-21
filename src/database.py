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
    
    async def add_normalized_quote(self, project_id: str, source_name: str, 
                                   suppliers_data: list, category: str = None, 
                                   missing_fields: dict = None):
        """
        Сохраняет нормализованные результаты парсинга с категорией и метаданными.
        
        Args:
            project_id: ID проекта
            source_name: Имя исходного файла
            suppliers_data: Список поставщиков с нормализованными данными
            category: Обнаруженная категория товаров
            missing_fields: Словарь отсутствующих полей по поставщикам
        """
        from datetime import datetime
        from bson import ObjectId
        
        quote_doc = {
            "project_id": ObjectId(project_id),
            "source_file": source_name,
            "created_at": datetime.utcnow(),
            "detected_category": category or "общее",
            "missing_fields": missing_fields or {},
            "suppliers": suppliers_data,
            "comparison_result": None  # Will be filled after comparison
        }
        
        result = await self.db.quotes.insert_one(quote_doc)
        return result.inserted_id

    async def get_project_items_flat(self, project_id: str):
        """
        Собирает все товары проекта в плоский список для экспорта.
        Включает как оригинальные, так и нормализованные данные.
        """
        from bson import ObjectId
        
        items = []
        # Ищем все загрузки (Quotes) по проекту
        cursor = self.db.quotes.find({"project_id": ObjectId(project_id)})
        
        async for quote in cursor:
            upload_date = quote.get("created_at")
            source = quote.get("source_file")
            category = quote.get("detected_category", "")
            
            for supplier in quote.get("suppliers", []):
                supp_name = supplier.get("name", "Unknown")
                
                for item in supplier.get("items", []):
                    # Базовая запись
                    row = {
                        "date": upload_date,
                        "source": source,
                        "category": category,
                        "supplier": supp_name,
                        "name": item.get("name"),
                        "qty": item.get("quantity"),
                        "unit": item.get("unit"),
                        "price": item.get("price_per_unit"),
                        "currency": item.get("currency"),
                        "total": item.get("total_price"),
                        # Нормализованные данные
                        "normalized_qty": item.get("normalized_quantity"),
                        "normalized_unit": item.get("normalized_unit"),
                        "normalized_price": item.get("normalized_price"),
                        "completeness_score": item.get("completeness_score", 0),
                    }
                    
                    # Добавляем динамические характеристики (specs)
                    specs = item.get("specs", {})
                    if specs:
                        for k, v in specs.items():
                            row[f"spec_{k}"] = v
                            
                    items.append(row)
                    
        return items
    
    async def get_comparable_items(self, project_id: str):
        """
        Получает товары проекта, сгруппированные для сравнения.
        Возвращает список quote документов с полной информацией.
        """
        from bson import ObjectId
        
        cursor = self.db.quotes.find({"project_id": ObjectId(project_id)})
        quotes = await cursor.to_list(length=1000)
        return quotes
    
    async def save_comparison_result(self, project_id: str, comparison_data: dict):
        """
        Сохраняет результаты сравнения для проекта.
        
        Args:
            project_id: ID проекта
            comparison_data: Результаты сравнения с рекомендациями
        """
        from bson import ObjectId
        from datetime import datetime
        
        comparison_doc = {
            "project_id": ObjectId(project_id),
            "created_at": datetime.utcnow(),
            "comparison_data": comparison_data
        }
        
        # Сохраняем в отдельную коллекцию comparisons
        result = await self.db.comparisons.insert_one(comparison_doc)
        return result.inserted_id
    
    async def get_latest_comparison(self, project_id: str):
        """
        Получает последнее сравнение для проекта.
        """
        from bson import ObjectId
        
        comparison = await self.db.comparisons.find_one(
            {"project_id": ObjectId(project_id)},
            sort=[("created_at", -1)]
        )
        return comparison
    
    async def get_quotes_needing_clarification(self, project_id: str):
        """
        Находит quotes с отсутствующими полями, требующими уточнения.
        
        Returns:
            Список quotes с непустым missing_fields
        """
        from bson import ObjectId
        
        cursor = self.db.quotes.find({
            "project_id": ObjectId(project_id),
            "missing_fields": {"$exists": True, "$ne": {}}
        })
        
        quotes = await cursor.to_list(length=100)
        return quotes
    
    async def mark_clarification_sent(self, quote_id: str):
        """
        Отмечает, что запрос на уточнение был отправлен для данной цитаты.
        """
        from bson import ObjectId
        
        await self.db.quotes.update_one(
            {"_id": ObjectId(quote_id)},
            {"$set": {"clarification_sent": True}}
        )

# Глобальный инстанс
db = Database()