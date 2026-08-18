import sqlite3
import os
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = os.getenv('DB_PATH', 'database.db')

def get_db():
    """Database connection qaytaradi"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db_context():
    """Context manager - avtomatik close"""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db():
    """18 ta jadvalni yaratish - migration"""
    conn = get_db()
    c = conn.cursor()

    # 1. users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        is_blocked INTEGER DEFAULT 0,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        failed_sends INTEGER DEFAULT 0
    )''')

    # 2. subscriptions
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        plan_type INTEGER NOT NULL,
        start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_date TIMESTAMP NOT NULL,
        status TEXT DEFAULT 'active',
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # 3. movies
    c.execute('''CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        quality TEXT,
        year INTEGER,
        language TEXT,
        rating REAL,
        file_id TEXT NOT NULL,
        request_count INTEGER DEFAULT 0
    )''')

    # 4. movie_ratings
    c.execute('''CREATE TABLE IF NOT EXISTS movie_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        movie_code TEXT NOT NULL,
        rating INTEGER NOT NULL,
        rated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, movie_code),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (movie_code) REFERENCES movies(code)
    )''')

    # 5. favorites
    c.execute('''CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        movie_code TEXT NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, movie_code),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (movie_code) REFERENCES movies(code)
    )''')

    # 6. user_watch_history
    c.execute('''CREATE TABLE IF NOT EXISTS user_watch_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        movie_code TEXT NOT NULL,
        watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (movie_code) REFERENCES movies(code)
    )''')

    # 7. promo_codes
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        discount_type TEXT NOT NULL,
        discount_value INTEGER NOT NULL,
        duration_days INTEGER,
        max_uses INTEGER DEFAULT 0,
        used_count INTEGER DEFAULT 0,
        start_date TIMESTAMP,
        end_date TIMESTAMP,
        is_active INTEGER DEFAULT 1
    )''')

    # 8. promo_uses
    c.execute('''CREATE TABLE IF NOT EXISTS promo_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        promo_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(promo_id, user_id),
        FOREIGN KEY (promo_id) REFERENCES promo_codes(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # 9. pending_payments
    c.execute('''CREATE TABLE IF NOT EXISTS pending_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        full_name TEXT,
        months INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        check_file_id TEXT NOT NULL,
        check_type TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # 10. offers
    c.execute('''CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        full_name TEXT,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # 11. admin_requests
    c.execute('''CREATE TABLE IF NOT EXISTS admin_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        full_name TEXT,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        handled_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # 12. bot_version
    c.execute('''CREATE TABLE IF NOT EXISTS bot_version (
        id INTEGER PRIMARY KEY CHECK(id=1),
        version TEXT DEFAULT '2.0',
        changelog TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 13. settings
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # 14. admins
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 15. movie_code_counter
    c.execute('''CREATE TABLE IF NOT EXISTS movie_code_counter (
        id INTEGER PRIMARY KEY CHECK(id=1),
        last_code INTEGER DEFAULT 0
    )''')

    # 16. mandatory_subscriptions
    c.execute('''CREATE TABLE IF NOT EXISTS mandatory_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        target_count INTEGER NOT NULL,
        active_count INTEGER DEFAULT 0,
        guarantee_days INTEGER NOT NULL,
        start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_date TIMESTAMP NOT NULL,
        status TEXT DEFAULT 'active',
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # 17. trial_subscriptions
    c.execute('''CREATE TABLE IF NOT EXISTS trial_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        trial_days INTEGER NOT NULL,
        start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_date TIMESTAMP NOT NULL,
        used INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # 18. referrals
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER NOT NULL,
        referred_id INTEGER NOT NULL,
        reward_type TEXT NOT NULL,
        reward_value INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (referrer_id) REFERENCES users(id),
        FOREIGN KEY (referred_id) REFERENCES users(id)
    )''')

    conn.commit()
    conn.close()

# ====================== USER FUNCTIONS ======================

def user_exists(user_id):
    """Foydalanuvchi mavjud yoki yoʻq"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE id=?', (user_id,))
        return c.fetchone() is not None

def add_user(user_id, username, full_name):
    """Yangi foydalanuvchi qoʻshish"""
    if user_exists(user_id):
        return
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO users (id, username, full_name) VALUES (?, ?, ?)',
                  (user_id, username, full_name))

def get_user(user_id):
    """Foydalanuvchi maʼlumoti"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE id=?', (user_id,))
        row = c.fetchone()
        return dict(row) if row else None

def is_blocked(user_id):
    """Foydalanuvchi bloklangan yoʻq"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT is_blocked FROM users WHERE id=?', (user_id,))
        row = c.fetchone()
        return row['is_blocked'] == 1 if row else False

