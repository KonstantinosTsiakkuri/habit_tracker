"""Celery-задачи привычек."""
import logging

from celery import shared_task
from django.utils import timezone

from habits.models import Habit
from habits.services import build_reminder_text, send_telegram_message

logger = logging.getLogger(__name__)


def _now():
    """Текущее время в TIME_ZONE проекта (вынесено в функцию, чтобы подменять в тестах)."""
    return timezone.localtime()


def _is_due(habit, today):
    """Пора ли напоминать: напоминаний не было или с последнего прошло >= periodicity дней."""
    if habit.last_reminder_date is None:
        return True
    return (today - habit.last_reminder_date).days >= habit.periodicity


@shared_task
def send_habit_reminders():
    """
    Запускается каждую минуту (CELERY_BEAT_SCHEDULE) и рассылает напоминания о полезных привычках,
    время которых совпадает с текущей минутой. Возвращает число отправленных напоминаний.
    """
    now = _now()
    today = now.date()
    habits = Habit.objects.filter(
        is_pleasant=False,
        time__hour=now.hour,
        time__minute=now.minute,
        owner__tg_chat_id__isnull=False,
    ).select_related("owner", "related_habit")

    sent = 0
    for habit in habits:
        if not _is_due(habit, today):
            continue
        try:
            if send_telegram_message(habit.owner.tg_chat_id, build_reminder_text(habit)):
                habit.last_reminder_date = today
                habit.save(update_fields=["last_reminder_date"])
                sent += 1
        except Exception:  # одна «плохая» привычка не должна остановить рассылку остальным
            logger.exception("Ошибка при обработке привычки %s", habit.pk)
    return sent
