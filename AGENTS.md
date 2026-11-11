# AGENTS.md — READY ROOM durable invariants

Repository-specific knowledge and gotchas for anyone (human or agent) working
here. Keep this file current when a durable invariant or boundary changes.

## Architecture boundaries (enforced by tests in `backend/tests/architecture/`)

- **Dependency direction points inward.** `domain` ← `application` ←
  `adapters`/`api`. Nothing inner imports something outer.
- **`domain/` is pure.** No FastAPI, SQLAlchemy, Pydantic transport schemas,
  ORM, sessions, environment reads, filesystem, or network. Domain unit tests
  run with no database.
- **`application/` services** coordinate domain objects and ports only. They
  must not import a concrete adapter, an ORM model, a FastAPI request, or a
  vendor SDK.
- **SQLAlchemy is confined to `adapters/persistence/sqlalchemy/`.** No other
  module may `import sqlalchemy`.
- **API routers are thin.** No business rules, no authorization policy logic,
  no database operations in route handlers.
- **The frontend does not reimplement authoritative urgency or recurrence
  rules.** It maps server-derived states to labels/icons/styles only.

## Domain invariants

- **Urgency is derived, never stored.** Computed on read from status, due date,
  local `today`, and the warning window (`domain/tasks/urgency.py`).
- **Recurrence is a chain of ordinary Task rows** sharing `series_id`, with a
  `recurrence_rule_id` and 1-based `occurrence_number`. There is **no**
  `TaskOccurrence` table.
- **Completion is idempotent.** Completing an already-completed task returns it
  unchanged and creates no second successor.
- **Exactly one successor.** Completing a recurring occurrence generates at most
  one successor; no successor is created if an open occurrence already exists
  for the rule.
- **No backfill.** Missed occurrences are skipped in a bounded fast-forward, not
  materialised. `occurrences_generated` stays truthful.
- **Month-end/leap-year arithmetic is anchored** on the series' first
  occurrence so clamping is deterministic (31 Jan → 31 Mar, not 28 Mar).
- **Editing a recurring task edits the existing rule** and preserves series
  identity and `occurrences_generated`; re-anchoring uses the current due date.
- **A rule is deactivated, never hard-deleted, while any occurrence references
  it** — completed history keeps its linkage.
- **Overdue tasks never disappear.** Completed tasks never appear in active
  operational sections.

## Time

- Persist datetimes as **naive UTC**. Due dates are plain `date`s.
- Resolve `today` from the operator's effective timezone via the clock port —
  never inline `datetime.now()`. Handles UTC rollover (23:30Z is still the prior
  day in America/New_York).
- Never compare a `date` with a `datetime`.
- **`tzdata` is required** in the runtime image for `zoneinfo`.

## Persistence

- `DatabasePort` (unit of work) exposes repositories and owns the transaction
  boundary. Repository methods **never commit**.
- Multi-step workflows (complete + create successor) run in **one** transaction;
  a successor failure must not leave a half-committed completion.
- Repository protocols are structural `Protocol`s returning domain entities,
  never ORM rows or sessions.
- Dialect is chosen from `READY_ROOM_DATABASE_URL`; the SQLAlchemy adapter must
  stay portable (no SQLite-only assumptions). `READY_ROOM_TEST_DATABASE_URL`
  lets the same suite run against PostgreSQL.
- The additive schema-evolution helper is idempotent and never destroys data.

## Identity and authorization

- Identity ("who") and authorization ("what may they do") are separate.
- The principal is resolved in **exactly one** FastAPI dependency and injected
  into use cases. Services never construct principals.
- Permission **and** ownership are both enforced; ownership filtering does not
  replace a permission check.
- `SingleUserAuthProvider` is a demo/development identity adapter. There is
  **no** login, session, or token flow, and the demo is **not** production
  security.

## Seed and reset

- Seeding is guarded by a `seed_version` marker **and** an "any tasks exist?"
  check; restarting containers must never duplicate demo data.
- `POST /api/demo/reset` clears task/recurrence/demo state and restores default
  categories and settings. A volume wipe is the last-resort reset.
- Seed data is **synthetic** (fictional detachment, made-up names). Never use
  real classified, sensitive, or operational military information.

## Runtime / Docker

- One command: `docker compose up --build`; browser at `http://localhost:8080`.
- The **frontend health check targets `127.0.0.1`**, not `localhost`. nginx
  must listen on IPv4 **and** IPv6.
- The frontend container depends on **backend health**, not just process start.
- Backend health endpoint: `/api/health`.
- No external services, credentials, or internet access at runtime.

## API conventions

- `?status=all` is the documented sentinel for "all statuses" in task listing.
- `422` for request-shape validation; `400`/`403`/`404`/`409` for domain and
  authorization outcomes, with a consistent typed error payload.
- `TaskRead` includes computed fields (`urgency`, `days_until_due`, embedded
  recurrence info). These are computed, not stored columns.
- `GET /api/timezones` returns the curated IANA shortlist plus `default_timezone`.
  The list always includes the operator's current zone, even if it is outside the
  shortlist. The backend still accepts any valid IANA identifier on `PATCH
  /api/settings`.

## Frontend dev proxy (gotcha)

- The Vite dev server proxies `/api` to `VITE_API_PROXY_TARGET`
  (default `http://localhost:8000`, see `frontend/.env.example`).
- If that target is **not** a running READY ROOM backend, **every** `/api/*`
  call returns `{"detail":"Not Found"}` — including quick capture. This is a
  proxy misconfiguration, not an endpoint defect. Point the variable at the
  backend (or the nginx origin) you actually started. The containerized app is
  unaffected: nginx proxies `/api/*` to `backend:8000`.

## Commands

```bash
# backend
cd backend && python -m pytest -q
# frontend
cd frontend && npm test -- --run && npm run build
```
