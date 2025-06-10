# handlers/monthly_report_handler.py
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import datetime
import requests

from bot_app import bot
from telebot import types
from models import SessionLocal
from models.transaction import Transaction
from models.category import Category
from models.monthly_metric import MonthlyMetric
from models.user import User
from handlers.start_handler import get_main_menu


# --------------------------------------------
# 1. Хендлер-команда для виклику місячного звіту
# --------------------------------------------
@bot.message_handler(func=lambda m: m.text == "📅 Щомісячний звіт")
def monthly_report(message):
    """
    Формує звіт за попередній місяць.
    """
    chat_id = message.chat.id

    # 1. Визначаємо період попереднього місяця
    today = datetime.date.today()
    first_of_current_month = today.replace(day=1)
    end_prev_month = first_of_current_month - datetime.timedelta(days=1)
    start_prev_month = end_prev_month.replace(day=1)

    prev_date = start_prev_month.replace(day=1) - datetime.timedelta(days=1)
    prev_year_month_str = prev_date.strftime("%Y-%m")

    # Перевіряємо, чи є в БД метрика за той місяць
    year_month_str = start_prev_month.strftime("%Y-%m")
    session = SessionLocal()
    prev_metric = session.query(MonthlyMetric).filter(
        MonthlyMetric.user_id == get_or_create_user_id(message.from_user.id, session),
        MonthlyMetric.year_month == prev_year_month_str
    ).first()
    session.close()

    # 2. Збираємо дані поточного місяця
    data = collect_monthly_data(message.from_user.id, start_prev_month, end_prev_month)

    # 3. Порівнюємо з попереднім
    comparison_text = build_comparison_text(prev_metric, data, start_prev_month)

    # 4. Генеруємо графіки
    pie_buf = build_pie_charts(data["cat_expenses"], data["cat_incomes"], start_prev_month, end_prev_month)
    line_buf = build_daily_line_chart(data["daily_expenses"], start_prev_month, end_prev_month)
    summary_buf = build_summary_bar_chart(data["total_income"], data["total_expense"], start_prev_month, end_prev_month)
    currency_buf = build_currency_chart(start_prev_month, end_prev_month)

    # 5. Відправляємо картинки
    bot.send_photo(chat_id, pie_buf);
    pie_buf.close()
    bot.send_photo(chat_id, line_buf);
    line_buf.close()
    bot.send_photo(chat_id, summary_buf);
    summary_buf.close()
    bot.send_photo(chat_id, currency_buf);
    currency_buf.close()

    # 6. Текстовий підсумок
    text_report = format_text_report(data, comparison_text, start_prev_month, end_prev_month)
    bot.send_message(chat_id, text_report, reply_markup=get_main_menu())

    # 7. Зберігаємо метрики для наступного місяця
    save_monthly_metric(message.from_user.id, year_month_str, data)


# --------------------------------------------
# 2. Допоміжна функція: створює/повертає user_id
# --------------------------------------------
def get_or_create_user_id(telegram_id: int, session):
    user = session.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        return user.id
    user = User(telegram_id=telegram_id, username="", timezone=None)
    session.add(user)
    session.commit()
    return user.id


