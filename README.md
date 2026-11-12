# READY ROOM

Operational-awareness for a single Navy aviation detachment officer.

Maverick currently spreads his responsibilities across sticky notes, email
flags, a whiteboard, and memory. READY ROOM replaces that with one operational
scan that answers three questions at a glance:

1. **What requires my attention now?**
2. **What is on the horizon?**
3. **Is anything important approaching that I might otherwise overlook?**

It is deliberately *not* another unrestricted task list. The dashboard is the
product; the full inventory is a secondary view.

---

## Quick start

```bash
docker compose up --build
```

Then open **<http://localhost:8080>**.

That single command builds and starts the complete application (FastAPI +
SQLite backend, React SPA served by nginx) with synthetic demonstration data
seeded automatically. No other software, cloud services, external databases,
identity providers, or API keys are required -- only Docker.

### Stop

```bash
docker compose down          # stop containers, keep data
docker compose down -v       # stop containers AND wipe the SQLite volume
```

---

## Reset

Three ways to return to the demonstration state:

| Method | How | Effect |
|---|---|---|
| **UI** | Settings -> *Reset demo data* | Clears tasks and recurrence rules; restores default categories and settings; reseeds the demo scenario immediately. |
| **API** | `curl -X POST http://localhost:8080/api/demo/reset` | Same as the UI action. |
| **Volume wipe** (last resort) | `docker compose down -v && docker compose up --build` | Destroys the SQLite volume entirely; a fresh database is initialised and reseeded. |

---

## Local development (frontend hot reload)

Docker Compose is the supported runtime; the instructions below are only for
running the SPA with Vite hot reload against a backend.

1. Start a backend the dev server can reach. Easiest: run the stack and point
   the proxy at the nginx origin, which forwards `/api` to the backend:

   ```bash
   docker compose up --build          # stack on http://localhost:8080
   cd frontend
   VITE_API_PROXY_TARGET=http://localhost:8080 npm run dev   # http://localhost:5173
   ```

   Alternatively run the backend directly (it needs no Docker) and keep the
   default proxy target:

   ```bash
   cd backend && uvicorn app.main:app --reload --port 8000
   cd frontend && npm run dev
   ```

The Vite dev server proxies `/api` to `VITE_API_PROXY_TARGET` (default
`http://localhost:8000`; see `frontend/.env.example`). The same proxy applies to
`vite preview` (production build). **If that target is not a running READY ROOM
backend, every `/api/*` call — including quick capture — returns
`{"detail":"Not Found"}`.** Point the variable at the backend/nginx origin you
actually started.

---

## Product overview

### The operational scan

The dashboard shows, in order:

- a persistent **quick-capture** bar (available on every view),
- a local-time greeting and the current date in the operator's timezone,
- a one-line readiness summary,
- compact counts (overdue / due / watch / horizon / completed-this-week),
- **TODAY** -- overdue and due-today responsibilities,
- **WATCH** -- responsibilities inside the configured warning window (the label
  reflects the window, e.g. `3-Day Watch`),
- **ON THE HORIZON** -- everything beyond the watch window,
- actions to open the daily briefing or the full inventory.

### Urgency (derived, never stored)

| Condition | Urgency | Meaning |
|---|---|---|
| Completed | `COMPLETED` | Completed |
| No due date | `NORMAL` | Normal |
| Due before local today | `OVERDUE` | Overdue |
| Due today | `DUE` | Due today |
| Due within the warning window | `WATCH` | Watch |
| Beyond the warning window | `UP_NEXT` | On the Horizon |

Every state has a text label and a glyph; colour is never the only signal.
Overdue work never disappears; completed work never appears in active sections.

### Recurrence

Recurring responsibilities (e.g. the Monday morning brief, the Friday status
roll-up, quarterly currency paperwork) are modelled as a **chain of ordinary
Task rows** sharing a `series_id`, each with a `recurrence_rule_id` and a
1-based `occurrence_number`. Completing an occurrence preserves its history and
generates **exactly one** successor if the rule permits and no open occurrence
already exists. Missed occurrences are *not* backfilled (bounded
fast-forward). Month-end and leap-year arithmetic is deterministic.

---

## Technology stack

| Layer | Choice |
|---|---|
| Frontend | React 18, TypeScript, Vite, hand-written CSS, Vitest + React Testing Library |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Pytest |
| Database | SQLite (default) behind a persistence port; PostgreSQL supported by configuration |
| Runtime | Docker Compose; nginx serves the SPA and reverse-proxies `/api/*` |

