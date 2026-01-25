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
    db_exists = os.path.exists('onegifts.db')

    if db_exists:
        logger.info("База данных существует, проверяем структуру...")
        try:
            cursor.execute("PRAGMA table_info(user_gifts)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'status' not in columns:
                logger.info("Добавляем поле status в таблицу user_gifts...")
                cursor.execute('ALTER TABLE user_gifts ADD COLUMN status TEXT DEFAULT "active"')
                conn.commit()
        except sqlite3.OperationalError:
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

# Шансы выигрыша для обычных подарков (стоимость открытия 25 звезд) - ИЗМЕНЕНЫ ШАНСЫ
PRIZE_CHANCES = {
    "1 звезда": 40.0,
    "3 звезды": 20.0,
    "5 звезд": 15.0,
    "10 звезд": 15.0,
    "50 звезд": 5.0,
    "100 звезд": 3.0,
    "500 звезд": 1.5,
    "NFT": 0.5,  # Добавил NFT с шансом 0.5%
    "Проигрыш": 0.0  # Проигрыш рассчитывается автоматически
}

# Пересчитываем проигрыш чтобы сумма была 100%
total_chance = sum(PRIZE_CHANCES.values())
PRIZE_CHANCES["Проигрыш"] = 100.0 - total_chance

PRIZE_VALUES = {
    "1 звезда": 1,
    "3 звезды": 3,
    "5 звезд": 5,
    "10 звезд": 10,
    "50 звезд": 50,
    "100 звезд": 100,
    "500 звезд": 500,
    "NFT": 0,  # NFT не дает звезд, добавляется в инвентарь
    "Проигрыш": 0
}

# Шансы для ежедневного подарка (только NFT с шансом 0.001%)
DAILY_GIFT_CHANCES = {
    "NFT": 0.001,  # Только NFT в ежедневном подарке с шансом 0.001%
    "Проигрыш": 99.999  # Добавлен проигрыш для баланса
}

# Подарки в виде ячеек рулетки (реальные шансы изменены для Алмаза и Кубка)
GIFTS_CELLS = [
    {"name": "Алмаз", "emoji": "💎", "cell_emoji": "💎💎", "cost": 45, "chance_display": 40, "chance_real": 30, "sell_price": 20},  # Изменено с 25 на 30%
    {"name": "Кубок", "emoji": "🏆", "cell_emoji": "🏆🏆", "cost": 45, "chance_display": 40, "chance_real": 30, "sell_price": 20},  # Изменено с 25 на 30%
    {"name": "Ракета", "emoji": "🚀", "cell_emoji": "🚀🚀", "cost": 25, "chance_display": 40, "chance_real": 25, "sell_price": 10},
    {"name": "Шампанское", "emoji": "🍾", "cell_emoji": "🍾🍾", "cost": 25, "chance_display": 40, "chance_real": 25, "sell_price": 10},
    {"name": "Торт", "emoji": "🎂", "cell_emoji": "🎂🎂", "cost": 25, "chance_display": 40, "chance_real": 25, "sell_price": 10},
    {"name": "Розы", "emoji": "🌹", "cell_emoji": "🌹🌹", "cost": 12, "chance_display": 40, "chance_real": 25, "sell_price": 5},
    {"name": "Подарок", "emoji": "🎁", "cell_emoji": "🎁🎁", "cost": 12, "chance_display": 40, "chance_real": 25, "sell_price": 5},
    {"name": "Сердечко", "emoji": "💖", "cell_emoji": "💖💖", "cost": 12, "chance_display": 40, "chance_real": 25, "sell_price": 5},
    {"name": "Мишка", "emoji": "🧸", "cell_emoji": "🧸🧸", "cost": 8, "chance_display": 40, "chance_real": 25, "sell_price": 3}
]

# NFT ячейки - ИЗМЕНЕНЫ ЦЕНЫ И ШАНСЫ
NFT_CELLS = [
    {"cell": 1, "cost": 5, "chance_display": 1.0, "chance_real": 1.0, "description": "1% шанс"},
    {"cell": 2, "cost": 50, "chance_display": 10.0, "chance_real": 8.0, "description": "10% шанс"},
    {"cell": 3, "cost": 175, "chance_display": 45.0, "chance_real": 25.0, "description": "45% шанс"}  # Изменено с 30 на 25%
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
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name) 
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))

        cursor.execute('''
            UPDATE users SET username = ?, first_name = ? 
            WHERE user_id = ? AND (username != ? OR first_name != ?)
        ''', (username, first_name, user_id, username, first_name))

        conn.commit()

        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        stars = result[0] if result else 0

        await message.answer(
            f"<b>🎁 Добро пожаловать в Vitcoin gifts!</b>\n\n"
            f"✨ <b>Твои звёзды:</b> {stars}\n\n"
            f"🎰 <b>Открывай подарочки за 25 звезд!</b>\n"
            f"🎁 <b>Бесплатный NFT подарок раз в 24 часа с шансом 0.001%!</b>\n\n"
            f"💰 <b>Пополнить баланс:</b> нажмите кнопку 'Депозит'\n"
            f"🛟 <b>Нужна помощь?</b> нажмите 'Поддержка'",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="HTML"
        )
        logger.info(f"Приветственное сообщение отправлено пользователю {user_id}")

    except Exception as e:
        logger.error(f"Ошибка при обработке /start: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

# ========== ОБРАБОТЧИКИ КОЛБЭКОВ ==========

@dp.callback_query(F.data == "open_gift")
async def open_gift(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    logger.info(f"Пользователь {user_id} пытается открыть подарок")

    try:
        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            await callback.answer("❌ Пользователь не найден. Напишите /start", show_alert=True)
            return

        stars = result[0]

        if stars < 25:  # Изменено с 30 на 25
            await callback.answer("❌ Недостаточно звёзд! Нужно минимум 25 звёзд для открытия.", show_alert=True)
            return

        new_stars = stars - 25  # Изменено с 30 на 25
        cursor.execute('UPDATE users SET stars = ?, total_opened = total_opened + 1 WHERE user_id = ?', 
                       (new_stars, user_id))

        prize = random.choices(
            list(PRIZE_CHANCES.keys()),
            weights=list(PRIZE_CHANCES.values())
        )[0]

        if prize != "Проигрыш":
            if prize == "NFT":
                # NFT добавляем в инвентарь как предмет
                gift_name = "NFT"
                gift_emoji = "💎"
                gift_value = 1000  # Стоимость NFT
                
                # Добавляем NFT в инвентарь
                cursor.execute('''
                    INSERT INTO user_gifts (user_id, gift_name, gift_emoji, gift_value, timestamp) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, gift_name, gift_emoji, gift_value, datetime.now().isoformat()))
                
                # Увеличиваем счетчик NFT
                cursor.execute('UPDATE users SET nft_won = nft_won + 1 WHERE user_id = ?', (user_id,))
                
                result_text = f"💎 <b>Поздравляем! Ты выиграл:</b> NFT\n📊 <b>Шанс выигрыша:</b> 0.5%\n\n✨ <b>Твои звёзды:</b> {new_stars}\n\n🎒 <b>NFT добавлен в ваш инвентарь!</b>"
            else:
                # Обычные призы (звезды)
                prize_value = PRIZE_VALUES[prize]
                new_stars += prize_value
                cursor.execute('UPDATE users SET stars = ? WHERE user_id = ?', (new_stars, user_id))
                result_text = f"⭐ <b>Поздравляем! Ты выиграл:</b> {prize}\n📊 <b>Шанс выигрыша:</b> {PRIZE_CHANCES[prize]}%\n\n✨ <b>Твои звёзды:</b> {new_stars}"

            # Запись выигрыша
            cursor.execute('''
                INSERT INTO wins (user_id, username, prize_type, prize_value, chance, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, prize, prize_value if prize != "NFT" else 1000, PRIZE_CHANCES[prize], datetime.now().isoformat()))

            # Запись транзакции
            if prize != "NFT":
                cursor.execute('''
                    INSERT INTO transactions (user_id, username, amount, type, timestamp) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, username, prize_value, "win", datetime.now().isoformat()))

            # Уведомление админа о большом выигрыше или NFT
            if prize == "NFT" or prize_value >= 500:
                try:
                    await bot.send_message(
                        ADMIN_ID,
                        f"🎉 <b>КРУПНЫЙ ВЫИГРЫШ!</b>\n\n"
                        f"👤 Пользователь: @{username if username else 'нет'}\n"
                        f"🆔 ID: {user_id}\n"
                        f"🎁 Приз: {prize}\n"
                        f"⭐ Значение: {1000 if prize == 'NFT' else prize_value} звезд\n"
                        f"📊 Шанс: {PRIZE_CHANCES[prize]}%\n"
                        f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу: {e}")
        else:
            result_text = f"😔 <b>К сожалению, ты ничего не выиграл...</b>\n\n✨ <b>Твои звёзды:</b> {new_stars}\n🎰 <b>Попробуй ещё раз!</b>"

        conn.commit()

        # Отправка результата
        await callback.message.edit_text(
            f"<b>🎁 Результат открытия:</b>\n\n{result_text}",
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
            # Определяем результат с шансом 0.001%
            is_nft_win = random.random() * 100 < 0.001  # 0.001% шанс
            
            # Обновляем время последнего использования
            cursor.execute('''
                UPDATE users 
                SET free_gift_used = free_gift_used + 1,
                    last_free_gift_date = ?,
                    total_opened = total_opened + 1
                WHERE user_id = ?
            ''', (now.isoformat(), user_id))

            if is_nft_win:
                # Выигрыш NFT - добавляем в инвентарь как отдельный предмет
                gift_name = "NFT"
                gift_emoji = "💎"
                gift_value = 1000  # Стоимость NFT
                
                # Добавляем NFT в инвентарь (НЕ добавляем звезды на баланс!)
                cursor.execute('''
                    INSERT INTO user_gifts (user_id, gift_name, gift_emoji, gift_value, timestamp) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, gift_name, gift_emoji, gift_value, now.isoformat()))
                
                # Увеличиваем счетчик NFT
                cursor.execute('UPDATE users SET nft_won = nft_won + 1 WHERE user_id = ?', (user_id,))

                # Получение баланса (без изменения)
                cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
                stars_result = cursor.fetchone()
                current_stars = stars_result[0] if stars_result else 0

                # Запись выигрыша
                cursor.execute('''
                    INSERT INTO wins (user_id, username, prize_type, prize_value, chance, timestamp) 
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, username, "NFT", gift_value, 0.001, now.isoformat()))

                # Запись транзакции
                cursor.execute('''
                    INSERT INTO transactions (user_id, username, amount, type, timestamp) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, username, gift_value, "daily_nft_win", now.isoformat()))

                conn.commit()

                # Отправка результата ТОЛЬКО ПРИ ВЫИГРЫШЕ
                await callback.message.edit_text(
                    f"<b>🎁 Бесплатный NFT подарок:</b>\n\n"
                    f"💎 <b>Поздравляем! Ты выиграл:</b> NFT\n"
                    f"📊 <b>Шанс выигрыша:</b> 0.001%\n\n"
                    f"✨ <b>Твои звёзды:</b> {current_stars}\n"
                    f"🎒 <b>NFT добавлен в ваш инвентарь!</b>\n"
                    f"🕐 <b>Следующий бесплатный NFT подарок через 24 часа</b>\n\n"
                    f"<i>Можете вывести или продать NFT в разделе 'Инвентарь'</i>",
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
                        f"🎁 Приз: NFT\n"
                        f"💰 Стоимость: {gift_value} звезд\n"
                        f"📊 Шанс: 0.001%\n"
                        f"⏰ Время: {now.strftime('%H:%M %d.%m.%Y')}\n"
                        f"🎯 Тип: Ежедневный NFT подарок",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу: {e}")
            else:
                # Проигрыш - НЕ ПОКАЗЫВАЕМ РЕЗУЛЬТАТ
                conn.commit()
                
                # Получение баланса
                cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
                stars_result = cursor.fetchone()
                current_stars = stars_result[0] if stars_result else 0
                
                # Просто показываем сообщение о том, что подарок использован
                await callback.message.edit_text(
                    f"<b>🎁 Бесплатный NFT подарок использован</b>\n\n"
                    f"✨ <b>Твои звёзды:</b> {current_stars}\n"
                    f"🕐 <b>Следующий бесплатный NFT подарок через 24 часа</b>\n\n"
                    f"<i>Попробуй ещё раз через 24 часа!</i>",
                    reply_markup=get_main_menu_keyboard(user_id),
                    parse_mode="HTML"
                )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении бесплатного NFT подарка: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@dp.callback_query(F.data == "gifts_section")
async def gifts_section(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    stars = result[0] if result else 0

    keyboard = InlineKeyboardBuilder()

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
        f"• Шанс выигрыша: 40%\n"
        f"• При выигрыше подарок добавляется в инвентарь\n"
        f"• Подарки можно продать по цене в инвентаре\n\n"
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

    gift = None
    for g in GIFTS_CELLS:
        if g["name"].lower() == gift_name_lower:
            gift = g
            break

    if not gift:
        await callback.answer("❌ Подарок не найден", show_alert=True)
        return

    try:
        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        stars = result[0]

        if stars < gift["cost"]:
            await callback.answer(f"❌ Недостаточно звёзд! Нужно {gift['cost']}⭐", show_alert=True)
            return

        new_stars = stars - gift["cost"]
        cursor.execute('UPDATE users SET stars = ? WHERE user_id = ?', (new_stars, user_id))

        # Используем реальный шанс (для Алмаза и Кубка 30%, для остальных 25%)
        is_win = random.random() * 100 < gift["chance_real"]

        if is_win:
            cursor.execute('''
                INSERT INTO user_gifts (user_id, gift_name, gift_emoji, gift_value, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, gift["name"], gift["emoji"], gift["sell_price"], datetime.now().isoformat()))

            cursor.execute('UPDATE users SET gifts_won = gifts_won + 1 WHERE user_id = ?', (user_id,))

            cursor.execute('''
                INSERT INTO wins (user_id, username, prize_type, prize_value, chance, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, f"Подарок {gift['name']}", gift["sell_price"], gift["chance_display"], datetime.now().isoformat()))

            cursor.execute('''
                INSERT INTO transactions (user_id, username, amount, type, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, gift["cost"], "gift_win", datetime.now().isoformat()))

            result_text = (
                f"🎉 <b>Поздравляем! Вы выиграли:</b>\n"
                f"{gift['emoji']} <b>{gift['name']}</b>\n"
                f"💰 <b>Цена покупки:</b> {gift['cost']}⭐\n"
                f"💰 <b>Цена продажи:</b> {gift['sell_price']}⭐\n"
                f"📊 <b>Шанс:</b> {gift['chance_display']}%\n\n"
                f"🎁 <b>Подарок добавлен в ваш инвентарь!</b>\n"
                f"✨ <b>Можете продать или вывести его в разделе 'Инвентарь'</b>"
            )

            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"🎁 <b>ПОДАРОК ВЫИГРАН!</b>\n\n"
                    f"👤 Пользователь: @{username if username else 'нет'}\n"
                    f"🆔 ID: {user_id}\n"
                    f"🎁 Приз: {gift['name']}\n"
                    f"💰 Стоимость покупки: {gift['cost']} звезд\n"
                    f"💰 Цена продажи: {gift['sell_price']} звезд\n"
                    f"📊 Шанс: {gift['chance_display']}%\n"
                    f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
                    f"🎯 Тип: Ячейка подарков",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу: {e}")
        else:
            cursor.execute('''
                INSERT INTO transactions (user_id, username, amount, type, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, gift["cost"], "gift_lose", datetime.now().isoformat()))

            result_text = (
                f"😔 <b>К сожалению, не повезло</b>\n"
                f"🎯 <b>Цель:</b> {gift['emoji']} {gift['name']}\n"
                f"💰 <b>Стоимость попытки:</b> {gift['cost']}⭐\n"
                f"📊 <b>Шанс был:</b> {gift['chance_display']}%\n\n"
                f"💫 <b>Попробуйте ещё раз!</b>"
            )

        conn.commit()

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
        # Получаем ВСЕ активные подарки пользователя
        cursor.execute('''
            SELECT id, gift_emoji, gift_name, gift_value 
            FROM user_gifts 
            WHERE user_id = ? AND status = 'active'
            ORDER BY CASE 
                WHEN gift_name = 'NFT' THEN 1
                ELSE 2
            END, gift_name, timestamp DESC
        ''', (user_id,))

        gifts = cursor.fetchall()

        # Считаем количество каждого типа подарка
        gift_counts = {}
        nft_count = 0
        
        for gift_id, emoji, name, value in gifts:
            if name == "NFT":
                nft_count += 1
            else:
                key = f"{emoji} {name}"
                if key in gift_counts:
                    gift_counts[key]["count"] += 1
                    gift_counts[key]["ids"].append(gift_id)
                else:
                    gift_counts[key] = {"emoji": emoji, "name": name, "value": value, "count": 1, "ids": [gift_id]}

        # Получаем NFT отдельно
        cursor.execute('''
            SELECT id FROM user_gifts 
            WHERE user_id = ? AND status = 'active' AND gift_name = 'NFT'
            ORDER BY timestamp DESC
        ''', (user_id,))
        
        nft_gifts = cursor.fetchall()
        nft_ids = [nft[0] for nft in nft_gifts]

        keyboard = InlineKeyboardBuilder()

        if not gifts and nft_count == 0:
            inventory_text = "📭 <b>Ваш инвентарь пуст</b>\n\n🎁 <b>Попробуйте ячейки подарков!</b>"
            keyboard.row(InlineKeyboardButton(text="🎁 Ячейки подарков", callback_data="gifts_section"))
            keyboard.row(InlineKeyboardButton(text="💎 NFT ячейки", callback_data="nft_cells"))
            keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
        else:
            inventory_text = "<b>🎁 Ваши подарки (нажмите для вывода или продажи):</b>\n"
            total_gift_count = len(gifts)

            # Показываем обычные подарки с количеством
            for gift_info in gift_counts.values():
                inventory_text += f"{gift_info['emoji']} {gift_info['name']}: {gift_info['value']}⭐ (x{gift_info['count']})\n"
            
            # Показываем NFT отдельно
            if nft_count > 0:
                inventory_text += f"\n💎 <b>NFT:</b> {nft_count} шт. (1000⭐ каждый)\n"
            
            # Добавляем кнопки для обычных подарков (продажа и вывод)
            for gift_info in gift_counts.values():
                if gift_info["count"] > 1:
                    # Для нескольких одинаковых подарков создаем кнопки для каждого
                    for i, gift_id in enumerate(gift_info["ids"], 1):
                        keyboard.row(
                            InlineKeyboardButton(
                                text=f"💰 Продать {gift_info['emoji']} {gift_info['name']} #{i} ({gift_info['value']}⭐)",
                                callback_data=f"sell_gift_{gift_id}"
                            ),
                            InlineKeyboardButton(
                                text=f"📤 Вывести {gift_info['emoji']} {gift_info['name']} #{i}",
                                callback_data=f"withdraw_gift_{gift_id}"
                            )
                        )
                else:
                    # Для одного подарка
                    keyboard.row(
                        InlineKeyboardButton(
                            text=f"💰 Продать {gift_info['emoji']} {gift_info['name']} ({gift_info['value']}⭐)",
                            callback_data=f"sell_gift_{gift_info['ids'][0]}"
                        ),
                        InlineKeyboardButton(
                            text=f"📤 Вывести {gift_info['emoji']} {gift_info['name']}",
                            callback_data=f"withdraw_gift_{gift_info['ids'][0]}"
                        )
                    )
            
            # Добавляем кнопки для NFT (только вывод)
            if nft_count > 0:
                for i, nft_id in enumerate(nft_ids, 1):
                    keyboard.row(
                        InlineKeyboardButton(
                            text=f"💰 Продать 💎 NFT #{i} (1000⭐)",
                            callback_data=f"sell_gift_{nft_id}"
                        ),
                        InlineKeyboardButton(
                            text=f"📤 Вывести 💎 NFT #{i}",
                            callback_data=f"withdraw_gift_{nft_id}"
                        )
                    )

            inventory_text += f"\n<b>📊 Всего предметов:</b> {total_gift_count}"

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

# Новая функция для продажи подарка
@dp.callback_query(F.data.startswith("sell_gift_"))
async def sell_gift(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    gift_id = int(callback.data.split("_")[2])

    try:
        cursor.execute('''
            SELECT gift_name, gift_emoji, gift_value 
            FROM user_gifts 
            WHERE id = ? AND user_id = ? AND status = 'active'
        ''', (gift_id, user_id))

        gift_info = cursor.fetchone()

        if not gift_info:
            await callback.answer("❌ Подарок не найден или уже продан/выведен", show_alert=True)
            return

        gift_name, gift_emoji, gift_value = gift_info

        # Помечаем подарок как проданный
        cursor.execute('UPDATE user_gifts SET status = "sold" WHERE id = ?', (gift_id,))

        # Добавляем звезды на баланс
        cursor.execute('UPDATE users SET stars = stars + ? WHERE user_id = ?', (gift_value, user_id))

        # Получаем новый баланс
        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        new_stars_result = cursor.fetchone()
        new_stars = new_stars_result[0] if new_stars_result else gift_value

        # Записываем транзакцию продажи
        cursor.execute('''
            INSERT INTO transactions (user_id, username, amount, type, timestamp) 
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, gift_value, "sell_gift", datetime.now().isoformat()))

        conn.commit()

        await callback.message.edit_text(
            f"<b>✅ Подарок успешно продан!</b>\n\n"
            f"🎁 <b>Продан:</b> {gift_emoji} {gift_name}\n"
            f"💰 <b>Получено:</b> {gift_value}⭐\n"
            f"✨ <b>Ваш баланс:</b> {new_stars}⭐\n\n"
            f"<i>Подарок удален из вашего инвентаря.</i>",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="HTML"
        )

        # Уведомление админа о продаже NFT
        if gift_name == "NFT":
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"💰 <b>NFT ПРОДАН!</b>\n\n"
                    f"👤 Пользователь: @{username if username else 'нет'}\n"
                    f"🆔 ID: {user_id}\n"
                    f"🎁 Подарок: {gift_emoji} {gift_name}\n"
                    f"💰 Получено: {gift_value} звезд\n"
                    f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу: {e}")

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при продаже подарка: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@dp.callback_query(F.data.startswith("withdraw_gift_"))
async def withdraw_gift(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    gift_id = int(callback.data.split("_")[2])

    try:
        cursor.execute('''
            SELECT gift_name, gift_emoji, gift_value 
            FROM user_gifts 
            WHERE id = ? AND user_id = ? AND status = 'active'
        ''', (gift_id, user_id))

        gift_info = cursor.fetchone()

        if not gift_info:
            await callback.answer("❌ Подарок не найден или уже продан/выведен", show_alert=True)
            return

        gift_name, gift_emoji, gift_value = gift_info

        cursor.execute('UPDATE user_gifts SET status = "withdrawn" WHERE id = ?', (gift_id,))

        cursor.execute('''
            INSERT INTO withdrawal_requests (user_id, username, gift_name, gift_emoji, gift_value, timestamp, support_username)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, gift_name, gift_emoji, gift_value, datetime.now().isoformat(), SUPPORT_USERNAME))

        conn.commit()

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
        "• NFT = добавляется в инвентарь как предмет\n"
        "• Можете продать или вывести NFT через раздел 'Инвентарь'\n\n"
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

    cell_data = None
    for cell in NFT_CELLS:
        if cell["cell"] == cell_num:
            cell_data = cell
            break

    if not cell_data:
        await callback.answer("❌ Ячейка не найден", show_alert=True)
        return

    try:
        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        stars = result[0]

        if stars < cell_data["cost"]:
            await callback.answer(f"❌ Недостаточно звёзд! Нужно {cell_data['cost']}⭐", show_alert=True)
            return

        new_stars = stars - cell_data["cost"]
        cursor.execute('UPDATE users SET stars = ?, nft_cells_opened = nft_cells_opened + 1 WHERE user_id = ?', 
                      (new_stars, user_id))

        # Используем РЕАЛЬНЫЙ шанс (не отображаемый)
        is_nft_win = random.random() * 100 < cell_data["chance_real"]

        if is_nft_win:
            # Выигрыш NFT - добавляем в инвентарь как отдельный предмет
            gift_name = "NFT"
            gift_emoji = "💎"
            gift_value = 1000  # Стоимость NFT
            
            # Добавляем NFT в инвентарь (НЕ добавляем звезды на баланс!)
            cursor.execute('''
                INSERT INTO user_gifts (user_id, gift_name, gift_emoji, gift_value, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, gift_name, gift_emoji, gift_value, datetime.now().isoformat()))
            
            # Увеличиваем счетчик NFT
            cursor.execute('UPDATE users SET nft_won = nft_won + 1 WHERE user_id = ?', (user_id,))

            cursor.execute('''
                INSERT INTO wins (user_id, username, prize_type, prize_value, chance, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, "NFT из ячейки", gift_value, cell_data["chance_display"], datetime.now().isoformat()))

            cursor.execute('''
                INSERT INTO transactions (user_id, username, amount, type, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, gift_value, "nft_cell_win", datetime.now().isoformat()))

            result_text = f"🎉 <b>Поздравляем! Вы выиграли NFT!</b>\n💎 <b>NFT добавлен в ваш инвентарь!</b>\n📊 <b>Шанс:</b> {cell_data['chance_display']}%"

            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"🎉 <b>NFT ИЗ ЯЧЕЙКИ!</b>\n\n"
                    f"👤 Пользователь: @{username if username else 'нет'}\n"
                    f"🆔 ID: {user_id}\n"
                    f"🎁 Приз: NFT\n"
                    f"💰 Стоимость: {gift_value} звезд\n"
                    f"📊 Шанс: {cell_data['chance_display']}%\n"
                    f"🎯 Ячейка: {cell_num}\n"
                    f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу: {e}")
        else:
            cursor.execute('''
                INSERT INTO nft_cells (user_id, cell_type, cost, chance, result, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, cell_num, cell_data["cost"], cell_data["chance_display"], False, datetime.now().isoformat()))

            result_text = f"😔 <b>К сожалению, NFT не выпал</b>\n📊 <b>Шанс был:</b> {cell_data['chance_display']}%"

        conn.commit()

        cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
        final_stars = cursor.fetchone()[0]

        nft_note = "\n\n<i>NFT добавлен в инвентарь. Можете продать или вывести его в разделе 'Инвентарь'!</i>" if is_nft_win else ""

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
            f"🎁 <b>Для открытия подарочка нужно 25 звёзд</b>\n"
            f"💎 <b>Бесплатный NFT подарок с шансом 0.001%!</b>\n\n"
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

# ========== ЗАПУСК БОТА ==========

async def main():
    logger.info("Инициализация базы данных...")
    init_db()

    logger.info("Запуск бота...")

    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        keep_alive()
        logger.info("Keep-alive сервер запущен")

        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
