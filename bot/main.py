from bot_app import bot
from utils.config import DATABASE_URL
from models import init_db

# Initialize database
engine = init_db(DATABASE_URL)

# Import handler modules (they register via decorators)
import handlers.start_handler
import handlers.category_handler

if __name__ == "__main__":
    print("Starting bot...")
    bot.polling(none_stop=True)