---

## Architecture

Dependency direction points inward (domain-driven, ports & adapters):

```
React SPA
   |
   v
HTTP / FastAPI inbound adapters        (backend/app/api)
   |
   v
Application services / use cases       (backend/app/application)
   |
   +--> Domain model & domain services  (backend/app/domain)
   |
   +--> Outbound ports                  (backend/app/application/ports)
             |
             v
        Adapter registry / composition root   (backend/app/composition.py)
             |
      +------+-------+
      v              v
 SQLAlchemy      Single-user identity,
 persistence     policy authorizer
 adapter         (backend/app/adapters/*)
      |
      v
   Database
```

Key rules (enforced by `backend/tests/architecture/test_boundaries.py`):

- `domain/` imports no FastAPI, SQLAlchemy, or Pydantic transport schemas, and
  no environment/filesystem/network. Domain unit tests need no database.
- `application/` services depend only on domain objects and ports -- never a
  concrete adapter, ORM model, or FastAPI request.
- SQLAlchemy is confined to `adapters/persistence/sqlalchemy/`.
- API routers are thin: parse/validate, resolve the principal, call a service,
  map the outcome to HTTP. No business rules in handlers.
- The frontend maps server-derived urgency/recurrence states to
  labels/icons/styles only; the backend is authoritative.

---

## Authentication & authorization (explicit no-login demo)

Authentication (**who is acting**) and authorization (**what may they do**) are
separate, first-class concerns -- even though the demo has no login screen.

- **Identity**: a framework-independent `Principal` (`id`, `display_name`,
  `timezone`, `roles`) lives in `domain/identity/`. Nothing in the domain or
  application layer knows about cookies, JWTs, sessions, or HTTP headers.
- **Authentication port**: `AuthProvider.resolve_current_principal(context)`.
  The demo adapter `SingleUserAuthProvider` returns one configured operator
  (id/name/timezone from configuration) and never prompts for credentials. It
  is resolved in exactly one FastAPI dependency; routers never inspect auth
  state themselves.
- **Authorization**: `Permission` values (`tasks:read`, `tasks:create`,
  `tasks:complete`, `settings:update`, `demo:reset`, ...), an
  `AuthorizationDecision` (allow/deny + code/reason), and an `AuthorizationPort`.
  The application service boundary calls `authorize(...)` **before** protected
  work. The demo policy grants the single operator all first-cut permissions,
  but it runs the *same* code path a future provider would.
- **Ownership**: user-owned entities carry `owner_id`; repositories scope reads
  and mutations by owner. Permission checks and ownership filtering are both
  applied -- ownership does not replace authorization.

> **Limitation.** This demo provides **no production security**. There are no
> credentials, sessions, or tokens. The single-user provider is a
> development/demonstration identity adapter. Attaching a real provider means
> adding a new `AuthProvider` adapter and wiring it in the registry -- no changes
> to domain entities or application services.

---

## Persistence (a port, not an architecture)

Persistence is an outbound adapter behind `DatabaseFactoryPort` /
`DatabasePort` (a unit of work exposing repositories and owning the transaction
boundary). Repositories are structural `typing.Protocol` interfaces that accept
and return **domain entities**, never ORM rows or sessions. Application services
never import SQLAlchemy; driver exceptions are translated into an
application-owned `PersistenceError`.

### Database configuration

| Variable | Default | Purpose |
|---|---|---|
| `READY_ROOM_DB_ADAPTER` | `sqlalchemy` | Selects the persistence adapter |
| `READY_ROOM_DATABASE_URL` | `sqlite:////data/ready_room.db` | SQLAlchemy URL (dialect chosen by URL) |

The SQLAlchemy adapter picks its dialect from the URL. **PostgreSQL** is a
first-class target for the same adapter -- point `READY_ROOM_DATABASE_URL` at a
`postgresql+psycopg://...` URL and no domain, application, API, or frontend
change is required. The same integration suite can be run against either
database via `READY_ROOM_TEST_DATABASE_URL`.

Schema initialisation is automatic on startup. Additive, idempotent migration
helpers live inside the SQLAlchemy adapter; Alembic is intentionally not adopted
for this first cut (see `DECISIONS.md`).

---

## Configuration

All backend configuration is read from the environment with the `READY_ROOM_`
prefix:

