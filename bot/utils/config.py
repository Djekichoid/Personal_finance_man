import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot configuration variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

# Validate required environment variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in the environment (.env)")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the environment (.env)")
