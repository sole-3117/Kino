import sqlite3
from datetime import datetime

DB_NAME = "database.db"


def connect():
    return sqlite3.connect(DB_NAME)


def init_db():
    with connect() as db:
        c = db.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            join_date TEXT
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            file_id TEXT
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)

        db.commit()


def add_user(user_id, username):
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO users VALUES (?, ?, ?)",
            (user_id, username, datetime.now().isoformat())
        )
        db.commit()


def users_count():
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def add_movie(code, title, description, file_id):
    with connect() as db:
        db.execute(
            "INSERT INTO movies VALUES (?, ?, ?, ?)",
            (code, title, description, file_id)
        )
        db.commit()


def get_movie(code):
    with connect() as db:
        return db.execute(
            "SELECT * FROM movies WHERE code=?",
            (code,)
        ).fetchone()


def search_movie(query):
    with connect() as db:
        return db.execute(
            "SELECT code, title FROM movies WHERE title LIKE ?",
            (f"%{query}%",)
        ).fetchall()


def delete_movie(code):
    with connect() as db:
        db.execute("DELETE FROM movies WHERE code=?", (code,))
        db.commit()


def set_setting(key, value):
    with connect() as db:
        db.execute(
            "INSERT OR REPLACE INTO settings VALUES (?, ?)",
            (key, value)
        )
        db.commit()


def get_setting(key):
    with connect() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,)
        ).fetchone()
        return row[0] if row else None