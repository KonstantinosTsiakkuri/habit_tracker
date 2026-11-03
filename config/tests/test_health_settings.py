"""Тесты служебного эндпоинта /health/ и настроек для работы в контейнере."""
from unittest import mock

import pytest
from django.db.utils import OperationalError


@pytest.mark.django_db
class TestHealth:
    def test_ok_without_token(self, api_client):
        response = api_client.get("/health/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_database_down_returns_503(self, api_client):
        with mock.patch("config.views.connection.ensure_connection", side_effect=OperationalError("down")):
            response = api_client.get("/health/")
        assert response.status_code == 503
        assert response.json()["status"] == "error"

    def test_not_in_api_schema(self, api_client):
        schema = api_client.get("/api/schema/", {"format": "json"}).json()
        assert "/health/" not in schema["paths"]


class TestContainerSettings:
    def test_static_root_is_set_for_collectstatic(self, settings):
        assert str(settings.STATIC_ROOT).endswith("staticfiles")

    def test_swagger_assets_come_from_sidecar_not_cdn(self, settings):
        assert settings.SPECTACULAR_SETTINGS["SWAGGER_UI_DIST"] == "SIDECAR"
        assert settings.SPECTACULAR_SETTINGS["REDOC_DIST"] == "SIDECAR"
        assert "drf_spectacular_sidecar" in settings.INSTALLED_APPS

    def test_proxy_ssl_header(self, settings):
        assert settings.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")

    def test_logging_goes_to_console(self, settings):
        assert settings.LOGGING["root"]["handlers"] == ["console"]

    @pytest.mark.django_db
    def test_next_link_uses_forwarded_proto(self, auth_client, user):
        from habits.models import Habit
        import datetime

        Habit.objects.bulk_create(
            [Habit(owner=user, place="p", time=datetime.time(8, 0), action="a", duration=10) for _ in range(6)]
        )
        response = auth_client.get("/habits/", HTTP_X_FORWARDED_PROTO="https")
        assert response.data["next"].startswith("https://")
