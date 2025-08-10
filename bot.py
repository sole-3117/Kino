# bot.py
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaVideo, ParseMode
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import traceback

from config import BOT_TOKEN, DATABASE_FILE, MAIN_ADMIN
from database import Database

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Bot & Dispatcher ---
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- DB & Scheduler ---
db = Database(DATABASE_FILE)
scheduler = AsyncIOScheduler()

# --- FSM states for adding movie and ad ---
class AddMovieStates(StatesGroup):
    waiting_for_video = State()
    waiting_for_title = State()
    waiting_for_format = State()
    waiting_for_language = State()

class AddAdStates(StatesGroup):
    waiting_for_image = State()
    waiting_for_text = State()
    waiting_for_button = State()
    waiting_for_time = State()
    waiting_for_repeat = State()

# helper: report errors to superadmin
async def report_error(err_text: str):
    try:
        await bot.send_message(MAIN_ADMIN, f"⚠️ Bot xatosi:\n<pre>{err_text}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.exception("Failed to report error to MAIN_ADMIN: %s", e)

# a decorator-like wrapper for handlers to catch exceptions
def safe_handler(func):
    async def wrapper(message_or_event, *args, **kwargs):
        try:
            return await func(message_or_event, *args, **kwargs)
        except Exception as e:
            tb = traceback.format_exc()
            logger.exception("Handler error: %s", e)
            await report_error(tb)
    return wrapper

# START and new user joining
@dp.message_handler(commands=['start'])
@safe_handler
async def cmd_start(message: types.Message):
    # save user
    username = message.from_user.username or ""
    fullname = (message.from_user.full_name or "").strip()
    await db.add_or_update_user(message.from_user.id, username, fullname)

    # Notify main admin of new user
    text = f"🆕 Yangi foydalanuvchi:\nIsmi: {fullname}\nUsername: @{username if username else '—'}\nID: {message.from_user.id}"
    await bot.send_message(MAIN_ADMIN, text)

    # Check mandatory subscription
    force = await db.get_setting("force_subscribe", "off")
    if force == "on":
        channels = await db.list_channels()
        if channels:
            # build keyboard with channel links and confirm button
            kb = InlineKeyboardMarkup()
            for ch in channels:
                kb.add(InlineKeyboardButton(text=ch, url=f"https://t.me/{ch.lstrip('@')}"))
            kb.add(InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_subs"))
            await message.reply("Kanal(lar)ga obuna bo‘lishingiz kerak:", reply_markup=kb)
            return

    await message.reply("Xush kelibsiz! Kino kodi yuboring yoki buyruqlar bilan ishlating.")

# Callback to check subscriptions
@dp.callback_query_handler(lambda c: c.data == "check_subs")
@safe_handler
async def cb_check_subs(query: types.CallbackQuery):
    await query.answer()
    channels = await db.list_channels()
    if not channels:
        await query.message.edit_text("Hech qanday kanal sozlanmagan.")
        return
    not_subscribed = []
    for ch in channels:
        chat = ch
        try:
            member = await bot.get_chat_member(chat, query.from_user.id)
            # statuses: 'left', 'member', 'creator', 'administrator', 'restricted'
            if member.status in ('left', 'kicked'):
                not_subscribed.append(ch)
        except Exception as e:
            # problem getting member — assume not subscribed or channel incorrect
            not_subscribed.append(ch)
    if not_subscribed:
        kb = InlineKeyboardMarkup()
        for ch in not_subscribed:
            kb.add(InlineKeyboardButton(text=ch, url=f"https://t.me/{ch.lstrip('@')}"))
        kb.add(InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_subs"))
        await query.message.edit_text("Siz quyidagi kanallarga obuna emassiz. Avval obuna bo‘ling:", reply_markup=kb)
    else:
        await query.message.edit_text("Rahmat! Siz barcha kanallarga obunasiz. Endi kino kodi yuboring yoki menyudan davom eting.")

# MOVIE: get by code (user sends a code)
@dp.message_handler(lambda m: m.text and m.text.strip().isdigit())
@safe_handler
async def movie_by_code(message: types.Message):
    code = int(message.text.strip())
    movie = await db.get_movie(code)
    if not movie or movie["is_deleted"]:
        await message.reply("Bunday koddagi kino topilmadi.")
        return

    # mandatory subscription check
    force = await db.get_setting("force_subscribe", "off")
    if force == "on":
        channels = await db.list_channels()
        if channels:
            # check subs
            for ch in channels:
                try:
                    member = await bot.get_chat_member(ch, message.from_user.id)
                    if member.status in ('left', 'kicked'):
                        # show channels + confirm
                        kb = InlineKeyboardMarkup()
                        for c in channels:
                            kb.add(InlineKeyboardButton(text=c, url=f"https://t.me/{c.lstrip('@')}"))
                        kb.add(InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_subs"))
                        await message.reply("Iltimos, avval kanallarga obuna bo'ling:", reply_markup=kb)
                        return
                except Exception:
                    kb = InlineKeyboardMarkup()
                    for c in channels:
                        kb.add(InlineKeyboardButton(text=c, url=f"https://t.me/{c.lstrip('@')}"))
                    kb.add(InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_subs"))
                    await message.reply("Iltimos, avval kanallarga obuna bo'ling:", reply_markup=kb)
                    return

    # send video using file_id (no server storage)
    caption = (
        f"🎬 <b>{movie['title']}</b>\n"
        f"📌 Kod: <code>{movie['code']}</code>\n"
        f"🗂️ Format: {movie['format']}\n"
        f"🗣️ Til: {movie['language']}\n"
        f"👁️ Ko‘rishlar: {movie['views']}\n"
    )
    try:
        await bot.send_video(chat_id=message.chat.id, video=movie['file_id'], caption=caption, parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply("Videoni yuborishda xatolik yuz berdi.")
        await report_error(str(e))
        return

    # increment view count
    await db.increment_views(code)

# ADMIN check decorator
def admin_only(func):
    async def wrapper(message: types.Message, *args, **kwargs):
        uid = message.from_user.id
        # main admin always admin
        if uid == MAIN_ADMIN or await db.is_admin(uid):
            return await func(message, *args, **kwargs)
        else:
            await message.reply("❌ Sizda bu buyruqdan foydalanish huquqi yo‘q.")
    return wrapper

# Add movie sequence
@dp.message_handler(commands=['addmovie'])
@admin_only
@safe_handler
async def cmd_addmovie(message: types.Message):
    await message.reply("Joriy kino qo'shish: Iltimos video yuboring (faylni yuboring).")
    await AddMovieStates.waiting_for_video.set()

@dp.message_handler(content_types=['video', 'document'], state=AddMovieStates.waiting_for_video)
@safe_handler
async def addmovie_video(message: types.Message, state: FSMContext):
    # accept video or video document — get file_id
    if message.video:
        file_id = message.video.file_id
    elif message.document:
        file_id = message.document.file_id
    else:
        await message.reply("Iltimos video fayl yuboring.")
        return
    await state.update_data(file_id=file_id)
    await message.reply("Endi kinoning nomini yuboring:")
    await AddMovieStates.waiting_for_title.set()

@dp.message_handler(state=AddMovieStates.waiting_for_title, content_types=types.ContentTypes.TEXT)
@safe_handler
async def addmovie_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.reply("Formatni yuboring (masalan: mp4, mkv):")
    await AddMovieStates.waiting_for_format.set()

@dp.message_handler(state=AddMovieStates.waiting_for_format, content_types=types.ContentTypes.TEXT)
@safe_handler
async def addmovie_format(message: types.Message, state: FSMContext):
    await state.update_data(format=message.text.strip())
    await message.reply("Tilni yuboring (masalan: Uzbek, English):")
    await AddMovieStates.waiting_for_language.set()

@dp.message_handler(state=AddMovieStates.waiting_for_language, content_types=types.ContentTypes.TEXT)
@safe_handler
async def addmovie_language(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = data.get('title')
    format_ = data.get('format')
    language = message.text.strip()
    file_id = data.get('file_id')
    code = await db.add_movie(title, format_, language, file_id)
    await message.reply(f"✅ Kino qo'shildi. Kod: <code>{code}</code>\nNom: {title}", parse_mode=ParseMode.HTML)
    await state.finish()

# Delete movie (soft)
@dp.message_handler(commands=['deletemovie'])
@admin_only
@safe_handler
async def cmd_deletemovie(message: types.Message):
    args = message.get_args().strip()
    if not args.isdigit():
        await message.reply("Iltimos: /deletemovie <kod> — ko'rinishida yuboring.")
        return
    code = int(args)
    movie = await db.get_movie(code)
    if not movie:
        await message.reply("Bunday kod topilmadi.")
        return
    await db.delete_movie(code)
    await message.reply(f"✅ {code} kodli kino o‘chirildi (soft delete).")

# Admin panel
@dp.message_handler(commands=['admin'])
@admin_only
@safe_handler
async def cmd_admin(message: types.Message):
    users = await db.count_users()
    movies = await db.movies_count()
    views = await db.total_views()
    text = (
        f"🔧 Admin panel\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"🎞️ Kinolar: {movies}\n"
        f"👁️ Umumiy ko‘rishlar: {views}\n\n"
        f"Buyruqlar:\n"
        f"/msgall <matn> — barcha foydalanuvchilarga xabar (batching)\n"
        f"/msguser <user_id> <matn> — foydalanuvchiga xabar\n"
        f"/setadmin <user_id> — admin qo‘shish\n"
        f"/removeadmin <user_id> — admin olib tashlash\n"
        f"/setchannels add|remove <username> — kanal qo‘shish/o‘chirish\n"
        f"/set_force_subscribe on|off — majburiy obuna\n"
        f"/addad — reklama qo‘shish\n"
        f"/listads — reklama ro‘yxati\n"
        f"/deletead <id> — reklama o‘chirish\n"
    )
    await message.reply(text)

# Message all (batching)
@dp.message_handler(commands=['msgall'])
@admin_only
@safe_handler
async def cmd_msgall(message: types.Message):
    text = message.get_args().strip()
    if not text:
        await message.reply("Iltimos: /msgall <matn>")
        return
    user_ids = await db.all_user_ids()
    sent = 0
    failed = 0
    # batching: send in small pauses
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # small delay to avoid flooding
    await message.reply(f"Xabar yuborildi: {sent} ta, muvaffaqiyatsiz: {failed} ta.")

# Message single user
@dp.message_handler(commands=['msguser'])
@admin_only
@safe_handler
async def cmd_msguser(message: types.Message):
    parts = message.get_args().split(maxsplit=1)
    if len(parts) < 2 or not parts[0].isdigit():
        await message.reply("Iltimos: /msguser <user_id> <matn>")
        return
    uid = int(parts[0])
    text = parts[1]
    try:
        await bot.send_message(uid, text)
        await message.reply("Xabar yuborildi.")
    except Exception as e:
        await message.reply("Xabar yuborilmadi.")
        await report_error(str(e))

# Admin add/remove
@dp.message_handler(commands=['setadmin'])
@admin_only
@safe_handler
async def cmd_setadmin(message: types.Message):
    args = message.get_args().strip()
    if not args.isdigit():
        await message.reply("Iltimos: /setadmin <user_id>")
        return
    uid = int(args)
    if uid == MAIN_ADMIN:
        await message.reply("Bu foydalanuvchi superadmin — u doimiy mavjud.")
        return
    await db.add_admin(uid)
    await message.reply(f"✅ {uid} admin sifatida qo‘shildi.")

@dp.message_handler(commands=['removeadmin'])
@admin_only
@safe_handler
async def cmd_removeadmin(message: types.Message):
    args = message.get_args().strip()
    if not args.isdigit():
        await message.reply("Iltimos: /removeadmin <user_id>")
        return
    uid = int(args)
    if uid == MAIN_ADMIN:
        await message.reply("Superadminni olib tashlash mumkin emas.")
        return
    await db.remove_admin(uid)
    await message.reply(f"✅ {uid} adminlikdan chiqarildi.")

# Channels management
@dp.message_handler(commands=['setchannels'])
@admin_only
@safe_handler
async def cmd_setchannels(message: types.Message):
    args = message.get_args().strip().split()
    if not args or args[0] not in ("add", "remove", "list"):
        await message.reply("Foydalanish: /setchannels add <username> | remove <username> | list")
        return
    op = args[0]
    if op == "list":
        chs = await db.list_channels()
        if not chs:
            await message.reply("Hech qanday kanal sozlanmagan.")
        else:
            await message.reply("Kanal ro'yxati:\n" + "\n".join(chs))
        return
    if len(args) < 2:
        await message.reply("Iltimos: kanal username ni yuboring.")
        return
    username = args[1]
    if op == "add":
        await db.add_channel(username)
        await message.reply(f"✅ Kanal qo'shildi: {username}")
    elif op == "remove":
        await db.remove_channel(username)
        await message.reply(f"✅ Kanal o'chirildi: {username}")

# Force subscribe on/off
@dp.message_handler(commands=['set_force_subscribe'])
@admin_only
@safe_handler
async def cmd_set_force_subscribe(message: types.Message):
    args = message.get_args().strip().lower()
    if args not in ("on", "off"):
        await message.reply("Foydalanish: /set_force_subscribe on|off")
        return
    await db.set_setting("force_subscribe", args)
    await message.reply(f"✅ Majburiy obuna: {args}")

# Ads: add (FSM)
@dp.message_handler(commands=['addad'])
@admin_only
@safe_handler
async def cmd_addad(message: types.Message):
    await message.reply("Reklama qo'shish: iltimos, rasm yuboring (photo).")
    await AddAdStates.waiting_for_image.set()

@dp.message_handler(content_types=['photo'], state=AddAdStates.waiting_for_image)
@safe_handler
async def ad_image(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(image_file_id=file_id)
    await message.reply("Reklama matnini yuboring:")
    await AddAdStates.waiting_for_text.set()

@dp.message_handler(state=AddAdStates.waiting_for_text, content_types=types.ContentTypes.TEXT)
@safe_handler
async def ad_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    await message.reply("Tugma matnini va URL ni shu formatda yuboring:\nTugmaMatni|https://example.com")
    await AddAdStates.waiting_for_button.set()

@dp.message_handler(state=AddAdStates.waiting_for_button, content_types=types.ContentTypes.TEXT)
@safe_handler
async def ad_button(message: types.Message, state: FSMContext):
    parts = message.text.split("|", 1)
    if len(parts) < 2:
        await message.reply("Format noto'g'ri. Misol: TugmaMatni|https://example.com")
        return
    await state.update_data(button_text=parts[0].strip(), button_url=parts[1].strip())
    await message.reply("Jadval vaqtini yuboring (YYYY-MM-DD HH:MM, UTC vaqtni ishlating):")
    await AddAdStates.waiting_for_time.set()

@dp.message_handler(state=AddAdStates.waiting_for_time, content_types=types.ContentTypes.TEXT)
@safe_handler
async def ad_time(message: types.Message, state: FSMContext):
    text = message.text.strip()
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        try:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        except Exception:
            await message.reply("Format noto'g'ri. Misol: 2025-08-10 15:30")
            return
    await state.update_data(schedule_time=dt.isoformat())
    await message.reply("Reklama necha marta yuborilsin? (raqam)")
    await AddAdStates.waiting_for_repeat.set()

@dp.message_handler(state=AddAdStates.waiting_for_repeat, content_types=types.ContentTypes.TEXT)
@safe_handler
async def ad_repeat(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.reply("Iltimos raqam yuboring.")
        return
    repeat = int(message.text)
    data = await state.get_data()
    ad_id = await db.add_ad(
        image_file_id=data['image_file_id'],
        text=data['text'],
        button_text=data['button_text'],
        button_url=data['button_url'],
        schedule_time_iso=data['schedule_time'],
        repeat_count=repeat
    )
    await message.reply(f"✅ Reklama qo'shildi. ID: {ad_id}")
    # schedule the ad
    schedule_ad_job(ad_id)
    await state.finish()

# list ads
@dp.message_handler(commands=['listads'])
@admin_only
@safe_handler
async def cmd_listads(message: types.Message):
    ads = await db.list_ads()
    if not ads:
        await message.reply("Hech qanday reklama yo'q.")
        return
    lines = []
    for ad in ads:
        lines.append(f"ID: {ad[0]} | Sent: {ad[7]}/{ad[6]} | Time: {ad[5]}\nText: {ad[2]}\nBtn: {ad[3]} -> {ad[4]}\n")
    await message.reply("\n\n".join(lines))

@dp.message_handler(commands=['deletead'])
@admin_only
@safe_handler
async def cmd_deletead(message: types.Message):
    args = message.get_args().strip()
    if not args.isdigit():
        await message.reply("Iltimos: /deletead <id>")
        return
    ad_id = int(args)
    await db.delete_ad(ad_id)
    # optionally remove job from scheduler if exists
    try:
        scheduler.remove_job(f"ad_{ad_id}")
    except Exception:
        pass
    await message.reply("✅ Reklama o'chirildi.")

# schedule helper
def schedule_ad_job(ad_id: int):
    # get ad details and schedule
    async def job():
        try:
            ad = await db.get_ad(ad_id)
            if not ad:
                return
            ad_id_local, image_file_id, text, button_text, button_url, schedule_time_iso, repeat_count, times_sent = ad
            # if times_sent >= repeat_count -> remove job
            if repeat_count is not None and times_sent >= repeat_count:
                try:
                    scheduler.remove_job(f"ad_{ad_id}")
                except Exception:
                    pass
                return
            # send ad to all users
            user_ids = await db.all_user_ids()
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton(button_text, url=button_url))
            for uid in user_ids:
                try:
                    await bot.send_photo(uid, photo=image_file_id, caption=text, reply_markup=kb)
                except Exception:
                    pass
                await asyncio.sleep(0.05)
            await db.increment_ad_sent(ad_id)
        except Exception as e:
            await report_error(traceback.format_exc())

    # fetch schedule_time
    async def schedule_future():
        try:
            ad = await db.get_ad(ad_id)
            if not ad:
                return
            schedule_time_iso = ad[5]
            dt = datetime.fromisoformat(schedule_time_iso)
            # if dt in past, schedule immediately once
            run_date = dt if dt > datetime.utcnow() else datetime.utcnow() + timedelta(seconds=5)
            scheduler.add_job(job, 'date', run_date=run_date, id=f"ad_{ad_id}")
        except Exception as e:
            await report_error(traceback.format_exc())

    asyncio.ensure_future(schedule_future())

# On startup: init DB and scheduler and ensure MAIN_ADMIN exists
async def on_startup(dp):
    try:
        await db.init_db()
        # ensure MAIN_ADMIN is in admins table
        await db.add_admin(MAIN_ADMIN)
        # start scheduler and load existing ads
        scheduler.start()
        ads = await db.list_ads()
        for ad in ads:
            schedule_ad_job(ad[0])
        logger.info("Bot started and DB initialized.")
    except Exception:
        await report_error(traceback.format_exc())

# On shutdown
async def on_shutdown(dp):
    await bot.close()
    scheduler.shutdown(wait=False)

# Fallback handler for unknown commands/messages
@dp.message_handler()
@safe_handler
async def fallback(message: types.Message):
    # If message is not numeric code and not command, instruct user
    await message.reply("Kino ko‘rish uchun kod yuboring yoki /start /admin kabi buyruqlardan foydalaning.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)
