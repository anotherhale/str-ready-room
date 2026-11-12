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
| M10 Dev quick-capture "Not Found" fix + timezone/UX polish | **verified** | Root-caused to the Vite dev proxy target (not the capture endpoint); proxy target now configurable + documented; `GET /api/timezones` + Settings drop-down; overdue/due card shading; quick capture captures category/due/priority. Backend **122 passed** + ruff clean; frontend **23 passed** + typecheck + build; live browser E2E on the rebuilt container (capture 201, "Captured.", 18 timezone options) |
| M11 Calendar + mailbox integrations (optional profile) | **verified** | Optional `integrations` Compose profile (Radicale + GreenMail); CalDAV and IMAP adapters verified against real containers through the nginx origin; capture (event/message -> task) idempotent; no duplication across restart. Backend **183 passed** + ruff + mypy clean; frontend **34 passed** + typecheck + build. See D-025–D-034 |

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
- 2026-11-11 — **Reproduced the "Not Found" report**: `npm run dev` (default
  proxy `http://localhost:8000`) → all `/api/*` return `{"detail":"Not Found"}`
  (404); `POST /api/tasks` from the UI shows a "Not Found" error. Root cause:
  port 8000 was an unrelated service, not the backend (M10).
- 2026-11-11 — `VITE_API_PROXY_TARGET=http://localhost:8099 npm run dev` →
  `GET /api/me` 200 and browser quick capture `POST /api/tasks` **201**,
  toast "Captured." (M10).
- 2026-11-11 — `pytest -q` (full) -> **122 passed, 1 warning** (adds two
  `/api/timezones` integration tests); `ruff check app tests` -> **All checks
  passed** (M10).
- 2026-11-11 — `npm run test:run` -> **23 passed** (QuickCapture suite expanded
  to 5); `npm run typecheck` -> clean; `npm run build` -> built (M10).
- 2026-11-11 — `docker compose up --build` (rebuilt) -> both containers healthy;
  `GET /api/timezones` -> 18 zones incl. `America/New_York`, default
  `America/Denver`; browser E2E on the container: quick capture with
  category/priority/date `POST 201`, toast "Captured.", input cleared, Settings
  timezone `<select>` renders 18 options, no console errors (M10).
- 2026-11-12 — `pytest` (full) -> **183 passed, 1 warning**; `ruff check app tests`
  -> **All checks passed**; `mypy app` -> **Success: no issues found in 84 source
  files** (M11).
- 2026-11-12 — `npm run test:run` -> **34 passed**; `npm run typecheck` -> clean;
  `npm run build` -> built (M11).
- 2026-11-12 — `docker compose up --build` (base stack) -> backend + frontend
  healthy; `/api/health` ok; SPA HTTP 200; `POST /api/demo/reset` then backend
  restart reseeded **10** tasks (M11 base regression check).
- 2026-11-12 — Live recurring completion through the nginx origin: complete ->
  `completed`, **idempotent** second complete -> unchanged, exactly **one** open
  successor (`occurrence_number=2`, `due_date=2026-11-20`) (M11).
- 2026-11-12 — `READY_ROOM_CALENDAR_PROVIDER=caldav READY_ROOM_EMAIL_PROVIDER=imap
  docker compose --profile integrations up --build` -> **four** services healthy
  (backend, frontend, radicale, greenmail). `POST /api/calendar/sync` ->
  `fetched 4, created 4`; agenda shows the events at the correct local wall-clock
  times; `POST /api/mail/messages/{id}/tasks` and
  `POST /api/calendar/events/{id}/tasks` both captured into tasks (recapture
  reused the same task) (M11).
- 2026-11-12 — Integration restart check: `docker compose --profile integrations
  restart backend` -> mailbox still 3 messages (no duplication), calendar cache
  still 4 events, Radicale `PUT` count unchanged at 4; the mailbox seed
  self-repaired after the in-memory mail store was lost (M11).
- 2026-11-12 — Mailbox capture UX fix: after capturing a message the detail pane
  now flips to "In inventory" immediately (was showing a stale snapshot until the
  message was reopened); regression test added (`frontend` 35 passed).
- 2026-11-12 — Mailbox capture dialog now defaults its due date to the operator's
  local today (server-resolved `dashboard.today`), instead of the empty
  `mm/dd/yyyy` placeholder (`frontend` 36 passed, typecheck + build clean).
- 2026-11-12 — Default operator timezone changed to **America/Denver** (MST/MDT)
  in `config.py`, the domain default, and `docker-compose.yml`; docs updated
  (README config table, AGENTS). A fresh reset/volume uses Denver.
- 2026-11-12 — Calendar create-timezone fix: an event entered as 16:00 in the
  `datetime-local` form was stored/returned **naive**, so the browser
  re-interpreted it in its own zone and displayed 18:00. `create_event` now
  anchors floating local times to the operator's zone; live check: POST
  `2026-11-12T16:00` -> `2026-11-12T16:00:00-07:00`, survives sync. Backend
  **193 passed** (+3), ruff + mypy clean (D-037).
- 2026-11-12 — Calendar delete fix: `DELETE /api/calendar/events/{id}` returned
  **500** because the cached CalDAV href is server-relative and `urllib` rejects
  it; the provider now resolves hrefs to absolute in `list_events`/`delete_event`.
  Live check: delete -> **204**. Backend tests added for the URL shapes (D-038).

## Remaining work

- None blocking. All mandatory Definition of Done items verified.
- The optional calendar/mailbox integrations (M11) are implemented and verified
  behind the `integrations` Compose profile; they are off by default so the base
  stack remains self-contained.
- Optional/deferred (documented, out of scope for this cut): PostgreSQL in the
  default Compose stack, Alembic migrations, notifications, and multi-user
  collaboration.