| Variable | Default | Notes |
|---|---|---|
| `READY_ROOM_ENVIRONMENT` | `demo` | Surfaced on `/api/health` |
| `READY_ROOM_DB_ADAPTER` | `sqlalchemy` | Adapter registry key |
| `READY_ROOM_DATABASE_URL` | `sqlite:////data/ready_room.db` | SQLite by default; PostgreSQL supported |
| `READY_ROOM_AUTH_PROVIDER` | `single_user` | Identity adapter key |
| `READY_ROOM_OPERATOR_ID` | `maverick` | Demo principal id |
| `READY_ROOM_OPERATOR_DISPLAY_NAME` | `Maverick` | Demo principal name |
| `READY_ROOM_DEFAULT_TIMEZONE` | `America/New_York` | Operator timezone (validated) |
| `READY_ROOM_AUTHORIZATION_ENGINE` | `policy` | Authorization adapter key |
| `READY_ROOM_SEED_ON_STARTUP` | `true` | Idempotent demo seeding |
| `READY_ROOM_CALENDAR_PROVIDER` | `none` | Calendar adapter: `caldav` or `none` (off) |
| `READY_ROOM_CALDAV_URL` | `http://radicale:5232` | CalDAV base URL |
| `READY_ROOM_CALDAV_USERNAME` | `maverick` | CalDAV username |
| `READY_ROOM_CALDAV_PASSWORD` | `readyroom` | CalDAV password |
| `READY_ROOM_CALDAV_CALENDAR` | `detachment` | Default calendar collection |
| `READY_ROOM_EMAIL_PROVIDER` | `none` | Mailbox adapter: `imap` or `none` (off) |
| `READY_ROOM_IMAP_HOST` | `greenmail` | IMAP host |
| `READY_ROOM_IMAP_PORT` | `3143` | IMAP port |
| `READY_ROOM_IMAP_USERNAME` | `maverick@detachment.demo` | **Full** mailbox address (see note) |
| `READY_ROOM_IMAP_PASSWORD` | `readyroom` | IMAP password |
| `READY_ROOM_IMAP_MAILBOX` | `INBOX` | Mailbox to read |
| `READY_ROOM_SMTP_HOST` | `greenmail` | SMTP host (seeding/helper only) |
| `READY_ROOM_SMTP_PORT` | `3025` | SMTP port |

Frontend dev server proxies `/api` to the backend (see `frontend/vite.config.ts`).

---

## Optional integrations (calendar + mailbox)

The base stack above is fully self-contained. Two **optional** integrations add
a Calendar view and a Mailbox view. They are off by default and degrade
gracefully — if the servers are down or disabled, the views report
"unavailable" and the rest of READY ROOM is unaffected.

Start the optional servers (a self-hosted CalDAV calendar, [Radicale], and a
demo mail server, [GreenMail]) with the `integrations` profile:

```bash
READY_ROOM_CALENDAR_PROVIDER=caldav READY_ROOM_EMAIL_PROVIDER=imap \
  docker compose --profile integrations up --build
```

Then open <http://localhost:8080> and use the **Calendar** and **Mailbox** tabs.
The backend seeds both with synthetic demo data (best-effort, non-blocking, and
idempotent), so restarting never duplicates it.

- **Calendar** — READY ROOM keeps its own cache of events. `Sync` pulls from the
  provider; the dashboard and Calendar view read only the cache. An event can be
  **captured into a responsibility** with one click.
- **Mailbox** — read-only by design: list, read, and capture a message into a
  responsibility. There is no send/move/delete path. A captured message is
  marked so it cannot silently spawn duplicates.

Direct service ports (only needed for debugging): Radicale `http://localhost:5232`,
GreenMail SMTP `localhost:3025` / IMAP `localhost:3143`.

> **Note on the mailbox address:** the IMAP username must be the **full**
> address (`maverick@detachment.demo`). GreenMail creates a *different* mailbox
> for the bare local part, so using `maverick` alone would appear empty.

[Radicale]: https://radicale.org/
[GreenMail]: https://greenmail-mail-test.github.io/greenmail/

---

## API summary

