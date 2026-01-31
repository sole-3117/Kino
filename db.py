import aiosqlite
from datetime import datetime, timedelta

DB_FILE = "bot_data.db"

async def init():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            title TEXT,
            quality TEXT,
            year INTEGER,
            language TEXT,
            rating TEXT,
            file_id TEXT NOT NULL,
            added_by INTEGER,
            added_at TEXT
        )''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            join_at TEXT,
            sub_until TEXT,
            failed INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0
        )''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')

        # default qiymatlar
        for k, v in [
            ("price_1m", "35000"),
            ("price_3m", "90000"),
            ("price_6m", "160000"),
            ("price_12m", "300000"),
            ("card_number", "8600 xxxx xxxx xxxx"),
            ("card_holder", "SOLEJON ADASHOV ISROILOVICH")
        ]:
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        await db.commit()


async def is_admin(uid: int) -> bool:
    async with aiosqlite.connect(DB_FILE) as db:
        row = await (await db.execute("SELECT 1 FROM admins WHERE user_id = ?", (uid,))).fetchone()
        return bool(row)


async def add_admin(uid: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (uid,))
        await db.commit()


async def add_user(uid: int, username: str | None):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, join_at)
            VALUES (?, ?, datetime('now'))
        """, (uid, username))
        await db.commit()


async def has_active_sub(uid: int) -> bool:
    async with aiosqlite.connect(DB_FILE) as db:
        row = await (await db.execute(
            "SELECT sub_until FROM users WHERE user_id = ?",
            (uid,)
        )).fetchone()

        if not row or not row[0]:
            return False

        return datetime.fromisoformat(row[0]) > datetime.now()


async def set_subscription(uid: int, days: int):
    until = (datetime.now() + timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            UPDATE users
            SET sub_until = ?, failed = 0, blocked = 0
            WHERE user_id = ?
        """, (until, uid))
        await db.commit()


async def add_movie(code: str, data: dict, admin_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        try:
            await db.execute("""
                INSERT INTO movies (code, title, quality, year, language, rating, file_id, added_by, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                code,
                data["title"],
                data.get("quality"),
                data.get("year"),
                data.get("language"),
                data.get("rating"),
                data["file_id"],
                admin_id
            ))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_movie(code: str):
    async with aiosqlite.connect(DB_FILE) as db:
        row = await (await db.execute("SELECT * FROM movies WHERE code = ?", (code,))).fetchone()
        return row


async def get_setting(key: str, default=None):
    async with aiosqlite.connect(DB_FILE) as db:
        row = await (await db.execute("SELECT value FROM settings WHERE key = ?", (key,))).fetchone()
        return row[0] if row else default


async def inc_failed(uid: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            UPDATE users
            SET failed = failed + 1,
                blocked = CASE WHEN failed + 1 >= 3 THEN 1 ELSE blocked END
            WHERE user_id = ?
        """, (uid,))
        await db.commit()
