import os
import re
import html
import asyncio
import logging
import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
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

# Render/Koyeb port xatosini oldini olish
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Kino Bot v2.0 Live")

def start_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

threading.Thread(target=start_server, daemon=True).start()

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MAIN_ADMIN = int(os.getenv("MAIN_ADMIN", "6887251996"))
db.DB_PATH = os.getenv("DB_PATH", "database.db")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# States
(
    ADD_CODE_CHOICE, ADD_CODE_MANUAL, ADD_PART, ADD_VIDEO, ADD_NAME, 
    ADD_YEAR, ADD_QUALITY, ADD_LANG, ADD_RATING,
    SEARCH_CODE, SEARCH_NAME,
    SEND_OFFER, SEND_ADMIN_MSG,
    PROMO_INPUT, PAYMENT_CHECK,
    DELETE_MOVIE_INPUT
) = range(16)

# Reply Menyular
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

def get_admin_settings_inline():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Karta va Narxlar", callback_data="adm_set_prices"), InlineKeyboardButton("🎁 Trial Kunlar", callback_data="adm_set_trial")],
        [InlineKeyboardButton("👥 Referral Mukofoti", callback_data="adm_set_ref"), InlineKeyboardButton("📢 Majburiy Kanallar", callback_data="adm_set_mand")],
        [InlineKeyboardButton("🔄 Sync Markazi", callback_data="adm_sync_hub"), InlineKeyboardButton("💾 Zaxira (Backup)", callback_data="adm_backup_hub")],
        [InlineKeyboardButton("📊 Bot Statistikasi", callback_data="adm_stats_hub")]
    ])
    # Majburiy obunani tekshirish
