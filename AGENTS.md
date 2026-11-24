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
- **Occurrences snapshot, the rule evolves** (ADR-007). Each occurrence stores
  its `rule_revision`, `scheduled_date`, due date/instant, assignee snapshot,
  routing position, scope and owner, so a later revision can never reinterpret
  history. Rule revisions and per-occurrence exceptions are append-only tables,
  not extra occurrence rows.
- **"This occurrence" and "this and future" are separate operations.** A series
  edit writes a revision effective from the next ungenerated occurrence and
  changes no existing occurrence; an occurrence edit writes an exception and
  never touches the rule. There is no "edit the past".
- **A duty-position holder change routes open and future occurrences forward**
  and never rewrites closed ones; the accountable owner and the append-only
  assignee history are unchanged. A vacant position falls back to the
  accountable owner and is flagged for the scan.
- **`cancelled` is closed but is not completion.** It leaves active sections like
  a completed task, is excluded from completion metrics, and generates no
  successor.
- **A rule is deactivated, never hard-deleted, while any occurrence references
  it** — completed history keeps its linkage.
- **Overdue tasks never disappear.** Completed tasks never appear in active
  operational sections.
- **A task has four visibility scopes** — `personal`, `shared`, `team`,
  `squadron` — and exactly one **accountable owner** (a human user). A duty
  position is an *assignee kind*, never a fifth task scope (ADR-006).
- **Ownership roles are distinct, not interchangeable** (ADR-006). Accountable
  owner (1, user), assignee (0..1: user/team/duty position), collaborators
  (many, write), watchers (many, read). Shared work never implies every member is
  responsible, and a watcher never gains a mutating verb.
- **Shares are one table with two levels.** `task_shares(task_id, squadron_id,
  user_id, access ∈ {read, write})`: a `write` share *is* a collaborator, a
  `read` share *is* a watcher. A read share never authorizes a write. Do not add
  a second collaborator table — two sources of truth drift from the policy.
- **"No accountable owner" means the owner's membership is not `ACTIVE`**, not a
  null column. Such tasks are surfaced for reassignment and stay reachable by
  `squadron_admin` and the owning team lead; shares held by non-active members
  are inert but retained, and restored on reactivation.
- **A task's visibility is computed once** by a single pure policy that also
  emits the repository filter keys (ADR-006 §8). List paths filter in SQL, never
  post-fetch — post-filtering leaks through counts, pagination, and timing.
  Every read path (scan, briefing, search, notifications, turnover, Jev context)
  uses the same policy.
- **Reassignment clears acknowledgment**; acknowledging never changes status and
  never implies completion. An agent may never acknowledge a task.

## Time

- Persist datetimes as **naive UTC**. Due dates are plain `date`s.
- Resolve `today` from the operator's effective timezone via the clock port —
  never inline `datetime.now()`. Handles UTC rollover (23:30Z is still the prior
  day in America/Denver). The demo default zone is **America/Denver** (MST/MDT).
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
- **Squadron scope is a data-access boundary, not a route-handler check** (ADR-005).
  Every squadron-scoped table carries `squadron_id` **and** keeps `owner_id`
  ("whose record" is not "which tenant"). Indexes lead with `squadron_id`, and
  every repository read takes a `ScopeCriteria` built in one place from the
  resolved principal — never from a request field. Cross-squadron reads return
  `404` (do not confirm existence); an in-squadron scope denial returns `403`.
  Aggregate/summary reads go through scoped repository methods, never ad-hoc SQL.
- **Schema evolution is a versioned, forward-only runner**, not a fixed
  column-add tuple. Migrations are ordered, recorded in `schema_migrations`,
  idempotent, and data-preserving — they never drop or rewrite rows. Tenant
  columns land as expand → backfill → startup guard (fails closed on any null
  tenant key) → contract in a later release. Every step ships with a fixture test
  that asserts row-for-row survival plus idempotency.
- **Repositories must persist every mapped field on update.** `save` copies all
  columns via the single mapper, never a hand-written field list — a hand-written
  list silently drops newly added fields (this broke `demo_arrival_seq`).

## Identity and authorization

- Identity ("who") and authorization ("what may they do") are separate.
- The principal is resolved in **exactly one** FastAPI dependency and injected
  into use cases. Services never construct principals.
- Permission **and** ownership are both enforced; ownership filtering does not
  replace a permission check.
- `SingleUserAuthProvider` is a demo/development identity adapter. There is
  **no** login, session, or token flow, and the demo is **not** production
  security.
- Authorization is **deny-by-default and scope-aware** (ADR-004). Evaluation is
  ordered and short-circuiting: `ACTIVE` membership, then the role permission,
  then the resource scope (`personal`/`shared`/`team`/`squadron`/
  `duty_position`), then resource relationship, then any approval gate. A
  permission is valid only inside its grant's scope ceiling; scope never widens
  a grant.
- Roles are `squadron_admin`, `officer`, `team_lead`, `member`, `read_only`.
  `operator`/`viewer` survive as demo-only aliases in `default_policy()`, and no
  production role grant contains a `demo:*` permission.
- Denial codes are a stable API contract: `forbidden`, `forbidden_membership`,
  `forbidden_scope`, `forbidden_ownership` (personal scope, kept for
  compatibility), `approval_required`.
- A duty position confers only its non-administrative capability set at duty
  scope; it can never confer `*:manage`, `approvals:decide`, `audit:read`,
  delegation, or `demo:*`. Nobody may change their own role or membership, and a
  delegation can never exceed the delegator's permissions or scope.
- Agents hold **no** roles. They act only through explicit, revocable delegation
  and may never perform a human-accountability action (`tasks:acknowledge`,
  `turnover:acknowledge`, `approvals:decide`).

## Seed and reset

