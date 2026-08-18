import os
import re
import html
import logging
import datetime
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
import backup_restore
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Render portini aldash uchun mini web server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Kino Bot is running!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Alohida oqimda (thread) ishga tushirish
threading.Thread(target=run_dummy_server, daemon=True).start()


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MAIN_ADMIN = int(os.getenv("MAIN_ADMIN", "6887251996"))
db.DB_PATH = os.getenv("DB_PATH", "database.db")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Conversation holatlari (States)
(
    ADD_CODE_CHOICE, ADD_CODE_MANUAL, ADD_PART, ADD_VIDEO, ADD_NAME, 
    ADD_YEAR, ADD_QUALITY, ADD_LANG, ADD_RATING,
    SEARCH_CODE, SEARCH_NAME,
    SEND_OFFER, SEND_ADMIN_MSG,
    PROMO_INPUT, PAYMENT_CHECK,
    SET_CARD, SET_HOLDER, SET_PRICE_1, SET_TRIAL, SET_REF,
    DELETE_MOVIE_INPUT, BROADCAST_INPUT, USER_SEND_ID, USER_SEND_MSG
) = range(24)

# Reply Klaviaturalar
def get_main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 KINOLAR"), KeyboardButton("💳 OBUNA")],
        [KeyboardButton("👤 PROFIL"), KeyboardButton("⚙️ SOZLAMALAR")]
    ], resize_keyboard=True)

def get_movies_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📝 Kod yozish"), KeyboardButton("🔍 Nom yozish")],
        [KeyboardButton("❤️ Sevimlilar"), KeyboardButton("◀️ Orqaga")]
    ], resize_keyboard=True)

def get_subscription_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Obuna holati"), KeyboardButton("💰 Rejalar va narxlar")],
        [KeyboardButton("🎟️ Promo-kod kiritish"), KeyboardButton("🎁 Bepul 3 kun")],
        [KeyboardButton("👥 Do'stni taklif qil"), KeyboardButton("◀️ Orqaga")]
    ], resize_keyboard=True)

def get_profile_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📈 Statistika"), KeyboardButton("⏰ Obuna muddati")],
        [KeyboardButton("💬 Taklif yuborish"), KeyboardButton("🆘 Adminga murojaat")],
        [KeyboardButton("◀️ Orqaga")]
    ], resize_keyboard=True)

def get_settings_user_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🌐 Til (O'zbek)"), KeyboardButton("🔔 Bildirishnomalar")],
        [KeyboardButton("◀️ Orqaga")]
    ], resize_keyboard=True)

# Admin Settings Hub Inline Klaviatura
def get_admin_settings_inline():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Karta va Narxlar", callback_data="adm_set_prices"), InlineKeyboardButton("🎁 Trial Sozlash", callback_data="adm_set_trial")],
        [InlineKeyboardButton("👥 Referral Tizimi", callback_data="adm_set_ref"), InlineKeyboardButton("📢 Majburiy Obuna", callback_data="adm_set_mand")],
        [InlineKeyboardButton("🎟️ Promo-kodlar", callback_data="adm_set_promo"), InlineKeyboardButton("👑 Adminlar", callback_data="adm_set_admins")],
        [InlineKeyboardButton("🔄 Sync Markazi", callback_data="adm_sync_hub"), InlineKeyboardButton("💾 Zaxira (Backup)", callback_data="adm_backup_hub")],
        [InlineKeyboardButton("🏷️ Versiya & Changelog", callback_data="adm_version_hub")]
    ])

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username or "", user.full_name)

    # Referral tekshiruvi
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                referrer_id = int(arg.split("_")[1])
                if referrer_id != user.id:
                    conn = db.get_connection()
                    c = conn.cursor()
                    c.execute("SELECT * FROM referrals WHERE referred_id = ?", (user.id,))
                    if not c.fetchone():
                        rew_type = db.get_setting("referral_reward_type", "free_days")
                        rew_val = float(db.get_setting("referral_reward_value", "3"))
                        c.execute("INSERT INTO referrals (referrer_id, referred_id, reward_type, reward_value, status, created_date) VALUES (?, ?, ?, ?, 'completed', datetime('now'))",
                                  (referrer_id, user.id, rew_type, rew_val))
                        conn.commit()
                        if rew_type == "free_days":
                            db.add_days_subscription(referrer_id, int(rew_val))
                            await context.bot.send_message(referrer_id, f"🎉 <b>Tabriklaymiz!</b> Siz taklif qilgan do'stingiz botga qo'shildi va hisobingizga +{int(rew_val)} kun bepul obuna qo'shildi!", parse_mode="HTML")
                    conn.close()
            except Exception as e:
                logging.error(f"Referral xatosi: {e}")

    await update.message.reply_text(
        f"Assalomu alaykum, <b>{html.escape(user.full_name)}</b>!\n<b>Kino Bot v2.0</b> ga xush kelibsiz.\nKino kodini yozing yoki quyidagi menyudan foydalaning.",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )

