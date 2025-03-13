import random
import string
import logging
import re
from database import get_all_users  # Импортируем функцию
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.utils import executor
import time 
from aiogram.dispatcher.filters import Text
import sqlite3
from datetime import datetime
from database import get_user_numbers
logging.basicConfig(level=logging.INFO)
confirmed_numbers = []
rejected_numbers = []
# === 🔧 Настройки ===
TOKEN = "7839128982:AAExgg9qvwNrIO67c2h6An9nwqQnFDYgiGs"  # Укажи свой токен
ADMIN_GROUP_ID = -1002329021975  # ID группы админов
ADMIN_USER_IDS = {8101813488, 987654321}  # Выдача прав админа
WITHDRAW_GROUP_ID = -1002290860098  # ID группы для заявок на вывод
CHANNEL_USERNAME = "@legionWA_Rent"  # ID вашего канала (например, "@your_channel")

def update_statistics():
    current_time = datetime.now()

    # Обновляем статистику каждый 24 часа
    last_update_time = get_last_update_time()

    if last_update_time and current_time - last_update_time < timedelta(days=1):
        return  # Статистика уже обновлялась за последние 24 часа

    # Обновляем время последнего обновления статистики
    execute_query("UPDATE statistics SET last_update_time = ?", (current_time,))
    # Здесь может быть код для обновления статистики по номерам и пользователям
    
def get_user_numbers(user_id, status=None):
    query = "SELECT number, time FROM user_numbers WHERE user_id = ?"
    params = [user_id]

    if status:
        query += " AND status = ?"
        params.append(status)

    return execute_query(query, tuple(params)) or []

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Список пользователей и их балансов
user_balances = {}  # {user_id: balance}
user_numbers = {}   # {номер: {"user_id": id, "msg_id": msg_id, "photo_sent": False, "confirmed": False}}

# База номеров пользователей
user_numbers = {}  # {user_id: [{"number": "79123456789", "time": "12:30:45"}]}

# === Проверка на администратора ===
def is_admin(user_id):
    return user_id in ADMIN_IDS

#Словарь для хранения информации о подписке пользователей
subscribed_users = {}

# Проверка подписки на канал
async def is_subscribed(user_id: int) -> bool:
    try:
        # Проверка, является ли пользователь подписчиком канала
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        # Если статус пользователя "member" или выше, то он подписан
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False
        
