import io
import logging
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from src.config import TELEGRAM_TOKEN
from src.database import db
from src.ai_engine import process_content_with_ai
from src.category_intelligence import category_intelligence
from src.unit_normalizer import unit_normalizer
from src.clarifier import auto_clarifier
from src.comparator import quote_comparator

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
        BotCommand("compare", "🏆 Сравнить предложения"),
        BotCommand("clarify", "📝 Запросить уточнения"),
        BotCommand("analysis", "📊 Полный анализ"),
        BotCommand("export", "📥 Скачать Excel"),
        BotCommand("help", "❓ Справка"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Database connected & Commands set")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """👋 Привет! Я умный бот для анализа коммерческих предложений.

Что я умею:
✅ Парсить файлы (PDF, Excel, Word, Фото)
✅ Нормализовать единицы измерения
✅ Сравнивать предложения от разных поставщиков
✅ Находить лучшие цены
✅ Генерировать запросы на уточнения

Начни с /new_project"""
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """📖 **СПРАВКА**

**Команды:**
/new_project <название> - Создать проект
/compare - Сравнить все предложения
/clarify - Получить запросы на уточнения
/analysis - Полный анализ с рекомендациями
/export - Скачать Excel с данными

**Процесс работы:**
1. Создай проект
2. Загружай файлы от поставщиков
3. Используй /compare для анализа
4. Экспортируй результаты"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

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
    
    if data.startswith("compare_"):
        await compare_callback(update, context)
        return
    elif data.startswith("clarify_"):
        await clarify_callback(update, context)
        return
    elif data.startswith("analysis_"):
        await analysis_callback(update, context)
        return
    elif data.startswith("proj_"):
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
                error_msg = "❌ Не удалось извлечь данные.\n\n"
                error_msg += "Возможные причины:\n"
                error_msg += "• API не ответил (таймаут)\n"
                error_msg += "• Неверный формат данных\n"
                error_msg += "• Проверьте логи для деталей"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=error_msg)
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

            # NEW: Category detection
            all_items = []
            for supplier in ai_result:
                all_items.extend(supplier.get("items", []))
            
            category = await category_intelligence.detect_category(all_items)
            logger.info(f"📁 Detected category: {category}")

            # NEW: Unit normalization
            normalized_suppliers = await unit_normalizer.normalize_quote(ai_result)
            
            # NEW: Enrich with category-specific validation
            for supplier in normalized_suppliers:
                supplier["items"] = await category_intelligence.enrich_specs_with_category(
                    supplier.get("items", []), category
                )
            
            # NEW: Check for missing fields
            mock_quote = {"suppliers": normalized_suppliers}
            missing_fields = auto_clarifier.detect_missing_fields(mock_quote, category)

            # MONGO WRITE with enhanced data
            await db.add_normalized_quote(
                project_id=project_id,
                source_name=context.user_data.get('filename', 'Text message'),
                suppliers_data=normalized_suppliers,
                category=category,
                missing_fields=missing_fields
            )

            # Подсчет статистики для ответа
            total_items = sum(len(s.get('items', [])) for s in normalized_suppliers)
            suppliers_names = ", ".join([s.get('name', 'Unknown') for s in normalized_suppliers])
            
            response_text = f"✅ Сохранено!\n\n"
            response_text += f"📁 Категория: {category}\n"
            response_text += f"👥 Поставщики: {suppliers_names}\n"
            response_text += f"📦 Товаров: {total_items}\n"
            
            if missing_fields:
                response_text += f"\n⚠️ Требуется уточнение у {len(missing_fields)} поставщиков\n"
                response_text += f"Используй /clarify для деталей"

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=response_text
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
        "date": "Дата", "source": "Файл", "category": "Категория",
        "supplier": "Поставщик", "name": "Наименование", 
        "qty": "Кол-во", "unit": "Ед.изм", "price": "Цена", 
        "currency": "Валюта", "total": "Сумма",
        "normalized_qty": "Норм. кол-во", "normalized_unit": "Норм. ед.",
        "normalized_price": "Норм. цена", "completeness_score": "Полнота данных"
    }
    df.rename(columns=rename_map, inplace=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main data sheet
        df.to_excel(writer, index=False, sheet_name='Сводная')
        
        # Авто-ширина колонок
        worksheet = writer.sheets['Сводная']
        for column in worksheet.columns:
            try:
                length = max(len(str(cell.value)) for cell in column)
                worksheet.column_dimensions[column[0].column_letter].width = min(length + 2, 50)
            except:
                pass
        
        # Add comparison sheet if available
        comparison = await db.get_latest_comparison(project_id)
        if comparison and comparison.get('comparison_data'):
            comp_data = comparison['comparison_data']
            
            if comp_data.get('status') == 'success':
                comparisons = comp_data.get('item_comparisons', [])
                
                if comparisons:
                    comp_rows = []
                    for comp in comparisons:
                        rec = comp['recommendation']
                        comp_rows.append({
                            'Товар': comp['item_name'],
                            'Кол-во предложений': comp['suppliers_count'],
                            'Рекомендация': rec.get('recommended_supplier'),
                            'Лучшая цена': rec.get('recommended_price'),
                            'Единица': rec.get('price_unit'),
                            'Экономия %': rec.get('price_difference_percent'),
                            'Причина': rec.get('reasoning')
                        })
                    
                    comp_df = pd.DataFrame(comp_rows)
                    comp_df.to_excel(writer, index=False, sheet_name='Сравнение')
                    
                    # Авто-ширина для листа сравнения
                    comp_ws = writer.sheets['Сравнение']
                    for column in comp_ws.columns:
                        try:
                            length = max(len(str(cell.value)) for cell in column)
                            comp_ws.column_dimensions[column[0].column_letter].width = min(length + 2, 60)
                        except:
                            pass

    output.seek(0)
    
    # Получим имя проекта для файла
    proj = await db.get_project_by_id(project_id)
    proj_name = proj['name'] if proj else "project"

    caption = "📊 Ваша таблица с нормализованными данными готова."
    if comparison:
        caption += "\n🏆 Включены результаты сравнения!"

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=output,
        filename=f"{proj_name}.xlsx",
        caption=caption
    )

