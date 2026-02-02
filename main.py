import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
from dotenv import load_dotenv

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

from db import Database

# .env faylini yuklash
load_dotenv()

# Sozlamalar
BOT_TOKEN = os.getenv('BOT_TOKEN')
MAIN_ADMIN = int(os.getenv('MAIN_ADMIN'))
DB_PATH = os.getenv('DB_PATH', 'database.db')

# Conversation holatlari
ADD_MOVIE, GET_TITLE, GET_QUALITY, GET_YEAR, GET_LANGUAGE, GET_RATING = range(6)
SETTINGS_MENU, SET_PRICE, SET_CARD = range(3)
PAYMENT_CONFIRM = range(1)

# Database obyekti
db = Database(DB_PATH)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== YORDAMCHI FUNKSIYALAR ==========
def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin yoki yo'qligini tekshirish"""
    return user_id == MAIN_ADMIN or db.is_admin(user_id)

def get_subscription_keyboard():
    """Obuna paketlari keyboardi"""
    monthly = db.get_setting('monthly_price')
    quarterly = db.get_setting('quarterly_price')
    semiannual = db.get_setting('semiannual_price')
    annual = db.get_setting('annual_price')
    
    keyboard = [
        [InlineKeyboardButton(f"📅 1 oylik - {monthly} so'm", callback_data='sub_1')],
        [InlineKeyboardButton(f"📅 3 oylik - {quarterly} so'm", callback_data='sub_3')],
        [InlineKeyboardButton(f"📅 6 oylik - {semiannual} so'm", callback_data='sub_6')],
        [InlineKeyboardButton(f"📅 12 oylik - {annual} so'm", callback_data='sub_12')],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payment_info():
    """To'lov ma'lumotlari"""
    card_number = db.get_setting('card_number')
    card_holder = db.get_setting('card_holder')
    
    return f"""
💳 **To'lov ma'lumotlari:**
    
Karta raqami: `{card_number}`
Karta egasi: {card_holder}

⚠️ **OGOHLANTIRISH!** Kartaga ko'p ham, kam ham pul tashlanmasin!
To'lov cheki talab qilinadi.

💸 To'lov qilgach, chekni (foto yoki fayl) shu yerga yuboring.
"""

def format_movie_info(movie):
    """Kino ma'lumotlarini chiroyli formatlash"""
    return f"""
🎬 **{movie['name']}**
    
📁 Kodi: `{movie['code']}`
📊 Sifati: {movie['quality']}
📅 Yili: {movie['year']}
🌐 Tili: {movie['language']}
⭐ Bahosi: {movie['rating']}
    
📝 Tavsif: {movie['description']}
"""

# ========== ASOSIY HANDLERLAR ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    user_id = user.id
    
    # Foydalanuvchini bazaga qo'shish
    db.add_user(user_id, user.username, user.full_name)
    
    # Aktivlikni yangilash
    db.update_activity(user_id)
    
    # Subscriptionni tekshirish
    has_subscription = db.check_subscription(user_id)
    user_data = db.get_user(user_id)
    
    if user_data and user_data.get('is_blocked'):
        await update.message.reply_text("❌ Siz bloklangansiz. Botdan foydalana olmaysiz.")
        return
    
    if not has_subscription:
        # Obuna boshlash
        welcome_text = """
🎬 **Kino Botga xush kelibsiz!**

Bu bot oylik obuna asosida ishlaydi.
Obuna haqi:
"""
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_subscription_keyboard()
        )
    else:
        # Obuna aktiv
        await update.message.reply_text(
            "🎬 Kino Botga xush kelibsiz!\n\n"
            "Kino kodini yuboring yoki /search bilan qidiring.",
            reply_markup=ReplyKeyboardMarkup(
                [["🔍 Kino qidirish"], ["📊 Statistika"]],
                resize_keyboard=True
            )
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabarlarni qayta ishlash"""
    user_id = update.effective_user.id
    
    # Bloklanganligini tekshirish
    user_data = db.get_user(user_id)
    if user_data and user_data.get('is_blocked'):
        return
    
    # Aktivlikni yangilash
    db.update_activity(user_id)
    
    # Subscriptionni tekshirish
    if not db.check_subscription(user_id):
        await update.message.reply_text(
            "❌ Sizda aktiv obuna yo'q.\n"
            "Obuna uchun /start ni bosing.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    # Kino kodini tekshirish
    text = update.message.text
    if text.isdigit() or (len(text) <= 10 and text.isalnum()):
        movie = db.get_movie(text)
        if movie:
            # Kino yuborish
            if movie['file_type'] == 'video':
                await update.message.reply_video(
                    video=movie['file_id'],
                    caption=format_movie_info(movie)
                )
            elif movie['file_type'] == 'document':
                await update.message.reply_document(
                    document=movie['file_id'],
                    caption=format_movie_info(movie)
                )
        else:
            await update.message.reply_text("❌ Bunday kodli kino topilmadi.")

async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kino qidirish"""
    user_id = update.effective_user.id
    
    if not db.check_subscription(user_id):
        await update.message.reply_text("❌ Obuna talab qilinadi.")
        return
    
    if context.args:
        query = ' '.join(context.args)
        movies = db.search_movies(query)
        
        if movies:
            response = "🔍 **Qidiruv natijalari:**\n\n"
            for movie in movies:
                response += f"🎬 {movie['name']} - Kodi: `{movie['code']}`\n"
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("❌ Hech narsa topilmadi.")
    else:
        await update.message.reply_text("Qidirish uchun: /search <kino nomi yoki kodi>")

# ========== OBUNA/TO'LOV HANDLERLARI ==========
async def subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obuna callback handler"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith('sub_'):
        period = int(data.split('_')[1])
        
        # Narxlarni olish
        if period == 1:
            amount = db.get_setting('monthly_price')
            days = int(db.get_setting('subscription_days'))
        elif period == 3:
            amount = db.get_setting('quarterly_price')
            days = 90
        elif period == 6:
            amount = db.get_setting('semiannual_price')
            days = 180
        elif period == 12:
            amount = db.get_setting('annual_price')
            days = 365
        
        # Contextda saqlash
        context.user_data['payment_data'] = {
            'period': period,
            'days': days,
            'amount': amount
        }
        
        # To'lov ma'lumotlarini chiqarish
        payment_text = get_payment_info()
        payment_text += f"\n💵 Tanlangan obuna: {period} oy - {amount} so'm"
        
        keyboard = [[InlineKeyboardButton("💳 To'lov qildim", callback_data='confirm_payment')]]
        
        await query.edit_message_text(
            payment_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def confirm_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lovni tasdiqlash"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "💸 To'lov qilgach, chekni (foto yoki fayl) shu yerga yuboring.\n\n"
        "Chekda quyidagilar ko'rinishi kerak:\n"
        "• To'lov summasi\n"
        "• Vaqti\n"
        "• Karta raqami (oxirgi 4 ta raqam)\n\n"
        "⚠️ Soxta chek yuborilgan holda hisob bloklanadi!"
    )
    return PAYMENT_CONFIRM

async def handle_payment_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chekni qabul qilish"""
    user_id = update.effective_user.id
    
    if not context.user_data.get('payment_data'):
        await update.message.reply_text("Iltimos, avval obuna tanlang.")
        return ConversationHandler.END
    
    payment_data = context.user_data['payment_data']
    
    # Fayl ID sini olish
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = 'photo'
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = 'document'
    else:
        await update.message.reply_text("Iltimos, rasm yoki fayl yuboring.")
        return PAYMENT_CONFIRM
    
    # To'lovni bazaga qo'shish
    payment_id = db.add_payment(
        user_id, 
        payment_data['amount'], 
        payment_data['days'],
        file_id
    )
    
    # Adminlarga xabar berish
    admins = [MAIN_ADMIN] + db.get_all_admins()
    
    user = update.effective_user
    payment_info = f"""
🔄 Yangi to'lov so'rovi:

👤 Foydalanuvchi: @{user.username}
🆔 ID: {user.id}
📛 Ism: {user.full_name}

💰 Summa: {payment_data['amount']} so'm
📅 Davomiylik: {payment_data['days']} kun
🆔 To'lov ID: {payment_id}

Tasdiqlaysizmi?
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Ha", callback_data=f"approve_{payment_id}"),
            InlineKeyboardButton("❌ Yo'q", callback_data=f"reject_{payment_id}")
        ]
    ])
    
    for admin_id in admins:
        try:
            if file_type == 'photo':
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=payment_info,
                    reply_markup=keyboard
                )
            else:
                await context.bot.send_document(
                    chat_id=admin_id,
                    document=file_id,
                    caption=payment_info,
                    reply_markup=keyboard
                )
        except Exception as e:
            logger.error(f"Adminga xabar yuborishda xato: {e}")
    
    await update.message.reply_text(
        "✅ Chek qabul qilindi. Admin tomonidan tekshirilmoqda.\n"
        "Tasdiqlanganidan so'ng obuna faollashtiriladi."
    )
    
    return ConversationHandler.END

