import pytest
import datetime
from bot.models import User, Category, Transaction, MonthlyMetric


def test_user_crud(session):
    # Створення нового користувача
    u = User(telegram_id=42, username="alice")
    session.add(u)
    session.commit()

    # Отримання за telegram_id
    retrieved = session.query(User).filter_by(telegram_id=42).one()
    assert retrieved.username == "alice"


def test_category_crud(session):
    # Перш за все створимо користувача
    user = User(telegram_id=99, username="bob")
    session.add(user)
    session.flush()  # щоб отримати user.id

    # Створення категорії
    cat = Category(name="Food", type="expense", user_id=user.id)
    session.add(cat)
    session.commit()

    got = session.query(Category).filter_by(user_id=user.id).one()
    assert got.name == "Food"
    assert got.user_id == user.id


def test_transaction_crud(session):
    # Підготуємо користувача та категорію
    user = User(telegram_id=7, username="carol")
    session.add(user)
    session.flush()

    cat = Category(name="Transport", type="expense", user_id=user.id)
    session.add(cat)
    session.flush()

    # Створимо транзакцію
    tx = Transaction(
        amount=123.45,
        date=datetime.date(2025, 5, 10),
        type="expense",
        user_id=user.id,
        category_id=cat.id,
        note="Taxi ride"
    )
    session.add(tx)
    session.commit()

    stored = session.query(Transaction).filter_by(user_id=user.id).one()
    assert stored.amount == 123.45
    assert stored.category_id == cat.id
    assert stored.note == "Taxi ride"


def test_monthly_metric_crud(session):
    # Підготовка
    user = User(telegram_id=55, username="dave")
    session.add(user)
    session.flush()

    ym = "2025-05"
    metric = MonthlyMetric(
        user_id=user.id,
        year_month=ym,
        total_income=1000.0,
        total_expense=500.0,
        avg_daily_expense=16.67,
        top_category="Food",
        top_category_pct=0.45,
        avg_usd=27.5,
        avg_eur=30.0
    )
    session.add(metric)
    session.commit()

    fetched = session.query(MonthlyMetric).filter_by(user_id=user.id, year_month=ym).one()
    assert fetched.total_income == 1000.0
    assert fetched.top_category == "Food"
    assert fetched.avg_eur == 30.0
