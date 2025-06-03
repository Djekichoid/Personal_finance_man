# handlers/report_handler.py
import matplotlib

matplotlib.use('Agg')  # Use non-GUI backend for image generation
import matplotlib.pyplot as plt
from io import BytesIO
import datetime
import requests

from bot_app import bot
from telebot import types
from models import SessionLocal
from models.transaction import Transaction
from models.category import Category
from models.user import User
from handlers.start_handler import get_main_menu


# --- Menu вибору типу звіту ---
@bot.message_handler(func=lambda m: m.text == "📆 Звіт за період")
def report_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📊 Круговий по категоріям"),
        types.KeyboardButton("📈 Лінійний по дням"),
        types.KeyboardButton("📑 Зведений"),
        types.KeyboardButton("📝 Транзакції"),
        types.KeyboardButton("📊 Звіт по валютам"),
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
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    # Витрати по категоріям
    exp_txs = session.query(Transaction).filter(
        Transaction.date >= start_dt,
        Transaction.date <= end_dt,
        Transaction.type == 'expense',
        Transaction.user_id == user.id
    ).all()
    exp_data = {}
    for t in exp_txs:
        cat = session.query(Category).get(t.category_id)
        exp_data[cat.name] = exp_data.get(cat.name, 0) + t.amount
    # Доходи по категоріям
    inc_txs = session.query(Transaction).filter(
        Transaction.date >= start_dt,
        Transaction.date <= end_dt,
        Transaction.type == 'income',
        Transaction.user_id == user.id
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
    buf = BytesIO()
    fig.savefig(buf, format='png')
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
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    txs = session.query(Transaction).filter(
        Transaction.date >= start_dt,
        Transaction.date <= end_dt,
        Transaction.user_id == user.id
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
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    txs = session.query(Transaction).filter(
        Transaction.date >= sd,
        Transaction.date <= ed,
        Transaction.user_id == user.id
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
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    txs = session.query(Transaction).filter(
        Transaction.date >= st,
        Transaction.date <= et,
        Transaction.user_id == user.id
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

@bot.message_handler(func=lambda m: m.text == "📊 Звіт по валютам")
def currency_period_start(message):
    """
    Запитує у користувача період у форматі YYYY-MM-DD : YYYY-MM-DD,
    а потім будує графік валют за цей проміжок.
    """
    markup = types.ForceReply(selective=True)
    bot.send_message(
        message.chat.id,
        "Введіть період для валютного звіту у форматі YYYY-MM-DD : YYYY-MM-DD:",
        reply_markup=markup
    )
    bot.register_next_step_handler(message, currency_period_generate)

def currency_period_generate(message):
    text = message.text.strip()
    try:
        start_str, end_str = [s.strip() for s in text.split(':')]
        start_dt = datetime.datetime.fromisoformat(start_str).date()
        end_dt   = datetime.datetime.fromisoformat(end_str).date()
    except Exception:
        bot.send_message(
            message.chat.id,
            "Невірний формат. Спробуйте ще раз у форматі YYYY-MM-DD : YYYY-MM-DD.",
            reply_markup=None
        )
        return


    def fetch_timeseries_nbu(c_char_code: str, start: datetime.date, end: datetime.date) -> list:
        """
        Повертає список (date_obj, rate) для c_char_code (\"USD\" або \"EUR\") за весь місяць
        Використовуємо NBU API: https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?date=YYYYMMDD&json
        """
        result = []
        cur = start
        while cur <= end:
            date_str = cur.strftime("%Y%m%d")
            url = f"https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?date={date_str}&json"
            try:
                resp = requests.get(url, timeout=5)
                rates_list = resp.json()  # список словників
                for item in rates_list:
                    if item.get("cc") == c_char_code:
                        d_obj = cur
                        rate = float(item.get("rate", 0.0))
                        result.append((d_obj, rate))
                        break
            except:
                pass
            cur += datetime.timedelta(days=1)
        return result

    # --- 8.2. Функція для BTC/ETH→USD через CoinGecko ---
    def fetch_timeseries_crypto(symbol_id: str, vs_currency: str, start: datetime.date, end: datetime.date) -> list:
        """
        Повертає список (date_obj, price) для криптовалюти symbol_id за період.
        Використовуємо CoinGecko: останні N днів, потім филтруємо по датах.
        """
        url = f"https://api.coingecko.com/api/v3/coins/{symbol_id}/market_chart"
        params = {
            "vs_currency": vs_currency,
            "days":        (end - start).days + 1
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json().get("prices", [])  # [[timestamp_ms, price], …]
            result = []
            for timestamp_ms, price in data:
                d_obj = datetime.datetime.utcfromtimestamp(timestamp_ms / 1000.0).date()
                if start <= d_obj <= end:
                    result.append((d_obj, price))
            return sorted(result)
        except:
            return []



    # Збираємо дані курсів за вказаний період (через API НБУ для USD, EUR,
    # CoinGecko для BTC, ETH). Побудова графіка – аналогічно місячному звіту.
    usd_series = fetch_timeseries_nbu("USD", start_dt, end_dt)
    eur_series = fetch_timeseries_nbu("EUR", start_dt, end_dt)
    btc_series = fetch_timeseries_crypto("bitcoin", "USD", start_dt, end_dt)
    eth_series = fetch_timeseries_crypto("ethereum", "USD", start_dt, end_dt)

    # Малюємо два підграфіки: фіат (USD→UAH, EUR→UAH) та крипто (BTC→USD, ETH→USD)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=False)

    # Фіат:
    if usd_series:
        dates_usd, vals_usd = zip(*usd_series)
        ax1.plot(dates_usd, vals_usd, label="USD/UAH", color="blue")
    if eur_series:
        dates_eur, vals_eur = zip(*eur_series)
        ax1.plot(dates_eur, vals_eur, label="EUR/UAH", color="orange")
    ax1.set_title(f"Курси USD та EUR → UAH ({start_dt} – {end_dt})")
    ax1.set_ylabel("Курс (UAH)")
    if usd_series or eur_series:
        ax1.legend()
    ax1.grid(True)

    # Крипто:
    if btc_series:
        dates_btc, vals_btc = zip(*btc_series)
        ax2.plot(dates_btc, vals_btc, label="BTC/USD", color="black")
    if eth_series:
        dates_eth, vals_eth = zip(*eth_series)
        ax2_sec = ax2.twinx()
        ax2_sec.plot(dates_eth, vals_eth, label="ETH/USD", color="gray", linestyle="--")
        ax2_sec.set_ylabel("ETH/USD", color="gray")
        ax2_sec.tick_params(axis="y", labelcolor="gray")

    ax2.set_title(f"Курси BTC та ETH → USD ({start_dt} – {end_dt})")
    ax2.set_xlabel("Дата")
    ax2.set_ylabel("BTC/USD", color="black")
    ax2.tick_params(axis="y", labelcolor="black")
    if btc_series:
        ax2.legend(loc="upper left")
    ax2.grid(True)

    fig.autofmt_xdate()
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)

    # Відправляємо графік у чат
    bot.send_photo(message.chat.id, buf)
    bot.send_message(message.chat.id, "Звіт по валютам готовий.", reply_markup=get_main_menu())
    buf.close()