# --------------------------------------------
# 3. Збір даних по транзакціях + курси валют з НБУ
# --------------------------------------------
def collect_monthly_data(telegram_id: int, start_dt: datetime.date, end_dt: datetime.date) -> dict:
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        session.close()
        return {
            "total_income": 0.0,
            "total_expense": 0.0,
            "daily_expenses": {},
            "cat_expenses": {},
            "cat_incomes": {},
            "avg_usd": 0.0,
            "avg_eur": 0.0
        }

    # -------- 3.1. Загальні суми доходів і витрат --------
    txs = session.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.date >= datetime.datetime.combine(start_dt, datetime.time.min),
        Transaction.date <= datetime.datetime.combine(end_dt, datetime.time.max)
    ).all()

    total_income = sum(t.amount for t in txs if t.type == "income")
    total_expense = sum(t.amount for t in txs if t.type == "expense")

    # -------- 3.2. Денні витрати --------
    daily_expenses = {}
    cur_date = start_dt
    while cur_date <= end_dt:
        daily_expenses[cur_date] = 0.0
        cur_date += datetime.timedelta(days=1)

    for t in txs:
        if t.type == "expense":
            d = t.date.date()
            if d in daily_expenses:
                daily_expenses[d] += t.amount

    # -------- 3.3. Витрати та доходи за категоріями --------
    cat_expenses = {}
    cat_incomes = {}
    for t in txs:
        cat = session.query(Category).get(t.category_id)
        if not cat:
            continue
        if t.type == "expense":
            cat_expenses[cat.name] = cat_expenses.get(cat.name, 0.0) + t.amount
        else:
            cat_incomes[cat.name] = cat_incomes.get(cat.name, 0.0) + t.amount

    session.close()

    # -------- 3.4. Середній курс USD→UAH та EUR→UAH через API НБУ --------
    def fetch_avg_rate_nbu(c_char_code: str, start: datetime.date, end: datetime.date) -> float:
        """
        Повертає середній курс c_char_code→UAH за діапазон дат,
        використовуючи щоденний JSON-ендпоінт НБУ:
        https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?date=YYYYMMDD&json
        """
        total = 0.0
        count = 0

        cur = start
        while cur <= end:
            # формуємо рядок дати у форматі YYYYMMDD
            date_str = cur.strftime("%Y%m%d")
            url = f"https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?date={date_str}&json"
            try:
                resp = requests.get(url, timeout=5)
                rates_list = resp.json()  # список об’єктів з ключами "r030","txt","rate","cc","exchangedate"
                # шукаємо елемент із "cc" == c_char_code
                for item in rates_list:
                    if item.get("cc") == c_char_code:
                        total += float(item.get("rate", 0))
                        count += 1
                        break
            except:
                # Якщо з якоїсь причини не вдалося отримати дані за конкретний день, просто ігноруємо
                pass

            cur += datetime.timedelta(days=1)

        return (total / count) if count > 0 else 0.0

    avg_usd = fetch_avg_rate_nbu("USD", start_dt, end_dt)
    avg_eur = fetch_avg_rate_nbu("EUR", start_dt, end_dt)

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "daily_expenses": daily_expenses,
        "cat_expenses": cat_expenses,
        "cat_incomes": cat_incomes,
        "avg_usd": avg_usd,
        "avg_eur": avg_eur
    }


# --------------------------------------------
# 4. Порівняння з попереднім місяцем → текст
# --------------------------------------------
def build_comparison_text(prev_metric: MonthlyMetric, data: dict, start_dt: datetime.date) -> str:
    if not prev_metric:
        return "Немає даних за попередній місяць для порівняння.\n"

    txt = ""
    # 4.1. Доходи
    diff_inc = data["total_income"] - prev_metric.total_income
    pct_inc = (diff_inc / prev_metric.total_income * 100) if prev_metric.total_income else 0.0
    arrow_inc = "🔺" if diff_inc >= 0 else "🔻"
    txt += f"Доходи: {data['total_income']:.2f} ({arrow_inc} {abs(pct_inc):.1f}% )\n"

    # 4.2. Витрати
    diff_exp = data["total_expense"] - prev_metric.total_expense
    pct_exp = (diff_exp / prev_metric.total_expense * 100) if prev_metric.total_expense else 0.0
    arrow_exp = "🔺" if diff_exp >= 0 else "🔻"
    txt += f"Витрати: {data['total_expense']:.2f} ({arrow_exp} {abs(pct_exp):.1f}% )\n"

    # 4.3. Середня добова витрата
    days_in_month = len(data["daily_expenses"])
    avg_daily = data["total_expense"] / days_in_month if days_in_month else 0.0
    diff_avg = avg_daily - prev_metric.avg_daily_expense
    pct_avg = (diff_avg / prev_metric.avg_daily_expense * 100) if prev_metric.avg_daily_expense else 0.0
    arrow_avg = "🔺" if diff_avg >= 0 else "🔻"
    txt += f"Середня добова витрата: {avg_daily:.2f} ({arrow_avg} {abs(pct_avg):.1f}% )\n"

    # 4.4. Топ-категорія
    if prev_metric.top_category == data["cat_expenses"] and prev_metric.top_category:
        txt += f"Найбільша категорія витрат залишилася: {prev_metric.top_category} ({prev_metric.top_category_pct:.1f}%)\n"
    else:
        if data["cat_expenses"]:
            top_cat_name, top_cat_amt = max(data["cat_expenses"].items(), key=lambda x: x[1])
            share = top_cat_amt / data["total_expense"] * 100 if data["total_expense"] else 0.0
            txt += f"Топ-категорія витрат змінилася: {top_cat_name} — {top_cat_amt:.2f} грн ({share:.1f}%)({prev_metric.top_category} ({prev_metric.top_category_pct:.1f}%))\n"

    return txt + "\n"


