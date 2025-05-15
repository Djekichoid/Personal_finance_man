# handlers/report_handler.py
import matplotlib

matplotlib.use('Agg')  # Use non-GUI backend for image generation
import matplotlib.pyplot as plt
from io import BytesIO
import datetime

from bot_app import bot
from telebot import types
from models import SessionLocal
from models.transaction import Transaction
from models.category import Category
from handlers.start_handler import get_main_menu


# --- Menu выбора типа отчета ---
@bot.message_handler(func=lambda m: m.text == "📆 Звіт за період")
def report_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📊 Круговий по категоріям"),
        types.KeyboardButton("📈 Лінійний по дням"),
        types.KeyboardButton("📑 Зведений"),
        types.KeyboardButton("📝 Транзакції"),
        types.KeyboardButton("🔙 Назад")
    )
    bot.send_message(message.chat.id, "Оберіть тип звіту:", reply_markup=markup)


# --- 1. Кругова діаграма по категоріям ---
@bot.message_handler(func=lambda m: m.text == "📊 Круговий по категоріям")
def report_pie_start(message):
    msg = bot.send_message(
        message.chat.id,
        "Введіть період у форматі YYYY-MM-DD:YYYY-MM-DD:",
        reply_markup=types.ForceReply(selective=True)
    )
    bot.register_next_step_handler(msg, report_pie)


def report_pie(message):
    # Парсимо дати
    text = message.text.strip()
    try:
        start_str, end_str = [s.strip() for s in text.split(":", 1)]
        start_dt = datetime.datetime.fromisoformat(start_str)
        end_dt = datetime.datetime.fromisoformat(end_str)
    except:
        bot.send_message(message.chat.id, "Невірний формат. Повторіть:", reply_markup=get_main_menu())
        return

    session = SessionLocal()
    # Витрати по категоріям
    exp_txs = session.query(Transaction).filter(
        Transaction.date >= start_dt,
        Transaction.date <= end_dt,
        Transaction.type == 'expense'
    ).all()
    exp_data = {}
    for t in exp_txs:
        cat = session.query(Category).get(t.category_id)
        exp_data[cat.name] = exp_data.get(cat.name, 0) + t.amount
    # Доходи по категоріям
    inc_txs = session.query(Transaction).filter(
        Transaction.date >= start_dt,
        Transaction.date <= end_dt,
        Transaction.type == 'income'
    ).all()
    inc_data = {}
    for t in inc_txs:
        cat = session.query(Category).get(t.category_id)
        inc_data[cat.name] = inc_data.get(cat.name, 0) + t.amount
    session.close()

    # Графік з двома круговими діаграмами
    labels_exp = list(exp_data.keys()) or ['Немає']
    sizes_exp = list(exp_data.values()) or [1]
    labels_inc = list(inc_data.keys()) or ['Немає']
    sizes_inc = list(inc_data.values()) or [1]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4))
    ax1.pie(sizes_exp, labels=labels_exp, autopct='%1.1f%%')
    ax1.set_title('Витрати')
    ax2.pie(sizes_inc, labels=labels_inc, autopct='%1.1f%%')
    ax2.set_title('Доходи')
    fig.suptitle(f"Категорії: {start_dt.date()}–{end_dt.date()}")
    buf = BytesIO();
    fig.savefig(buf, format='png');
    buf.seek(0);
    plt.close(fig)

    bot.send_photo(message.chat.id, buf)
    buf.close()
    bot.send_message(message.chat.id, "Круговий звіт готовий.", reply_markup=get_main_menu())


# --- 2. Лінійний графік доходів/витрат по днях ---
@bot.message_handler(func=lambda m: m.text == "📈 Лінійний по дням")
def report_line_start(message):
    msg = bot.send_message(
        message.chat.id,
        "Введіть період у форматі YYYY-MM-DD:YYYY-MM-DD:",
        reply_markup=types.ForceReply(selective=True)
    )
    bot.register_next_step_handler(msg, report_line)