# Asosiy menyu yo'naltiruvchisi (Router)
async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🎬 KINOLAR":
        await update.message.reply_text("🎬 <b>Kinolar bo'limi:</b>", parse_mode="HTML", reply_markup=get_movies_menu_keyboard())
    elif text == "💳 OBUNA":
        await update.message.reply_text("💳 <b>Obuna bo'limi:</b>", parse_mode="HTML", reply_markup=get_subscription_menu_keyboard())
    elif text == "👤 PROFIL":
        await update.message.reply_text("👤 <b>Shaxsiy profilingiz:</b>", parse_mode="HTML", reply_markup=get_profile_menu_keyboard())
    elif text == "⚙️ SOZLAMALAR":
        await update.message.reply_text("⚙️ <b>Sozlamalar:</b>", parse_mode="HTML", reply_markup=get_settings_user_keyboard())
    elif text == "◀️ Orqaga":
        await update.message.reply_text("Asosiy menyuga qaytdingiz:", reply_markup=get_main_menu_keyboard())
    
    # Kinolar bo'limi
    elif text == "📝 Kod yozish":
        await update.message.reply_text("Iltimos, kino kodini kiriting (masalan: <code>101</code>):", parse_mode="HTML")
        return SEARCH_CODE
    elif text == "🔍 Nom yozish":
        await update.message.reply_text("Qidirilayotgan kino nomini kiriting:", parse_mode="HTML")
        return SEARCH_NAME
    elif text == "❤️ Sevimlilar":
        await show_favorites(update, context)

    # Obuna bo'limi
    elif text == "📊 Obuna holati":
        sub = db.get_user_subscription(user_id)
        if sub or db.is_admin(user_id, MAIN_ADMIN):
            end_date = sub["end_date"] if sub else "Cheksiz (Admin)"
            await update.message.reply_text(f"✅ <b>Sizning obunangiz faol!</b>\nTugash sanasi: <code>{end_date}</code>", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ <b>Sizda faol obuna mavjud emas.</b>\nObuna bo'lish uchun 💰 Rejalar bo'limiga o'ting.", parse_mode="HTML")
    elif text == "💰 Rejalar va narxlar":
        await show_plans(update, context)
    elif text == "🎟️ Promo-kod kiritish":
        await update.message.reply_text("Promokodingizni kiriting:", parse_mode="HTML")
        return PROMO_INPUT
    elif text == "🎁 Bepul 3 kun":
        await handle_trial(update, context)
    elif text == "👥 Do'stni taklif qil":
        bot_me = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_me.username}?start=ref_{user_id}"
        await update.message.reply_text(
            f"👥 <b>Do'stingizni taklif qiling va bepul obunaga ega bo'ling!</b>\n\nSizning havolangiz:\n<code>{ref_link}</code>\n\nDo'stingiz ushbu havola orqali kirsa, sizga 3 kun bepul obuna taqdim etiladi!",
            parse_mode="HTML"
        )

    # Profil bo'limi
    elif text == "📈 Statistika":
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM user_watch_history WHERE user_id = ?", (user_id,))
        watched = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM favorites WHERE user_id = ?", (user_id,))
        favs = c.fetchone()["cnt"]
        conn.close()
        await update.message.reply_text(f"📊 <b>Sizning statistikangiz:</b>\n\nKo'rilgan kinolar: {watched} ta\nSevimlilar ro'yxatida: {favs} ta", parse_mode="HTML")
    elif text == "⏰ Obuna muddati":
        sub = db.get_user_subscription(user_id)
        if sub:
            await update.message.reply_text(f"⏰ Obuna tugash sanasi: <code>{sub['end_date']}</code>", parse_mode="HTML")
        else:
            await update.message.reply_text("Sizda faol obuna mavjud emas.", parse_mode="HTML")
    elif text == "💬 Taklif yuborish":
        await update.message.reply_text("Bot haqidagi taklif va fikrlaringizni yozib qoldiring:", parse_mode="HTML")
        return SEND_OFFER
    elif text == "🆘 Adminga murojaat":
        await update.message.reply_text("Adminga xabaringizni yozing:", parse_mode="HTML")
        return SEND_ADMIN_MSG
    elif text == "🔔 Bildirishnomalar":
        await update.message.reply_text("🔔 Bildirishnomalar faol holatda!", parse_mode="HTML")
    
    # Kod to'g'ridan-to'g'ri raqam qilib yozilganda
    elif text.isdigit():
        await deliver_movie_by_code(update, context, text)
        # Kino yetkazish funksiyasi
