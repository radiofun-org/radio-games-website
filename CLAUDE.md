# radio.games website

Open-source amateur radio QSO matching service (like LoTW/Club Log but fully open). Operators upload ADIF logs and the system finds confirmed mutual contacts.

## Architecture

- **Django 6 / Python 3.14** running under **uvicorn** (ASGI)
- **PostgreSQL 18** for all data, **Redis 8** for cache + session store + upload queue
- **Django Ninja** for the REST API (`/api/`)
- **Go-based fast-matcher** (separate repo at `../fast-matcher`) consumes uploads from Redis, writes to `contacts` and `matches` tables directly
- Frontend is server-rendered Django templates + Bootstrap 5 CDN + vanilla JS

## Docker Compose services

`web` (Django) / `matcher` (Go) / `db` (Postgres) / `redis` — all configured via `.env`

## Django apps

| App | Purpose |
|------|---------|
| `app` | Core: auth, callsign management, file upload, profile, pages |
| `api` | Django Ninja REST API (callsign lookup, upload, matches) |
| `contacts` | Models for `Contact` and `Match` — written by the Go matcher, read-only from Django |

## Key models

- **`AuthUser`** — extends `AbstractUser`, adds `api_key` (64-char hex). Uses `db_table = "auth_user"`.
- **`CallsignAssociation`** — links callsigns to users with metadata (name, country, grid, lat/lon, date range). Unique on `(callsign, user)`.
- **`LogUpload`** — uploaded ADIF file + callsign + processed flag.
- **`Contact`** / **`Match`** — owned by the Go matcher. `Contact` fields are integer-encoded ADIF data. `Match` pairs two contact IDs. Both use `BigIntegerField` for IDs, not Django ForeignKeys.

## URL structure

- `/` — landing page (login + signup in one form, toggled by `form_type`)
- `/profile/` — dashboard, callsign CRUD, API key management
- `/upload/` — ADIF file upload with drag-drop and header parsing
- `/api/` — Ninja API root; `/api/docs` — Swagger UI
- `/accounts/` — Django auth (login, logout, password change/reset)
- `/about/`, `/faq/`, `/how-it-works/` — info pages

## API authentication

`X-API-Key` header, validated against `AuthUser.api_key`. Three endpoints:
- `GET /api/callsign/{call}/` (public)
- `POST /api/upload/?callsign=X` (authenticated)
- `GET /api/matches/` (authenticated, supports limit/offset)

## Running locally

```bash
docker compose up          # all services
./run test                 # pytest in container
./run manage makemigrations
```

`serve.sh` runs collectstatic + migrate, then uvicorn (dev: `--reload`, prod: 4 workers via `/venv/bin/uvicorn`).

## Testing

pytest + pytest-django. Test settings (`app/test_settings.py`) swap Redis cache for LocMemCache and sessions to DB backend.

```bash
./run test                      # all tests
./run test api/tests.py -k match  # filtered
```

## Code style

- **ruff** format + lint (rules: E, F, UP) — line length 99
- **mypy** for type checking
- Method-based pytest (no classes)
- Async views where needed (e.g. `callsign_lookup` calls callook.info via httpx)

## External integrations

- **callook.info** — US callsign metadata lookup (async httpx)
- **Mailgun** — transactional email via django-anymail
- **ALTCHA** — captcha on signup form

## Conventions

- Username field is always the user's email, normalized to lowercase
- `contacts` models use integer-encoded fields (band, mode, callsign IDs) — the Go matcher handles encoding/decoding
- Uploads go to `uploads/` (mounted volume shared with matcher container)
- Production uses `/venv/bin/uvicorn` directly to avoid uv memory overhead
