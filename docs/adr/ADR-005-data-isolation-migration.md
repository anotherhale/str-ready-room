# ADR-005: Squadron data isolation, owner migration, and schema evolution

- **Status:** Accepted — 2026-11-24
- **Date:** 2026-11-24
- **Ticket:** [#7](https://github.com/anotherhale/str-ready-room/issues/7) (`P0-05`)
- **Deciders:** READY ROOM engineering
- **Supersedes:** none
- **Constrained by:** [ADR-001](ADR-001-deployment-classification.md) (single squadron, unclassified synthetic data, no runtime egress), [ADR-002](ADR-002-authentication-session.md) (membership-gated sessions), [ADR-004](ADR-004-role-permission-matrix.md) (scope model and deny-by-default evaluation)
- **Constrains:** [#20](https://github.com/anotherhale/str-ready-room/issues/20) (`P1-05` models and migration), [#21](https://github.com/anotherhale/str-ready-room/issues/21) (`P1-06` repositories and `DatabasePort` wiring), [#32](https://github.com/anotherhale/str-ready-room/issues/32) (`P1-17` data backfill), and every later persistence ticket (#41, #55, #78, #79)
- **Requirements:** R-SQDN-08, R-SQDN-09, R-ARCH-05, R-DEPLOY-03

## Context

Every table in the current schema is scoped by a single `owner_id`, and every
repository method receives that `owner_id` as an explicit argument:

| Table | Key shape today | Owner column |
|---|---|---|
| `tasks` | `id` PK; indexes `(owner_id, status)`, `(owner_id, due_date)` | `owner_id` |
| `recurrence_rules` | `id` PK; `owner_id` indexed | `owner_id` |
| `operator_settings` | `owner_id` **is** the primary key | `owner_id` (PK) |
| `categories` | `id` PK; `(owner_id, name)` index | `owner_id` |
| `calendar_events` | `id` PK; `(owner_id, uid, calendar_id)` unique | `owner_id` |
| `email_sources` | `id` PK; `(owner_id, message_id)` unique | `owner_id` |

That is a real isolation boundary for one user and a useless one for a squadron:
`AuthorizationPolicyService` allows a write only when
`owner_id == principal.id`, so any record a second member must see is either
invisible or would have to be duplicated per person. ADR-004 already fixes the
authorization side — five scopes (`personal`, `shared`, `team`, `squadron`,
`duty_position`), deny-by-default evaluation, and squadron membership as the
first gate. This ADR fixes the persistence side: **where the tenant key lives,
which query enforces it, how existing rows acquire it, and how the schema itself
evolves from six owner-scoped tables to the expansion's table set without
destroying data.**

The existing schema-evolution mechanism is `Base.metadata.create_all` plus
`run_additive_migrations` (`AI-DECISIONS` D-009): a fixed tuple of
`ALTER TABLE … ADD COLUMN` statements, idempotent, add-only, with no record of
what ran. That was proportionate for adding three columns to a greenfield demo.
The expansion is a step change — new tables for squadrons, memberships, teams,
duty positions, shares, comments, audit, sessions, and credentials, plus a
tenant column on every existing table and a one-time backfill. The helper cannot
express ordering, a backfill, or "has this run?" without being extended.

Two requirements frame the decision:

- **R-SQDN-09** — squadron scope is a security boundary in data access *and in
  queries*, not only in route handlers.
- **R-ARCH-05** — data migration preserves ownership, is reversible where
  practical, and is tested against fixtures.

## Decision

### 1. Tenant key: `squadron_id` on every scoped row

A `squadron_id` column (`String(36)`, matching the id type already in use) is
added to every squadron-scoped table, and `owner_id` is **retained** rather than
replaced. Ownership answers "whose record is this?"; the tenant key answers
"which squadron may see it at all?" They are different questions and both are
needed.

| Table | Change |
|---|---|
| `tasks` | `+ squadron_id`; indexes become `(squadron_id, status)`, `(squadron_id, owner_id, status)`, `(squadron_id, due_date)` |
| `recurrence_rules` | `+ squadron_id`; index `(squadron_id, owner_id)` |
| `categories` | `+ squadron_id`; unique `(squadron_id, owner_id, name)` |
| `operator_settings` | primary key becomes `(squadron_id, owner_id)` |
| `calendar_events` | `+ squadron_id`; unique `(squadron_id, owner_id, uid, calendar_id)` |
| `email_sources` | `+ squadron_id`; unique `(squadron_id, owner_id, message_id)` |
| new tables | carry `squadron_id NOT NULL` from the first migration that creates them |

Rules that follow from this, and that `P1-05`/`P1-06` must implement:

- **Every index that leads with `owner_id` today must lead with `squadron_id`.**
  A query that filters only by owner is a tenant-boundary bug, not an
  optimisation.
- **`squadron_id` is never accepted from a request.** It is derived from the
  principal's resolved membership, which ADR-002/ADR-004 already establish. No
  request schema carries it, so no client can assert a tenant.
- **`operator_settings` splits into two concerns.** The row stays per person
  (timezone, warning window are personal preferences); squadron-wide defaults
  live on the `squadrons` row. The composite key `(squadron_id, owner_id)` keeps
  one person's preferences from colliding across squadrons without inventing a
  second settings table.
- **A series cannot cross squadrons.** `tasks.series_id` keeps its meaning, and
  a successor task copies `squadron_id` from its predecessor. The completion use
  case already runs in one transaction, so the copy is atomic.
- **Child rows inherit the parent's tenant key.** Any row that references
  another scoped row (comment → task, occurrence exception → series, share →
  task) takes `squadron_id` from the parent inside the same transaction, never
  from the caller. A composite foreign key is deliberately *not* used: SQLite
  and PostgreSQL support it differently, and the invariant is enforced where it
  is written.

**Single squadron now, without baking it in.** R-SQDN-08 forbids enterprise
multi-tenant administration, and ADR-001 fixes one squadron. The schema still
carries the key so that a second squadron is a data change, not a schema
rewrite. The constraint "one squadron exists" is enforced by bootstrap and
configuration, not by omitting the column.

### 2. Enforcement points: three layers, one source of truth

Isolation is enforced where it can fail closed, at three layers:

| Layer | Mechanism | Failure mode |
|---|---|---|
| Application / authorization | ADR-004 evaluation: `ACTIVE` membership, then permission, then scope. The use case builds the query criteria from the principal. | Deny with `forbidden_membership` / `forbidden_scope` |
| Repository | Every method takes a scope criterion that **always** contains `squadron_id`; the predicate is part of the statement, never post-filtered in Python | Empty result |
| Database | `NOT NULL` tenant column on new tables, tenant-leading indexes, FK to `squadrons.id` | Statement fails |

**Repository shape (`P1-06`).** Repository signatures keep returning domain
entities and keep their structural `Protocol`s. What changes is the criteria
argument: instead of a bare `owner_id: str`, each read takes a `ScopeCriteria`
value object carrying `squadron_id`, `owner_id`, and the caller's visible scope
keys. This is the "application-owned query object" the ticket guidance asks for:
the application decides *what* is visible, and the repository cannot be called
without a tenant. The unit of work still owns the transaction boundary and
repositories still never commit.

**One criterion, one construction site.** `ScopeCriteria` is built in exactly one
place — by the use case from the resolved principal — so an endpoint cannot pass
its own. A repository method that admits a raw `str` tenant argument is a defect.

**Existence disclosure.** A cross-squadron read (detail by id, update, delete)
returns **`404`**, because confirming that an id exists in another squadron is
itself a leak. A same-squadron scope denial returns `403` with the ADR-004 code
(`forbidden_scope`, or `forbidden_ownership` for personal scope). Aggregates
never disclose: a summary counts only rows the caller may see.

### 3. Schema evolution: a versioned, forward-only migration runner inside the adapter

**Decision: do not adopt Alembic in this release. Replace the fixed
additive-column tuple with a versioned, ordered, idempotent migration runner that
lives in `adapters/persistence/sqlalchemy/`.**

| Approach | Verdict | Rationale |
|---|---|---|
| Alembic with autogenerate | Deferred, not rejected | Adds a dependency and a second source of schema truth (autogenerate vs. `__table__`). Its `downgrade()` path would be unused on a single host whose recovery story is an operator snapshot (ADR-001 §3/Q6) |
| Keep the current fixed tuple | Rejected | Cannot order steps, cannot backfill, cannot create new tables with an "only if missing" record, and has no durable record of what ran |
| Versioned runner in the persistence adapter | **Selected** | No new dependency, one source of truth, ordered and recorded, portable across SQLite and PostgreSQL, and testable against fixtures |

**Runner contract.**

1. A `schema_migrations` table records `(version, applied_at, description)`.
   Version is an integer and the list is ordered.
2. A migration is a Python callable registered in an ordered tuple. Each runs in
   its own transaction, records its version, and is skipped when its version is
   already recorded. Re-running the runner is always a no-op.
3. Migrations are **data-preserving by construction**: they may add tables,
   columns, and indexes, and may backfill values. They may not drop or rewrite
   existing rows, and they may not narrow a column type.
4. `create_all` stays for brand-new databases, followed by the runner, so an
   empty database and an upgraded volume converge on the same schema. The runner
   must therefore be tolerant of tables that `create_all` already created.
5. A failed step rolls back, the runner stops, and **startup fails closed** with
   a clear error rather than serving a half-migrated schema.

**Reversibility, honestly stated.** R-ARCH-05 asks for reversibility "where
practical". Automated `downgrade()` is not practical here: a downgrade that drops
a column or a table destroys data, and the chosen deployment's recovery unit is
the volume snapshot the operator already takes (ADR-001 §3, Q6). So
reversibility is delivered as:

- **Forward-only, data-preserving steps** — running them twice changes nothing.
- **A recorded version** so an operator can see exactly what has been applied.
- **A documented restore step** — redeploy the previous image and restore the
  pre-upgrade snapshot.
- **No destructive step in the same release as an additive one.** A column
  removal is a deliberate, later decision, never a side effect of an upgrade.

**Expand now, contract later.** SQLite cannot add a `NOT NULL` column with a
constant default in place, and neither dialect can add one to a table with rows
without a rewrite. So the tenant column arrives in two phases:

| Phase | What happens |
|---|---|
| Expand (this release) | Add `squadron_id` nullable, add the new tables with `NOT NULL`, register indexes |
| Backfill (same release, next step) | Populate every existing row deterministically (§4) |
| Guard (every startup) | Startup counts rows with a null tenant key and **refuses to start** if any exist |
| Contract (a later release, recorded as follow-up) | Rebuild the affected table to enforce `NOT NULL` at DDL level, once a release has soaked |

The guard is what makes the nullable window safe: the application cannot run
against a partially migrated database, so "nullable at DDL" never becomes
"nullable in practice".

**Fixture-tested migrations.** Every step must land with a test that:

1. builds a pre-migration database from a versioned SQL fixture under
   `backend/tests/fixtures/schema/`;
2. runs the runner;
3. asserts the post-state, including that **every** pre-existing row survived,
   kept its `owner_id`, and acquired the expected `squadron_id`;
4. runs the runner a second time and asserts zero applied versions and no data
   change (idempotency);
5. for a step that rewrites a key (the `operator_settings` composite PK),
   asserts row-for-row equality of the payload columns across the rewrite.

The fixtures also give the PostgreSQL profile (`READY_ROOM_TEST_DATABASE_URL`)
the same coverage, which is why the runner may use only portable operations.

### 4. Backfill: existing owner-scoped records to the bootstrap squadron

The backfill is one migration step, guarded by its version and by "does the
bootstrap squadron already exist?" so it cannot double-apply.

**Deterministic bootstrap identity.** Ids are `uuid5` values derived from fixed
names (`ready-room.bootstrap.squadron`, `ready-room.personal-workspace`), not
random UUIDs. Every environment that migrates computes the same id, so a re-run,
a fixture, and a restored snapshot line up, and no code needs to look up "the
first squadron".

**Squadron name.** The migration creates the row with the name
`Bootstrap Squadron`. Renaming it is an ordinary squadron update (or, in the demo
profile, part of the synthetic seed), not a schema concern. No real unit name is
written by a migration.

**Per-table mapping.** Every existing row is personal-scope, because today every
row is visible to exactly one owner. That mapping is not a guess; it is the
existing behaviour expressed in the new model, which is what preserves the
`forbidden_ownership` denial code and today's API responses.

| Table | `squadron_id` | `owner_id` | Other columns |
|---|---|---|---|
| `tasks` | bootstrap squadron | unchanged | `scope = 'personal'` added with that default |
| `recurrence_rules` | bootstrap squadron | unchanged | `scope = 'personal'`; `occurrences_generated` untouched |
| `categories` | bootstrap squadron | unchanged | `is_default` and `active` preserved |
| `operator_settings` | bootstrap squadron | unchanged | primary key rewritten to `(squadron_id, owner_id)`; all preference values preserved |
| `calendar_events` | bootstrap squadron | unchanged | `task_id` provenance links preserved |
| `email_sources` | bootstrap squadron | unchanged | `task_id` provenance links preserved |

**Membership creation.** For each distinct `owner_id` found in the data, the
backfill creates one `ACTIVE` membership in the bootstrap squadron with role
`member`. Exactly one member is promoted to `squadron_admin`: the id named by
`READY_ROOM_BOOTSTRAP_ADMIN_ID`, which defaults to the configured single-user
operator id when `environment=demo`. This preserves "each person keeps their own
records" without silently minting administrators, and it keeps the migration
idempotent — an owner that already has a membership is left alone.

**What is never backfilled.** Nothing is widened. No row becomes `shared`,
`team`, or `squadron` scope, no share row is invented, and no duty position is
created. Inventing a share is indistinguishable from a leak, and there is no
record of intent to derive one from.

**Post-backfill invariant.** The sum of row counts per table before and after is
equal. That assertion is part of the migration test and is the check an operator
runs after the upgrade.

### 5. Demo-mode compatibility

R-DEPLOY-03 requires the current single-user/demo behaviour to survive.

- **One artifact set.** The demo profile runs the same migrations; there is no
  demo-only schema branch. `environment=demo` changes identity (ADR-002 §9: the
  `single_user` provider is refused outside `demo`/`test`), not the schema.
- **Demo seed writes the new columns explicitly.** `squadron_id` and
  `scope = 'personal'` are set by the seeder rather than defaulted, so a seed
  cannot create an unattributed row. The existing seed guards (`seed_version`
  plus "do any tasks exist?") are unchanged.
- **Reset preserves the tenant and membership rows.** `POST /api/demo/reset`
  clears task/recurrence/demo state and reseeds; it must **not** delete the
  bootstrap squadron row or its memberships, for the same reason it already
  restores categories and settings rather than leaving the board empty. Deleting
  them would either orphan the reseeded rows or let a second reset create a
  duplicate squadron.
- **A volume wipe stays the last resort.** The database is recreated, `create_all`
  runs, the runner applies every step to an empty database, and the demo seed
  repopulates.
- **Idempotency on restart.** Container restarts re-run `init_schema`; the runner
  applies nothing and the seed guards hold, so repeated `docker compose up`
  cannot duplicate data or re-backfill.

### 6. Operator recovery procedure

Documented so a failed upgrade is a procedure, not an improvisation:

1. **Before upgrade** — snapshot the database volume and configuration (Q6).
2. **Upgrade** — deploy the new image; `init_schema` runs `create_all` plus the
   runner. Startup fails closed on a failed or incomplete step.
3. **Verify** — `/api/health` returns healthy, the guard finds no null tenant
   keys, and per-table row counts match the pre-upgrade counts.
4. **On failure** — stop the new container, redeploy the previous image, restore
   the snapshot. Because no step drops or rewrites data, a partially applied run
   loses nothing, and restoring the snapshot is belt-and-braces rather than
   required to recover.
5. **Never** hand-edit the `schema_migrations` table to force an upgrade through.
   A version recorded without its step is a silent, unrecoverable divergence.

### 7. Isolation test matrix

`P1-06`, `P1-17`, and the QA tickets must cover every read path. Each case runs
with two squadrons, two users per squadron, and asserts that the denied caller
fails closed (empty, `404`, or `403`) rather than receiving another squadron's
data. Count leakage is tested explicitly: an aggregate that excludes the denied
rows must also exclude them from its totals.

| Read path | Case | Expected |
|---|---|---|
| Task list (`?status=all`) | Sibling user in another squadron lists tasks | Only own-squadron rows; no cross-squadron row, no count of them |
| Task detail / update / delete by id | Guessed id from another squadron | `404` |
| Task detail by id | Same squadron, outside caller's scope | `403` `forbidden_scope` (or `forbidden_ownership` for personal scope) |
| Recurrence rule list, detail, series timeline | Another squadron | `404` / empty |
| Categories list and settings read | Another squadron's id in a request path | `404` |
| Dashboard / briefing summaries | Aggregate across squadrons | Totals exclude other squadrons entirely |
| Search (once #98 exists) | Cross-squadron match | Match filtered out before it is returned, including in result counts |
| Notifications (#88–#90) | Another squadron's notification | Not listed, not counted, not markable |
| Audit read (#40, ADR-011) | Non-admin or another squadron | `403` / empty |
| Calendar cache (`calendar_events`) | Sync/capture as another squadron | Row invisible to the other tenant; sync writes carry the caller's tenant |
| Mailbox provenance (`email_sources`) | Capture idempotency across tenants | Two tenants may hold the same `Message-ID`; recapture stays per tenant |
| Turnover package (#91–#93) | Package built from another squadron's records | Excluded by construction; builder reads through scoped queries only |
| Jev context assembly (#65) | Prompt built for a principal | Contains only rows the principal may see, asserted against a second squadron |
| Settings / preferences | Two users, same squadron | Distinct rows; one user cannot read the other's preferences |

The harness that makes these cheap is ticket #14 (multi-principal test harness
and configurable test auth provider); until it lands, `P1-06` writes the
two-squadron fixture directly.

## Consequences

**Positive**

- One tenant key, one construction site, and one place per query that can leak —
  which makes the security property reviewable instead of incidental.
- Existing data keeps its ownership and its exact current visibility, so the demo
  and its tests survive the upgrade without a behaviour change.
- The migration runner is small, portable, and fixture-tested, with no new
  dependency, consistent with D-009 and ADR-001's offline deployment constraint.
- Cross-squadron access fails closed at the repository even if an authorization
  check is forgotten, which is the failure mode a single-layer design cannot
  survive.

**Negative / accepted trade-offs**

- Every scoped table and query grows a column and a predicate; the repository
  protocols change shape once, before any of the dependent tickets land.
- The tenant column is nullable at DDL level until the contract phase, so the
  startup guard is load-bearing and must not be removed for convenience.
- A nullable-to-`NOT NULL` contract step is deferred work that a future session
  must not lose; it is tracked as a follow-up, not left as a comment.
- The composite primary key on `operator_settings` means a table rebuild on
  SQLite, which is the most delicate step in the migration and is explicitly
  fixture-tested.

**Risks**

- An aggregate written as raw SQL rather than through a scoped repository would
  bypass the boundary. The mitigation is the rule that aggregate reads are
  repository methods, not ad-hoc queries in a service.
- A future ticket that adds a scoped table without `squadron_id` reopens the
  hole. The mitigation is the review rule plus the isolation matrix being part of
  each persistence ticket's acceptance criteria.
- If a later release genuinely needs multi-squadron administration, the schema is
  ready but ADR-004's membership model and ADR-008's delegation scoping must be
  revisited; the key's existence is not permission to build tenancy.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Scope everything by `owner_id` plus share rows only | Team and squadron scope still need a set of member ids per query, which is a tenant query in disguise and cannot be indexed |
| Replace `owner_id` with `squadron_id` | Loses "whose record is this?", which the personal scope, handoffs, and accountability all depend on |
| One database or schema per squadron | Multi-tenancy infrastructure for a product whose explicit non-goal is multi-tenant administration (R-SQDN-08) |
| Adopt Alembic now | Adds a dependency and a second schema description for a schema this size; its downgrade path is not the chosen recovery mechanism |
| Keep the add-only column tuple | No ordering, no backfill, no record of what ran — the exact gaps this ticket exists to close |
| Enforce isolation only in route handlers | R-SQDN-09 requires it in the queries; a single forgotten handler is a cross-squadron leak |
| Backfill every row to squadron scope for convenience | Widens visibility of personal records; the upgrade must not change who can see what |
| Random UUIDs for the bootstrap squadron | Non-deterministic across fixtures and restored snapshots; a re-run would create a second bootstrap |

## Open questions

These do not block `P1-05`, `P1-06`, or `P1-17`; each has a default now.

| # | Question | Default until decided | Owner |
|---|---|---|---|
| I1 | When is the `NOT NULL` contract step scheduled? | The release after the expand/backfill soaks; recorded as a follow-up issue when `P1-05` lands | Engineering |
| I2 | Should `operator_settings` eventually move to per-user rows with squadron defaults separate? | Yes, that is the shape chosen here; the composite key is the first step, not the final form | Engineering |
| I3 | Is a second squadron ever administered, or is the key only insurance? | Insurance only; R-SQDN-08 keeps multi-tenant administration out of scope | Product owner |
| I4 | How long are pre-migration snapshots retained? | Follows Q6: 30 days, quarterly restore drill | Operations |
| I5 | Do calendar/mailbox caches need a per-squadron provider account? | One incident/provider configuration per squadron row, set by configuration; revisit if a squadron ever has a second provider | Engineering |

## Validation

Documentation-only change: this ADR adds
`docs/adr/ADR-005-data-isolation-migration.md`, updates the ADR index, and
records the durable persistence invariants in `AGENTS.md`. No application code,
configuration default, dependency, or test was modified. The backend baseline
was run before and after the change and stayed green; the exact commands and
results are recorded on issue #7.

| Acceptance criterion | Section |
|---|---|
| Tenant key and enforcement points specified | §1, §2 |
| Schema-evolution approach chosen with rationale and rollback story | §3, §6 |
| Backfill mapping for every existing table specified | §4 |
| Isolation test matrix listed | §7 |
| `P1-05`, `P1-06`, `P1-17` can implement without re-deciding | §1–§4, plus the open-question defaults |
