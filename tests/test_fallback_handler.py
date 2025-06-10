from unittest.mock import MagicMock
import pytest
from bot.handlers.fallback_handler import handle_invalid_main


class DummyMessage:
    def __init__(self, text, chat_id=321):
        self.text = text
        self.chat = type("C", (object,), {"id": chat_id})()


@pytest.fixture(autouse=True)
def patch_bot(monkeypatch):
    fake_send = MagicMock()
    monkeypatch.setattr('bot.handlers.fallback_handler.bot.send_message', fake_send)
    monkeypatch.setattr('bot.handlers.fallback_handler.get_main_menu', lambda: "MAIN_MENU")
    return fake_send


def test_fallback_ignores_valid(patch_bot):
    msg = DummyMessage("➕ Витрата")
    handle_invalid_main(msg)
    # для валідної кнопки не має виклику send_message
    patch_bot.assert_not_called()


def test_fallback_handles_invalid(patch_bot):
    msg = DummyMessage("random text")
    handle_invalid_main(msg)
    patch_bot.assert_called_once_with(
        msg.chat.id,
        "Вибачте, я не розумію цю команду. Будь ласка, оберіть опцію з меню.",
        reply_markup="MAIN_MENU"
    )
