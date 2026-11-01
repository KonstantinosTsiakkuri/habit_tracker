"""Сериализаторы пользователей."""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from users.models import User


class UserRegisterSerializer(serializers.ModelSerializer):
    """Регистрация: email + пароль (пароль только на запись)."""

    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("id", "email", "password", "first_name", "last_name", "tg_chat_id")

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        # create_user хеширует пароль, обычный create() сохранил бы его открытым текстом
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    """Профиль текущего пользователя. Email менять нельзя (это логин)."""

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "tg_chat_id")
        read_only_fields = ("id", "email")


class TokenPairSerializer(serializers.Serializer):
    """Описание ответа входа (только для документации)."""

    access = serializers.CharField(help_text="Короткоживущий токен для заголовка Authorization")
    refresh = serializers.CharField(help_text="Долгоживущий токен для получения нового access")


class TokenAccessSerializer(serializers.Serializer):
    """Описание ответа обновления токена (только для документации)."""

    access = serializers.CharField(help_text="Новый access-токен")
