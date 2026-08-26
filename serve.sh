#!/usr/bin/env bash

set -euo pipefail

python manage.py collectstatic --no-input
python manage.py migrate

if [[ $ENV = "production" ]]; then
  /venv/bin/uvicorn --host 0.0.0.0 --port "${PORT}" --workers 4 --lifespan off app.asgi:application
else
  uvicorn --host 0.0.0.0 --port "${PORT}" --lifespan off --reload --reload-include "*.py" --reload-include "*.html" app.asgi:application
fi
