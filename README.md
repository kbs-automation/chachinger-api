# CHA3535 Session Intelligence — Backend

Backend API for the CHA3535 Flutter app (`../cha_chingler`), built from the
*CHA3535 Backend API Creation Prompt v3.0*.

- **API:** Python 3.12, FastAPI (async), SQLAlchemy 2, Alembic
- **Data:** PostgreSQL 16, Redis 7 (refresh-token state and rate limiting)
- **Auth:** JWT RS256 access tokens (15 min) and rotating 30-day refresh tokens (httpOnly cookie,
  also returned in the body for the mobile app). Admins use a separate HS256 secret and a separate login.
- **Integrations:** Stripe Billing with idempotent webhooks, S3 avatars (private bucket, presigned URLs),
  Sentry, and Datadog (`ddtrace-run`)

```
cha3535/
├── api/
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/        auth, sessions, plays, spins, modes, users, billing, admin
│   │   ├── models/         SQLAlchemy ORM (all tables)
│   │   ├── schemas/        Pydantic — no click_number in any user response schema
│   │   ├── services/       engine, budget, play_tracker, sessions, billing, auth, storage, admin, …
│   │   └── engine/         CONFIDENTIAL — zone_maps, mode_engine, ru_calc, early_attack (stub)
│   ├── migrations/         Alembic (0001 creates every table and seeds the 5 P1 modes)
│   ├── scripts/            create_admin.py, generate_jwt_keys.py
│   └── tests/              the 11 required test modules
├── docker-compose.yml      postgres + redis (+ optional api profile)
└── .github/workflows/ci.yml  lint → test → build → ECR → ECS
```

## Local development

```bash
docker compose up -d postgres redis   # POSTGRES_PORT=55432 if 5432 is already taken

cd api
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                               # adjust DATABASE_URL / Stripe keys
alembic upgrade head
python -m scripts.create_admin admin@example.com   # prompts for a password
uvicorn app.main:app --reload
```

Interactive docs are served at <http://localhost:8000/docs> outside production.

With `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` empty, development generates an ephemeral key pair at
startup, so tokens are invalidated on restart. Production refuses to start without real keys and an
`ADMIN_JWT_SECRET` of at least 32 bytes. Run `python -m scripts.generate_jwt_keys` to create keys.

## Tests

```bash
pytest -q                                          # in-memory SQLite + fakeredis
TEST_DATABASE_URL=postgresql+asyncpg://cha3535:cha3535@localhost:5432/cha3535_test pytest -q
```

CI runs the suite against Postgres 16, runs `test_click_number_not_exposed.py` as its own step, and
checks that `alembic upgrade head` followed by `alembic check` reports no drift between migrations and models.

## API flow (mobile app)

All routes live under `/api/v1`. Every error has the shape `{"detail": {"code", "message", ...}}`.

1. `GET /modes` lists the active P1 modes with their minimum budget and baseline bets.
   `POST /modes/{id}/suggest {budget}` previews the bets and Session Budget a new session would get.
2. `POST /sessions {p1_mode, budget}` returns suggested bets and a `session_budget` that the server
   has already raised to cover the suggested ladder's full 96-click exposure.
   `DELETE /sessions/{id}` discards a session that has no plays yet (the player backed out of bet setup).
3. Whenever the player changes bets or switches a posture off, call
   `POST /sessions/{id}/recalculate-budget {base, press, max, active_postures?}`. Before Play-1 starts,
   the budget follows the bets up or down. Bets entered by hand, or played with a posture switched off,
   cost exactly their 96-click exposure. After Play-1 starts the budget only goes up.
4. `POST /sessions/{id}/plays {confirmed_base, confirmed_press, confirmed_max, active_postures?}` locks
   the bets for the play. P1 returns `409 budget_recalculation_required` if the bets need a bigger budget.
   `active_postures` lists at least two of `base`, `press`, `max`. A switched-off posture's clicks are
   played at the nearest active posture below it, or above it if none is below.
   `DELETE /plays/{id}` discards a play that has no spins yet, so the player can go back to bet setup.
5. `POST /plays/{id}/spins` (no body) is sent once per machine spin. The response gives the posture and
   bet amount for that spin. `POST /plays/{id}/spins/undo` reverses the latest spin if it has no result.
6. `POST /plays/{id}/spins/{spin_id}/result` reports a payout, as either `{result: "34x" | "bonus"}`,
   `{win_amount}` (the dollar payout, converted to a multiplier of the spin's bet), or
   `{result: "bonus", win_amount}`. `redirect` is `next_play` (10x or more, or a bonus), `hard_exit`,
   or `continue`.

The spin response follows section 4.5 exactly and adds two fields: `spin_id`, which step 6 needs, and
`redirect`, which reports a hard exit when a spin is attempted past the cap.

## Engine rules as implemented

- **Click caps:** P1 (the session's first play) uses `p1_mode_configs.click_cap` (96) for every mode.
  Every later play uses 70. The engine always reads the cap from `plays.click_cap`.
- **Hard exit:** a non-qualifying result on the cap click, or any spin attempted past the cap, ends both
  the play and the session as `hard_exit`.
- **Mode deactivation:** a qualifying P1 result sets `p1_mode_active = false`. Later plays use the
  standard map with no mode logic.
- **Play numbering:** `play_number` runs 1–6 and then wraps, incrementing `cycle_number`.
- **Admin writes:** every admin write goes through `services/audit.record_admin_action` inside the same
  transaction. A Postgres trigger rejects `UPDATE` and `DELETE` on `admin_audit_log`.
- **Zone maps:** never serialized. Admin mode endpoints report only `zone_count`, and audit-log payloads
  are redacted to a SHA-256 hash.

## Additions beyond the prompt's schema

| Addition | Why |
|---|---|
| `users.is_suspended`, `created_at`, `updated_at` | `/admin/users/{id}/suspend` and the admin users list (join date) need them |
| `users.username` nullable (displayed as `PLAYER`) | A literal `PLAYER` default conflicts with `UNIQUE` |
| `users.avatar_url` stores the S3 key | Presigned URLs expire, so a fresh one is generated on every read |
| `p1_mode_configs.label`, `sort_order` | `GET /modes` must return a label |
| `engine_config` table | Backs `PATCH /admin/config` inside the same audited transaction |
| `GET /admin/modes`, `GET /admin/config`, `POST /admin/auth/login` | Read endpoints and a separate admin login for the admin panel |
| Optional `win_amount` on bonus results | A bonus has no multiplier, so its payout must be entered directly |
| `win_amount` without `result` | The mobile app asks for the dollar payout, not a multiplier |
| `plays.active_postures`, `sessions.player_budget` | Posture switching and budget repricing as the mobile app does them |
| `POST /plays/{id}/spins/undo`, `DELETE /sessions/{id}`, `DELETE /plays/{id}`, `POST /modes/{id}/suggest` | Undo spin, the app's back buttons before play starts, and its budget preview screen |

## Not yet built

- **Admin UI:** the React 18 + Tailwind admin panel. Every admin API it needs is implemented.
- **Execution grade:** stubbed as `A+`. It is configurable through `execution_grade_default`.
- **Early Attack:** `engine/early_attack.py` is a stub. `authorize()` returns `False` until the spec lands.
