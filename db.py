import sqlite3
import logging
import os
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path=None):
        # Render uchun to'g'ri yo'lni aniqlash
        if db_path:
            self.db_path = db_path
        elif 'RENDER' in os.environ:
            self.db_path = '/tmp/database.db'
        else:
            self.db_path = 'database.db'
        
        logger.info(f"Database fayl yo'li: {self.db_path}")
        
        # Fayl yo'lini yaratish
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        self.init_db()
        self.test_connection()
    
    def test_connection(self):
        """Baza bilan ulanishni test qilish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                logger.info(f"Bazadagi jadvallar: {[table[0] for table in tables]}")
                return True
        except Exception as e:
            logger.error(f"Baza testida xato: {e}")
            return False
    
    @contextmanager
    def get_connection(self):
        """Bazaga ulanishni olish"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Bazada xato: {e}")
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
            
            logger.info("Baza jadvallari yaratildi/yuklandi")
    
    # ========== USER METHODS ==========
    def add_user(self, user_id, username, full_name):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO users (user_id, username, full_name, join_date)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, username, full_name, datetime.now()))
                logger.info(f"Foydalanuvchi qo'shildi/yuklandi: {user_id} - {username}")
                return True
        except Exception as e:
            logger.error(f"Foydalanuvchi qo'shishda xato: {e}")
            return False
    
    def get_user(self, user_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Foydalanuvchi olishda xato: {e}")
            return None
    
    def update_subscription(self, user_id, days):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                user = self.get_user(user_id)
                if user and user.get('subscription_end'):
                    current_end = datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S')
                    new_end = current_end + timedelta(days=days)
                else:
                    new_end = datetime.now() + timedelta(days=days)
                
                cursor.execute('''
                    UPDATE users 
                    SET subscription_end = ?, is_active = 1 
                    WHERE user_id = ?
                ''', (new_end, user_id))
                logger.info(f"Obuna yangilandi: {user_id} - {days} kun")
                return True
        except Exception as e:
            logger.error(f"Obuna yangilashda xato: {e}")
            return False
    
    def check_subscription(self, user_id):
        try:
            user = self.get_user(user_id)
            if not user:
                return False
            
            if user.get('subscription_end'):
                end_date = datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S')
                return end_date > datetime.now()
            return False
        except Exception as e:
            logger.error(f"Obuna tekshirishda xato: {e}")
            return False
    
    def update_activity(self, user_id):
        try:
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
                return True
        except Exception as e:
            logger.error(f"Aktivlik yangilashda xato: {e}")
            return False
    
    def get_inactive_users(self, days=3):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cutoff_date = datetime.now() - timedelta(days=days)
                cursor.execute('''
                    SELECT user_id FROM users 
                    WHERE last_activity < ? AND is_blocked = 0
                ''', (cutoff_date,))
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Inaktiv foydalanuvchilarni olishda xato: {e}")
            return []
    
    def block_user(self, user_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET is_blocked = 1 WHERE user_id = ?', (user_id,))
                logger.info(f"Foydalanuvchi bloklandi: {user_id}")
                return True
        except Exception as e:
            logger.error(f"Foydalanuvchini bloklashda xato: {e}")
            return False
    
    # ========== MOVIE METHODS ==========
    def add_movie(self, code, name, description, quality, year, language, rating, file_id, file_type, added_by):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO movies (code, name, description, quality, year, language, rating, file_id, file_type, added_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (code, name, description, quality, year, language, rating, file_id, file_type, added_by))
                logger.info(f"Kino qo'shildi: {code} - {name}")
                return True
        except Exception as e:
            logger.error(f"Kino qo'shishda xato: {e}")
            return False
    
    def get_movie(self, code):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM movies WHERE code = ?', (code,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Kino olishda xato: {e}")
            return None
    
    def search_movies(self, query):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM movies 
                    WHERE code LIKE ? OR name LIKE ? OR description LIKE ?
                    LIMIT 10
                ''', (f'%{query}%', f'%{query}%', f'%{query}%'))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Kino qidirishda xato: {e}")
            return []
    
    def get_all_movies(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM movies ORDER BY added_date DESC')
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Barcha kinolarni olishda xato: {e}")
            return []
    
    def delete_movie(self, code):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM movies WHERE code = ?', (code,))
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Kino o'chirildi: {code}")
                return deleted
        except Exception as e:
            logger.error(f"Kino o'chirishda xato: {e}")
            return False
    
    def get_next_movie_code(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT code FROM movies ORDER BY code DESC LIMIT 1')
                result = cursor.fetchone()
                if result:
                    try:
                        return str(int(result['code']) + 1)
                    except:
                        return "1"
                return "1"
        except Exception as e:
            logger.error(f"Keyingi kino kodini olishda xato: {e}")
            return "1"
    
    # ========== PAYMENT METHODS ==========
    def add_payment(self, user_id, amount, period_days, photo_file_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO payments (user_id, amount, period_days, photo_file_id)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, amount, period_days, photo_file_id))
                payment_id = cursor.lastrowid
                logger.info(f"To'lov qo'shildi: ID={payment_id}, user={user_id}")
                return payment_id
        except Exception as e:
            logger.error(f"To'lov qo'shishda xato: {e}")
            return None
    
    def get_pending_payments(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM payments WHERE status = "pending" ORDER BY created_date DESC')
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Kutilayotgan to'lovlarni olishda xato: {e}")
            return []
    
    def update_payment_status(self, payment_id, status, admin_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE payments 
                    SET status = ?, admin_id = ?, processed_date = ?
                    WHERE id = ?
                ''', (status, admin_id, datetime.now(), payment_id))
                logger.info(f"To'lov holati yangilandi: ID={payment_id}, status={status}")
                return True
        except Exception as e:
            logger.error(f"To'lov holatini yangilashda xato: {e}")
            return False
    
    # ========== SETTINGS METHODS ==========
    def get_setting(self, key):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
                result = cursor.fetchone()
                return result['value'] if result else None
        except Exception as e:
            logger.error(f"Sozlama olishda xato: {e}")
            return None
    
    def update_setting(self, key, value):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
                ''', (key, value))
                logger.info(f"Sozlama yangilandi: {key}={value}")
                return True
        except Exception as e:
            logger.error(f"Sozlamani yangilashda xato: {e}")
            return False
    
    # ========== ADMIN METHODS ==========
    def add_admin(self, user_id, added_by):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)', (user_id, added_by))
                logger.info(f"Admin qo'shildi: {user_id}")
                return True
        except Exception as e:
            logger.error(f"Admin qo'shishda xato: {e}")
            return False
    
    def is_admin(self, user_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Admin tekshirishda xato: {e}")
            return False
    
    def get_all_admins(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM admins')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Adminlarni olishda xato: {e}")
            return []
    
    # ========== STATISTICS METHODS ==========
    def get_statistics(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Jami foydalanuvchilar
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
                
                # Faol obunachilar
                cursor.execute('''
                    SELECT COUNT(*) FROM users 
                    WHERE subscription_end > datetime('now') AND is_blocked = 0
                ''')
                active_subscribers = cursor.fetchone()[0]
                
                # Oddiy foydalanuvchilar
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
        except Exception as e:
            logger.error(f"Statistika olishda xato: {e}")
            return {
                'total_users': 0,
                'active_subscribers': 0,
                'regular_users': 0,
                'blocked_users': 0,
                'daily_active': 0,
                'total_movies': 0
            }
    
    def get_db_info(self):
        """Baza haqida ma'lumot"""
        try:
            if not os.path.exists(self.db_path):
                return {
                    'exists': False,
                    'size': 0,
                    'path': self.db_path
                }
            
            size = os.path.getsize(self.db_path)
            return {
                'exists': True,
                'size': size,
                'path': self.db_path,
                'tables': self.get_table_counts()
            }
        except Exception as e:
            logger.error(f"DB info olishda xato: {e}")
            return {
                'exists': False,
                'size': 0,
                'path': self.db_path
            }
    
    def get_table_counts(self):
        """Har bir jadvaldagi yozuvlar soni"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                counts = {}
                for table in tables:
                    cursor.execute(f'SELECT COUNT(*) FROM {table}')
                    counts[table] = cursor.fetchone()[0]
                
                return counts
        except Exception as e:
            logger.error(f"Jadval sonlarini olishda xato: {e}")
            return {}
