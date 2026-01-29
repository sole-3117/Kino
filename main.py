import os
import random
import string
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

import db

# ================== CONFIG ==================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_ADMIN = int(os.getenv("MAIN_ADMIN"))

db.init_db()


# ================== HELPERS ==================
def is_admin(user_id: int) -> bool:
    return user_id == MAIN_ADMIN


def generate_code() -> str:
    return "M" + "".join(random.choices(string.digits, k=5))


async def check_force_sub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    channel = db.get_setting("force_sub")
    if not channel:
        return True

    try:
        member = await context.bot.get_chat_member(channel, update.effective_user.id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False


# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username)

    if not await check_force_sub(update, context):
        await update.message.reply_text(
            "❌ Botdan foydalanish uchun kanalga obuna bo‘ling."
        )
        return

    await update.message.reply_text(
        "🎬 Kino botga xush kelibsiz!\n\n"
        "Kino kodi yuboring yoki kino nomini yozing."
    )


async def add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.video:
        await update.message.reply_text("🎥 Videoga reply qilib /add yozing")
        return

    video = update.message.reply_to_message.video
    text = update.message.text.split(maxsplit=1)

    title = text[1] if len(text) > 1 else "Nomsiz kino"
    code = generate_code()

    db.add_movie(code, title, "", video.file_id)

    await update.message.reply_text(
        f"✅ Kino qo‘shildi\n\n"
        f"🎬 Nomi: {title}\n"
        f"🔑 Kodi: `{code}`",
        parse_mode="Markdown"
    )


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("❌ Kino kodi kiriting")
        return

    db.delete_movie(context.args[0])
    await update.message.reply_text("🗑 Kino o‘chirildi")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    text = update.message.text.replace("/broadcast", "").strip()
    if not text:
        await update.message.reply_text("Xabar matnini yozing")
        return

    with db.connect() as con:
        users = con.execute("SELECT id FROM users").fetchall()

    sent = 0
    for user_id, in users:
        try:
            await context.bot.send_message(user_id, text)
            sent += 1
        except Exception:
            pass

    await update.message.reply_text(f"📢 Yuborildi: {sent} ta foydalanuvchiga")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        f"👥 Foydalanuvchilar: {db.users_count()}"
    )


async def set_fsub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Kanal username kiriting")
        return

    db.set_setting("force_sub", context.args[0])
    await update.message.reply_text("✅ Majburiy obuna sozlandi")


async def set_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    text = update.message.text.replace("/set_ad", "").strip()
    db.set_setting("ad_text", text)
    await update.message.reply_text("📢 Reklama saqlandi")


# ================== MESSAGES ==================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_force_sub(update, context):
        await update.message.reply_text("❌ Avval kanalga obuna bo‘ling")
        return

    text = update.message.text.strip()

    movie = db.get_movie(text)
    if movie:
        _, title, desc, file_id = movie
        await update.message.reply_video(file_id, caption=title)
        return

    results = db.search_movie(text)
    if results:
        msg = "🔍 Topilgan kinolar:\n\n"
        for code, title in results[:10]:
            msg += f"🎬 {title} — `{code}`\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    await update.message.reply_text("❌ Kino topilmadi")


# ================== RUN ==================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_movie))
    app.add_handler(CommandHandler("delete", delete))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("set_fsub", set_fsub))
    app.add_handler(CommandHandler("set_ad", set_ad))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()