async def check_mandatory_sub(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if db.is_admin(user_id, MAIN_ADMIN):
        return True
    channels = db.get_mandatory_channels()
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=ch["channel_id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            continue
    return True

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if db.is_user_blocked(user.id):
        await update.message.reply_text("⛔ Siz botdan bloklangansiz.")
        return

    db.add_user(user.id, user.username or "", user.full_name)

    # Referral tekshiruvi
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                ref_id = int(arg.split("_")[1])
                if ref_id != user.id:
                    conn = db.get_connection()
                    c = conn.cursor()
                    c.execute("SELECT * FROM referrals WHERE referred_id = ?", (user.id,))
                    if not c.fetchone():
                        rew_type = db.get_setting("referral_reward_type", "free_days")
                        rew_val = float(db.get_setting("referral_reward_value", "3"))
                        c.execute("INSERT INTO referrals (referrer_id, referred_id, reward_type, reward_value, status, created_date) VALUES (?, ?, ?, ?, 'completed', datetime('now'))",
                                  (ref_id, user.id, rew_type, rew_val))
                        conn.commit()
                        if rew_type == "free_days":
                            db.add_days_subscription(ref_id, int(rew_val))
                            await context.bot.send_message(ref_id, f"🎉 <b>Do'stingiz qo'shildi!</b> Hisobingizga +{int(rew_val)} kun bepul obuna berildi!", parse_mode="HTML")
                    conn.close()
            except Exception as e:
                logging.error(f"Ref error: {e}")

    # Majburiy obuna tekshiruvi
    is_subbed = await check_mandatory_sub(user.id, context)
    if not is_subbed:
        channels = db.get_mandatory_channels()
        kb_buttons = [[InlineKeyboardButton(f"📢 {ch['channel_name'] or 'Kanal'}", url=ch['channel_url'])] for ch in channels]
        kb_buttons.append([InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_mand_sub")])
        await update.message.reply_text(
            "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_buttons)
        )
        return

    await update.message.reply_text(
        f"Assalomu alaykum, <b>{html.escape(user.full_name)}</b>!\n<b>Kino Bot v2.0</b> ga xush kelibsiz.\nKino kodini yuboring yoki menyudan foydalaning:",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )

# Asosiy Menyu Routeri
async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_user_blocked(user_id):
        return

    text = update.message.text

    if text == "🎬 KINOLAR":
        await update.message.reply_text("🎬 <b>Kinolar bo'limi:</b>", parse_mode="HTML", reply_markup=get_movies_menu_keyboard())
    elif text == "💳 OBUNA":
        await update.message.reply_text("💳 <b>Obuna bo'limi:</b>", parse_mode="HTML", reply_markup=get_subscription_menu_keyboard())
    elif text == "👤 PROFIL":
        await update.message.reply_text("👤 <b>Shaxsiy profilingiz:</b>", parse_mode="HTML", reply_markup=get_profile_menu_keyboard())
    elif text == "⚙️ SOZLAMALAR":
        await update.message.reply_text("⚙️ <b>Sozlamalar:</b>", parse_mode="HTML", reply_markup=get_settings_user_keyboard())
    elif text == "◀️ Orqaga":
        await update.message.reply_text("Asosiy menyu:", reply_markup=get_main_menu_keyboard())
    elif text == "📝 Kod yozish":
        await update.message.reply_text("Kino kodini kiriting (masalan: <code>101</code>):", parse_mode="HTML")
        return SEARCH_CODE
    elif text == "🔍 Nom yozish":
        await update.message.reply_text("Kino nomini kiriting:", parse_mode="HTML")
        return SEARCH_NAME
    elif text == "❤️ Sevimlilar":
        await show_favorites(update, context)
    elif text == "📊 Obuna holati":
        sub = db.get_user_subscription(user_id)
        if sub or db.is_admin(user_id, MAIN_ADMIN):
            end_date = sub["end_date"] if sub else "Cheksiz (Admin)"
            await update.message.reply_text(f"✅ <b>Obunangiz faol!</b>\nTugash sanasi: <code>{end_date}</code>", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ <b>Sizda faol obuna yo'q.</b>", parse_mode="HTML")
    elif text == "💰 Rejalar va narxlar":
        await show_plans(update, context)
    elif text == "🎟️ Promo-kod kiritish":
        await update.message.reply_text("Promo-kodni kiriting:", parse_mode="HTML")
        return PROMO_INPUT
    elif text == "🎁 Bepul 3 kun":
        await handle_trial(update, context)
    elif text == "👥 Do'stni taklif qil":
        bot_me = await context.bot.get_me()
        await update.message.reply_text(
            f"👥 <b>Do'stingizni taklif qiling:</b>\n<code>https://t.me/{bot_me.username}?start=ref_{user_id}</code>",
            parse_mode="HTML"
        )
    elif text == "📈 Statistika":
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM user_watch_history WHERE user_id = ?", (user_id,))
        w = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM favorites WHERE user_id = ?", (user_id,))
        f = c.fetchone()["cnt"]
        conn.close()
        await update.message.reply_text(f"📊 Ko'rilgan: {w} ta\n❤️ Sevimlilar: {f} ta", parse_mode="HTML")
    elif text == "⏰ Obuna muddati":
        sub = db.get_user_subscription(user_id)
        msg = f"⏰ Muddat: <code>{sub['end_date']}</code>" if sub else "Faol obuna yo'q."
        await update.message.reply_text(msg, parse_mode="HTML")
    elif text == "💬 Taklif yuborish":
        await update.message.reply_text("Taklifingizni yozing:")
        return SEND_OFFER
    elif text == "🆘 Adminga murojaat":
        await update.message.reply_text("Murojaatingizni yozing:")
        return SEND_ADMIN_MSG
    elif text == "🔔 Bildirishnomalar":
        await update.message.reply_text("🔔 Bildirishnomalar yoqilgan.")
    elif text.isdigit():
        await deliver_movie_by_code(update, context, text)
        # Kino yetkazish logikasi
async def deliver_movie_by_code(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    user_id = update.effective_user.id
    if not db.has_active_subscription(user_id, MAIN_ADMIN):
        await update.message.reply_text("🔒 <b>Kino ko'rish uchun obuna kerak!</b>\n💳 OBUNA bo'limidan to'lov qiling.", parse_mode="HTML")
        return

    movies = db.get_movies_by_code(code)
    if not movies:
        await update.message.reply_text("❌ Bunday kodli kino topilmadi.")
        return

    conn = db.get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO user_watch_history (user_id, movie_code, watched_at) VALUES (?, ?, datetime('now'))", (user_id, code))
    conn.commit()
    conn.close()

    if len(movies) == 1:
        await send_single_movie(update.message, movies[0])
    else:
        buttons = [[InlineKeyboardButton(f"▶️ {m['part']}-qism", callback_data=f"getpart_{m['id']}")] for m in movies]
        await update.message.reply_text(
            f"🎬 <b>{html.escape(movies[0]['name'])}</b> ({len(movies)} ta qism)\nQismni tanlang:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

async def send_single_movie(target, m):
    caption = (
        f"🎬 <b>{html.escape(m['name'])}</b>\n\n"
        f"📅 Yili: {m['year']}\n"
        f"💾 Sifati: {m['quality']}\n"
        f"🌐 Tili: {m['language']}\n"
        f"⭐ Reyting: {m['rating']}/5.0\n"
        f"🔑 Kodi: <code>{m['code']}</code> (Qism: {m['part']})"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ 1", callback_data=f"rate_{m['code']}_1"),
            InlineKeyboardButton("⭐ 2", callback_data=f"rate_{m['code']}_2"),
            InlineKeyboardButton("⭐ 3", callback_data=f"rate_{m['code']}_3"),
            InlineKeyboardButton("⭐ 4", callback_data=f"rate_{m['code']}_4"),
            InlineKeyboardButton("⭐ 5", callback_data=f"rate_{m['code']}_5"),
        ],
        [InlineKeyboardButton("❤️ Sevimlilarga qo'shish", callback_data=f"fav_{m['code']}")]
    ])
    await target.reply_video(video=m["file_id"], caption=caption, parse_mode="HTML", reply_markup=kb)

# Callback Router
async def global_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()

    if data.startswith("rate_"):
        _, code, val = data.split("_")
        db.add_rating(user_id, code, int(val))
        await query.answer(f"⭐ {val} ball qabul qilindi!", show_alert=True)

    elif data.startswith("fav_"):
        code = data.split("_")[1]
        try:
            conn = db.get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO favorites (user_id, movie_code, added_at) VALUES (?, ?, datetime('now'))", (user_id, code))
            conn.commit()
            conn.close()
            await query.answer("❤️ Sevimlilarga qo'shildi!", show_alert=True)
        except Exception:
            await query.answer("Allaqachon sevimlilarda bor.", show_alert=True)

    elif data.startswith("getpart_"):
        mid = int(data.split("_")[1])
        m = db.get_movie_by_id(mid)
        if m:
            await send_single_movie(query.message, m)

    elif data == "check_mand_sub":
        if await check_mandatory_sub(user_id, context):
            await query.message.delete()
            await context.bot.send_message(user_id, "✅ Obuna tasdiqlandi!", reply_markup=get_main_menu_keyboard())
        else:
            await query.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)

    elif data.startswith("pay_app_"):
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
        c.execute("UPDATE pending_payments SET status = 'rejected' WHERE id = ?", (pay_id,))
        conn.commit()
        conn.close()
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")

    elif data == "adm_stats_hub":
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM users")
        u_cnt = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM subscriptions WHERE status = 'active'")
        s_cnt = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM movies")
        m_cnt = c.fetchone()["cnt"]
        c.execute("SELECT name, request_count FROM movies ORDER BY request_count DESC LIMIT 5")
        top_movies = c.fetchall()
        conn.close()
        text = f"📊 <b>Bot Statistikasi:</b>\n\n👥 Foydalanuvchilar: {u_cnt}\n💳 Obunachilar: {s_cnt}\n🎬 Kinolar: {m_cnt}\n\n<b>Top 5 Kino:</b>\n"
        for i, tm in enumerate(top_movies, 1):
            text += f"{i}. {tm['name']} — {tm['request_count']} marta\n"
        await query.message.reply_text(text, parse_mode="HTML")

    elif data == "adm_backup_hub":
        zf = backup_restore.create_backup_zip()
        if zf:
            with open(zf, "rb") as doc:
                await context.bot.send_document(user_id, document=doc, caption="📦 <b>Baza Zaxirasi</b>", parse_mode="HTML")
            os.remove(zf)

# Qidiruv va Murojaat Handlerlari
async def search_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await deliver_movie_by_code(update, context, update.message.text.strip())
    return ConversationHandler.END

async def search_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = db.search_movies_by_name(update.message.text.strip())
    if not results:
        await update.message.reply_text("❌ Kino topilmadi.")
        return ConversationHandler.END
    msg = "🔍 <b>Topilgan kinolar:</b>\n\n" + "\n".join([f"🎬 <b>{r['name']}</b> ({r['year']}) — Kod: <code>{r['code']}</code>" for r in results])
    await update.message.reply_text(msg, parse_mode="HTML")
    return ConversationHandler.END

async def offer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO offers (user_id, username, full_name, message, created_at) VALUES (?, ?, ?, ?, datetime('now'))", (u.id, u.username, u.full_name, update.message.text))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Taklif yuborildi.")
    return ConversationHandler.END

async def admin_msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO admin_requests (user_id, username, full_name, message, status, created_at) VALUES (?, ?, ?, ?, 'pending', datetime('now'))", (u.id, u.username, u.full_name, update.message.text))
    conn.commit()
    conn.close()
    await context.bot.send_message(MAIN_ADMIN, f"🆘 <b>Yangi murojaat:</b> {u.full_name} (@{u.username}):\n\n{update.message.text}", parse_mode="HTML")
    await update.message.reply_text("✅ Murojaat adminga yuborildi.")
    return ConversationHandler.END

async def handle_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT used FROM trial_subscriptions WHERE user_id = ?", (uid,))
    row = c.fetchone()
    if row and row["used"] == 1:
        await update.message.reply_text("❌ Siz trial olgansiz.")
    else:
        days = int(db.get_setting("trial_days", "3"))
        c.execute("INSERT OR REPLACE INTO trial_subscriptions (user_id, trial_days, start_date, end_date, used) VALUES (?, ?, datetime('now'), datetime('now', '+3 days'), 1)", (uid, days))
        db.add_days_subscription(uid, days)
        conn.commit()
        await update.message.reply_text(f"🎉 Sizga {days} kun bepul berildi!")
    conn.close()

async def promo_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    code = update.message.text.strip().upper()
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM promo_codes WHERE code = ? AND is_active = 1", (code,))
    p = c.fetchone()
    if not p:
        await update.message.reply_text("❌ Bunday promo-kod yo'q.")
    else:
        c.execute("SELECT * FROM promo_uses WHERE promo_id = ? AND user_id = ?", (p["id"], uid))
        if c.fetchone():
            await update.message.reply_text("❌ Bu kodni ishlatgansiz.")
        else:
            c.execute("INSERT INTO promo_uses (promo_id, user_id, used_at) VALUES (?, ?, datetime('now'))", (p["id"], uid))
            c.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE id = ?", (p["id"],))
            conn.commit()
            days = int(p["duration_days"] or p["discount_value"])
            db.add_days_subscription(uid, days)
            await update.message.reply_text(f"🎉 Promo qabul qilindi: +{days} kun!")
    conn.close()
    return ConversationHandler.END

# To'lov Handlerlari
async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"1 oylik — {db.get_setting('price_1', '5000')} so'm", callback_data="buy_1"),
         InlineKeyboardButton(f"3 oylik — {db.get_setting('price_3', '15000')} so'm", callback_data="buy_3")],
        [InlineKeyboardButton(f"6 oylik — {db.get_setting('price_6', '30000')} so'm", callback_data="buy_6"),
         InlineKeyboardButton(f"12 oylik — {db.get_setting('price_12', '60000')} so'm", callback_data="buy_12")]
    ])
    await update.message.reply_text("💰 Obuna rejasini tanlang:", reply_markup=kb)

