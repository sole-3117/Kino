import asyncio
import logging
from telegram import Bot
from telegram.request import HTTPXRequest

logging.basicConfig(level=logging.INFO)

TOKEN = "8706907034:AAGq9LCcVwF6Yn3UjR3RtM2LRMO6Aft3sNE"  # o‘z tokeningizni qo‘ying

async def main():
    print("Ulanish tekshirilmoqda...")
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    bot = Bot(token=TOKEN, request=request)
    try:
        me = await bot.get_me()
        print(f"✅ Muvaffaqiyatli: @{me.username}")
    except Exception as e:
        print(f"❌ Xatolik: {e}")

asyncio.run(main())