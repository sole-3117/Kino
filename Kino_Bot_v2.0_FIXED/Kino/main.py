import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler
from telegram.error import TelegramError
from apscheduler.schedulers.background import BackgroundScheduler
import db
import backup_restore

load_dotenv()

# ====================== CONFIG ======================
BOT_TOKEN = os.getenv('BOT_TOKEN')
MAIN_ADMIN_ID = int(os.getenv('MAIN_ADMIN', 0))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN .env'da topilmadi!")
if MAIN_ADMIN_ID == 0:
    raise ValueError("❌ MAIN_ADMIN .env'da to'g'ri o'rnatilmagan!")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================== HELPERS ======================

def is_admin(user_id):
    """Admin ekanligini tekshirish"""
    return db.is_admin(user_id, MAIN_ADMIN_ID)

async def send_error(update: Update, text: str):
    """Xato xabari yuborish (callback/message uchun)"""
    if update.message:
        try:
            await update.message.reply_text(text)
        except:
            pass
    elif update.callback_query:
        try:
            await update.callback_query.answer(text, show_alert=True)
        except:
            pass

async def send_safe(context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str, parse_mode='HTML', reply_markup=None):
    """Xavfsiz xabar yuborish"""
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
    except TelegramError as e:
        logger.warning(f"Send failed to {user_id}: {e}")
        # failed_sends orttirish
        with db.get_db_context() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET failed_sends=failed_sends+1 WHERE id=?", (user_id,))

