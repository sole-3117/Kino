# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_FILE = os.getenv("DATABASE_FILE", "movies.db")
MAIN_ADMIN = int(os.getenv("MAIN_ADMIN", "6887251996"))  # superadmin doimiy
