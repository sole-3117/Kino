import os
import asyncio
import logging

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from db import init, is_admin, add_user, has_active_sub, set_subscription, add_movie, get_movie, get_setting, inc_failed
from states import AddMovie, SubscriptionCheck

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MAIN_ADMIN = int(os.getenv("MAIN_ADMIN", "0"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------ START ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await add_user(u.id, u.username)

    if u.id == MAIN_ADMIN or await is_admin(u.id):
        await update.message.reply_text("Admin panelga xush kelibsiz!\n/addfilm — kino qo‘shish")
        return

    if await has_active_sub(u.id):
        await update.message.reply_text(
            "🎬 Kino kodini yuboring!\nMasalan: K123"
        )
        return

    prices = {
        "30":  await get_setting("price_1m", "35000"),
        "90":  await get_setting("price_3m", "90000"),
        "180": await get_setting("price_6m", "160000"),
        "365": await get_setting("price_12m", "300000"),
    }

    kb = [
        [InlineKeyboardButton(f"1 oy — {prices['30']} so‘m",  callback_data="sub_30")],
        [InlineKeyboardButton(f"3 oy — {prices['90']} so‘m",  callback_data="sub_90")],
        [InlineKeyboardButton(f"6 oy — {prices['180']} so‘m", callback_data="sub_180")],
        [InlineKeyboardButton(f"12 oy — {prices['365']} so‘m",callback_data="sub_365")],
    ]

    text = (
        "⚠️ Ushbu bot faqat obunachilar uchun ishlaydi!\n\n"
        f"Karta: {await get_setting('card_number')}\n"
        f"Egasi: {await get_setting('card_holder')}\n\n"
        "To‘g‘ri miqdorda to‘lang!\nChek rasmini yuboring."
    )

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))


# ------------------ KINO QIDIRISH ------------------

async def find_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = update.message.text.strip()

    if not await has_active_sub(u.id):
        await update.message.reply_text("Obuna faol emas. /start ni bosing.")
        await inc_failed(u.id)
        return

    movie = await get_movie(text)
    if not movie:
        await update.message.reply_text("Bunday kod topilmadi 😔")
        return

    code, title, qual, year, lang, rat, file_id = movie[0:7]

    caption = (
        f"🎬 <b>{title}</b>\n"
        f"📀 Sifat: {qual or '—'}\n"
        f"📅 Yil: {year or '—'}\n"
        f"🗣️ Til: {lang or '—'}\n"
        f"⭐️ Baho: {rat or '—'}"
    )

    await update.message.reply_video(file_id, caption=caption, parse_mode="HTML")


# ------------------ OBUNA TANLASH VA CHEK ------------------

async def sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("sub_"):
        return

    days = int(query.data.split("_")[1])
    price_key = f"price_{days//30 if days<=30 else days//30*10 if days<=90 else days//30*5 if days<=180 else 12}m"
    price = await get_setting(price_key, "35000")

    context.user_data["sub_days"] = days
    context.user_data["sub_price"] = price

    text = (
        f"To‘lov miqdori: <b>{price} so‘m</b>\n"
        f"Karta: {await get_setting('card_number')}\n"
        f"Ism: {await get_setting('card_holder')}\n\n"
        "Chek (rasm yoki fayl) yuboring:"
    )

    await query.edit_message_text(text, parse_mode="HTML")
    return SubscriptionCheck.CHECK


async def receive_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    file_id = None

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id

    if not file_id:
        await update.message.reply_text("Faqat rasm yoki hujjat yuboring!")
        return SubscriptionCheck.CHECK

    days = context.user_data.get("sub_days", 30)

    kb = [
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"acc_{u.id}_{days}")],
        [InlineKeyboardButton("❌ Rad etish",   callback_data=f"rej_{u.id}")],
    ]

    caption = (
        f"Yangi chek!\n\n"
        f"🆔 {u.id}\n"
        f"@{u.username or 'yo‘q'}\n"
        f"Obuna: {days} kun"
    )

    await context.bot.send_photo(
        chat_id=MAIN_ADMIN,
        photo=file_id,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(kb)
    )

    await update.message.reply_text("Chekingiz ko‘rib chiqilmoqda. Javobni kuting...")
    return ConversationHandler.END


