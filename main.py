# main.py
import logging
import sqlite3
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)

# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_ADMIN = int(os.getenv("MAIN_ADMIN"))

# Logging
logging.basicConfig(level=logging.INFO)

# Database helper
def init_db():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            obuna_start TEXT,
            obuna_end TEXT,
            status TEXT DEFAULT 'oddiy'
        )
    """)
    # Movies table
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
    # Payments table
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

# Helpers
def generate_movie_code():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM movies")
    count = c.fetchone()[0] + 1
    code = f"M{count:05d}"
    conn.close()
    return code

def get_user_status(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT status, obuna_end FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        status, obuna_end = row
        if status == "faol" and datetime.strptime(obuna_end, "%Y-%m-%d") >= datetime.now():
            return "faol"
        else:
            return "oddiy"
    return "oddiy"

# Start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (user.id, user.username))
    conn.commit()
    conn.close()
    await update.message.reply_text("Salom! Kino botga xush kelibsiz. Oylik obuna 10 000 so'm.")

# Admin check
def is_admin(user_id):
    return user_id == MAIN_ADMIN

# /add handler (skeleton)
async def add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Sizga ruxsat yo'q!")
        return
    await update.message.reply_text("Iltimos, kino faylini yuboring (video/hujjat).")
    # Keyingi step: fayl qabul qilish, nom, yil, sifat, janr, til → bazaga saqlash
    # Bu yerda ConversationHandler bilan step-by-step ishlash kerak

# /delete handler
async def delete_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Sizga ruxsat yo'q!")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Iltimos, kino kodini kiriting. Misol: /delete M00001")
        return
    code = args[0]
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("DELETE FROM movies WHERE code=?", (code,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"Kino {code} o‘chirildi ✅")

# /stats handler
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Sizga ruxsat yo'q!")
        return
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    # Faol oylik
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM users WHERE status='faol' AND obuna_end>=?", (today,))
    active_monthly = c.fetchone()[0]
    # Oddiy
    c.execute("SELECT COUNT(*) FROM users WHERE status='oddiy' OR obuna_end<?", (today,))
    oddiy = c.fetchone()[0]
    # Hamma
    c.execute("SELECT COUNT(*) FROM users")
    all_users = c.fetchone()[0]
    # Bloklangan: bu yerda logika uchun status='bloklangan'
    c.execute("SELECT COUNT(*) FROM users WHERE status='bloklangan'")
    blocked = c.fetchone()[0]
    conn.close()
    msg = f"""
📊 Statistika:
Oylik obunachilar: {active_monthly}
Oddiy obunachilar: {oddiy}
Hamma foydalanuvchilar: {all_users}
Bloklangan foydalanuvchilar: {blocked}
"""
    await update.message.reply_text(msg)

# Main function
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_movie))
    app.add_handler(CommandHandler("delete", delete_movie))
    app.add_handler(CommandHandler("stats", stats))

    # Run bot
    app.run_polling()

if __name__ == "__main__":
    main()
