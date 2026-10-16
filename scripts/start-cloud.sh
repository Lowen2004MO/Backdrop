#!/bin/sh
set -eu

python manage.py migrate --noinput
if [ -n "${PEOPLE_PULSE_DEMO_PASSWORD:-}" ] || \
   [ -n "${PEOPLE_PULSE_DEMO_PASSWORD_SECRET_ARN:-}" ]; then
    python manage.py create_demo_users
fi
exec gunicorn people_pulse.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
