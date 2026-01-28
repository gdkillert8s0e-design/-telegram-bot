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

# Настройки бота
TOKEN = "8005337864:AAGmI78aZNxvJqMyW9nkP4JoMDEFR4xB4tc"
ADMIN_IDS = [1989613788, 5883796026]
SUPPORT_USERNAME = "@ownsuicude"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Флаг для рассылки
broadcast_mode = {}

# База данных
conn = sqlite3.connect('onegifts.db', check_same_thread=False, isolation_level=None)
cursor = conn.cursor()

def init_db():
    """Инициализация базы данных"""
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

# Шансы выигрыша
PRIZE_CHANCES = {
    "1 звезда": 40.0, "3 звезды": 20.0, "5 звезд": 15.0,
    "10 звезд": 15.0, "50 звезд": 5.0, "100 звезд": 3.0,
    "500 звезд": 1.5, "NFT": 0.5, "Проигрыш": 0.0
}
total_chance = sum(PRIZE_CHANCES.values())
PRIZE_CHANCES["Проигрыш"] = 100.0 - total_chance

PRIZE_VALUES = {
    "1 звезда": 1, "3 звезды": 3, "5 звезд": 5,
    "10 звезд": 10, "50 звезд": 50, "100 звезд": 100,
    "500 звезд": 500, "NFT": 0, "Проигрыш": 0
}

# Подарки
GIFTS = [
    {"name": "Алмаз", "emoji": "💎", "cell_emoji": "💎💎", "cost": 45, "sell": 100},
    {"name": "Кубок", "emoji": "🏆", "cell_emoji": "🏆🏆", "cost": 45, "sell": 100},
    {"name": "Ракета", "emoji": "🚀", "cell_emoji": "🚀🚀", "cost": 25, "sell": 50},
    {"name": "Шампанское", "emoji": "🍾", "cell_emoji": "🍾🍾", "cost": 25, "sell": 50},
    {"name": "Торт", "emoji": "🎂", "cell_emoji": "🎂🎂", "cost": 25, "sell": 50},
    {"name": "Розы", "emoji": "🌹", "cell_emoji": "🌹🌹", "cost": 12, "sell": 25},
    {"name": "Подарок", "emoji": "🎁", "cell_emoji": "🎁🎁", "cost": 12, "sell": 25},
    {"name": "Сердечко", "emoji": "💖", "cell_emoji": "💖💖", "cost": 12, "sell": 15},
    {"name": "Мишка", "emoji": "🧸", "cell_emoji": "🧸🧸", "cost": 8, "sell": 15}
]

# NFT ячейки
NFT_CELLS = [
    {"cell": 1, "cost": 5, "chance": 1.0, "desc": "1% шанс"},
    {"cell": 2, "cost": 50, "chance": 10.0, "desc": "10% шанс"},
    {"cell": 3, "cost": 175, "chance": 45.0, "desc": "45% шанс"}
]

# Вспомогательные функции
def get_main_menu(user_id):
    """Главное меню"""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🎁 Открыть подарочек", callback_data="open_gift"),
        InlineKeyboardButton(text="⭐ Мои звёзды", callback_data="my_stars")
    )
    kb.row(
        InlineKeyboardButton(text="🎁 Бесплатный NFT подарок", callback_data="free_nft_gift"),
        InlineKeyboardButton(text="🎁 Подарки", callback_data="gifts_section")
    )
    kb.row(
        InlineKeyboardButton(text="💎 NFT ячейки", callback_data="nft_cells"),
        InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory")
    )
    kb.row(
        InlineKeyboardButton(text="💰 Депозит", callback_data="deposit"),
        InlineKeyboardButton(text="🛟 Поддержка", callback_data="support")
    )
    if user_id in ADMIN_IDS:
        kb.row(InlineKeyboardButton(text="👑 Админ панель", callback_data="admin_panel"))
    return kb.as_markup()

def get_user_data(user_id):
    """Получить данные пользователя"""
    cursor.execute('SELECT stars, deposit_total FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone() or (0, 0)

def update_user(user_id, username="", first_name=""):
    """Обновить/создать пользователя"""
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)', 
                   (user_id, username, first_name))
    cursor.execute('UPDATE users SET username = ?, first_name = ? WHERE user_id = ?', 
                   (username, first_name, user_id))
    conn.commit()

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    """Команда /start"""
    user_id = message.from_user.id
    update_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
    
    stars, _ = get_user_data(user_id)
    await message.answer(
        f"<b>🎁 Добро пожаловать в Vitcoin gifts!</b>\n\n"
        f"✨ <b>Твои звёзды:</b> {stars}\n\n"
        f"🎰 <b>Открывай подарочки за 25 звезд!</b>\n"
        f"🎁 <b>Бесплатный NFT подарок раз в 24 часа с шансом 0.1%!</b>\n\n"
        f"💰 <b>Пополнить баланс:</b> нажмите 'Депозит'\n"
        f"🛟 <b>Нужна помощь?</b> нажмите 'Поддержка'",
        reply_markup=get_main_menu(user_id),
        parse_mode="HTML"
    )

# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========

@dp.callback_query(F.data == "open_gift")
async def open_gift_handler(callback: types.CallbackQuery):
    """Открытие подарка с подтверждением"""
    user_id = callback.from_user.id
    stars, _ = get_user_data(user_id)
    
    if stars < 25:
        await callback.answer("❌ Недостаточно звёзд! Нужно 25⭐", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Да, открыть", callback_data="confirm_open"),
        InlineKeyboardButton(text="❌ Нет, отмена", callback_data="back_to_main")
    )
    
    await callback.message.edit_text(
        f"<b>🎁 Открытие подарочка</b>\n\n"
        f"✨ <b>Ваши звёзды:</b> {stars}\n"
        f"💰 <b>Стоимость открытия:</b> 25⭐\n\n"
        f"<b>Вы уверены, что хотите открыть подарочек за 25 звезд?</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "confirm_open")
async def confirm_open_handler(callback: types.CallbackQuery):
    """Подтвержденное открытие подарка"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
    stars = cursor.fetchone()[0]
    
    if stars < 25:
        await callback.answer("❌ Недостаточно звёзд!", show_alert=True)
        return
    
    # Списание звезд
    new_stars = stars - 25
    cursor.execute('UPDATE users SET stars = ?, total_opened = total_opened + 1 WHERE user_id = ?', 
                   (new_stars, user_id))
    
    # Выбор приза
    prize = random.choices(list(PRIZE_CHANCES.keys()), weights=list(PRIZE_CHANCES.values()))[0]
    
    if prize == "Проигрыш":
        result_text = f"😔 <b>К сожалению, ты ничего не выиграл...</b>\n\n✨ <b>Твои звёзды:</b> {new_stars}"
    elif prize == "NFT":
        gift_value = 400
        cursor.execute('INSERT INTO user_gifts (user_id, gift_name, gift_emoji, gift_value, timestamp) VALUES (?, ?, ?, ?, ?)',
                       (user_id, "NFT", "💎", gift_value, datetime.now().isoformat()))
        cursor.execute('UPDATE users SET nft_won = nft_won + 1 WHERE user_id = ?', (user_id,))
        result_text = f"💎 <b>Поздравляем! Ты выиграл NFT!</b>\n📊 <b>Шанс:</b> 0.5%\n\n✨ <b>Твои звёзды:</b> {new_stars}\n\n🎒 <b>NFT добавлен в инвентарь!</b>"
        
        # Уведомление админам
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"🎉 NFT ВЫИГРАН! @{username} (ID: {user_id})")
    else:
        prize_value = PRIZE_VALUES[prize]
        new_stars += prize_value
        cursor.execute('UPDATE users SET stars = ? WHERE user_id = ?', (new_stars, user_id))
        result_text = f"⭐ <b>Поздравляем! Ты выиграл:</b> {prize}\n📊 <b>Шанс:</b> {PRIZE_CHANCES[prize]}%\n\n✨ <b>Твои звёзды:</b> {new_stars}"
    
    conn.commit()
    await callback.message.edit_text(f"<b>🎁 Результат открытия:</b>\n\n{result_text}", 
                                     reply_markup=get_main_menu(user_id), parse_mode="HTML")

@dp.callback_query(F.data == "free_nft_gift")
async def free_nft_handler(callback: types.CallbackQuery):
    """Бесплатный NFT подарок"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    cursor.execute('SELECT last_free_gift_date FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    now = datetime.now()
    if result and result[0]:
        last_date = datetime.fromisoformat(result[0])
        if (now - last_date) < timedelta(hours=24):
            next_time = last_date + timedelta(hours=24)
            time_left = next_time - now
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            await callback.answer(f"⏳ Доступно через {hours}ч {minutes}мин", show_alert=True)
            return
    
    # Обновление времени
    cursor.execute('UPDATE users SET free_gift_used = free_gift_used + 1, last_free_gift_date = ?, total_opened = total_opened + 1 WHERE user_id = ?',
                   (now.isoformat(), user_id))
    
    # Шанс 0.001%
    if random.random() * 100 < 0.001:
        gift_value = 400
        cursor.execute('INSERT INTO user_gifts (user_id, gift_name, gift_emoji, gift_value, timestamp) VALUES (?, ?, ?, ?, ?)',
                       (user_id, "NFT", "💎", gift_value, now.isoformat()))
        cursor.execute('UPDATE users SET nft_won = nft_won + 1 WHERE user_id = ?', (user_id,))
        result_text = f"💎 <b>Поздравляем! Ты выиграл NFT!</b>\n📊 <b>Шанс:</b> 0.001%\n\n🎒 <b>NFT добавлен в инвентарь!</b>"
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"🎉 БЕСПЛАТНЫЙ NFT! @{username} (ID: {user_id})")
    else:
        result_text = "🎁 <b>Бесплатный NFT подарок использован</b>\n\n🕐 <b>Следующий через 24 часа</b>"
    
    conn.commit()
    stars, _ = get_user_data(user_id)
    await callback.message.edit_text(
        f"<b>🎁 Бесплатный NFT подарок</b>\n\n{result_text}\n\n✨ <b>Твои звёзды:</b> {stars}",
        reply_markup=get_main_menu(user_id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "gifts_section")
async def gifts_handler(callback: types.CallbackQuery):
    """Раздел с подарками"""
    user_id = callback.from_user.id
    stars, _ = get_user_data(user_id)
    
    kb = InlineKeyboardBuilder()
    gifts_per_row = 3
    for i in range(0, len(GIFTS), gifts_per_row):
        row = GIFTS[i:i+gifts_per_row]
        buttons = [InlineKeyboardButton(text=f"{g['cell_emoji']} {g['cost']}⭐", 
                  callback_data=f"open_cell_{g['name'].lower()}") for g in row]
        kb.row(*buttons)
    
    kb.row(InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    
    await callback.message.edit_text(
        f"<b>🎁 Ячейки подарков</b>\n\n✨ <b>Баланс:</b> {stars}⭐\n\n"
        f"🎰 <b>Шанс выигрыша:</b> 40%\n"
        f"💰 <b>Цены продажи:</b>\n"
        f"💎 Алмаз/🏆 Кубок: 100⭐\n"
        f"🚀 Ракета/🍾 Шампанское/🎂 Торт: 50⭐\n"
        f"🌹 Розы/🎁 Подарок: 25⭐\n"
        f"💖 Сердечко/🧸 Мишка: 15⭐",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("open_cell_"))
async def open_cell_handler(callback: types.CallbackQuery):
    """Открытие ячейки подарка"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    gift_name = callback.data.split("_")[2]
    
    gift = next((g for g in GIFTS if g["name"].lower() == gift_name), None)
    if not gift:
        await callback.answer("❌ Подарок не найден", show_alert=True)
        return
    
    stars, _ = get_user_data(user_id)
    if stars < gift["cost"]:
        await callback.answer(f"❌ Нужно {gift['cost']}⭐", show_alert=True)
        return
    
    # Списание
    new_stars = stars - gift["cost"]
    cursor.execute('UPDATE users SET stars = ? WHERE user_id = ?', (new_stars, user_id))
    
    # Шанс 40%
    if random.random() * 100 < 40:
        cursor.execute('INSERT INTO user_gifts (user_id, gift_name, gift_emoji, gift_value, timestamp) VALUES (?, ?, ?, ?, ?)',
                       (user_id, gift["name"], gift["emoji"], gift["sell"], datetime.now().isoformat()))
        cursor.execute('UPDATE users SET gifts_won = gifts_won + 1 WHERE user_id = ?', (user_id,))
        result_text = f"🎉 <b>Вы выиграли {gift['emoji']} {gift['name']}!</b>\n💰 <b>Цена продажи:</b> {gift['sell']}⭐"
    else:
        result_text = f"😔 <b>Не повезло с {gift['emoji']} {gift['name']}</b>\n📊 <b>Шанс был:</b> 40%"
    
    conn.commit()
    final_stars, _ = get_user_data(user_id)
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🎁 Ещё раз", callback_data=f"open_cell_{gift_name}"))
    kb.row(InlineKeyboardButton(text="🎁 Другие подарки", callback_data="gifts_section"))
    kb.row(InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    
    await callback.message.edit_text(
        f"<b>🎰 Результат:</b>\n\n{result_text}\n\n✨ <b>Баланс:</b> {final_stars}⭐",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "inventory")
async def inventory_handler(callback: types.CallbackQuery):
    """Инвентарь"""
    user_id = callback.from_user.id
    
    cursor.execute('SELECT id, gift_emoji, gift_name, gift_value FROM user_gifts WHERE user_id = ? AND status = "active" ORDER BY timestamp DESC', (user_id,))
    gifts = cursor.fetchall()
    
    if not gifts:
        text = "📭 <b>Инвентарь пуст</b>"
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🎁 Ячейки подарков", callback_data="gifts_section"))
        kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    else:
        text = "<b>🎒 Ваш инвентарь:</b>\n"
        kb = InlineKeyboardBuilder()
        
        for gift_id, emoji, name, value in gifts:
            text += f"{emoji} {name}: {value}⭐\n"
            kb.row(
                InlineKeyboardButton(text=f"💰 Продать {emoji} {name} ({value}⭐)", callback_data=f"sell_{gift_id}"),
                InlineKeyboardButton(text=f"📤 Вывести {emoji} {name}", callback_data=f"withdraw_{gift_id}")
            )
        
        kb.row(InlineKeyboardButton(text="🎁 Ячейки подарков", callback_data="gifts_section"))
        kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("sell_"))
async def sell_handler(callback: types.CallbackQuery):
    """Продажа подарка"""
    user_id = callback.from_user.id
    gift_id = int(callback.data.split("_")[1])
    
    cursor.execute('SELECT gift_name, gift_emoji, gift_value FROM user_gifts WHERE id = ? AND user_id = ? AND status = "active"', (gift_id, user_id))
    gift = cursor.fetchone()
    
    if not gift:
        await callback.answer("❌ Подарок не найден", show_alert=True)
        return
    
    name, emoji, value = gift
    
    # Продажа
    cursor.execute('UPDATE user_gifts SET status = "sold" WHERE id = ?', (gift_id,))
    cursor.execute('UPDATE users SET stars = stars + ? WHERE user_id = ?', (value, user_id))
    cursor.execute('INSERT INTO transactions (user_id, username, amount, type, timestamp) VALUES (?, ?, ?, ?, ?)',
                   (user_id, callback.from_user.username or "", value, "sell", datetime.now().isoformat()))
    
    conn.commit()
    stars, _ = get_user_data(user_id)
    
    await callback.message.edit_text(
        f"<b>✅ Подарок продан!</b>\n\n"
        f"🎁 {emoji} {name}\n"
        f"💰 +{value}⭐\n\n"
        f"✨ <b>Баланс:</b> {stars}⭐",
        reply_markup=get_main_menu(user_id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("withdraw_"))
async def withdraw_handler(callback: types.CallbackQuery):
    """Вывод подарка"""
    user_id = callback.from_user.id
    gift_id = int(callback.data.split("_")[1])
    
    cursor.execute('SELECT gift_name, gift_emoji, gift_value FROM user_gifts WHERE id = ? AND user_id = ? AND status = "active"', (gift_id, user_id))
    gift = cursor.fetchone()
    
    if not gift:
        await callback.answer("❌ Подарок не найден", show_alert=True)
        return
    
    name, emoji, value = gift
    
    cursor.execute('UPDATE user_gifts SET status = "withdrawn" WHERE id = ?', (gift_id,))
    cursor.execute('INSERT INTO withdrawal_requests (user_id, username, gift_name, gift_emoji, gift_value, timestamp, support_username) VALUES (?, ?, ?, ?, ?, ?, ?)',
                   (user_id, callback.from_user.username or "", name, emoji, value, datetime.now().isoformat(), SUPPORT_USERNAME))
    
    conn.commit()
    
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"📤 НОВАЯ ЗАЯВКА НА ВЫВОД! @{callback.from_user.username or 'нет'} (ID: {user_id}) - {emoji} {name} ({value}⭐)")
    
    await callback.message.edit_text(
        f"<b>✅ Заявка на вывод создана!</b>\n\n"
        f"🎁 {emoji} {name}\n"
        f"💰 {value}⭐\n\n"
        f"👤 <b>Свяжитесь с поддержкой:</b>\n{SUPPORT_USERNAME}",
        reply_markup=get_main_menu(user_id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "nft_cells")
async def nft_cells_handler(callback: types.CallbackQuery):
    """NFT ячейки"""
    kb = InlineKeyboardBuilder()
    for cell in NFT_CELLS:
        kb.row(InlineKeyboardButton(text=f"Ячейка {cell['cell']} - {cell['cost']}⭐ ({cell['desc']})", 
              callback_data=f"nft_cell_{cell['cell']}"))
    
    kb.row(InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    
    await callback.message.edit_text(
        "<b>💎 NFT ячейки</b>\n\n"
        "🎯 <b>Откройте ячейку с шансом получить NFT:</b>\n"
        "• NFT добавляется в инвентарь\n"
        "• Можно продать за 400⭐ или вывести",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("nft_cell_"))
async def open_nft_cell_handler(callback: types.CallbackQuery):
    """Открытие NFT ячейки"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    cell_num = int(callback.data.split("_")[2])
    
    cell = next((c for c in NFT_CELLS if c["cell"] == cell_num), None)
    if not cell:
        await callback.answer("❌ Ячейка не найдена", show_alert=True)
        return
    
    stars, _ = get_user_data(user_id)
    if stars < cell["cost"]:
        await callback.answer(f"❌ Нужно {cell['cost']}⭐", show_alert=True)
        return
    
    # Списание
    new_stars = stars - cell["cost"]
    cursor.execute('UPDATE users SET stars = ?, nft_cells_opened = nft_cells_opened + 1 WHERE user_id = ?', 
                   (new_stars, user_id))
    
    # Шанс (реальный ниже отображаемого)
    real_chance = cell["chance"] * 0.8  # 80% от отображаемого
    if random.random() * 100 < real_chance:
        gift_value = 400
        cursor.execute('INSERT INTO user_gifts (user_id, gift_name, gift_emoji, gift_value, timestamp) VALUES (?, ?, ?, ?, ?)',
                       (user_id, "NFT", "💎", gift_value, datetime.now().isoformat()))
        cursor.execute('UPDATE users SET nft_won = nft_won + 1 WHERE user_id = ?', (user_id,))
        result_text = f"🎉 <b>Вы выиграли NFT!</b>\n📊 <b>Шанс:</b> {cell['chance']}%"
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"🎉 NFT ИЗ ЯЧЕЙКИ {cell_num}! @{username} (ID: {user_id})")
    else:
        result_text = f"😔 <b>NFT не выпал</b>\n📊 <b>Шанс был:</b> {cell['chance']}%"
    
    conn.commit()
    final_stars, _ = get_user_data(user_id)
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💎 Ещё ячейку", callback_data="nft_cells"))
    kb.row(InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    
    await callback.message.edit_text(
        f"<b>💎 Ячейка {cell_num}</b>\n\n"
        f"💰 <b>Стоимость:</b> {cell['cost']}⭐\n"
        f"{result_text}\n\n"
        f"✨ <b>Баланс:</b> {final_stars}⭐",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "deposit")
async def deposit_handler(callback: types.CallbackQuery):
    """Раздел депозита"""
    user_id = callback.from_user.id
    
    cursor.execute('SELECT amount, status, timestamp FROM deposits WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10', (user_id,))
    deposits = cursor.fetchall()
    
    history = ""
    if deposits:
        history = "\n<b>📜 История:</b>\n"
        for amount, status, timestamp in deposits:
            emoji = "✅" if status == "completed" else "⏳" if status == "pending" else "❌"
            date = datetime.fromisoformat(timestamp).strftime('%d.%m')
            history += f"{emoji} {amount}⭐ - {status} ({date})\n"
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📤 Создать депозит", callback_data="create_deposit"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    
    await callback.message.edit_text(
        f"<b>💰 Депозит</b>\n\n"
        f"💳 <b>Как пополнить:</b>\n"
        f"1. Нажмите 'Создать депозит'\n"
        f"2. Укажите сумму\n"
        f"3. Отправьте {SUPPORT_USERNAME} звёзды\n"
        f"4. Пришлите скриншот\n"
        f"5. Ждите подтверждения\n\n"
        f"👤 <b>Саппорт:</b> {SUPPORT_USERNAME}{history}",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "create_deposit")
async def create_deposit_handler(callback: types.CallbackQuery):
    """Создание депозита"""
    await callback.message.edit_text(
        f"<b>📤 Создание депозита</b>\n\n"
        f"💳 <b>Инструкция:</b>\n"
        f"1. Решите сумму\n"
        f"2. Отправьте звёзды {SUPPORT_USERNAME}\n"
        f"3. Сделайте скриншот\n"
        f"4. Отправьте мне: <code>депозит 100</code>\n\n"
        f"👤 <b>Саппорт:</b> {SUPPORT_USERNAME}",
        parse_mode="HTML"
    )

@dp.message(F.text.startswith("депозит"))
async def deposit_message_handler(message: types.Message):
    """Обработчик сообщения депозита"""
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Формат: <code>депозит 100</code>", parse_mode="HTML")
            return
        
        amount = int(parts[1])
        if amount <= 0:
            await message.answer("❌ Сумма > 0")
            return
        
        user_id = message.from_user.id
        username = message.from_user.username or ""
        
        cursor.execute('INSERT INTO deposits (user_id, username, amount, timestamp) VALUES (?, ?, ?, ?)',
                       (user_id, username, amount, datetime.now().isoformat()))
        conn.commit()
        
        await message.answer(
            f"✅ <b>Заявка создана!</b>\n\n"
            f"💰 <b>Сумма:</b> {amount}⭐\n"
            f"👤 <b>Саппорт:</b> {SUPPORT_USERNAME}\n\n"
            f"<i>Отправьте {SUPPORT_USERNAME} {amount}⭐ и скриншот</i>",
            parse_mode="HTML"
        )
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"💰 НОВАЯ ЗАЯВКА НА ДЕПОЗИТ! @{username} (ID: {user_id}) - {amount}⭐")
            
    except ValueError:
        await message.answer("❌ Неверная сумма")
    except Exception as e:
        logger.error(f"Ошибка депозита: {e}")
        await message.answer("❌ Ошибка")

@dp.callback_query(F.data == "support")
async def support_handler(callback: types.CallbackQuery):
    """Поддержка"""
    await callback.message.edit_text(
        f"<b>🛟 Поддержка</b>\n\n"
        f"🛠️ <b>Нужна помощь?</b>\n"
        f"• По вопросам депозитов\n"
        f"• По техническим проблемам\n"
        f"• По вопросам сотрудничества\n\n"
        f"👤 <b>Саппорт:</b> {SUPPORT_USERNAME}\n\n"
        f"💬 <b>Напишите напрямую:</b>\n"
        f"1. Откройте чат с {SUPPORT_USERNAME}\n"
        f"2. Опишите проблему\n"
        f"3. Приложите скриншоты\n\n"
        f"⏰ <b>Время ответа:</b> до 24 часов",
        reply_markup=get_main_menu(callback.from_user.id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "my_stars")
async def my_stars_handler(callback: types.CallbackQuery):
    """Мои звезды"""
    user_id = callback.from_user.id
    stars, deposit_total = get_user_data(user_id)
    
    await callback.message.edit_text(
        f"<b>⭐ Ваш баланс:</b>\n\n"
        f"✨ <b>Звёзды:</b> {stars}\n"
        f"💰 <b>Всего депозитов:</b> {deposit_total}⭐\n\n"
        f"🎁 <b>Для открытия подарочка нужно 25 звёзд</b>\n"
        f"💎 <b>Бесплатный NFT подарок с шансом 0.1%!</b>",
        reply_markup=get_main_menu(user_id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "back_to_main")
async def back_handler(callback: types.CallbackQuery):
    """Назад в главное меню"""
    user_id = callback.from_user.id
    stars, _ = get_user_data(user_id)
    
    await callback.message.edit_text(
        f"<b>🎁 Vitcoin gifts</b>\n\n"
        f"✨ <b>Твои звёзды:</b> {stars}\n\n"
        f"🎰 <b>Открывай подарочки за 25 звезд!</b>\n"
        f"🎁 <b>Бесплатный NFT подарок раз в 24 часа с шансом 0.1%!</b>",
        reply_markup=get_main_menu(user_id),
        parse_mode="HTML"
    )

# ========== АДМИН ПАНЕЛЬ ==========

@dp.callback_query(F.data == "admin_panel")
async def admin_panel_handler(callback: types.CallbackQuery):
    """Админ панель"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(stars) FROM users')
    total_stars = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM withdrawal_requests WHERE status = "pending"')
    pending = cursor.fetchone()[0]
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    kb.row(InlineKeyboardButton(text="💰 Добавить звёзды", callback_data="admin_add"))
    kb.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    kb.row(InlineKeyboardButton(text="📤 Заявки на вывод", callback_data="admin_withdrawals"))
    kb.row(InlineKeyboardButton(text="💳 Депозиты", callback_data="admin_deposits"))
    kb.row(InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    
    await callback.message.edit_text(
        f"<b>👑 Админ панель</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• 👥 Пользователей: {total_users}\n"
        f"• ⭐ Всего звёзд: {total_stars}\n"
        f"• 📤 Ожидают вывода: {pending}\n\n"
        f"<b>Выберите действие:</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: types.CallbackQuery):
    """Статистика админа"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM wins WHERE prize_type = "NFT"')
    nft_wins = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(amount) FROM deposits WHERE status = "completed"')
    total_deposited = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM withdrawal_requests WHERE status = "pending"')
    pending = cursor.fetchone()[0]
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users"))
    kb.row(InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin_panel"))
    
    await callback.message.edit_text(
        f"<b>📊 Статистика</b>\n\n"
        f"<b>👥 Пользователи:</b>\n"
        f"• Всего: {total_users}\n\n"
        f"<b>💰 Финансы:</b>\n"
        f"• Сумма депозитов: {total_deposited}⭐\n\n"
        f"<b>🎁 Активность:</b>\n"
        f"• NFT выиграно: {nft_wins}\n\n"
        f"<b>📤 Выводы:</b>\n"
        f"• Ожидают: {pending}",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_users")
async def admin_users_handler(callback: types.CallbackQuery):
    """Все пользователи"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    cursor.execute('SELECT user_id, username, first_name, stars, deposit_total FROM users ORDER BY stars DESC LIMIT 100')
    users = cursor.fetchall()
    
    if not users:
        await callback.answer("❌ Пользователей нет", show_alert=True)
        return
    
    text = "<b>👥 Топ-100 пользователей:</b>\n\n"
    for i, (uid, uname, fname, stars, deposit) in enumerate(users, 1):
        deposit = deposit or 0
        cursor.execute('SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = "admin_add_stars"', (uid,))
        admin_stars = cursor.fetchone()[0] or 0
        text += f"{i}. @{uname or 'нет'} ({fname})\n   🆔: {uid} | ⭐: {stars} | 💰: {deposit} | 👑: {admin_stars}\n\n"
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin_panel"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_add")
async def admin_add_handler(callback: types.CallbackQuery):
    """Добавление звезд"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "<b>💰 Добавление звёзд</b>\n\n"
        "<b>Формат:</b>\n"
        "<code>ID_пользователя количество</code>\n\n"
        "<i>Пример:</i>\n"
        "<code>123456789 100</code> - добавить 100⭐\n"
        "<code>987654321 -50</code> - убрать 50⭐",
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_handler(callback: types.CallbackQuery):
    """Рассылка"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    broadcast_mode[user_id] = True
    await callback.message.edit_text(
        "<b>📢 Рассылка</b>\n\n"
        "<b>Отправьте сообщение для рассылки:</b>\n\n"
        "<i>Формат:</i>\n"
        "Текст (поддерживается HTML)\n\n"
        "<i>Пример:</i>\n"
        "<code>🔥 Новый конкурс! 🎁</code>\n\n"
        "<i>Отправьте сообщение или /cancel для отмены</i>",
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals_handler(callback: types.CallbackQuery):
    """Заявки на вывод"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    cursor.execute('SELECT id, user_id, username, gift_name, gift_emoji, gift_value, timestamp FROM withdrawal_requests WHERE status = "pending" ORDER BY timestamp DESC LIMIT 20')
    withdrawals = cursor.fetchall()
    
    if not withdrawals:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin_panel"))
        await callback.message.edit_text("✅ Нет ожидающих заявок", reply_markup=kb.as_markup())
        return
    
    text = "<b>📤 Ожидающие заявки:</b>\n\n"
    kb = InlineKeyboardBuilder()
    
    for w_id, w_uid, w_uname, w_name, w_emoji, w_value, w_time in withdrawals:
        time_str = datetime.fromisoformat(w_time).strftime('%d.%m %H:%M')
        text += f"<b>#{w_id}</b>\n👤 @{w_uname or 'нет'} (ID: {w_uid})\n🎁 {w_emoji} {w_name} ({w_value}⭐)\n⏰ {time_str}\n\n"
        kb.row(InlineKeyboardButton(text=f"✅ Обработать #{w_id}", callback_data=f"process_w_{w_id}"))
    
    kb.row(InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin_panel"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("process_w_"))
async def process_withdrawal_handler(callback: types.CallbackQuery):
    """Обработка заявки на вывод"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    w_id = int(callback.data.split("_")[2])
    cursor.execute('UPDATE withdrawal_requests SET status = "completed" WHERE id = ?', (w_id,))
    conn.commit()
    await admin_withdrawals_handler(callback)
    await callback.answer(f"✅ Заявка #{w_id} обработана")

@dp.callback_query(F.data == "admin_deposits")
async def admin_deposits_handler(callback: types.CallbackQuery):
    """Заявки на депозит"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    cursor.execute('SELECT id, user_id, username, amount, timestamp FROM deposits WHERE status = "pending" ORDER BY timestamp DESC LIMIT 20')
    deposits = cursor.fetchall()
    
    if not deposits:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin_panel"))
        await callback.message.edit_text("✅ Нет ожидающих депозитов", reply_markup=kb.as_markup())
        return
    
    text = "<b>💳 Ожидающие депозиты:</b>\n\n"
    kb = InlineKeyboardBuilder()
    
    for d_id, d_uid, d_uname, d_amount, d_time in deposits:
        time_str = datetime.fromisoformat(d_time).strftime('%d.%m %H:%M')
        text += f"<b>#{d_id}</b>\n👤 @{d_uname or 'нет'} (ID: {d_uid})\n💰 {d_amount}⭐\n⏰ {time_str}\n\n"
        kb.row(InlineKeyboardButton(text=f"✅ Подтвердить #{d_id}", callback_data=f"process_d_{d_id}"))
    
    kb.row(InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin_panel"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("process_d_"))
async def process_deposit_handler(callback: types.CallbackQuery):
    """Обработка депозита"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    d_id = int(callback.data.split("_")[2])
    
    cursor.execute('SELECT user_id, username, amount FROM deposits WHERE id = ?', (d_id,))
    deposit = cursor.fetchone()
    
    if deposit:
        d_uid, d_uname, d_amount = deposit
        cursor.execute('UPDATE deposits SET status = "completed" WHERE id = ?', (d_id,))
        cursor.execute('UPDATE users SET stars = stars + ?, deposit_total = deposit_total + ? WHERE user_id = ?', 
                       (d_amount, d_amount, d_uid))
        cursor.execute('INSERT INTO transactions (user_id, username, amount, type, timestamp, admin_id) VALUES (?, ?, ?, ?, ?, ?)',
                       (d_uid, d_uname, d_amount, "deposit", datetime.now().isoformat(), user_id))
        conn.commit()
        
        try:
            await bot.send_message(d_uid, f"✅ Ваш депозит {d_amount}⭐ подтвержден!")
        except:
            pass
    
    await admin_deposits_handler(callback)
    await callback.answer(f"✅ Депозит #{d_id} подтвержден")

# ========== ОБРАБОТЧИК АДМИНСКИХ СООБЩЕНИЙ ==========

@dp.message(F.from_user.id.in_(ADMIN_IDS))
async def admin_message_handler(message: types.Message):
    """Обработчик сообщений админа"""
    user_id = message.from_user.id
    
    # Режим рассылки
    if user_id in broadcast_mode and broadcast_mode[user_id]:
        broadcast_mode[user_id] = False
        
        if message.text == "/cancel":
            await message.answer("❌ Рассылка отменена")
            return
        
        text = message.text
        await message.answer(f"📢 Начинаю рассылку...")
        
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
        total = len(users)
        success = 0
        
        for (uid,) in users:
            try:
                await bot.send_message(uid, text, parse_mode="HTML")
                success += 1
                await asyncio.sleep(0.05)
            except:
                pass
        
        await message.answer(f"✅ Рассылка завершена!\n👥 Всего: {total}\n✅ Успешно: {success}")
        return
    
    # Добавление звезд
    if not message.text.startswith('/') and not message.text.startswith('депозит'):
        try:
            parts = message.text.strip().split()
            if len(parts) == 2:
                target_id = int(parts[0])
                amount = int(parts[1])
                
                cursor.execute('SELECT username, stars FROM users WHERE user_id = ?', (target_id,))
                user = cursor.fetchone()
                
                if user:
                    username, current_stars = user
                    new_stars = current_stars + amount
                    
                    if new_stars < 0:
                        await message.answer(f"❌ Нельзя убрать больше {current_stars}⭐")
                        return
                    
                    cursor.execute('UPDATE users SET stars = ? WHERE user_id = ?', (new_stars, target_id))
                    cursor.execute('INSERT INTO transactions (user_id, username, amount, type, timestamp, admin_id) VALUES (?, ?, ?, ?, ?, ?)',
                                   (target_id, username, amount, "admin_add_stars", datetime.now().isoformat(), user_id))
                    conn.commit()
                    
                    await message.answer(
                        f"✅ Баланс обновлен!\n👤 @{username or 'нет'}\n🆔 {target_id}\n"
                        f"✨ Было: {current_stars}⭐\n{'➕' if amount > 0 else '➖'} {abs(amount)}⭐\n"
                        f"✨ Стало: {new_stars}⭐"
                    )
                    
                    try:
                        await bot.send_message(target_id, f"✨ Ваш баланс изменен на {amount}⭐\nНовый баланс: {new_stars}⭐")
                    except:
                        pass
                else:
                    await message.answer(f"❌ Пользователь {target_id} не найден")
        except ValueError:
            await message.answer("❌ Формат: <code>ID количество</code>", parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка админа: {e}")

# ========== ЗАПУСК ==========

async def main():
    init_db()
    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
