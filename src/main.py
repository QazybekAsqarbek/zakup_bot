import io
import logging
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from src.config import TELEGRAM_TOKEN
from src.database import db  # Импортируем наш новый объект БД
from src.ai_engine import process_content_with_ai

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def post_init(application):
    # Инициализируем подключение к БД при старте бота
    db.connect()
    
    commands = [
        BotCommand("start", "🚀 Начало"),
        BotCommand("new_project", "📁 Новый проект"),
        BotCommand("export", "📊 Скачать Excel"),
        BotCommand("help", "❓ Справка"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Database connected & Commands set")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Я переехал на MongoDB и стал умнее.\nСоздай проект через /new_project и загружай файлы (PDF, Excel, Фото, Word).")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Кидай файлы -> Выбирай проект -> Получай Excel со всеми характеристиками.")

async def new_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args)
    user_id = update.effective_user.id
    
    if not name:
        await update.message.reply_text("⚠️ Имя проекта обязательно: `/new_project Стройка`", parse_mode="Markdown")
        return

    # MONGO CREATE
    await db.create_project(user_id, name)
    
    await update.message.reply_text(f"✅ Проект **«{name}»** создан (в MongoDB)!", parse_mode="Markdown")

async def handle_incoming_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # MONGO READ
    projects = await db.get_user_projects(user_id)

    if not projects:
        await update.message.reply_text("⛔️ Сначала создайте проект: `/new_project <Имя>`")
        return

    # Логика определения файла (как в прошлом шаге)
    is_text = False
    file_id = None
    text_content = None
    filename = "message.txt"
    mime_type = "text/plain"

    if update.message.text:
        is_text = True
        text_content = update.message.text
    elif update.message.document:
        file_id = update.message.document.file_id
        filename = update.message.document.file_name
        mime_type = update.message.document.mime_type
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
        filename = "photo.jpg"
        mime_type = "image/jpeg"
    else:
        return

    context.user_data['payload_type'] = 'text' if is_text else 'file'
    context.user_data['text_content'] = text_content
    context.user_data['file_id'] = file_id
    context.user_data['filename'] = filename
    context.user_data['mime_type'] = mime_type

    # Кнопки. Важно: используем str(p['_id']) так как это ObjectId
    keyboard = [
        [InlineKeyboardButton(f"📂 {p['name']}", callback_data=f"proj_{str(p['_id'])}")] for p in projects
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Куда сохранить **{filename}**?", reply_markup=reply_markup, parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("proj_"):
        project_id = data.split("_")[1] # Это строка ObjectId
        
        await query.edit_message_text("⏳ Читаю файл и извлекаю характеристики...")
        
        try:
            # Получение данных файла
            payload_type = context.user_data.get('payload_type')
            ai_result = None
            
            if payload_type == 'text':
                text_content = context.user_data.get('text_content')
                ai_result = process_content_with_ai(text_content=text_content)
            else:
                file_id = context.user_data.get('file_id')
                filename = context.user_data.get('filename')
                mime_type = context.user_data.get('mime_type')
                
                new_file = await context.bot.get_file(file_id)
                file_byte_array = await new_file.download_as_bytearray()
                
                ai_result = process_content_with_ai(
                    image_data=bytes(file_byte_array),
                    filename=filename,
                    media_type=mime_type
                )

            if not ai_result:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Не удалось извлечь данные.")
                return

            # AI теперь возвращает список поставщиков List[Dict]
            # Если вернулся один словарь, обернем его в список для универсальности
            if isinstance(ai_result, dict):
                # Если AI вернул старый формат с одним suppliers_name
                # Адаптируем под новую структуру
                if "supplier_name" in ai_result:
                     ai_result = [{
                         "name": ai_result.get("supplier_name"), 
                         "items": ai_result.get("items", [])
                     }]
                else:
                    ai_result = [ai_result]

            # MONGO WRITE
            # Мы сохраняем весь результат разбора как один документ Quote
            await db.add_quote(
                project_id=project_id,
                source_name=context.user_data.get('filename', 'Text message'),
                suppliers_data=ai_result
            )

            # Подсчет статистики для ответа
            total_items = sum(len(s.get('items', [])) for s in ai_result)
            suppliers_names = ", ".join([s.get('name', 'Unknown') for s in ai_result])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ Сохранено в MongoDB!\nПоставщики: {suppliers_names}\nТоваров: {total_items}"
            )

        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Ошибка при сохранении.")

    elif data.startswith("export_"):
        await export_callback(update, context)

async def export_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    projects = await db.get_user_projects(user_id)

    if not projects:
        await update.message.reply_text("Нет проектов.")
        return

    keyboard = [[InlineKeyboardButton(f"📥 {p['name']}", callback_data=f"export_{str(p['_id'])}")] for p in projects]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите проект для экспорта:", reply_markup=reply_markup)

async def export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    project_id = query.data.split("_")[1]
    
    # MONGO AGGREGATION (FLAT LIST)
    items = await db.get_project_items_flat(project_id)
    
    if not items:
        await query.edit_message_text("В проекте пока пусто.")
        return
        
    # Pandas делает всю магию - ключи spec_... станут колонками
    df = pd.DataFrame(items)
    
    # Переименуем колонки для красоты
    rename_map = {
        "date": "Дата", "source": "Файл", "supplier": "Поставщик",
        "name": "Наименование", "qty": "Кол-во", "unit": "Ед.изм",
        "price": "Цена", "currency": "Валюта", "total": "Сумма"
    }
    df.rename(columns=rename_map, inplace=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Сводная')
        
        # Авто-ширина колонок
        worksheet = writer.sheets['Сводная']
        for column in worksheet.columns:
            try:
                length = max(len(str(cell.value)) for cell in column)
                worksheet.column_dimensions[column[0].column_letter].width = min(length + 2, 50)
            except:
                pass

    output.seek(0)
    
    # Получим имя проекта для файла
    proj = await db.get_project_by_id(project_id)
    proj_name = proj['name'] if proj else "project"

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=output,
        filename=f"{proj_name}.xlsx",
        caption="📊 Ваша таблица с характеристиками готова."
    )

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new_project", new_project))
    app.add_handler(CommandHandler("export", export_project))
    app.add_handler(CommandHandler("help", help_command))
    
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL | (filters.TEXT & ~filters.COMMAND), 
        handle_incoming_message
    ))
    
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot is running...")
    app.run_polling()
