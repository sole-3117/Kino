import os
import logging
import random
import string
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
)
import sqlite3
from contextlib import contextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
MAIN_ADMIN = int(os.getenv('MAIN_ADMIN'))

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database connection (SQLite)
DB_FILE = 'bot.db'

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Movies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                file_id TEXT NOT NULL
            )
        ''')
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                join_date TEXT
            )
        ''')
        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # Default settings
        default_settings = [
            ('fsub_channels', ''),
            ('ad_text', ''),
            ('ad_interval', '5'),
            ('ad_daily_limit', '10'),
            ('ad_schedule', '')
        ]
        for key, value in default_settings:
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                         (key, value))
        conn.commit()

init_db()

# Helper functions for DB
def add_user(user_id, username):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (id, username, join_date) VALUES (?, ?, ?)",
            (user_id, username, datetime.now().isoformat())
        )
        conn.commit()

def get_setting(key):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        return result[0] if result else None

def set_setting(key, value):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("REPLACE INTO settings (key, value) VALUES (?, ?)",
                      (key, value))
        conn.commit()

def add_movie(code, name, description, file_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO movies (code, name, description, file_id) VALUES (?, ?, ?, ?)",
            (code, name, description, file_id)
        )
        conn.commit()

def delete_movie(code):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movies WHERE code = ?", (code,))
        conn.commit()

def get_movie_by_code(code):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, file_id FROM movies WHERE code = ?",
                      (code,))
        return cursor.fetchone()

def search_movies(query):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT code, name FROM movies WHERE name LIKE ?",
                      (f"%{query}%",))
        return cursor.fetchall()

def get_all_users():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users")
        return [row[0] for row in cursor.fetchall()]

def generate_unique_code():
    while True:
        code = 'M' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if not get_movie_by_code(code):
            return code

# Ad tracking (in-memory for simplicity)
user_ad_counts = {}  # {user_id: {'requests': 0, 'ads_today': 0, 'last_ad_date': date}}

def reset_daily_ads():
    global user_ad_counts
    today = datetime.now().date()
    for user_id in list(user_ad_counts.keys()):
        if user_ad_counts[user_id]['last_ad_date'] != today:
            user_ad_counts[user_id]['ads_today'] = 0
            user_ad_counts[user_id]['last_ad_date'] = today

# Ad scheduler
scheduler = BackgroundScheduler()

def broadcast_ad(application: Application):
    ad_text = get_setting('ad_text')
    if not ad_text:
        return
    users = get_all_users()
    for user_id in users:
        try:
            application.bot.send_message(chat_id=user_id, text=ad_text)
        except Exception as e:
            logger.error(f"Failed to send ad to {user_id}: {e}")

def schedule_ads(application: Application):
    ad_schedule = get_setting('ad_schedule')
    if ad_schedule == 'hourly':
        scheduler.add_job(lambda: broadcast_ad(application),
                         CronTrigger(minute=0))
    elif ad_schedule == 'daily':
        scheduler.add_job(lambda: broadcast_ad(application),
                         CronTrigger(hour=12, minute=0))
    scheduler.start()

# Mandatory subscription check
async def check_subscription(update: Update, context: CallbackContext) -> bool:
    user_id = update.effective_user.id
    channels = get_setting('fsub_channels')
    if not channels:
        return True
    
    channels = channels.split(',')
    for channel in channels:
        try:
            member = await context.bot.get_chat_member(
                chat_id=channel.strip(),
                user_id=user_id
            )
            if member.status not in ('member', 'administrator', 'creator'):
                return False
        except Exception as e:
            logger.error(f"Error checking subscription: {e}")
            return False
    return True

