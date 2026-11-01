# Трекер полезных привычек (backend)

Бэкенд SPA-приложения для формирования полезных привычек по методике книги Джеймса Клира
«Атомные привычки». Привычка описывается формулой «я буду **[действие]** в **[время]** в **[место]**».
Полезная привычка поощряется либо приятной привычкой (поле «связанная привычка»), либо произвольным
вознаграждением. Пользователю приходят напоминания в Telegram по расписанию.

## Содержание

- [Стек](#стек)
- [Структура проекта](#структура-проекта)
- [Установка](#установка)
- [Переменные окружения (.env)](#переменные-окружения-env)
- [Миграции и запуск сервера](#миграции-и-запуск-сервера)
- [Эндпоинты](#эндпоинты)
- [Правила для привычек](#правила-для-привычек)
- [Redis, Celery и Telegram-бот](#redis-celery-и-telegram-бот)
- [Документация API](#документация-api)
- [CORS](#cors)
- [Тесты и линтер](#тесты-и-линтер)

## Стек

- Python 3.13, Django 6.0, Django REST Framework
- JWT-авторизация (djangorestframework-simplejwt)
- PostgreSQL
- Celery + Redis + django-celery-beat (напоминания)
- django-cors-headers, drf-spectacular (Swagger / ReDoc)
- Poetry, pytest (+ pytest-django, pytest-cov), flake8

## Структура проекта

```
config/    настройки Django, Celery, корневые URL
users/     кастомный пользователь (вход по email), регистрация, JWT, профиль
habits/    модель привычки, валидаторы, API, Telegram-сервис, Celery-задача
conftest.py  общие фикстуры pytest
```

## Установка

Нужны Python 3.13+, [Poetry](https://python-poetry.org/), PostgreSQL и (для напоминаний) Redis.

```bash
# 1. Зависимости
poetry install

# 2. Переменные окружения
cp .env.template .env      # Windows PowerShell: Copy-Item .env.template .env
# отредактируйте .env (см. ниже)

# 3. База данных (PostgreSQL должен быть запущен)
psql -U postgres -c "CREATE DATABASE habit_tracker;"
```

Если нужен `requirements.txt` вместо Poetry: `pip install -r requirements.txt` (только основные зависимости).

## Переменные окружения (.env)

Все настройки и секреты читаются из `.env` (в git не попадает). Шаблон со всеми ключами — `.env.template`.

| Переменная | Назначение |
|---|---|
| `SECRET_KEY` | секретный ключ Django |
| `DEBUG` | `True` только для разработки |
| `ALLOWED_HOSTS` | разрешённые хосты через запятую |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | подключение к PostgreSQL |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Redis для Celery |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_URL` | токен бота (от @BotFather) и адрес Bot API |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | домены фронтенда через запятую |

Сгенерировать `SECRET_KEY`:
`python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`

## Миграции и запуск сервера

```bash
poetry run python manage.py migrate
poetry run python manage.py createsuperuser   # по желанию, для админки (/admin/)
poetry run python manage.py runserver
```

Сервер: http://127.0.0.1:8000/

## Эндпоинты

| Метод и путь | Описание | Доступ |
|---|---|---|
| `POST /users/register/` | регистрация | все |
| `POST /users/login/` | пара JWT-токенов | все |
| `POST /users/token/refresh/` | обновление access-токена | все |
| `GET/PATCH /users/me/` | свой профиль (в т.ч. `tg_chat_id`) | авторизованные |
| `GET/POST /habits/` | свои привычки (пагинация `limit`/`offset`) / создание | авторизованные |
| `GET/PUT/PATCH/DELETE /habits/<id>/` | своя привычка (чужая — 404) | владелец |
| `GET /habits/public/` | публичные привычки (только чтение, пагинация) | авторизованные |

Токен передаётся в заголовке `Authorization: Bearer <access>`. Списки возвращают
`{"count", "next", "previous", "results"}`, по умолчанию 5 записей на страницу (`?limit=` до 50, `?offset=`).

## Правила для привычек

- нельзя одновременно указывать вознаграждение и связанную привычку;
- связанная привычка — только приятная, только своя и не сама на себя;
- у приятной привычки нет вознаграждения и связанной привычки;
- время выполнения — не больше 120 секунд;
- периодичность — от 1 до 7 дней.

Правила проверяются и при создании, и при частичном обновлении (PATCH), а также в админке.

## Redis, Celery и Telegram-бот

Напоминания рассылает периодическая задача `habits.tasks.send_habit_reminders`.
Она запускается **каждую минуту**, выбирает полезные привычки, время которых совпадает с текущей минутой
(по часовому поясу `Europe/Moscow`), у владельцев которых указан `tg_chat_id`, и отправляет сообщение
через Telegram Bot API. Напоминание повторяется не чаще, чем раз в `periodicity` дней.

### 1. Создайте бота и получите токен
1. В Telegram откройте [@BotFather](https://t.me/BotFather) → `/newbot` → задайте имя.
2. Скопируйте выданный токен в `.env`: `TELEGRAM_BOT_TOKEN=<токен>`.

### 2. Узнайте свой chat_id
1. Найдите своего бота в Telegram и отправьте ему `/start` (бот не может писать первым).
2. Откройте в браузере `https://api.telegram.org/bot<ТОКЕН>/getUpdates`.
3. В ответе найдите `"chat":{"id": 123456789, ...}` — это ваш `chat_id`.
   (Альтернатива: написать боту [@userinfobot](https://t.me/userinfobot).)
4. Сохраните его в профиле:
   ```bash
   curl -X PATCH http://127.0.0.1:8000/users/me/ \
        -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
        -d '{"tg_chat_id": 123456789}'
   ```

### 3. Redis (брокер Celery)
Celery требует запущенный Redis (`CELERY_BROKER_URL` в `.env`, по умолчанию `redis://localhost:6379/0`).
Варианты для Windows:
- **Docker:** `docker run -d --name redis -p 6379:6379 redis`
- **WSL:** `sudo apt install redis-server && sudo service redis-server start`
- **Memurai** (Redis-совместимый сервер для Windows): https://www.memurai.com/

Проверка: `redis-cli ping` → `PONG`.

### 4. Worker и beat (в двух отдельных терминалах)
```bash
# Терминал 1 — исполнитель задач. На Windows обязателен --pool=solo
poetry run celery -A config worker -l info --pool=solo

# Терминал 2 — планировщик (раз в минуту ставит задачу в очередь)
poetry run celery -A config beat -l info
```
Ключ `-B` (встроенный beat) на Windows не работает, поэтому beat запускается отдельно.
Перед первым запуском beat должны быть применены миграции (`django_celery_beat` хранит расписание в БД).

### 5. Проверка
Создайте полезную привычку на ближайшую минуту (например, `"time": "14:06"`), и в это время бот пришлёт:
```
Я буду выпить воды в 14:06 в дом
Награда: шоколадка
Время на выполнение: 30 сек.
```

## Документация API

Интерактивная документация (drf-spectacular), доступна после `runserver`:

- Swagger UI: http://127.0.0.1:8000/api/docs/ — кнопка **Authorize**: вставьте `access`-токен из `POST /users/login/`
- ReDoc: http://127.0.0.1:8000/api/redoc/
- Схема OpenAPI: http://127.0.0.1:8000/api/schema/

Проверка схемы: `poetry run python manage.py spectacular --validate --fail-on-warn`

## CORS

Запросы браузера разрешены только с доменов из `CORS_ALLOWED_ORIGINS` (`.env`), `CORS_ALLOW_ALL_ORIGINS` не используется.
Домены фронтенда указываются через запятую, со схемой и без `/` в конце. Для POST-запросов с cookie
(например, админка за прокси) домен нужно добавить и в `CSRF_TRUSTED_ORIGINS`.

## Тесты и линтер

Тестам нужен PostgreSQL (создаётся отдельная БД `test_<DB_NAME>`, у пользователя должно быть право `CREATEDB`).
Redis и реальный Telegram не нужны: сетевые вызовы замоканы.

```bash
poetry run pytest                                                  # тесты + отчёт о покрытии в консоли
poetry run pytest --cov --cov-report=term-missing --cov-report=html  # + HTML-отчёт в htmlcov/
poetry run flake8 .                                                # PEP 8 (max-line-length = 119)
```

Текущее покрытие: **100 %** (154 теста, включая замер ветвлений). Из замера исключены миграции,
`manage.py`, `wsgi.py`/`asgi.py` и сами тесты.
