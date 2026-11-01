"""Фикстуры тестов привычек: сеть Telegram замокана всегда, реальных запросов быть не может."""
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def telegram_post(settings):
    """Подменяет requests.post и задаёт тестовый токен бота."""
    settings.TELEGRAM_BOT_TOKEN = "123456:TEST-TOKEN"
    settings.TELEGRAM_API_URL = "https://api.telegram.org"
    with mock.patch("habits.services.requests.post") as post:
        post.return_value.raise_for_status.return_value = None
        yield post
