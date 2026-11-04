# Трекер полезных привычек (backend)

Бэкенд SPA-приложения для формирования полезных привычек по методике книги Джеймса Клира
«Атомные привычки». Привычка описывается формулой «я буду **[действие]** в **[время]** в **[место]**».
Полезная привычка поощряется либо приятной привычкой (поле «связанная привычка»), либо произвольным
вознаграждением. Пользователю приходят напоминания в Telegram по расписанию.

Проект запускается одной командой в Docker (Django, PostgreSQL, Redis, Celery worker и beat, Nginx),
проверяется в GitHub Actions и автоматически выкладывается на сервер.

**Развёрнутое приложение:** http://84.54.57.75/ · документация API: http://84.54.57.75/api/docs/

## Содержание

- [Стек](#стек)
- [Структура проекта](#структура-проекта)
- [Переменные окружения (.env)](#переменные-окружения-env)
- [Быстрый запуск в Docker](#быстрый-запуск-в-docker)
- [Сервисы Docker Compose](#сервисы-docker-compose)
- [Запуск без Docker](#запуск-без-docker)
- [Эндпоинты](#эндпоинты)
- [Правила для привычек](#правила-для-привычек)
- [Telegram-бот и напоминания](#telegram-бот-и-напоминания)
- [Документация API](#документация-api)
- [CORS](#cors)
- [Тесты и линтер](#тесты-и-линтер)
- [CI/CD: GitHub Actions](#cicd-github-actions)
- [Настройка сервера и деплоя](#настройка-сервера-и-деплоя)
- [Частые проблемы](#частые-проблемы)

## Стек

- Python 3.13, Django 6.0, Django REST Framework, gunicorn
- JWT-авторизация (djangorestframework-simplejwt)
- PostgreSQL 17, Redis 7
- Celery + django-celery-beat (напоминания)
- django-cors-headers, drf-spectacular (Swagger / ReDoc)
- Docker, Docker Compose, Nginx
- GitHub Actions, GitHub Container Registry (GHCR)
- Poetry, pytest (+ pytest-django, pytest-cov), flake8

## Структура проекта

```
config/                настройки Django, Celery, корневые URL, /health/
users/                 кастомный пользователь (вход по email), регистрация, JWT, профиль
habits/                модель привычки, валидаторы, API, Telegram-сервис, Celery-задача
docker/entrypoint.sh   миграции и collectstatic перед запуском приложения
nginx/nginx.conf       конфиг Nginx (reverse proxy и статика)
Dockerfile             образ приложения
docker-compose.yaml    все сервисы проекта
.github/workflows/     CI/CD (ci_cd.yaml)
```

## Переменные окружения (.env)

Все настройки и секреты читаются из `.env` (в git не попадает). Шаблон со всеми ключами — `.env.template`.

| Переменная | Назначение |
|---|---|
| `SECRET_KEY` | секретный ключ Django |
| `DEBUG` | `True` только для разработки |
| `ALLOWED_HOSTS` | разрешённые хосты через запятую (на сервере обязательно с IP/доменом сервера) |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | подключение к PostgreSQL |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Redis для Celery |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_URL` | токен бота (от @BotFather) и адрес Bot API |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | домены фронтенда через запятую |
| `GUNICORN_WORKERS`, `CELERY_CONCURRENCY`, `LOG_LEVEL` | необязательные: число воркеров gunicorn и Celery, уровень логов |

Хосты `db` и `redis` внутри Docker подставляет `docker-compose.yaml`, поэтому один и тот же `.env`
(с `localhost`) подходит и для запуска без Docker, и для Docker.

Сгенерировать `SECRET_KEY`:
`python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`

Значения со знаком `$` (например, `SECRET_KEY`) берите в одинарные кавычки: иначе Docker Compose воспримет `$` как подстановку.

## Быстрый запуск в Docker

Нужны Docker Desktop (Windows + WSL2) или Docker Engine с Compose v2. Команды для PowerShell:

```powershell
git clone https://github.com/KonstantinosTsiakkuri/habit_tracker.git
cd habit_tracker
Copy-Item .env.template .env      # затем отредактируйте .env: SECRET_KEY, DB_PASSWORD, токен бота
docker compose up -d --build
docker compose ps                 # все сервисы Up, db/redis/app/nginx — healthy
```

Первый запуск занимает несколько минут (сборка образа, миграции). Что открыть:

- http://localhost/api/docs/ — Swagger UI
- http://localhost/admin/ — админка (создайте суперпользователя ниже)
- http://localhost/health/ — проверка работоспособности (`{"status": "ok"}`)

Полезные команды:

```powershell
docker compose logs -f app                 # логи (app, celery_worker, celery_beat, nginx, db, redis)
docker compose exec app python manage.py createsuperuser
docker compose down                        # остановить (данные БД сохраняются в volume)
docker compose down -v                     # остановить и УДАЛИТЬ данные (локально)
```

Если порт 80 занят другим приложением, остановите его или измените `ports` у сервиса `nginx`.

## Сервисы Docker Compose

| Сервис | Образ | Назначение |
|---|---|---|
| `db` | postgres:17-alpine | база данных, данные в volume `pg_data`, healthcheck `pg_isready` |
| `redis` | redis:7-alpine | брокер Celery, volume `redis_data`, healthcheck `redis-cli ping` |
| `app` | образ проекта | Django за gunicorn; при старте применяет миграции и собирает статику; healthcheck `/health/` |
| `celery_worker` | образ проекта | выполняет задачи Celery (отправка напоминаний) |
| `celery_beat` | образ проекта | раз в минуту ставит задачу напоминаний; стартует после healthy `app` |
| `nginx` | nginx:alpine | единственный сервис, открытый наружу (порт 80): проксирует на `app`, раздаёт `/static/` |

Порты `db`, `redis` и `app` наружу не публикуются: они доступны только внутри сети compose.
Образ проекта один, у `app`, `celery_worker` и `celery_beat` отличаются только команды.
Образ задаётся переменной `APP_IMAGE`: локально это `habit_tracker:local` (собирается из исходников),
на сервере — образ из GHCR с тегом коммита.

## Запуск без Docker

Нужны Python 3.13+, [Poetry](https://python-poetry.org/), PostgreSQL и (для напоминаний) Redis.

```bash
poetry install
cp .env.template .env      # PowerShell: Copy-Item .env.template .env; DB_HOST=localhost
psql -U postgres -c "CREATE DATABASE habit_tracker;"
poetry run python manage.py migrate
poetry run python manage.py createsuperuser   # по желанию
poetry run python manage.py runserver         # http://127.0.0.1:8000/
```

Celery и Redis (Windows: Docker, WSL или [Memurai](https://www.memurai.com/); проверка `redis-cli ping` → `PONG`):

```bash
# Терминал 1 — исполнитель задач. На Windows обязателен --pool=solo
poetry run celery -A config worker -l info --pool=solo
# Терминал 2 — планировщик (на Windows встроенный ключ -B не работает)
poetry run celery -A config beat -l info
```

В Docker `--pool=solo` не нужен: контейнеры работают на Linux, где есть пул `prefork`.

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
| `GET /health/` | проверка работоспособности (приложение и БД) | все |

Токен передаётся в заголовке `Authorization: Bearer <access>`. Списки возвращают
`{"count", "next", "previous", "results"}`, по умолчанию 5 записей на страницу (`?limit=` до 50, `?offset=`).

## Правила для привычек

- нельзя одновременно указывать вознаграждение и связанную привычку;
- связанная привычка — только приятная, только своя и не сама на себя;
- у приятной привычки нет вознаграждения и связанной привычки;
- время выполнения — не больше 120 секунд;
- периодичность — от 1 до 7 дней.

Правила проверяются и при создании, и при частичном обновлении (PATCH), а также в админке.

## Telegram-бот и напоминания

Напоминания рассылает периодическая задача `habits.tasks.send_habit_reminders`.
Она запускается **каждую минуту**, выбирает полезные привычки, время которых совпадает с текущей минутой
(по часовому поясу `Europe/Moscow`), у владельцев которых указан `tg_chat_id`, и отправляет сообщение
через Telegram Bot API. Напоминание повторяется не чаще, чем раз в `periodicity` дней.

1. **Токен бота.** В Telegram откройте [@BotFather](https://t.me/BotFather) → `/newbot`, токен запишите в `.env`
   (`TELEGRAM_BOT_TOKEN`). На сервере — в секрет `ENV_FILE`.
2. **chat_id.** Отправьте своему боту `/start` (бот не может писать первым), откройте
   `https://api.telegram.org/bot<ТОКЕН>/getUpdates` и найдите `"chat":{"id": 123456789, ...}`
   (или напишите боту [@userinfobot](https://t.me/userinfobot)).
3. **Привязка к профилю:**
   ```powershell
   Invoke-RestMethod -Method Patch -Uri "http://localhost/users/me/" `
     -Headers @{ Authorization = "Bearer <access>" } -ContentType "application/json" `
     -Body '{"tg_chat_id": 123456789}'
   ```
4. **Проверка.** Создайте полезную привычку на ближайшую минуту (например, `"time": "14:06"`): в это время бот пришлёт

   ```
   Я буду выпить воды в 14:06 в дом
   Награда: шоколадка
   Время на выполнение: 30 сек.
   ```

## Документация API

Интерактивная документация (drf-spectacular):

- Swagger UI: `/api/docs/` — кнопка **Authorize**: вставьте `access`-токен из `POST /users/login/`
- ReDoc: `/api/redoc/`
- Схема OpenAPI: `/api/schema/`

Стили и скрипты Swagger и ReDoc лежат в пакете `drf-spectacular-sidecar` и отдаются как статика (через Nginx),
поэтому документация работает без доступа к CDN. Проверка схемы:
`poetry run python manage.py spectacular --validate --fail-on-warn`

## CORS

Запросы браузера разрешены только с доменов из `CORS_ALLOWED_ORIGINS` (`.env`), `CORS_ALLOW_ALL_ORIGINS` не используется.
Домены фронтенда указываются через запятую, со схемой и без `/` в конце.

## Тесты и линтер

Тестам нужен PostgreSQL (создаётся отдельная БД `test_<DB_NAME>`, у пользователя должно быть право `CREATEDB`).
Redis и реальный Telegram не нужны: сетевые вызовы замоканы. Порог покрытия 80 % (`fail_under` в `pyproject.toml`).

```bash
poetry run pytest                                                   # тесты + покрытие в консоли
poetry run pytest --cov --cov-report=term-missing --cov-report=html   # + HTML-отчёт в htmlcov/
poetry run flake8 .                                                 # PEP 8 (max-line-length = 119)
```

Текущее покрытие: **100 %** (162 теста, с замером ветвлений). Из замера исключены миграции,
`manage.py`, `wsgi.py`/`asgi.py` и сами тесты.

## CI/CD: GitHub Actions

Workflow: `.github/workflows/ci_cd.yaml`. Запускается при push в `develop` и `feature/docker_ci_cd`
и при pull request в `develop`.

```
lint ──┐
       ├──► build ──► deploy
test ──┘
```

| Job | Что делает | Когда |
|---|---|---|
| `lint` | ставит зависимости (кэш Poetry), запускает `flake8` | всегда |
| `test` | поднимает PostgreSQL как service-контейнер, запускает `pytest` с покрытием; ниже 80 % — ошибка | всегда |
| `build` | собирает Docker-образ (Buildx, кэш слоёв); на push публикует в `ghcr.io/konstantinostsiakkuri/habit_tracker` с тегами `latest` и sha коммита | после `lint` и `test`; на pull request только сборка без публикации |
| `deploy` | выкладывает приложение на сервер по SSH (см. ниже) и проверяет его smoke-тестом | после `build`, только на push |

Деплой по шагам: подготовка SSH-ключа → копирование `docker-compose.yaml` и `nginx/nginx.conf` в `~/habit_tracker` →
запись `.env` из секрета `ENV_FILE` (права 600) → вход в GHCR токеном job → `docker compose pull` и
`docker compose up -d` с образом текущего коммита (`APP_IMAGE`) → `docker image prune -f` → smoke-тест
(`/health/`, `/api/docs/`, `/api/schema/`, статика админки должны ответить 200, до ~7 минут ожидания).
Два деплоя одновременно не идут (группа `concurrency`). Если проверка не прошла, job падает и печатает
`docker compose ps` и логи сервисов. Первый деплой на слабой ВМ занимает около 5 минут (скачивание образов).

## Настройка сервера и деплоя

Инструкция подходит для любой Ubuntu-ВМ с публичным IP.

### 1. Требования к серверу
- Ubuntu 22.04 или 24.04, публичный IP;
- Docker Engine и плагин Docker Compose v2 ([инструкция](https://docs.docker.com/engine/install/ubuntu/));
- открытые входящие порты: **22** (SSH) и **80** (HTTP), при необходимости 443;
- свободный порт 80 (остановите другой веб-сервер или проект);
- ресурсы: достаточно 2 vCPU и 2–4 ГБ RAM (весь стек занимает около 0,5 ГБ).

### 2. Пользователь для деплоя
```bash
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG docker deploy      # доступ к Docker без sudo
sudo install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
```

### 3. SSH-ключ для деплоя
На своём компьютере создайте **отдельный ключ только для деплоя, без пароля** (в CI некому его вводить):

```powershell
ssh-keygen -t ed25519 -C "github-actions-deploy" -f $HOME\.ssh\habit_tracker_deploy -N '""'
```

Публичную часть (`habit_tracker_deploy.pub`) добавьте на сервер в `authorized_keys` пользователя `deploy`:

```bash
echo "ssh-ed25519 AAAA... github-actions-deploy" | sudo tee -a /home/deploy/.ssh/authorized_keys
sudo chown deploy:deploy /home/deploy/.ssh/authorized_keys
sudo chmod 600 /home/deploy/.ssh/authorized_keys
```

> **Внимание:** используйте `>>` или `tee -a` (дописать в конец). Одинарный `>` **перезапишет** файл и удалит
> все остальные ключи, включая ваш собственный, а вы потеряете доступ к серверу.

Приватную часть (`habit_tracker_deploy`, без `.pub`) целиком, включая строки `-----BEGIN ...` и `-----END ...`,
вставьте в секрет `SSH_KEY` (см. ниже). Проверка: `ssh -i $HOME\.ssh\habit_tracker_deploy deploy@<IP>`.

### 4. Секреты GitHub
Репозиторий → **Settings → Secrets and variables → Actions → New repository secret**:

| Секрет | Что содержит |
|---|---|
| `SSH_KEY` | приватный SSH-ключ для деплоя (файл целиком, с `BEGIN`/`END`) |
| `SSH_HOST` | публичный IP или домен сервера, например `84.54.57.75` |
| `SSH_USER` | пользователь деплоя, например `deploy` |
| `ENV_FILE` | полное содержимое продового `.env` (строки `КЛЮЧ=значение`) |

Пример структуры `ENV_FILE` (подставьте свои значения, реальные в репозиторий не попадают):

```
SECRET_KEY='<длинная случайная строка>'
DEBUG=False
ALLOWED_HOSTS=<IP-сервера>,localhost
DB_NAME=habit_tracker
DB_USER=<пользователь БД>
DB_PASSWORD=<пароль БД>
DB_HOST=db
DB_PORT=5432
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
TELEGRAM_BOT_TOKEN=<токен бота>
TELEGRAM_API_URL=https://api.telegram.org
CORS_ALLOWED_ORIGINS=http://<IP-сервера>
CSRF_TRUSTED_ORIGINS=http://<IP-сервера>
```

Важно: `ALLOWED_HOSTS` обязательно содержит IP или домен сервера (иначе Django отвечает 400), `DEBUG=False`.
Токен GHCR создавать не нужно: workflow использует временный `GITHUB_TOKEN`. Строку `APP_IMAGE` в `ENV_FILE` не пишите:
workflow дописывает её сам.

### 5. Права workflow и пакет
- **Settings → Actions → General → Workflow permissions**: разрешить запись (Read and write permissions), если сборка
  падает с `denied: permission_denied: write_package`.
- Пакет `habit_tracker` появляется в GHCR после первой сборки; он приватный, сервер входит в реестр токеном job.

### 6. Первый деплой и проверка
Сделайте push в `develop` (или `feature/docker_ci_cd`), на вкладке **Actions** дождитесь зелёных `lint`, `test`, `build`, `deploy`.
Затем:
- откройте `http://<IP>/api/docs/` и `http://<IP>/admin/` — со стилями;
- на сервере: `ssh deploy@<IP> "docker compose -p habit_tracker ps"` — все сервисы `Up`, `db`, `redis`, `app`, `nginx` — `healthy`;
- логи: `ssh deploy@<IP> "cd ~/habit_tracker && docker compose logs --tail=50"`;
- суперпользователь: `docker compose exec app python manage.py createsuperuser` (в каталоге `~/habit_tracker`).

Не выполняйте на сервере `docker system prune` и `docker compose down -v`: первая команда удалит неиспользуемые ресурсы,
вторая — данные БД.

## Частые проблемы

| Симптом | Причина и решение |
|---|---|
| `400 Bad Request` на любой странице | адреса (IP, домена) нет в `ALLOWED_HOSTS` |
| Страницы без стилей | не собрана статика или недоступен volume `static_data`: `docker compose logs app`, `docker compose exec nginx ls /app/staticfiles` |
| `password authentication failed` после смены `DB_PASSWORD` | Postgres применяет пароль только при создании volume. Верните старый пароль или выполните `ALTER USER` через `docker compose exec db psql`; локально можно `docker compose down -v` (данные будут удалены) |
| `port is already allocated` / ошибка порта 80 | порт занят другим сервисом; проверьте `Get-NetTCPConnection -LocalPort 80 -State Listen` (Windows) или `ss -tlnp` (Linux) |
| `Permission denied (publickey)` в deploy | публичный ключ не добавлен или перезаписан; секрет `SSH_KEY` вставлен не полностью (нужны строки `BEGIN`/`END` и перевод строки в конце) |
| `denied` при `docker compose pull` на сервере | у токена нет `packages: read` или пакет не связан с репозиторием: проверьте настройки пакета и права workflow |
| `denied: permission_denied: write_package` в job `build` | включите запись в Workflow permissions (см. выше) |
| entrypoint падает: `not found` / `bad interpreter` | CRLF в `docker/entrypoint.sh`; файл `.gitattributes` задаёт LF для `*.sh`, пересоздайте файл после `git checkout` |
| Напоминания не приходят | нет `tg_chat_id` в профиле, неверный `TELEGRAM_BOT_TOKEN` или вы не нажали `/start` у бота; смотрите `docker compose logs celery_worker` |
| Smoke-тест падает по тайм-ауту | сервис не стал healthy: `docker compose ps -a` и `docker compose logs` (деплой печатает их сам) |
| В значении `.env` теряется часть после `$` | возьмите значение в одинарные кавычки |
