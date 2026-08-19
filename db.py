import sqlite3
import datetime
from typing import Optional, List, Dict, Any

DB_PATH = "database.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        is_blocked INTEGER DEFAULT 0,
        join_date TEXT,
        failed_sends INTEGER DEFAULT 0
    )
    """)

    # 2. subscriptions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plan_type INTEGER,
        start_date TEXT,
        end_date TEXT,
        status TEXT DEFAULT 'active'
    )
    """)

    # 3. movies
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        name TEXT,
        quality TEXT,
        year TEXT,
        language TEXT,
        rating REAL DEFAULT 5.0,
        file_id TEXT,
        request_count INTEGER DEFAULT 0,
        part INTEGER DEFAULT 1
    )
    """)

    # 4. movie_ratings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movie_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        movie_code TEXT,
        rating INTEGER,
        rated_at TEXT,
        UNIQUE(user_id, movie_code)
    )
    """)

    # 5. favorites
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        movie_code TEXT,
        added_at TEXT,
        UNIQUE(user_id, movie_code)
    )
    """)

    # 6. user_watch_history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_watch_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        movie_code TEXT,
        watched_at TEXT
    )
    """)

    # 7. promo_codes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promo_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        discount_type TEXT,
        discount_value REAL,
        duration_days INTEGER,
        max_uses INTEGER DEFAULT 0,
        used_count INTEGER DEFAULT 0,
        start_date TEXT,
        end_date TEXT,
        is_active INTEGER DEFAULT 1
    )
    """)

    # 8. promo_uses
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promo_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        promo_id INTEGER,
        user_id INTEGER,
        used_at TEXT,
        UNIQUE(promo_id, user_id)
    )
    """)

    # 9. pending_payments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pending_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        full_name TEXT,
        months INTEGER,
        amount INTEGER,
        check_file_id TEXT,
        check_type TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )
    """)

    # 10. offers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        full_name TEXT,
        message TEXT,
        created_at TEXT
    )
    """)

    # 11. admin_requests
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        full_name TEXT,
        message TEXT,
        status TEXT DEFAULT 'pending',
        handled_by INTEGER,
        created_at TEXT
    )
    """)

    # 12. bot_version
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_version (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        version TEXT,
        changelog TEXT,
        updated_at TEXT
    )
    """)

    # 13. settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # 14. admins
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        added_date TEXT
    )
    """)

    # 15. movie_code_counter
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movie_code_counter (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        last_code INTEGER DEFAULT 100
    )
    """)

    # 16. mandatory_subscriptions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mandatory_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT UNIQUE,
        channel_url TEXT,
        channel_name TEXT,
        status TEXT DEFAULT 'active'
    )
    """)

    # 17. trial_subscriptions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trial_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        trial_days INTEGER DEFAULT 3,
        start_date TEXT,
        end_date TEXT,
        used INTEGER DEFAULT 0
    )
    """)

    # 18. referrals
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER UNIQUE,
        reward_type TEXT DEFAULT 'free_days',
        reward_value REAL DEFAULT 3,
        status TEXT DEFAULT 'pending',
        created_date TEXT
    )
    """)

    # Standart sozlamalar
    default_settings = {
        "card_number": "9860170109969320",
        "card_holder": "Solejon Adashov Isroilovich",
        "price_1": "5000",
        "price_3": "15000",
        "price_6": "30000",
        "price_12": "60000",
        "trial_days": "3",
        "referral_reward_type": "free_days",
        "referral_reward_value": "3"
    }

    for key, val in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    cursor.execute("INSERT OR IGNORE INTO bot_version (id, version, changelog, updated_at) VALUES (1, 'v2.0', 'Kino Bot v2.0 toliq ishga tushdi', datetime('now'))")
    cursor.execute("INSERT OR IGNORE INTO movie_code_counter (id, last_code) VALUES (1, 100)")

    conn.commit()
    conn.close()

# Helper DB Funksiyalar
def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def is_admin(user_id: int, main_admin_id: int) -> bool:
    if user_id == main_admin_id:
        return True
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None

def add_user(user_id: int, username: str, full_name: str):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR REPLACE INTO users (id, username, full_name, join_date) VALUES (?, ?, ?, COALESCE((SELECT join_date FROM users WHERE id = ?), ?))",
              (user_id, username, full_name, user_id, now))
    conn.commit()
    conn.close()

def is_user_blocked(user_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT is_blocked FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row["is_blocked"]) if row else False

def get_user_subscription(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' AND end_date > ? ORDER BY id DESC LIMIT 1", (user_id, now))
    sub = c.fetchone()
    conn.close()
    return sub

def has_active_subscription(user_id: int, main_admin_id: int) -> bool:
    if is_admin(user_id, main_admin_id):
        return True
    return get_user_subscription(user_id) is not None

def get_next_movie_code() -> str:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT last_code FROM movie_code_counter WHERE id = 1")
    last_code = c.fetchone()["last_code"]
    next_code = last_code + 1
    c.execute("UPDATE movie_code_counter SET last_code = ? WHERE id = 1", (next_code,))
    conn.commit()
    conn.close()
    return str(next_code)

def add_movie(code: str, name: str, quality: str, year: str, language: str, rating: float, file_id: str, part: int = 1):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO movies (code, name, quality, year, language, rating, file_id, part)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (code, name, quality, year, language, rating, file_id, part))
    conn.commit()
    conn.close()

def get_movie_by_id(movie_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_movies_by_code(code: str) -> List[sqlite3.Row]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM movies WHERE code = ? ORDER BY part ASC", (code,))
    rows = c.fetchall()
    if rows:
        c.execute("UPDATE movies SET request_count = request_count + 1 WHERE code = ?", (code,))
        conn.commit()
    conn.close()
    return rows

def search_movies_by_name(query: str) -> List[sqlite3.Row]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT code, name, year, quality, language, rating FROM movies WHERE name LIKE ? ORDER BY id DESC LIMIT 15", (f"%{query}%",))
    rows = c.fetchall()
    conn.close()
    return rows

def add_rating(user_id: int, movie_code: str, rating: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO movie_ratings (user_id, movie_code, rating, rated_at) VALUES (?, ?, ?, datetime('now'))",
              (user_id, movie_code, rating))
    # Yangi o'rtacha reytingni hisoblab movies jadvaliga yozish
    c.execute("SELECT AVG(rating) as avg_rating FROM movie_ratings WHERE movie_code = ?", (movie_code,))
    avg_r = c.fetchone()["avg_rating"]
    if avg_r:
        c.execute("UPDATE movies SET rating = ROUND(?, 1) WHERE code = ?", (avg_r, movie_code))
    conn.commit()
    conn.close()

def add_subscription(user_id: int, plan_months: int):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now()
    end_date = now + datetime.timedelta(days=plan_months * 30)
    c.execute("""
    INSERT INTO subscriptions (user_id, plan_type, start_date, end_date, status)
    VALUES (?, ?, ?, ?, 'active')
    """, (user_id, plan_months, now.strftime("%Y-%m-%d %H:%M:%S"), end_date.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def add_days_subscription(user_id: int, days: int):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now()
    sub = get_user_subscription(user_id)
    if sub:
        cur_end = datetime.datetime.strptime(sub["end_date"], "%Y-%m-%d %H:%M:%S")
        new_end = max(now, cur_end) + datetime.timedelta(days=days)
        c.execute("UPDATE subscriptions SET end_date = ? WHERE id = ?", (new_end.strftime("%Y-%m-%d %H:%M:%S"), sub["id"]))
    else:
        new_end = now + datetime.timedelta(days=days)
        c.execute("INSERT INTO subscriptions (user_id, plan_type, start_date, end_date, status) VALUES (?, 0, ?, ?, 'active')",
                  (user_id, now.strftime("%Y-%m-%d %H:%M:%S"), new_end.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_mandatory_channels() -> List[sqlite3.Row]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM mandatory_subscriptions WHERE status = 'active'")
    rows = c.fetchall()
    conn.close()
    return rows
    