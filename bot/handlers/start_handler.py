from bot_app import bot
from telebot import types
from models import SessionLocal
from models.user import User
from models.category import Category


DEFAULT_CATEGORIES = [
    ("Їжа", "expense"),
    ("Транспорт", "expense"),
    ("Розваги", "expense"),
    ("Інше витрати", "expense"),
    ("Зарплата", "income"),
    ("Підробіток", "income"),
]


@bot.message_handler(commands=["start"])
def start_handler(message: types.Message):
    """
    Handle the /start command: register user and show main menu.
    """
    session = SessionLocal()
    # Check if user exists
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user:
        # Register new user
        user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username or message.from_user.full_name,
            timezone=message.from_user.language_code  # fallback for timezone
        )
        session.add(user)
        session.commit()
        # Create default categories for new user
        for name, ctype in DEFAULT_CATEGORIES:
            cat = Category(
                name=name,
                type=ctype,
                is_default=True,
                user_id=user.id
            )
            session.add(cat)
        session.commit()
    session.close()

    # Build main menu keyboard
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("➕ Витрата"),
        types.KeyboardButton("➕ Дохід"),
        types.KeyboardButton("📂 Категорії"),
        types.KeyboardButton("📆 Звіт за період"),
        types.KeyboardButton("⚙️ Налаштування")
    )
    bot.send_message(
        message.chat.id,
        f"Привіт, {message.from_user.full_name}! Оберіть дію:",
        reply_markup=markup
    )

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("➕ Витрата"),
        types.KeyboardButton("➕ Дохід"),
        types.KeyboardButton("📂 Категорії"),
        types.KeyboardButton("📆 Звіт за період"),
        types.KeyboardButton("⚙️ Налаштування")
    )
    return markup
