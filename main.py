import os
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_ADMIN = int(os.getenv("MAIN_ADMIN"))

# Conversation states
ADD_FILE, ADD_TITLE, ADD_YEAR, ADD_QUALITY, ADD_GENRE, ADD_LANG = range(6)
PAYMENT_INFO, PAYMENT_CHECK = range(2)

# Database setup
DB_NAME = "bot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            obuna_start TEXT,
            obuna_end TEXT,
            status TEXT DEFAULT 'oddiy',
            fail_count INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            title TEXT,
            file_id TEXT,
            year TEXT,
            quality TEXT,
            genre TEXT,
            language TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            user_id INTEGER,
            card TEXT,
            name TEXT,
            amount INTEGER,
            chek_file TEXT,
            status TEXT DEFAULT 'tasdiqlanmagan'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Helper functions
def generate_movie_code():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM movies")
    count = c.fetchone()[0] + 1
    conn.close()
    return f"M{count:05d}"

def is_admin(user_id):
    return user_id == MAIN_ADMIN

def add_user_if_not_exists(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def get_user_status(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT status, obuna_end FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        status, obuna_end = row
        if status == "faol" and obuna_end and datetime.strptime(obuna_end, "%Y-%m-%d") >= datetime.now():
            return "faol"
    return "oddiy"

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user_if_not_exists(user.id, user.username)
    await update.message.reply_text(
        "Salom! Kino botga xush kelibsiz. Oylik obuna 10 000 so'm.\n"
        "Kino ko‘rish uchun /pay bilan to‘lov qilishingiz mumkin."
    )

# /pay - to'lov jarayoni
async def pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user_if_not_exists(user.id, user.username)
    await update.message.reply_text(
        "Iltimos, quyidagi ma’lumotlarni yuboring:\n"
        "1️⃣ Karta raqami\n"
        "2️⃣ Ism Familiya\n"
        "3️⃣ Miqdor (faqat 10000 so'm)"
    )
    return PAYMENT_INFO

async def pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    try:
        card, name, amount = text.split("\n")
        amount = int(amount.strip())
        if amount != 10000:
            await update.message.reply_text("❌ Miqdor faqat 10000 so'm bo‘lishi kerak")
            return PAYMENT_INFO
        context.user_data['payment'] = {'card': card, 'name': name, 'amount': amount}
        await update.message.reply_text("Iltimos, to‘lov chekini yuboring (rasm yoki fayl)")
        return PAYMENT_CHECK
    except Exception as e:
        await update.message.reply_text("❌ Format noto‘g‘ri, qayta yuboring")
        return PAYMENT_INFO

async def pay_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("❌ Rasm yoki fayl yuboring")
        return PAYMENT_CHECK

    payment = context.user_data['payment']
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO payments (user_id, card, name, amount, chek_file) VALUES (?, ?, ?, ?, ?)",
              (user.id, payment['card'], payment['name'], payment['amount'], file_id))
    conn.commit()
    conn.close()

    # Adminga xabar
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Ha", callback_data=f"pay_ok_{user.id}"),
         InlineKeyboardButton("Yo'q", callback_data=f"pay_no_{user.id}")]
    ])
    await context.bot.send_message(MAIN_ADMIN, text=f"Foydalanuvchi @{user.username} to‘lov qildi. Chek tekshiring:", reply_markup=keyboard)
    await update.message.reply_text("To‘lov ma'lumotlari yuborildi, admin tasdiqlaydi ✅")
    return ConversationHandler.END

# Admin tasdiqlash callback
async def pay_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = int(data.split("_")[-1])
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if data.startswith("pay_ok"):
        start_date = datetime.now()
        end_date = start_date + timedelta(days=30)
        c.execute("UPDATE users SET status='faol', obuna_start=?, obuna_end=? WHERE id=?",
                  (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), user_id))
        c.execute("UPDATE payments SET status='tasdiqlangan' WHERE user_id=?", (user_id,))
        conn.commit()
        await context.bot.send_message(user_id, "✅ To‘lov tasdiqlandi. 30 kunlik obuna faollashdi!")
    else:
        c.execute("UPDATE payments SET status='tasdiqlanmagan' WHERE user_id=?", (user_id,))
        conn.commit()
        await context.bot.send_message(user_id, "❌ To‘lov tasdiqlanmadi. Iltimos, qayta yuboring.")
    conn.close()
    await query.edit_message_text("✅ Tasdiqlash bajarildi")

# /add - kino qo'shish (skeleton)
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Sizga ruxsat yo'q!")
        return ConversationHandler.END
    await update.message.reply_text("Iltimos, kino faylini yuboring (video/fayl).")
    return ADD_FILE

# Kino qo'shish step handlers
async def add_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_id = None
    if update.message.video:
        file_id = update.message.video.file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("❌ Fayl yuboring")
        return ADD_FILE
    context.user_data['movie'] = {'file_id': file_id}
    await update.message.reply_text("Kinoning nomini kiriting:")
    return ADD_TITLE

async def add_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['movie']['title'] = update.message.text
    await update.message.reply_text("Yilini kiriting:")
    return ADD_YEAR

async def add_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['movie']['year'] = update.message.text
    await update.message.reply_text("Sifatini kiriting:")
    return ADD_QUALITY

async def add_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['movie']['quality'] = update.message.text
    await update.message.reply_text("Janrini kiriting:")
    return ADD_GENRE

async def add_genre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['movie']['genre'] = update.message.text
    await update.message.reply_text("Tilini kiriting:")
    return ADD_LANG

async def add_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['movie']['language'] = update.message.text
    movie = context.user_data['movie']
    movie['code'] = generate_movie_code()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""INSERT INTO movies (code, title, file_id, year, quality, genre, language)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (movie['code'], movie['title'], movie['file_id'], movie['year'], movie['quality'], movie['genre'], movie['language']))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Kino qo‘shildi:\n"
                                    f"🎥 {movie['title']}\n📆 {movie['year']} | 📹 {movie['quality']}\n"
                                    f"🎞 {movie['genre']}\n🇺🇿 {movie['language']}\n🔢 Kino kodi: {movie['code']}")
    return ConversationHandler.END

# /delete, /stats handlerlar yuqorida mavjud (shu skelet)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Start / pay
    app.add_handler(CommandHandler("start", start))

    pay_conv = ConversationHandler(
        entry_points=[CommandHandler("pay", pay_start)],
        states={
            PAYMENT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_info)],
            PAYMENT_CHECK: [MessageHandler(filters.PHOTO | filters.Document.ALL, pay_check)],
        },
        fallbacks=[]
    )
    app.add_handler(pay_conv)
    app.add_handler(CallbackQueryHandler(pay_confirm, pattern="^pay_"))

    # Add movie
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ADD_FILE: [MessageHandler(filters.Document.ALL | filters.Video.ALL, add_file)],
            ADD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_title)],
            ADD_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_year)],
            ADD_QUALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_quality)],
            ADD_GENRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_genre)],
            ADD_LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_lang)],
        },
        fallbacks=[]
    )
    app.add_handler(add_conv)

    # Delete / stats
    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler("delete", delete_movie))
    app.add_handler(CommandHandler("stats", stats))

    app.run_polling()

if __name__ == "__main__":
    main()