async def admin_decide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, uid_str, *extra = q.data.split("_")
    uid = int(uid_str)

    if action == "acc":
        days = int(extra[0]) if extra else 30
        await set_subscription(uid, days)
        await context.bot.send_message(uid, f"✅ Obuna {days} kunlik faollashtirildi!")
        await q.edit_message_caption(caption=q.message.caption + "\n\n✅ TASDIQLANDI")
    else:
        await context.bot.send_message(uid, "❌ To‘lov rad etildi. Qayta urinib ko‘ring.")
        await q.edit_message_caption(caption=q.message.caption + "\n\n❌ RAD ETILDI")


# ------------------ /addfilm — KINO QO‘SHISH ------------------

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if u.id != MAIN_ADMIN and not await is_admin(u.id):
        await update.message.reply_text("Ruxsat yo‘q!")
        return ConversationHandler.END

    await update.message.reply_text("🎥 Videoni yuboring")
    return AddMovie.VIDEO


async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video:
        await update.message.reply_text("Video yuboring!")
        return AddMovie.VIDEO

    context.user_data["file_id"] = update.message.video.file_id
    await update.message.reply_text("Kino nomi (title)?")
    return AddMovie.TITLE


async def add_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text.strip()
    await update.message.reply_text("Sifati? (720p, 1080p, ...)")
    return AddMovie.QUALITY


async def add_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quality"] = update.message.text.strip()
    await update.message.reply_text("Chiqarilgan yili?")
    return AddMovie.YEAR


async def add_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["year"] = int(update.message.text.strip())
    except:
        await update.message.reply_text("Yil raqam bo‘lishi kerak!")
        return AddMovie.YEAR

    await update.message.reply_text("Tili? (UZB, RUS, ENG, ...)")
    return AddMovie.LANGUAGE


async def add_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["language"] = update.message.text.strip()
    await update.message.reply_text("Baho? (IMDb 7.2, Kinopoisk 8.1, ...)")
    return AddMovie.RATING


async def add_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["rating"] = update.message.text.strip()
    await update.message.reply_text("Noyob kod bering (masalan: K456 yoki MOV123)")
    return AddMovie.CODE


async def add_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    success = await add_movie(code, context.user_data, update.effective_user.id)

    if success:
        await update.message.reply_text(f"✅ Kino qo‘shildi! Kod: <b>{code}</b>", parse_mode="HTML")
    else:
        await update.message.reply_text("Bu kod allaqachon mavjud!")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi.")
    context.user_data.clear()
    return ConversationHandler.END


# ------------------ STATISTIKA (oddiy versiya) ------------------

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if u.id != MAIN_ADMIN and not await is_admin(u.id):
        return

    async with aiosqlite.connect(db.DB_FILE) as db:
        total = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        active = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE sub_until > datetime('now')"
        )).fetchone())[0]

    text = (
        f"📊 Statistik\n\n"
        f"Jami foydalanuvchilar: {total}\n"
        f"Faol obunachilar: {active}\n"
        # keyinchalik blocked va oddiy qo‘shsa bo‘ladi
    )

    await update.message.reply_text(text)


def main():
    app = Application.builder().token(TOKEN).build()

    # oddiy buyruqlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))

    # kino qidirish — har qanday matn
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, find_movie))

    # obuna jarayoni
    sub_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(sub_callback, pattern="^sub_")],
        states={
            SubscriptionCheck.CHECK: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_check)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(sub_conv)

    # admin tasdiqlash
    app.add_handler(CallbackQueryHandler(admin_decide, pattern="^(acc|rej)_"))

    # kino qo‘shish jarayoni
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("addfilm", add_start)],
        states={
            AddMovie.VIDEO:    [MessageHandler(filters.VIDEO, add_video)],
            AddMovie.TITLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_title)],
            AddMovie.QUALITY:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_quality)],
            AddMovie.YEAR:     [MessageHandler(filters.TEXT & ~filters.COMMAND, add_year)],
            AddMovie.LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_lang)],
            AddMovie.RATING:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_rating)],
            AddMovie.CODE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, add_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(add_conv)

    asyncio.run(init())
    print("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
