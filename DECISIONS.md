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
- **Decision:** `POST /api/demo/reset` clears tasks and recurrence rules and
  restores default categories and settings, and zeroes the seed marker so the
  idempotent seeder will repopulate the demonstration scenario on the next
  startup. The reset is verified to clear data immediately and reseed on restart.
- **Alternatives:** Have reset immediately re-seed in the same transaction —
  rejected because the verified/tested contract is "clear + restore defaults,
  reseed on startup", and it keeps reset a fast, single-transaction operation.
- **Consequences:** Documented in README; a volume wipe remains the last-resort
  full reset.

## D-020 — Retrospective note on milestone tracking (2026-11-11)

- **Category:** ED
- **Context:** Backend work completed across earlier sessions; frontend and
  Docker completed in this session.
- **Decision:** BUILD_STATUS.md records each milestone's gate command and the
  observed result. Entries added after the fact are marked in this journal
  rather than back-dated.
- **Reasoning:** The spec forbids fabricating historical timestamps; all
  recorded dates are the actual date of execution.