#Инициализация базы данных SQLite
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        referral_code TEXT,
        referred_by INTEGER,
        balance REAL DEFAULT 0.0
    )''')
    conn.commit()
    conn.close()
    
#Функция для создания нового пользователя в базе данных
def add_user(user_id, username, referral_code, referred_by=None):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        referral_code TEXT,
        referred_by INTEGER,
        balance REAL DEFAULT 0
    )
    """)
    cursor.execute("INSERT INTO users (user_id, username, referral_code, referred_by) VALUES (?, ?, ?, ?)", 
                   (user_id, username, referral_code, referred_by))
    conn.commit()
    conn.close()

# Функция для получения информации о пользователе по ID
def get_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# Функция для получения пользователя по реферальному коду
def get_user_by_referral_code(referral_code):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE referral_code=?", (referral_code,))
    user = cursor.fetchone()
    conn.close()
    return user

# Функция для обновления баланса пользователя
def update_balance(user_id, amount):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

# Генерация случайного реферального кода
def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
def get_all_users():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

# === 📌 Главное меню ===
# Основное меню
def main_menu():
    menu = InlineKeyboardMarkup(row_width=2)
    menu.add(
        InlineKeyboardButton("📤 Сдать номер", callback_data="submit_number"),
        InlineKeyboardButton("📂 Мои номера", callback_data="my_numbers")
    )
    menu.add(
        InlineKeyboardButton("💰 Вывести", callback_data="withdraw"),
        InlineKeyboardButton("📈 Реферальная система", callback_data="referral_system")  # Эта кнопка
    )
    menu.add(
        InlineKeyboardButton("❓ FAQ", callback_data="faq")  # Кнопка FAQ
    )
    return menu  # Правильный return для меню

#Обработчик старта
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id

    if user_id not in subscribed_users or not subscribed_users[user_id]:
        # Если не подписан, отправляем запрос на подписку
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔗 Подписаться на канал", url=f"https://t.me/legionWA_Rent"))
        keyboard.add(InlineKeyboardButton("🔄 Проверить подписку", callback_data="check_subscription"))
        await message.answer("Для того, чтобы продолжить, подпишитесь на наш канал:", reply_markup=keyboard)
        subscribed_users[user_id] = False
    else:
        # Если подписан, показываем меню
        await message.answer("🚀 Добро пожаловать! Выберите действие:", reply_markup=main_menu())

# Обработчик команды /start с реферальной ссылкой
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    referral_code = message.text.split()[-1]  # Получаем реферальный код
    user_id = message.from_user.id

    # Проверяем, если пользователь перешел по реферальной ссылке
    if referral_code:
        referred_by_user = get_user_by_referral_code(referral_code)
        if referred_by_user:
            add_user(user_id, message.from_user.username, generate_referral_code(), referred_by=referred_by_user[0])
            await message.answer(f"Вы зарегистрированы через реферальную ссылку @{referred_by_user[1]}.")
            await message.answer("Добро пожаловать в систему!")

            # Отчисляем 10% владельцу ссылки
            referral_bonus = 10  # 10% от суммы, которую мы хотим начислить
            update_balance(referred_by_user[0], referral_bonus)

            # Отправляем владельцу ссылки информацию о новом пользователе
            await bot.send_message(referred_by_user[0], f"Получено {referral_bonus} долларов за реферала @{message.from_user.username}!")

        else:
            await message.answer("❌ Неверная реферальная ссылка.")
    else:
        # Если реферальной ссылки нет, то просто генерируем новый код
        referral_code = generate_referral_code()
        add_user(user_id, message.from_user.username, referral_code)
        await message.answer("Привет, добро пожаловать в наш бот! Используйте /referral для получения своей реферальной ссылки.")

@dp.callback_query_handler(lambda c: c.data == "referral_system")
async def referral_system(call: types.CallbackQuery):
    user_id = call.from_user.id

    # Получаем username бота
    bot_username = (await bot.get_me()).username

    if bot_username:
        referral_link = f"https://t.me/{bot_username}?start={user_id}"  # Генерируем ссылку для пользователя
    else:
        referral_link = "Ошибка: имя пользователя бота не настроено."

    # Отправляем пользователю его реферальную ссылку
    await call.message.answer(f"Если вы пригласите своего друга, то будете получать с каждого его отстоявшего номера по 10%. Вот ваша реферальная ссылка: {referral_link}")
    await call.answer()  # Отвечаем на callback, чтобы убрать индикатор загрузки

# === Обработчик проверки подписки ===
@dp.callback_query_handler(lambda c: c.data == "check_subscription")
async def check_subscription(call: types.CallbackQuery):
    user_id = call.from_user.id

    try:
        chat_member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            subscribed_users[user_id] = True
            # Кнопка для начала работы
            start_keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🚀 Начать работу", callback_data="start_work")
            )
            await call.message.answer("✅ Вы подписаны на канал. Теперь можно использовать все функции бота.", reply_markup=start_keyboard)
        else:
            await call.message.answer("❌ Вы не подписаны на канал. Пожалуйста, подпишитесь, чтобы продолжить.")
    except Exception as e:
        await call.message.answer(f"❌ Ошибка при проверке подписки: {e}")

    await call.answer()

# === Обработчик кнопки "🚀 Начать работу" ===
@dp.callback_query_handler(lambda c: c.data == "start_work")
async def open_main_menu(call: types.CallbackQuery):
    await call.message.edit_text("📌 Главное меню:", reply_markup=main_menu())
        
#=== 📤 Сдать номер ===
@dp.callback_query_handler(lambda c: c.data == "submit_number")
async def submit_number(call: types.CallbackQuery):
    # Создаем клавиатуру с кнопкой "Вернуться в главное меню"
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="back_to_main_menu")
    )
    
    # Отправляем сообщение с инструкцией
    await call.message.answer("📲 Введите номер в формате: `+7XXXXXXXXXX`", parse_mode="Markdown", reply_markup=keyboard)
    await call.answer()

@dp.message_handler(lambda message: message.text.startswith("+7"))
async def receive_number(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Без имени"
    number = message.text.strip()

    if number in user_numbers and user_numbers[number].get("confirmed"):
        await message.answer("❌ Этот номер уже подтвержден.")
        return

    # Добавляем номер в user_numbers с флагом, что он еще не подтвержден
    user_numbers[number] = {"user_id": user_id, "confirmed": False}

    admin_message = f"📞 *Новый номер от @{username} (ID: `{user_id}`):*\n📲 `{number}`"

    try:
        msg = await bot.send_message(ADMIN_GROUP_ID, admin_message, parse_mode="Markdown")
        user_numbers[number]["msg_id"] = msg.message_id
        await message.answer("✅ Номер отправлен на проверку администратору.")
    except Exception as e:
        await message.answer("❌ Ошибка отправки номера. Проверь настройки группы.")
        logging.error(f"Ошибка отправки в группу: {e}")
        
#Обработка кнопки "Вернуться в меню"
@dp.callback_query_handler(lambda c: c.data == "back_to_main_menu")
async def back_to_main_menu(call: types.CallbackQuery):
    # Главное меню
    main_menu = InlineKeyboardMarkup(row_width=2)
    main_menu.add(
        InlineKeyboardButton("📤 Сдать номер", callback_data="submit_number"),
        InlineKeyboardButton("📂 Мои номера", callback_data="my_numbers")
    )
    main_menu.add(
        InlineKeyboardButton("💰 Вывести", callback_data="withdraw"),
        InlineKeyboardButton("❓ FAQ", callback_data="faq")
    )
    
    # Отправляем главное меню
    await call.message.answer("Вы вернулись в главное меню:", reply_markup=main_menu)
    await call.answer()

# Пример структуры user_numbers
user_numbers = {}

@dp.callback_query_handler(lambda c: c.data.startswith("code_"))
async def handle_code_confirmation(callback_query: types.CallbackQuery):
    action, number = callback_query.data.split("_")[-2], callback_query.data.split("_")[-1]  # Извлекаем действие и номер

    logging.info(f"Кнопка нажата: {callback_query.data}")
    
    if number not in user_numbers:
        logging.error(f"❌ Ошибка: номер {number} не найден в системе.")
        return await callback_query.answer("❌ Ошибка: номер не найден в системе.")

    user_info = user_numbers[number]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if action == "entered":
        user_info["status"] = "confirmed"
        await callback_query.answer("✅ Код подтвержден.")
        await bot.send_message(user_info["user_id"], "✅ Ваш код был успешно подтвержден.")
        text = f"✅ Код подтвержден!\n📲 Номер: {number}\n⏰ Время: {timestamp}"
    elif action == "not_entered":
        user_info["status"] = "rejected"
        await callback_query.answer("❌ Код не введен.")
        await bot.send_message(user_info["user_id"], "❌ Ваш код не был подтвержден.")
        text = f"❌ Код не введен!\n📲 Номер: {number}\n⏰ Время: {timestamp}"

    user_numbers[number] = user_info

    # Создаем инлайн-кнопку "Пропустить номер"
    skip_button = InlineKeyboardButton("⏭️ Пропустить номер", callback_data=f"skip_{number}")
    skip_keyboard = InlineKeyboardMarkup().add(skip_button)

    # Отправляем сообщение в чат администраторов с кнопкой
    await bot.send_message(ADMIN_GROUP_ID, text, reply_markup=skip_keyboard)

    # Убираем кнопки у пользователя после нажатия
    await callback_query.message.edit_reply_markup()

@dp.callback_query_handler(lambda c: c.data.startswith("skip_"))
async def handle_skip(callback_query: types.CallbackQuery):
    number = callback_query.data.split("_")[-1]

    if number not in user_numbers:
        return await callback_query.answer("❌ Номер не найден в системе.")

    user_info = user_numbers[number]
    user_info["status"] = "skipped"
    
    await bot.send_message(user_info["user_id"], "⚠️ Ваш код был пропущен.")
    await bot.send_message(ADMIN_GROUP_ID, f"📲 Номер {number} был пропущен.")

    user_numbers[number] = user_info
    await callback_query.answer("✅ Номер пропущен.")
    await callback_query.message.edit_reply_markup()  # Убираем кнопку

@dp.message_handler(content_types=["photo"])
async def admin_reply_photo(message: types.Message):
    if not message.reply_to_message or message.chat.id != ADMIN_GROUP_ID:
        return

    text = message.reply_to_message.text or ""
    number = re.search(r"\+7\d{10}", text)

    if not number:
        await message.reply("❌ Ошибка: номер не найден в сообщении.")
        return

    number = number.group(0)

    if number not in user_numbers:
        user_numbers[number] = {"user_id": message.from_user.id, "status": "pending"}

    user_id = user_numbers[number]["user_id"]

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Код введен", callback_data=f"code_entered_{number}"),
        InlineKeyboardButton("❌ Код не введен", callback_data=f"code_not_entered_{number}")
    )

    try:
        photo = message.photo[-1].file_id
        msg = await bot.send_photo(user_id, photo=photo, caption="🔑 Введите полученный код:", reply_markup=keyboard)

        user_numbers[number]["msg_id"] = msg.message_id
        user_numbers[number]["photo_sent"] = True

        await message.reply("✅ Код отправлен пользователю.")
    except Exception as e:
        logging.exception(f"Ошибка отправки фото пользователю: {e}")
        await message.reply("❌ Ошибка отправки фото пользователю.")
        
# Обработка ответа от администратора, когда он отправляет результат (например, "-1" или "+50")
@dp.message_handler(lambda message: message.text.startswith(("-", "+")))
async def handle_admin_code_input(message: types.Message):
    text = message.text.strip()

    # Проверяем, что текст начинается с "-" или "+"
    if not text[1:].isdigit() and (text[0] not in ["-", "+"]):
        await message.reply("❌ Ошибка: Неверный формат сообщения.")
        return
    
    # Извлекаем номер из текста ответа администратора
    number = None
    if message.reply_to_message:
        match = re.search(r"\+7\d{10}", message.reply_to_message.text or "")
        if match:
            number = match.group(0)
    
    if number is None:
        await message.reply("❌ Ошибка: Номер не найден в ответе администратора.")
        return

    if number not in user_numbers:
        await message.reply(f"❌ Ошибка: номер {number} не найден.")
        return

    # Обрабатываем результаты
    if text.startswith("-"):
        # Слетевший номер
        user_id = user_numbers[number]["user_id"]
        await bot.send_message(user_id, f"❌ Номер {number} слетел, код не введен.")
        await bot.send_message(ADMIN_GROUP_ID, f"❌ Номер {number} слетел.")
        del user_numbers[number]
    elif text.startswith("+") and user_numbers[number].get("confirmed"):
        # Если номер подтвержден, то добавляем в мои номера
        amount = float(text[1:])  # Сумма в долларах
        user_id = user_numbers[number]["user_id"]
        
        # Добавляем сумму на баланс пользователя в долларах
        if user_id not in user_balances:
            user_balances[user_id] = 0.0
        user_balances[user_id] += amount

        await bot.send_message(user_id, f"✅ Номер {number} отстоял. Вам начислено {amount} USD.")
        await bot.send_message(ADMIN_GROUP_ID, f"✅ Номер {number} отстоял. Пользователю @{user_id} начислено {amount} USD.")

        # Удаляем номер после обработки
        del user_numbers[number]

# === 📂 Мои номера ===
@dp.callback_query_handler(lambda c: c.data == "my_numbers")
async def my_numbers(call: types.CallbackQuery):
    user_id = call.from_user.id

    # Получаем подтвержденные и слетевшие номера для пользователя
    confirmed_numbers = get_user_numbers(user_id, status="confirmed")
    dropped_numbers = get_user_numbers(user_id, status="dropped")

    message_text = "📂 **Ваши номера:**\n\n"

    # Подтвержденные номера
    if confirmed_numbers:
        message_text += "✅ Подтвержденные номера:\n" + "\n".join(
            [f"📞 {num[0]} - 🕒 {num[1]}" for num in confirmed_numbers]
        ) + "\n\n"
    else:
        message_text += "✅ У вас нет подтвержденных номеров.\n\n"

    # Слетевшие номера
    if dropped_numbers:
        message_text += "⚠️ Слетевшие номера:\n" + "\n".join(
            [f"❌ {num[0]} - 🕒 {num[1]}" for num in dropped_numbers]
        ) + "\n\n"
    else:
        message_text += "❌ У вас нет слетевших номеров.\n\n"

    # Статистика
    total_confirmed = len(confirmed_numbers)
    total_dropped = len(dropped_numbers)

    message_text += f"📊 **Статистика:**\n"
    message_text += f"✅ Подтвержденных номеров: {total_confirmed}\n"
    message_text += f"❌ Слетевших номеров: {total_dropped}"

    # Отправляем сообщение
    await call.message.answer(message_text)

    # Создаем кнопку для возврата в главное меню
    back_to_main_menu = InlineKeyboardMarkup()
    back_to_main_menu.add(InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="back_to_main_menu"))

    # Отправляем кнопку
    await call.message.answer("Выберите действие:", reply_markup=back_to_main_menu)

    # Здесь выполняется запрос к базе данных с учетом параметров
    # Вернуть список номеров с временем
    result = execute_query(query, params)
    return result

async def update_statistics_task():
    while True:
        update_statistics()  # Обновляем статистику
        await asyncio.sleep(86400)  # Задержка 24 часа

@dp.callback_query_handler(lambda c: c.data.startswith("code_entered_"))
async def handle_code_confirmation(callback_query: types.CallbackQuery):
    number = callback_query.data.split("_")[-1]

    # Сохраняем номер в БД
    save_confirmed_number(number)

    # Отправляем уведомление пользователю
    await bot.send_message(callback_query.from_user.id, f"✅ Ваш номер {number} подтвержден и сохранен!")

    # Обновляем статистику в админ-панели
    await admin_list(callback_query)

    await callback_query.answer("✅ Номер успешно записан!")

    # Создаем инлайн кнопку "Вернуться в меню"
    back_to_main_menu = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="back_to_main_menu")
    )

    await call.message.answer(message_text, parse_mode="Markdown", reply_markup=back_to_main_menu)

#=== 💰 Вывести средства ===
@dp.callback_query_handler(lambda c: c.data == "withdraw")
async def withdraw_request(call: types.CallbackQuery):
    user_id = call.from_user.id
    balance = user_balances.get(user_id, 0)

    if balance <= 0:
        await call.message.answer("❌ У вас нет средств на вывод.")
        return

    # Отправляем информацию о балансе
    await call.message.answer(f"💸 Ваш текущий баланс: {balance} USD.")

    # Создаем инлайн кнопку "Вернуться в главное меню"
    back_to_main_menu = InlineKeyboardMarkup()
    back_to_main_menu.add(InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="back_to_main_menu"))

    # Запрос суммы для вывода
    await call.message.answer("💰 Введите сумму для вывода в долларах:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Отменить", callback_data="cancel_withdraw")))

# Обработчик для ввода суммы для вывода
@dp.message_handler(lambda message: message.text.replace('.', '', 1).isdigit())
async def handle_withdraw_amount(message: types.Message):
    user_id = message.from_user.id
    balance = user_balances.get(user_id, 0)
    amount = float(message.text)

    if amount > balance:
        await message.answer("❌ У вас недостаточно средств для вывода.")
        return

    if amount <= 0:
        await message.answer("❌ Сумма вывода должна быть положительной.")
        return

    # Обновление баланса пользователя
    user_balances[user_id] -= amount

    # Отправляем заявку на вывод в группу администраторов
    await bot.send_message(WITHDRAW_GROUP_ID, f"💰 @{message.from_user.username} (ID: {user_id}) хочет вывести {amount} USD.")
    await message.answer(f"✅ Запрос на вывод {amount} USD отправлен на проверку.")

# === ❓ FAQ ===
@dp.callback_query_handler(lambda c: c.data == "faq")
async def faq(call: types.CallbackQuery):
    faq_text = """**❓ FAQ ❓**
1️⃣ Мы не несем ответственность за аккаунты.  
2️⃣ В случае скама офиса, выплаты не гарантируются.  
3️⃣ Если номер отстоял 59 мин вместо 1 часа — оплаты не будет.  
4️⃣ Выплаты в течение 7 дней.  
5️⃣ Постоянный «Скип» может привести к блокировке.  
6️⃣ Принимаются только РФ номера 6+ месяцев.  
7️⃣ Администрация имеет право исключить вас без объяснений."""
    
    # Создаем инлайн кнопку "Вернуться в главное меню"
    back_to_main_menu = InlineKeyboardMarkup()
    back_to_main_menu.add(InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="back_to_main_menu"))
    
    # Отправляем FAQ с кнопкой "Вернуться в меню"
    await call.message.answer(faq_text, parse_mode="Markdown", reply_markup=back_to_main_menu)
    await call.answer()
    
@dp.message_handler(commands=["broadcast"])
async def start_broadcast(message: types.Message):
    if message.from_user.id not in ADMIN_USER_IDS:
        return await message.answer("❌ У вас нет прав для рассылки.")
    
    await message.answer("Введите текст для рассылки:")
    await dp.current_state(user=message.from_user.id).set_state("waiting_for_broadcast")

@dp.message_handler(state="waiting_for_broadcast")
async def send_broadcast(message: types.Message, state):
    text = message.text
    users = get_all_users()

    sent_count = 0
    failed_count = 0

    for user_id in users:
        try:
            await bot.send_message(user_id, text)
            sent_count += 1
            await asyncio.sleep(0.5)  # Антиспам-задержка
        except Exception:
            failed_count += 1

    await message.answer(f"✅ Рассылка завершена! Отправлено: {sent_count}, Ошибок: {failed_count}.")
    await state.finish()
    
# Убедитесь, что эта функция не принимает никаких аргументов
def admin_panel():
    menu = InlineKeyboardMarkup(row_width=2)
    menu.add(
        InlineKeyboardButton("📊 Общая статистика", callback_data="admin_stats"),
        InlineKeyboardButton("📜 Список", callback_data="admin_list"),  # список
        #InlineKeyboardButton("📤 Сдать номер", callback_data="submit_number"),
        #InlineKeyboardButton("💰 Вывести", callback_data="withdraw")
    )
    return menu

 #Функция для получения ТОЛЬКО подтвержденных номеров
def get_confirmed_numbers():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT number, time FROM confirmed_numbers")  
    numbers = cursor.fetchall()
    conn.close()
    return numbers if numbers else []

# Обработчик кнопки "📜 Список"
@dp.callback_query_handler(lambda c: c.data == "admin_list")
async def admin_list(call: types.CallbackQuery):
    confirmed_numbers = get_confirmed_numbers()  # Получаем подтвержденные номера

    if not confirmed_numbers:
        await call.message.answer("⚠️ Подтвержденных номеров нет.")
        await call.answer()
        return

    # Формируем список номеров
    list_text = "📜 **Список подтвержденных номеров:**\n\n"
    list_text += "\n".join([f"📞 {num[0]} - 🕒 {num[1]}" for num in confirmed_numbers])

    # Отправляем список
    await call.message.answer(list_text, parse_mode="Markdown")
    await call.answer()

# Обработчик команды /admin
@dp.message_handler(commands=['admin'])
async def admin_menu(message: types.Message):
    # Проверка на доступ
    if message.from_user.id not in ADMIN_USER_IDS:
        return await message.answer("❌ У вас нет доступа к админ-панели.")
    
    # Передаем клавиатуру в ответ
    await message.answer("🔧 Админ-панель:", reply_markup=admin_panel())

# Обработчик для кнопки "Общая статистика"
@dp.callback_query_handler(lambda c: c.data == "admin_stats")
async def admin_stats(call: types.CallbackQuery):
    # Получаем статистику из базы данных
    confirmed_numbers = get_confirmed_numbers()
    rejected_numbers = get_rejected_numbers()
    total_users = get_all_users_count()
    total_balance = get_total_balance()

    # Логируем полученные данные
    logging.info(f"✅ Подтвержденные номера: {confirmed_numbers}")
    logging.info(f"❌ Отклоненные номера: {rejected_numbers}")
    logging.info(f"👥 Количество пользователей: {total_users}")
    logging.info(f"💰 Общий баланс: {total_balance}")

    # Формируем текст статистики
    stats_text = """📊 **Общая статистика**
✅ Подтвержденные номера: {confirmed}
{confirmed_list}

❌ Отклоненные номера: {rejected}
{rejected_list}

👥 Общее количество пользователей: {users}
💰 Общий баланс пользователей: {balance} USD
""".format(
        confirmed=len(confirmed_numbers),
        confirmed_list="\n".join([f"📞 {num[0]} - 🕒 {num[1]}" for num in confirmed_numbers]) if confirmed_numbers else "—",
        rejected=len(rejected_numbers),
        rejected_list="\n".join([f"❌ {num[0]} - 🕒 {num[1]}" for num in rejected_numbers]) if rejected_numbers else "—",
        users=total_users,
        balance=total_balance
    )

    # Отправка обновленной статистики
    await call.message.edit_text(stats_text, parse_mode="Markdown", reply_markup=admin_panel())
    await call.answer()
# === 📂 Мои номера ===
@dp.callback_query_handler(lambda c: c.data == "my_numbers")
async def my_numbers(call: types.CallbackQuery):
    user_id = call.from_user.id

    # Получаем подтвержденные и слетевшие номера для пользователя
    confirmed_numbers = get_user_numbers(user_id, status="confirmed")
    rejected_numbers = get_user_numbers(user_id, status="rejected")

    message_text = "📂 **Ваши номера:**\n\n"

    # Подтвержденные номера
    if confirmed_numbers:
        message_text += "✅ Подтвержденные номера:\n" + "\n".join(
            [f"📞 {num[0]} - 🕒 {num[1]}" for num in confirmed_numbers]
        ) + "\n\n"
    else:
        message_text += "✅ У вас нет подтвержденных номеров.\n\n"

    # Отклоненные номера
    if rejected_numbers:
        message_text += "⚠️ Отклоненные номера:\n" + "\n".join(
            [f"❌ {num[0]} - 🕒 {num[1]}" for num in rejected_numbers]
        ) + "\n\n"
    else:
        message_text += "❌ У вас нет отклоненных номеров.\n\n"

    # Статистика
    total_confirmed = len(confirmed_numbers)
    total_rejected = len(rejected_numbers)

    message_text += f"📊 **Статистика:**\n"
    message_text += f"✅ Подтвержденных номеров: {total_confirmed}\n"
    message_text += f"❌ Отклоненных номеров: {total_rejected}"

    # Отправляем сообщение
    await call.message.answer(message_text)

    # Кнопка "Вернуться в главное меню"
    back_to_main_menu = InlineKeyboardMarkup()
    back_to_main_menu.add(InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="back_to_main_menu"))

    await call.message.answer("Выберите действие:", reply_markup=back_to_main_menu)
    await call.answer()

# Функция для добавления пользователя в базу данных
def add_user(user_id, username, referral_code=None, referred_by=None):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (user_id, username, referral_code, referred_by) VALUES (?, ?, ?, ?)",
                   (user_id, username, referral_code, referred_by))
    conn.commit()
    conn.close()
    
# Функция для получения информации о пользователе
def get_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user
    
# Функция для обновления баланса пользователя
def update_balance(user_id, amount):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    
# Главная кнопка меню с реферальной ссылкой
@dp.callback_query_handler(lambda c: c.data == "referral_link")
async def referral_link(call: types.CallbackQuery):
    user_id = call.from_user.id
    user = get_user(user_id)
    
    if not user:
        # Если пользователь еще не зарегистрирован в базе, то добавляем его
        referral_code = generate_referral_code()
        add_user(user_id, call.from_user.username, referral_code)
    
    referral_url = f"t.me/{BOT_USERNAME}?start={user[2]}"  # Пример реферальной ссылки
    await call.message.answer(f"Ваша реферальная ссылка: {referral_url}")
    
    await call.answer()

from datetime import datetime
import sqlite3

@dp.callback_query_handler(lambda c: c.data.startswith("code_entered_") or c.data.startswith("code_not_entered_"))
async def handle_code_confirmation(callback_query: types.CallbackQuery):
    number = callback_query.data.split("_")[-1]
    user_id = user_numbers.get(number, {}).get("user_id")

    if not user_id:
        return await callback_query.answer("Ошибка: номер не найден!")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if callback_query.data.startswith("code_entered_"):
        save_confirmed_number(number, now)
        text = f"✅ Номер {number} подтверждён в {now}!"
    else:
        save_rejected_number(number, now)
        text = f"❌ Номер {number} отклонён в {now}!"

    save_user(user_id)

    # Отправка сообщения в админ-чат с кнопками
    admin_keyboard = InlineKeyboardMarkup().row(
        InlineKeyboardButton("📩 Взять номер", callback_data=f"take_{number}"),
        InlineKeyboardButton("⏭ Пропустить номер", callback_data=f"skip_{number}")
    )

    await bot.send_message(ADMIN_GROUP_ID, text, reply_markup=admin_keyboard)
    await callback_query.answer("✅ Данные сохранены и статистика обновлена!")

# === 🔥 Запуск бота ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=False)