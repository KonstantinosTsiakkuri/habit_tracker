# Образ Django-приложения. Один и тот же образ запускается как app (gunicorn),
# celery_worker и celery_beat — различается только команда (см. docker-compose.yaml).
FROM python:3.13-slim

# PYTHONDONTWRITEBYTECODE — не создавать .pyc; PYTHONUNBUFFERED — логи сразу в stdout (docker logs)
# POETRY_VIRTUALENVS_CREATE=false — ставим пакеты в системный Python образа: контейнер сам является изоляцией
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN pip install "poetry==2.4.3"

# Сначала только файлы зависимостей: слой с установкой пакетов пересобирается лишь при их изменении,
# а правки кода (ниже) не заставляют скачивать зависимости заново
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY . .

# Приложение запускается не от root. Каталог для статики создаём заранее с владельцем app:
# именованный volume при первом монтировании наследует эти права
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app \
    && mkdir -p /app/staticfiles \
    && chown -R app:app /app/staticfiles
USER app

EXPOSE 8000

# Число воркеров задаётся переменной GUNICORN_WORKERS (на слабой ВМ достаточно 2)
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-2} --timeout 60 --access-logfile -"]
