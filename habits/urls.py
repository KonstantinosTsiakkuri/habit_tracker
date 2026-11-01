from django.urls import path

from habits.apps import HabitsConfig
from habits.views import HabitDetailView, HabitListCreateView, PublicHabitListView

app_name = HabitsConfig.name

urlpatterns = [
    path("", HabitListCreateView.as_view(), name="list"),
    path("public/", PublicHabitListView.as_view(), name="public"),
    path("<int:pk>/", HabitDetailView.as_view(), name="detail"),
]
