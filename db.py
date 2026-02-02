import sqlite3
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path='database.db'):
        self.db_path = db_path
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Foydalanuvchilar jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    subscription_end TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    is_blocked INTEGER DEFAULT 0,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Filmlar jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS movies (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    quality TEXT,
                    year INTEGER,
                    language TEXT,
                    rating TEXT,
                    file_id TEXT NOT NULL,
                    file_type TEXT,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    added_by INTEGER
                )
            ''')
            
            # Sozlamalar jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # To'lovlar jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    period_days INTEGER,
                    photo_file_id TEXT,
                    status TEXT DEFAULT 'pending',
                    admin_id INTEGER,
                    processed_date TIMESTAMP,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Adminlar jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    added_by INTEGER,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Aktivlik jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_activity (
                    user_id INTEGER,
                    activity_date DATE,
                    message_count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, activity_date)
                )
            ''')
            
            # Boshlang'ich sozlamalar
            cursor.execute('''
                INSERT OR IGNORE INTO settings (key, value) VALUES 
                ('monthly_price', '29900'),
                ('quarterly_price', '79900'),
                ('semiannual_price', '149900'),
                ('annual_price', '279900'),
                ('card_number', '8600 1234 5678 9012'),
                ('card_holder', 'SOLEJON ADASHOV ISROILOVICH'),
                ('subscription_days', '30')
            ''')
    
    # ========== USER METHODS ==========
    def add_user(self, user_id, username, full_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, full_name, join_date)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, full_name, datetime.now()))
    
    def get_user(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            return cursor.fetchone()
    
    def update_subscription(self, user_id, days):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            user = self.get_user(user_id)
            if user and user['subscription_end']:
                current_end = datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S')
                new_end = current_end + timedelta(days=days)
            else:
                new_end = datetime.now() + timedelta(days=days)
            
            cursor.execute('''
                UPDATE users 
                SET subscription_end = ?, is_active = 1 
                WHERE user_id = ?
            ''', (new_end, user_id))
    
    def check_subscription(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return False
        
        if user['subscription_end']:
            end_date = datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S')
            return end_date > datetime.now()
        return False
    
    def update_activity(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().date()
            cursor.execute('''
                INSERT INTO user_activity (user_id, activity_date, message_count)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, activity_date) 
                DO UPDATE SET message_count = message_count + 1
            ''', (user_id, today))
            
            cursor.execute('''
                UPDATE users SET last_activity = ? WHERE user_id = ?
            ''', (datetime.now(), user_id))
    
    def get_inactive_users(self, days=3):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cutoff_date = datetime.now() - timedelta(days=days)
            cursor.execute('''
                SELECT user_id FROM users 
                WHERE last_activity < ? AND is_blocked = 0
            ''', (cutoff_date,))
            return [row[0] for row in cursor.fetchall()]
    
    def block_user(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_blocked = 1 WHERE user_id = ?', (user_id,))
    
    # ========== MOVIE METHODS ==========
    def add_movie(self, code, name, description, quality, year, language, rating, file_id, file_type, added_by):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO movies (code, name, description, quality, year, language, rating, file_id, file_type, added_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (code, name, description, quality, year, language, rating, file_id, file_type, added_by))
    
    def get_movie(self, code):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM movies WHERE code = ?', (code,))
            return cursor.fetchone()
    
    def search_movies(self, query):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM movies 
                WHERE code LIKE ? OR name LIKE ? OR description LIKE ?
                LIMIT 10
            ''', (f'%{query}%', f'%{query}%', f'%{query}%'))
            return cursor.fetchall()
    
    def get_all_movies(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM movies ORDER BY added_date DESC')
            return cursor.fetchall()
    
    def delete_movie(self, code):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM movies WHERE code = ?', (code,))
            return cursor.rowcount > 0
    
    def get_next_movie_code(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT code FROM movies ORDER BY code DESC LIMIT 1')
            result = cursor.fetchone()
            if result:
                try:
                    return str(int(result[0]) + 1)
                except:
                    return "1"
            return "1"
    
    # ========== PAYMENT METHODS ==========
    def add_payment(self, user_id, amount, period_days, photo_file_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO payments (user_id, amount, period_days, photo_file_id)
                VALUES (?, ?, ?, ?)
            ''', (user_id, amount, period_days, photo_file_id))
            return cursor.lastrowid
    
    def get_pending_payments(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM payments WHERE status = "pending" ORDER BY created_date DESC')
            return cursor.fetchall()
    
    def update_payment_status(self, payment_id, status, admin_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE payments 
                SET status = ?, admin_id = ?, processed_date = ?
                WHERE id = ?
            ''', (status, admin_id, datetime.now(), payment_id))
    
    # ========== SETTINGS METHODS ==========
    def get_setting(self, key):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def update_setting(self, key, value):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', (key, value))
    
    # ========== ADMIN METHODS ==========
    def add_admin(self, user_id, added_by):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)', (user_id, added_by))
    
    def is_admin(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
            return cursor.fetchone() is not None
    
    def get_all_admins(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM admins')
            return [row[0] for row in cursor.fetchall()]
    
    # ========== STATISTICS METHODS ==========
    def get_statistics(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Jami foydalanuvchilar
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            # Faol obunachilar (subscription tugamagan)
            cursor.execute('''
                SELECT COUNT(*) FROM users 
                WHERE subscription_end > datetime('now') AND is_blocked = 0
            ''')
            active_subscribers = cursor.fetchone()[0]
            
            # Oddiy foydalanuvchilar (subscription yo'q yoki tugagan)
            cursor.execute('''
                SELECT COUNT(*) FROM users 
                WHERE (subscription_end IS NULL OR subscription_end <= datetime('now')) 
                AND is_blocked = 0
            ''')
            regular_users = cursor.fetchone()[0]
            
            # Bloklangan foydalanuvchilar
            cursor.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1')
            blocked_users = cursor.fetchone()[0]
            
            # Kunlik faol foydalanuvchilar
            today = datetime.now().date()
            cursor.execute('SELECT COUNT(DISTINCT user_id) FROM user_activity WHERE activity_date = ?', (today,))
            daily_active = cursor.fetchone()[0]
            
            # Filmlar soni
            cursor.execute('SELECT COUNT(*) FROM movies')
            total_movies = cursor.fetchone()[0]
            
            return {
                'total_users': total_users,
                'active_subscribers': active_subscribers,
                'regular_users': regular_users,
                'blocked_users': blocked_users,
                'daily_active': daily_active,
                'total_movies': total_movies
            }
