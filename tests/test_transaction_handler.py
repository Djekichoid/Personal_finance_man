import pytest
from unittest.mock import MagicMock
from bot.handlers.transaction_handler import expense_amount, income_amount
from bot.handlers.start_handler import get_main_menu


class DummyMessage:
    def __init__(self, text, user_id=1, chat_id=123):
        self.text = text
        self.chat = type("C", (object,), {"id": chat_id})()
        self.from_user = type("U", (object,), {"id": user_id})()


# Ця фікстура мокатиме тільки для expense-тестів
@pytest.fixture(autouse=True)
def patch_bot(monkeypatch):
    fake_send = MagicMock()
    fake_register = MagicMock()
    # Підміняємо send_message і register_next_step_handler саме там, де їх викликає expense_amount
    monkeypatch.setattr(
        'bot.handlers.transaction_handler.bot.send_message',
        fake_send
    )
    monkeypatch.setattr(
        'bot.handlers.transaction_handler.bot.register_next_step_handler',
        fake_register
    )
    monkeypatch.setattr(
        'bot.handlers.transaction_handler.get_main_menu',
        lambda: "MAIN_MENU"
    )
    return fake_send, fake_register


def test_expense_amount_back(patch_bot):
    fake_send, fake_register = patch_bot
    msg = DummyMessage("🔙 Назад")
    expense_amount(msg)

    fake_send.assert_called_once_with(
        msg.chat.id,
        "Додавання витрати скасовано.",
        reply_markup="MAIN_MENU"
    )
    fake_register.assert_not_called()


def test_expense_amount_invalid(patch_bot):
    fake_send, fake_register = patch_bot
    msg = DummyMessage("abc")
    expense_amount(msg)

    fake_send.assert_called_once_with(
        msg.chat.id,
        "Невірна сума. Спробуйте ще раз.",
        reply_markup="MAIN_MENU"
    )
    fake_register.assert_not_called()


def test_expense_amount_valid_triggers_next_step(monkeypatch, patch_bot):
    fake_send, fake_register = patch_bot

    # Повертаємо дві категорії для будь-якого telegram_id
    class Cat:
        def __init__(self, name): self.name = name

    monkeypatch.setattr(
        'bot.handlers.transaction_handler.fetch_categories',
        lambda telegram_id, ctype: [Cat("Food"), Cat("Taxi")]
    )

    msg = DummyMessage("200.5")
    expense_amount(msg)

    # Перевіряємо, що перший виклик send_message містить наш chat.id і правильний текст
    first_call = fake_send.call_args_list[0]
    assert first_call[0][0] == msg.chat.id
    assert first_call[0][1] == "Оберіть категорію:"

    # І має бути щонайменше один виклик register_next_step_handler
    assert fake_register.call_count == 1


# Цю фікстуру використовуємо тільки для income-тестів
@pytest.fixture()
def patch_bot_income(monkeypatch):
    fake_send = MagicMock()
    fake_register = MagicMock()
    monkeypatch.setattr(
        'bot.handlers.transaction_handler.bot.send_message',
        fake_send
    )
    monkeypatch.setattr(
        'bot.handlers.transaction_handler.bot.register_next_step_handler',
        fake_register
    )
    monkeypatch.setattr(
        'bot.handlers.transaction_handler.fetch_categories',
        lambda telegram_id, ctype: []
    )
    monkeypatch.setattr(
        'bot.handlers.transaction_handler.get_main_menu',
        lambda: "MAIN_MENU"
    )
    return fake_send, fake_register


def test_income_amount_back(patch_bot_income):
    fake_send, fake_register = patch_bot_income
    msg = DummyMessage("🔙 Назад")
    income_amount(msg)

    fake_send.assert_called_once_with(
        msg.chat.id,
        "Додавання доходу скасовано.",
        reply_markup="MAIN_MENU"
    )
    fake_register.assert_not_called()


def test_income_amount_invalid(patch_bot_income):
    fake_send, fake_register = patch_bot_income
    msg = DummyMessage("notanumber")
    income_amount(msg)

    fake_send.assert_called_once_with(
        msg.chat.id,
        "Невірна сума. Спробуйте ще раз.",
        reply_markup="MAIN_MENU"
    )
    fake_register.assert_not_called()
