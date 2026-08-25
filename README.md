# radio.games website

The web application behind [radio.games](https://radio.games/), an open-source amateur radio QSO matching service. Operators upload ADIF logs and the system finds confirmed mutual contacts.

Django 6 / Python 3.14, PostgreSQL 18, Redis 8. The REST API is [Django Ninja](https://django-ninja.dev/); the frontend is server-rendered templates with Bootstrap 5. Contact matching itself happens in [fast-adif-matcher](https://github.com/radiofun-org/fast-adif-matcher), a Go service that consumes uploads from a Redis queue and writes to the shared database.

## Running

```bash
cp env.example .env
docker compose up
```

Services: `web` (Django), `matcher` (Go), `awards-worker`, `db`, `redis`.

## Development

```bash
./run test                      # pytest
./run test api/tests.py -k match  # filtered
./run manage makemigrations     # any manage.py command
prek run --all-files            # ruff + ty
```

## Layout

- `app/` — auth, callsign management, uploads, profile, info pages
- `api/` — REST API (`/api/docs` for Swagger)
- `awards/` — award definitions, evaluator engine, worker
- `contacts/` — read-only models over the `matcher_*` tables the Go matcher writes

## Contributing

Issues and PRs welcome. To help translate the site, email [translation@radio.games](mailto:translation@radio.games).