async def plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    m = int(q.data.split("_")[1])
    context.user_data["pay_months"] = m
    context.user_data["pay_amount"] = db.get_setting(f"price_{m}", "5000")
    await q.edit_message_text(
        f"💳 Karta: <code>{db.get_setting('card_number')}</code>\n👤 Egasi: {db.get_setting('card_holder')}\nSumma: {context.user_data['pay_amount']} so'm\n\nChekni (rasm/fayl) yuboring:",
        parse_mode="HTML"
    )
    return PAYMENT_CHECK

async def payment_check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    fid = update.message.photo[-1].file_id if update.message.photo else (update.message.document.file_id if update.message.document else "")
    ftype = "photo" if update.message.photo else "document"
    if not fid:
        await update.message.reply_text("Chek yuboring!")
        return PAYMENT_CHECK

    conn = db.get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO pending_payments (user_id, username, full_name, months, amount, check_file_id, check_type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', datetime('now'))",
              (u.id, u.username, u.full_name, context.user_data["pay_months"], context.user_data["pay_amount"], fid, ftype))
    pid = c.lastrowid
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_app_{pid}"), InlineKeyboardButton("❌ Rad etish", callback_data=f"pay_rej_{pid}")]])
    cap = f"💳 Chek: {u.full_name} | {context.user_data['pay_months']} oy | {context.user_data['pay_amount']} so'm"
    if ftype == "photo":
        await context.bot.send_photo(MAIN_ADMIN, photo=fid, caption=cap, reply_markup=kb)
    else:
        await context.bot.send_document(MAIN_ADMIN, document=fid, caption=cap, reply_markup=kb)

    await update.message.reply_text("✅ Chek adminga yuborildi.")
    return ConversationHandler.END
    # Kino Qo'shish (/add Conversation)
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id, MAIN_ADMIN):
        return ConversationHandler.END
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔢 Avto Kod", callback_data="c_auto"), InlineKeyboardButton("✍️ Qo'lda", callback_data="c_man")]])
    await update.message.reply_text("Kino kodi turi:", reply_markup=kb)
    return ADD_CODE_CHOICE