async def payment_decision_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin tomonidan to'lovni tasdiqlash/rad etish"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    
    data = query.data
    action, payment_id = data.split('_')
    
    # To'lovni topish
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM payments WHERE id = ?', (payment_id,))
        payment = cursor.fetchone()
    
    if not payment:
        await query.edit_message_text("❌ To'lov topilmadi.")
        return
    
    if action == 'approve':
        # Obunani faollashtirish
        db.update_subscription(payment['user_id'], payment['period_days'])
        db.update_payment_status(payment_id, 'approved', query.from_user.id)
        
        # Foydalanuvchiga xabar
        try:
            await context.bot.send_message(
                chat_id=payment['user_id'],
                text=f"✅ To'lovingiz tasdiqlandi!\n"
                     f"Obuna {payment['period_days']} kunga faollashtirildi.\n\n"
                     f"Endi kinolarni tomosha qilishingiz mumkin!"
            )
        except:
            pass
        
        await query.edit_message_text(f"✅ To'lov tasdiqlandi. Foydalanuvchiga obuna berildi.")
    
    elif action == 'reject':
        db.update_payment_status(payment_id, 'rejected', query.from_user.id)
        
        # Foydalanuvchiga xabar
        try:
            await context.bot.send_message(
                chat_id=payment['user_id'],
                text="❌ To'lovingiz rad etildi.\n"
                     "Sabab: Noto'g'ri chek yoki to'lov ma'lumotlari.\n\n"
                     "Iltimos, to'lovni qayta amalga oshiring va haqiqiy chek yuboring."
            )
        except:
            pass
        
        await query.edit_message_text("❌ To'lov rad etildi. Foydalanuvchi ogohlantirildi.")