async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compare quotes and generate recommendations"""
    try:
        user_id = update.effective_user.id
        projects = await db.get_user_projects(user_id)
        
        if not projects:
            await update.message.reply_text("⛔️ Сначала создайте проект: /new_project <Имя>")
            return
        
        # Show project selection buttons
        keyboard = [
            [InlineKeyboardButton(f"🏆 {p['name']}", callback_data=f"compare_{str(p['_id'])}")] 
            for p in projects
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите проект для сравнения:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Compare command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка команды /compare: {str(e)}")

async def compare_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle comparison callback"""
    query = update.callback_query
    await query.answer()
    project_id = query.data.split("_")[1]
    
    await query.edit_message_text("🔍 Анализирую предложения...")
    
    try:
        # Get all quotes for project
        quotes = await db.get_comparable_items(project_id)
        
        if not quotes:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="В проекте нет данных для сравнения."
            )
            return
        
        # Run comparison
        comparison_result = await quote_comparator.compare_project_quotes(quotes)
        
        # Save comparison result
        from datetime import datetime
        comparison_result["generated_at"] = datetime.utcnow()
        await db.save_comparison_result(project_id, comparison_result)
        
        # Generate summary
        summary = await quote_comparator.generate_recommendation_summary(comparison_result)
        
        # Send results (split if too long)
        if len(summary) > 4000:
            # Split into chunks
            chunks = [summary[i:i+4000] for i in range(0, len(summary), 4000)]
            for chunk in chunks:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=chunk,
                    parse_mode="Markdown"
                )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=summary,
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Comparison error: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Ошибка при сравнении"
        )

