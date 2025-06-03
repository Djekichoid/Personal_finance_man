#handlers\fallback_handler.py
from bot_app import bot
from handlers.start_handler import get_main_menu
from telebot import types

@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_invalid_main(message: types.Message):
    valid_buttons = [
        "➕ Витрата", "➕ Дохід", "📂 Категорії", "⚙️ Налаштування", "📆 Звіт за період, 📅 Щомісячний звіт"
    ]
    if message.text not in valid_buttons:
        bot.send_message(
            message.chat.id,
            "Вибачте, я не розумію цю команду. Будь ласка, оберіть опцію з меню.",
            reply_markup=get_main_menu()
        )
