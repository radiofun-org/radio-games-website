#!/usr/bin/env bash

./manage.py collectstatic --no-input
./manage.py migrate
./manage.py runserver "0.0.0.0:${PORT}"