async def force_subscribe_message(update: Update, context: CallbackContext):
    channels = get_setting('fsub_channels').split(',')
    keyboard = [
        [InlineKeyboardButton(f"Obuna bo'lish: {ch}",
                             url=f"https://t.me/{ch.lstrip('@')}")
         ] for ch in channels
    ]
    keyboard.append([InlineKeyboardButton("Tekshirish", callback_data='check_sub')])
    await update.message.reply_text(
        "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Command handlers
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    add_user(user.id, user.username)
    await update.message.reply_text("Salom! Kino kodini yuboring yoki nomini qidiring.")

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not await check_subscription(update, context):
        await force_subscribe_message(update, context)
        return

    # Track requests for ads
    if user_id not in user_ad_counts:
        user_ad_counts[user_id] = {
            'requests': 0,
            'ads_today': 0,
            'last_ad_date': datetime.now().date()
        }
    user_ad_counts[user_id]['requests'] += 1

    # Check for ad interval
    ad_interval = int(get_setting('ad_interval') or 5)
    ad_daily_limit = int(get_setting('ad_daily_limit') or 10)
    ad_text = get_setting('ad_text')
    
    if (ad_text and 
        user_ad_counts[user_id]['requests'] % ad_interval == 0 and 
        user_ad_counts[user_id]['ads_today'] < ad_daily_limit):
        await update.message.reply_text(ad_text)
        user_ad_counts[user_id]['ads_today'] += 1
        user_ad_counts[user_id]['last_ad_date'] = datetime.now().date()

    # Movie code or search
    movie = get_movie_by_code(text)
    if movie:
        name, description, file_id = movie
        caption = f"{name}\n{description}" if description else name
        await update.message.reply_video(video=file_id, caption=caption)
    else:
        results = search_movies(text)
        if results:
            response = "Topilgan kinolar:\n" + "\n".join(
                [f"{code}: {name}" for code, name in results]
            )
            await update.message.reply_text(response)
        else:
            await update.message.reply_text(
                "Kino topilmadi. Kod yoki nomni qayta kiriting."
            )

async def check_sub_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    if await check_subscription(update, context):
        await query.answer("Obuna tasdiqlandi! Botdan foydalaning.")
        await query.edit_message_text("Rahmat! Endi botdan foydalaning.")
    else:
        await query.answer("Hali obuna bo'lmagansiz.")

# Admin command decorator
def admin_only(func):
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        if update.effective_user.id != MAIN_ADMIN:
            await update.message.reply_text("Siz admin emassiz.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# Admin commands
@admin_only
async def add_movie_cmd(update: Update, context: CallbackContext):
    if not update.message.reply_to_message or not update.message.reply_to_message.video:
        await update.message.reply_text(
            "Video faylga reply qilib /add <nom> <tavsif> yozing."
        )
        return
    
    try:
        args = context.args
        if not args:
            await update.message.reply_text("Nom kiritilmadi.")
            return
            
        name = args[0]
        description = ' '.join(args[1:]) if len(args) > 1 else ''
        file_id = update.message.reply_to_message.video.file_id
        code = generate_unique_code()
        
        add_movie(code, name, description, file_id)
        await update.message.reply_text(f"Kino qo'shildi. Kod: {code}")
    
    except Exception as e:
        logger.error(f"Error in add_movie_cmd: {e}")
        await update.message.reply_text(f"Xato: {e}")

@admin_only
async def delete_movie_cmd(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("/delete <code>")
        return
        
    code = context.args[0]
    if get_movie_by_code(code):
        delete_movie(code)
        await update.message.reply_text(f"{code} o'chirildi.")
    else:
        await update.message.reply_text("Kod topilmadi.")

@admin_only
async def broadcast_cmd(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("/broadcast <matn>")
        return
        
    message = ' '.join(context.args)
    users = get_all_users()
    success_count = 0
    fail_count = 0
    
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to broadcast to {user_id}: {e}")
            fail_count += 1
            
    await update.message.reply_text(
        f"Xabar yuborildi.\nMuvaffaqiyatli: {success_count}\nMuvaffaqiyatsiz: {fail_count}"
    )

@admin_only
async def stats_cmd(update: Update, context: CallbackContext):
    users = get_all_users()
    await update.message.reply_text(f"Foydalanuvchilar soni: {len(users)}")

@admin_only
async def set_fsub_cmd(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text(
            "/set_fsub <kanal1,kanal2> (e.g., @channel1,@channel2)"
        )
        return
        
    channels = ','.join(context.args)
    set_setting('fsub_channels', channels)
    await update.message.reply_text("Majburiy obuna sozlandi.")

@admin_only
async def set_ad_cmd(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text(
            "/set_ad <matn> [interval] [daily_limit] [schedule]\nSchedule: hourly or daily"
        )
        return
        
    ad_text = context.args[0]
    set_setting('ad_text', ad_text)
    
    if len(context.args) > 1:
        set_setting('ad_interval', context.args[1])
    if len(context.args) > 2:
        set_setting('ad_daily_limit', context.args[2])
    if len(context.args) > 3:
        set_setting('ad_schedule', context.args[3])
        schedule_ads(context.application)
        
    await update.message.reply_text("Reklama sozlandi.")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('add', add_movie_cmd))
    application.add_handler(CommandHandler('delete', delete_movie_cmd))
    application.add_handler(CommandHandler('broadcast', broadcast_cmd))
    application.add_handler(CommandHandler('stats', stats_cmd))
    application.add_handler(CommandHandler('set_fsub', set_fsub_cmd))
    application.add_handler(CommandHandler('set_ad', set_ad_cmd))
    
    # Message handlers
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_handler(
        CallbackQueryHandler(check_sub_callback, pattern='check_sub')
    )

    # Start schedulers
    scheduler.add_job(reset_daily_ads, CronTrigger(hour=0, minute=0))
    schedule_ads(application)

    try:
        application.run_polling()
    finally:
        scheduler.shutdown()

if __name__ == '__main__':
    main()
