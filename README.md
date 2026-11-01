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
poetry run python manage.py createsuperuser   # по желанию, для админки
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
| `GET/PUT/PATCH/DELETE /habits/<id>/` | своя привычка | владелец |
| `GET /habits/public/` | публичные привычки (только чтение) | авторизованные |

Токен передаётся в заголовке `Authorization: Bearer <access>`.

## Celery и Telegram-бот

Напоминания рассылает периодическая задача `habits.tasks.send_habit_reminders`.
Она запускается **каждую минуту**, выбирает полезные привычки, время которых совпадает с текущей минутой
(по часовому поясу `Europe/Moscow`), у владельцев которых указан `tg_chat_id`, и отправляет сообщение
с помощью Telegram Bot API. Напоминание повторяется не чаще, чем раз в `periodicity` дней.

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

```bash
poetry run pytest          # тесты + покрытие (Telegram замокан, Redis не нужен)
poetry run flake8 .
```
