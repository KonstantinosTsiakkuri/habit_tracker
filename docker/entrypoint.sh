#!/bin/sh
# Подготовка перед запуском веб-приложения: миграции и сбор статики в общий volume (его читает nginx).
# Затем управление передаётся команде контейнера (gunicorn); exec делает её процессом PID 1,
# поэтому сигналы остановки docker доходят до gunicorn.
set -e

echo "Применяем миграции..."
python manage.py migrate --noinput

echo "Собираем статику..."
python manage.py collectstatic --noinput

exec "$@"
