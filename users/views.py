"""Представления пользователей: регистрация, вход, обновление токена и профиль."""
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.serializers import (
    TokenAccessSerializer,
    TokenPairSerializer,
    UserProfileSerializer,
    UserRegisterSerializer,
)

UNAUTHORIZED = OpenApiResponse(description="Не авторизован: нет токена или он недействителен")
VALIDATION_ERROR = OpenApiResponse(description="Ошибка валидации")


@extend_schema_view(
    post=extend_schema(
        tags=["users"],
        summary="Регистрация пользователя",
        description=(
            "Создаёт пользователя. Логином служит email, пароль хешируется и в ответе не возвращается. "
            "Доступно без авторизации."
        ),
        request=UserRegisterSerializer,
        responses={
            201: UserRegisterSerializer,
            400: OpenApiResponse(description="Ошибка валидации: email занят, слабый пароль и т.п."),
        },
        examples=[
            OpenApiExample(
                "Запрос",
                value={"email": "user@example.com", "password": "StrongPass123!"},
                request_only=True,
            ),
            OpenApiExample(
                "Успешный ответ",
                value={
                    "id": 1,
                    "email": "user@example.com",
                    "first_name": "",
                    "last_name": "",
                    "tg_chat_id": None,
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
)
class RegisterView(generics.CreateAPIView):
    """Регистрация нового пользователя (доступна без авторизации)."""

    serializer_class = UserRegisterSerializer
    permission_classes = (AllowAny,)


@extend_schema_view(
    post=extend_schema(
        tags=["users"],
        summary="Вход: получение пары JWT-токенов",
        description="По email и паролю возвращает `access` (для запросов) и `refresh` (для обновления access).",
        responses={200: TokenPairSerializer, 401: OpenApiResponse(description="Неверный email или пароль")},
        examples=[
            OpenApiExample(
                "Запрос",
                value={"email": "user@example.com", "password": "StrongPass123!"},
                request_only=True,
            ),
            OpenApiExample(
                "Успешный ответ",
                value={"refresh": "eyJhbGciOi...", "access": "eyJhbGciOi..."},
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
)
class LoginView(TokenObtainPairView):
    """Вход по email и паролю."""


@extend_schema_view(
    post=extend_schema(
        tags=["users"],
        summary="Обновление access-токена",
        description="По действующему `refresh`-токену выдаёт новый `access`.",
        responses={200: TokenAccessSerializer, 401: OpenApiResponse(description="Refresh-токен недействителен")},
        examples=[
            OpenApiExample("Запрос", value={"refresh": "eyJhbGciOi..."}, request_only=True),
            OpenApiExample(
                "Успешный ответ", value={"access": "eyJhbGciOi..."}, response_only=True, status_codes=["200"]
            ),
        ],
    )
)
class RefreshView(TokenRefreshView):
    """Обновление access-токена."""


@extend_schema_view(
    get=extend_schema(
        tags=["users"],
        summary="Мой профиль",
        responses={200: UserProfileSerializer, 401: UNAUTHORIZED},
        examples=[
            OpenApiExample(
                "Ответ",
                value={
                    "id": 1,
                    "email": "user@example.com",
                    "first_name": "Иван",
                    "last_name": "Иванов",
                    "tg_chat_id": 123456789,
                },
                response_only=True,
            )
        ],
    ),
    put=extend_schema(
        tags=["users"],
        summary="Обновить профиль целиком",
        description="Email изменить нельзя — это логин.",
        responses={200: UserProfileSerializer, 400: VALIDATION_ERROR, 401: UNAUTHORIZED},
    ),
    patch=extend_schema(
        tags=["users"],
        summary="Частично обновить профиль",
        description="Например, указать `tg_chat_id` для получения напоминаний в Telegram.",
        responses={200: UserProfileSerializer, 400: VALIDATION_ERROR, 401: UNAUTHORIZED},
        examples=[OpenApiExample("Запрос", value={"tg_chat_id": 123456789}, request_only=True)],
    ),
)
class MeView(generics.RetrieveUpdateAPIView):
    """Просмотр и редактирование собственного профиля (GET/PATCH/PUT)."""

    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user