async def deliver_movie_by_code(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    user_id = update.effective_user.id
    if not db.has_active_subscription(user_id, MAIN_ADMIN):
        await update.message.reply_text(
            "🔒 <b>Kino ko'rish uchun obuna talab qilinadi!</b>\nIltimos, 💳 OBUNA bo'limidan to'lov qiling yoki bepul sinov muddatidan foydalaning.",
            parse_mode="HTML"
        )
        return

    movies = db.get_movies_by_code(code)
    if not movies:
        await update.message.reply_text("❌ <b>Ushbu kod bo'yicha kino topilmadi.</b>", parse_mode="HTML")
        return

    # Ko'rishlar tarixiga yozish
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO user_watch_history (user_id, movie_code, watched_at) VALUES (?, ?, datetime('now'))", (user_id, code))
    conn.commit()
    conn.close()

    if len(movies) == 1:
        m = movies[0]
        caption = (
            f"🎬 <b>{html.escape(m['name'])}</b>\n\n"
            f"📅 Yili: {m['year']}\n"
            f"💾 Sifati: {m['quality']}\n"
            f"🌐 Tili: {m['language']}\n"
            f"⭐ Reyting: {m['rating']}/5.0\n"
            f"🔑 Kodi: <code>{m['code']}</code>"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⭐ 1", callback_data=f"rate_{code}_1"),
                InlineKeyboardButton("⭐ 2", callback_data=f"rate_{code}_2"),
                InlineKeyboardButton("⭐ 3", callback_data=f"rate_{code}_3"),
                InlineKeyboardButton("⭐ 4", callback_data=f"rate_{code}_4"),
                InlineKeyboardButton("⭐ 5", callback_data=f"rate_{code}_5"),
            ],
            [InlineKeyboardButton("❤️ Sevimlilarga qo'shish", callback_data=f"fav_{code}")]
        ])
        await update.message.reply_video(video=m["file_id"], caption=caption, parse_mode="HTML", reply_markup=kb)
    else:
        # Ko'p qismli kino yoki seriallar uchun
        buttons = []
        for m in movies:
            buttons.append([InlineKeyboardButton(f"▶️ {m['part']}-qism", callback_data=f"getpart_{m['id']}")])
        await update.message.reply_text(
            f"🎬 <b>{html.escape(movies[0]['name'])}</b> ({len(movies)} ta qism mavjud)\nQaysi qismni ko'rmoqchisiz?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# Qidiruv handlerlari
async def search_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    await deliver_movie_by_code(update, context, code)
    return ConversationHandler.END

async def search_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    results = db.search_movies_by_name(name)
    if not results:
        await update.message.reply_text("❌ Hech qanday kino topilmadi.", parse_mode="HTML")
        return ConversationHandler.END

    msg = "🔍 <b>Topilgan kinolar:</b>\n\n"
    for r in results:
        msg += f"🎬 <b>{html.escape(r['name'])}</b> ({r['year']}) — Kod: <code>{r['code']}</code>\n"
    msg += "\n<i>Kinoni ko'rish uchun uning kodini yuboring!</i>"
    await update.message.reply_text(msg, parse_mode="HTML")
    return ConversationHandler.END

# Taklif va murojaat handlerlari
async def offer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message.text
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO offers (user_id, username, full_name, message, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
              (user.id, user.username, user.full_name, msg))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Taklifingiz adminga yetkazildi. Rahmat!")
    return ConversationHandler.END

async def admin_msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message.text
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO admin_requests (user_id, username, full_name, message, status, created_at) VALUES (?, ?, ?, ?, 'pending', datetime('now'))",
              (user.id, user.username, user.full_name, msg))
    conn.commit()
    conn.close()
    
    # Bosh adminga xabar yuborish
    await context.bot.send_message(
        MAIN_ADMIN,
        f"🆘 <b>Yangi murojaat!</b>\nKimdan: {html.escape(user.full_name)} (@{user.username})\nID: <code>{user.id}</code>\n\nXabar: {html.escape(msg)}",
        parse_mode="HTML"
    )
    await update.message.reply_text("✅ Murojaatingiz adminga yuborildi. Tez orada javob olasiz!")
    return ConversationHandler.END