def block_user(user_id):
    """Foydalanuvchini bloklash"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET is_blocked=1 WHERE id=?', (user_id,))

def unblock_user(user_id):
    """Blokni ochish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET is_blocked=0 WHERE id=?', (user_id,))

def get_all_users():
    """Barcha foydalanuvchilar"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE is_blocked=0 ORDER BY id')
        return [row['id'] for row in c.fetchall()]

# ====================== SUBSCRIPTION FUNCTIONS ======================

def get_subscription(user_id):
    """Obuna maʼlumoti"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM subscriptions WHERE user_id=?', (user_id,))
        row = c.fetchone()
        return dict(row) if row else None

def has_active_subscription(user_id):
    """Faol obuna bor yoʻq"""
    sub = get_subscription(user_id)
    if not sub:
        return False
    end_date = datetime.fromisoformat(sub['end_date'])
    return end_date > datetime.now() and sub['status'] == 'active'

def create_subscription(user_id, plan_type):
    """Yangi obuna yaratish"""
    with get_db_context() as conn:
        c = conn.cursor()
        # Eski obunani o'chirish
        c.execute('DELETE FROM subscriptions WHERE user_id=?', (user_id,))
        
        # Narxlar
        prices = {1: 50000, 3: 135000, 6: 255000, 12: 450000}
        end_date = datetime.now() + timedelta(days=plan_type * 30)
        
        c.execute('''INSERT INTO subscriptions (user_id, plan_type, end_date, status)
                     VALUES (?, ?, ?, 'active')''',
                  (user_id, plan_type, end_date.isoformat()))

def extend_subscription(user_id, months):
    """Obunani uzaytirish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT end_date FROM subscriptions WHERE user_id=?', (user_id,))
        row = c.fetchone()
        if not row:
            return
        
        end_date = datetime.fromisoformat(row['end_date'])
        new_end = end_date + timedelta(days=months * 30)
        c.execute('UPDATE subscriptions SET end_date=? WHERE user_id=?',
                  (new_end.isoformat(), user_id))

def reduce_subscription(user_id, months):
    """Obunani qisqartirish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT end_date FROM subscriptions WHERE user_id=?', (user_id,))
        row = c.fetchone()
        if not row:
            return
        
        end_date = datetime.fromisoformat(row['end_date'])
        new_end = end_date - timedelta(days=months * 30)
        if new_end > datetime.now():
            c.execute('UPDATE subscriptions SET end_date=? WHERE user_id=?',
                      (new_end.isoformat(), user_id))

# ====================== MOVIE FUNCTIONS ======================

def get_next_movie_code():
    """Keyingi movie code qaytaradi (000001, 000002, ...)"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT last_code FROM movie_code_counter WHERE id=1')
        row = c.fetchone()
        last_code = row['last_code'] if row else 0
        
        new_code = last_code + 1
        c.execute('''INSERT OR REPLACE INTO movie_code_counter (id, last_code)
                     VALUES (1, ?)''', (new_code,))
        
        return f"{new_code:06d}"

def add_movie(code, name, quality, year, language, rating, file_id):
    """Yangi kino qoʻshish"""
    with get_db_context() as conn:
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO movies (code, name, quality, year, language, rating, file_id)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (code, name, quality, year, language, rating, file_id))
        except sqlite3.IntegrityError:
            return False
        return True

def get_movie_by_code(code):
    """Kino topish (code boʻyicha)"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM movies WHERE code=?', (code,))
        row = c.fetchone()
        return dict(row) if row else None

def get_movie_by_name(name):
    """Kino topish (nom boʻyicha)"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM movies WHERE name LIKE ?', (f'%{name}%',))
        rows = c.fetchall()
        return [dict(row) for row in rows]

def get_all_movies():
    """Barcha kinolar"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM movies ORDER BY code DESC')
        return [dict(row) for row in c.fetchall()]

def delete_movie(code):
    """Kinoni oʻchirish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('DELETE FROM movies WHERE code=?', (code,))

def increment_request_count(code):
    """Request count orttirish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('UPDATE movies SET request_count=request_count+1 WHERE code=?', (code,))

# ====================== RATING & FAVORITES ======================

def add_rating(user_id, movie_code, rating):
    """Reyting qoʻshish"""
    with get_db_context() as conn:
        c = conn.cursor()
        try:
            c.execute('''INSERT OR REPLACE INTO movie_ratings (user_id, movie_code, rating)
                         VALUES (?, ?, ?)''', (user_id, movie_code, rating))
        except:
            pass

def add_favorite(user_id, movie_code):
    """Sevimlilarga qoʻshish"""
    with get_db_context() as conn:
        c = conn.cursor()
        try:
            c.execute('INSERT INTO favorites (user_id, movie_code) VALUES (?, ?)',
                      (user_id, movie_code))
        except:
            pass