- Seeding is guarded by a `seed_version` marker **and** an "any tasks exist?"
  check; restarting containers must never duplicate demo data.
- `POST /api/demo/reset` clears task/recurrence/demo state, restores default
  categories and settings, and **immediately reseeds** the demo scenario so the
  board is repopulated the moment the request returns (never left blank). It
  also **clears the demo providers** (purges the demo mailbox and deletes the
  demo calendar's events) and **restores the integrations** (reseed + calendar
  cache refresh), and **zeroes the `demo_arrival_seq` counter**; the provider
  clear and the reseed are best-effort and never raise. So a reset returns the
  *whole* demo — tasks, calendar, and mailbox — to the baseline, and repeated
  "Simulate arrival" injections do not accumulate across resets (D-040).
  A volume wipe is the last-resort reset.
- The demo providers (GreenMail / Radicale) are **this stack's own disposable
  demo servers**, so resetting them is safe and expected. Clearing happens only
  through `IntegrationSeedService.clear_demo_data`, which goes through the
  provider ports (`MailboxProvider.purge`, `CalendarProvider.delete_event`) —
  never by reaching into a container. A disabled or unreachable provider is
  skipped, not fatal.
- Seed data is **synthetic** (fictional detachment, made-up names). Never use
  real classified, sensitive, or operational military information.

## Integrations (calendar + mailbox)

- Both integrations are **on by default** (`READY_ROOM_CALENDAR_PROVIDER=caldav`,
  `READY_ROOM_EMAIL_PROVIDER=imap`) and start with the base stack. Opt out per
  integration with `*_PROVIDER=none`. A disabled or unreachable provider yields an
  "unavailable" view; it must never break the rest of the app.
- **`POST /api/demo/arrivals` injects a live arrival** — one incoming email (via
  the `MailSender` port) and one calendar event (via `CalendarService`) — to show
  work arriving during a demo. It is best-effort **per channel** and returns a
  per-channel delivered/detail summary; a disabled/unreachable integration is
  reported, never fatal. A monotonic `demo_arrival_seq` on `OperatorSettings`
  keeps successive arrivals distinct (fresh message-id / event-uid). It requires
  the `demo:simulate` permission.
- **Calendar is cache-first.** The app keeps its own `calendar_events` copy; the
  dashboard/Calendar view read only the cache, and `POST /api/calendar/sync` is
  the only read path that talks to the provider. The startup task seeds the
  provider **and** syncs the cache when `calendar_sync_on_startup` is set, so the
  view is populated on first load. Adapter: `CalDavCalendarProvider`
  (stdlib `urllib` + `xml.etree`, zero new dependencies).
- **Mailbox is read-only for the operator.** List/read/capture only — there is
  **no** send, move, or delete path from the mailbox. `MailSender` (SMTP) is used
  only to deliver demo data (seeding, and the `POST /api/demo/arrivals` demo
  action); it never mutates or removes an existing message. The one exception is
  `MailboxProvider.purge()`, which is a **demo-reset-only** capability (used by
  `clear_demo_data`, D-040) and is never reachable from an operator workflow.
- **Capture is idempotent.** An event's `calendar_events.task_id` and a message's
  single `email_sources` row record provenance, so recapturing returns/updates the
  existing link instead of duplicating.
- **Provider selection is registry-only.** `build_calendar_provider` /
  `build_mailbox_provider` are the single place a concrete adapter is chosen. An
  unknown provider name is a configuration error.
- **Seeding is separate and non-blocking.** `IntegrationSeedService` retries a few
  times and logs; each integration has its own idempotency marker
  (`calendar_seed_version`, `email_seed_version`). Never block API readiness on an
  auxiliary container.
- **IMAP gotchas (GreenMail):** address the mailbox by its **full** address
  (`maverick@detachment.demo`), not the local part; look a message up by
  `HEADER Message-ID` with a `seq-N` fallback.
- **iCalendar parsing is scoped to the VEVENT.** A `VTIMEZONE` block carries its
  own `DTSTART` lines; `parse_calendar` must ignore them (regression-tested).
- **CalDAV collection creation:** a calendar is created with `MKCALENDAR` inside
  the principal home (`/‹user›/‹calendar›/`). `409 Conflict` on an existing
  collection is the idempotent "already exists" case, not an error.
- **A canonical calendar id is an absolute URL.** `resolve_calendar_id` returns it
  unchanged; it must never re-prefix the principal home (that yields
  `/maverick/http://host/maverick/cal/` → `403`).
- **The calendar seed reconciles against the provider, not only its marker.** A
  reset or DB wipe clears the marker while the provider (Radicale) still holds the
  demo events; the seeder lists existing events and creates only the missing ones,
  so it never mis-reports a create conflict as "provider unavailable".
- **The mailbox seed reconciles against the mailbox, not only its marker.** GreenMail
  keeps mail in memory; the seeder is idempotent on the demo messages' own
  `Message-ID`s, so it reseeds a lost/empty mailbox and never duplicates mail that
  is still present (a zero marker must not re-send existing messages).
- **Exercise a new adapter against its real protocol, not only a double.** The
  in-memory doubles are genuine second adapters, but they normalise ids
  idempotently and emit no `VTIMEZONE`, which hid three real bugs. Adapter-shape
  regressions belong in `tests/unit/adapters/`.

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

## Branch hygiene

- Merged PR head branches are deleted automatically (`delete_branch_on_merge`).
  Agents must not leave a merged branch on `origin`; if auto-delete misses one,
  delete it explicitly. Never delete an unmerged branch or a branch with an open
  PR.

## Commands

```bash
# backend
cd backend && python -m pytest -q && ruff check app tests && mypy
# frontend
cd frontend && npm test -- --run && npm run build
```
