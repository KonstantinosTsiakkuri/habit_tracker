"""Тесты отправки в Telegram и Celery-задачи напоминаний (requests.post замокан)."""
import datetime
import logging
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
import requests

from config.celery import app as celery_app
from habits.models import Habit
from habits.services import build_reminder_text, send_telegram_message
from habits.tasks import send_habit_reminders

pytestmark = pytest.mark.django_db

MOSCOW = ZoneInfo("Europe/Moscow")
NOW = datetime.datetime(2026, 11, 2, 8, 0, 15, tzinfo=MOSCOW)  # 08:00:15 по Москве
TODAY = NOW.date()


@pytest.fixture
def now():
    """Фиксирует «текущее время» задачи."""
    with mock.patch("habits.tasks._now", return_value=NOW):
        yield NOW


@pytest.fixture
def chat_user(user):
    user.tg_chat_id = 111222333
    user.save()
    return user


def make_habit(owner, **fields):
    defaults = {"place": "дом", "time": datetime.time(8, 0), "action": "пить воду", "duration": 60}
    defaults.update(fields)
    return Habit.objects.create(owner=owner, **defaults)


class TestSendTelegramMessage:
    def test_success_calls_bot_api(self, telegram_post):
        assert send_telegram_message(555, "привет") is True
        telegram_post.assert_called_once()
        args, kwargs = telegram_post.call_args
        assert args[0] == "https://api.telegram.org/bot123456:TEST-TOKEN/sendMessage"
        assert kwargs["json"] == {"chat_id": 555, "text": "привет"}
        assert kwargs["timeout"] > 0

    def test_uses_api_url_from_settings(self, telegram_post, settings):
        settings.TELEGRAM_API_URL = "http://localhost:8081"
        send_telegram_message(1, "x")
        assert telegram_post.call_args[0][0] == "http://localhost:8081/bot123456:TEST-TOKEN/sendMessage"

    def test_no_token_does_not_send(self, telegram_post, settings, caplog):
        settings.TELEGRAM_BOT_TOKEN = ""
        with caplog.at_level(logging.WARNING):
            assert send_telegram_message(1, "x") is False
        telegram_post.assert_not_called()
        assert "TELEGRAM_BOT_TOKEN" in caplog.text

    @pytest.mark.parametrize("error", [requests.ConnectionError("нет сети"), requests.Timeout("таймаут")])
    def test_network_error_is_logged_not_raised(self, telegram_post, caplog, error):
        telegram_post.side_effect = error
        with caplog.at_level(logging.ERROR):
            assert send_telegram_message(1, "x") is False
        assert "Не удалось отправить" in caplog.text

    def test_http_error_returns_false(self, telegram_post):
        telegram_post.return_value.raise_for_status.side_effect = requests.HTTPError("400 Bad Request")
        assert send_telegram_message(1, "x") is False

    def test_token_is_not_leaked_into_logs(self, telegram_post, caplog):
        telegram_post.side_effect = requests.ConnectionError("failed: .../bot123456:TEST-TOKEN/sendMessage")
        with caplog.at_level(logging.ERROR):
            send_telegram_message(1, "x")
        assert "123456:TEST-TOKEN" not in caplog.text
        assert "***" in caplog.text


class TestReminderText:
    def test_with_reward(self, user):
        habit = make_habit(user, action="бегать", place="парк", time=datetime.time(7, 30), reward="кофе", duration=90)
        text = build_reminder_text(habit)
        assert text.splitlines()[0] == "Я буду бегать в 07:30 в парк"
        assert "Награда: кофе" in text
        assert "Время на выполнение: 90 сек." in text

    def test_with_related_habit(self, user):
        pleasant = make_habit(user, action="принять ванну", is_pleasant=True)
        habit = make_habit(user, related_habit=pleasant)
        assert "Приятная привычка после выполнения: принять ванну" in build_reminder_text(habit)

    def test_without_reward_and_related(self, user):
        text = build_reminder_text(make_habit(user))
        assert "Награда" not in text and "Приятная" not in text
        assert text.endswith("Время на выполнение: 60 сек.")