async def get_main_menu():
    """Asosiy menyu tugmalari"""
    keyboard = [
        [InlineKeyboardButton("🎬 KINOLAR", callback_data="menu_movies")],
        [InlineKeyboardButton("💳 OBUNA", callback_data="menu_subscription")],
        [InlineKeyboardButton("👤 PROFIL", callback_data="menu_profile")],
        [InlineKeyboardButton("⚙️ SOZLAMALAR", callback_data="menu_settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ====================== START / HELP ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botni boshlash"""
    user = update.effective_user
    
    # Foydalanuvchi qoʻshish
    db.add_user(user.id, user.username or "N/A", user.full_name or "N/A")
    
    text = """
🎬 <b>Kino Bot v2.0</b>'ga xush kelibsiz!

Bu bot Uzbek kinolarini ko'rish uchun tuzilgan.

<b>Qanday ishlaydi:</b>
1. Kino kodini yozing (masalan: 000001)
2. Yoki kino nomini qidirib toping
3. Obuna bo'lish uchun rejalarga qarang
4. Sevimlilar va reyting qo'shishni unutmang!

/help — barcha buyruqlar
/cancel — bekor qilish
"""
    
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=await get_main_menu())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yordam"""
    user = update.effective_user
    
    text = """
<b>📚 FOYDALANUVCHI BUYRUQLARI:</b>
/start — boshlanish
/help — bu xabar
/profile — mening profilim
/sub — obuna holati
/promo — promo-kod kiritish
/offers — taklifni yuborish
/admin_send — adminga murojaat
/bot — bot haqida
/list — buyruqlar ro'yxati
/favorites — sevimlilar
/mystats — mening statistikam
/cancel — bekor qilish
"""
    
    if is_admin(user.id):
        text += """

<b>👨‍💼 ADMIN BUYRUQLARI:</b>
/add — kino qo'shish
/delete — kino o'chirish
/broadcast — hammaga xabar
/user_send — bitta foydalanuvchiga xabar
/user_sends — faol obunachilar yoki hammaga
/block — foydalanuvchini bloklash
/unblock — blokni ochish
/sub_manage — obunani uzaytirish/qisqartirish
/promo_admin — promo-kodlar paneli
/stats — statistika
/settings — narx va sozlamalar
/setversion — versiya
/addadmin — yangi admin qo'shish
/removeadmin — adminni o'chirish
/admins — adminlar ro'yxati
/backup — backup yaratish
/mandatory — majburiy obuna sozlash
/trial — trial obuna sozlash
/sync_start — ulashish (kinolar ro'yxati)
/sync_send — tanlangan kinolarni yuborish
/restore — backup'dan tiklash
"""
    
    await update.message.reply_text(text, parse_mode='HTML')

# ====================== MAIN MENU ======================

async def menu_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kinolar menyu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📝 Kod yozish", callback_data="movies_by_code")],
        [InlineKeyboardButton("🔍 Nom yozish", callback_data="movies_by_name")],
        [InlineKeyboardButton("❤️ Sevimlilar", callback_data="movies_favorites")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_main")]
    ]
    
    await query.edit_message_text(
        text="<b>🎬 KINOLAR</b>\n\nNima qilishni xohlaysiz?",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def movies_by_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kod boʻyicha kino qidirish"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="<b>Kino kodini kiriting:</b>\n(Masalan: 000001)",
        parse_mode='HTML'
    )
    
    context.user_data['mode'] = 'search_by_code'
    return 0

async def movies_by_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Nom boʻyicha kino qidirish"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="<b>Kino nomini kiriting:</b>",
        parse_mode='HTML'
    )
    
    context.user_data['mode'] = 'search_by_name'
    return 0

async def movies_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sevimlilar"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    favorites = db.get_favorites(user_id)
    if not favorites:
        await query.edit_message_text(
            text="<b>❤️ Sevimlilar</b>\n\nHaligina sevimli film yoʻq.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_movies")]
            ])
        )
        return
    
    keyboard = []
    for code in favorites[:10]:
        movie = db.get_movie_by_code(code)
        if movie:
            keyboard.append([InlineKeyboardButton(f"{movie['name'][:30]}", callback_data=f"view_movie_{code}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Orqaga", callback_data="menu_movies")])
    
    await query.edit_message_text(
        text="<b>❤️ SEVIMLILAR</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def view_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kino ko'rish"""
    query = update.callback_query
    await query.answer()
    
    code = query.data.split('_')[-1]
    movie = db.get_movie_by_code(code)
    
    if not movie:
        await query.answer("Kino topilmadi", show_alert=True)
        return
    
    user_id = query.from_user.id
    
    # Subscription tekshirish
    if not is_admin(user_id):
        if not db.has_active_subscription(user_id):
            await query.answer("Obuna mavjud emas!", show_alert=True)
            return
    
    # Video yuborish
    try:
        keyboard = [
            [InlineKeyboardButton("⭐ Reyting", callback_data=f"rate_{code}")],
            [
                InlineKeyboardButton(
                    "❤️ Sevimlilarga" if not db.is_favorite(user_id, code) else "💔 Sevimlilardan oʻchirish",
                    callback_data=f"favorite_{code}"
                )
            ],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_movies")]
        ]
        
        text = f"""
<b>{movie['name']}</b>

📅 <b>Yil:</b> {movie['year']}
🎬 <b>Sifat:</b> {movie['quality']}
🗣️ <b>Til:</b> {movie['language']}
⭐ <b>Reyting:</b> {movie['rating']}
🔑 <b>Kod:</b> {code}

<i>Videoni ko'rish uchun pastga qarang...</i>
"""
        
        try:
            await query.delete_message()
        except:
            pass
        
        await context.bot.send_video(
            chat_id=user_id,
            video=movie['file_id'],
            caption=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Request count orttirish
        db.increment_request_count(code)
        # Watch history
        db.add_watch_history(user_id, code)
        
    except TelegramError as e:
        logger.error(f"Video send error: {e}")
        await query.answer("Video yuborishda xato!", show_alert=True)

async def rate_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kinoni reytingla"""
    query = update.callback_query
    await query.answer()
    
    code = query.data.split('_')[-1]
    
    keyboard = [
        [
            InlineKeyboardButton("⭐", callback_data=f"rate_value_{code}_1"),
            InlineKeyboardButton("⭐⭐", callback_data=f"rate_value_{code}_2"),
            InlineKeyboardButton("⭐⭐⭐", callback_data=f"rate_value_{code}_3"),
        ],
        [
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"rate_value_{code}_4"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"rate_value_{code}_5"),
        ],
        [InlineKeyboardButton("◀️ Orqaga", callback_data=f"view_movie_{code}")]
    ]
    
    await query.edit_message_text(
        text="<b>Reytingni tanlang:</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def rate_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reyting saqlash"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    code = parts[2]
    rating = int(parts[3])
    
    db.add_rating(query.from_user.id, code, rating)
    
    await query.answer("✅ Reyting saqlandi!", show_alert=True)

async def favorite_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sevimlilarga qoʻshish/oʻchirish"""
    query = update.callback_query
    await query.answer()
    
    code = query.data.split('_')[-1]
    user_id = query.from_user.id
    
    if db.is_favorite(user_id, code):
        db.remove_favorite(user_id, code)
        text = "💔 Sevimlilardan oʻchirildi"
    else:
        db.add_favorite(user_id, code)
        text = "❤️ Sevimlilarga qoʻshildi"
    
    await query.answer(text, show_alert=True)

# ====================== SUBSCRIPTION MENU ======================

async def menu_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obuna menyu"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    sub = db.get_subscription(user_id)
    trial = db.get_trial_subscription(user_id)
    
    status = "Faol emas"
    if sub and db.has_active_subscription(user_id):
        end_date = datetime.fromisoformat(sub['end_date'])
        days_left = (end_date - datetime.now()).days
        status = f"✅ Faol ({days_left} kun qolgan)"
    elif trial:
        end_date = datetime.fromisoformat(trial['end_date'])
        days_left = max(0, (end_date - datetime.now()).days)
        status = f"🎁 Trial ({days_left} kun qolgan)"
    
    text = f"""
<b>💳 OBUNA</b>

<b>Holati:</b> {status}

<b>Rejalari:</b>
1️⃣ 1 oy: 50,000 so'm
3️⃣ 3 oy: 135,000 so'm (10% chegirma)
6️⃣ 6 oy: 255,000 so'm (15% chegirma)
1️⃣2️⃣ 12 oy: 450,000 so'm (25% chegirma)

<b>To'lov usuli:</b> Humo Card
9860170109969320 | Solejon Adashov
"""
    
    keyboard = [
        [InlineKeyboardButton("💰 Rejalar va narxlar", callback_data="sub_plans")],
        [InlineKeyboardButton("🎟️ Promo-kod kiritish", callback_data="sub_promo")],
        [InlineKeyboardButton("🎁 Bepul 3 kun", callback_data="sub_trial")],
        [InlineKeyboardButton("👥 Dostu taklif qil", callback_data="sub_referral")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_main")]
    ]
    
    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def sub_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obuna rejalari"""
    query = update.callback_query
    await query.answer()
    
    text = """
<b>💳 OBUNA REJALARIMIZ</b>

<b>Narxlar (chegirmali):</b>
1️⃣ 1 oy: <b>50,000 so'm</b>
3️⃣ 3 oy: <b>135,000 so'm</b> (10% chegirma)
6️⃣ 6 oy: <b>255,000 so'm</b> (15% chegirma)
1️⃣2️⃣ 12 oy: <b>450,000 so'm</b> (25% chegirma)

<b>To'lov usuli:</b>
<code>Humo Card: 9860170109969320</code>
<code>Egasi: Solejon Adashov Isroilovich</code>

<b>Qanday to'lash:</b>
1. Pul o'tkazing (chekni olib qo'ysin)
2. Chekni rasm/fayl sifatida yuboring
3. Admin tasdiqladi
4. Obuna avtomatik faollashadi

<b>⏰ Obuna mudati:</b> To'lov sanasidan hisoblab
"""
    
    keyboard = [
        [InlineKeyboardButton("📸 Chek yuborish", callback_data="sub_send_check")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_subscription")]
    ]
    
    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def sub_send_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chek yuborish (foydalanuvchi tanlanadi)"""
    query = update.callback_query
    await query.answer()
    
    text = "<b>Qaysi rejani tanlaysiz?</b>"
    
    keyboard = [
        [InlineKeyboardButton("1 oy (50,000 so'm)", callback_data="check_1")],
        [InlineKeyboardButton("3 oy (135,000 so'm)", callback_data="check_3")],
        [InlineKeyboardButton("6 oy (255,000 so'm)", callback_data="check_6")],
        [InlineKeyboardButton("12 oy (450,000 so'm)", callback_data="check_12")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="sub_plans")]
    ]
    
    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def check_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chek tanlandi, yuboring"""
    query = update.callback_query
    await query.answer()
    
    months = int(query.data.split('_')[-1])
    context.user_data['payment_months'] = months
    context.user_data['mode'] = 'upload_check'
    
    prices = {1: 50000, 3: 135000, 6: 255000, 12: 450000}
    amount = prices.get(months, 0)
    
    await query.edit_message_text(
        text=f"""
<b>Chekni yuboring</b>

<b>Rejasi:</b> {months} oy
<b>Summa:</b> {amount:,} so'm
<b>Karta:</b> 9860170109969320

Chekni rasm yoki fayl sifatida yuboring.
""",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Orqaga", callback_data="sub_send_check")]
        ])
    )

async def sub_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Promo-kod kiritish"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['mode'] = 'promo_input'
    
    await query.edit_message_text(
        text="<b>Promo-kodni kiriting:</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_subscription")]
        ])
    )

async def sub_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trial obuna"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    trial = db.get_trial_subscription(user_id)
    if trial and trial['used'] == 0:
        end_date = datetime.fromisoformat(trial['end_date'])
        days_left = max(0, (end_date - datetime.now()).days)
        
        await query.answer(f"🎁 Siz allaqachon trial bo'lganingiz ({days_left} kun qolgan)", show_alert=True)
        return
    
    if trial and trial['used'] == 1:
        await query.answer("🎁 Siz trial obunani allaqachon ishlatdingiz", show_alert=True)
        return
    
    # Trial yaratish
    db.create_trial_subscription(user_id, 3)
    db.trial_used(user_id)
    
    await query.answer("✅ 3 kunlik bepul obuna faollashtirildi!", show_alert=True)

async def sub_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Referral"""
    query = update.callback_query
    await query.answer()
    
    text = """
<b>👥 DOSTU TAKLIF QIL</b>

Dostu @kinobotuzbot'ni taklif qil va:
- <b>3 kunlik bepul obuna</b> yoki
- <b>10% chegirma</b> oling!

/referral bilan ro'yxat qilingiz.
"""
    
    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_subscription")]
        ])
    )

