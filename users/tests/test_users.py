"""Тесты регистрации, JWT-авторизации и профиля."""
import pytest
from django.urls import reverse

from users.models import User

pytestmark = pytest.mark.django_db


class TestUserModel:
    def test_create_user_hashes_password(self):
        user = User.objects.create_user(email="a@example.com", password="StrongPass123!")
        assert user.password != "StrongPass123!"
        assert user.check_password("StrongPass123!")
        assert str(user) == "a@example.com"

    def test_create_user_without_email_fails(self):
        with pytest.raises(ValueError):
            User.objects.create_user(email="", password="x")

    def test_create_superuser(self):
        admin = User.objects.create_superuser(email="root@example.com", password="StrongPass123!")
        assert admin.is_staff and admin.is_superuser

    def test_create_superuser_requires_flags(self):
        with pytest.raises(ValueError):
            User.objects.create_superuser(email="r@example.com", password="x", is_staff=False)
        with pytest.raises(ValueError):
            User.objects.create_superuser(email="r@example.com", password="x", is_superuser=False)


class TestRegister:
    url = "/users/register/"

    def test_register_success(self, api_client):
        response = api_client.post(self.url, {"email": "new@example.com", "password": "StrongPass123!"})
        assert response.status_code == 201
        assert response.data["email"] == "new@example.com"
        assert "password" not in response.data
        user = User.objects.get(email="new@example.com")
        assert user.check_password("StrongPass123!")  # пароль хеширован

    def test_register_duplicate_email(self, api_client, user):
        response = api_client.post(self.url, {"email": user.email, "password": "StrongPass123!"})
        assert response.status_code == 400
        assert "email" in response.data

    def test_register_weak_password(self, api_client):
        response = api_client.post(self.url, {"email": "weak@example.com", "password": "123"})
        assert response.status_code == 400
        assert "password" in response.data

    def test_register_with_tg_chat_id(self, api_client):
        response = api_client.post(
            self.url, {"email": "tg@example.com", "password": "StrongPass123!", "tg_chat_id": 123456}
        )
        assert response.status_code == 201
        assert User.objects.get(email="tg@example.com").tg_chat_id == 123456


class TestLoginAndRefresh:
    def test_login_returns_token_pair(self, api_client, user):
        response = api_client.post("/users/login/", {"email": user.email, "password": "StrongPass123!"})
        assert response.status_code == 200
        assert "access" in response.data and "refresh" in response.data

    def test_login_wrong_password(self, api_client, user):
        response = api_client.post("/users/login/", {"email": user.email, "password": "wrong"})
        assert response.status_code == 401

    def test_refresh_returns_new_access(self, api_client, user):
        tokens = api_client.post("/users/login/", {"email": user.email, "password": "StrongPass123!"}).data
        response = api_client.post("/users/token/refresh/", {"refresh": tokens["refresh"]})
        assert response.status_code == 200
        assert "access" in response.data

    def test_refresh_invalid_token(self, api_client):
        response = api_client.post("/users/token/refresh/", {"refresh": "garbage"})
        assert response.status_code == 401


class TestMe:
    url = "/users/me/"

    def test_me_requires_auth(self, api_client):
        assert api_client.get(self.url).status_code == 401

    def test_me_with_jwt_token(self, api_client, user):
        tokens = api_client.post("/users/login/", {"email": user.email, "password": "StrongPass123!"}).data
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        response = api_client.get(self.url)
        assert response.status_code == 200
        assert response.data["email"] == user.email

    def test_me_with_invalid_token(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer invalid")
        assert api_client.get(self.url).status_code == 401

    def test_patch_tg_chat_id(self, auth_client, user):
        response = auth_client.patch(self.url, {"tg_chat_id": 555}, format="json")
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.tg_chat_id == 555

    def test_email_is_read_only(self, auth_client, user):
        response = auth_client.patch(self.url, {"email": "hacked@example.com"}, format="json")
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.email == "user@example.com"


class TestAdmin:
    def test_admin_user_list(self, client):
        User.objects.create_superuser(email="root@example.com", password="StrongPass123!")
        client.login(email="root@example.com", password="StrongPass123!")
        assert client.get(reverse("admin:users_user_changelist")).status_code == 200
        assert client.get(reverse("admin:users_user_add")).status_code == 200
