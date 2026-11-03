"""Служебные представления."""
from django.db import connection
from django.http import JsonResponse


def health(request):
    """
    Проверка работоспособности: приложение запущено и база данных отвечает.

    Используется healthcheck-ом Docker и smoke-тестом после деплоя; в документацию API не входит.
    """
    try:
        connection.ensure_connection()
    except Exception:
        return JsonResponse({"status": "error", "detail": "database unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
