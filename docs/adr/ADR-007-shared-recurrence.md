# ADR-007: Shared recurrence, duty-position routing, occurrence exceptions

- **Status:** Accepted 2026-11-24
- **Ticket:** [#9](https://github.com/anotherhale/str-ready-room/issues/9) (`P0-07`)
- **Requirements:** R-REC-02, R-REC-03, R-REC-04, R-REC-05, R-REC-06, R-REC-08,
  R-REC-09, R-REC-10, R-REC-11, R-REC-12, R-REC-13, R-REC-14, R-ARCH-06
- **Depends on:** ADR-004 (roles and scopes), ADR-005 (tenant key and migration),
  ADR-006 (task scope, sharing, accountable ownership)
- **Constrains:** `P3-01`..`P3-04` (domain), `P3-07`/`P3-08` (use cases), `P3-09`
  (API), and every later recurrence consumer (scan, briefing, turnover, Jev)

## Context

Recurrence today is a **chain of ordinary `Task` rows** sharing `series_id`, with
`recurrence_rule_id` and a 1-based `occurrence_number`. There is no occurrence
table. `RecurrenceRule` holds `frequency`, `interval`, `anchor_date`,
`day_of_week`, `end_type`/`end_count`/`end_date`, `occurrences_generated`, and
`active`; it is owner-only (`owner_id`) and its edits mutate in place.
`plan_next()` is pure arithmetic anchored on the series' first occurrence,
fast-forwards over missed dates in a bounded loop, and never backfills.
Completion is idempotent and generates at most one successor, in one transaction.

The expansion requires the same model to carry: personal/team/squadron scope, a
series owner plus a responsible duty position, default assignee and
collaborators, due time and timezone, start/end and pause/resume, per-occurrence
exceptions (due-date change, reassignment, skip/cancel), series revision
history, acknowledgment/completion requirements, and optional escalation.

Three spec statements drive every decision below:

1. "A series edit must clearly distinguish changes to future occurrences from
   edits to a single occurrence."
2. "Preserve historical occurrences and their responsible parties."
3. "If duty-position holder changes, route future occurrences to the new holder;
   do not rewrite historical accountability."

ADR-006 already fixes what a task's scope means, who may act at each scope, and
that a duty position is an *assignee kind*, never a fifth task scope. This ADR
does not revisit those rules; it decides how a **series** produces tasks that
obey them.

## Decision

### 1. The chain stays; the rule becomes a versioned series definition

No occurrence table is introduced. `series_id` remains the chain identity and
`occurrence_number` remains contiguous and 1-based within a series; numbers are
never reused and never renumbered, including after a rule edit.

`RecurrenceRule` becomes the series definition and gains:

| Field | Type | Meaning |
|---|---|---|
| `series_id` | text, unique | Stable series identity, independent of rule revision |
| `squadron_id` | text | Tenant key (ADR-005) |
| `scope` | `personal` \| `team` \| `squadron` | Series visibility (ADR-006 §1) |
| `team_id` | text, nullable | Required when `scope = team` |
| `accountable_owner_id` | text | The human answerable for the series (ADR-006 §2) |
| `responsible_duty_position_id` | text, nullable | Duty position the series is routed to |
| `default_assignee` | typed, nullable | `user` / `team` / `duty_position` (ADR-006 §2) |
| `default_collaborator_ids` | set of user ids | Written as `write` shares on each occurrence |
| `start_date` | date | First date the series may generate (default = `anchor_date`) |
| `timezone` | IANA id | Zone the series' due times are expressed in |
| `due_time_local` | time, nullable | Null means a date-only series (today's behaviour) |
| `paused_at` | datetime (UTC), nullable | Non-null means paused |
| `revision` | int, starts at 1 | Current revision number (§5) |
| `escalation_policy_id` | text, nullable | Extension point only (§10) |

`owner_id` is retained and kept equal to `accountable_owner_id` during migration,
exactly as ADR-006 §9 requires for tasks.

### 2. Series scope: three values, inherited by every occurrence

A series is `personal`, `team`, or `squadron` — the three scopes the
specification names for recurring responsibilities. `shared` is **not** a series
scope: a series must be findable by whoever maintains it, and named-person
distribution is already expressible with `default_assignee` and
`default_collaborator_ids` (a `personal` series with a user assignee is exactly
ADR-006 §2 invariant 6: the assignee must also hold a share, which the generator
writes as a `write` share).

- Every occurrence is created with **the series' scope at generation time**
  (ADR-006 §5, "Recurrence occurrence inherits the series' scope"). A successor
  never widens scope.
- Creating or widening a series requires the actor's grant ceiling to reach the
  target scope (`recurrence:write`, ceiling `team`), otherwise
  `forbidden_scope`. Narrowing is allowed and keeps existing occurrences as they
  were.
- A `team` series must name a `team_id` that exists in the same squadron; a
  `squadron` series needs none. A `personal` series cannot carry a team or
  duty-position `default_assignee` (ADR-006 §2 invariant 6).
- Read/write authority over a *series* uses `recurrence:read` / `recurrence:write`
  plus the ADR-006 §4 relationship rules for the series' scope. Authority over a
  single *occurrence* is the ADR-006 §4 task rules for that task's scope.

### 3. Duty-position routing snapshots the holder per occurrence

The series stores `responsible_duty_position_id`; each occurrence stores the
**resolved person** plus the provenance of that routing:

- `routed_from_position_id` — the position the occurrence was routed from
  (null for a user/team-assigned series).
- `assignee_snapshot_user_id` — the holder resolved at generation.
- `assignee_history` — append-only list of `(user_id, from, to, reason, actor)`.

Rules:

1. **Generation resolves the current holder.** A new occurrence is assigned to
   the position's holder at the moment it is created. A series routed to an
   empty position is rejected at validation (ADR-006 §2 invariant 3) — routing
   work to nobody creates invisible work.
2. **A holder change routes open work forward and never rewrites the past.**
   In one audited transaction: occurrences of the series with `status = open`
   and `routed_from_position_id = P` are reassigned to the new holder; completed
   and cancelled occurrences are untouched; `occurrence_number`, `series_id`,
   scheduled dates, and completion records are unchanged; reassignment clears
   `acknowledged_at`/`acknowledged_by` (ADR-006 §6).
3. **"Future" means "not yet closed", not "not yet created".** Leaving an open
   occurrence with a departed holder would strand live work, which the spec's
   "route future occurrences to the new holder" is meant to prevent.
   Historical accountability survives in the append-only `assignee_history` and
   in the untouched completed rows, so nothing is rewritten.
4. **Vacancy falls back to the accountable owner.** If the position empties
   without a successor, open occurrences and future generation fall back to the
   series' `accountable_owner_id` and the series is flagged
   `unassigned_position` for the operational scan. Work is never left with no
   assignee silently.
5. **Position authority is not series ownership.** A holder gains the ADR-004
   duty-position capability set (`tasks:assign`, `recurrence:override`, …) at
   duty scope; the accountable owner remains a human user and is unchanged by a
   holder change (ADR-006 §2 invariant 1, ADR-004 §5).

### 4. Per-occurrence exceptions: task edits plus an append-only exception log

An occurrence is a normal task. Editing one therefore needs **no new storage for
its values** — the change lands on the task row (`due_date`, assignee, status) —
and the series is not touched. What is stored separately is the *fact* that the
occurrence deviates from its rule:

`recurrence_exceptions(series_id, occurrence_number, kind, payload_json,
rule_revision, created_by, created_at)`, primary key
`(series_id, occurrence_number, kind)`, append-only.

| `kind` | Effect on the occurrence task | Notes |
|---|---|---|
| `due_date_changed` | `due_date` (and `due_at_utc` if the series has a due time) updated | Original rule date stays recoverable from the rule revision |
| `reassigned` | Assignee changed; acknowledgment cleared (ADR-006 §6) | Requires `tasks:assign` on the occurrence |
| `skipped` | `status = cancelled` | Deliberate cancellation, not completion |

Invariants:

- **Skipping an already-generated occurrence cancels it; skipping an occurrence
  that was never generated records the exception and consumes the slot.** Either
  way the series advances past that occurrence number and no task is created for
  it.
- **`cancelled` is a closed status, not a completion.** `TaskStatus` gains
  `CANCELLED` in `P3-02`/`#52`. Operational sections exclude it exactly like
  `COMPLETED` (a cancelled occurrence is not overdue work), but **completion
  metrics never count it**, and the series report counts it separately as
  `occurrences_skipped`.
- Exceptions are idempotent on `(series_id, occurrence_number, kind)`: repeating
  a skip or a due-date change with the same payload is a no-op, not a second
  row.
- An exception never edits the rule, never bumps `revision`, and never affects
  any other occurrence. This is the structural guarantee behind acceptance
  scenario 6.

### 5. Revisions: occurrences snapshot, the rule evolves

`recurrence_rule_revisions(rule_id, revision, kind, effective_from_occurrence,
snapshot_json, created_by, created_at, reason)` is append-only. Every rule edit
writes a new row and increments `rule.revision`.

Each occurrence **snapshots** the fields that define its own schedule and
assignment at creation: `rule_revision`, `scheduled_date` (the arithmetic date
from the rule), `due_date`, `due_at_utc`, `assignee_snapshot_user_id`,
`routed_from_position_id`, `scope`, `squadron_id`, `accountable_owner_id`.
Consequently:

- A later revision can never reinterpret history: reading an occurrence does not
  re-derive its dates from the current rule.
- `plan_next()` keeps anchoring on `first_occurrence(rule)` (month-end and
  leap-year clamping stay deterministic: 31 Jan → 31 Mar, never 28 Mar).
- When an edit changes `frequency`, `interval`, or `anchor_date`, the new anchor
  becomes the **scheduled date of the current open occurrence** (or the next
  ungenerated date if none is open). Occurrence numbering continues from the
  existing `occurrences_generated`; nothing is renumbered.
- Editing a series preserves `series_id` and `occurrences_generated`
  (`AGENTS.md`).

### 6. API semantics: "this occurrence" vs "this and future occurrences"

One rule, stated so it is directly testable: **a series edit affects only
occurrences generated after it; an occurrence edit affects only that occurrence.**

| Operation | Endpoint (shape) | Permission | Effect |
|---|---|---|---|
| Edit series, future | `PATCH /api/recurrence/rules/{rule_id}` (`scope=future`, default) | `recurrence:write` + series-scope relationship | New revision; `effective_from_occurrence` = next ungenerated number. Existing occurrences, open or closed, unchanged |
| Edit series, explicit alias | `PATCH …/rules/{rule_id}?scope=series` | as above | Identical to `future`; accepted so clients can be explicit |
| Edit one occurrence | `PATCH /api/recurrence/series/{series_id}/occurrences/{occurrence_number}` | `recurrence:override` (or `tasks:update` on that task) | Task edit + exception row; rule untouched |
| Skip one occurrence | `POST …/occurrences/{occurrence_number}/skip` | `recurrence:override` | `skipped` exception (§4) |
| Pause / resume | `POST …/rules/{rule_id}/pause`, `/resume` | `recurrence:write` | Revision row of kind `paused`/`resumed`; schedule unchanged |
| Preview | `GET …/rules/{rule_id}/preview` | `recurrence:read` | Dates only; no writes |

- `scope=past` and `scope=all` do not exist and are rejected with `422`. There
  is no operation that rewrites history.
- `scope=occurrence` without an occurrence identifier is `422`; the two edits
  are never ambiguous in one request.
- An already-generated **open** occurrence is *not* retroactively edited by a
  `future` edit — it already exists as a task and is changed through the
  occurrence endpoint. This keeps both directions of the invariant
  ("one occurrence does not change the series" and "the series does not
  silently change live work") true at the same time.
- Pause/resume do not shift dates: on resume, dates that fell inside the paused
  window are skipped by the existing bounded fast-forward, consistent with
  no-backfill. `occurrences_generated` counts them, so it stays truthful.

### 7. Due time and timezone

- A date-only series keeps `due_date` (a plain `date`) and no due instant —
  today's behaviour, unchanged.
- A series with `due_time_local` produces `due_at_utc`, a **naive UTC**
  datetime computed at generation from `due_date + due_time_local` in the
  series' `timezone` (`zoneinfo`, `tzdata` required in the runtime image).
- The series stores its `timezone` explicitly; it is not re-read from operator
  settings on every read, so changing the operator's zone never silently moves
  an existing deadline. Changing the series zone is a revision and affects
  future occurrences only.
- Urgency stays **derived** from status, due date/instant, the operator's local
  `today`, and the warning window. Nothing about a series adds a stored urgency.
- Never compare a `date` with a `datetime`; a date-only series is evaluated on
  dates and a timed series on instants converted through the operator zone.

### 8. Acknowledgment and completion requirements

- `requires_acknowledgment` (bool, default `false`) is series metadata. When
  true, an open unacknowledged occurrence is reported in the scan's
  `awaiting_acknowledgment` section and notifies the assignee.
- It **never blocks completion**, and completion never implies acknowledgment
  (ADR-006 §6). The scan reports `completed_unacknowledged` separately.
- Every occurrence requires completion to advance the chain, so no
  "completion optional" flag is added. A mode in which an occurrence may expire
  without closure would contradict `AGENTS.md` ("overdue tasks never
  disappear") and the readiness semantics; if the product later needs
  "informational" responsibilities, they belong in a different record type, not
  in this flag.
- Idempotent completion is unchanged: completing an already-completed
  occurrence returns it unchanged and creates no second successor. A cancelled
  occurrence cannot be completed and generates no successor; the series advances
  only when the exception was recorded.

### 9. Generation invariants (idempotency, scenario 5)

- Exactly one successor per completed occurrence; none if an open occurrence
  already exists for the rule; no successor for a cancelled occurrence.
- `occurrence_number = predecessor + 1`; the successor snapshots (§5) and
  inherits the series' `scope`, `squadron_id`, and `accountable_owner_id`.
- Uniqueness of `(recurrence_rule_id, occurrence_number)` is a database
  constraint, so a double generation is a `409`, never a duplicate row.
- Generation and completion run in one transaction: a successor failure must not
  leave a half-committed completion.
- No backfill; the fast-forward is bounded; `occurrences_generated` counts
  skipped slots so series reports stay truthful.

### 10. Escalation and follow-up are an extension point only

`escalation_policy_id` is stored and surfaced but has no first-cut behaviour.
Escalation rules (reminders, reassignment after N days, notification escalation)
have no ticket yet; the scan's duty-routing and at-risk visibility land in
`P3-11`/`#61`. When prioritised, escalation must be a policy evaluated on read or
by a scheduler — never extra columns on the chain and never a second generator
competing with completion.

### 11. Migration and compatibility

- Existing rules become: `series_id = rule.id`, `scope = personal`,
  `accountable_owner_id = owner_id`, `timezone` = operator's effective zone,
  `due_time_local = NULL`, `revision = 1`, no position, no default assignee or
  collaborators. Behaviour for existing demo data is unchanged.
- Existing tasks keep `series_id`/`occurrence_number`; the new snapshot columns
  are backfilled from the current rule so historical occurrences remain readable
  without a rule lookup.
- Migration follows ADR-005: expand → backfill → startup guard → contract, with a
  fixture test proving row-for-row survival and idempotency. No rows are
  rewritten in place and no occurrence is regenerated.

### 12. Check against the acceptance scenarios

| Scenario | Result |
|---|---|
| 5. A shared recurring responsibility generates occurrences idempotently | Series scope is inherited per occurrence; `(rule, occurrence_number)` is unique; exactly one successor per completion in one transaction (§2, §9) |
| 6. Editing one occurrence does not unintentionally change the recurrence series | Occurrence edits write an exception row and the task only; the rule, its revision, and every other occurrence are untouched (§4, §6) |
| 7. Changing a duty-position holder routes future occurrences to the new holder while preserving historical ownership | Open occurrences are reassigned, completed/cancelled ones and all history are untouched, the accountable owner is unchanged (§3) |

## Consequences

**Positive**

- The chain model, its idempotency, its anchoring, and its no-backfill rule are
  preserved exactly; nothing about recurrence needs re-proving.
- "Future vs single" stops being a UI convention: it is two endpoints with
  different permissions and different storage effects.
- History cannot be rewritten by construction — occurrences snapshot, revisions
  and exceptions are append-only.
- Duty-position routing gives live work to the current holder without inventing
  a fifth scope or a second assignment model.

**Negative / costs**

- Two new append-only tables (`recurrence_rule_revisions`, `recurrence_exceptions`)
  and several snapshot columns on tasks; the migration is real work in `P3-02`.
- `CANCELLED` becomes a third task status, so every "closed vs open" query must
  be reviewed once. Completion metrics must exclude it, which is a place to get
  wrong if a query says `status != 'open'`.
- An open occurrence is deliberately not edited by a series edit, so a user who
  edits "the series" and sees today's task unchanged may report a bug. The UI
  must say which occurrence is which.
- Series timezone is stored per series, so a squadron-wide series spanning zones
  is expressed as several series, not one.

## Alternatives considered

1. **Introduce a `TaskOccurrence` table.** Rejected by the ticket and by the
   existing invariants: it duplicates task state, splits the authorization policy
   across two record types, and immediately drifts from the task rows the scan
   reads.
2. **Model "future vs single" as a `Task.is_exception` boolean on the task.**
   Rejected: a boolean cannot say *which* field deviated, cannot be audited, and
   would let a series edit overwrite an exception silently.
3. **Rewrite the series in place and re-derive occurrence dates on read.**
   Rejected: it retroactively changes history (violates the spec), makes
   "completed on time" unknowable, and turns every read into rule arithmetic.
4. **Reassign only occurrences generated after a holder change.** Rejected: it
   strands live work with a departed holder, which is the operational failure the
   requirement exists to prevent.
5. **A `completion_optional` flag.** Rejected: it makes "not done and not
   overdue" representable, contradicting the readiness semantics.
6. **Store due time as a local naive datetime.** Rejected: it cannot survive a
   DST transition or an operator zone change without silently moving deadlines.

## Open questions (confirmable defaults, non-blocking)

| # | Question | Default until decided | Owner |
|---|---|---|---|
| R1 | May a series have a `team` default assignee at `personal` scope? | No — ADR-006 §2 invariant 6; such a series must be `team` scope | Product owner |
| R2 | Should pausing a series cancel its already-generated open occurrence? | No. Pause stops generation only; the open occurrence stays work and must be completed, skipped, or reassigned explicitly | Product owner |
| R3 | Does a holder change also reassign occurrences routed from the *team* default assignee? | No. Only occurrences routed from the changed position move; team-assigned work is unchanged | Engineering |
| R4 | Are series revisions visible to every reader of the series, or admins only? | Visible to anyone who may read the series; the snapshot is operational context, not an audit secret | Product owner |
| R5 | Do `default_collaborator_ids` follow a scope narrowing? | Yes, existing shares are kept (ADR-006 §5); narrowing never hides work from a collaborator | Engineering |
| R6 | Should a skipped occurrence appear in the turnover package? | Yes, as a closed item with its reason; turnover needs to know work was deliberately dropped | Product owner |

## Validation

Documentation-only change: this ADR adds
`docs/adr/ADR-007-shared-recurrence.md`, flips its row in `docs/adr/README.md` to
Accepted, and records the durable recurrence invariants in `AGENTS.md`. No
application code, configuration default, dependency, test, or migration was
modified. The backend baseline was run before and after the change and stayed
green; the exact commands and results are recorded on issue #9.

| Acceptance criterion | Section |
|---|---|
| New rule fields and invariants are specified | §1, §2, §5, §9 |
| Exception and revision models are specified without an occurrence table | §4, §5 |
| Future-vs-single edit semantics are explicit and testable | §6 (endpoints, permissions, effects) |
| Duty-position routing preserves historical accountability | §3 |
| `P3-01`..`P3-04` can implement directly | §1–§11 plus the open-question defaults |

## References

- `docs/SQUADRON_PLATFORM_EXPANSION.md` §4 (shared recurring responsibilities),
  acceptance scenarios 5, 6, 7
- `docs/adr/ADR-006-task-scope-sharing.md` §1 (scopes), §2 (relationships and
  invariants), §4 (per-scope verbs), §5 (scope inheritance), §6 (acknowledgment
  and reassignment), §9 (compatibility)
- `docs/adr/ADR-004-role-permission-matrix.md` §3 (`recurrence:read`,
  `recurrence:write`, `recurrence:override`), §5 (team-lead and duty-position
  authority)
- `docs/adr/ADR-005-data-isolation-migration.md` §1 (tenant key), §4 (migration
  sequence)
- `backend/app/domain/tasks/recurrence.py` (`plan_next`, anchoring,
  no-backfill), `backend/app/domain/tasks/entities.py` (`RecurrenceRule`,
  `Task.series_id`/`occurrence_number`),
  `backend/app/application/services/task_service.py` (`complete_task`,
  `_generate_successor`)
