# main.py
from bot_app import bot
from utils.config import DATABASE_URL
from models import init_db, SessionLocal
from models.user import User
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Initialize database
engine = init_db(DATABASE_URL)

# Import handler modules (they register via decorators)
import handlers.start_handler
import handlers.category_handler
import handlers.transaction_handler
import handlers.report_handler
import handlers.monthly_report_handler
import handlers.fallback_handler

def send_daily_reminder():
    session = SessionLocal()
    users = session.query(User).all()
    session.close()
    for u in users:
        bot.send_message(
            u.telegram_id,
            "Не забудьте внести сьогоднішні витрати!"
        )

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        send_daily_reminder,
        CronTrigger(hour=20, minute=0)
    )
    scheduler.start()

    print("Starting bot…")
    bot.polling(none_stop=True)