# ========== ADMIN HANDLERLARI ==========
async def add_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kino qo'shishni boshlash"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Sizda ruxsat yo'q!")
        return
    
    await update.message.reply_text(
        "🎬 Yangi kino qo'shish\n\n"
        "1. Avval kino faylini (video yoki dokument) yuboring:"
    )
    return ADD_MOVIE

async def add_movie_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kino faylini qabul qilish"""
    user_id = update.effective_user.id
    
    # Fayl ID sini olish
    if update.message.video:
        file_id = update.message.video.file_id
        file_type = 'video'
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = 'document'
    else:
        await update.message.reply_text("Iltimos, video yoki fayl yuboring.")
        return ADD_MOVIE
    
    context.user_data['movie_file'] = file_id
    context.user_data['file_type'] = file_type
    
    await update.message.reply_text(
        "✅ Fayl qabul qilindi.\n"
        "2. Endi kino nomini kiriting:"
    )
    return GET_TITLE

async def get_movie_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kino nomini qabul qilish"""
    context.user_data['movie_title'] = update.message.text
    
    await update.message.reply_text(
        "3. Kino sifati (HD, FullHD, 4K):"
    )
    return GET_QUALITY

async def get_movie_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kino sifati"""
    context.user_data['movie_quality'] = update.message.text
    
    await update.message.reply_text(
        "4. Chiqarilgan yili:"
    )
    return GET_YEAR

async def get_movie_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chiqarilgan yili"""
    context.user_data['movie_year'] = update.message.text
    
    await update.message.reply_text(
        "5. Tili:"
    )
    return GET_LANGUAGE

