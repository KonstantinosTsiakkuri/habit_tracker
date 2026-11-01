"""Представления привычек."""
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from habits.models import Habit
from habits.paginators import HabitPagination
from habits.permissions import IsOwner
from habits.serializers import HabitSerializer

UNAUTHORIZED = OpenApiResponse(description="Не авторизован: нет токена или он недействителен")
VALIDATION_ERROR = OpenApiResponse(description="Ошибка валидации (нарушено правило привычки)")
NOT_FOUND = OpenApiResponse(description="Привычка не найдена (в том числе чужая)")

HABIT_EXAMPLE = {
    "id": 1,
    "owner": 1,
    "place": "парк",
    "time": "07:30:00",
    "action": "бегать",
    "is_pleasant": False,
    "related_habit": None,
    "periodicity": 1,
    "reward": "выпить кофе",
    "duration": 90,
    "is_public": False,
    "created_at": "2026-11-01T10:00:00+03:00",
    "last_reminder_date": None,
}
HABIT_REQUEST_EXAMPLE = {
    "place": "парк",
    "time": "07:30",
    "action": "бегать",
    "periodicity": 1,
    "reward": "выпить кофе",
    "duration": 90,
    "is_public": False,
}
PAGE_EXAMPLE = {
    "count": 7,
    "next": "http://127.0.0.1:8000/habits/?limit=5&offset=5",
    "previous": None,
    "results": [HABIT_EXAMPLE],
}


@extend_schema_view(
    get=extend_schema(
        tags=["habits"],
        summary="Список моих привычек",
        description=(
            "Только привычки текущего пользователя. Пагинация: `limit` (по умолчанию 5, максимум 50) и `offset`."
        ),
        responses={200: HabitSerializer(many=True), 401: UNAUTHORIZED},
        examples=[OpenApiExample("Ответ", value=PAGE_EXAMPLE, response_only=True, status_codes=["200"])],
    ),
    post=extend_schema(
        tags=["habits"],
        summary="Создать привычку",
        description=(
            "Владелец подставляется автоматически (текущий пользователь). Правила: либо `reward`, либо "
            "`related_habit` (но не оба); связанная привычка — только своя и приятная; у приятной привычки нет "
            "награды и связанной привычки; `duration` ≤ 120 секунд; `periodicity` от 1 до 7 дней."
        ),
        responses={201: HabitSerializer, 400: VALIDATION_ERROR, 401: UNAUTHORIZED},
        examples=[
            OpenApiExample("Запрос", value=HABIT_REQUEST_EXAMPLE, request_only=True),
            OpenApiExample("Успешный ответ", value=HABIT_EXAMPLE, response_only=True, status_codes=["201"]),
            OpenApiExample(
                "Ошибка: награда и связанная привычка одновременно",
                value={"related_habit": ["Нельзя одновременно указывать вознаграждение и связанную привычку."]},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
class HabitListCreateView(generics.ListCreateAPIView):
    """GET — список привычек текущего пользователя, POST — создание (владелец = request.user)."""

    serializer_class = HabitSerializer
    pagination_class = HabitPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Habit.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=["habits"],
        summary="Получить свою привычку",
        responses={200: HabitSerializer, 401: UNAUTHORIZED, 404: NOT_FOUND},
        examples=[OpenApiExample("Ответ", value=HABIT_EXAMPLE, response_only=True, status_codes=["200"])],
    ),
    put=extend_schema(
        tags=["habits"],
        summary="Обновить свою привычку целиком",
        responses={200: HabitSerializer, 400: VALIDATION_ERROR, 401: UNAUTHORIZED, 404: NOT_FOUND},
        examples=[OpenApiExample("Запрос", value=HABIT_REQUEST_EXAMPLE, request_only=True)],
    ),
    patch=extend_schema(
        tags=["habits"],
        summary="Частично обновить свою привычку",
        description="Правила проверяются по итоговому состоянию: недостающие поля берутся из текущей привычки.",
        responses={200: HabitSerializer, 400: VALIDATION_ERROR, 401: UNAUTHORIZED, 404: NOT_FOUND},
        examples=[OpenApiExample("Запрос", value={"is_public": True}, request_only=True)],
    ),
    delete=extend_schema(
        tags=["habits"],
        summary="Удалить свою привычку",
        responses={204: OpenApiResponse(description="Привычка удалена"), 401: UNAUTHORIZED, 404: NOT_FOUND},
    ),
)
class HabitDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Просмотр, изменение и удаление СВОЕЙ привычки."""

    serializer_class = HabitSerializer
    permission_classes = (IsAuthenticated, IsOwner)

    def get_queryset(self):
        # Чужая привычка в queryset не попадает, поэтому отвечаем 404, а не 403
        return Habit.objects.filter(owner=self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=["habits"],
        summary="Список публичных привычек",
        description=(
            "Публичные привычки всех пользователей (`is_public=true`). Только чтение. "
            "Пагинация: `limit` (по умолчанию 5, максимум 50) и `offset`."
        ),
        responses={200: HabitSerializer(many=True), 401: UNAUTHORIZED},
        examples=[OpenApiExample("Ответ", value=PAGE_EXAMPLE, response_only=True, status_codes=["200"])],
    )
)
class PublicHabitListView(generics.ListAPIView):
    """Публичные привычки всех пользователей — только чтение."""

    serializer_class = HabitSerializer
    pagination_class = HabitPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Habit.objects.filter(is_public=True)
