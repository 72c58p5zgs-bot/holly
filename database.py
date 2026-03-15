import sqlite3
from datetime import datetime, timedelta


def init_db():
    """Создаёт таблицы, если их нет"""
    with sqlite3.connect("quotes.db") as conn:
        cursor = conn.cursor()
        # Таблица цитат
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL
            )
        """)
        # Таблица отправленных сообщений
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_messages (
                message_id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                date TEXT  -- формат: YYYY-MM-DD
            )
        """)
        conn.commit()


def add_quote(text):
    """Добавляет новую цитату"""
    with sqlite3.connect("quotes.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO quotes (text) VALUES (?)", (text,))
        conn.commit()


def get_random_quote():
    """Возвращает случайную цитату"""
    with sqlite3.connect("quotes.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM quotes ORDER BY RANDOM() LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else "Цитата не найдена."


def get_all_quotes():
    """Возвращает список всех цитат"""
    with sqlite3.connect("quotes.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM quotes")
        return [row[0] for row in cursor.fetchall()]


def add_sent_message(message_id: int, chat_id: int):
    """Сохраняет ID сообщения и дату отправки"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect("quotes.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO sent_messages (message_id, chat_id, date)
            VALUES (?, ?, ?)
        """, (message_id, chat_id, date_str))
        conn.commit()


def get_messages_for_date(chat_id: int, target_date: str):
    """Получает все message_id, отправленные в указанную дату"""
    with sqlite3.connect("quotes.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT message_id FROM sent_messages
            WHERE chat_id = ? AND date = ?
        """, (chat_id, target_date))
        return [row[0] for row in cursor.fetchall()]


def clear_old_records():
    """Удаляет записи старше 7 дней для чистоты БД"""
    cutoff_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    with sqlite3.connect("quotes.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sent_messages WHERE date < ?", (cutoff_date,))
        conn.commit()
