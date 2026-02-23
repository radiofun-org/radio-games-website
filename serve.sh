#!/usr/bin/env bash

python manage.py collectstatic --no-input
python manage.py migrate

if [[ $ENV = "production" ]]; then
  /venv/bin/uvicorn --host 0.0.0.0 --port "${PORT}" --workers 4 app.asgi:application
else
  uvicorn --host 0.0.0.0 --port "${PORT}" --reload --reload-include "*.py" --reload-include "*.html" app.asgi:application
fi
