"""Тесты CORS и документации API (Swagger / ReDoc / OpenAPI-схема)."""
import pytest
from django.core.management import call_command

ALLOWED = "http://allowed.example"
FOREIGN = "http://evil.example"


@pytest.fixture(autouse=True)
def cors_settings(settings):
    settings.CORS_ALLOWED_ORIGINS = [ALLOWED]


class TestCors:
    def test_header_present_for_allowed_origin(self, api_client):
        response = api_client.get("/api/schema/", HTTP_ORIGIN=ALLOWED)
        assert response["Access-Control-Allow-Origin"] == ALLOWED

    def test_header_absent_for_foreign_origin(self, api_client):
        response = api_client.get("/api/schema/", HTTP_ORIGIN=FOREIGN)
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response

    def test_no_header_without_origin(self, api_client):
        assert "Access-Control-Allow-Origin" not in api_client.get("/api/schema/")

    def test_preflight_allowed_origin(self, api_client):
        response = api_client.options(
            "/habits/",
            HTTP_ORIGIN=ALLOWED,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
        )
        assert response.status_code == 200
        assert response["Access-Control-Allow-Origin"] == ALLOWED
        assert "POST" in response["Access-Control-Allow-Methods"]
        assert "authorization" in response["Access-Control-Allow-Headers"].lower()

    def test_preflight_foreign_origin(self, api_client):
        response = api_client.options(
            "/habits/",
            HTTP_ORIGIN=FOREIGN,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        assert "Access-Control-Allow-Origin" not in response

    def test_header_on_api_endpoint_for_allowed_origin(self, api_client):
        """CORS-заголовок добавляется и к ответам API (в том числе 401)."""
        response = api_client.get("/habits/", HTTP_ORIGIN=ALLOWED)
        assert response.status_code == 401
        assert response["Access-Control-Allow-Origin"] == ALLOWED


class TestCorsConfiguration:
    def test_cors_middleware_is_first(self, settings):
        assert settings.MIDDLEWARE[0] == "corsheaders.middleware.CorsMiddleware"

    def test_allow_all_origins_is_not_enabled(self, settings):
        assert getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False) is False

    def test_env_list_helper(self, monkeypatch):
        from config.settings import env_list

        monkeypatch.setenv("TEST_LIST", " http://a.com , ,http://b.com ")
        assert env_list("TEST_LIST") == ["http://a.com", "http://b.com"]
        assert env_list("TEST_MISSING_LIST") == []
        assert env_list("TEST_MISSING_LIST", "x,y") == ["x", "y"]

    def test_origins_come_from_env(self, settings):
        assert isinstance(settings.CSRF_TRUSTED_ORIGINS, list)


class TestDocsPages:
    def test_schema_is_available_without_token(self, api_client):
        response = api_client.get("/api/schema/")
        assert response.status_code == 200

    def test_swagger_ui(self, api_client):
        response = api_client.get("/api/docs/")
        assert response.status_code == 200
        assert b"swagger" in response.content.lower()

    def test_redoc(self, api_client):
        response = api_client.get("/api/redoc/")
        assert response.status_code == 200
        assert b"redoc" in response.content.lower()


class TestSchemaContent:
    @pytest.fixture
    def schema(self, api_client):
        return api_client.get("/api/schema/", {"format": "json"}).json()

    def test_all_endpoints_documented(self, schema):
        expected = {
            "/users/register/": {"post"},
            "/users/login/": {"post"},
            "/users/token/refresh/": {"post"},
            "/users/me/": {"get", "put", "patch"},
            "/habits/": {"get", "post"},
            "/habits/{id}/": {"get", "put", "patch", "delete"},
            "/habits/public/": {"get"},
        }
        assert set(schema["paths"]) == set(expected)
        for path, methods in expected.items():
            assert set(schema["paths"][path]) == methods, path

    def test_every_operation_has_tag_summary_and_responses(self, schema):
        for path, methods in schema["paths"].items():
            for method, operation in methods.items():
                assert operation["tags"] in (["users"], ["habits"]), (path, method)
                assert operation["summary"], (path, method)
                assert any(code.startswith("2") for code in operation["responses"]), (path, method)

    def test_jwt_security_scheme_for_swagger_authorize(self, schema):
        scheme = schema["components"]["securitySchemes"]["jwtAuth"]
        assert scheme["type"] == "http" and scheme["scheme"] == "bearer"
        assert {"jwtAuth": []} in schema["paths"]["/habits/"]["get"]["security"]

    def test_list_endpoints_describe_pagination(self, schema):
        for path in ("/habits/", "/habits/public/"):
            names = {p["name"] for p in schema["paths"][path]["get"]["parameters"]}
            assert {"limit", "offset"} <= names
        response_schema = schema["components"]["schemas"]["PaginatedHabitList"]["properties"]
        assert {"count", "next", "previous", "results"} <= set(response_schema)

    def test_examples_are_present(self, schema):
        register = schema["paths"]["/users/register/"]["post"]
        assert "example" in str(register["requestBody"]) or "examples" in str(register["requestBody"])

    def test_title_and_description(self, schema):
        assert schema["info"]["title"] == "Трекер полезных привычек API"
        assert "Authorize" in schema["info"]["description"]

    def test_schema_generates_without_warnings(self, tmp_path):
        call_command("spectacular", validate=True, fail_on_warn=True, file=str(tmp_path / "schema.yml"))
