# BUILD_STATUS — READY ROOM autonomous build

Truthful milestone tracker. "Verified" means the gate's command/interaction was
actually executed and its result observed. Timestamps use the local machine
clock.

Last updated: 2026-11-11

| Milestone | Status | Gate evidence |
|---|---|---|
| M0 Repository inspection, decisions, runnable skeleton | **verified** | Docs created; `docker compose up --build` builds and serves the SPA at http://localhost:8080 with backend `healthy` and frontend `healthy`; `/api/health` -> `{"status":"ok",...}`; SPA HTTP 200 |
| M1 Domain core | **verified** | `pytest tests/unit` -> 59 passed (urgency boundaries, recurrence incl. month-end/leap-year/bounded no-backfill, entities, authorization, clock/timezone). No DB required. |
| M2 Ports, SQLAlchemy adapter, lifecycle | **verified** | Integration tests over real temporary SQLite: lifecycle, transaction rollback, idempotent completion, exactly-one successor |
| M3 API, identity, authorization | **verified** | API integration tests: allowed/denied actions, principal injection, owner scoping, validation errors, no-login demo |
| M4 Dashboard and briefing | **verified** | Dashboard/briefing tests: scan derived from persisted tasks, overdue visible, completed excluded, briefing reflects stored data |
| M5 Frontend shell, capture, inventory, dashboard | **verified** | `vitest run` -> 21 passed; `npm run build` succeeds; live UI exercised through nginx (dashboard renders, quick capture persists, inventory filters/actions present) |
| M6 Recurrence UX and settings | **verified** | Frontend recurrence preview + settings views; backend tests cover editing recurrence in place, preserving series/history, bounded generation, configurable window, category persistence |
| M7 Seeding and operational polish | **verified** | Idempotent seed (restart does not duplicate); reset restores defaults; README setup/config documented |
| M8 Database portability verification | **verified** | Same suite green on SQLite **and** PostgreSQL (`READY_ROOM_TEST_DATABASE_URL=postgresql+psycopg://...:55432/...`) with no domain/application changes |
| M9 Full verification and submission | **verified** | Clean Docker build; backend 120 passed + ruff + mypy clean; frontend 21 passed + typecheck + build; persistence across restart confirmed; live API exercised through the nginx origin |

## Environment notes

- Repo was an empty skeleton (only a stub `README.md`) at session start; working
  tree clean on `main`.
- Tooling: Docker 29.9.2, Docker Compose v5.6.1, Node v24.22.2, Python 3.12
  (backend `.venv`).
- A pre-existing `postgres:16-alpine` container (`rr-pg-test`, port 55432,
  user/db `readyroom`) is used for the M8 PostgreSQL verification only and is
  **not** part of the default Compose stack.

## Verification log

- 2026-11-11 — `pytest tests/unit -q` -> **59 passed** (M1 gate).
- 2026-11-11 — `pytest` (full) -> **120 passed, 1 warning** (M2–M4, M6, M7).
- 2026-11-11 — `ruff check .` -> **All checks passed**; `mypy app` ->
  **Success: no issues found in 64 source files**.
- 2026-11-11 — `READY_ROOM_TEST_DATABASE_URL='postgresql+psycopg://readyroom:readyroom@localhost:55432/readyroom' pytest` -> **120 passed** (M8).
- 2026-11-11 — `npm run test:run` -> **21 passed**; `npm run build` -> built in
  ~240 ms (M5).
- 2026-11-11 — `docker compose up --build -d` -> backend `Up (healthy)`,
  frontend `Up (healthy)`; `/api/health` ok; SPA HTTP 200 (M0).
- 2026-11-11 — Live API through nginx origin: create recurring task ->
  complete -> **idempotent** second complete -> **exactly one** open successor
  (`occurrence_number=2`, `due_date=2026-11-23`) (M9).
- 2026-11-11 — Settings PATCH window 3->5 -> dashboard `watch_label` becomes
  `5-Day Watch`; briefing reflects persisted data (M4/M6).
- 2026-11-11 — `docker compose restart backend` -> task count and modified
  settings persisted (12 tasks, window 5, tz America/Chicago) (M9).
- 2026-11-11 — `POST /api/demo/reset` -> cleared tasks/rules, restored default
  categories and settings; subsequent restart reseeded the demo scenario (M7).
- 2026-11-11 — Browser: dashboard renders live seeded data; quick capture from
  the UI persisted a task visible in the inventory; Settings and Inventory views
  render correctly (M5).

## Remaining work

- None blocking. All mandatory Definition of Done items verified.
- Optional/deferred (documented, out of scope for this cut): PostgreSQL in the
  default Compose stack, Alembic migrations, notifications, integrations, and
  multi-user collaboration.