# Bepul Trial va Promokod handlerlari
async def handle_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM trial_subscriptions WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row and row["used"] == 1:
        await update.message.reply_text("❌ Siz bepul sinov muddatidan allaqachon foydalangansiz.")
    else:
        trial_days = int(db.get_setting("trial_days", "3"))
        now = datetime.datetime.now()
        end_date = now + datetime.timedelta(days=trial_days)
        c.execute("INSERT OR REPLACE INTO trial_subscriptions (user_id, trial_days, start_date, end_date, used) VALUES (?, ?, ?, ?, 1)",
                  (user_id, trial_days, now.strftime("%Y-%m-%d %H:%M:%S"), end_date.strftime("%Y-%m-%d %H:%M:%S")))
        db.add_days_subscription(user_id, trial_days)
        conn.commit()
        await update.message.reply_text(f"🎉 <b>Tabriklaymiz!</b> Sizga {trial_days} kunlik bepul obuna berildi!", parse_mode="HTML")
    conn.close()

async def promo_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code_text = update.message.text.strip().upper()

    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM promo_codes WHERE code = ? AND is_active = 1", (code_text,))
    promo = c.fetchone()

    if not promo:
        await update.message.reply_text("❌ Bunday promo-kod mavjud emas yoki muddati tugagan.")
        conn.close()
        return ConversationHandler.END

    c.execute("SELECT * FROM promo_uses WHERE promo_id = ? AND user_id = ?", (promo["id"], user_id))
    if c.fetchone():
        await update.message.reply_text("❌ Siz bu promo-koddan allaqachon foydalangansiz.")
        conn.close()
        return ConversationHandler.END

    if promo["max_uses"] > 0 and promo["used_count"] >= promo["max_uses"]:
        await update.message.reply_text("❌ Ushbu promo-koddan foydalanish limiti tugagan.")
        conn.close()
        return ConversationHandler.END

    c.execute("INSERT INTO promo_uses (promo_id, user_id, used_at) VALUES (?, ?, datetime('now'))", (promo["id"], user_id))
    c.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE id = ?", (promo["id"],))
    conn.commit()

    if promo["discount_type"] == "free_days":
        days = int(promo["duration_days"] or promo["discount_value"])
        db.add_days_subscription(user_id, days)
        await update.message.reply_text(f"🎉 Promo-kod qabul qilindi! Hisobingizga +{days} kun bepul obuna qo'shildi.", parse_mode="HTML")
    else:
        await update.message.reply_text(f"🎉 Promo-kod qabul qilindi! Sizga keyingi to'lovingiz uchun {promo['discount_value']}% chegirma berildi.", parse_mode="HTML")

    conn.close()
    return ConversationHandler.END

