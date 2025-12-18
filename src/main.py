import io
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from src.config import TELEGRAM_TOKEN
from src.database import SessionLocal, Project, Quote, QuoteItem
from src.ai_engine import process_content_with_ai
import logging

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я SmartProcure AI 🤖.\n\n"
        "1. Создай проект: /new_project <Имя>\n"
        "2. Пришли мне КП (текст, фото или файл)\n"
        "3. Я спрошу, к какому проекту это добавить\n"
        "4. Выгрузи сравнение: /export"
    )

async def new_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args)
    if not name:
        await update.message.reply_text("Укажите имя проекта. Пример: /new_project Закупка столов")
        return

    user_id = update.effective_user.id
    logger.info(f"User {user_id} is creating project: '{name}'")
    session = SessionLocal()
    project = Project(user_id=user_id, name=name)
    session.add(project)
    session.commit()
    session.close()
    
    await update.message.reply_text(f"✅ Проект '{name}' создан! Теперь присылайте файлы или текст.")

# --- ОБНОВЛЕННАЯ ФУНКЦИЯ ОБРАБОТКИ СООБЩЕНИЙ ---
async def handle_incoming_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"📩 Received message from {user_id}")
    
    # Проверка наличия проектов
    session = SessionLocal()
    projects = session.query(Project).filter(Project.user_id == user_id).all()
    session.close()

    if not projects:
        await update.message.reply_text("Сначала создайте проект через /new_project")
        return

    # Определяем тип входящих данных
    is_text = False
    is_image = False
    file_id = None
    text_content = None
    mime_type = None

    if update.message.text:
        is_text = True
        text_content = update.message.text
    elif update.message.photo:
        is_image = True
        file_id = update.message.photo[-1].file_id
        mime_type = "image/jpeg"
    elif update.message.document:
        file_id = update.message.document.file_id
        mime_type = update.message.document.mime_type
        if mime_type and "image" in mime_type:
            is_image = True
    else:
        await update.message.reply_text("Я понимаю только текст, фото или документы.")
        return

    # Сохраняем во временное хранилище user_data
    context.user_data['payload_type'] = 'text' if is_text else 'file'
    context.user_data['text_content'] = text_content
    context.user_data['file_id'] = file_id
    context.user_data['is_image'] = is_image
    context.user_data['mime_type'] = mime_type

    # Рисуем кнопки с проектами
    keyboard = [
        [InlineKeyboardButton(p.name, callback_data=f"proj_{p.id}")] for p in projects
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📂 К какому проекту относится эта информация?", reply_markup=reply_markup)

# --- ОБНОВЛЕННАЯ ФУНКЦИЯ ОБРАБОТКИ КНОПОК ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    logger.info(f"🔘 Button clicked: {data}") # Лог нажатия кнопки
    
    # Обработка выбора проекта (proj_ID)
    if data.startswith("proj_"):
        project_id = int(data.split("_")[1])
        
        payload_type = context.user_data.get('payload_type')
        
        await query.edit_message_text(text="⏳ Читаю данные и структурирую через AI... Секунду.")

        json_data = None
        
        try:
            # СЦЕНАРИЙ 1: ТЕКСТ
            if payload_type == 'text':
                text_content = context.user_data.get('text_content')
                # Вызываем Claude только с текстом
                json_data = process_content_with_ai(text_content=text_content)
                
            # СЦЕНАРИЙ 2: ФАЙЛ / ФОТО
            else:
                file_id = context.user_data.get('file_id')
                mime_type = context.user_data.get('mime_type')
                
                new_file = await context.bot.get_file(file_id)
                file_byte_array = await new_file.download_as_bytearray()
                
                if context.user_data.get('is_image'):
                    json_data = process_content_with_ai(image_data=bytes(file_byte_array), media_type=mime_type)
                else:
                    # Если PDF/Doc, пробуем отправить как есть (если модель поддерживает) 
                    # или просто текст, если файл небольшой. Для MVP обрабатываем как image/pdf если применимо
                    # Либо здесь можно добавить библиотеку pypdf для извлечения текста из PDF
                    json_data = process_content_with_ai(image_data=bytes(file_byte_array), media_type="application/pdf")

            if not json_data:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ AI не смог найти полезные данные.")
                return

            # --- Сохранение в БД (Общая часть) ---
            session = SessionLocal()
            quote = Quote(
                project_id=project_id, 
                supplier_name=json_data.get('supplier_name', 'Unknown'),
                raw_text_source="User Input"
            )
            session.add(quote)
            session.flush()

            items_count = 0
            for item in json_data.get('items', []):
                # Защита от отсутствующих полей
                qty = item.get('quantity')
                price = item.get('price_per_unit')
                
                # Приводим к 0, если None
                qty = float(qty) if qty else 0.0
                price = float(price) if price else 0.0
                
                q_item = QuoteItem(
                    quote_id=quote.id,
                    name=item.get('name', 'Без названия'),
                    quantity=qty,
                    unit=item.get('unit', ''),
                    price_per_unit=price,
                    currency=item.get('currency', ''),
                    total_price=qty * price
                )
                session.add(q_item)
                items_count += 1
            
            session.commit()
            session.close()

            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text=f"✅ Готово! Добавлено {items_count} товаров.\nПоставщик: {json_data.get('supplier_name')}"
            )
            
        except Exception as e:
            print(f"Error: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Ошибка обработки: {str(e)}")

    # Обработка экспорта (осталась прежней, но callback_query handler нужен один на все)
    elif data.startswith("export_"):
        await export_callback(update, context)

# --- ФУНКЦИЯ ЭКСПОРТА (без изменений, просто перенесите код из прошлого ответа) ---
async def export_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = SessionLocal()
    projects = session.query(Project).filter(Project.user_id == user_id).all()
    session.close()

    if not projects:
        await update.message.reply_text("Нет проектов.")
        return

    keyboard = [[InlineKeyboardButton(f"📥 {p.name}", callback_data=f"export_{p.id}")] for p in projects]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите проект для выгрузки Excel:", reply_markup=reply_markup)

async def export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # await query.answer() уже вызван в общей функции, если объединять, 
    # но лучше разделить логику.
    # В коде ниже я покажу как правильно зарегистрировать хендлеры.
    
    project_id = int(query.data.split("_")[1])
    
    session = SessionLocal()
    items = session.query(QuoteItem, Quote).join(Quote).filter(Quote.project_id == project_id).all()
    session.close()

    if not items:
        await query.edit_message_text("В этом проекте нет данных.")
        return

    data = []
    for item, quote in items:
        data.append({
            "Поставщик": quote.supplier_name,
            "Товар": item.name,
            "Кол-во": item.quantity,
            "Ед.изм": item.unit,
            "Цена": item.price_per_unit,
            "Валюта": item.currency,
            "Сумма": item.total_price,
            "Дата": quote.created_at
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Comparison')
    output.seek(0)

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=output,
        filename=f"project_{project_id}_comparison.xlsx",
        caption="📊 Сводная таблица."
    )

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new_project", new_project))
    app.add_handler(CommandHandler("export", export_project))
    
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL | (filters.TEXT & ~filters.COMMAND), 
        handle_incoming_message
    ))
    
    # Обработчик кнопок (один общий, внутри разводим логику)
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot is running...")
    app.run_polling()