async def get_movie_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kino tili"""
    context.user_data['movie_language'] = update.message.text
    
    await update.message.reply_text(
        "6. Bahosi (masalan: 8.5/10):"
    )
    return GET_RATING

async def get_movie_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kino bahosi va saqlash"""
    context.user_data['movie_rating'] = update.message.text
    
    # Kino kodini generatsiya qilish
    code = db.get_next_movie_code()
    
    # Bazaga saqlash
    db.add_movie(
        code=code,
        name=context.user_data['movie_title'],
        description="",  # Tavsif keyinroq qo'shilishi mumkin
        quality=context.user_data['movie_quality'],
        year=context.user_data['movie_year'],
        language=context.user_data['movie_language'],
        rating=context.user_data['movie_rating'],
        file_id=context.user_data['movie_file'],
        file_type=context.user_data['file_type'],
        added_by=update.effective_user.id
    )
    
    await update.message.reply_text(
        f"✅ Kino muvaffaqiyatli qo'shildi!\n\n"
        f"📁 Kodi: `{code}`\n"
        f"🎬 Nomi: {context.user_data['movie_title']}\n"
        f"📊 Sifati: {context.user_data['movie_quality']}"
    )
    
    # Contextni tozalash
    context.user_data.clear()
    return ConversationHandler.END

async def delete_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kino o'chirish"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Sizda ruxsat yo'q!")
        return
    
    if not context.args:
        await update.message.reply_text("Ishlatish: /delete <kino kodi>")
        return
    
    code = context.args[0]
    if db.delete_movie(code):
        await update.message.reply_text(f"✅ '{code}' kodli kino o'chirildi.")
    else:
        await update.message.reply_text(f"❌ '{code}' kodli kino topilmadi.")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabar yuborish"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Sizda ruxsat yo'q!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Ishlatish: /broadcast <xabar>\n\n"
            "Yoki reply qilib yuboring."
        )
        return
    
    message = ' '.join(context.args)
    
    # Reply qilish imkoniyati
    if update.message.reply_to_message:
        if update.message.reply_to_message.text:
            message = update.message.reply_to_message.text
        elif update.message.reply_to_message.caption:
            message = update.message.reply_to_message.caption
    
    # Barcha foydalanuvchilarga yuborish
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE is_blocked = 0')
        users = cursor.fetchall()
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user['user_id'],
                text=f"📢 **Admin xabari:**\n\n{message}"
            )
            sent += 1
        except:
            failed += 1
    
    await update.message.reply_text(
        f"📊 Xabar yuborildi:\n"
        f"✅ Muvaffaqiyatli: {sent}\n"
        f"❌ Xatolik: {failed}"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistika"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Sizda ruxsat yo'q!")
        return
    
    stats_data = db.get_statistics()
    
    # Inaktiv foydalanuvchilarni bloklash
    inactive_users = db.get_inactive_users(days=3)
    for user_id in inactive_users:
        db.block_user(user_id)
    
    response = f"""
📊 **Bot statistika:**

👥 Foydalanuvchilar:
├ Faol obunachilar: {stats_data['active_subscribers']}
├ Oddiy foydalanuvchilar: {stats_data['regular_users']}
├ Bloklangan: {stats_data['blocked_users']}
└ Jami: {stats_data['total_users']}

🎬 Filmlar: {stats_data['total_movies']} ta

📈 Faollik:
└ Bugun faol: {stats_data['daily_active']} ta

🔄 Bloklangan: {len(inactive_users)} ta foydalanuvchi
"""
    
    await update.message.reply_text(response)

