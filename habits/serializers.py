"""Сериализаторы привычек."""
from rest_framework import serializers

from habits.models import Habit
from habits.validators import validate_habit_rules


class HabitSerializer(serializers.ModelSerializer):
    """Привычка. Владелец не передаётся клиентом — подставляется во view."""

    class Meta:
        model = Habit
        fields = "__all__"
        read_only_fields = ("owner", "created_at", "last_reminder_date")

    def validate(self, attrs):
        instance = self.instance

        def value(name, default=None):
            # PATCH: недостающие поля берём из instance, иначе правила обходятся изменением одного поля
            if name in attrs:
                return attrs[name]
            return getattr(instance, name) if instance is not None else default

        owner_id = instance.owner_id if instance is not None else self.context["request"].user.id
        errors = validate_habit_rules(
            owner_id=owner_id,
            is_pleasant=value("is_pleasant", False),
            related_habit=value("related_habit"),
            reward=value("reward", ""),
            instance=instance,
        )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
