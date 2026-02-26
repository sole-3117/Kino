import asyncio
import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, Text
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

import sqlite3

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6887251996

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- DATABASE ---
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Users Table
cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    telegram_id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    subscription_status TEXT,
    subscription_end DATE
)""")

# Payments Table
cursor.execute("""CREATE TABLE IF NOT EXISTS payments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    package TEXT,
    price REAL,
    discount REAL,
    file_path TEXT,
    status TEXT
)""")

# Movies Table
cursor.execute("""CREATE TABLE IF NOT EXISTS movies(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    year TEXT,
    genre TEXT,
    rating TEXT,
    description TEXT,
    file_id TEXT
)""")

# Settings Table
cursor.execute("""CREATE TABLE IF NOT EXISTS settings(
    key TEXT PRIMARY KEY,
    value TEXT
)""")
conn.commit()

# --- STATES ---
class AddMovie(StatesGroup):
    waiting_name = State()
    waiting_year = State()
    waiting_genre = State()
    waiting_rating = State()
    waiting_description = State()
    waiting_file = State()

class Payment(StatesGroup):
    waiting_package = State()
    waiting_receipt = State()

# --- HELPERS ---
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    return cursor.fetchone()

def update_subscription(user_id, duration_days):
    end_date = datetime.now() + timedelta(days=duration_days)
    cursor.execute("UPDATE users SET subscription_status='Active', subscription_end=? WHERE telegram_id=?",
                   (end_date.date(), user_id))
    conn.commit()
    return end_date

def add_user(user_id, first_name, username):
    if not get_user(user_id):
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, 'Expired', ?)", 
                       (user_id, first_name, username, datetime.now().date()))
        conn.commit()

def get_movies_by_name(name):
    cursor.execute("SELECT * FROM movies WHERE name LIKE ?", ('%'+name+'%',))
    return cursor.fetchall()

def get_movie_by_id(movie_id):
    cursor.execute("SELECT * FROM movies WHERE id=?", (movie_id,))
    return cursor.fetchone()

def add_movie(name, year, genre, rating, description, file_id):
    cursor.execute("INSERT INTO movies(name, year, genre, rating, description, file_id) VALUES(?,?,?,?,?,?)",
                   (name, year, genre, rating, description, file_id))
    conn.commit()

def delete_movie(movie_id):
    cursor.execute("DELETE FROM movies WHERE id=?", (movie_id,))
    conn.commit()

# --- DAILY TASKS ---
scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("interval", hours=24)
async def subscription_check():
    cursor.execute("SELECT telegram_id, subscription_end FROM users WHERE subscription_status='Active'")
    users = cursor.fetchall()
    for user_id, end_date in users:
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        days_left = (end_date_obj - datetime.now().date()).days
        if days_left <= 2 and days_left > 0:
            await bot.send_message(user_id, f"Sizning obunangiz {days_left} kun ichida tugaydi!")
        elif days_left <= 0:
            cursor.execute("UPDATE users SET subscription_status='Expired' WHERE telegram_id=?", (user_id,))
            conn.commit()
            await bot.send_message(user_id, "Sizning obunangiz tugadi! Kino ko‘ra olmaysiz.")

scheduler.start()

# --- COMMANDS ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    add_user(message.from_user.id, message.from_user.first_name, message.from_user.username)
    user = get_user(message.from_user.id)
    await message.answer(f"Salom {message.from_user.first_name}!\n"
                         f"Obuna holatingiz: {user[3]}")

# Admin only commands
def is_admin(user_id):
    return user_id == ADMIN_ID

@dp.message(Command("add"))
async def cmd_add(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Kino nomini kiriting:")
    await state.set_state(AddMovie.waiting_name)

@dp.message(AddMovie.waiting_name)
async def movie_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Yilni kiriting:")
    await state.set_state(AddMovie.waiting_year)

@dp.message(AddMovie.waiting_year)
async def movie_year(message: types.Message, state: FSMContext):
    await state.update_data(year=message.text)
    await message.answer("Janrni kiriting:")
    await state.set_state(AddMovie.waiting_genre)

@dp.message(AddMovie.waiting_genre)
async def movie_genre(message: types.Message, state: FSMContext):
    await state.update_data(genre=message.text)
    await message.answer("Bahoni kiriting:")
    await state.set_state(AddMovie.waiting_rating)

@dp.message(AddMovie.waiting_rating)
async def movie_rating(message: types.Message, state: FSMContext):
    await state.update_data(rating=message.text)
    await message.answer("Qisqa izoh kiriting:")
    await state.set_state(AddMovie.waiting_description)

@dp.message(AddMovie.waiting_description)
async def movie_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Video faylini yuboring (Telegram fayl bo‘lishi kerak):")
    await state.set_state(AddMovie.waiting_file)

@dp.message(AddMovie.waiting_file, F.content_type == ["video", "document"])
async def movie_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.video.file_id if message.video else message.document.file_id
    add_movie(data['name'], data['year'], data['genre'], data['rating'], data['description'], file_id)
    await message.answer("Kino muvaffaqiyatli qo‘shildi!")
    await state.clear()

# Search movies
@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    text = message.get_args()
    if not text:
        await message.answer("Qidiriladigan kino nomini yozing: /search <nomi>")
        return
    movies = get_movies_by_name(text)
    if not movies:
        await message.answer("Kino topilmadi.")
        return
    for movie in movies:
        await message.answer(f"{movie[1]} ({movie[2]})\nJanr: {movie[3]}\nRating: {movie[4]}\n{movie[5]}",
                             reply_markup=InlineKeyboardMarkup(
                                 inline_keyboard=[[InlineKeyboardButton(text="Ko‘rish", callback_data=f"watch_{movie[0]}")]]
                             ))

@dp.callback_query(Text(startswith="watch_"))
async def watch_movie(callback: types.CallbackQuery):
    movie_id = int(callback.data.split("_")[1])
    user = get_user(callback.from_user.id)
    if user[3] != "Active":
        await callback.message.answer("Sizning obunangiz tugagan! Kino ko‘ra olmaysiz.")
        return
    movie = get_movie_by_id(movie_id)
    if movie:
        await bot.send_video(callback.from_user.id, movie[6], caption=f"{movie[1]} ({movie[2]})")

# Run
if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))