# ====================== PROFILE MENU ======================

async def menu_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Profil menyu"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    user = db.get_user(user_id)
    sub = db.get_subscription(user_id)
    
    status = "Faol emas"
    if sub and db.has_active_subscription(user_id):
        end_date = datetime.fromisoformat(sub['end_date'])
        status = end_date.strftime("%Y-%m-%d")
    
    text = f"""
<b>👤 PROFIL</b>

👤 <b>Ism:</b> {user['full_name']}
🔖 <b>Username:</b> @{user['username']}
📅 <b>Ro'yxat sana:</b> {user['join_date'][:10]}
💳 <b>Obuna tugash:</b> {status}
"""
    
    keyboard = [
        [InlineKeyboardButton("📈 Statistika", callback_data="profile_stats")],
        [InlineKeyboardButton("💬 Taklif yuborish", callback_data="profile_offer")],
        [InlineKeyboardButton("🆘 Adminga murojaat", callback_data="profile_admin_request")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_main")]
    ]
    
    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def profile_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistika"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    favorites = len(db.get_favorites(user_id))
    
    with db.get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) as count FROM user_watch_history WHERE user_id=?', (user_id,))
        watched = c.fetchone()[0]
    
    text = f"""
<b>📈 MENING STATISTIKAM</b>

❤️ <b>Sevimlilar:</b> {favorites} ta
👁️ <b>Ko'rilgan:</b> {watched} ta
"""
    
    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_profile")]
        ])
    )

