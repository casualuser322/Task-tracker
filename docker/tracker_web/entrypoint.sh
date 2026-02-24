#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
    sleep 1
done
echo "PostgreSQL is available."

echo "Waiting for Redis..."
while ! nc -z "$REDIS_HOST" "$REDIS_PORT"; do
    sleep 1
done
echo "Redis is available."

if [ "$SERVICE" = "web" ]; then
    echo "Running database migrations..."
    python manage.py migrate --noinput

    if [ "$DEBUG" = "True" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
        echo "Creating superuser..."
        python manage.py createsuperuser \
            --email "$DJANGO_SUPERUSER_EMAIL" \
            --noinput || true
    fi
fi

exec "$@"