# --------------------------------------------
# 5. Побудова кругових діаграм
# --------------------------------------------
def build_pie_charts(cat_expenses: dict, cat_incomes: dict, start_dt: datetime.date, end_dt: datetime.date):
    labels_exp = list(cat_expenses.keys()) or ["Немає витрат"]
    sizes_exp = list(cat_expenses.values()) or [1.0]
    labels_inc = list(cat_incomes.keys()) or ["Немає доходів"]
    sizes_inc = list(cat_incomes.values()) or [1.0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4))
    ax1.pie(sizes_exp, labels=labels_exp, autopct="%1.1f%%", startangle=90)
    ax1.set_title("Витрати")
    ax2.pie(sizes_inc, labels=labels_inc, autopct="%1.1f%%", startangle=90)
    ax2.set_title("Доходи")
    fig.suptitle(f"Категорії: {start_dt}–{end_dt}")

    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return buf


# --------------------------------------------
# 6. Побудова лінійного графіку денних витрат
# --------------------------------------------
def build_daily_line_chart(daily_expenses: dict, start_dt: datetime.date, end_dt: datetime.date):
    dates = sorted(daily_expenses.keys())
    vals = [daily_expenses[d] for d in dates]
    max_val = max(vals) if vals else 0.0
    max_day = dates[vals.index(max_val)] if vals else None

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(dates, vals, color="red", label="Витрати")
    if max_day:
        ax.scatter([max_day], [max_val], color="black")
        ax.text(max_day, max_val, f"  Макс: {max_val:.2f}", fontsize=8)

    ax.set_title(f"Добові витрати: {start_dt}–{end_dt}")
    ax.set_xlabel("Дата")
    ax.set_ylabel("Сума витрат, грн")
    fig.autofmt_xdate()

    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return buf


# --------------------------------------------
# 7. Побудова стовпчикової діаграми зведених сум
# --------------------------------------------
def build_summary_bar_chart(total_income: float, total_expense: float, start_dt: datetime.date, end_dt: datetime.date):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["Доходи", "Витрати"], [total_income, total_expense], color=["green", "red"])
    ax.set_title(f"Зведений звіт: {start_dt}–{end_dt}")
    ax.set_ylabel("Сума, грн")

    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return buf


# --------------------------------------------
# 8. Побудова графіку курсів валют (НБУ + CoinGecko)
# --------------------------------------------
def build_currency_chart(start_dt: datetime.date, end_dt: datetime.date):
    """
    1) Збираємо USD→UAH та EUR→UAH через API НБУ;
    2) BTC→USD і ETH→USD через CoinGecko;
    3) Малюємо два підграфіки: фіат та крипто.
    """

    # --- 8.1. Функція для курсу USD/EUR→UAH з НБУ ---
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
            "days": (end - start).days + 1
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

    # Збираємо дані
    usd_series = fetch_timeseries_nbu("USD", start_dt, end_dt)
    eur_series = fetch_timeseries_nbu("EUR", start_dt, end_dt)
    btc_series = fetch_timeseries_crypto("bitcoin", "usd", start=start_dt, end=end_dt)
    eth_series = fetch_timeseries_crypto("ethereum", "usd", start=start_dt, end=end_dt)

    # Малюємо дві панелі
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=False)

    # ----- 8.3. Перший підграфік: USD→UAH та EUR→UAH -----
    if usd_series:
        dates_usd, vals_usd = zip(*usd_series)
        ax1.plot(dates_usd, vals_usd, label="USD/UAH", color="blue")
    if eur_series:
        dates_eur, vals_eur = zip(*eur_series)
        ax1.plot(dates_eur, vals_eur, label="EUR/UAH", color="orange")

    ax1.set_title("Середній курс фіат: USD та EUR → UAH")
    ax1.set_ylabel("Курс (UAH)")
    if usd_series or eur_series:
        ax1.legend()
    ax1.grid(True)

    # ----- 8.4. Другий підграфік: BTC→USD та ETH→USD -----
    if btc_series:
        dates_btc, vals_btc = zip(*btc_series)
        ax2.plot(dates_btc, vals_btc, label="BTC/USD", color="black")

    if eth_series:
        dates_eth, vals_eth = zip(*eth_series)
        ax2_sec = ax2.twinx()
        ax2_sec.plot(dates_eth, vals_eth, label="ETH/USD", color="gray", linestyle="--")
        ax2_sec.set_ylabel("ETH/USD", color="gray")
        ax2_sec.tick_params(axis="y", labelcolor="gray")

    ax2.set_title("Курс крипто: BTC та ETH → USD")
    ax2.set_xlabel("Дата")
    ax2.set_ylabel("BTC/USD", color="black")
    ax2.tick_params(axis="y", labelcolor="black")
    # Додаємо легенду лише якщо дані є
    if btc_series:
        ax2.legend(loc="upper left")
    ax2.grid(True)

    fig.autofmt_xdate()
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return buf