async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin sozlamalari"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Sizda ruxsat yo'q!")
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 Narxlarni sozlash", callback_data='set_prices')],
        [InlineKeyboardButton("💳 Karta ma'lumotlari", callback_data='set_card')],
        [InlineKeyboardButton("👥 Admin qo'shish", callback_data='add_admin')],
    ]
    
    await update.message.reply_text(
        "⚙️ **Admin sozlamalari**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sozlamalar callback"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    
    data = query.data
    
    if data == 'set_prices':
        current_prices = f"""
💰 **Joriy narxlar:**

1 oylik: {db.get_setting('monthly_price')} so'm
3 oylik: {db.get_setting('quarterly_price')} so'm
6 oylik: {db.get_setting('semiannual_price')} so'm
12 oylik: {db.get_setting('annual_price')} so'm

Yangi narxni quyidagi formatda yuboring:
`oylik_narx;3_oylik_narx;6_oylik_narx;12_oylik_narx`

Masalan: 29900;79900;149900;279900
"""
        await query.edit_message_text(current_prices, parse_mode='Markdown')
        context.user_data['waiting_for'] = 'prices'
    
    elif data == 'set_card':
        current_card = f"""
💳 **Joriy karta ma'lumotlari:**

Karta raqami: {db.get_setting('card_number')}
Karta egasi: {db.get_setting('card_holder')}

Yangi ma'lumotlarni quyidagi formatda yuboring:
`karta_raqami;karta_egasi`

Masalan: 8600 1234 5678 9012;SOLEJON ADASHOV ISROILOVICH
"""
        await query.edit_message_text(current_card)
        context.user_data['waiting_for'] = 'card'
    
    elif data == 'add_admin':
        await query.edit_message_text(
            "Yangi admin ID sini yuboring:\n\n"
            "Admin ID sini olish uchun: @userinfobot"
        )
        context.user_data['waiting_for'] = 'admin_id'

async def handle_settings_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sozlamalar inputini qabul qilish"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if not context.user_data.get('waiting_for'):
        return
    
    waiting_for = context.user_data['waiting_for']
    
    if waiting_for == 'prices':
        try:
            prices = text.split(';')
            if len(prices) != 4:
                raise ValueError
            
            db.update_setting('monthly_price', prices[0])
            db.update_setting('quarterly_price', prices[1])
            db.update_setting('semiannual_price', prices[2])
            db.update_setting('annual_price', prices[3])
            
            await update.message.reply_text("✅ Narxlar yangilandi!")
        except:
            await update.message.reply_text("❌ Noto'g'ri format!")
    
    elif waiting_for == 'card':
        try:
            card_data = text.split(';', 1)
            if len(card_data) != 2:
                raise ValueError
            
            db.update_setting('card_number', card_data[0].strip())
            db.update_setting('card_holder', card_data[1].strip())
            
            await update.message.reply_text("✅ Karta ma'lumotlari yangilandi!")
        except:
            await update.message.reply_text("❌ Noto'g'ri format!")
    
    elif waiting_for == 'admin_id':
        try:
            admin_id = int(text.strip())
            db.add_admin(admin_id, user_id)
            await update.message.reply_text(f"✅ {admin_id} admin sifatida qo'shildi!")
        except:
            await update.message.reply_text("❌ Noto'g'ri ID!")
    
    context.user_data.clear()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel command"""
    await update.message.reply_text("❌ Operatsiya bekor qilindi.")
    context.user_data.clear()
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xatolarni qayta ishlash"""
    logger.error(f"Xato: {context.error}", exc_info=context.error)

# ========== ASOSIY FUNKSIYA ==========
def main():
    """Botni ishga tushirish"""
    # Bot yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handlerlar
    add_movie_conv = ConversationHandler(
        entry_points=[CommandHandler('add', add_movie_start)],
        states={
            ADD_MOVIE: [MessageHandler(filters.VIDEO | filters.Document.ALL, add_movie_file)],
            GET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_movie_title)],
            GET_QUALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_movie_quality)],
            GET_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_movie_year)],
            GET_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_movie_language)],
            GET_RATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_movie_rating)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(confirm_payment_callback, pattern='^confirm_payment$')],
        states={
            PAYMENT_CONFIRM: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_payment_receipt)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Handlerlarni qo'shish
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('search', search_movie))
    application.add_handler(CommandHandler('delete', delete_movie))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('settings', admin_settings))
    
    application.add_handler(add_movie_conv)
    application.add_handler(payment_conv)
    
    application.add_handler(CallbackQueryHandler(subscription_callback, pattern='^sub_'))
    application.add_handler(CallbackQueryHandler(payment_decision_callback, pattern='^(approve|reject)_'))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern='^(set_prices|set_card|add_admin)$'))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_settings_input))
    
    application.add_error_handler(error_handler)
    
    # Botni ishga tushirish
    print("🤖 Bot ishga tushdi...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
