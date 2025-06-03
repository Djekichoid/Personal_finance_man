#handlers\category_handler.py
from bot_app import bot
from telebot import types
from models import SessionLocal
from models.category import Category
from models.user import User
from handlers.start_handler import get_main_menu


# Menu of category operations
def get_categories_menu():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📑 Всі категорії"),
        types.KeyboardButton("➕ Додати категорію"),
        types.KeyboardButton("✏️ Редагувати категорію"),
        types.KeyboardButton("🗑️ Видалити категорію"),
        types.KeyboardButton("🔙 Назад")
    )
    return markup


# Main categories menu
enhanced_menu = get_categories_menu()


@bot.message_handler(func=lambda m: m.text == "📂 Категорії")
def categories_menu(message):
    bot.send_message(
        message.chat.id,
        "Меню категорій:",
        reply_markup=get_categories_menu()
    )


# Show all categories\
@bot.message_handler(func=lambda m: m.text == "📑 Всі категорії")
def show_categories(message):
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    categories = session.query(Category).filter(Category.user_id == user.id).all()
    session.close()
    if not categories:
        text = "У вас ще немає категорій."
    else:
        lines = []
        for cat in categories:
            default_note = "Шаблон" if cat.is_default else "Персональна"
            cat_type = "Витрати" if cat.type == "expense" else "Дохід"
            lines.append(f"• {cat.name} [{cat_type}] ({default_note})")
        text = "Ваші категорії:\n" + "\n".join(lines)
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=get_categories_menu()
    )


# Add category
@bot.message_handler(func=lambda m: m.text == "➕ Додати категорію")
def add_category_start(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("Витрата"),
        types.KeyboardButton("Дохід"),
        types.KeyboardButton("🔙 Назад")
    )
    msg = bot.send_message(
        message.chat.id,
        "Оберіть тип категорії або '🔙 Назад' для виходу:",
        reply_markup=markup
    )
    bot.register_next_step_handler(msg, add_category_type)


def add_category_type(message):
    choice = message.text.strip()
    if choice == "🔙 Назад":
        bot.send_message(message.chat.id, "Додавання категорії скасовано.", reply_markup=get_categories_menu())
        return
    if choice not in ("Витрата", "Дохід"):
        bot.send_message(message.chat.id, "Невідома опція.", reply_markup=get_categories_menu())
        return
    ctype = "expense" if choice == "Витрата" else "income"
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(
        message.chat.id,
        f"Введіть назву нової категорії ({choice}):", reply_markup=markup
    )
    bot.register_next_step_handler(msg, add_category_name, ctype)


def add_category_name(message, ctype):
    name = message.text.strip()
    if name == "🔙 Назад":
        bot.send_message(message.chat.id, "Додавання категорії скасовано.", reply_markup=get_categories_menu())
        return
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    category = Category(name=name, type=ctype, is_default=False, user_id=user.id)
    session.add(category)
    session.commit()
    session.close()
    bot.send_message(message.chat.id, f"Категорію '{name}' додано ({ctype}).", reply_markup=get_categories_menu())


