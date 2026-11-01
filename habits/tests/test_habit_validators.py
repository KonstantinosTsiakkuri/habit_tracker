"""Тесты валидаторов привычки: на каждое правило — валидный, невалидный случай и обход через PATCH."""
import datetime
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from habits.models import Habit
from habits.serializers import HabitSerializer
from habits.validators import validate_duration, validate_periodicity
from users.models import User

pytestmark = pytest.mark.django_db


def payload(**overrides):
    """Минимально валидная полезная привычка."""
    data = {"place": "дом", "time": "08:00", "action": "пить воду", "duration": 60}
    data.update(overrides)
    return data


def create(user, data):
    """Создание через сериализатор. Возвращает (serializer, is_valid)."""
    serializer = HabitSerializer(data=data, context={"request": SimpleNamespace(user=user)})
    return serializer, serializer.is_valid()


def patch(habit, data):
    """Частичное обновление (PATCH) через сериализатор."""
    context = {"request": SimpleNamespace(user=habit.owner)}
    serializer = HabitSerializer(habit, data=data, partial=True, context=context)
    return serializer, serializer.is_valid()


def make_habit(user, **fields):
    defaults = {"place": "дом", "time": datetime.time(8, 0), "action": "пить воду", "duration": 60}
    defaults.update(fields)
    return Habit.objects.create(owner=user, **defaults)


@pytest.fixture
def pleasant(user):
    return make_habit(user, action="принять ванну", is_pleasant=True)


class TestRewardAndRelatedExclusive:
    """Нельзя одновременно вознаграждение и связанная привычка."""

    def test_reward_only_is_valid(self, user):
        assert create(user, payload(reward="кофе"))[1]

    def test_related_only_is_valid(self, user, pleasant):
        assert create(user, payload(related_habit=pleasant.id))[1]

    def test_both_is_invalid(self, user, pleasant):
        serializer, ok = create(user, payload(reward="кофе", related_habit=pleasant.id))
        assert not ok
        assert "related_habit" in serializer.errors

    def test_patch_adds_related_to_habit_with_reward(self, user, pleasant):
        habit = make_habit(user, reward="кофе")
        serializer, ok = patch(habit, {"related_habit": pleasant.id})
        assert not ok and "related_habit" in serializer.errors

    def test_patch_adds_reward_to_habit_with_related(self, user, pleasant):
        habit = make_habit(user, related_habit=pleasant)
        serializer, ok = patch(habit, {"reward": "кофе"})
        assert not ok and "related_habit" in serializer.errors


class TestDuration:
    """Время выполнения — не больше 120 секунд."""

    @pytest.mark.parametrize("value", [1, 60, 120])
    def test_valid(self, user, value):
        assert create(user, payload(duration=value))[1]

    @pytest.mark.parametrize("value", [0, 121, 500])
    def test_invalid(self, user, value):
        serializer, ok = create(user, payload(duration=value))
        assert not ok and "duration" in serializer.errors

    def test_patch_duration_over_limit(self, user):
        habit = make_habit(user)
        serializer, ok = patch(habit, {"duration": 500})
        assert not ok and "duration" in serializer.errors

    def test_validator_function(self):
        validate_duration(120)
        with pytest.raises(ValidationError):
            validate_duration(121)


class TestRelatedMustBePleasant:
    """В связанные попадают только приятные привычки."""

    def test_pleasant_is_valid(self, user, pleasant):
        assert create(user, payload(related_habit=pleasant.id))[1]

    def test_non_pleasant_is_invalid(self, user):
        useful = make_habit(user, action="бегать")
        serializer, ok = create(user, payload(related_habit=useful.id))
        assert not ok and "related_habit" in serializer.errors

    def test_patch_related_to_non_pleasant(self, user):
        useful = make_habit(user, action="бегать")
        habit = make_habit(user)
        serializer, ok = patch(habit, {"related_habit": useful.id})
        assert not ok and "related_habit" in serializer.errors

    def test_patch_cannot_unmark_pleasant_used_as_related(self, user, pleasant):
        make_habit(user, related_habit=pleasant)
        serializer, ok = patch(pleasant, {"is_pleasant": False})
        assert not ok and "is_pleasant" in serializer.errors

    def test_unmark_pleasant_not_used_is_ok(self, pleasant):
        assert patch(pleasant, {"is_pleasant": False})[1]


class TestPleasantHabitRestrictions:
    """У приятной привычки нет вознаграждения и связанной привычки."""

    def test_pleasant_without_reward_is_valid(self, user):
        assert create(user, payload(is_pleasant=True))[1]

    def test_pleasant_with_reward_is_invalid(self, user):
        serializer, ok = create(user, payload(is_pleasant=True, reward="кофе"))
        assert not ok and "reward" in serializer.errors

    def test_pleasant_with_related_is_invalid(self, user, pleasant):
        serializer, ok = create(user, payload(is_pleasant=True, related_habit=pleasant.id))
        assert not ok and "related_habit" in serializer.errors

    def test_patch_reward_to_pleasant(self, pleasant):
        serializer, ok = patch(pleasant, {"reward": "кофе"})
        assert not ok and "reward" in serializer.errors

    def test_patch_make_habit_with_reward_pleasant(self, user):
        habit = make_habit(user, reward="кофе")
        serializer, ok = patch(habit, {"is_pleasant": True})  # reward берётся из instance
        assert not ok and "reward" in serializer.errors

    def test_patch_make_habit_with_related_pleasant(self, user, pleasant):
        habit = make_habit(user, related_habit=pleasant)
        serializer, ok = patch(habit, {"is_pleasant": True})  # related_habit берётся из instance
        assert not ok and "related_habit" in serializer.errors


