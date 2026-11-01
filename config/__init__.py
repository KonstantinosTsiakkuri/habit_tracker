# Приложение Celery загружается вместе с Django, чтобы работал @shared_task
from .celery import app as celery_app

__all__ = ("celery_app",)
