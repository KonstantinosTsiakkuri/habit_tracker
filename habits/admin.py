"""Админка привычек."""
from django.contrib import admin

from habits.models import Habit


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "time", "place", "owner", "is_pleasant", "is_public", "periodicity")
    list_filter = ("is_pleasant", "is_public", "periodicity")
    search_fields = ("action", "place", "owner__email")
    readonly_fields = ("created_at",)