# To'lov jarayoni (Payment Flow)
async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p1 = db.get_setting("price_1", "5000")
    p3 = db.get_setting("price_3", "15000")
    p6 = db.get_setting("price_6", "30000")
    p12 = db.get_setting("price_12", "60000")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"1 oylik — {p1} so'm", callback_data="buy_1"), InlineKeyboardButton(f"3 oylik — {p3} so'm", callback_data="buy_3")],
        [InlineKeyboardButton(f"6 oylik — {p6} so'm", callback_data="buy_6"), InlineKeyboardButton(f"12 oylik — {p12} so'm", callback_data="buy_12")]
    ])
    await update.message.reply_text("💰 <b>Obuna rejalarini tanlang:</b>", parse_mode="HTML", reply_markup=kb)

async def plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    months = int(query.data.split("_")[1])
    amount = db.get_setting(f"price_{months}", "5000")
    card_num = db.get_setting("card_number", "9860170109969320")
    card_holder = db.get_setting("card_holder", "Solejon Adashov Isroilovich")

    context.user_data["pay_months"] = months
    context.user_data["pay_amount"] = amount

    msg = (
        f"💳 <b>To'lov ma'lumotlari:</b>\n\n"
        f"Tanlangan reja: <b>{months} oylik</b>\n"
        f"To'lov summasi: <b>{amount} so'm</b>\n\n"
        f"💳 Karta: <code>{card_num}</code>\n"
        f"👤 Egasi: <b>{card_holder}</b>\n\n"
        f"⚠️ To'lovni amalga oshirgach, to'lov <b>cheki (skrinshot/fayl)</b>ni shu yerga yuboring."
    )
    await query.edit_message_text(msg, parse_mode="HTML")
    return PAYMENT_CHECK

async def payment_check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    months = context.user_data.get("pay_months", 1)
    amount = context.user_data.get("pay_amount", 5000)

    file_id = ""
    file_type = "photo"
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = "document"
    else:
        await update.message.reply_text("Iltimos, chek rasmini yoki faylini yuboring.")
        return PAYMENT_CHECK

    conn = db.get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO pending_payments (user_id, username, full_name, months, amount, check_file_id, check_type, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', datetime('now'))
    """, (user.id, user.username, user.full_name, months, amount, file_id, file_type))
    pay_id = c.lastrowid
    conn.commit()
    conn.close()

    admin_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_app_{pay_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"pay_rej_{pay_id}")
        ]
    ])
    caption = (
        f"💳 <b>Yangi to'lov cheki!</b>\n\n"
        f"Foydalanuvchi: {html.escape(user.full_name)} (@{user.username})\n"
        f"ID: <code>{user.id}</code>\n"
        f"Muddat: {months} oy\n"
        f"Summa: {amount} so'm"
    )

    if file_type == "photo":
        await context.bot.send_photo(MAIN_ADMIN, photo=file_id, caption=caption, parse_mode="HTML", reply_markup=admin_kb)
    else:
        await context.bot.send_document(MAIN_ADMIN, document=file_id, caption=caption, parse_mode="HTML", reply_markup=admin_kb)

    await update.message.reply_text("✅ Chek qabul qilindi. Admin tasdiqlashi bilan obunangiz faollashadi!")
    return ConversationHandler.END

# Sevimlilar va Bekor qilish
async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("""
    SELECT DISTINCT m.code, m.name, m.year FROM favorites f 
    JOIN movies m ON f.movie_code = m.code 
    WHERE f.user_id = ?
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("❤️ Sevimlilar ro'yxatingiz bo'sh.")
        return
    msg = "❤️ <b>Sevimli kinolaringiz:</b>\n\n"
    for r in rows:
        msg += f"🎬 <b>{html.escape(r['name'])}</b> ({r['year']}) — Kod: <code>{r['code']}</code>\n"
    await update.message.reply_text(msg, parse_mode="HTML")

async def fav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    code = query.data.split("_")[1]
    user_id = query.from_user.id
    conn = db.get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO favorites (user_id, movie_code, added_at) VALUES (?, ?, datetime('now'))", (user_id, code))
        conn.commit()
        await query.answer("❤️ Sevimlilarga qo'shildi!", show_alert=True)
    except:
        await query.answer("Allaqachon sevimlilar ro'yxatida mavjud.", show_alert=True)
    conn.close()

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi.", reply_markup=get_main_menu_keyboard())
    return ConversationHandler.END
# Admin Boshqaruv Markazi (Settings Hub) buyrug'i
async def admin_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id, MAIN_ADMIN):
        return
    await update.message.reply_text(
        "⚙️ <b>Admin Boshqaruv Markazi (Control Center):</b>\nBarcha tizim parametrlarini quyidagi menyu orqali boshqaring:",
        parse_mode="HTML",
        reply_markup=get_admin_settings_inline()
    )