Base path: `/api`. Interactive docs at `/api/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + adapter/provider info |
| GET | `/api/me` | Resolved principal |
| GET | `/api/dashboard` | Operational scan: counts + Today/Watch/Horizon |
| GET | `/api/briefing` | Daily briefing from persisted data |
| GET | `/api/tasks` | List tasks (`?status=open\|completed\|all`, `?category=`, `?search=`) |
| POST | `/api/tasks` | Create task |
| GET | `/api/tasks/{id}` | Task detail |
| PATCH | `/api/tasks/{id}` | Update task (including recurrence) |
| POST | `/api/tasks/{id}/complete` | Complete (idempotent; generates successor) |
| POST | `/api/tasks/{id}/reopen` | Reopen |
| DELETE | `/api/tasks/{id}` | Delete |
| GET | `/api/recurrence` | Recurrence-rule overview + upcoming |
| POST | `/api/recurrence/preview` | Preview upcoming occurrence dates |
| GET | `/api/settings` | Read settings + categories |
| PATCH | `/api/settings` | Update warning window / timezone |
| GET | `/api/timezones` | Curated IANA timezone list (includes the current zone) |
| GET | `/api/categories` | List categories |
| POST | `/api/categories` | Create category (normalised, duplicate -> 409) |
| PATCH | `/api/categories/{id}` | Rename / activate / deactivate |
| DELETE | `/api/categories/{id}` | Delete category |
| POST | `/api/demo/reset` | Clear data, restore defaults |
| GET | `/api/calendar/status` | Calendar provider availability |
| GET | `/api/calendar/agenda` | Cached events for the agenda window |
| POST | `/api/calendar/sync` | Pull events from the provider (best-effort) |
| POST | `/api/calendar/events` | Create an event on the provider + cache |
| DELETE | `/api/calendar/events/{id}` | Delete a cached/provider event |
| POST | `/api/calendar/events/{id}/tasks` | Capture an event into a responsibility |
| GET | `/api/mail/status` | Mailbox provider availability |
| GET | `/api/mail/messages` | List mailbox messages (read-only) |
| GET | `/api/mail/messages/{id}` | Read one message |
| POST | `/api/mail/messages/{id}/tasks` | Capture a message into a responsibility |

`TaskRead` includes **computed** fields -- `urgency`, `days_until_due`, and an
embedded recurrence summary -- which are derived on read and never persisted.

**Status sentinel:** `?status=all` returns both open and completed tasks; the
default is `open`.

---

## Tests, lint, and type checks

Backend (from `backend/`, with a virtualenv):

```bash
python -m pytest                 # unit + integration + architecture
ruff check .
mypy app
```

Run the same persistence/service suite against PostgreSQL (optional; needs a
reachable PostgreSQL):

```bash
READY_ROOM_TEST_DATABASE_URL='postgresql+psycopg://readyroom:readyroom@localhost:55432/readyroom' \
  python -m pytest
```

Frontend (from `frontend/`):

```bash
npm install
npm run test:run     # Vitest + React Testing Library
npm run typecheck    # tsc --noEmit
npm run build        # production build
```

---

## Known limitations & future extension seams

- **No login / no production security.** The single-user identity provider is a
  demo adapter; a real provider attaches as a new `AuthProvider` adapter.
- **Single operator only.** Multi-user collaboration, delegation, and tenancy
  are intentionally out of scope for the first cut. The ownership model
  (`owner_id` on every user-owned entity) is already in place so a future
  multi-user implementation does not require a schema redesign.
- **No notifications, AI extraction, mobile apps, cloud deployment, real-time
  sync, or server-side PDF.** Printing uses the browser's print dialog with a
  dedicated print stylesheet.
- **Optional calendar/mailbox integrations are off by default.** They are
  read-oriented (the mailbox is read-only; the calendar keeps a local cache) and
  selected through a provider registry. They require the `integrations` Compose
  profile and are not part of the base stack.
- **PostgreSQL** is supported by configuration and covered by the shared test
  suite; it is deliberately *not* part of the default Compose stack.
- **Schema evolution** is additive and idempotent inside the SQLAlchemy adapter;
  Alembic is deferred until schema complexity justifies it.

---

## Documentation

- `DECISIONS.md` -- contemporaneous engineering journal (decisions, alternatives,
  trade-offs, and whether each item is a customer requirement, interpretation,
  assumption, or engineering decision).
- `PREBRIEF.md` -- draft one-pager for the customer meeting; **human-owned**,
  flagged for review.
- `AGENTS.md` -- durable repository invariants and gotchas.
- `BUILD_STATUS.md` -- milestone tracker with verification evidence.