# --------------------------------------------
# 9. Форматуємо текстовий підсумок
# --------------------------------------------
def format_text_report(data: dict, comparison_text: str, start_dt: datetime.date, end_dt: datetime.date) -> str:
    total_income = data["total_income"]
    total_expense = data["total_expense"]
    balance = total_income - total_expense
    days_count = len(data["daily_expenses"])
    avg_daily = (total_expense / days_count) if days_count else 0.0
    save_pct = (balance / total_income * 100) if total_income else 0.0

    txt = f"📅 Звіт за {start_dt.strftime('%B %Y')}\n\n"
    txt += f"• Загальні доходи: {total_income:.2f} грн\n"
    txt += f"• Загальні витрати: {total_expense:.2f} грн\n"
    txt += f"• Баланс (заощаджено): {balance:.2f} грн ({save_pct:.1f}% доходів)\n\n"
    txt += "🔄 Порівняння з попереднім:\n" + comparison_text + "\n"

    # Топ-3 категорії витрат
    if data["cat_expenses"]:
        sorted_exp = sorted(data["cat_expenses"].items(), key=lambda x: x[1], reverse=True)
        txt += "🔥 Топ-3 категорії витрат:\n"
        for i, (cat, amt) in enumerate(sorted_exp[:3], start=1):
            pct = (amt / total_expense * 100) if total_expense else 0.0
            txt += f"   {i}. {cat} — {amt:.2f} грн ({pct:.1f}%)\n"
    else:
        txt += "🔥 Витрат не було.\n"

    # Топ-3 категорії доходів
    if data["cat_incomes"]:
        sorted_inc = sorted(data["cat_incomes"].items(), key=lambda x: x[1], reverse=True)
        txt += "💰 Топ-3 категорії доходів:\n"
        for i, (cat, amt) in enumerate(sorted_inc[:3], start=1):
            pct = (amt / total_income * 100) if total_income else 0.0
            txt += f"   {i}. {cat} — {amt:.2f} грн ({pct:.1f}%)\n"
    else:
        txt += "💰 Доходів не було.\n"

    txt += f"\n• Середня добова витрата: {avg_daily:.2f} грн\n"
    txt += f"• Середній курс USD→UAH: {data['avg_usd']:.2f} грн\n"
    txt += f"• Середній курс EUR→UAH: {data['avg_eur']:.2f} грн\n"

    return txt


# --------------------------------------------
# 10. Зберігаємо метрики в таблицю monthly_metrics
# --------------------------------------------
def save_monthly_metric(telegram_id: int, year_month: str, data: dict):
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        session.close()
        return

    metric = session.query(MonthlyMetric).filter(
        MonthlyMetric.user_id == user.id,
        MonthlyMetric.year_month == year_month
    ).first()

    # Знаходимо топ-категорію витрат
    top_cat = None
    top_pct = 0.0
    if data["cat_expenses"] and data["total_expense"] > 0:
        top_cat_name, top_cat_amt = max(data["cat_expenses"].items(), key=lambda x: x[1])
        top_cat = top_cat_name
        top_pct = (top_cat_amt / data["total_expense"]) * 100

    days_count = len(data["daily_expenses"])
    avg_daily = data["total_expense"] / days_count if days_count else 0.0

    if not metric:
        metric = MonthlyMetric(
            user_id=user.id,
            year_month=year_month,
            total_income=data["total_income"],
            total_expense=data["total_expense"],
            avg_daily_expense=avg_daily,
            top_category=top_cat,
            top_category_pct=top_pct,
            avg_usd=data["avg_usd"],
            avg_eur=data["avg_eur"]
        )
        session.add(metric)
    else:
        metric.total_income = data["total_income"]
        metric.total_expense = data["total_expense"]
        metric.avg_daily_expense = avg_daily
        metric.top_category = top_cat
        metric.top_category_pct = top_pct
        metric.avg_usd = data["avg_usd"]
        metric.avg_eur = data["avg_eur"]

    session.commit()
    session.close()
