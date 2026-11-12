# Engineering Decisions — READY ROOM

This is a running engineering journal for the READY ROOM first cut. Entries are
appended as decisions are made. Each entry is tagged with its category:

- **[CR]** Customer-stated requirement — supported by the discovery notes/assignment.
- **[PI]** Product interpretation — a design derived from the customer's pain.
- **[ED]** Engineering decision — a technical choice implementing the product.
- **[AV]** Assumption to validate — to be tested with Maverick at the demo.

> Note on timestamps: the local machine clock is the source for these entries.
> Entries marked *(retrospective)* were written after the fact to describe work
> already completed in the same session; no historical activity is fabricated.

---

## D-001 — Product interpretation: the dashboard is the product (2026-11-11)

- **Category:** PI / CR
- **Context:** Maverick spreads responsibilities across sticky notes, email
  flags, a whiteboard, and memory. He explicitly dislikes a list of hundreds of
  tasks and describes the desired experience as scanning aircraft instruments:
  what is now, what is next, what might sneak up.
- **Options:** (a) A conventional task list with a dashboard as a secondary tab;
  (b) a dashboard-first operational scan with the full inventory demoted to a
  secondary view.
- **Decision:** Dashboard-first. The default view answers *what needs me now /
  what is on the horizon / what might sneak up*. The complete inventory is a
  separate, secondary view.
- **Reasoning:** The customer's stated pain is the *feeling of being behind the
  jet*. A long list reproduces the problem. Progressive disclosure of relevance
  is the product.
- **Consequences:** The backend must derive urgency and aggregate a scan rather
  than exposing a flat list as the primary contract.

## D-002 — Technology stack (2026-11-11)

- **Category:** ED
- **Context:** The assignment fixes a stack; the spec says to use it unless a
  documented constraint requires otherwise.
- **Decision:** React 18 + TypeScript + Vite (hand-written CSS), FastAPI +
  Pydantic v2 + SQLAlchemy 2.0 + SQLite, Pytest/Vitest, Docker Compose at repo
  root, one-command startup, browser at `http://localhost:8080`.
- **Reasoning:** Matches the assignment and keeps the demo dependency-free at
  runtime (no cloud, no broker, no external identity provider).
- **Consequences:** The frontend is served by nginx which also reverse-proxies
  `/api/*` to FastAPI; Vite proxies `/api` during local development.

## D-003 — Domain model and recurrence chain (2026-11-11)

- **Category:** ED
- **Context:** Recurring responsibilities (Monday brief, Friday roll-up,
  quarterly currency paperwork) must preserve history and avoid manual re-entry.
- **Options:** (a) A separate `TaskOccurrence` table; (b) a chain of ordinary
  `Task` rows sharing a `series_id` with a `recurrence_rule_id` and
  `occurrence_number`.
- **Decision:** Option (b). A recurring series is a chain of ordinary tasks.
  Completing an occurrence preserves it and generates exactly one successor.
- **Reasoning:** Keeps the aggregate small, makes the completed history first
  class, and avoids a second entity to keep consistent.
- **Consequences:** Successor generation must be guarded against duplicates and
  run in the same transaction as completion.

## D-004 — Urgency is derived, never stored (2026-11-11)

- **Category:** CR / ED
- **Context:** Urgency (overdue/due/watch/horizon) changes as time passes.
- **Decision:** Urgency is computed on read from `status`, `due_date`, the
  operator's local `today`, and the configurable warning window. It is not a
  persisted or editable field.
- **Reasoning:** A stored urgency would go stale and could not react to a
  changed warning window or timezone.
- **Consequences:** The domain owns one pure `compute_urgency`; the frontend only
  maps the derived state to labels/icons/styles.

## D-005 — Timezone and time strategy (2026-11-11)

- **Category:** ED
- **Context:** The operator's "today" can differ from UTC; a UTC timestamp near
  midnight may belong to the previous local date.
- **Decision:** Persist datetimes as *naive UTC*; due dates are plain dates;
  resolve `today` via the operator's effective timezone; use an injectable clock
  port for determinism.
- **Reasoning:** Avoids comparing a date with a datetime and avoids the UTC
  rollover bug. `zoneinfo` requires the `tzdata` package, which is pinned and
  installed in the image.
