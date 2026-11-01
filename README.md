# Трекер полезных привычек (backend)

Бэкенд SPA-приложения для формирования полезных привычек по методике книги Джеймса Клира
«Атомные привычки». Привычка описывается формулой «я буду **[действие]** в **[время]** в **[место]**».
Полезная привычка поощряется либо приятной привычкой (поле «связанная привычка»), либо произвольным
вознаграждением. Пользователю приходят напоминания в Telegram по расписанию.

## Стек

- Python 3.13, Django 6.0, Django REST Framework
- JWT-авторизация (djangorestframework-simplejwt)
- PostgreSQL
- Celery + Redis + django-celery-beat (напоминания)
- django-cors-headers, drf-spectacular (Swagger / ReDoc)
- Poetry, pytest, flake8

## Установка

```bash
# 1. Зависимости
poetry install

# 2. Переменные окружения
cp .env.template .env      # Windows PowerShell: Copy-Item .env.template .env
# отредактируйте .env: SECRET_KEY, пароль БД, токен бота и т.д.

# 3. База данных (PostgreSQL должен быть запущен)
psql -U postgres -c "CREATE DATABASE habit_tracker;"
```

## Запуск

```bash
poetry run python manage.py migrate
poetry run python manage.py runserver
```

Сервер: http://127.0.0.1:8000/

## Celery и Telegram-бот

Будет описано в Блоке 5 (запуск Redis, worker и beat, получение `chat_id`).

## Документация API

Будет добавлена в Блоке 6 (`/api/docs/`, `/api/redoc/`).

## Тесты и линтер

```bash
poetry run pytest
poetry run flake8 .
```
