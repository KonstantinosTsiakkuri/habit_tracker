"""Пагинация списков привычек."""
from rest_framework.pagination import LimitOffsetPagination


class HabitPagination(LimitOffsetPagination):
    """Ответ: count, next, previous, results. Параметры: ?limit=&offset=."""

    default_limit = 5  # по ТЗ — 5 привычек на страницу
    max_limit = 50  # защита от ?limit=1000000
