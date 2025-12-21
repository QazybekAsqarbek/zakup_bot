# 🔧 Fixing Non-Responsive Commands

## Your Issue: Commands `/compare`, `/clarify`, `/analysis` Don't Respond

### Root Cause
The bot is running the OLD version without the new commands. You need to **restart the bot** to load the new code.

---

## ✅ Solution (3 Steps)

### Step 1: Verify Setup (Optional but Recommended)

```bash
python scripts/verify_setup.py
```

This will check:
- Python version
- Dependencies
- Configuration (.env)
- MongoDB connection
- All modules

**Expected output**:
```
🎉 ALL CHECKS PASSED!
✅ Your bot is ready to run: python src/main.py
```

---

### Step 2: Stop Current Bot

In the terminal where the bot is running:
1. Press `Ctrl+C` to stop the bot
2. Wait for "Stopped polling" message

---

### Step 3: Restart Bot

```bash
python src/main.py
```

**What you should see**:
```
🔥 Connected to MongoDB: smartprocure
INFO - ✅ Database connected & Commands set
Bot is running...
```

---

## 🧪 Test Commands

After restart, in Telegram:

### 1. Check Commands Menu
- Tap the menu button (☰) next to the message input
- You should see ALL 7 commands:
  - 🚀 Начало
  - 📁 Новый проект
  - **🏆 Сравнить предложения** ← NEW
  - **📝 Запросить уточнения** ← NEW
  - **📊 Полный анализ** ← NEW
  - 📥 Скачать Excel
  - ❓ Справка

### 2. Test /compare
```
/compare
```

**Expected response**:
```
Выберите проект для сравнения:
🏆 Офисная мебель 2025
🏆 плитки
```

### 3. Test /clarify
```
/clarify
```

**Expected response**:
```
Выберите проект для запроса уточнений:
📝 Офисная мебель 2025
📝 плитки
```

---

## ⚠️ Important Notes

### For /compare to Work:
You need **at least 2 quotes** with **similar items**.

**Example**:
- File 1 (Supplier A): "Плитка керамическая 50x50" - 100 руб
- File 2 (Supplier B): "Плитка 50x50" - 95 руб

These will be grouped and compared.

**Won't work with**:
- Only 1 uploaded file
- Completely different items in each file
- Items with very different names

### For /clarify to Work:
The system detects missing fields based on **category**.

**Example missing fields**:
- **Строительные материалы**: срок поставки, НДС
- **Электроника**: гарантия, страна производства

If all fields are present, you'll see:
```
✅ Все данные полные! Уточнения не требуются.
```

---

## 🐛 Still Not Working?

### Check Logs

Look for errors in the terminal:

**Good (Commands working)**:
```
INFO - Bot is running...
```

**Bad (Import error)**:
```
ERROR - ModuleNotFoundError: No module named 'src.comparator'
```
**Fix**: `pip install -r requirements.txt`

**Bad (Config error)**:
```
ERROR - DEEPSEEK_API_KEY not found
```
**Fix**: Check your `.env` file

---

### Manual Verification

Test if modules load correctly:

```python
python -c "from src.comparator import quote_comparator; print('✅ OK')"
python -c "from src.clarifier import auto_clarifier; print('✅ OK')"
python -c "from src.category_intelligence import category_intelligence; print('✅ OK')"
python -c "from src.unit_normalizer import unit_normalizer; print('✅ OK')"
```

All should print `✅ OK`

---

## 📊 Understanding the Screenshot

Looking at your screenshot, I can see:

1. ✅ **Bot parsed the file successfully**
   - Detected supplier: "Сибирская Керамика"
   - Saved 1 item to MongoDB

2. ❌ **Commands `/compare` and `/clarify` didn't respond**
   - This confirms the bot needs restart

3. ✅ **Command `/export` worked**
   - Shows you're on an older version where export existed

**After restart**: `/compare` and `/clarify` will work just like `/export`!

---

## 🎯 Complete Workflow After Restart

```
1. /new_project Тест
2. Upload file from Supplier A (with 5 items)
3. Upload file from Supplier B (with same 5 items)
4. /compare → Select "Тест" project
   ✅ See comparison and recommendations
5. /clarify → Select "Тест" project
   ✅ See clarification requests (if any missing fields)
6. /export → Select "Тест" project
   ✅ Download Excel with 2 sheets:
      - Сводная (all items + normalized data)
      - Сравнение (recommendations)
```

---

## 💡 Tips

### Get Better Comparisons
- Use structured files (Excel tables work best)
- Keep item names consistent across suppliers
- Include all specs (brand, size, material)

### Get Clarification Requests
- Upload incomplete quotes (missing delivery date, warranty, etc.)
- System auto-detects based on product category

### Faster Processing
- Upload smaller files first (<5MB)
- Use Excel instead of scanned PDFs when possible

---

## 🆘 Emergency Reset

If nothing works, try full reset:

```bash
# 1. Stop bot
Ctrl+C

# 2. Clear Python cache
find . -type d -name __pycache__ -exec rm -r {} +

# 3. Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# 4. Restart MongoDB
docker-compose restart

# 5. Start bot
python src/main.py
```

---

## ✅ Success Checklist

After restart, verify:
- [ ] Bot starts without errors
- [ ] See "✅ Database connected & Commands set" in logs
- [ ] Menu shows all 7 commands in Telegram
- [ ] `/compare` shows project selection
- [ ] `/clarify` shows project selection
- [ ] `/analysis` shows project selection
- [ ] `/export` still works (with enhanced features)

---

**Once all checked ✅, your bot is fully operational!** 🚀

For detailed troubleshooting, see `TROUBLESHOOTING.md`
