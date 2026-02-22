#!/usr/bin/env bash

.venv/bin/python manage.py collectstatic --no-input
.venv/bin/python manage.py migrate

if [[ $ENV = "production" ]]; then
  .venv/bin/gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers 4 \
    --threads 2 \
    app.wsgi
else
  .venv/bin/python manage.py runserver "0.0.0.0:${PORT}"
fi
