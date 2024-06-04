#!/usr/bin/env bash

./manage.py collectstatic --no-input
./manage.py migrate

if [[ $ENV = "production" ]]; then
  gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers 4 \
    --threads 2 \
    app.wsgi
else
  ./manage.py runserver "0.0.0.0:${PORT}"
fi