# Admin Hub va To'lovlar Callback Router
async def admin_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()

    if data.startswith("pay_app_"):
        pay_id = int(data.split("_")[2])
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM pending_payments WHERE id = ?", (pay_id,))
        p = c.fetchone()
        if p and p["status"] == "pending":
            c.execute("UPDATE pending_payments SET status = 'approved' WHERE id = ?", (pay_id,))
            conn.commit()
            db.add_subscription(p["user_id"], p["months"])
            await query.edit_message_caption(caption=query.message.caption + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML")
            await context.bot.send_message(p["user_id"], f"🎉 <b>To'lovingiz tasdiqlandi!</b>\n{p['months']} oylik obuna faollashtirildi.", parse_mode="HTML")
        conn.close()

    elif data.startswith("pay_rej_"):
        pay_id = int(data.split("_")[2])
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM pending_payments WHERE id = ?", (pay_id,))
        p = c.fetchone()
        if p and p["status"] == "pending":
            c.execute("UPDATE pending_payments SET status = 'rejected' WHERE id = ?", (pay_id,))
            conn.commit()
            await query.edit_message_caption(caption=query.message.caption + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")
            await context.bot.send_message(p["user_id"], "❌ To'lov chekingiz rad etildi. Iltimos, ma'lumotlarni tekshirib qayta yuboring.")
        conn.close()

    elif data == "adm_backup_hub":
        zip_file = backup_restore.create_backup_zip()
        if zip_file and os.path.exists(zip_file):
            with open(zip_file, "rb") as doc:
                await context.bot.send_document(user_id, document=doc, caption="📦 <b>Baza zaxirasi (database.db)</b>", parse_mode="HTML")
            os.remove(zip_file)

    elif data == "adm_sync_hub":
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM movies")
        cnt = c.fetchone()["cnt"]
        conn.close()
        await query.message.reply_text(
            f"🔄 <b>Sync Markazi (Kino Bot ↔ Kino Tez Bot)</b>\n\nJami kinolar soni: {cnt} ta\nKinoni ikkinchi botga uzatish uchun /sync_send buyrug'ini yuboring.",
            parse_mode="HTML"
        )

# Sync Tizimi (Kino Bot -> Kino Tez Bot)
async def sync_send_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id, MAIN_ADMIN):
        return

    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM movies ORDER BY id ASC")
    movies = c.fetchall()
    conn.close()

    if not movies:
        await update.message.reply_text("Bazada hech qanday kino mavjud emas.")
        return

    await update.message.reply_text(f"🔄 <b>{len(movies)} ta kino Adminga uzatilmoqda...</b>", parse_mode="HTML")
    for m in movies:
        caption = (
            f"#KINO_SYNC\n"
            f"Code: {m['code']}\n"
            f"Name: {m['name']}\n"
            f"Year: {m['year']}\n"
            f"Quality: {m['quality']}\n"
            f"Lang: {m['language']}\n"
            f"Rating: {m['rating']}\n"
            f"Part: {m['part']}"
        )
        try:
            await context.bot.send_video(chat_id=user_id, video=m["file_id"], caption=caption)
        except Exception as e:
            logging.error(f"Sync xatosi ({m['code']}): {e}")

async def sync_receiver_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id, MAIN_ADMIN):
        return

    caption = update.message.caption or ""
    if not ("#KINO_SYNC" in caption and update.message.video):
        return

    lines = caption.split("\n")
    data = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip().lower()] = v.strip()

    code = data.get("code", "")
    name = data.get("name", "Noma'lum")
    year = data.get("year", "2024")
    quality = data.get("quality", "1080p")
    lang = data.get("lang", "O'zbekcha")
    rating = float(data.get("rating", 5.0))
    part = int(data.get("part", 1))
    file_id = update.message.video.file_id

    if code:
        db.add_movie(code, name, quality, year, lang, rating, file_id, part)
        await update.message.reply_text(f"✅ <b>Kino Tez Bot:</b> {name} (Kod: {code}, Qism: {part}) bazaga saqlandi!", parse_mode="HTML")