class TestPeriodicity:
    """Периодичность — от 1 до 7 дней."""

    @pytest.mark.parametrize("value", [1, 3, 7])
    def test_valid(self, user, value):
        assert create(user, payload(periodicity=value))[1]

    @pytest.mark.parametrize("value", [0, 8, 30])
    def test_invalid(self, user, value):
        serializer, ok = create(user, payload(periodicity=value))
        assert not ok and "periodicity" in serializer.errors

    def test_default_is_one(self, user):
        serializer, ok = create(user, payload())
        assert ok and serializer.validated_data.get("periodicity", 1) == 1

    def test_patch_periodicity_over_limit(self, user):
        habit = make_habit(user)
        serializer, ok = patch(habit, {"periodicity": 10})
        assert not ok and "periodicity" in serializer.errors

    def test_validator_function(self):
        validate_periodicity(7)
        with pytest.raises(ValidationError):
            validate_periodicity(8)


class TestRelatedOwnerAndSelfReference:
    """Дополнительно: связанная привычка — своя и не сама на себя."""

    def test_own_related_is_valid(self, user, pleasant):
        assert create(user, payload(related_habit=pleasant.id))[1]

    def test_foreign_related_is_invalid(self, user, other_user):
        foreign = make_habit(other_user, is_pleasant=True)
        serializer, ok = create(user, payload(related_habit=foreign.id))
        assert not ok and "related_habit" in serializer.errors

    def test_patch_foreign_related_is_invalid(self, user, other_user):
        foreign = make_habit(other_user, is_pleasant=True)
        habit = make_habit(user)
        serializer, ok = patch(habit, {"related_habit": foreign.id})
        assert not ok and "related_habit" in serializer.errors

    def test_self_reference_is_invalid(self, user):
        habit = make_habit(user)
        serializer, ok = patch(habit, {"related_habit": habit.id})
        assert not ok
        assert any("сама с собой" in str(e) for e in serializer.errors["related_habit"])


class TestSerializerOutput:
    def test_owner_and_service_fields_are_read_only(self, user, other_user):
        serializer, ok = create(user, payload(owner=other_user.id, last_reminder_date="2020-01-01"))
        assert ok
        assert "owner" not in serializer.validated_data
        assert "last_reminder_date" not in serializer.validated_data

    def test_required_fields(self, user):
        serializer, ok = create(user, {})
        assert not ok
        assert {"place", "time", "action", "duration"} <= set(serializer.errors)


class TestModelClean:
    """Те же правила через Model.full_clean() (так работает админка)."""

    @staticmethod
    def build(user, **fields):
        data = {"place": "дом", "time": datetime.time(8, 0), "action": "бегать", "duration": 60}
        data.update(fields)
        return Habit(owner=user, **data)

    def test_valid(self, user):
        self.build(user).full_clean()

    def test_both_reward_and_related(self, user, pleasant):
        habit = self.build(user, reward="кофе", related_habit=pleasant)
        with pytest.raises(ValidationError) as exc:
            habit.full_clean()
        assert "related_habit" in exc.value.message_dict

    def test_pleasant_with_reward(self, user):
        habit = self.build(user, is_pleasant=True, reward="кофе")
        with pytest.raises(ValidationError) as exc:
            habit.full_clean()
        assert "reward" in exc.value.message_dict

    def test_field_validators(self, user):
        habit = self.build(user, duration=500, periodicity=9)
        with pytest.raises(ValidationError) as exc:
            habit.full_clean()
        assert {"duration", "periodicity"} <= set(exc.value.message_dict)

    def test_self_reference_in_clean(self, user):
        habit = make_habit(user, is_pleasant=True)
        habit.related_habit = habit
        with pytest.raises(ValidationError):
            habit.full_clean()


class TestModelAndAdmin:
    def test_str_format(self, user):
        habit = make_habit(user, action="бегать", place="парк", time=datetime.time(7, 30))
        assert str(habit) == "я буду бегать в 07:30 в парк"

    def test_defaults(self, user):
        habit = make_habit(user)
        assert habit.periodicity == 1
        assert habit.is_pleasant is False and habit.is_public is False
        assert habit.reward == "" and habit.related_habit is None
        assert habit.last_reminder_date is None and habit.created_at is not None

    def test_related_set_null_on_delete(self, user, pleasant):
        habit = make_habit(user, related_habit=pleasant)
        pleasant.delete()
        habit.refresh_from_db()
        assert habit.related_habit is None

    def test_ordering_by_time(self, user):
        late = make_habit(user, time=datetime.time(20, 0))
        early = make_habit(user, time=datetime.time(6, 0))
        assert list(Habit.objects.all()) == [early, late]

    def test_admin_pages(self, client, user):
        admin = User.objects.create_superuser(email="root@example.com", password="StrongPass123!")
        client.force_login(admin)
        habit = make_habit(user)
        assert client.get(reverse("admin:habits_habit_changelist")).status_code == 200
        assert client.get(reverse("admin:habits_habit_add")).status_code == 200
        assert client.get(reverse("admin:habits_habit_change", args=[habit.id])).status_code == 200
