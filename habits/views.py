"""Представления привычек."""
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from habits.models import Habit
from habits.paginators import HabitPagination
from habits.permissions import IsOwner
from habits.serializers import HabitSerializer


class HabitListCreateView(generics.ListCreateAPIView):
    """GET — список привычек текущего пользователя, POST — создание (владелец = request.user)."""

    serializer_class = HabitSerializer
    pagination_class = HabitPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Habit.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class HabitDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Просмотр, изменение и удаление СВОЕЙ привычки."""

    serializer_class = HabitSerializer
    permission_classes = (IsAuthenticated, IsOwner)

    def get_queryset(self):
        # Чужая привычка в queryset не попадает, поэтому отвечаем 404, а не 403
        return Habit.objects.filter(owner=self.request.user)


class PublicHabitListView(generics.ListAPIView):
    """Публичные привычки всех пользователей — только чтение."""

    serializer_class = HabitSerializer
    pagination_class = HabitPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Habit.objects.filter(is_public=True)