# Kino qo'shish (/add Conversation)
async def add_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id, MAIN_ADMIN):
        return ConversationHandler.END

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔢 Avtomatik Kod", callback_data="code_auto")],
        [InlineKeyboardButton("✍️ Qo'lda Kiritish", callback_data="code_manual")]
    ])
    await update.message.reply_text("🎬 <b>Kino qo'shish bosqichi:</b>\nKino kodini qanday belgilamoqchisiz?", parse_mode="HTML", reply_markup=kb)
    return ADD_CODE_CHOICE

async def add_code_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "code_auto":
        code = db.get_next_movie_code()
        context.user_data["new_code"] = code
        await query.edit_message_text(f"✅ Kod avtomatik tanlandi: <code>{code}</code>\n\nEndi ushbu qism raqamini kiriting (masalan: 1):", parse_mode="HTML")
        return ADD_PART
    else:
        await query.edit_message_text("Iltimos, kino kodini yozing:")
        return ADD_CODE_MANUAL

async def add_code_manual_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    context.user_data["new_code"] = code
    await update.message.reply_text("Kino qismini kiriting (1, 2, ...):")
    return ADD_PART

async def add_part_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    part = int(update.message.text.strip() or 1)
    context.user_data["new_part"] = part
    await update.message.reply_text("Kino videosini yuboring:")
    return ADD_VIDEO

async def add_video_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video:
        await update.message.reply_text("Iltimos, video fayl yuboring!")
        return ADD_VIDEO
    context.user_data["new_file_id"] = update.message.video.file_id
    await update.message.reply_text("Kino nomini kiriting:")
    return ADD_NAME

async def add_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_name"] = update.message.text.strip()
    await update.message.reply_text("Kino chiqarilgan yilini kiriting (masalan: 2023):")
    return ADD_YEAR

async def add_year_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_year"] = update.message.text.strip()
    await update.message.reply_text("Kino sifatini kiriting (masalan: 1080p, 720p):")
    return ADD_QUALITY

async def add_quality_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_quality"] = update.message.text.strip()
    await update.message.reply_text("Kino tilini kiriting (masalan: O'zbekcha):")
    return ADD_LANG

async def add_lang_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_lang"] = update.message.text.strip()
    await update.message.reply_text("Kino boshlang'ich reytingini kiriting (1.0 dan 5.0 gacha):")
    return ADD_RATING