def report_line(message):
    text = message.text.strip()
    try:
        start_str, end_str = [s.strip() for s in text.split(":", 1)]
        start_dt = datetime.datetime.fromisoformat(start_str)
        end_dt = datetime.datetime.fromisoformat(end_str)
    except:
        bot.send_message(message.chat.id, "Невірний формат. Повторіть:", reply_markup=get_main_menu())
        return
    session = SessionLocal()
    txs = session.query(Transaction).filter(
        Transaction.date >= start_dt,
        Transaction.date <= end_dt
    ).all()
    session.close()

    days = {}
    cur = start_dt.date()
    while cur <= end_dt.date():
        days[cur] = {'income': 0, 'expense': 0}
        cur += datetime.timedelta(days=1)
    for t in txs:
        d = t.date.date()
        days[d][t.type] += t.amount
    dates = sorted(days.keys())
    income_vals = [days[d]['income'] for d in dates]
    expense_vals = [days[d]['expense'] for d in dates]

    fig, ax = plt.subplots()
    ax.plot(dates, income_vals, label='Доходи')
    ax.plot(dates, expense_vals, label='Витрати')
    ax.legend()
    ax.set_title(f"Дохід/Витрати: {start_dt.date()}–{end_dt.date()}")
    fig.autofmt_xdate()
    buf = BytesIO();
    fig.savefig(buf, format='png');
    buf.seek(0);
    plt.close(fig)

    bot.send_photo(message.chat.id, buf)
    buf.close()
    bot.send_message(message.chat.id, "Лінійний звіт готовий.", reply_markup=get_main_menu())


# --- 3. Зведений звіт (суми) з діаграмою ---
@bot.message_handler(func=lambda m: m.text == "📑 Зведений")
def report_summary_start(message):
    msg = bot.send_message(
        message.chat.id,
        "Введіть період у форматі YYYY-MM-DD:YYYY-MM-DD:",
        reply_markup=types.ForceReply(selective=True)
    )
    bot.register_next_step_handler(msg, report_summary)


def report_summary(message):
    text = message.text.strip()
    try:
        start_str, end_str = [s.strip() for s in text.split(":", 1)]
        sd = datetime.datetime.fromisoformat(start_str)
        ed = datetime.datetime.fromisoformat(end_str)
    except:
        bot.send_message(message.chat.id, "Невірний формат.", reply_markup=get_main_menu())
        return
    session = SessionLocal()
    txs = session.query(Transaction).filter(
        Transaction.date >= sd,
        Transaction.date <= ed
    ).all()
    session.close()
    inc = sum(t.amount for t in txs if t.type == 'income')
    exp = sum(t.amount for t in txs if t.type == 'expense')
    bal = inc - exp

    # Діаграма барів
    fig, ax = plt.subplots()
    ax.bar(['Доходи', 'Витрати'], [inc, exp])
    ax.set_title(f"Зведений звіт: {sd.date()}–{ed.date()}")
    buf = BytesIO();
    fig.savefig(buf, format='png');
    buf.seek(0);
    plt.close(fig)

    bot.send_photo(message.chat.id, buf)
    buf.close()

    # Текстовий підсумок
    text = (
        f"Звіт з {sd.date()} по {ed.date()}:\n"
        f"• Доходи:  {inc}\n"
        f"• Витрати: {exp}\n"
        f"• Баланс:  {bal}"
    )
    bot.send_message(message.chat.id, text, reply_markup=get_main_menu())


# --- 4. Текстовий звіт по транзакціям ---
@bot.message_handler(func=lambda m: m.text == "📝 Транзакції")
def report_tx_start(message):
    msg = bot.send_message(
        message.chat.id,
        "Введіть період у форматі YYYY-MM-DD:YYYY-MM-DD:",
        reply_markup=types.ForceReply(selective=True)
    )
    bot.register_next_step_handler(msg, report_tx)


def report_tx(message):
    text = message.text.strip()
    try:
        s, e = [s.strip() for s in text.split(":", 1)]
        st = datetime.datetime.fromisoformat(s)
        et = datetime.datetime.fromisoformat(e)
    except:
        bot.send_message(message.chat.id, "Невірний формат.", reply_markup=get_main_menu())
        return
    session = SessionLocal()
    txs = session.query(Transaction).filter(
        Transaction.date >= st,
        Transaction.date <= et
    ).order_by(Transaction.date).all()
    session.close()
    if not txs:
        bot.send_message(message.chat.id, "Транзакцій немає.", reply_markup=get_main_menu())
        return
    report_text = ""
    last = None
    for t in txs:
        d = t.date.date()
        if d != last:
            report_text += f"\n📅 {d}:\n"
            last = d
        report_text += f" – [{t.type}] {t.amount} ({t.note or 'без опису'})\n"
    bot.send_message(message.chat.id, report_text, reply_markup=get_main_menu())