async def profile_offer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Taklif yuborish"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="<b>Taklifni kiriting:</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_profile")]
        ])
    )
    
    context.user_data['mode'] = 'offer_input'
    return 0

async def profile_admin_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin talab"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="<b>Adminga murojaat:</b>\n\n(Savolni kiriting)",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_profile")]
        ])
    )
    
    context.user_data['mode'] = 'admin_request_input'
    return 0

# ====================== SETTINGS MENU ======================

async def menu_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sozlamalar menyu"""
    query = update.callback_query
    await query.answer()
    
    text = "<b>⚙️ SOZLAMALAR</b>\n\nHaligina mavjud:"
    
    keyboard = [
        [InlineKeyboardButton("🌐 Til", callback_data="settings_language")],
        [InlineKeyboardButton("🔔 Bildirishnomalar", callback_data="settings_notifications")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_main")]
    ]
    
    await query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def settings_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Til"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="<b>🌐 Til</b>\n\nHozir: <b>Uzbek</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_settings")]
        ])
    )

# ====================== MESSAGE HANDLER ======================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabarni qabul qilish (text, photo, document, video)"""
    user = update.effective_user
    mode = context.user_data.get('mode')
    
    if mode == 'search_by_code':
        code = update.message.text.strip()
        movie = db.get_movie_by_code(code)
        
        if not movie:
            await update.message.reply_text("Kino topilmadi!")
            return
        
        await view_movie_direct(update, context, code)
        context.user_data['mode'] = None
    
    elif mode == 'search_by_name':
        name = update.message.text.strip()
        movies = db.get_movie_by_name(name)
        
        if not movies:
            await update.message.reply_text("Kino topilmadi!")
            return
        
        keyboard = []
        for m in movies[:10]:
            keyboard.append([InlineKeyboardButton(f"{m['name'][:30]}", callback_data=f"view_movie_{m['code']}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Orqaga", callback_data="menu_movies")])
        
        await update.message.reply_text(
            "<b>Qidirish natijalari:</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data['mode'] = None
    
    elif mode == 'upload_check':
        months = context.user_data.get('payment_months', 1)
        prices = {1: 50000, 3: 135000, 6: 255000, 12: 450000}
        amount = prices.get(months, 0)
        
        file_id = None
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.document:
            file_id = update.message.document.file_id
        
        if not file_id:
            await update.message.reply_text("Iltimos, rasm yoki fayl yuboring!")
            return
        
        # Pending payment qoʻshish
        db.add_pending_payment(
            user.id,
            user.username or "N/A",
            user.full_name or "N/A",
            months,
            amount,
            file_id,
            'photo' if update.message.photo else 'document'
        )
        
        await update.message.reply_text(
            f"✅ Chek qabul qilindi!\n\nAdmin toʻlovni tasdiqlashi uchun kuting...",
            parse_mode='HTML'
        )
        
        context.user_data['mode'] = None
    
    elif mode == 'promo_input':
        code = update.message.text.strip().upper()
        can_use, reason = db.promo_can_be_used(code, user.id)
        
        if not can_use:
            await update.message.reply_text(f"❌ {reason}")
            context.user_data['mode'] = None
            return
        
        promo = db.get_promo_code(code)
        
        # Promo qoʻllash
        if promo['discount_type'] == 'free_days':
            end_date = datetime.now() + timedelta(days=promo['discount_value'])
            with db.get_db_context() as conn:
                c = conn.cursor()
                c.execute('DELETE FROM subscriptions WHERE user_id=?', (user.id,))
                c.execute('''INSERT INTO subscriptions (user_id, plan_type, end_date, status)
                             VALUES (?, 1, ?, 'active')''', (user.id, end_date.isoformat()))
        
        db.use_promo_code(promo['id'], user.id)
        
        await update.message.reply_text(
            f"✅ Promo-kod ishlatildi!\n\n🎉 {promo['discount_value']} kun bepul obuna faollashtirildi!",
            parse_mode='HTML'
        )
        
        context.user_data['mode'] = None
    
    elif mode == 'offer_input':
        message = update.message.text.strip()
        db.add_offer(user.id, user.username or "N/A", user.full_name or "N/A", message)
        
        await update.message.reply_text(
            "✅ Taklif saqlandi! Rahmat!",
            parse_mode='HTML'
        )
        
        context.user_data['mode'] = None
    
    elif mode == 'admin_request_input':
        message = update.message.text.strip()
        db.add_admin_request(user.id, user.username or "N/A", user.full_name or "N/A", message)
        
        await update.message.reply_text(
            "✅ Murojaat adminga yuborildi!",
            parse_mode='HTML'
        )
        
        context.user_data['mode'] = None

async def view_movie_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    """Kino bevosita ko'rish (message uchun)"""
    movie = db.get_movie_by_code(code)
    
    if not movie:
        await update.message.reply_text("Kino topilmadi!")
        return
    
    user_id = update.effective_user.id
    
    # Subscription tekshirish
    if not is_admin(user_id):
        if not db.has_active_subscription(user_id):
            await update.message.reply_text("❌ Obuna mavjud emas!")
            return
    
    try:
        keyboard = [
            [InlineKeyboardButton("⭐ Reyting", callback_data=f"rate_{code}")],
            [
                InlineKeyboardButton(
                    "❤️ Sevimlilarga" if not db.is_favorite(user_id, code) else "💔 Sevimlilardan oʻchirish",
                    callback_data=f"favorite_{code}"
                )
            ],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_movies")]
        ]
        
        text = f"""
<b>{movie['name']}</b>

📅 <b>Yil:</b> {movie['year']}
🎬 <b>Sifat:</b> {movie['quality']}
🗣️ <b>Til:</b> {movie['language']}
⭐ <b>Reyting:</b> {movie['rating']}
🔑 <b>Kod:</b> {code}
"""
        
        await context.bot.send_video(
            chat_id=user_id,
            video=movie['file_id'],
            caption=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        db.increment_request_count(code)
        db.add_watch_history(user_id, code)
        
    except TelegramError as e:
        logger.error(f"Video send error: {e}")
        await update.message.reply_text("Video yuborishda xato!")

# ====================== ADMIN COMMANDS ======================

async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kino qoʻshish (7 bosqich)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yoʻq!")
        return ConversationHandler.END
    
    context.user_data['add_step'] = 1
    
    text = """
<b>🎬 KINO QOʻSHISH (bosqich 1/7)</b>

<b>Kino nomini kiriting:</b>
"""
    
    await update.message.reply_text(text, parse_mode='HTML')
    
    return 1

async def admin_add_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Qoʻshish bosqichlari"""
    step = context.user_data.get('add_step', 1)
    user = update.effective_user
    
    if step == 1:
        if not update.message.text:
            await update.message.reply_text("❌ Matn kiritish kerak!")
            return 1
        context.user_data['movie_name'] = update.message.text
        context.user_data['add_step'] = 2
        await update.message.reply_text("<b>bosqich 2/7</b>\n\n<b>Sifatini kiriting:</b> (1080p, 720p, vb)", parse_mode='HTML')
    
    elif step == 2:
        if not update.message.text:
            await update.message.reply_text("❌ Matn kiritish kerak!")
            return 1
        context.user_data['movie_quality'] = update.message.text
        context.user_data['add_step'] = 3
        await update.message.reply_text("<b>bosqich 3/7</b>\n\n<b>Yilini kiriting:</b> (masalan: 2023)", parse_mode='HTML')
    
    elif step == 3:
        try:
            year = int(update.message.text)
            context.user_data['movie_year'] = year
            context.user_data['add_step'] = 4
            await update.message.reply_text("<b>bosqich 4/7</b>\n\n<b>Tilini kiriting:</b> (Uzbek, English, vb)", parse_mode='HTML')
        except:
            await update.message.reply_text("❌ Yil raqam bo'lishi kerak!")
            return 1
    
    elif step == 4:
        if not update.message.text:
            await update.message.reply_text("❌ Matn kiritish kerak!")
            return 1
        context.user_data['movie_language'] = update.message.text
        context.user_data['add_step'] = 5
        await update.message.reply_text("<b>bosqich 5/7</b>\n\n<b>Reytingini kiriting:</b> (masalan: 8.5)", parse_mode='HTML')
    
    elif step == 5:
        try:
            rating = float(update.message.text)
            context.user_data['movie_rating'] = rating
            context.user_data['add_step'] = 6
            await update.message.reply_text("<b>bosqich 6/7</b>\n\n<b>Videoni yuboring:</b> (Telegram videosi)", parse_mode='HTML')
        except:
            await update.message.reply_text("❌ Reyting raqam bo'lishi kerak!")
            return 1
    
    elif step == 6:
        if not update.message.video:
            await update.message.reply_text("❌ Video yuborish kerak!")
            return 1
        
        context.user_data['movie_file_id'] = update.message.video.file_id
        context.user_data['add_step'] = 7
        
        # Kino kodini yaratish
        code = db.get_next_movie_code()
        
        # Saqlash
        success = db.add_movie(
            code,
            context.user_data['movie_name'],
            context.user_data['movie_quality'],
            context.user_data['movie_year'],
            context.user_data['movie_language'],
            context.user_data['movie_rating'],
            context.user_data['movie_file_id']
        )
        
        if success:
            await update.message.reply_text(
                f"✅ Kino qoʻshildi!\n\n🔑 <b>Kod:</b> {code}\n<b>Nomi:</b> {context.user_data['movie_name']}",
                parse_mode='HTML'
            )
            # Holat tozalash
            context.user_data.pop('add_step', None)
            context.user_data.pop('movie_name', None)
            context.user_data.pop('movie_quality', None)
            context.user_data.pop('movie_year', None)
            context.user_data.pop('movie_language', None)
            context.user_data.pop('movie_rating', None)
            context.user_data.pop('movie_file_id', None)
            return ConversationHandler.END
        else:
            await update.message.reply_text("❌ Kino qoʻshishda xato!")
            return 1
    
    return 1

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bekor qilish"""
    # Barcha state va mode tozalash
    context.user_data.pop('mode', None)
    context.user_data.pop('add_step', None)
    context.user_data.pop('movie_name', None)
    context.user_data.pop('movie_quality', None)
    context.user_data.pop('movie_year', None)
    context.user_data.pop('movie_language', None)
    context.user_data.pop('movie_rating', None)
    context.user_data.pop('movie_file_id', None)
    context.user_data.pop('payment_months', None)
    
    await update.message.reply_text(
        "❌ Bekor qilindi.",
        reply_markup=await get_main_menu()
    )
    return ConversationHandler.END

async def menu_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asosiy menyu"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="<b>🎬 Kino Bot v2.0</b>\n\nNima qilishni xohlaysiz?",
        parse_mode='HTML',
        reply_markup=await get_main_menu()
    )

# ====================== BACKUP SCHEDULER ======================

def backup_task(app: Application):
    """Har 7 kunda backup yaratish (blocking job)"""
    try:
        backup_file = backup_restore.create_backup()
        
        if backup_file and os.path.exists(backup_file):
            # Admin'ga yuborish (async -> sync wrapper)
            import asyncio
            asyncio.create_task(
                app.bot.send_document(
                    chat_id=MAIN_ADMIN_ID,
                    document=open(backup_file, 'rb'),
                    caption="📦 Avtomatik backup (har 7 kun)"
                )
            )
        
        logger.info("✅ Backup muvaffaqiyatli yaratildi")
    except Exception as e:
        logger.error(f"❌ Backup xato: {e}")

# ====================== MAIN ======================

def main():
    """Bot qoʻyish"""
    # Database init
    db.init_db()
    
    # Application yaratish
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(backup_task, "interval", days=7, args=(app,))
    scheduler.start()
    
    # ===== HANDLERS =====
    
    # Start / Help
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    
    # Main menu
    app.add_handler(CallbackQueryHandler(menu_main, pattern="menu_main"))
    app.add_handler(CallbackQueryHandler(menu_movies, pattern="menu_movies"))
    app.add_handler(CallbackQueryHandler(menu_subscription, pattern="menu_subscription"))
    app.add_handler(CallbackQueryHandler(menu_profile, pattern="menu_profile"))
    app.add_handler(CallbackQueryHandler(menu_settings, pattern="menu_settings"))
    
    # Movies
    app.add_handler(CallbackQueryHandler(movies_by_code, pattern="movies_by_code"))
    app.add_handler(CallbackQueryHandler(movies_by_name, pattern="movies_by_name"))
    app.add_handler(CallbackQueryHandler(movies_favorites, pattern="movies_favorites"))
    app.add_handler(CallbackQueryHandler(view_movie, pattern="view_movie_"))
    app.add_handler(CallbackQueryHandler(rate_movie, pattern="rate_"))
    app.add_handler(CallbackQueryHandler(rate_value, pattern="rate_value_"))
    app.add_handler(CallbackQueryHandler(favorite_toggle, pattern="favorite_"))
    
    # Subscription
    app.add_handler(CallbackQueryHandler(sub_plans, pattern="sub_plans"))
    app.add_handler(CallbackQueryHandler(sub_send_check, pattern="sub_send_check"))
    app.add_handler(CallbackQueryHandler(check_selected, pattern="check_"))
    app.add_handler(CallbackQueryHandler(sub_promo, pattern="sub_promo"))
    app.add_handler(CallbackQueryHandler(sub_trial, pattern="sub_trial"))
    app.add_handler(CallbackQueryHandler(sub_referral, pattern="sub_referral"))
    
    # Profile
    app.add_handler(CallbackQueryHandler(menu_profile, pattern="menu_profile"))
    app.add_handler(CallbackQueryHandler(profile_stats, pattern="profile_stats"))
    app.add_handler(CallbackQueryHandler(profile_offer, pattern="profile_offer"))
    app.add_handler(CallbackQueryHandler(profile_admin_request, pattern="profile_admin_request"))
    
    # Settings
    app.add_handler(CallbackQueryHandler(settings_language, pattern="settings_language"))
    
    # Add movie conversation (text + video filter)
    add_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", admin_add)],
        states={
            1: [MessageHandler(filters.TEXT | filters.VIDEO, admin_add_steps)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(add_conv_handler)
    
    # Message handler (text, photo, document, video)
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.VIDEO,
        handle_message
    ))
    
    # /list command
    app.add_handler(CommandHandler("list", help_command))
    
    # Cancel
    app.add_handler(CommandHandler("cancel", cancel))
    
    # Polling
    logger.info("🚀 Bot ishga tushdi...")
    app.run_polling()

if __name__ == '__main__':
    main()