def is_favorite(user_id, movie_code):
    """Sevimlida bor yoʻq"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT id FROM favorites WHERE user_id=? AND movie_code=?',
                  (user_id, movie_code))
        return c.fetchone() is not None

def remove_favorite(user_id, movie_code):
    """Sevimlilardan oʻchirish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('DELETE FROM favorites WHERE user_id=? AND movie_code=?',
                  (user_id, movie_code))

def get_favorites(user_id):
    """Foydalanuvchining sevimlilar roʻyxati"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT movie_code FROM favorites WHERE user_id=? ORDER BY added_at DESC',
                  (user_id,))
        return [row['movie_code'] for row in c.fetchall()]

def add_watch_history(user_id, movie_code):
    """Ko'rish tarixiga qoʻshish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO user_watch_history (user_id, movie_code) VALUES (?, ?)',
                  (user_id, movie_code))

# ====================== PROMO CODE FUNCTIONS ======================

def create_promo_code(code, discount_type, discount_value, duration_days=None, max_uses=0, start_date=None, end_date=None):
    """Promo-kod yaratish"""
    with get_db_context() as conn:
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO promo_codes 
                         (code, discount_type, discount_value, duration_days, max_uses, start_date, end_date)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (code, discount_type, discount_value, duration_days, max_uses, start_date, end_date))
        except sqlite3.IntegrityError:
            return False
        return True

def get_promo_code(code):
    """Promo-kod maʼlumoti"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM promo_codes WHERE code=?', (code,))
        row = c.fetchone()
        return dict(row) if row else None

def promo_can_be_used(code, user_id):
    """Promo-kodni ishlatish mumkin yoʻq"""
    promo = get_promo_code(code)
    if not promo or promo['is_active'] == 0:
        return False, "Promo-kod faol emas"
    
    # Muddat tekshirish
    if promo['start_date']:
        start = datetime.fromisoformat(promo['start_date'])
        if datetime.now() < start:
            return False, "Promo-kod hali faol emas"
    
    if promo['end_date']:
        end = datetime.fromisoformat(promo['end_date'])
        if datetime.now() > end:
            return False, "Promo-kod muddati tugadi"
    
    # Max uses tekshirish
    if promo['max_uses'] > 0 and promo['used_count'] >= promo['max_uses']:
        return False, "Promo-kod cheklovini yetkazdi"
    
    # User oldin ishlatgan yoʻq
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT id FROM promo_uses WHERE promo_id=? AND user_id=?',
                  (promo['id'], user_id))
        if c.fetchone():
            return False, "Siz bu promo-kodni allaqachon ishlatdingiz"
    
    return True, "OK"

def use_promo_code(promo_id, user_id):
    """Promo-kod ishlatildi deb belgilash"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO promo_uses (promo_id, user_id) VALUES (?, ?)',
                  (promo_id, user_id))
        c.execute('UPDATE promo_codes SET used_count=used_count+1 WHERE id=?', (promo_id,))

# ====================== PAYMENT FUNCTIONS ======================

def add_pending_payment(user_id, username, full_name, months, amount, check_file_id, check_type):
    """To'lov talab qoʻshish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO pending_payments 
                     (user_id, username, full_name, months, amount, check_file_id, check_type)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, username, full_name, months, amount, check_file_id, check_type))

def get_pending_payments():
    """Barcha kutilayotgan toʻlovlar"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM pending_payments WHERE status=? ORDER BY created_at DESC', ('pending',))
        return [dict(row) for row in c.fetchall()]

def approve_payment(payment_id):
    """To'lovni tasdiqlash va obuna yaratish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM pending_payments WHERE id=?', (payment_id,))
        payment = c.fetchone()
        if not payment:
            return False
        
        c.execute('UPDATE pending_payments SET status=? WHERE id=?', ('approved', payment_id))
        
        # Obunani yaratish
        create_subscription(payment['user_id'], payment['months'])
        return True

def reject_payment(payment_id):
    """To'lovni rad etish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('UPDATE pending_payments SET status=? WHERE id=?', ('rejected', payment_id))

# ====================== OFFER & REQUEST FUNCTIONS ======================

def add_offer(user_id, username, full_name, message):
    """Taklifni saqlash"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO offers (user_id, username, full_name, message) VALUES (?, ?, ?, ?)',
                  (user_id, username, full_name, message))

def add_admin_request(user_id, username, full_name, message):
    """Admin talab qoʻshish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO admin_requests (user_id, username, full_name, message) VALUES (?, ?, ?, ?)',
                  (user_id, username, full_name, message))

def get_pending_admin_requests():
    """Kutilayotgan admin talablar"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM admin_requests WHERE status=? ORDER BY created_at DESC', ('pending',))
        return [dict(row) for row in c.fetchall()]

def mark_admin_request_handled(request_id, admin_id):
    """Talabni bajarildi deb belgilash"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('UPDATE admin_requests SET status=?, handled_by=? WHERE id=?',
                  ('handled', admin_id, request_id))

