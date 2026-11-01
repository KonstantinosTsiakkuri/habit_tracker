"""Общие фикстуры pytest."""
import pytest
from rest_framework.test import APIClient

from users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="user@example.com", password="StrongPass123!")


@pytest.fixture
def auth_client(user):
    """Клиент, авторизованный как обычный пользователь."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email="other@example.com", password="StrongPass123!")
