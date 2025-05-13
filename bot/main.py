# main.py
import telebot
from utils.config import BOT_TOKEN, DATABASE_URL
from models import init_db

# Initialize database
engine = init_db(DATABASE_URL)
# TODO: Configure Alembic for DB migrations (run `pip install alembic` then `alembic init migrations`)

# Initialize Telegram bot using pyTelegramBotAPI
bot = telebot.TeleBot(BOT_TOKEN)

# Import handler modules (they register via decorators)
# import handlers.start_handler

if __name__ == "__main__":
    print("Starting bot...")
    bot.polling(none_stop=True)