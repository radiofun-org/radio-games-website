# radio.games website

Open-source amateur radio QSO matching service (like LoTW/Club Log but fully open). Operators upload ADIF logs and the system finds confirmed mutual contacts.

## Architecture

- **Django 6 / Python 3.14** running under **uvicorn** (ASGI)
- **PostgreSQL 18** for all data, **Redis 8** for cache + session store + upload queue
- **Django Ninja** for the REST API (`/api/`)
- **Go-based fast-matcher** (separate repo at `../fast-matcher`) consumes uploads from Redis, writes to `matcher_*` tables directly
- Frontend is server-rendered Django templates + Bootstrap 5 CDN + vanilla JS

## Docker Compose services

`web` (Django) / `matcher` (Go) / `awards-worker` (Django) / `db` (Postgres) / `redis` — all configured via `.env`

## Django apps

| App | Purpose |
|------|---------|
| `app` | Core: auth, callsign management, file upload, profile, pages |
| `api` | Django Ninja REST API (callsign lookup, upload, matches) |
| `awards` | Award definitions, grants, and progress tracking. Evaluator engine in `awards/evaluate.py`, worker in `awards/worker.py`. |
| `contacts` | Models for `Callsign`, `AdifMetadata`, `Contact`, and `Match` — written by the Go matcher, read-only from Django. All use `matcher_*` table names. |

## Key models

- **`AuthUser`** — extends `AbstractUser`, adds `api_key` (64-char hex). Uses `db_table = "auth_user"`.
- **`CallsignAssociation`** — links callsigns to users with metadata (name, country, grid, lat/lon, date range). Unique on `(callsign, user)`.
- **`LogUpload`** — uploaded ADIF file + callsign + processed flag. `replaces` links a corrected re-upload to the upload it supersedes; the matcher diffs the two files and deletes contacts (and their matches) that only the old file asserted.
- **`Callsign`** — maps callsign strings to integer IDs (`matcher_callsign`). Written by the Go matcher, used by Django to decode `from_id`/`to_id` on contacts.
- **`AdifMetadata`** — ADIF file metadata (hash, version, program) (`matcher_adif_metadata`).
- **`Contact`** / **`Match`** — owned by the Go matcher (`matcher_contact`, `matcher_match`). `Contact` fields are integer-encoded ADIF data; `contacts/decode.py` has the reverse maps. `Match` pairs two contact IDs. Both use `BigIntegerField` for IDs, not Django ForeignKeys.
- **`AwardDefinition`** — defines an award: slug, name, category, tier (QUERY or CODE), and evaluator (JSON rule or dotted Python path).
- **`AwardGrant`** — records a user earning an award. `granted_at` = processing time, `evidence_at` = date of qualifying contact. Unique constraint ensures one active grant per user/award.
- **`AwardProgress`** — cached progress toward each award per user. JSON `detail` field shape varies by award type.

## URL structure

- `/` — landing page (login + signup in one form, toggled by `form_type`)
- `/profile/` — dashboard with contact stats (by mode/band/country), callsign CRUD, API key management, account deletion
- `/profile/apps/` — OAuth2 application management (create/delete apps)
- `/logbook/` — user's contacts with confirmed/unconfirmed status, paginated
- `/upload/` — ADIF file upload with drag-drop and header parsing
- `/api/` — Ninja API root; `/api/docs` — Swagger UI
- `/accounts/` — Django auth (login, logout, password change/reset)
- `/oauth/` — OAuth2 provider endpoints (authorize, token, revoke)
- `/about/`, `/faq/`, `/how-it-works/` — info pages

## API authentication

`X-API-Key` header, validated against `AuthUser.api_key`. Four endpoints:
- `GET /api/callsign/{call}/` (public)
- `POST /api/upload/?callsign=X` (authenticated)
- `GET /api/matches/` (authenticated, cursor-paginated: `page_size` up to 200, follow `next`/`previous` URLs; response is `{results, next, previous}`)
- `GET /api/matches/adif?since=TIMESTAMP` (authenticated, returns gzipped ADIF; `since` is Unix timestamp for incremental sync)

## OAuth2

Uses `django-oauth-toolkit`. Users can create OAuth2 applications at `/profile/apps/` for building third-party tools. Supports authorization code grant flow. Scopes: `read` (matches/callsigns), `upload` (ADIF upload). OAuth endpoints at `/oauth/authorize/`, `/oauth/token/`, `/oauth/revoke_token/`; RFC 8414 server metadata at `/oauth/.well-known/oauth-authorization-server`. Settings opt into the RFC 9700 security BCP gates (S256-only PKCE, no implicit/password grants, hashed token storage, refresh-token reuse protection); `http` redirect URIs stay allowed for native-app loopback callbacks.

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

- **ruff** format + lint (rules: E, F, UP) — line length 99; generated migrations are exempt from E501
- **ty** for type checking, with **django-stubs** supplying Django types (stubs only — no mypy plugin; ty reads them directly). The only suppressions are `# ty: ignore[invalid-argument-type]` markers on the `@login_required()`/`@require_POST` decorator stacks in `app/views.py`: ty cannot yet solve `require_POST`'s `Callable[[_F], _F]` alias application. Drop them when it can. Use `.pk` (not `.id`) on models — the stubs only declare `pk` without the mypy plugin.
- **prek** (`prek.toml`) runs ruff check/format and the project's locked ty on commit; `prek run --all-files` to run manually
- Method-based pytest (no classes)
- Async views where needed (e.g. `callsign_lookup` calls callook.info via httpx)

## External integrations

- **callook.info** — US callsign metadata lookup (async httpx)
- **Mailgun** — transactional email via django-anymail
- **ALTCHA** — captcha on signup form

## Conventions

- Username field is always the user's email, normalized to lowercase
- `contacts` models use integer-encoded fields (band, mode, callsign IDs) — the Go matcher encodes, `contacts/decode.py` decodes
- `Match.a_call_id`/`b_call_id` reference `Callsign.id` (NOT `CallsignAssociation.id`) — resolve via callsign string
- Uploads go to `uploads/` (mounted volume shared with matcher container)
- Account deletion erases the user's uploads (rows + files), matcher contacts, and their matches, then queues counterparty callsigns for award re-evaluation; counterparties' own log entries, bare `matcher_callsign` rows, and already-granted awards stay
- Production uses `/venv/bin/uvicorn` directly to avoid uv memory overhead

## Awards pipeline

1. Upload → Redis `log_upload_queue` → Go matcher processes contacts + matches
2. Matcher `SADD`s affected `matcher_callsign` IDs to Redis set `awards_eval_pending`
3. Awards worker (`manage.py run_awards_worker`) `SPOP`s batches, resolves callsign IDs → users via `CallsignAssociation`, evaluates all enabled `AwardDefinition`s
4. Two evaluation tiers:
   - **QUERY** (tier 1): structured JSON rules interpreted by `awards/evaluate.py` — `count`, `count_distinct`, `collect_all`
   - **CODE** (tier 2): dotted Python path to a function with signature `(contacts, matcher_ids) -> EvalResult`
5. Results written to `AwardGrant` (earned) and `AwardProgress` (cached progress for display)
