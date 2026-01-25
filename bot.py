import asyncio
import sqlite3
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging
import os
# Добавь эти импорты в самое начало
from flask import Flask
from threading import Thread
import time

# Создаем Flask приложение для keep-alive
app = Flask('')

@app.route('/')
def home():
    return "Бот работает! 🚀"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# Настройки бота
TOKEN = "8005337864:AAGmI78aZNxvJqMyW9nkP4JoMDEFR4xB4tc"
ADMIN_ID = 1989613788
SUPPORT_USERNAME = "@ownsuicude"

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Подключение к базе данных
conn = sqlite3.connect('onegifts.db', check_same_thread=False, isolation_level=None)
cursor = conn.cursor()

# Создание таблиц
def init_db():
    # Проверяем, существует ли база данных
    db_exists = os.path.exists('onegifts.db')

    if db_exists:
        logger.info("База данных существует, проверяем структуру...")

        # Проверяем наличие поля status в таблице user_gifts
        try:
            cursor.execute("PRAGMA table_info(user_gifts)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'status' not in columns:
                logger.info("Добавляем поле status в таблицу user_gifts...")
                cursor.execute('ALTER TABLE user_gifts ADD COLUMN status TEXT DEFAULT "active"')
                conn.commit()
        except sqlite3.OperationalError:
            # Таблица не существует, создаем заново
            logger.info("Таблица user_gifts не существует, создаем...")
            db_exists = False

    if not db_exists:
        logger.info("Создаем новую базу данных с правильной структурой...")

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        stars INTEGER DEFAULT 0,
        free_gift_used INTEGER DEFAULT 0,
        last_free_gift_date TEXT,
        total_opened INTEGER DEFAULT 0,
        nft_won INTEGER DEFAULT 0,
        registered_date TEXT DEFAULT CURRENT_TIMESTAMP,
        gifts_won INTEGER DEFAULT 0,
        nft_cells_opened INTEGER DEFAULT 0,
        deposit_total INTEGER DEFAULT 0
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        amount INTEGER,
        type TEXT,
        timestamp TEXT,
        admin_id INTEGER DEFAULT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS wins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        prize_type TEXT,
        prize_value TEXT,
        chance REAL,
        timestamp TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_gifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        gift_name TEXT,
        gift_emoji TEXT,
        gift_value INTEGER,
        timestamp TEXT,
        status TEXT DEFAULT 'active'
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        amount INTEGER,
        status TEXT DEFAULT 'pending',
        timestamp TEXT,
        screenshot_id TEXT DEFAULT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS nft_cells (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        cell_type INTEGER,
        cost INTEGER,
        chance REAL,
        result BOOLEAN,
        timestamp TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS withdrawal_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        gift_name TEXT,
        gift_emoji TEXT,
        gift_value INTEGER,
        status TEXT DEFAULT 'pending',
        timestamp TEXT,
        support_username TEXT
    )
    ''')

    conn.commit()
    logger.info("База данных инициализирована")

# Шансы выигрыша для обычных подарков
PRIZE_CHANCES = {
    "1 звезда": 40.0,
    "3 звезды": 25.0,
    "5 звезд": 15.0,
    "10 звезд": 10.0,
    "50 звезд": 5.0,
    "100 звезд": 3.0,
    "500 звезд": 1.5,
    "NFT": 0.001,
    "Проигрыш": 0.499
}

PRIZE_VALUES = {
    "1 звезда": 1,
    "3 звезды": 3,
    "5 звезд": 5,
    "10 звезд": 10,
    "50 звезд": 50,
    "100 звезд": 100,
    "500 звезд": 500,
    "NFT": 1000,
    "Проигрыш": 0
}

# Шансы для ежедневного подарка (только NFT)
DAILY_GIFT_CHANCES = {
    "NFT": 100.0  # Только NFT в ежедневном подарке
}

# Подарки в виде ячеек рулетки - ИЗМЕНЕНЫ ШАНСЫ: реальный 25%, визуальный 40%
GIFTS_CELLS = [
    {"name": "Алмаз", "emoji": "💎", "cell_emoji": "💎💎", "cost": 45, "chance_display": 40, "chance_real": 25},
    {"name": "Кубок", "emoji": "🏆", "cell_emoji": "🏆🏆", "cost": 45, "chance_display": 40, "chance_real": 25},
    {"name": "Ракета", "emoji": "🚀", "cell_emoji": "🚀🚀", "cost": 25, "chance_display": 40, "chance_real": 25},
    {"name": "Шампанское", "emoji": "🍾", "cell_emoji": "🍾🍾", "cost": 25, "chance_display": 40, "chance_real": 25},
    {"name": "Торт", "emoji": "🎂", "cell_emoji": "🎂🎂", "cost": 25, "chance_display": 40, "chance_real": 25},
    {"name": "Розы", "emoji": "🌹", "cell_emoji": "🌹🌹", "cost": 12, "chance_display": 40, "chance_real": 25},
    {"name": "Подарок", "emoji": "🎁", "cell_emoji": "🎁🎁", "cost": 12, "chance_display": 40, "chance_real": 25},
    {"name": "Сердечко", "emoji": "💖", "cell_emoji": "💖💖", "cost": 12, "chance_display": 40, "chance_real": 25},
    {"name": "Мишка", "emoji": "🧸", "cell_emoji": "🧸🧸", "cost": 8, "chance_display": 40, "chance_real": 25}
]

# NFT ячейки
NFT_CELLS = [
    {"cell": 1, "cost": 80, "chance": 1.0, "description": "1% шанс"},
    {"cell": 2, "cost": 100, "chance": 10.0, "description": "10% шанс"},
    {"cell": 3, "cost": 250, "chance": 45.0, "description": "45% шанс"}
]

# Вспомогательная функция для получения клавиатуры главного меню
def get_main_menu_keyboard(user_id):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🎁 Открыть подарочек", callback_data="open_gift"),
        InlineKeyboardButton(text="⭐ Мои звёзды", callback_data="my_stars")
    )
    keyboard.row(
        InlineKeyboardButton(text="🎁 Бесплатный NFT подарок", callback_data="free_nft_gift"),
        InlineKeyboardButton(text="🎁 Подарки", callback_data="gifts_section")
    )
    keyboard.row(
        InlineKeyboardButton(text="💎 NFT ячейки", callback_data="nft_cells"),
        InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory")
    )
    keyboard.row(
        InlineKeyboardButton(text="💰 Депозит", callback_data="deposit"),
        InlineKeyboardButton(text="🛟 Поддержка", callback_data="support")
    )

    if user_id == ADMIN_ID:
        keyboard.row(InlineKeyboardButton(text="👑 Админ панель", callback_data="admin_panel"))

    return keyboard.as_markup()

# ========== ОБРАБОТЧИКИ КОМАНД ==========

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"Команда /start от пользователя {message.from_user.id}")

    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Пользователь"

    try:
        # Регистрация пользователя
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name) 
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))

        # Обновление username если изменился
        cursor.execute('''
            UPDATE users SET username = ?, first_name = ? 
            WHERE user_id = ? AND (username != ? OR first_name != ?)
        ''', (username, first_name, user_id, username, first_name))

        conn.commit()

        # Получение баланса
        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        stars = result[0] if result else 0

        await message.answer(
            f"<b>🎁 Добро пожаловать в OneGifts!</b>\n\n"
            f"✨ <b>Твои звёзды:</b> {stars}\n\n"
            f"🎰 <b>Открывай подарочки и получай звёзды!</b>\n"
            f"🎁 <b>Бесплатный NFT подарок раз в 24 часа!</b>\n"
            f"💎 <b>Шанс выиграть NFT в обычном подарке!</b>\n\n"  # УБРАЛ 0.001%
            f"💰 <b>Пополнить баланс:</b> нажмите кнопку 'Депозит'\n"
            f"🛟 <b>Нужна помощь?</b> нажмите 'Поддержка'",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="HTML"
        )
        logger.info(f"Приветственное сообщение отправлено пользователю {user_id}")

    except Exception as e:
        logger.error(f"Ошибка при обработке /start: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = f"""
<b>🎮 Как играть:</b>

1. <b>🎁 Открыть подарочек</b> - стоит 100 звезд, можно выиграть от 1 до 500 звезд или NFT
2. <b>🎁 Бесплатный NFT подарок</b> - доступен раз в 24 часа, только NFT!
3. <b>🎁 Подарки</b> - рулетка с подарками (40% шанс на выигрыш)  # ИЗМЕНЕНО С 35% НА 40%
4. <b>🎒 Инвентарь</b> - посмотреть ваши подарки и NFT
5. <b>💎 NFT ячейки</b> - открой ячейку с шансом получить NFT
6. <b>💰 Депозит</b> - пополнить баланс звездами
7. <b>🛟 Поддержка</b> - связаться с поддержкой

<b>🎁 Ячейки подарков (шанс 40%):</b>  # ИЗМЕНЕНО С 35% НА 40%
• 💎💎 Алмаз: 45 звезд
• 🏆🏆 Кубок: 45 звезд
• 🚀🚀 Ракета: 25 звезд
• 🍾🍾 Шампанское: 25 звезд
• 🎂🎂 Торт: 25 звезд
• 🌹🌹 Розы: 12 звезд
• 🎁🎁 Подарок: 12 звезд
• 💖💖 Сердечко: 12 звезд
• 🧸🧸 Мишка: 8 звезд

<b>💎 NFT ячейки:</b>
• Ячейка 1: 80 звезд (1% шанс)
• Ячейка 2: 100 звезд (10% шанс)
• Ячейка 3: 250 звезд (45% шанс)

<b>💰 Для депозита:</b>
Напишите нашему саппорту: {SUPPORT_USERNAME}
Отправьте звезды или подарок!

<b>🎯 Удачи в игре!</b>
"""
    await message.answer(help_text, parse_mode="HTML")

# ========== ОБРАБОТЧИКИ КОЛБЭКОВ ==========

@dp.callback_query(F.data == "open_gift")
async def open_gift(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    logger.info(f"Пользователь {user_id} пытается открыть подарок")

    try:
        # Проверка баланса
        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            await callback.answer("❌ Пользователь не найден. Напишите /start", show_alert=True)
            return

        stars = result[0]

        if stars < 100:
            await callback.answer("❌ Недостаточно звёзд! Нужно минимум 100 звёзд для открытия.", show_alert=True)
            return

        # Вычитание звёзд
        new_stars = stars - 100
        cursor.execute('UPDATE users SET stars = ?, total_opened = total_opened + 1 WHERE user_id = ?', 
                       (new_stars, user_id))

        # Определение выигрыша
        prize = random.choices(
            list(PRIZE_CHANCES.keys()),
            weights=list(PRIZE_CHANCES.values())
        )[0]

        # Добавление выигрыша
        if prize != "Проигрыш":
            prize_value = PRIZE_VALUES[prize]
            new_stars += prize_value
            cursor.execute('UPDATE users SET stars = ? WHERE user_id = ?', (new_stars, user_id))

            if prize == "NFT":
                cursor.execute('UPDATE users SET nft_won = nft_won + 1 WHERE user_id = ?', (user_id,))

            # Запись выигрыша
            cursor.execute('''
                INSERT INTO wins (user_id, username, prize_type, prize_value, chance, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, prize, prize_value, PRIZE_CHANCES[prize], datetime.now().isoformat()))

            # Запись транзакции
            cursor.execute('''
                INSERT INTO transactions (user_id, username, amount, type, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, prize_value, "win", datetime.now().isoformat()))

            # Уведомление админа о большом выигрыше
            if prize_value >= 500 or prize == "NFT":
                try:
                    await bot.send_message(
                        ADMIN_ID,
                        f"🎉 <b>КРУПНЫЙ ВЫИГРЫШ!</b>\n\n"
                        f"👤 Пользователь: @{username if username else 'нет'}\n"
                        f"🆔 ID: {user_id}\n"
                        f"🎁 Приз: {prize}\n"
                        f"⭐ Значение: {prize_value} звезд\n"
                        f"📊 Шанс: {PRIZE_CHANCES[prize]}%\n"
                        f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу: {e}")

        conn.commit()

        # Отправка результата
        if prize == "Проигрыш":
            await callback.message.edit_text(
                f"<b>🎁 Результат открытия:</b>\n\n"
                f"😔 К сожалению, ты ничего не выиграл...\n\n"
                f"✨ <b>Твои звёзды:</b> {new_stars}\n"
                f"🎰 <b>Попробуй ещё раз!</b>",
                reply_markup=get_main_menu_keyboard(user_id),
                parse_mode="HTML"
            )
        else:
            emoji = "💎" if prize == "NFT" else "⭐"
            nft_note = "\n\n<i>Если выиграл NFT - админ сам вам отпишет!</i>" if prize == "NFT" else ""
            await callback.message.edit_text(
                f"<b>🎁 Результат открытия:</b>\n\n"
                f"{emoji} <b>Поздравляем! Ты выиграл:</b> {prize}\n"
                f"📊 <b>Шанс выигрыша:</b> {PRIZE_CHANCES[prize]}%\n\n"
                f"✨ <b>Твои звёзды:</b> {new_stars}"
                f"{nft_note}",
                reply_markup=get_main_menu_keyboard(user_id),
                parse_mode="HTML"
            )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при открытии подарка: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@dp.callback_query(F.data == "free_nft_gift")
async def free_nft_gift(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    logger.info(f"Пользователь {user_id} запросил бесплатный NFT подарок")

    try:
        # Проверка времени последнего использования
        cursor.execute('SELECT last_free_gift_date FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        now = datetime.now()
        can_use = True
        time_left = None

        if result and result[0]:
            last_date = datetime.fromisoformat(result[0])
            if (now - last_date) < timedelta(hours=24):
                can_use = False
                next_time = last_date + timedelta(hours=24)
                time_left = next_time - now
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60

                await callback.answer(
                    f"⏳ Бесплатный NFT подарок будет доступен через {hours}ч {minutes}мин",
                    show_alert=True
                )
                return

        if can_use:
            # В ежедневном подарке только NFT
            prize = "NFT"
            prize_value = PRIZE_VALUES[prize]

            # Обновление данных пользователя
            cursor.execute('''
                UPDATE users 
                SET stars = stars + ?, 
                    free_gift_used = free_gift_used + 1,
                    last_free_gift_date = ?,
                    total_opened = total_opened + 1,
                    nft_won = nft_won + 1
                WHERE user_id = ?
            ''', (prize_value, now.isoformat(), user_id))

            # Получение нового баланса
            cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
            new_stars_result = cursor.fetchone()
            new_stars = new_stars_result[0] if new_stars_result else prize_value

            # Запись выигрыша
            cursor.execute('''
                INSERT INTO wins (user_id, username, prize_type, prize_value, chance, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, prize, prize_value, DAILY_GIFT_CHANCES[prize], now.isoformat()))

            # Запись транзакции
            cursor.execute('''
                INSERT INTO transactions (user_id, username, amount, type, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, prize_value, "daily_nft_win", now.isoformat()))

            conn.commit()

            # Отправка результата
            await callback.message.edit_text(
                f"<b>🎁 Бесплатный NFT подарок:</b>\n\n"
                f"💎 <b>Поздравляем! Ты выиграл:</b> NFT\n"
                f"📊 <b>Шанс выигрыша:</b> 100%\n\n"
                f"✨ <b>Твои звёзды:</b> {new_stars}\n"
                f"🕐 <b>Следующий бесплатный NFT подарок через 24 часа</b>\n\n"
                f"<i>Админ сам вам отпишет!</i>",
                reply_markup=get_main_menu_keyboard(user_id),
                parse_mode="HTML"
            )

            # Уведомление админа
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"🎉 <b>NFT В БЕСПЛАТНОМ ПОДАРКЕ!</b>\n\n"
                    f"👤 Пользователь: @{username if username else 'нет'}\n"
                    f"🆔 ID: {user_id}\n"
                    f"🎁 Приз: {prize}\n"
                    f"⭐ Значение: {prize_value} звезд\n"
                    f"📊 Шанс: {DAILY_GIFT_CHANCES[prize]}%\n"
                    f"⏰ Время: {now.strftime('%H:%M %d.%m.%Y')}\n"
                    f"🎯 Тип: Ежедневный NFT подарок",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу: {e}")

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении бесплатного NFT подарка: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@dp.callback_query(F.data == "gifts_section")
async def gifts_section(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    # Проверяем баланс
    cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    stars = result[0] if result else 0

    # Создаем клавиатуру с ячейками подарков
    keyboard = InlineKeyboardBuilder()

    # Добавляем ячейки подарков в 3 столбца
    gifts_per_row = 3
    for i in range(0, len(GIFTS_CELLS), gifts_per_row):
        row_gifts = GIFTS_CELLS[i:i+gifts_per_row]
        buttons = []
        for gift in row_gifts:
            buttons.append(InlineKeyboardButton(
                text=f"{gift['cell_emoji']} {gift['cost']}⭐", 
                callback_data=f"open_gift_cell_{gift['name'].lower()}"
            ))
        keyboard.row(*buttons)

    keyboard.row(InlineKeyboardButton(text="🎒 Мой инвентарь", callback_data="inventory"))
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

    await callback.message.edit_text(
        f"<b>🎁 Ячейки подарков</b>\n\n"
        f"✨ <b>Ваш баланс:</b> {stars}⭐\n\n"
        f"🎰 <b>Правила игры:</b>\n"
        f"• Выберите ячейку с подарком\n"
        f"• Стоимость: указана под каждой ячейкой\n"
        f"• Шанс выигрыша: 40%\n"  # ИЗМЕНЕНО С 35% НА 40%
        f"• При выигрыше подарок добавляется в инвентарь\n\n"
        f"💰 <b>Цены за попытку:</b>\n"
        f"💎💎 Алмаз: 45⭐ | 🏆🏆 Кубок: 45⭐\n"
        f"🚀🚀 Ракета: 25⭐ | 🍾🍾 Шампанское: 25⭐\n"
        f"🎂🎂 Торт: 25⭐ | 🌹🌹 Розы: 12⭐\n"
        f"🎁🎁 Подарок: 12⭐ | 💖💖 Сердечко: 12⭐\n"
        f"🧸🧸 Мишка: 8⭐",
        reply_markup=keyboard.as_markup(),
        parse_mode="HTML"
    )

    await callback.answer()

@dp.callback_query(F.data.startswith("open_gift_cell_"))
async def open_gift_cell(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    gift_name_lower = callback.data.split("_")[3]

    # Находим подарок по имени
    gift = None
    for g in GIFTS_CELLS:
        if g["name"].lower() == gift_name_lower:
            gift = g
            break

    if not gift:
        await callback.answer("❌ Подарок не найден", show_alert=True)
        return

    try:
        # Проверяем баланс
        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        stars = result[0]

        if stars < gift["cost"]:
            await callback.answer(f"❌ Недостаточно звёзд! Нужно {gift['cost']}⭐", show_alert=True)
            return

        # Вычитаем звезды
        new_stars = stars - gift["cost"]
        cursor.execute('UPDATE users SET stars = ? WHERE user_id = ?', (new_stars, user_id))

        # Определяем выигрыш (реальный шанс 25%, показываем 40%) - ИЗМЕНЕНО С 15% НА 25%
        is_win = random.random() * 100 < 25  # Реальный шанс 25%

        if is_win:
            # Добавляем подарок в инвентарь
            cursor.execute('''
                INSERT INTO user_gifts (user_id, gift_name, gift_emoji, gift_value, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, gift["name"], gift["emoji"], gift["cost"], datetime.now().isoformat()))

            cursor.execute('UPDATE users SET gifts_won = gifts_won + 1 WHERE user_id = ?', (user_id,))

            # Записываем выигрыш
            cursor.execute('''
                INSERT INTO wins (user_id, username, prize_type, prize_value, chance, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, f"Подарок {gift['name']}", gift["cost"], 40, datetime.now().isoformat()))  # ИЗМЕНЕНО С 35 НА 40

            # Записываем транзакцию
            cursor.execute('''
                INSERT INTO transactions (user_id, username, amount, type, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, gift["cost"], "gift_win", datetime.now().isoformat()))

            # СООБЩЕНИЕ ПРИ ВЫИГРЫШЕ - УБРАЛ ДУБЛИРОВАНИЕ, ИСПОЛЬЗУЕМ ОДНО СООБЩЕНИЕ
            result_text = (
                f"🎉 <b>Поздравляем! Вы выиграли:</b>\n"
                f"{gift['emoji']} <b>{gift['name']}</b>\n"
                f"💰 <b>Стоимость:</b> {gift['cost']}⭐\n"
                f"📊 <b>Шанс:</b> 40%\n\n"  # ИЗМЕНЕНО С 35% НА 40%
                f"🎁 <b>Подарок добавлен в ваш инвентарь!</b>\n"
                f"✨ <b>Можете вывести его в разделе 'Инвентарь'</b>"
            )

            # Уведомляем админа
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"🎁 <b>ПОДАРОК ВЫИГРАН!</b>\n\n"
                    f"👤 Пользователь: @{username if username else 'нет'}\n"
                    f"🆔 ID: {user_id}\n"
                    f"🎁 Приз: {gift['name']}\n"
                    f"💰 Стоимость: {gift['cost']} звезд\n"
                    f"📊 Шанс: 40%\n"  # ИЗМЕНЕНО С 35% НА 40%
                    f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
                    f"🎯 Тип: Ячейка подарков",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу: {e}")
        else:
            # Записываем проигрыш
            cursor.execute('''
                INSERT INTO transactions (user_id, username, amount, type, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, gift["cost"], "gift_lose", datetime.now().isoformat()))

            result_text = (
                f"😔 <b>К сожалению, не повезло</b>\n"
                f"🎯 <b>Цель:</b> {gift['emoji']} {gift['name']}\n"
                f"💰 <b>Стоимость попытки:</b> {gift['cost']}⭐\n"
                f"📊 <b>Шанс был:</b> 40%\n\n"  # ИЗМЕНЕНО С 35% НА 40%
                f"💫 <b>Попробуйте ещё раз!</b>"
            )

        conn.commit()

        # Получаем финальный баланс
        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        final_stars = cursor.fetchone()[0]

        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="🎁 Попробовать ещё раз", callback_data=f"open_gift_cell_{gift_name_lower}"))
        keyboard.row(InlineKeyboardButton(text="🎁 Другие подарки", callback_data="gifts_section"))
        keyboard.row(InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory"))
        keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

        await callback.message.edit_text(
            f"<b>🎰 Результат открытия ячейки:</b>\n\n"
            f"{result_text}\n\n"
            f"✨ <b>Ваш баланс:</b> {final_stars}⭐",
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при открытии ячейки подарка: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@dp.callback_query(F.data == "inventory")
async def inventory(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    try:
        # Получаем активные подарки пользователя
        cursor.execute('''
            SELECT id, gift_emoji, gift_name, gift_value, timestamp 
            FROM user_gifts 
            WHERE user_id = ? AND status = 'active'
            ORDER BY timestamp DESC
        ''', (user_id,))

        gifts = cursor.fetchall()

        # Получаем NFT пользователя
        cursor.execute('SELECT nft_won FROM users WHERE user_id = ?', (user_id,))
        nft_result = cursor.fetchone()
        nft_count = nft_result[0] if nft_result else 0

        # Создаем клавиатуру для выбора подарка
        keyboard = InlineKeyboardBuilder()

        if not gifts and nft_count == 0:
            inventory_text = "📭 <b>Ваш инвентарь пуст</b>\n\n🎁 <b>Попробуйте ячейки подарков!</b>"
            keyboard.row(InlineKeyboardButton(text="🎁 Ячейки подарков", callback_data="gifts_section"))
            keyboard.row(InlineKeyboardButton(text="💎 NFT ячейки", callback_data="nft_cells"))
            keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
        else:
            inventory_text = "<b>🎁 Ваши подарки (нажмите для вывода):</b>\n"
            gift_count = 0

            # Группируем одинаковые подарки
            gift_dict = {}
            for gift in gifts:
                gift_id, emoji, name, value, timestamp = gift
                key = f"{emoji} {name}"
                if key in gift_dict:
                    gift_dict[key]["count"] += 1
                    gift_dict[key]["ids"].append(gift_id)
                else:
                    gift_dict[key] = {"emoji": emoji, "name": name, "value": value, "count": 1, "ids": [gift_id]}
                gift_count += 1

            # Отображаем группированные подарки
            for gift_info in gift_dict.values():
                if gift_info["count"] > 1:
                    inventory_text += f"{gift_info['emoji']} {gift_info['name']}: {gift_info['value']}⭐ (x{gift_info['count']})\n"
                    # Кнопка для вывода одного экземпляра подарка (первый ID)
                    keyboard.row(InlineKeyboardButton(
                        text=f"📤 Вывести {gift_info['emoji']} {gift_info['name']} ({gift_info['value']}⭐)",
                        callback_data=f"withdraw_gift_{gift_info['ids'][0]}"
                    ))
                else:
                    inventory_text += f"{gift_info['emoji']} {gift_info['name']}: {gift_info['value']}⭐\n"
                    # Кнопка для вывода подарка
                    keyboard.row(InlineKeyboardButton(
                        text=f"📤 Вывести {gift_info['emoji']} {gift_info['name']} ({gift_info['value']}⭐)",
                        callback_data=f"withdraw_gift_{gift_info['ids'][0]}"
                    ))

            inventory_text += f"\n<b>💎 Ваши NFT:</b> {nft_count}\n"
            inventory_text += f"<b>📊 Всего предметов:</b> {gift_count + nft_count}"

            keyboard.row(InlineKeyboardButton(text="🎁 Ячейки подарков", callback_data="gifts_section"))
            keyboard.row(InlineKeyboardButton(text="💎 NFT ячейки", callback_data="nft_cells"))
            keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

        await callback.message.edit_text(
            f"<b>🎒 Ваш инвентарь</b>\n\n{inventory_text}",
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении инвентаря: {e}")
        await callback.answer("❌ Произошла ошибка.", show_alert=True)

@dp.callback_query(F.data.startswith("withdraw_gift_"))
async def withdraw_gift(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    gift_id = int(callback.data.split("_")[2])

    try:
        # Получаем информацию о подарке
        cursor.execute('''
            SELECT gift_name, gift_emoji, gift_value 
            FROM user_gifts 
            WHERE id = ? AND user_id = ? AND status = 'active'
        ''', (gift_id, user_id))

        gift_info = cursor.fetchone()

        if not gift_info:
            await callback.answer("❌ Подарок не найден или уже выведен", show_alert=True)
            return

        gift_name, gift_emoji, gift_value = gift_info

        # Помечаем подарок как удаленный (изменяем статус)
        cursor.execute('UPDATE user_gifts SET status = "withdrawn" WHERE id = ?', (gift_id,))

        # Создаем заявку на вывод
        cursor.execute('''
            INSERT INTO withdrawal_requests (user_id, username, gift_name, gift_emoji, gift_value, timestamp, support_username)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, gift_name, gift_emoji, gift_value, datetime.now().isoformat(), SUPPORT_USERNAME))

        conn.commit()

        # Уведомляем пользователя
        await callback.message.edit_text(
            f"<b>✅ Заявка на вывод создана!</b>\n\n"
            f"🎁 <b>Подарок:</b> {gift_emoji} {gift_name}\n"
            f"💰 <b>Стоимость:</b> {gift_value}⭐\n\n"
            f"👤 <b>Свяжитесь с поддержкой:</b>\n"
            f"{SUPPORT_USERNAME}\n\n"
            f"<i>Подарок удален из вашего инвентаря.</i>\n"
            f"<i>Администратор получил уведомление о вашей заявке.</i>",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="HTML"
        )

        # Уведомляем администратора
        try:
            await bot.send_message(
                ADMIN_ID,
                f"📤 <b>НОВАЯ ЗАЯВКА НА ВЫВОД ПОДАРКА!</b>\n\n"
                f"👤 <b>Пользователь:</b> @{username if username else 'нет'}\n"
                f"🆔 <b>ID:</b> {user_id}\n"
                f"🎁 <b>Подарок:</b> {gift_emoji} {gift_name}\n"
                f"💰 <b>Стоимость:</b> {gift_value}⭐\n"
                f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                f"📞 <b>Саппорт для связи:</b> {SUPPORT_USERNAME}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу: {e}")

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при создании заявки на вывод: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@dp.callback_query(F.data == "nft_cells")
async def nft_cells(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    keyboard = InlineKeyboardBuilder()

    for cell in NFT_CELLS:
        keyboard.row(InlineKeyboardButton(
            text=f"Ячейка {cell['cell']} - {cell['cost']}⭐ ({cell['description']})", 
            callback_data=f"open_nft_cell_{cell['cell']}"
        ))

    keyboard.row(InlineKeyboardButton(text="🎒 Мой инвентарь", callback_data="inventory"))
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

    await callback.message.edit_text(
        "<b>💎 NFT ячейки</b>\n\n"
        "🎯 <b>Откройте ячейку с шансом получить NFT:</b>\n"
        "• NFT = 1000 звезд\n"
        "• Админ сам напишет при выигрыше\n\n"
        "💰 <b>Выберите ячейку:</b>",
        reply_markup=keyboard.as_markup(),
        parse_mode="HTML"
    )

    await callback.answer()

@dp.callback_query(F.data.startswith("open_nft_cell_"))
async def open_nft_cell(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    cell_num = int(callback.data.split("_")[3])

    # Находим ячейку
    cell_data = None
    for cell in NFT_CELLS:
        if cell["cell"] == cell_num:
            cell_data = cell
            break

    if not cell_data:
        await callback.answer("❌ Ячейка не найден", show_alert=True)
        return

    try:
        # Проверяем баланс
        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        stars = result[0]

        if stars < cell_data["cost"]:
            await callback.answer(f"❌ Недостаточно звёзд! Нужно {cell_data['cost']}⭐", show_alert=True)
            return

        # Вычитаем звезды
        new_stars = stars - cell_data["cost"]
        cursor.execute('UPDATE users SET stars = ?, nft_cells_opened = nft_cells_opened + 1 WHERE user_id = ?', 
                      (new_stars, user_id))

        # Определяем выигрыш
        is_nft_win = random.random() * 100 < cell_data["chance"]

        if is_nft_win:
            # Выиграли NFT (1000 звезд)
            nft_value = 1000
            new_stars += nft_value
            cursor.execute('UPDATE users SET stars = ?, nft_won = nft_won + 1 WHERE user_id = ?', 
                          (new_stars, user_id))

            # Записываем выигрыш
            cursor.execute('''
                INSERT INTO wins (user_id, username, prize_type, prize_value, chance, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, "NFT из ячейки", nft_value, cell_data["chance"], datetime.now().isoformat()))

            # Записываем транзакцию
            cursor.execute('''
                INSERT INTO transactions (user_id, username, amount, type, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, nft_value, "nft_cell_win", datetime.now().isoformat()))

            result_text = f"🎉 <b>Поздравляем! Вы выиграли NFT!</b>\n💎 <b>Выигрыш:</b> {nft_value}⭐\n📊 <b>Шанс:</b> {cell_data['chance']}%"

            # Уведомляем админа
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"🎉 <b>NFT ИЗ ЯЧЕЙКИ!</b>\n\n"
                    f"👤 Пользователь: @{username if username else 'нет'}\n"
                    f"🆔 ID: {user_id}\n"
                    f"🎁 Приз: NFT\n"
                    f"⭐ Значение: {nft_value} звезд\n"
                    f"📊 Шанс: {cell_data['chance']}%\n"
                    f"🎯 Ячейка: {cell_num}\n"
                    f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу: {e}")
        else:
            # Не выиграли
            cursor.execute('''
                INSERT INTO nft_cells (user_id, cell_type, cost, chance, result, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, cell_num, cell_data["cost"], cell_data["chance"], False, datetime.now().isoformat()))

            result_text = f"😔 <b>К сожалению, NFT не выпал</b>\n📊 <b>Шанс был:</b> {cell_data['chance']}%"

        conn.commit()

        # Получаем финальный баланс
        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        final_stars = cursor.fetchone()[0]

        nft_note = "\n\n<i>Админ сам вам отпишет!</i>" if is_nft_win else ""

        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="💎 Открыть ещё ячейку", callback_data="nft_cells"))
        keyboard.row(InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory"))
        keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

        await callback.message.edit_text(
            f"<b>💎 Открытие NFT ячейки {cell_num}</b>\n\n"
            f"💰 <b>Стоимость:</b> {cell_data['cost']}⭐\n"
            f"{result_text}\n\n"
            f"✨ <b>Ваш баланс:</b> {final_stars}⭐"
            f"{nft_note}",
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при открытии NFT ячейки: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@dp.callback_query(F.data == "deposit")
async def deposit_section(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    try:
        # Получаем историю депозитов
        cursor.execute('''
            SELECT amount, status, timestamp 
            FROM deposits 
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        ''', (user_id,))

        deposits = cursor.fetchall()

        deposits_text = ""
        if deposits:
            deposits_text = "\n<b>📜 История депозитов:</b>\n"
            for dep in deposits:
                status_emoji = "✅" if dep[1] == "completed" else "⏳" if dep[1] == "pending" else "❌"
                deposits_text += f"{status_emoji} {dep[0]}⭐ - {dep[1]} ({datetime.fromisoformat(dep[2]).strftime('%d.%m')})\n"
        else:
            deposits_text = "\n📭 У вас пока нет депозитов"

        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="📤 Создать депозит", callback_data="create_deposit"))
        keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

        await callback.message.edit_text(
            f"<b>💰 Депозит</b>\n\n"
            f"💳 <b>Как пополнить баланс:</b>\n"
            f"1. Нажмите 'Создать депозит'\n"
            f"2. Укажите сумму депозита\n"
            f"3. Отправьте {SUPPORT_USERNAME} звезды или подарок\n"
            f"4. Пришлите скриншот подтверждения\n"
            f"5. Ждите подтверждения от администратора\n\n"
            f"👤 <b>Саппорт:</b> {SUPPORT_USERNAME}\n"
            f"⚠️ <b>Внимание:</b> Работаем только с {SUPPORT_USERNAME}"
            f"{deposits_text}",
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка в разделе депозита: {e}")
        await callback.answer("❌ Произошла ошибка.", show_alert=True)

@dp.callback_query(F.data == "create_deposit")
async def create_deposit(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"<b>📤 Создание депозита</b>\n\n"
        f"💳 <b>Инструкция:</b>\n"
        f"1. Решите какую сумму хотите внести\n"
        f"2. Отправьте звезды или подарок {SUPPORT_USERNAME}\n"
        f"3. Сделайте скриншот перевода\n"
        f"4. Отправьте мне сумму депозита в звездах\n\n"
        f"<b>Формат сообщения:</b>\n"
        f"<code>депозит 100</code> - для депозита 100 звезд\n\n"
        f"👤 <b>Саппорт:</b> {SUPPORT_USERNAME}\n"
        f"⚠️ <b>Только для этого саппорта!</b>",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "support")
async def support_section(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"<b>🛟 Поддержка</b>\n\n"
        f"🛠️ <b>Нужна помощь?</b>\n"
        f"• По вопросам депозитов\n"
        f"• По техническим проблемам\n"
        f"• По вопросам сотрудничества\n\n"
        f"👤 <b>Наш саппорт:</b>\n"
        f"{SUPPORT_USERNAME}\n\n"
        f"💬 <b>Напишите напрямую:</b>\n"
        f"1. Откройте чат с {SUPPORT_USERNAME}\n"
        f"2. Опишите вашу проблему\n"
        f"3. Приложите скриншоты если нужно\n\n"
        f"⏰ <b>Время ответа:</b> до 24 часов",
        reply_markup=get_main_menu_keyboard(callback.from_user.id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "my_stars")
async def my_stars(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    try:
        cursor.execute('SELECT stars, deposit_total FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            stars = 0
            deposit_total = 0
        else:
            stars = result[0]
            deposit_total = result[1] or 0

        await callback.message.edit_text(
            f"<b>⭐ Ваш баланс:</b>\n\n"
            f"✨ <b>Звёзды:</b> {stars}\n"
            f"💰 <b>Всего внесено депозитов:</b> {deposit_total}⭐\n\n"
            f"🎁 <b>Для открытия подарочка нужно 100 звёзд</b>\n"
            f"💎 <b>Каждый подарок даёт шанс выиграть NFT!</b>\n\n"
            f"💳 <b>Пополнить баланс:</b> нажмите 'Депозит'",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении баланса: {e}")
        await callback.answer("❌ Произошла ошибка.", show_alert=True)

# ========== АДМИН ПАНЕЛЬ ==========

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    if user_id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа к админ панели", show_alert=True)
        return

    try:
        # Получаем статистику
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM transactions WHERE type = "win"')
        total_wins = cursor.fetchone()[0]

        cursor.execute('SELECT SUM(stars) FROM users')
        total_stars_result = cursor.fetchone()[0]
        total_stars = total_stars_result if total_stars_result else 0

        cursor.execute('SELECT COUNT(*) FROM withdrawal_requests WHERE status = "pending"')
        pending_withdrawals = cursor.fetchone()[0]

        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
        keyboard.row(InlineKeyboardButton(text="💰 Добавить звёзды", callback_data="admin_add_stars"))
        keyboard.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
        keyboard.row(InlineKeyboardButton(text="📤 Заявки на вывод", callback_data="admin_withdrawals"))
        keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

        await callback.message.edit_text(
            f"<b>👑 Админ панель</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• 👥 Пользователей: {total_users}\n"
            f"• 🎁 Выигрышей: {total_wins}\n"
            f"• ⭐ Всего звёзд: {total_stars}\n"
            f"• 📤 Ожидают вывода: {pending_withdrawals}\n\n"
            f"<b>Выберите действие:</b>",
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в админ панели: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    if user_id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    try:
        # Подробная статистика
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(registered_date) = DATE("now")')
        new_users_today = cursor.fetchone()[0]

        cursor.execute('SELECT SUM(stars) FROM users')
        total_stars_result = cursor.fetchone()[0]
        total_stars = total_stars_result if total_stars_result else 0

        cursor.execute('SELECT COUNT(*) FROM wins')
        total_wins = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM wins WHERE prize_type = "NFT"')
        nft_wins = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM transactions WHERE type = "deposit"')
        total_deposits = cursor.fetchone()[0]

        cursor.execute('SELECT SUM(amount) FROM deposits WHERE status = "completed"')
        total_deposited_result = cursor.fetchone()[0]
        total_deposited = total_deposited_result if total_deposited_result else 0

        cursor.execute('SELECT COUNT(*) FROM withdrawal_requests')
        total_withdrawals = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM withdrawal_requests WHERE status = "pending"')
        pending_withdrawals = cursor.fetchone()[0]

        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_panel"))

        await callback.message.edit_text(
            f"<b>📊 Подробная статистика</b>\n\n"
            f"<b>👥 Пользователи:</b>\n"
            f"• Всего: {total_users}\n"
            f"• Новых сегодня: {new_users_today}\n\n"
            f"<b>💰 Финансы:</b>\n"
            f"• Всего звёзд: {total_stars}⭐\n"
            f"• Всего депозитов: {total_deposits}\n"
            f"• Сумма депозитов: {total_deposited}⭐\n\n"
            f"<b>🎁 Активность:</b>\n"
            f"• Всего выигрышей: {total_wins}\n"
            f"• NFT выиграно: {nft_wins}\n\n"
            f"<b>📤 Выводы:</b>\n"
            f"• Всего заявок: {total_withdrawals}\n"
            f"• Ожидают обработки: {pending_withdrawals}",
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@dp.callback_query(F.data == "admin_add_stars")
async def admin_add_stars(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    if user_id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "<b>💰 Добавление звёзд пользователю</b>\n\n"
        "<b>Отправьте сообщение в формате:</b>\n"
        "<code>ID_пользователя количество_звёзд</code>\n\n"
        "<i>Примеры:</i>\n"
        "<code>123456789 100</code> - добавить 100⭐ пользователю с ID 123456789\n"
        "<code>987654321 -50</code> - убрать 50⭐ у пользователя с ID 987654321\n\n"
        "<b>⚠️ Внимание:</b> Можно указывать отрицательные числа для снятия звёзд.",
        parse_mode="HTML"
    )

    await callback.answer()

# Обработчик сообщений для добавления звёзд
@dp.message(F.from_user.id == ADMIN_ID)
async def handle_admin_stars_message(message: types.Message):
    # Проверяем, не является ли это командой
    if message.text.startswith('/'):
        return

    try:
        # Пробуем разобрать сообщение как команду добавления звёзд
        parts = message.text.strip().split()

        if len(parts) != 2:
            # Это не команда добавления звёзд, возможно это рассылка
            # Проверяем, не находится ли пользователь в процессе рассылки
            return

        try:
            target_user_id = int(parts[0])
            stars_amount = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат. Используйте: <code>ID количество</code>", parse_mode="HTML")
            return

        # Проверяем существование пользователя
        cursor.execute('SELECT username, first_name, stars FROM users WHERE user_id = ?', (target_user_id,))
        user_info = cursor.fetchone()

        if not user_info:
            await message.answer(f"❌ Пользователь с ID <code>{target_user_id}</code> не найден.", parse_mode="HTML")
            return

        username, first_name, current_stars = user_info

        # Проверяем, не уйдет ли баланс в минус
        new_stars = current_stars + stars_amount
        if new_stars < 0:
            await message.answer(f"❌ Нельзя убрать больше звёзд, чем есть у пользователя. Текущий баланс: {current_stars}⭐")
            return

        # Обновляем баланс
        cursor.execute('UPDATE users SET stars = ? WHERE user_id = ?', (new_stars, target_user_id))

        # Записываем транзакцию
        cursor.execute('''
            INSERT INTO transactions (user_id, username, amount, type, timestamp, admin_id) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (target_user_id, username, stars_amount, "admin_add_stars", datetime.now().isoformat(), ADMIN_ID))

        conn.commit()

        # Уведомляем администратора
        operation_type = "добавлено" if stars_amount > 0 else "убрано"
        operation_emoji = "➕" if stars_amount > 0 else "➖"

        await message.answer(
            f"{operation_emoji} <b>Баланс обновлен!</b>\n\n"
            f"👤 <b>Пользователь:</b> @{username if username else 'нет'}\n"
            f"📛 <b>Имя:</b> {first_name}\n"
            f"🆔 <b>ID:</b> {target_user_id}\n"
            f"✨ <b>Было:</b> {current_stars}⭐\n"
            f"{operation_emoji} <b>{operation_type}:</b> {abs(stars_amount)}⭐\n"
            f"✨ <b>Стало:</b> {new_stars}⭐\n"
            f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M %d.%m.%Y')}",
            parse_mode="HTML"
        )

        # Уведомляем пользователя
        try:
            await bot.send_message(
                target_user_id,
                f"✨ <b>Ваш баланс обновлен!</b>\n\n"
                f"{operation_emoji} <b>{operation_type.capitalize()}:</b> {abs(stars_amount)}⭐\n"
                f"✨ <b>Новый баланс:</b> {new_stars}⭐\n\n"
                f"<i>Изменение внесено администратором.</i>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при уведомлении пользователя {target_user_id}: {e}")
            await message.answer("⚠️ Пользователь получил звёзды, но не получил уведомление (возможно заблокировал бота).")

    except Exception as e:
        logger.error(f"Ошибка при добавлении звёзд: {e}")
        await message.answer("❌ Произошла ошибка при обработке команды.")

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    if user_id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "<b>📢 Рассылка сообщений</b>\n\n"
        "<b>Отправьте сообщение для рассылки всем пользователям:</b>\n\n"
        "<i>Формат:</i>\n"
        "Текст сообщения (поддерживается HTML разметка)\n\n"
        "<i>Пример:</i>\n"
        "<code>🔥 Новый конкурс! 🎁\n\nВыиграй 1000⭐! Подробности у @ownsuicude</code>\n\n"
        "<b>⚠️ Внимание:</b> Рассылка будет отправлена всем пользователям бота.",
        parse_mode="HTML"
    )

    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_broadcast:"))
async def confirm_broadcast(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    if user_id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    try:
        # Получаем ID оригинального сообщения
        message_id = int(callback.data.split(":")[1])

        # Получаем оригинальное сообщение
        original_message = await bot.forward_message(ADMIN_ID, ADMIN_ID, message_id)
        broadcast_text = original_message.text

        # Получаем всех пользователей
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()

        total_users = len(users)
        successful = 0
        failed = 0

        # Отправляем сообщение о начале рассылки
        status_message = await callback.message.answer(f"🔄 Начинаю рассылку для {total_users} пользователей...")

        # Рассылаем сообщение всем пользователям
        for user in users:
            user_id = user[0]
            try:
                await bot.send_message(user_id, broadcast_text, parse_mode="HTML")
                successful += 1

                # Обновляем статус каждые 10 отправок
                if successful % 10 == 0:
                    try:
                        await status_message.edit_text(
                            f"🔄 Рассылка в процессе...\n"
                            f"✅ Успешно: {successful}\n"
                            f"❌ Неудачно: {failed}\n"
                            f"📊 Всего: {total_users}"
                        )
                    except:
                        pass

                # Небольшая задержка чтобы не превысить лимиты Telegram
                await asyncio.sleep(0.1)

            except Exception as e:
                failed += 1
                logger.error(f"Ошибка при отправке пользователю {user_id}: {e}")

        # Финальное сообщение о результатах
        await status_message.edit_text(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📊 <b>Результаты:</b>\n"
            f"• ✅ Успешно: {successful}\n"
            f"• ❌ Неудачно: {failed}\n"
            f"• 📊 Всего: {total_users}\n\n"
            f"<i>Неудачные отправки обычно означают, что пользователь заблокировал бота.</i>",
            parse_mode="HTML"
        )

        # Возвращаем в админ панель
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_panel"))

        await callback.message.answer(
            "Рассылка завершена. Выберите следующее действие:",
            reply_markup=keyboard.as_markup()
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при рассылке: {e}")
        await callback.answer("❌ Произошла ошибка при рассылке", show_alert=True)

@dp.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    if user_id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    try:
        # Получаем заявки на вывод
        cursor.execute('''
            SELECT id, user_id, username, gift_name, gift_emoji, gift_value, timestamp 
            FROM withdrawal_requests 
            WHERE status = 'pending'
            ORDER BY timestamp DESC
            LIMIT 20
        ''')

        withdrawals = cursor.fetchall()

        if not withdrawals:
            keyboard = InlineKeyboardBuilder()
            keyboard.row(InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_panel"))

            await callback.message.edit_text(
                "<b>📤 Заявки на вывод</b>\n\n"
                "✅ Нет ожидающих заявок на вывод.",
                reply_markup=keyboard.as_markup(),
                parse_mode="HTML"
            )
            return

        withdrawals_text = "<b>📤 Ожидающие заявки на вывод:</b>\n\n"

        keyboard = InlineKeyboardBuilder()

        for withdrawal in withdrawals:
            w_id, w_user_id, w_username, w_gift_name, w_gift_emoji, w_gift_value, w_timestamp = withdrawal
            w_time = datetime.fromisoformat(w_timestamp).strftime('%d.%m %H:%M')

            withdrawals_text += f"<b>Заявка #{w_id}</b>\n"
            withdrawals_text += f"👤 @{w_username if w_username else 'нет'} (ID: {w_user_id})\n"
            withdrawals_text += f"🎁 {w_gift_emoji} {w_gift_name} ({w_gift_value}⭐)\n"
            withdrawals_text += f"⏰ {w_time}\n"
            withdrawals_text += f"📞 Саппорт: {SUPPORT_USERNAME}\n\n"

            keyboard.row(InlineKeyboardButton(
                text=f"✅ Обработать #{w_id}",
                callback_data=f"process_withdrawal:{w_id}"
            ))

        keyboard.row(InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_panel"))

        await callback.message.edit_text(
            withdrawals_text,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении заявок: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@dp.callback_query(F.data.startswith("process_withdrawal:"))
async def process_withdrawal(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    if user_id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    try:
        withdrawal_id = int(callback.data.split(":")[1])

        # Обновляем статус заявки
        cursor.execute('UPDATE withdrawal_requests SET status = "completed" WHERE id = ?', (withdrawal_id,))

        # Получаем информацию о заявке
        cursor.execute('''
            SELECT user_id, username, gift_name, gift_emoji, gift_value 
            FROM withdrawal_requests 
            WHERE id = ?
        ''', (withdrawal_id,))

        withdrawal_info = cursor.fetchone()

        if withdrawal_info:
            w_user_id, w_username, w_gift_name, w_gift_emoji, w_gift_value = withdrawal_info

            # Уведомляем пользователя
            try:
                await bot.send_message(
                    w_user_id,
                    f"✅ <b>Ваша заявка на вывод обработана!</b>\n\n"
                    f"🎁 <b>Подарок:</b> {w_gift_emoji} {w_gift_name}\n"
                    f"💰 <b>Стоимость:</b> {w_gift_value}⭐\n\n"
                    f"👤 <b>Свяжитесь с поддержкой:</b> {SUPPORT_USERNAME}\n"
                    f"<i>для получения вашего подарка.</i>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка при уведомлении пользователя {w_user_id}: {e}")

        conn.commit()

        # Обновляем список заявок
        await admin_withdrawals(callback)

        await callback.answer(f"✅ Заявка #{withdrawal_id} обработана")

    except Exception as e:
        logger.error(f"Ошибка при обработке заявки: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

# ========== ЗАПУСК БОТА ==========

async def main():
    logger.info("Инициализация базы данных...")
    init_db()

    logger.info("Запуск бота...")

    # Удаляем вебхук (если был)
    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем поллинг
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        # ЗАПУСКАЕМ KEEP-ALIVE СЕРВЕР
        keep_alive()
        logger.info("Keep-alive сервер запущен")

        # ЗАПУСКАЕМ БОТА
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
