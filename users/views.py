"""Представления пользователей: регистрация и профиль (вход и refresh — из simplejwt)."""
from rest_framework import generics
from rest_framework.permissions import AllowAny

from users.serializers import UserProfileSerializer, UserRegisterSerializer


class RegisterView(generics.CreateAPIView):
    """Регистрация нового пользователя (доступна без авторизации)."""

    serializer_class = UserRegisterSerializer
    permission_classes = (AllowAny,)


class MeView(generics.RetrieveUpdateAPIView):
    """Просмотр и редактирование собственного профиля (GET/PATCH/PUT)."""

    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user
