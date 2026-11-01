"""Конфигурация Celery: брокер и расписание берутся из настроек Django (префикс CELERY_)."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
# Ищет tasks.py во всех приложениях из INSTALLED_APPS
app.autodiscover_tasks()