class TestSendHabitReminders:
    def test_sends_matching_habit_and_updates_date(self, chat_user, now, telegram_post):
        habit = make_habit(chat_user, reward="кофе")
        assert send_habit_reminders() == 1
        kwargs = telegram_post.call_args.kwargs
        assert kwargs["json"]["chat_id"] == 111222333
        assert "Я буду пить воду в 08:00 в дом" in kwargs["json"]["text"]
        habit.refresh_from_db()
        assert habit.last_reminder_date == TODAY

    def test_time_with_seconds_matches_by_minute(self, chat_user, now, telegram_post):
        make_habit(chat_user, time=datetime.time(8, 0, 40))
        assert send_habit_reminders() == 1

    def test_other_minute_is_skipped(self, chat_user, now, telegram_post):
        make_habit(chat_user, time=datetime.time(8, 1))
        make_habit(chat_user, time=datetime.time(9, 0))
        assert send_habit_reminders() == 0
        telegram_post.assert_not_called()

    def test_owner_without_chat_id_is_skipped(self, user, now, telegram_post):
        habit = make_habit(user)
        assert user.tg_chat_id is None
        assert send_habit_reminders() == 0
        telegram_post.assert_not_called()
        habit.refresh_from_db()
        assert habit.last_reminder_date is None

    def test_pleasant_habit_is_skipped(self, chat_user, now, telegram_post):
        make_habit(chat_user, is_pleasant=True)
        assert send_habit_reminders() == 0
        telegram_post.assert_not_called()

    def test_first_reminder_when_never_sent(self, chat_user, now):
        make_habit(chat_user, periodicity=7, last_reminder_date=None)
        assert send_habit_reminders() == 1

    @pytest.mark.parametrize(
        "periodicity, days_ago, expected",
        [
            (1, 0, 0),  # уже напоминали сегодня
            (1, 1, 1),  # ежедневная, напоминали вчера
            (2, 1, 0),  # раз в 2 дня, прошёл 1 день
            (2, 2, 1),  # раз в 2 дня, прошло 2 дня
            (7, 6, 0),
            (7, 7, 1),
            (3, 10, 1),
        ],
    )
    def test_periodicity(self, chat_user, now, periodicity, days_ago, expected):
        make_habit(chat_user, periodicity=periodicity, last_reminder_date=TODAY - datetime.timedelta(days=days_ago))
        assert send_habit_reminders() == expected

    def test_second_run_in_same_minute_does_not_duplicate(self, chat_user, now, telegram_post):
        make_habit(chat_user)
        assert send_habit_reminders() == 1
        assert send_habit_reminders() == 0
        assert telegram_post.call_count == 1

    def test_failed_send_keeps_date_and_task_does_not_fail(self, chat_user, now, telegram_post):
        telegram_post.side_effect = requests.ConnectionError("нет сети")
        habit = make_habit(chat_user)
        assert send_habit_reminders() == 0
        habit.refresh_from_db()
        assert habit.last_reminder_date is None

    def test_error_in_one_habit_does_not_stop_others(self, chat_user, now, telegram_post, caplog):
        first = make_habit(chat_user, action="первая")
        second = make_habit(chat_user, action="вторая")
        with mock.patch("habits.tasks.build_reminder_text", side_effect=[RuntimeError("сбой"), "текст"]):
            with caplog.at_level(logging.ERROR):
                assert send_habit_reminders() == 1
        first.refresh_from_db()
        second.refresh_from_db()
        assert [first.last_reminder_date, second.last_reminder_date].count(TODAY) == 1
        assert "Ошибка при обработке привычки" in caplog.text

    def test_several_users_get_own_messages(self, chat_user, other_user, now, telegram_post):
        other_user.tg_chat_id = 999
        other_user.save()
        make_habit(chat_user)
        make_habit(other_user)
        assert send_habit_reminders() == 2
        chats = {call.kwargs["json"]["chat_id"] for call in telegram_post.call_args_list}
        assert chats == {111222333, 999}

    def test_uses_project_timezone_by_default(self, chat_user, telegram_post):
        """Без подмены времени задача не падает и берёт локальное время проекта (Europe/Moscow)."""
        assert send_habit_reminders() >= 0


class TestCeleryConfig:
    def test_beat_schedule_runs_task_every_minute(self):
        entry = celery_app.conf.beat_schedule["send-habit-reminders"]
        assert entry["task"] == "habits.tasks.send_habit_reminders"
        assert entry["schedule"].minute == set(range(60))
        assert entry["schedule"].hour == set(range(24))

    def test_task_name_matches_schedule(self):
        assert send_habit_reminders.name == "habits.tasks.send_habit_reminders"

    def test_timezone_and_scheduler(self):
        assert celery_app.conf.timezone == "Europe/Moscow"
        assert celery_app.conf.beat_scheduler == "django_celery_beat.schedulers:DatabaseScheduler"

    def test_task_can_run_via_apply(self, chat_user, now):
        make_habit(chat_user)
        result = send_habit_reminders.apply()
        assert result.successful() and result.result == 1