- **Consequences:** Every date-sensitive use case resolves `today` from the
  clock + settings timezone, never from `datetime.now()` inline.

## D-006 — Persistence behind a unit-of-work port (2026-11-11)

- **Category:** ED
- **Context:** SQLite is the default, but PostgreSQL must be supportable without
  domain/application changes.
- **Decision:** Define `DatabasePort` (unit of work exposing repositories and
  owning commit/rollback) and a `DatabaseFactoryPort`. The SQLAlchemy adapter is
  the first implementation; the adapter is the only module that imports
  SQLAlchemy.
- **Reasoning:** Keeps infrastructure replaceable and the domain pure.
- **Consequences:** Dialect is chosen from the configured URL. A future adapter
  implements the same ports and is selected in the composition root.

## D-007 — Authentication vs. authorization seams (2026-11-11)

- **Category:** ED
- **Context:** The demo has no login, but the spec requires first-class identity
  and authorization abstractions that a real provider can replace.
- **Decision:** A framework-independent `Principal`, an `AuthProvider` port with
  a `SingleUserAuthProvider` demo adapter, a `Permission` enum, a `Policy`, and
  an `AuthorizationPort` with a policy-based adapter. The principal is resolved
  in exactly one FastAPI dependency and injected into use cases.
- **Reasoning:** Identity ("who is acting") and authorization ("what may they
  do") are separate concerns. A demo shortcut must not erase the identity model.
- **Consequences:** No `if demo_mode` scattered in services. The demo policy
  grants the operator all first-cut permissions through the same code path a
  real policy would use.

## D-008 — Ownership scoping (2026-11-11)

- **Category:** ED / AV
- **Context:** Day one is single-operator, but future squadron collaboration is
  anticipated.
- **Decision:** Every user-owned entity carries `owner_id`; repository methods
  scope reads and writes by owner; services pass the principal's id. Policy
  permission **and** ownership are both enforced.
- **Reasoning:** Avoids a schema redesign when multi-user arrives, and keeps the
  ownership rule testable now.
- **Consequences:** In single-user mode filtering is trivially satisfied, but it
  is present and exercised by tests.

## D-009 — Schema evolution without Alembic (2026-11-11)

- **Category:** ED
- **Context:** The first cut needs automatic schema initialization and safe
  additive evolution, without over-engineering.
- **Options:** (a) Adopt Alembic now; (b) `create_all` plus a small idempotent
  additive-column helper inside the adapter.
- **Decision:** Option (b) for the first cut; record the trade-off.
- **Reasoning:** The schema is small and greenfield; Alembic adds ceremony
  without benefit at this size. A later Alembic adoption stays inside the
  persistence adapter and preserves the same ports.
- **Consequences:** The additive helper must be idempotent and never destroy
  data. Documented in README.

## D-010 — Bounded no-backfill recurrence policy (2026-11-11)

- **Category:** PI / ED
- **Context:** If the app is not run for a while, a recurring rule could generate
  a large backlog of missed occurrences.
- **Decision:** Never backfill. `plan_next` fast-forwards over missed dates in a
  bounded loop (limit 5000), returns the first occurrence on/after `today`, and
  reports how many it skipped so `occurrences_generated` stays truthful. A rule
  anchored far in the past returns a `bounded` flag rather than looping forever.
- **Reasoning:** Backfilling would flood the dashboard — the opposite of the
  customer's goal. A bound guarantees termination.
- **Consequences:** Tested explicitly, including the bound case.

## D-011 — Seeding and demo reset (2026-11-11)

- **Category:** ED / AV
- **Context:** The demo must initialize automatically and idempotently, and must
  reset to a known state.
- **Decision:** Seed once using a `seed_version` marker and a guard that skips
  seeding if application tasks already exist. `POST /api/demo/reset` clears
  task/recurrence/demo state and restores default categories/settings. A volume
  wipe is documented as a last-resort reset.
- **Reasoning:** Restarting containers must never duplicate demo data; the
  customer needs a reliable way back to a clean demonstration.
- **Consequences:** Seed data uses synthetic Navy-aviation-flavoured names only;
  due dates are anchored relative to the current date.

## D-012 — Categories are assumptions, not requirements (2026-11-11)

- **Category:** AV
- **Context:** The initial category list (Flight Administration, Maintenance,
  Detachment Operations, Personnel, Logistics, General) is a reasonable guess.
- **Decision:** Ship them as defaults but make them operator-editable and
  persisted. Normalize input and reject duplicates case-insensitively.
- **Reasoning:** The customer never confirmed these categories; they must be
  cheap to change and clearly labelled as assumptions.
- **Consequences:** Listed in PREBRIEF as an item to validate with Maverick.

## D-013 — No-notification design (2026-11-11)

- **Category:** CR / PI
- **Context:** Maverick dislikes notifications but does not want important work
  to become invisible.
- **Decision:** No push/SMS/email/popup notifications. Urgency is surfaced as
  visual signals on the dashboard ("quiet urgency").
- **Reasoning:** Directly follows the customer's stated preference.
- **Consequences:** Visual signals must never rely on colour alone (label + icon
  accompany every urgency state).

## D-014 — Testing strategy (2026-11-11)

- **Category:** ED
- **Context:** The spec prefers real code paths over mocks.
- **Decision:** Pure domain unit tests (no DB), real temporary-SQLite integration
  tests for ports/services, FastAPI integration tests through real adapters,
  architecture/import-boundary tests, and frontend Vitest/RTL tests. Mocks only
  at boundaries that cannot otherwise be exercised.
- **Reasoning:** Real adapters catch mapping/transaction bugs that mocks hide.
- **Consequences:** The same persistence/service suite is parameterised to run
  against SQLite and (when available) PostgreSQL.

## D-015 — AI suggestions accepted / modified / rejected (2026-11-11)

- **Category:** ED
- **Accepted:** The chain-of-tasks recurrence model, the derived-urgency rule
  table, the unit-of-work port, and the permission-based authorization seam.
- **Modified:** An initial suggestion to store a materialised `urgency` column
  was rejected in favour of on-read derivation (see D-004). An initial
  `TaskOccurrence` table suggestion was rejected (see D-003).
- **Rejected:** Suggestions to add email/calendar ingestion, AI task extraction,
  and browser notifications — all explicitly out of scope for the first cut.
- **Reasoning:** These additions would expand scope beyond the customer's stated
  first-cut needs and violate the "smallest complete product" principle.

## D-016 — Frontend server-state boundary (2026-11-11)

- **Category:** ED
- **Context:** The spec forbids a large state-management dependency and requires
  one well-defined hook/service boundary for server state.
- **Decision:** A single hand-written `useAppData` hook owns all shared server
  state (dashboard, briefing, tasks, settings, categories, recurrence,
  principal); a thin typed `apiClient` is the only module that calls `fetch`.
  Components never call the API directly for shared state. Mutations go through
  a `mutate()` helper that re-derives all server state afterwards.
- **Alternatives:** Redux/Zustand/React Query — rejected as unnecessary weight
  for a single-operator SPA.
- **Consequences:** One place to reason about loading/error/refresh; urgency and
  counts stay consistent because they are always re-derived by the backend.

## D-017 — Frontend does not reimplement urgency/recurrence rules (2026-11-11)

- **Category:** ED
- **Context:** The backend is authoritative for urgency and recurrence.
- **Decision:** Frontend `lib/urgency.ts` and `lib/recurrence.ts` only map
  server-derived values to labels, glyphs, tones, and wording. No arithmetic.
- **Reasoning:** Prevents rule drift between the two layers; the architecture
  test suite asserts the frontend does not own these rules.
- **Consequences:** A new urgency state or cadence requires only a label mapping
  on the client; the source of truth stays on the server.

## D-018 — Docker runtime and health gating (2026-11-11)

- **Category:** ED
- **Context:** The hard acceptance command is `docker compose up --build` at
  repo root, serving the SPA at http://localhost:8080.
- **Decision:** Two containers. Backend (python:3.12-slim + uvicorn) exposes
  `/api/health` and writes SQLite to a named volume `ready_room_data` mounted at
  `/data`. Frontend (multi-stage node build → nginx:1.27-alpine) serves the SPA
  and reverse-proxies `/api/*` to `backend:8000`. The frontend `depends_on` the
  backend with `condition: service_healthy`, so it waits for backend *health*,
  not mere process start.
- **Reasoning:** Keeps the browser on a single origin (no CORS in prod), matches
  the spec's nginx reverse-proxy requirement, and makes persistence explicit.
- **Consequences:** `tzdata` is installed in the backend image so timezone
  resolution works. nginx listens on IPv4 and IPv6; the frontend health check
  targets `127.0.0.1` (via `/healthz`), not `localhost`.

## D-019 — Demo reset semantics (2026-11-11)

- **Category:** ED
- **Context:** The spec requires reset to "clear application data and restore
  the default category list and seed state".
- **Decision:** `POST /api/demo/reset` clears tasks, recurrence rules, cached
  integration data, and categories, restores default categories/settings, and
  then **immediately reseeds** the synthetic demonstration scenario. The reset
  returns the operator to the *intended demonstration state* the moment the
  request returns; the board is repopulated, not left blank.
- **Alternatives:** (a) Zero the seed marker and let the idempotent seeder
  repopulate on the next container startup — this was the original D-019
  choice, but it left the dashboard visibly empty until a restart, which reads
  as data loss to the operator and contradicts "restore the seed state" (§3.8).
  Rejected. (b) Reseed inside the same clear transaction — rejected so a seed
  failure still leaves a clean, empty state rather than a half-cleared one; the
  two steps stay independent (clear+commit, then seed).
- **Consequences:** Reset is now self-contained and idempotent (repeatable
  without accumulation). The seed marker is still zeroed so startup seeding
  remains a no-op when data exists. Documented in README; a volume wipe remains
  the last-resort full reset. (Supersedes the original D-019 decision.)

## D-020 — Retrospective note on milestone tracking (2026-11-11)

- **Category:** ED
- **Context:** Backend work completed across earlier sessions; frontend and
  Docker completed in this session.
- **Decision:** BUILD_STATUS.md records each milestone's gate command and the
  observed result. Entries added after the fact are marked in this journal
  rather than back-dated.
- **Reasoning:** The spec forbids fabricating historical timestamps; all
  recorded dates are the actual date of execution.

## D-021 — Fix: quick capture "Not Found" in local dev (2026-11-11)

- **Category:** ED (bug fix)
- **Context:** Quick capture reported a **"Not Found"** error when the SPA was
  run with the Vite dev server, while the containerized app at
  `http://localhost:8080` worked. Reproduction: `npm run dev` → `POST /api/tasks`
  returned `{"detail":"Not Found"}` (404) for *every* `/api/*` path, including
  `GET /api/me` and `GET /api/dashboard`.
- **Root cause:** `vite.config.ts` proxied `/api` to `http://localhost:8000` by
  default. In this development environment port 8000 was occupied by an
  unrelated service that answers `/api/*` with a generic `{"detail":"Not Found"}`.
  The proxy forwarded faithfully; the dev server's own origin returned a JSON
  "Not Found" for all API calls, so the SPA surfaced a "Not Found" error on
  capture. This is a *development-environment* misconfiguration, not a defect in
  the capture endpoint (verified: the same POST returns `201` through the
  containerized nginx origin and through the dev proxy when pointed at a real
  backend).
- **Decision:** (1) Read the proxy target via `loadEnv` so a checked-in
  `frontend/.env` (or `VITE_API_PROXY_TARGET` in the environment) selects the
  backend, keeping the `http://localhost:8000` default for a directly-run
  `uvicorn`. (2) Apply the same proxy to `vite preview`, which otherwise serves
  the production build with no `/api` proxy and reproduces the identical
  "Not Found". (3) Add `frontend/.env.example` documenting the override and the
  nginx-origin alternative. (4) Document the failure mode in the README
  "Local development" section.
- **Alternatives:** Change the default to `http://localhost:8080` — rejected: it
  would break the common `uvicorn --port 8000` workflow and couple the frontend
  default to the Compose port mapping. Add CORS + call the backend directly from
  the browser — rejected: the spec keeps the browser same-origin behind a proxy.
- **Consequences:** Dev capture works once the proxy target is a running backend.
  The default remains correct for the documented `uvicorn` workflow; Compose users
  either publish the backend port or set `VITE_API_PROXY_TARGET` to the nginx
  origin. No application code changed.

## D-022 — Configurable timezone drop-down (2026-11-11)

- **Category:** ED
- **Context:** Settings exposed the operator timezone as a free-text field, which
  invited typos that the backend then rejected (400).
- **Decision:** Add `GET /api/timezones` returning a curated IANA shortlist
  (`COMMON_TIMEZONES` in `config.py`) plus `default_timezone`, and render a
  `<select>` in Settings. The list always includes the operator's current zone
  (even if it is outside the shortlist) so the control never displays a value it
  cannot represent; the backend still accepts any valid IANA identifier.
- **Alternatives:** Ship the full `zoneinfo.available_timezones()` (~600 entries)
  — rejected as noisy for a single-operator demo. Keep free text — rejected as
  error-prone.
- **Consequences:** `TimezonesResponse` added to the response schemas; two
  integration tests cover the shortlist and the outside-shortlist case. No domain
  or application change.

## D-023 — Overdue/due-today card shading (2026-11-11)

- **Category:** PI
- **Context:** The dashboard's visual convention calls for "red: overdue, amber:
  approaching" while never relying on colour alone. Task cards previously carried
  only a coloured left border; overdue and due-today were easy to miss in a scan.
- **Decision:** Add a subtle left-to-right background gradient to `.urgency-overdue`
  and `.urgency-due` cards, plus a green left border for `.urgency-completed`. The
  existing text label and glyph remain the primary, colour-independent signals.
- **Consequences:** CSS-only; no component or contract change. Respects the print
  stylesheet, which neutralises backgrounds.

## D-024 — Quick capture captures category, due date, and priority (2026-11-11)

- **Category:** PI
- **Context:** Fast capture previously recorded only a title (defaulting the
  category server-side). Maverick's core need is to capture a responsibility
  *before it is forgotten* with enough context to be useful later.
- **Decision:** Extend `QuickCapture` to a title plus three compact, pre-defaulted
  controls — category (first configured category), due date (local today), and
  priority (normal) — while keeping one-click capture. The full dialog remains the
  path for notes and recurrence. The component now receives the category list and
  submits a `TaskCreateInput`.
- **Alternatives:** Keep title-only and force a second edit pass — rejected: adds
  friction and defeats "fast capture".
- **Consequences:** `App.tsx` passes active categories and forwards the full input;
  QuickCapture tests updated (5 passing). The backend already accepted these fields.

---

## Integration block (D-025 – D-033) — email + calendar (2026-11-12)

> These entries record the email/calendar integration work. They are written on
> the day the code was completed. The module docstrings reference these numbers;
> the earlier integration code had reused numbers already taken by D-020 – D-024,
> so the references and these entries were renumbered together into a fresh,
> non-colliding block.

## D-025 — Calendar integration behind a cache and a zero-dependency CalDAV adapter (2026-11-12)

- **Category:** PI / ED
- **Context:** Maverick wants to see what is coming without another silo, and the
  brief explicitly lists calendar awareness. READY ROOM must stay usable when the
  calendar server is slow, misconfigured, or down.
- **Decision:** Keep READY ROOM's **own cache** of provider events
  (`calendar_events` table, `CalendarEventRecord`). The dashboard and Calendar
  view read only the cache; a single explicit `POST /calendar/sync` is the only
  read path that talks to the provider, and it is best-effort — an unreachable
  provider surfaces as an `available: false` status, never a failed request. The
  CalDAV adapter drives `PROPFIND`/`REPORT`/`MKCOL`/`PUT`/`DELETE` with the
  standard library (`urllib` + `xml.etree`), so the runtime gains **zero** new
  dependencies; iCalendar parse/serialize is shared with every future adapter via
  `calendar.domain`.
- **Alternatives:** Call the provider live on every dashboard load — rejected:
  couples page latency to an external server and breaks the "app works offline"
  property. Add a CalDAV client library — rejected: an avoidable dependency for
  the handful of verbs needed.
- **Consequences:** `CalendarProvider` is a port; the CalDAV adapter is one
  implementation selected by `READY_ROOM_CALENDAR_PROVIDER`. A Google/Microsoft
  adapter is added in the registry without touching domain, services, API, or UI.

## D-026 — Mailbox is read-only; capture writes one provenance row (2026-11-12)

- **Category:** PI / ED
- **Context:** "New work arrives through email … and must be captured before it is
  forgotten." That is an *inbound* concern. Sending, moving, or deleting mail is
  out of scope and would imply mailbox ownership READY ROOM does not have.
- **Decision:** The mailbox integration is deliberately **read-only**: the API
  exposes list/read/status and a single capture action, and there is no
  send/move/delete endpoint. Capturing a message writes one `EmailSource`
  provenance row (message id, sender, subject, received time, task id). The row is
  what lets the UI mark a message "already captured" so it cannot silently spawn
  duplicates; recapturing **reuses the single row** and re-points it at the newest
  task rather than inserting a second.
- **Alternatives:** Mark messages read/moved on capture — rejected: mutates the
  operator's mailbox, which is not ours to change. Store provenance on the task
  only — rejected: "was this captured?" would then need a scan and could not be
  enforced as a single-row invariant.
- **Consequences:** `EmailSource.message_id` is unique per owner. The UI's
  captured badge is derived from this row, not from a client-side flag.

## D-027 — IMAP adapter shaped by GreenMail realities; SMTP only for seeding (2026-11-12)

- **Category:** ED
- **Context:** The demo mailbox is a self-hosted GreenMail. Two behaviours had to
  be accommodated, and the capture path looks a message up by its identifier.
- **Decision:** All `imaplib` usage lives in the IMAP adapter and is read-only
  (`SELECT`/`SEARCH`/`FETCH`), using `BODY.PEEK` so listing never marks a message
  read. (1) The mailbox is addressed by its **full** address
  (`maverick@detachment.demo`), not the local part — logging in as the local part
  creates a *different* mailbox. (2) A message is looked up by
  `HEADER Message-ID`, with a `seq-N` sequence-number fallback for messages that
  genuinely lack a `Message-ID`. A separate `MailSender` port (SMTP adapter) exists
  **only** for the seeder and demo helper; it always sets an explicit `Message-ID`
  because a seeded message without one could not be found by the capture path. The
  application request path never sends mail.
- **Alternatives:** Parse the local part off the configured username — rejected:
  silently targets the wrong mailbox on GreenMail. Require `Message-ID` — rejected:
  would make some real messages uncapturable.
- **Consequences:** `MailSender` is not part of the read-only `MailboxProvider`
  port; the two are intentionally distinct.

## D-028 — Integration seeding is separate, best-effort, and non-blocking (2026-11-12)

- **Category:** ED
- **Context:** The calendar and mail containers may still be booting when the API
  becomes ready. Blocking startup on them would delay or break the app; running
  them inline would make startup flaky.
- **Decision:** Keep the integration seeders (`IntegrationSeedService`) separate
  from the core task seed (`DemoService`). On startup the lifespan schedules each
  integration seed as an `asyncio.to_thread` task — **non-blocking** — and each
  seeder is best-effort: it retries a few times, logs on failure, and never raises.
  Each integration has its **own** marker column (`calendar_seed_version`,
  `email_seed_version`) beside the core `seed_version`, so the integrations can be
  seeded or skipped independently and never duplicate data across restarts.
- **Alternatives:** Seed synchronously during startup — rejected: couples API
  readiness to auxiliary containers. One combined marker — rejected: could not
  re-seed one integration after only the other was cleared.
- **Consequences:** `demo reset` clears all three markers, so a reset re-seeds the
  full demonstration scenario on the next startup.

## D-029 — Calendar wall-clock fidelity: naive UTC plus an IANA zone (2026-11-12)

- **Category:** ED
- **Context:** A naive datetime handed to a provider is treated as UTC, which would
  shift a "07:30 local" event to 00:30 local when read back — an unacceptable error
  for a flight-quarters brief.
- **Decision:** Store each cached event's `start`/`end` as **naive UTC** alongside
  the IANA `timezone` it is anchored to. The seed builds events with **aware** local
  datetimes (`ZoneInfo(operator_tz)`) so the intended wall-clock time survives the
  round trip. This mirrors the app-wide rule: persist naive UTC, resolve local time
  through the operator's zone.
- **Alternatives:** Store aware datetimes — rejected: inconsistent with the rest of
  the schema and the "naive UTC" invariant. Store local wall-clock with no zone —
  rejected: loses the DST anchor.
- **Consequences:** An all-day event keeps its date; a timed event keeps its local
  clock time. Covered by calendar domain and service tests.

## D-030 — Capture a calendar event into a responsibility (2026-11-12)

- **Category:** PI / ED
- **Context:** Seeing an event is not the same as owning a responsibility for it.
  Maverick should be able to turn "tow bar inspection window" into a tracked task.
- **Decision:** `POST /calendar/events/{id}/tasks` captures a cached event into a
  task and sets `calendar_events.task_id` to link them. Capture is **idempotent**:
  an already-linked event returns its existing task instead of creating a second.
  The link lives on the cache row, so the Calendar view can show "captured".
- **Alternatives:** Copy the event with no back-link — rejected: the UI could not
  show provenance and re-capturing would duplicate. A separate link table —
  rejected: one nullable column is sufficient for this cut.
- **Consequences:** `task_id` is a nullable FK-like column on `calendar_events`;
  see D-031 for how it reaches an existing volume.

## D-031 — Additive schema evolution for the new integration tables/columns (2026-11-12)

- **Category:** ED
- **Context:** `create_all` only creates missing **tables**, never alters an
  existing one. A database on a persistent volume from before the integration
  feature would lack `calendar_events.task_id` and the two seed-marker columns, and
  capture (or seeding) would fail.
- **Decision:** Extend the existing idempotent additive-migration helper inside the
  SQLAlchemy adapter to add the missing columns portably (`ALTER TABLE … ADD COLUMN`),
  including `calendar_events.task_id`, `operator_settings.calendar_seed_version`,
  and `operator_settings.email_seed_version`. Still **no Alembic** at this size
  (see D-009); the helper only adds, never drops or rewrites, and is safe to re-run.
- **Alternatives:** Adopt Alembic now — rejected: disproportionate for three
  additive columns; the trade-off remains recorded in D-009. Require a volume wipe —
  rejected: destroys user data for an additive change.
- **Consequences:** Existing volumes upgrade in place. A later Alembic migration
  would live in the same adapter and preserve the same ports.

## D-032 — Event identity and cache key (2026-11-12)

- **Category:** ED
- **Context:** Sync must update events, not duplicate them; a locally created event
  must not be deleted-and-reinserted by the next sync, which would silently drop
  its capture link.
- **Decision:** Identify a cached event by `(owner_id, uid, calendar_id)` — the
  `uid` is the provider's stable event identifier and `calendar_id` the collection
  it lives in; `href` and `sequence` are carried for provider bookkeeping. A locally
  created event is cached under the provider's **canonical** calendar id (resolved
  through the port, not the user's typed label) so a later sync finds and updates
  the same row. A unique index enforces the key.
- **Alternatives:** Key on `href` — rejected: `href` is not stable across some
  providers and is absent for local creates. Key on summary+start — rejected:
  collides for legitimate repeats.
- **Consequences:** The unique index `ix_calendar_owner_uid` makes duplicate cache
  rows impossible; the agenda returns events by keying on the same identity.

## D-033 — Mailbox provider is selected by a registry, like calendar (2026-11-12)

- **Category:** ED
- **Context:** A future mailbox backend (Graph, Gmail API, JMAP) should attach the
  same way a calendar backend does, with no changes to domain, services, API, or UI.
- **Decision:** Add `mailbox/providers/registry.py` mirroring the calendar
  registry: `build_mailbox_provider(settings)` returns the configured
  `MailboxProvider` (currently `imap`) or `None` when disabled, and rejects an
  unknown provider name as a configuration error. Disabled simply means the Mailbox
  view reports "unavailable" and the rest of READY ROOM is unaffected.
- **Alternatives:** Instantiate the IMAP provider directly in composition —
  rejected: would spread provider selection across the codebase and break the
  "select adapters in one place" rule.
- **Consequences:** `READY_ROOM_EMAIL_PROVIDER=imap|none` selects the adapter; a new
  provider is one branch here plus its adapter module.

## D-034 — CalDAV/IMAP adapter hardening found by live-container probing (2026-11-12)

- **Category:** ED
- **Context:** The integration adapters passed the in-memory test doubles but
  failed against real containers. Probing a live Radicale (`:5232`) and GreenMail
  (`:3143`) exposed defects the doubles could not: the doubles normalise ids
  idempotently and never emit a `VTIMEZONE`, so they masked real-world behaviour.
- **Decisions / fixes:**
  1. **iCalendar parsing is scoped to the `VEVENT` block.** A `VCALENDAR` may carry
     a `VTIMEZONE` whose own `DTSTART` lines describe historical transitions;
     scanning the whole payload let `DTSTART:20001029T020000` win over the event's
     real start. `parse_calendar` now extracts the first `VEVENT` first
     (regression test `test_parse_ignores_vtimezone_dtstart`).
  2. **A canonical calendar id is an absolute URL and must never be re-prefixed.**
     `resolve_calendar_id` was prepending the principal home to an already-absolute
     id, yielding `/maverick/http://radicale:5232/maverick/detachment/` → `403`.
     It now returns an absolute id unchanged (unit tests in
     `tests/unit/adapters/test_caldav_urls.py`). This bug was invisible to the
     in-memory provider because its `resolve_calendar_id` is idempotent.
  3. **`list_calendars` searches the principal home, not just the root.** Radicale
     exposes calendars at `/<user>/<calendar>/`; a root-level `PROPFIND` depth 1
     returns only the principal, so the list was empty.
  4. **The mailbox seed reconciles against the mailbox, not just a DB marker.**
     GreenMail keeps mail in memory; after a partial restart (persistent DB, fresh
     mail container) the `email_seed_version` marker said "seeded" while the
     mailbox was empty. The seeder now reseeds when the marker is set but the
     mailbox is empty (test `test_mailbox_seed_repairs_after_mail_server_restart`).
- **Consequences:** Both integrations now work end to end against real containers
  through the nginx origin. The in-memory doubles remain (they are genuine second
  adapters), but the new adapter unit tests pin the URL/parse shapes the doubles
  cannot. Lesson recorded in `AGENTS.md`: exercise a new adapter against its real
  protocol, not only against a double.

## D-035 — Demo reset also restores the optional integrations (2026-11-12)

- **Category:** ED / PI
- **Context:** `DemoService.reset` cleared the calendar cache and zeroed the
  integration seed markers, but never re-ran the integration seeders. Two
  operator-visible defects followed, both reproduced against the live stack:
  1. **Reset left the Calendar view empty.** The cached events were deleted and
     the cache was only refilled by an explicit `POST /calendar/sync`, so the
     operator had to know to sync after a reset.
  2. **Reset + restart duplicated mail.** Reset zeroed `email_seed_version`
     while GreenMail (in-memory) still held the three demo messages; the next
     backend start saw a zero marker and re-sent them — 3 → 6 messages.
- **Decision:** Make reset restore the *whole* demo state, not just tasks.
  1. `DemoService.reset` now calls a best-effort `_reseed_integrations` after the
     core reseed: it re-runs `seed_calendar_if_needed`/`seed_mailbox_if_needed`
     and then `CalendarService.sync_quietly`, so the Calendar view is populated
     the moment the reset returns. It never raises, so the base stack (no
     providers) is unaffected.
  2. The mailbox seeder is now **idempotent on the demo messages' own
     `Message-ID`s**, not only on the marker. It lists the mailbox, sends only the
     messages that are missing, and treats an unreachable mailbox as "cannot
     tell" (fall back to the marker) rather than "empty" — so a transient error
     can never duplicate mail, and a reset can never re-send mail that is still
     present.
- **Alternatives:** (a) Have reset leave integrations alone and document a manual
  sync — rejected: reset is advertised as "return to the demonstration state",
  and an empty Calendar reads as a bug. (b) Delete the demo messages from
  GreenMail before reseeding — rejected: the mailbox port is deliberately
  read-only (no delete verb, D-026); reconciliation by `Message-ID` achieves
  idempotency without widening the port.
- **Consequences:** `POST /api/demo/reset` now restores tasks, calendar, and mail
  together, and is safe to run repeatedly and across restarts. `DemoService`
  gains two optional, injectable collaborators (`integration_seed`, `calendar`),
  wired only in `composition.py`; the application layer still imports no adapter.
  Integration-seed tests cover the calendar reseed+refresh, the mailbox reseed,
  the no-duplicate-on-reset case, and the base stack with no integrations.
