import sqlite3
import time 

def execute_query(query, params=()):
    conn = sqlite3.connect('your_database.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(query, params)
        conn.commit()
        if query.strip().upper().startswith('SELECT'):
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

    return None

# Функция для сохранения статуса номера (подтвержден или слетел)
def save_number_status(user_id, number, status, time):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_numbers (user_id, number, status, time) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(number) DO UPDATE SET status = ?, time = ?",
        (user_id, number, status, time, status, time)
    )
    conn.commit()
    conn.close()

# Функция для получения номеров пользователя по статусу

def get_user_numbers(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT number, status, timestamp FROM user_numbers WHERE user_id = ?", (user_id,))
    numbers = cursor.fetchall()
    conn.close()
    return numbers  # [(номер, статус, время), ...]

def execute_query(query, params=()):
    # Подключаемся к базе данных
    conn = sqlite3.connect('your_database.db')
    cursor = conn.cursor()
    
    try:
        # Выполняем запрос
        cursor.execute(query, params)
        conn.commit()
        # Если запрос типа SELECT, возвращаем результат
        if query.strip().upper().startswith('SELECT'):
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

    return None

# Функция для регистрации пользователя
def save_user(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

# Получение списка подтверждённых номеров
def get_confirmed_numbers():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT number, time FROM confirmed_numbers")
    data = cursor.fetchall()
    conn.close()
    return data

# Получение списка отклонённых номеров
def get_rejected_numbers():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT number, time FROM rejected_numbers")
    data = cursor.fetchall()
    conn.close()
    return data

def get_all_users():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_numbers")
    total_users = cursor.fetchone()[0]
    conn.close()
    return total_users

# Получение количества зарегистрированных пользователей
def get_all_users_count():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

# Получение общего баланса всех пользователей
def get_total_balance():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(balance) FROM users")
    balance = cursor.fetchone()[0] or 0
    conn.close()
    return balance