async def add_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "c_auto":
        context.user_data["code"] = db.get_next_movie_code()
        await q.edit_message_text(f"Kod: {context.user_data['code']}\nQism raqami (masalan 1):")
        return ADD_PART
    await q.edit_message_text("Kino kodini yozing:")
    return ADD_CODE_MANUAL

async def add_manual_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["code"] = update.message.text.strip()
    await update.message.reply_text("Qism raqamini kiriting:")
    return ADD_PART

async def add_part(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["part"] = int(update.message.text.strip() or 1)
    await update.message.reply_text("Kino videosini yuboring:")
    return ADD_VIDEO

async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video:
        await update.message.reply_text("Video yuboring!")
        return ADD_VIDEO
    context.user_data["fid"] = update.message.video.file_id
    await update.message.reply_text("Kino nomi:")
    return ADD_NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Yili:")
    return ADD_YEAR

async def add_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["year"] = update.message.text.strip()
    await update.message.reply_text("Sifati (1080p, 720p):")
    return ADD_QUALITY

async def add_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quality"] = update.message.text.strip()
    await update.message.reply_text("Tili:")
    return ADD_LANG

async def add_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lang"] = update.message.text.strip()
    await update.message.reply_text("Reytingi (masalan: 5.0):")
    return ADD_RATING

async def add_rating_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = float(update.message.text.strip())
    except:
        r = 5.0
    ud = context.user_data
    db.add_movie(ud["code"], ud["name"], ud["quality"], ud["year"], ud["lang"], r, ud["fid"], ud["part"])
    await update.message.reply_text(f"🎉 <b>Kino saqlandi!</b>\nNom: {ud['name']} | Kod: <code>{ud['code']}</code> | Qism: {ud['part']}", parse_mode="HTML")
    return ConversationHandler.END

# O'chirish (/delete Conversation)
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id, MAIN_ADMIN):
        return ConversationHandler.END
    await update.message.reply_text("O'chiriladigan kino kodini kiriting:")
    return DELETE_MOVIE_INPUT

