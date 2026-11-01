"""Модель привычки."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from habits.validators import validate_duration, validate_habit_rules, validate_periodicity


class Habit(models.Model):
    """Привычка: «я буду [действие] в [время] в [место]»."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="habits",
        verbose_name="создатель",
    )
    place = models.CharField("место", max_length=255)
    time = models.TimeField("время выполнения")
    action = models.CharField("действие", max_length=255)
    is_pleasant = models.BooleanField("признак приятной привычки", default=False)
    related_habit = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dependent_habits",
        verbose_name="связанная привычка",
    )
    periodicity = models.PositiveSmallIntegerField(
        "периодичность (дней)", default=1, validators=[validate_periodicity]
    )
    reward = models.CharField("вознаграждение", max_length=255, blank=True)
    duration = models.PositiveSmallIntegerField(
        "время на выполнение (секунд)", validators=[validate_duration]
    )
    is_public = models.BooleanField("признак публичности", default=False)

    # Служебные поля
    created_at = models.DateTimeField("создана", auto_now_add=True)
    last_reminder_date = models.DateField("дата последнего напоминания", null=True, blank=True)

    class Meta:
        verbose_name = "привычка"
        verbose_name_plural = "привычки"
        ordering = ("time", "id")

    def __str__(self):
        return f"я буду {self.action} в {self.time:%H:%M} в {self.place}"

    def clean(self):
        """Те же правила, что в сериализаторе, — для админки и full_clean()."""
        super().clean()
        errors = validate_habit_rules(
            owner_id=self.owner_id,
            is_pleasant=self.is_pleasant,
            related_habit=self.related_habit if self.related_habit_id else None,
            reward=self.reward,
            instance=self,
        )
        if errors:
            raise ValidationError(errors)
