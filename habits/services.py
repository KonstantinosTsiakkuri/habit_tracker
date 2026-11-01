"""Сервисы привычек: отправка сообщений в Telegram и формирование текста напоминания."""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # секунд: зависший Telegram не должен блокировать воркер


def _mask_token(text):
    """Токен бота входит в URL запроса, поэтому прячем его из логов."""
    token = settings.TELEGRAM_BOT_TOKEN
    return str(text).replace(token, "***") if token else str(text)


def send_telegram_message(chat_id, text):
    """
    Отправляет сообщение в Telegram через Bot API (sendMessage).

    Возвращает True при успехе и False при любой ошибке: ошибки логируются, но не пробрасываются,
    чтобы сбой одного сообщения не ронял всю Celery-задачу.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN не задан, сообщение не отправлено")
        return False

    url = f"{settings.TELEGRAM_API_URL}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Не удалось отправить сообщение в чат %s: %s", chat_id, _mask_token(exc))
        return False
    return True


def build_reminder_text(habit):
    """Текст напоминания: «Я буду [действие] в [время] в [место]» + награда/связанная привычка + длительность."""
    lines = [f"Я буду {habit.action} в {habit.time:%H:%M} в {habit.place}"]
    if habit.reward:
        lines.append(f"Награда: {habit.reward}")
    elif habit.related_habit:
        lines.append(f"Приятная привычка после выполнения: {habit.related_habit.action}")
    lines.append(f"Время на выполнение: {habit.duration} сек.")
    return "\n".join(lines)