async def delete_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM movies WHERE code = ?", (code,))
    cnt = c.rowcount
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ {cnt} ta kino o'chirildi.")
    return ConversationHandler.END

# Sevimlilar
async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT m.code, m.name, m.year FROM favorites f JOIN movies m ON f.movie_code = m.code WHERE f.user_id = ?", (uid,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("❤️ Sevimlilar bo'sh.")
        return
    await update.message.reply_text("❤️ <b>Sevimlilar:</b>\n\n" + "\n".join([f"🎬 {r['name']} — Kod: <code>{r['code']}</code>" for r in rows]), parse_mode="HTML")

# Sync Tizimi
async def sync_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id, MAIN_ADMIN):
        return
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM movies ORDER BY id ASC")
    movies = c.fetchall()
    conn.close()
    await update.message.reply_text(f"🔄 {len(movies)} ta kino uzatilmoqda...")
    for m in movies:
        cap = f"#KINO_SYNC\nCode: {m['code']}\nName: {m['name']}\nYear: {m['year']}\nQuality: {m['quality']}\nLang: {m['language']}\nRating: {m['rating']}\nPart: {m['part']}"
        try:
            await context.bot.send_video(update.effective_user.id, video=m["file_id"], caption=cap)
            await asyncio.sleep(0.05)
        except Exception:
            pass

