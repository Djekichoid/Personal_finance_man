# handlers\transaction_handler.py
from bot.bot_app import bot
from telebot import types
from bot.models import SessionLocal
from bot.models.transaction import Transaction
from bot.models.category import Category
from bot.models.user import User
from bot.handlers.start_handler import get_main_menu
import datetime


# Utility to fetch categories by type
def fetch_categories(telegram_id, ctype):
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        session.close()
        return []
    cats = session.query(Category).filter(Category.user_id == user.id, Category.type == ctype).all()
    session.close()
    return cats


@bot.message_handler(func=lambda m: m.text == "➕ Витрата")
def expense_start(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(message.chat.id, "Введіть суму витрати:", reply_markup=markup)
    bot.register_next_step_handler(msg, expense_amount)


@bot.message_handler(func=lambda m: m.text == "➕ Дохід")
def income_start(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(message.chat.id, "Введіть суму доходу:", reply_markup=markup)
    bot.register_next_step_handler(msg, income_amount)


def expense_amount(message):
    text = message.text.strip()
    if text == "🔙 Назад":
        bot.send_message(message.chat.id, "Додавання витрати скасовано.", reply_markup=get_main_menu())
        return
    try:
        amount = float(text)
    except ValueError:
        bot.send_message(message.chat.id, "Невірна сума. Спробуйте ще раз.", reply_markup=get_main_menu())
        return
    telegram_id = message.from_user.id
    categories = fetch_categories(telegram_id, 'expense')
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for cat in categories:
        markup.add(types.KeyboardButton(cat.name))
    markup.add(types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(message.chat.id, "Оберіть категорію:", reply_markup=markup)
    bot.register_next_step_handler(msg, expense_category, amount)


def expense_category(message, amount):
    name = message.text.strip()
    if name == "🔙 Назад":
        bot.send_message(message.chat.id, "Додавання витрати скасовано.", reply_markup=get_main_menu())
        return
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    category = session.query(Category).filter(Category.user_id == user.id, Category.name == name,
                                              Category.type == 'expense').first()
    session.close()
    if not category:
        bot.send_message(message.chat.id, "Категорія не знайдена.", reply_markup=get_main_menu())
        return
    # Prompt for optional note with skip and back options
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton("Пропустити"), types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(
        message.chat.id,
        "(Опційно) Додайте опис витрати або натисніть 'Пропустити' чи '🔙 Назад':",
        reply_markup=markup
    )
    bot.register_next_step_handler(msg, expense_note, amount, category.id if category else None, name)


def expense_note(message, amount, category_id, category_name):
    note = message.text.strip()
    if note == "🔙 Назад":
        bot.send_message(message.chat.id, "Додавання витрати скасовано.", reply_markup=get_main_menu())
        return
    if note == "Пропустити":
        note = ""
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    transaction = Transaction(
        amount=amount,
        date=datetime.datetime.utcnow(),
        type='expense',
        note=note,
        user_id=user.id,
        category_id=category_id
    )
    session.add(transaction)
    session.commit()
    session.close()
    bot.send_message(message.chat.id, f"Витрату {amount} додано до '{category_name}'.", reply_markup=get_main_menu())


def income_amount(message):
    text = message.text.strip()
    if text == "🔙 Назад":
        bot.send_message(message.chat.id, "Додавання доходу скасовано.", reply_markup=get_main_menu())
        return
    try:
        amount = float(text)
    except ValueError:
        bot.send_message(message.chat.id, "Невірна сума. Спробуйте ще раз.", reply_markup=get_main_menu())
        return
    telegram_id = message.from_user.id
    categories = fetch_categories(telegram_id, 'income')
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for cat in categories:
        markup.add(types.KeyboardButton(cat.name))
    markup.add(types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(message.chat.id, "Оберіть категорію:", reply_markup=markup)
    bot.register_next_step_handler(msg, income_category, amount)


def income_category(message, amount):
    name = message.text.strip()
    if name == "🔙 Назад":
        bot.send_message(message.chat.id, "Додавання доходу скасовано.", reply_markup=get_main_menu())
        return
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    category = session.query(Category).filter(Category.user_id == user.id, Category.name == name,
                                              Category.type == 'income').first()
    session.close()
    if not category:
        bot.send_message(message.chat.id, "Категорія не знайдена.", reply_markup=get_main_menu())
        return
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton("Пропустити"), types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(
        message.chat.id,
        "(Опційно) Додайте опис доходу або натисніть 'Пропустити' чи '🔙 Назад':",
        reply_markup=markup
    )
    bot.register_next_step_handler(msg, income_note, amount, category.id if category else None, name)


def income_note(message, amount, category_id, category_name):
    note = message.text.strip()
    if note == "🔙 Назад":
        bot.send_message(message.chat.id, "Додавання доходу скасовано.", reply_markup=get_main_menu())
        return
    if note == "Пропустити":
        note = ""
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    transaction = Transaction(
        amount=amount,
        date=datetime.datetime.utcnow(),
        type='income',
        note=note,
        user_id=user.id,
        category_id=category_id
    )
    session.add(transaction)
    session.commit()
    session.close()
    bot.send_message(message.chat.id, f"Дохід {amount} додано до '{category_name}'.", reply_markup=get_main_menu())
