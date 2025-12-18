import io
import logging
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from src.config import TELEGRAM_TOKEN
from src.database import SessionLocal, Project, Quote, QuoteItem
from src.ai_engine import process_content_with_ai
from src.file_reader import extract_text_from_file

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- НОВОЕ: Установка команд меню ---
async def post_init(application):
    """Эта функция запускается один раз при старте бота и настраивает меню"""
    commands = [
        BotCommand("start", "🚀 Начало работы"),
        BotCommand("new_project", "📁 Создать проект закупки"),
        BotCommand("export", "📊 Скачать Excel-сравнение"),
        BotCommand("help", "❓ Справка и примеры"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Commands menu updated successfully")

# --- ОБНОВЛЕННЫЙ START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"User {update.effective_user.id} started the bot")
    
    user_first_name = update.effective_user.first_name
    
    welcome_text = (
        f"👋 **Привет, {user_first_name}!**\n\n"
        "Я — **SmartProcure AI**, твой ассистент по автоматизации закупок.\n"
        "Я избавляю от ручного перебивания данных из счетов и КП в Excel.\n\n"
        "🧠 **Что я умею?**\n"
        "1. Читать **фото** ценников и прайс-листов (через Claude 3.5).\n"
        "2. Понимать **текстовые** запросы и списки (через DeepSeek V3).\n"
        "3. Сводить всё это в единую **Excel-таблицу** для сравнения.\n\n"
        "👇 **Как начать:**\n"
        "1️⃣ Создайте папку для работы:\n"
        "`/new_project Закупка плитки`\n\n"
        "2️⃣ Просто пересылайте мне сообщения от поставщиков, кидайте фото или пишите текст.\n"
        "Я сам спрошу, в какой проект это добавить.\n\n"
        "3️⃣ Когда наберете данных, нажмите:\n"
        "`/export` — чтобы получить готовый отчет."
    )
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🆘 **Справка**\n\n"
        "**Команды:**\n"
        "— `/new_project <Имя>` : Создать новую группу товаров.\n"
        "— `/export` : Выгрузить всё, что вы загрузили, в Excel.\n\n"
        "**Форматы:**\n"
        "📸 **Фото:** Сфоткайте ценник в магазине или скриншот таблицы. Я вытащу название и цену.\n"
        "📝 **Текст:** Скопируйте сообщение из переписки с поставщиком. Например:\n"
        "_\"Труба 50мм - 10 шт по 300р, Отвод 90гр - 5 шт по 150р\"_\n\n"
        "Если что-то не работает, попробуйте отправить более четкое фото."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def new_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args)
    user_id = update.effective_user.id
    
    if not name:
        await update.message.reply_text(
            "⚠️ **Ошибка:** Вы не указали название.\n"
            "Пример использования:\n`/new_project Офисная мебель`",
            parse_mode="Markdown"
        )
        return

    session = SessionLocal()
    project = Project(user_id=user_id, name=name)
    session.add(project)
    session.commit()
    session.close()
    
    logger.info(f"Project '{name}' created for user {user_id}")
    await update.message.reply_text(f"✅ Проект **«{name}»** создан!\nТеперь отправляйте фото или текст с ценами.", parse_mode="Markdown")

async def handle_incoming_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"📩 Received message from {user_id}")
    
    session = SessionLocal()
    projects = session.query(Project).filter(Project.user_id == user_id).all()
    session.close()

    if not projects:
        logger.warning(f"User {user_id} tried to upload without projects")
        await update.message.reply_text("⛔️ У вас нет активных проектов.\nСначала создайте его: `/new_project <Имя>`", parse_mode="Markdown")
        return

    is_text = False
    is_image = False
    file_id = None
    text_content = None
    mime_type = None
    filename = "message.txt"

    if update.message.text:
        is_text = True
        text_content = update.message.text
    elif update.message.photo:
        filename = "photo.jpg"
        is_image = True
        file_id = update.message.photo[-1].file_id
        mime_type = "image/jpeg"
    elif update.message.document:
        filename = update.message.document.file_name
        file_id = update.message.document.file_id
        mime_type = update.message.document.mime_type
        if mime_type and "image" in mime_type:
            is_image = True
    else:
        await update.message.reply_text("⚠️ Я понимаю только текст, фото или документы-изображения.")
        return

    context.user_data['payload_type'] = 'text' if is_text else 'file'
    context.user_data['text_content'] = text_content
    context.user_data['file_id'] = file_id
    context.user_data['is_image'] = is_image
    context.user_data['mime_type'] = mime_type
    context.user_data['filename'] = filename

    keyboard = [
        [InlineKeyboardButton(f"📂 {p.name}", callback_data=f"proj_{p.id}")] for p in projects
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Куда сохранить эти данные?", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Убираем часики на кнопке
    
    data = query.data
    logger.info(f"🔘 Button clicked: {data}")
    
    if data.startswith("proj_"):
        project_id = int(data.split("_")[1])
        
        payload_type = context.user_data.get('payload_type')
        
        await query.edit_message_text(text="⏳ **Анализирую данные...**\nОбычно это занимает 5-10 секунд.", parse_mode="Markdown")

        json_data = None
        
        try:
            if payload_type == 'text':
                text_content = context.user_data.get('text_content')
                json_data = process_content_with_ai(text_content=text_content)
            else:
                file_id = context.user_data.get('file_id')
                mime_type = context.user_data.get('mime_type')
                filename = context.user_data.get('filename')

                new_file = await context.bot.get_file(file_id)
                file_byte_array = await new_file.download_as_bytearray()                
                
                # 1. Если это Картинка или PDF -> Отправляем байты в Claude/Vision
                if context.user_data.get('is_image') or mime_type == 'application/pdf':
                     json_data = process_content_with_ai(
                         image_data=bytes(file_byte_array),
                         media_type=mime_type or "image/jpeg",
                         filename=filename
                     )
                
                # 2. Если это Текстовый документ (.docx, .md, .txt) -> Извлекаем текст -> DeepSeek
                else:
                    extracted_text = extract_text_from_file(bytes(file_byte_array), mime_type)
                    
                    if extracted_text:
                        logger.info(f"📄 Extracted {len(extracted_text)} chars from document. Sending to DeepSeek.")
                        json_data = process_content_with_ai(text_content=extracted_text)
                    else:
                        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Формат файла не поддерживается (пока).")
                        return

            if not json_data:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ AI не смог найти товары в этом сообщении.")
                return

            session = SessionLocal()
            quote = Quote(
                project_id=project_id, 
                supplier_name=json_data.get('supplier_name', 'Не указан'),
                raw_text_source="User Input"
            )
            session.add(quote)
            session.flush()

            items_count = 0
            for item in json_data.get('items', []):
                qty = float(item.get('quantity') or 0.0)
                price = float(item.get('price_per_unit') or 0.0)
                
                q_item = QuoteItem(
                    quote_id=quote.id,
                    name=item.get('name', 'Товар без названия'),
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
                text=f"✅ **Успешно!**\nПоставщик: {json_data.get('supplier_name')}\nДобавлено позиций: **{items_count}**",
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Processing error: {e}", exc_info=True)
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Произошла ошибка при обработке.")

    elif data.startswith("export_"):
        await export_callback(update, context)

async def export_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = SessionLocal()
    projects = session.query(Project).filter(Project.user_id == user_id).all()
    session.close()

    if not projects:
        await update.message.reply_text("📂 У вас пока нет проектов для выгрузки.")
        return

    keyboard = [[InlineKeyboardButton(f"📥 {p.name}", callback_data=f"export_{p.id}")] for p in projects]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите проект для получения Excel:", reply_markup=reply_markup)

async def export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    project_id = int(query.data.split("_")[1])
    
    session = SessionLocal()
    items = session.query(QuoteItem, Quote).join(Quote).filter(Quote.project_id == project_id).all()
    session.close()

    if not items:
        await query.edit_message_text("🤷‍♂️ В этом проекте пока пусто.")
        return

    data = []
    for item, quote in items:
        data.append({
            "Поставщик": quote.supplier_name,
            "Товар": item.name,
            "Кол-во": item.quantity,
            "Ед.изм": item.unit,
            "Цена за ед.": item.price_per_unit,
            "Валюта": item.currency,
            "Общая сумма": item.total_price,
            "Дата загрузки": quote.created_at.strftime("%Y-%m-%d %H:%M")
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Сравнение')
        # Автоширина колонок (базовая)
        worksheet = writer.sheets['Сравнение']
        for column in worksheet.columns:
            new_column_length = max(len(str(cell.value)) for cell in column)
            new_column_width = (new_column_length + 2) * 1.2
            worksheet.column_dimensions[column[0].column_letter].width = min(new_column_width, 50) # Ограничение ширины

    output.seek(0)

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=output,
        filename=f"Report_Project_{project_id}.xlsx",
        caption="📊 **Ваш отчет готов!**\nСравните цены и выберите лучшего поставщика.",
        parse_mode="Markdown"
    )

if __name__ == '__main__':
    # Добавляем post_init для регистрации команд
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new_project", new_project))
    app.add_handler(CommandHandler("export", export_project))
    
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL | (filters.TEXT & ~filters.COMMAND), 
        handle_incoming_message
    ))
    
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("🚀 Bot is running polling...")
    app.run_polling()