async def sync_recv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id, MAIN_ADMIN):
        return
    cap = update.message.caption or ""
    if "#KINO_SYNC" not in cap or not update.message.video:
        return
    data = dict(line.split(":", 1) for line in cap.split("\n") if ":" in line)
    db.add_movie(
        code=data.get("Code", "").strip(),
        name=data.get("Name", "").strip(),
        quality=data.get("Quality", "").strip(),
        year=data.get("Year", "").strip(),
        language=data.get("Lang", "").strip(),
        rating=float(data.get("Rating", 5.0)),
        file_id=update.message.video.file_id,
        part=int(data.get("Part", 1))
    )
    await update.message.reply_text(f"✅ Sync qabul qilindi: {data.get('Name')}")

# Admin Buyruqlari: /block, /unblock
async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id, MAIN_ADMIN) or not context.args:
        return
    uid = int(context.args[0])
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET is_blocked = 1 WHERE id = ?", (uid,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"⛔ User {uid} bloklandi.")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id, MAIN_ADMIN) or not context.args:
        return
    uid = int(context.args[0])
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET is_blocked = 0 WHERE id = ?", (uid,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ User {uid} blokdan chiqarildi.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi.", reply_markup=get_main_menu_keyboard())
    return ConversationHandler.END

# Asosiy main funksiyasi
def main():
    db.init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.bot_data["MAIN_ADMIN"] = MAIN_ADMIN

    # 7 kunlik avtomatik backup
    sched = AsyncIOScheduler()
    sched.add_job(backup_restore.auto_backup_job, "interval", days=7, args=[app])
    sched.start()

    # Asosiy buyruqlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", lambda u, c: u.message.reply_text("⚙️ <b>Admin Boshqaruv Markazi:</b>", parse_mode="HTML", reply_markup=get_admin_settings_inline()) if db.is_admin(u.effective_user.id, MAIN_ADMIN) else None))
    app.add_handler(CommandHandler("sync_send", sync_send))
    app.add_handler(CommandHandler("block", block_user))
    app.add_handler(CommandHandler("unblock", unblock_user))

    # Add Movie Conv
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ADD_CODE_CHOICE: [CallbackQueryHandler(add_choice, pattern="^c_")],
            ADD_CODE_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_manual_code)],
            ADD_PART: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_part)],
            ADD_VIDEO: [MessageHandler(filters.VIDEO, add_video)],
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_year)],
            ADD_QUALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_quality)],
            ADD_LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_lang)],
            ADD_RATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_rating_finish)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    # Delete Movie Conv
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("delete", delete_start)],
        states={DELETE_MOVIE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    # Inputs Conv
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex("^📝 Kod yozish$"), lambda u, c: SEARCH_CODE)], states={SEARCH_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_code_handler)]}, fallbacks=[CommandHandler("cancel", cancel)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex("^🔍 Nom yozish$"), lambda u, c: SEARCH_NAME)], states={SEARCH_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_name_handler)]}, fallbacks=[CommandHandler("cancel", cancel)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex("^💬 Taklif yuborish$"), lambda u, c: SEND_OFFER)], states={SEND_OFFER: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_handler)]}, fallbacks=[CommandHandler("cancel", cancel)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex("^🆘 Adminga murojaat$"), lambda u, c: SEND_ADMIN_MSG)], states={SEND_ADMIN_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_msg_handler)]}, fallbacks=[CommandHandler("cancel", cancel)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex("^🎟️ Promo-kod kiritish$"), lambda u, c: PROMO_INPUT)], states={PROMO_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_input_handler)]}, fallbacks=[CommandHandler("cancel", cancel)]))
    app.add_handler(ConversationHandler(entry_points=[CallbackQueryHandler(plan_callback, pattern="^buy_")], states={PAYMENT_CHECK: [MessageHandler(filters.PHOTO | filters.Document.ALL, payment_check_handler)]}, fallbacks=[CommandHandler("cancel", cancel)]))

    # Router va Sync Handlerlar
    app.add_handler(CallbackQueryHandler(global_callback_router))
    app.add_handler(MessageHandler(filters.VIDEO & filters.CaptionRegex("#KINO_SYNC"), sync_recv))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_router))

    print("Kino Bot v2.0 to'liq kuch bilan ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
    