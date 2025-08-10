# database.py
import aiosqlite
import asyncio
from datetime import datetime

DB_INIT_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    fullname TEXT,
    joined_date TEXT
);

CREATE TABLE IF NOT EXISTS movies (
    code INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    format TEXT,
    language TEXT,
    file_id TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    is_deleted INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS channels (
    username TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_file_id TEXT,
    text TEXT,
    button_text TEXT,
    button_url TEXT,
    schedule_time TEXT,  -- ISO datetime string
    repeat_count INTEGER DEFAULT 1,
    times_sent INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

class Database:
    def __init__(self, path):
        self.path = path
        self._lock = asyncio.Lock()

    async def init_db(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(DB_INIT_SQL)
            await db.commit()
        # Ensure MAIN_ADMIN exists as admin inserted externally by bot startup

    # USERS
    async def add_or_update_user(self, user_id: int, username: str, fullname: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (id, username, fullname, joined_date) VALUES (?, ?, ?, ?)",
                (user_id, username, fullname, datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def count_users(self):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM users")
            r = await cur.fetchone()
            return r[0] if r else 0

    async def all_user_ids(self):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT id FROM users")
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    # CHANNELS
    async def add_channel(self, username):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO channels (username) VALUES (?)", (username,))
            await db.commit()

    async def remove_channel(self, username):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM channels WHERE username = ?", (username,))
            await db.commit()

    async def list_channels(self):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT username FROM channels")
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    # SETTINGS
    async def set_setting(self, key, value):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            await db.commit()

    async def get_setting(self, key, default=None):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = await cur.fetchone()
            return row[0] if row else default

    # ADMINS
    async def add_admin(self, user_id):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
            await db.commit()

    async def remove_admin(self, user_id):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            await db.commit()

    async def is_admin(self, user_id):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            return bool(row)

    async def list_admins(self):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT user_id FROM admins")
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    # MOVIES
    async def _get_all_codes(self):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT code FROM movies")
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    async def get_next_code(self):
        # find smallest positive integer not currently used OR use deleted slots
        codes = set(await self._get_all_codes())
        i = 1
        while True:
            if i not in codes:
                return i
            i += 1

    async def add_movie(self, title, format_, language, file_id):
        code = await self.get_next_code()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO movies (code, title, format, language, file_id, views, is_deleted) VALUES (?, ?, ?, ?, ?, 0, 0)",
                (code, title, format_, language, file_id),
            )
            await db.commit()
        return code

    async def get_movie(self, code):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT code, title, format, language, file_id, views, is_deleted FROM movies WHERE code = ?", (code,))
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "code": row[0],
                "title": row[1],
                "format": row[2],
                "language": row[3],
                "file_id": row[4],
                "views": row[5],
                "is_deleted": row[6]
            }

    async def increment_views(self, code):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE movies SET views = views + 1 WHERE code = ?", (code,))
            await db.commit()

    async def delete_movie(self, code):
        # soft delete
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE movies SET is_deleted = 1 WHERE code = ?", (code,))
            await db.commit()

    async def movies_count(self):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM movies WHERE is_deleted = 0")
            r = await cur.fetchone()
            return r[0] if r else 0

    async def all_movies(self):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT code, title, format, language, file_id, views, is_deleted FROM movies ORDER BY code")
            rows = await cur.fetchall()
            return rows

    async def total_views(self):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT SUM(views) FROM movies")
            r = await cur.fetchone()
            return r[0] or 0

    # ADS
    async def add_ad(self, image_file_id, text, button_text, button_url, schedule_time_iso, repeat_count):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO ads (image_file_id, text, button_text, button_url, schedule_time, repeat_count, times_sent) VALUES (?, ?, ?, ?, ?, ?, 0)",
                (image_file_id, text, button_text, button_url, schedule_time_iso, repeat_count)
            )
            await db.commit()
            return cur.lastrowid

    async def list_ads(self):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT id, image_file_id, text, button_text, button_url, schedule_time, repeat_count, times_sent FROM ads")
            rows = await cur.fetchall()
            return rows

    async def delete_ad(self, ad_id):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
            await db.commit()

    async def increment_ad_sent(self, ad_id):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE ads SET times_sent = times_sent + 1 WHERE id = ?", (ad_id,))
            await db.commit()

    async def get_ad(self, ad_id):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT id, image_file_id, text, button_text, button_url, schedule_time, repeat_count, times_sent FROM ads WHERE id = ?", (ad_id,))
            return await cur.fetchone()