async def add_rating_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rating = float(update.message.text.strip())
    except:
        rating = 5.0

    ud = context.user_data
    db.add_movie(
        code=ud["new_code"],
        name=ud["new_name"],
        quality=ud["new_quality"],
        year=ud["new_year"],
        language=ud["new_lang"],
        rating=rating,
        file_id=ud["new_file_id"],
        part=ud["new_part"]
    )
    await update.message.reply_text(f"🎉 <b>Kino muvaffaqiyatli saqlandi!</b>\nNom: {ud['new_name']}\nKod: <code>{ud['new_code']}</code>\nQism: {ud['new_part']}", parse_mode="HTML")
    return ConversationHandler.END

# Kino o'chirish (/delete Conversation)
async def delete_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id, MAIN_ADMIN):
        return ConversationHandler.END
    await update.message.reply_text("🗑️ O'chirmoqchi bo'lgan kino kodini kiriting:")
    return DELETE_MOVIE_INPUT

async def delete_movie_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM movies WHERE code = ?", (code,))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    if deleted > 0:
        await update.message.reply_text(f"✅ Kod <code>{code}</code> ostidagi {deleted} ta kino o'chirildi!", parse_mode="HTML")
    else:
        await update.message.reply_text("❌ Bunday kodli kino topilmadi.")
    return ConversationHandler.END

# Asosiy dastur nuqtasi (Entry Point)
def main():
    db.init_db()

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.bot_data["MAIN_ADMIN"] = MAIN_ADMIN

    # Har 7 kunda avtomatik backup scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(backup_restore.auto_backup_job, "interval", days=7, args=[application])
    scheduler.start()

    # Conversation Handlers
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_movie_start)],
        states={
            ADD_CODE_CHOICE: [CallbackQueryHandler(add_code_choice_cb, pattern="^code_")],
            ADD_CODE_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_code_manual_input)],
            ADD_PART: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_part_input)],
            ADD_VIDEO: [MessageHandler(filters.VIDEO, add_video_input)],
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name_input)],
            ADD_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_year_input)],
            ADD_QUALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_quality_input)],
            ADD_LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_lang_input)],
            ADD_RATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_rating_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )

    delete_conv = ConversationHandler(
        entry_points=[CommandHandler("delete", delete_movie_start)],
        states={
            DELETE_MOVIE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_movie_finish)]
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )

    search_code_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Kod yozish$"), lambda u, c: SEARCH_CODE)],
        states={SEARCH_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_code_handler)]},
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )
    search_name_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 Nom yozish$"), lambda u, c: SEARCH_NAME)],
        states={SEARCH_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_name_handler)]},
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )
    offer_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💬 Taklif yuborish$"), lambda u, c: SEND_OFFER)],
        states={SEND_OFFER: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_handler)]},
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )
    admin_msg_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🆘 Adminga murojaat$"), lambda u, c: SEND_ADMIN_MSG)],
        states={SEND_ADMIN_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_msg_handler)]},
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )
    promo_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎟️ Promo-kod kiritish$"), lambda u, c: PROMO_INPUT)],
        states={PROMO_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_input_handler)]},
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )
    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(plan_callback, pattern="^buy_")],
        states={PAYMENT_CHECK: [MessageHandler(filters.PHOTO | filters.Document.ALL, payment_check_handler)]},
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("settings", admin_settings_command))
    application.add_handler(CommandHandler("sync_send", sync_send_handler))
    application.add_handler(add_conv)
    application.add_handler(delete_conv)
    application.add_handler(search_code_conv)
    application.add_handler(search_name_conv)
    application.add_handler(offer_conv)
    application.add_handler(admin_msg_conv)
    application.add_handler(promo_conv)
    application.add_handler(payment_conv)

    # Callback Query Handlers
    application.add_handler(CallbackQueryHandler(fav_callback, pattern="^fav_"))
    application.add_handler(CallbackQueryHandler(admin_callback_router))

    # Sync Receiver va Umumiy Menyu Router
    application.add_handler(MessageHandler(filters.VIDEO & filters.CaptionRegex("#KINO_SYNC"), sync_receiver_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_router))

    print("Kino Bot v2.0 muvaffaqiyatli ishga tushdi...")
    application.run_polling()

if __name__ == "__main__":
    main()