# Edit category: select category
@bot.message_handler(func=lambda m: m.text == "✏️ Редагувати категорію")
def edit_category_start(message):
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    categories = session.query(Category).filter(Category.user_id == user.id).all()
    session.close()
    if not categories:
        bot.send_message(message.chat.id, "У вас немає категорій для редагування.", reply_markup=get_categories_menu())
        return
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for cat in categories:
        markup.add(types.KeyboardButton(cat.name))
    markup.add(types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(message.chat.id, "Оберіть категорію для редагування:", reply_markup=markup)
    bot.register_next_step_handler(msg, edit_category_choice)


# Edit category: choose field
def edit_category_choice(message):
    name_old = message.text.strip()
    if name_old == "🔙 Назад":
        bot.send_message(message.chat.id, "Редагування категорії скасовано.", reply_markup=get_categories_menu())
        return
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    category = session.query(Category).filter(Category.user_id == user.id, Category.name == name_old).first()
    session.close()
    if not category:
        bot.send_message(message.chat.id, f"Категорія '{name_old}' не знайдена.", reply_markup=get_categories_menu())
        return
    # Ask what to edit
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton("Змінити назву"), types.KeyboardButton("Змінити тип"),
               types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(message.chat.id, f"Що ви хочете змінити в '{name_old}'?", reply_markup=markup)
    bot.register_next_step_handler(msg, edit_category_field, category.id)


# Edit category: apply field change
def edit_category_field(message, category_id):
    choice = message.text.strip()
    if choice == "🔙 Назад":
        bot.send_message(message.chat.id, "Редагування категорії скасовано.", reply_markup=get_categories_menu())
        return
    if choice == "Змінити назву":
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add(types.KeyboardButton("🔙 Назад"))
        msg = bot.send_message(message.chat.id, "Введіть нову назву:", reply_markup=markup)
        bot.register_next_step_handler(msg, edit_category_apply_name, category_id)
    elif choice == "Змінити тип":
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add(types.KeyboardButton("Витрата"), types.KeyboardButton("Дохід"), types.KeyboardButton("🔙 Назад"))
        msg = bot.send_message(message.chat.id, "Оберіть новий тип категорії:", reply_markup=markup)
        bot.register_next_step_handler(msg, edit_category_apply_type, category_id)
    else:
        bot.send_message(message.chat.id, "Невідома опція.", reply_markup=get_categories_menu())


# Edit category: apply new name
def edit_category_apply_name(message, category_id):
    new_name = message.text.strip()
    if new_name == "🔙 Назад":
        bot.send_message(message.chat.id, "Редагування категорії скасовано.", reply_markup=get_categories_menu())
        return
    session = SessionLocal()
    category = session.get(Category, category_id)
    category.name = new_name
    category.is_default = 0
    session.commit()
    session.close()
    bot.send_message(message.chat.id, f"Категорію перейменовано на '{new_name}'.", reply_markup=get_categories_menu())


# Edit category: apply new type
def edit_category_apply_type(message, category_id):
    choice = message.text.strip()
    if choice == "🔙 Назад":
        bot.send_message(message.chat.id, "Редагування категорії скасовано.", reply_markup=get_categories_menu())
        return
    if choice not in ("Витрата", "Дохід"):
        bot.send_message(message.chat.id, "Невірний тип.", reply_markup=get_categories_menu())
        return
    ctype = "expense" if choice == "Витрата" else "income"
    session = SessionLocal()
    category = session.get(Category, category_id)
    category.type = ctype
    category.is_default = 0
    session.commit()
    session.close()
    bot.send_message(message.chat.id, f"Тип категорії змінено на '{choice}'.", reply_markup=get_categories_menu())


# Delete category
@bot.message_handler(func=lambda m: m.text == "🗑️ Видалити категорію")
def delete_category_start(message):
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    categories = session.query(Category).filter(Category.user_id == user.id).all()
    session.close()
    if not categories:
        bot.send_message(
            message.chat.id,
            "У вас немає кастомних категорій для видалення.",
            reply_markup=get_categories_menu()
        )
        return
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for cat in categories:
        markup.add(types.KeyboardButton(cat.name))
    markup.add(types.KeyboardButton("🔙 Назад"))
    msg = bot.send_message(
        message.chat.id,
        "Оберіть категорію для видалення:", reply_markup=markup
    )
    bot.register_next_step_handler(msg, delete_category_confirm)


def delete_category_confirm(message):
    name = message.text.strip()
    if name == "🔙 Назад":
        bot.send_message(
            message.chat.id,
            "Видалення категорії скасовано.",
            reply_markup=get_categories_menu()
        )
        return
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    category = session.query(Category).filter(
        Category.user_id == user.id,
        Category.name == name
    ).first()
    session.close()
    if not category:
        bot.send_message(
            message.chat.id,
            f"Категорія '{name}' не знайдена.", reply_markup=get_categories_menu()
        )
        return
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton("✅ Так"), types.KeyboardButton("❌ Ні"))
    msg = bot.send_message(
        message.chat.id,
        f"Ви впевнені, що хочете видалити категорію '{name}'?", reply_markup=markup
    )
    bot.register_next_step_handler(msg, delete_category_apply, category.id)


def delete_category_apply(message, category_id):
    choice = message.text.strip()
    if choice == "✅ Так":
        session = SessionLocal()
        category = session.get(Category, category_id)
        session.delete(category)
        session.commit()
        session.close()
        bot.send_message(
            message.chat.id,
            "Категорію видалено.", reply_markup=get_categories_menu()
        )
    else:
        bot.send_message(
            message.chat.id,
            "Видалення категорії відмінено.", reply_markup=get_categories_menu()
        )


@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def return_to_menu(message):
    mes = message.text.strip()
    if mes == "🔙 Назад":
        bot.send_message(
            message.chat.id,
            "Головне меню:",
            reply_markup=get_main_menu()
        )
        return
    else:
        pass
