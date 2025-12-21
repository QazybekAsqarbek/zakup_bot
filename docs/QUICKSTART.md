# Quick Start Guide

Get your procurement bot running in 5 minutes!

## 📋 Prerequisites

- Python 3.10+
- MongoDB running
- Telegram Bot Token
- API Keys (Anthropic, DeepSeek)

## 🚀 Quick Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create `.env` File

Create a `.env` file in the project root:

```env
# Telegram
TELEGRAM_TOKEN=your_telegram_bot_token_here

# AI APIs
ANTHROPIC_API_KEY=sk-ant-your-key-here
DEEPSEEK_API_KEY=your-deepseek-key-here

# Database
MONGO_URL=mongodb://localhost:27017
```

### 3. Start MongoDB

**Option A: Using Docker (Recommended)**
```bash
docker-compose up -d
```

**Option B: Local MongoDB**
```bash
mongod
```

### 4. Run the Bot

```bash
python src/main.py
```

You should see: `Bot is running...`

## 💬 Using the Bot

### Step 1: Start Chat
Open Telegram and find your bot, send:
```
/start
```

### Step 2: Create Project
```
/new_project Офисная мебель 2025
```

### Step 3: Upload Supplier Quotes
- Send PDF/Excel/Word files with supplier quotes
- Or send photos of printed quotes
- Bot will automatically parse and normalize data

### Step 4: Compare Quotes
```
/compare
```
Select your project to see recommendations.

### Step 5: Get Clarification Requests
```
/clarify
```
Receive ready-to-send messages for suppliers with missing data.

### Step 6: Export Results
```
/export
```
Download Excel with all data and recommendations.

## 🧪 Test with Sample Data

### Sample Quote Format

Create a simple Excel file with columns:
| Товар | Количество | Единица | Цена | Поставщик |
|-------|------------|---------|------|-----------|
| Стол офисный | 10 | шт | 5000 | ООО "Мебель+" |
| Кресло компьютерное | 10 | штук | 3500 | ООО "Мебель+" |

Upload it to test the bot!

## 🔍 What to Expect

After uploading a file, you'll see:
```
✅ Сохранено!

📁 Категория: мебель
👥 Поставщики: ООО "Мебель+"
📦 Товаров: 2
```

After running `/compare` with 2+ suppliers:
```
📊 АНАЛИЗ КОММЕРЧЕСКИХ ПРЕДЛОЖЕНИЙ

Сравнено товаров: 2
Средняя экономия: 12.5%

🏆 РЕКОМЕНДАЦИИ:

1. Стол офисный
   Рекомендация: Поставщик А
   Цена: 4800 шт
   Экономия: 4%
   Причина: Лучшая цена при сохранении качества
```

## 🆘 Troubleshooting

### Bot doesn't respond
- Check `TELEGRAM_TOKEN` in `.env`
- Verify bot is running (check terminal)

### "MongoDB connection error"
- Ensure MongoDB is running
- Check `MONGO_URL` in `.env`

### "AI extraction failed"
- Verify API keys are correct
- Check API quotas/limits
- Review logs for specific errors

### "No items to compare"
- Upload at least 2 files with overlapping items
- Ensure item names are similar across suppliers

## 📚 Next Steps

Once basic functionality works:

1. **Read full README.md** for detailed documentation
2. **Review IMPLEMENTATION_SUMMARY.md** to understand architecture
3. **Customize categories** in `src/category_intelligence.py`
4. **Add more unit conversions** in `src/unit_normalizer.py`
5. **Test with real procurement documents**

## 🎯 Tips for Best Results

### For Better Parsing:
- Use clear, structured documents (tables work best)
- Include supplier name in document
- Specify units of measurement explicitly
- Include all important specs (brand, model, size, etc.)

### For Better Comparison:
- Upload at least 2-3 supplier quotes
- Ensure similar item naming across suppliers
- Include complete data (price, quantity, unit)

### For Better Clarifications:
- System auto-detects missing: VAT, delivery date, warranty
- Category-specific requirements apply automatically
- Edit generated messages before sending if needed

## 🔗 Resources

- **Full Documentation**: `README.md`
- **Architecture Details**: See plan file
- **Implementation Details**: `IMPLEMENTATION_SUMMARY.md`

## ✅ Verification Checklist

Before considering setup complete:

- [ ] Bot responds to `/start`
- [ ] Can create project with `/new_project`
- [ ] Can upload a file successfully
- [ ] File parsing extracts items correctly
- [ ] Category is detected automatically
- [ ] `/compare` shows recommendations (with 2+ files)
- [ ] `/export` downloads Excel file
- [ ] Excel has "Сводная" and "Сравнение" sheets

## 🎉 Success!

If all checks pass, your procurement bot is ready for real use!

Try it with actual supplier quotes to see the magic happen! 🚀
