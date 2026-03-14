import sqlite3

def init_db():
    """Создаёт таблицу цитат, если её нет"""
    with sqlite3.connect("quotes.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL
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