async def clarify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate clarification requests for missing data"""
    try:
        user_id = update.effective_user.id
        projects = await db.get_user_projects(user_id)
        
        if not projects:
            await update.message.reply_text("⛔️ Сначала создайте проект: /new_project <Имя>")
            return
        
        # Show project selection buttons
        keyboard = [
            [InlineKeyboardButton(f"📝 {p['name']}", callback_data=f"clarify_{str(p['_id'])}")] 
            for p in projects
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите проект для запроса уточнений:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Clarify command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка команды /clarify: {str(e)}")

async def clarify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle clarification callback"""
    query = update.callback_query
    await query.answer()
    project_id = query.data.split("_")[1]
    
    await query.edit_message_text("📝 Генерирую запросы на уточнения...")
    
    try:
        # Get project name
        proj = await db.get_project_by_id(project_id)
        project_name = proj.get('name') if proj else None
        
        # Get quotes needing clarification
        quotes_with_missing = await db.get_quotes_needing_clarification(project_id)
        
        if not quotes_with_missing:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ Все данные полные! Уточнения не требуются."
            )
            return
        
        # Generate clarification messages
        clarifications = await auto_clarifier.generate_all_clarifications(
            quotes_with_missing, project_name
        )
        
        if not clarifications:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ Все данные полные! Уточнения не требуются."
            )
            return
        
        # Send clarification messages
        for clarification in clarifications:
            message = f"**Файл:** {clarification['source_file']}\n"
            message += f"**Поставщик:** {clarification['supplier']}\n"
            message += f"**Требуется уточнить:** {', '.join(clarification['missing_fields'])}\n\n"
            message += f"**Запрос:**\n{clarification['message']}\n"
            message += "\n" + "="*50 + "\n"
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                parse_mode="Markdown"
            )
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Сгенерировано {len(clarifications)} запросов"
        )
        
    except Exception as e:
        logger.error(f"Clarification error: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Ошибка при генерации запросов"
        )

async def analysis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Full analysis: comparison + clarifications"""
    try:
        user_id = update.effective_user.id
        projects = await db.get_user_projects(user_id)
        
        if not projects:
            await update.message.reply_text("⛔️ Сначала создайте проект: /new_project <Имя>")
            return
        
        # Show project selection buttons
        keyboard = [
            [InlineKeyboardButton(f"📊 {p['name']}", callback_data=f"analysis_{str(p['_id'])}")] 
            for p in projects
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите проект для полного анализа:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Analysis command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка команды /analysis: {str(e)}")

async def analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle full analysis callback"""
    query = update.callback_query
    await query.answer()
    project_id = query.data.split("_")[1]
    
    await query.edit_message_text("🔍 Выполняю полный анализ...")
    
    try:
        # Run comparison first
        quotes = await db.get_comparable_items(project_id)
        
        if quotes:
            comparison_result = await quote_comparator.compare_project_quotes(quotes)
            from datetime import datetime
            comparison_result["generated_at"] = datetime.utcnow()
            await db.save_comparison_result(project_id, comparison_result)
            
            summary = await quote_comparator.generate_recommendation_summary(comparison_result)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=summary[:4000],  # Truncate if too long
                parse_mode="Markdown"
            )
        
        # Then check for missing data
        proj = await db.get_project_by_id(project_id)
        project_name = proj.get('name') if proj else None
        
        quotes_with_missing = await db.get_quotes_needing_clarification(project_id)
        
        if quotes_with_missing:
            clarifications = await auto_clarifier.generate_all_clarifications(
                quotes_with_missing, project_name
            )
            
            if clarifications:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"\n⚠️ **ТРЕБУЮТСЯ УТОЧНЕНИЯ:** {len(clarifications)} поставщиков\nИспользуй /clarify для деталей",
                    parse_mode="Markdown"
                )
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✅ Анализ завершен!"
        )
        
    except Exception as e:
        logger.error(f"Analysis error: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Ошибка при анализе"
        )

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new_project", new_project))
    app.add_handler(CommandHandler("compare", compare_command))
    app.add_handler(CommandHandler("clarify", clarify_command))
    app.add_handler(CommandHandler("analysis", analysis_command))
    app.add_handler(CommandHandler("export", export_project))
    app.add_handler(CommandHandler("help", help_command))
    
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL | (filters.TEXT & ~filters.COMMAND), 
        handle_incoming_message
    ))
    
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot is running...")
    app.run_polling()