# ====================== ADMIN FUNCTIONS ======================

def is_admin(user_id, main_admin):
    """Admin ekanligini tekshirish"""
    if user_id == main_admin:
        return True
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT user_id FROM admins WHERE user_id=?', (user_id,))
        return c.fetchone() is not None

def add_admin(user_id):
    """Admin qoʻshish"""
    with get_db_context() as conn:
        c = conn.cursor()
        try:
            c.execute('INSERT INTO admins (user_id) VALUES (?)', (user_id,))
        except:
            pass

def remove_admin(user_id):
    """Adminni oʻchirish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('DELETE FROM admins WHERE user_id=?', (user_id,))

def get_all_admins():
    """Barcha adminlar"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT user_id FROM admins ORDER BY added_date DESC')
        return [row['user_id'] for row in c.fetchall()]

# ====================== MANDATORY SUBSCRIPTION FUNCTIONS ======================

def create_mandatory_subscription(user_id, target_count, guarantee_days):
    """Majburiy obuna yaratish"""
    with get_db_context() as conn:
        c = conn.cursor()
        end_date = datetime.now() + timedelta(days=guarantee_days)
        try:
            c.execute('''INSERT INTO mandatory_subscriptions 
                         (user_id, target_count, guarantee_days, end_date)
                         VALUES (?, ?, ?, ?)''',
                      (user_id, target_count, guarantee_days, end_date.isoformat()))
        except:
            pass

def get_mandatory_subscription(user_id):
    """Majburiy obuna maʼlumoti"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM mandatory_subscriptions WHERE user_id=?', (user_id,))
        row = c.fetchone()
        return dict(row) if row else None

# ====================== TRIAL SUBSCRIPTION FUNCTIONS ======================

def create_trial_subscription(user_id, trial_days=3):
    """Trial obuna yaratish"""
    with get_db_context() as conn:
        c = conn.cursor()
        end_date = datetime.now() + timedelta(days=trial_days)
        try:
            c.execute('''INSERT INTO trial_subscriptions (user_id, trial_days, end_date)
                         VALUES (?, ?, ?)''', (user_id, trial_days, end_date.isoformat()))
        except:
            pass

def get_trial_subscription(user_id):
    """Trial obuna maʼlumoti"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM trial_subscriptions WHERE user_id=?', (user_id,))
        row = c.fetchone()
        return dict(row) if row else None

def trial_used(user_id):
    """Trial ishlatildi deb belgilash"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('UPDATE trial_subscriptions SET used=1 WHERE user_id=?', (user_id,))

# ====================== REFERRAL FUNCTIONS ======================

def create_referral(referrer_id, referred_id, reward_type, reward_value):
    """Referral yaratish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO referrals (referrer_id, referred_id, reward_type, reward_value)
                     VALUES (?, ?, ?, ?)''', (referrer_id, referred_id, reward_type, reward_value))

def get_pending_referrals(user_id):
    """Foydalanuvchining kutilayotgan referrallar"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM referrals WHERE referrer_id=? AND status=?',
                  (user_id, 'pending'))
        return [dict(row) for row in c.fetchall()]

def complete_referral(referral_id):
    """Referralni tugatish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('UPDATE referrals SET status=? WHERE id=?', ('completed', referral_id))

# ====================== SETTINGS FUNCTIONS ======================

def get_setting(key, default=None):
    """Sozlamani oʻqish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT value FROM settings WHERE key=?', (key,))
        row = c.fetchone()
        return row['value'] if row else default

def set_setting(key, value):
    """Sozlamani oʻrnatish"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))

def get_all_settings():
    """Barcha sozlamalar"""
    with get_db_context() as conn:
        c = conn.cursor()
        c.execute('SELECT key, value FROM settings')
        return {row['key']: row['value'] for row in c.fetchall()}

# ====================== STATS FUNCTIONS ======================

def get_stats():
    """Asosiy statistika"""
    with get_db_context() as conn:
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) as total FROM users')
        total_users = c.fetchone()['total']
        
        c.execute('SELECT COUNT(*) as active FROM subscriptions WHERE status=?', ('active',))
        active_subs = c.fetchone()['active']
        
        c.execute('SELECT COUNT(*) as total FROM movies')
        total_movies = c.fetchone()['total']
        
        c.execute('SELECT code, name, request_count FROM movies ORDER BY request_count DESC LIMIT 5')
        top_movies = [dict(row) for row in c.fetchall()]
        
        return {
            'total_users': total_users,
            'active_subs': active_subs,
            'total_movies': total_movies,
            'top_5': top_movies
        }

if __name__ == '__main__':
    init_db()
    print("✅ Database initialized!")
