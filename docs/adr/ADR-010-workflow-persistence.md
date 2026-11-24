# ADR-010: Workflow persistence, retries, cancellation, and idempotency

- **Status:** Accepted 2026-11-24
- **Ticket:** [#12](https://github.com/anotherhale/str-ready-room/issues/12) (`P0-10`)
- **Requirements:** R-WF-01, R-WF-02, R-WF-03, R-WF-04, R-ARCH-06
- **Depends on:** ADR-004 (roles, scoped permissions, delegable capability classes),
  ADR-005 (tenant key, migration runner), ADR-006 (task scope and ownership),
  ADR-008 (agent identity, delegation, approval binding — in review)
- **Constrains:** `P5-03` (run domain), `P5-10` (run service and API), the approval
  gate `P5-05`, the tool gateway `P5-06`, and every workflow consumer
  (briefing, turnover, scan, Jev drafts)

## Context

The platform will run a small number of AI-assisted workflows: daily briefing
preparation, task capture from an approved source, recurring responsibility
preparation, deadline follow-up drafts, owner recommendation, duty turnover
packages, and a readiness/attention scan. Each run must be durable and
inspectable: identity, initiating actor, agent identity/version, status,
timestamps, inputs, proposed actions, tool invocations, approvals, outputs,
errors, and retry history. The spec requires bounded retries, cancellation, and
recovery, and explicitly forbids a generic workflow designer, a DSL, or a large
multi-agent hierarchy.

Three constraints shape the design:

1. **The database is the only source of truth.** A run waiting for approval must
   survive a process restart; a resumed run must not repeat a side effect.
2. **Human accountability stays outside the agent.** An approval binds to an
   exact action and its parameters; agents cannot approve, and no timeout may
   become an implicit approval (ADR-004 §6, ADR-008).
3. **The adapter stays portable.** The stack runs on SQLite by default and must
   run unchanged on PostgreSQL, so the claim and idempotency mechanisms may not
   depend on partial indexes, advisory locks, or `SKIP LOCKED`.

There is no workflow code today: no run table, no runner, no tool gateway. This
ADR decides the record shape and the semantics that `P5-03` and `P5-10`
implement; it changes no code itself.

## Decision

### 1. One run table, one append-only event log, one step table

A workflow run is **a row, not a process**. `workflow_runs` holds current state;
`workflow_run_events` is an append-only log of every transition and attempt;
`workflow_run_steps` holds one row per idempotent unit of work. There is no
engine, no definition DSL, no dynamic graph: the workflow catalog in §2 is a
fixed enum, and the step sequence for each type is code in the application
service, not data.

This mirrors the pattern already used for recurrence: mutable current state plus
append-only history, with the history never rewritten.

### 2. Fixed workflow catalog

Seven types, one `workflow_version` integer, no user-defined workflows. Each type
declares its inputs, its outputs, and whether it can produce a consequential
step. Adding a type is a code change and a version bump, not configuration.

| Type | Trigger | Inputs | Outputs | Consequential step |
|---|---|---|---|---|
| `daily_briefing_preparation` | scheduled | `squadron_id`, `briefing_date` | briefing snapshot ref, item refs | none (read-only) |
| `task_capture_classification` | user | source ref (`email_id` or `calendar_event_id`), target scope | draft task proposal; personal task created on confirm | creating a `shared`/`team`/`squadron` task |
| `recurring_responsibility_preparation` | scheduled | `series_id`, horizon (days) | draft occurrence proposals | generating occurrences for a shared series |
| `deadline_followup_draft` | scheduled | task refs approaching due, channel | notification draft | sending the notification |
| `task_owner_recommendation` | user | `task_id` | ranked owner suggestions with reasons | none (read-only) |
| `duty_turnover_package` | user | outgoing holder, window, scope | turnover package draft | publishing the package to the incoming holder |
| `readiness_attention_scan` | scheduled | `squadron_id` | attention items, scan summary | none (read-only) |

Read-only workflows may run unattended inside the initiating user's delegation
scope. A consequential step always follows §4: it stops at
`waiting_approval`, and a human with `approvals:decide` decides.

### 3. Run state machine

Six states. Three are open (`queued`, `running`, `waiting_approval`), three are
terminal (`succeeded`, `failed`, `cancelled`). There is no `paused` state and no
"partially succeeded": a run either reaches `succeeded` with every step recorded
as `succeeded` or `skipped`, or it is terminal in a non-success state with a
`reason_code`.

| From | To | Trigger | `reason_code` |
|---|---|---|---|
| `queued` | `running` | runner claims the run (conditional update) | — |
| `queued` | `cancelled` | user cancels before a claim | `cancelled_by_user` |
| `queued` | `failed` | preflight fails (expired delegation, inactive membership, unknown type/version) | `preflight_denied`, `delegation_expired`, `unsupported_version` |
| `running` | `waiting_approval` | next step is consequential and has no valid approval | `approval_required` |
| `running` | `succeeded` | last step succeeded or skipped | `completed` |
| `running` | `failed` | non-retryable error, retry budget exhausted, deadline exceeded | `authorization_denied`, `validation_error`, `retry_exhausted`, `deadline_exceeded`, `internal_error` |
| `running` | `cancelled` | cancel requested, observed at a step boundary | `cancelled_by_user` |
| `waiting_approval` | `running` | approval granted and digest matches | `approval_granted` |
| `waiting_approval` | `failed` | approval denied, expired, or invalidated by a changed proposal | `approval_denied`, `approval_expired`, `approval_invalidated` |
| `waiting_approval` | `cancelled` | user cancels while waiting | `cancelled_by_user` |

Invariants the tests must assert:

- Terminal states have **no** outgoing transition. A retry is a new run with
  `retry_of_run_id` set; a run id is never reopened.
- `succeeded` is reachable only from `running`, and only when every step row is
  `succeeded` or `skipped`.
- `waiting_approval` is reachable only when a `pending` approval row exists for
  the step key. A run can never wait for an approval that was not created in the
  same transaction as the transition.
- Every transition writes exactly one `workflow_run_events` row with
  `from_state`, `to_state`, `reason_code`, `actor_kind`, `actor_id`, `occurred_at`.
  A transition without an event row is a bug, not a tolerated state.

### 4. Approval waiting is durable and binds to the exact action

`workflow_approvals` belongs to ADR-008; this ADR adds three columns to it
(`run_id`, `step_key`, `action_digest`) and the rules below.

- `action_digest` = SHA-256 of canonical JSON (sorted keys, no insignificant
  whitespace) over `{tool_name, tool_version, capability, target_ref, parameters}`.
- The runner recomputes the digest immediately before executing the step. If it
  differs from the approved digest, the approval becomes `invalidated` and the
  run transitions to `failed` with `approval_invalidated`. A changed proposal is
  never executed under an old approval.
- Approval expiry defaults to **24 hours**; on expiry the row becomes `expired`
  and the run fails with `approval_expired`. No timeout, missing response, or
  notification failure may produce execution.
- Deciding requires `approvals:decide` at the run's scope, a **human** principal,
  and an approver who is not the run's initiating user when the action is
  agent-proposed (ADR-004 §6, ADR-008). Agents can never decide.
- Approval and execution stay two operations: deciding an approval does not
  execute the step; it only makes the run eligible to resume.

### 5. Idempotency at two levels

**Run creation.** The caller supplies `Idempotency-Key` (or the scheduler derives
one from `type + subject + scheduled_slot`). `workflow_runs` has a unique
constraint on `(squadron_id, idempotency_key)`; a duplicate create returns the
existing run with `200` and does not start a second run.

**Step execution.** Each step has a content-derived, stable `step_key`:
`"{seq:02d}:{tool_name}:{input_digest}"`. `workflow_run_steps` has a unique
constraint on `(run_id, step_key)`. The runner claims a step by inserting its row
in state `started`; a second attempt on the same key reads the existing row and
returns its recorded outcome instead of re-invoking the effect. Because the
uniqueness is a plain constraint, the claim is atomic on SQLite and PostgreSQL
alike.

A step may only wrap a use case that is already idempotent (task completion,
capture, acknowledgment links). The tool gateway refuses to register a step whose
use case has no idempotency contract, so "retry safety" cannot be assumed by
accident.

### 6. Bounded retries

Retry unit is the **step attempt**, never the whole run.

| Rule | Value |
|---|---|
| Attempts per step | 3 (initial + 2 retries) |
| Backoff between attempts | 5 s, then 30 s (fixed, no jitter, so tests are deterministic) |
| Retryable error classes | `provider_timeout`, `provider_unavailable`, `transient_io` |
| Never retried | `authorization_denied`, `validation_error`, `not_found`, `conflict`, `approval_invalidated` |
| Run step budget | 20 steps |
| Run deadline | 15 minutes from `created_at` (per-type override allowed in the catalog) |
| Recovery attempts | 1 per run |

A retried attempt is a **new row** in `workflow_run_events` (`kind =
step_attempt`) with the incremented `attempt`; the step row keeps `attempt` and
`error_class` of the latest attempt. When the budget is exhausted the run fails
with `retry_exhausted`; when the deadline passes at a step boundary the run fails
with `deadline_exceeded`. Retrying a failed run creates a new run.

### 7. Cancellation is cooperative and never mid-write

`POST /api/workflows/runs/{id}/cancel` sets `cancel_requested_at` and
`cancel_requested_by_user_id`; it does not delete work. The runner checks the
flag at each step boundary and, if set, transitions to `cancelled` with
`cancelled_by_user`. An in-flight step is allowed to finish, because aborting
inside a use case would leave the half-committed state the transaction rules
exist to prevent.

`waiting_approval` cancels immediately (nothing is in flight). A cancelled run
creates no successor, no retry, and no notification beyond the cancellation
event.

### 8. Crash recovery is explicit and bounded

The runner writes `last_heartbeat_at` every **15 s** and records its
`runner_id`. On startup a sweep looks for runs in `running` whose heartbeat is
older than **30 s** and marks them `recovery_status = interrupted`.

- The runner resumes from the last step with a recorded terminal outcome. An
  in-flight step is retried with the same `step_key`, so its effect is not
  duplicated (§5).
- If the interrupted step's use case cannot prove idempotency, the run fails with
  `recovery_unsafe`. Guessing is worse than failing.
- `waiting_approval` is **never** resumed automatically: it waits for a human
  decision or expiry.
- A second interruption of the same run fails it (`recovery_exhausted`).
- Recovery is a sweep at startup plus the normal queue poll; there is no separate
  daemon, cron, or message broker.

### 9. Tool invocations and payload minimization

Each step records `tool_name`, `tool_version`, `capability`, `delegation_id`,
`input_digest`, `input_summary` (≤ 2 KiB), `output_summary` (≤ 8 KiB),
`error_class`, `started_at`, `finished_at`, and `attempt`.

Run records never store model prompts, completions, tokens, credentials, email
bodies, or calendar descriptions. They store **references** (email id, calendar
uid, task id, series id) and digests. This keeps the run inspectable without
turning it into a second copy of the data it touched, and keeps sensitive payloads
out of operational tables. The accountability record is the append-only audit
entry (`#40`), which references `run_id` and `step_key`; the run is the
operational view.

### 10. Concurrency: one active run per subject, portable claim

- `active_key = "{workflow_type}:{subject_kind}:{subject_id}"` while the run is
  open, `NULL` in a terminal state, with a **unique** constraint. Both SQLite and
  PostgreSQL allow multiple `NULL`s in a unique index, so this is portable and
  prevents two open runs of the same type against the same subject.
- The queue claim is a conditional update:
  `UPDATE workflow_runs SET state='running', runner_id=?, started_at=? WHERE id=? AND state='queued'`
  with a row-count check. Two processes polling the same database cannot both win.
- Exactly **one** in-process runner: an asyncio task started in the application
  lifespan, polling the queue every 2 s and sleeping when idle. Horizontal scaling
  and worker pools are out of scope; the conditional update is the seam if that
  changes.
- A run whose delegation expired between `queued` and claim fails preflight with
  `delegation_expired` rather than executing under stale authority.

### 11. Persistence sketch

Portable SQLAlchemy types only (`String`, `Integer`, `DateTime`, `Text`); naive
UTC datetimes; JSON stored as bounded `Text`. New tables land through the
versioned `schema_migrations` runner specified by ADR-005.

`workflow_runs`

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36)` PK | UUID string |
| `squadron_id` | `VARCHAR(36)` | required; index leads with it (ADR-005) |
| `workflow_type` | `VARCHAR(64)` | catalog value (§2) |
| `workflow_version` | `INTEGER` | 1 |
| `subject_kind`, `subject_id` | `VARCHAR(32)`, `VARCHAR(36)` | nullable |
| `initiated_by_user_id` | `VARCHAR(36)` | nullable for scheduled runs |
| `agent_id`, `agent_version`, `delegation_id` | `VARCHAR(36)`, `INTEGER`, `VARCHAR(36)` | nullable for non-agent runs |
| `state` | `VARCHAR(24)` | §3 |
| `reason_code` | `VARCHAR(48)` | nullable in open states |
| `recovery_status` | `VARCHAR(16)` | `none`/`interrupted`/`recovered`/`failed` |
| `idempotency_key` | `VARCHAR(128)` | unique with `squadron_id` |
| `active_key` | `VARCHAR(160)` | unique, `NULL` when terminal |
| `input_refs`, `output_refs` | `TEXT` | bounded JSON (≤ 8 KiB each) |
| `created_at`, `updated_at`, `started_at`, `finished_at`, `deadline_at`, `last_heartbeat_at` | `DATETIME` | naive UTC |
| `runner_id` | `VARCHAR(64)` | nullable |
| `cancel_requested_at`, `cancel_requested_by_user_id` | `DATETIME`, `VARCHAR(36)` | nullable |
| `retry_of_run_id` | `VARCHAR(36)` | nullable |
| `recovery_attempts` | `INTEGER` | default 0 |

`workflow_run_events` (append-only): `id`, `run_id`, `seq` (unique with
`run_id`), `kind` (`state_transition`/`step_attempt`/`note`), `from_state`,
`to_state`, `reason_code`, `actor_kind` (`user`/`agent`/`system`), `actor_id`,
`occurred_at`, `detail` (bounded JSON).

`workflow_run_steps`: `id`, `run_id`, `step_key` (unique with `run_id`), `seq`,
`tool_name`, `tool_version`, `capability`, `delegation_id`, `state`
(`started`/`succeeded`/`failed`/`skipped`), `attempt`, `input_digest`,
`input_summary`, `output_summary`, `error_class`, `started_at`, `finished_at`.

Repositories return domain entities, never ORM rows; `save` copies every mapped
column through the single mapper; repository methods never commit (AGENTS.md).

### 12. API surface (`P5-10`)

| Endpoint | Permission | Behaviour |
|---|---|---|
| `POST /api/workflows/{type}` | `workflows:manage` | create a run; honours `Idempotency-Key` |
| `GET /api/workflows/runs/{id}` | `workflows:read` | run, events, steps, linked approvals (payload summaries only) |
| `GET /api/workflows/runs` | `workflows:read` | filter by state, type, subject; squadron-scoped in SQL |
| `POST /api/workflows/runs/{id}/cancel` | `workflows:manage` | sets the cancel flag; 409 if already terminal |
| `POST /api/workflows/approvals/{id}/decide` | `approvals:decide` | human decision; 403 for agents and for a self-approving initiator |
| `POST /api/workflows/runs/{id}/retry` | `workflows:manage` | new run with `retry_of_run_id`; 409 unless the source run failed |

Cross-squadron reads return `404`; in-squadron scope denial returns `403`
(ADR-005). Every list path filters in SQL, never post-fetch.

### 13. Check against the acceptance criteria

| Criterion | Where |
|---|---|
| Run record fields and state transitions specified | §3, §11 |
| Retry, cancellation, recovery bounded and testable | §6, §7, §8 |
| Idempotency approach specified | §5 |
| Approval waiting is durable | §4 (row-backed, restart-safe, digest-bound) |
| `P5-03` and `P5-10` can implement directly | §1–§12, plus the defaults in the open questions |

## Consequences

**Positive**

- The durable record is small and boring: three tables, plain constraints, no
  engine. Every guarantee (single active run, once-only effect, no implicit
  approval) is enforced by a constraint or a conditional update rather than by
  runner discipline.
- Because a run is a row, an approval can outlive a restart, a container
  replacement, or a deploy — which is the whole point of "durable".
- Failure is always visible and classified: a run cannot end in an unnamed state.
- Payload minimization keeps the run table from becoming a shadow copy of task,
  mail, and calendar data, so the later retention and audit decisions (ADR-011)
  have one place to act on.

**Negative / costs**

- Three new tables and several indexes in `P5-03`/`P5-04`; the `active_key`
  trick needs a comment in the mapper or someone will "clean up" the `NULL`.
- Two-phase approval (decide, then resume) means an extra poll cycle; acceptable
  for a coordination product, surprising to anyone expecting a synchronous call.
- The in-process runner is single-node by design. A future second backend replica
  would need the claim seam extended before it is safe.
- Fixed retry counts will occasionally be wrong for a specific provider; the
  per-type catalog override is the escape hatch, not a new mechanism.

## Alternatives considered

1. **A workflow engine (Temporal, Celery, a state-machine library).** Rejected:
   new infrastructure, new failure modes, and the spec forbids a workflow
   designer. A row plus a conditional update covers the seven fixed workflows.
2. **Derive run state from the event log on every read.** Rejected: every list
   query would replay history, and the "one active run" constraint could not be
   expressed as a database constraint.
3. **Run everything in one transaction and roll back on failure.** Rejected:
   approval waits span human time (hours), and external effects (mail, calendar)
   are not transactional.
4. **Retry the whole run on any step failure.** Rejected: it re-executes
   successful steps, which is exactly the duplicate-effect bug idempotency exists
   to prevent.
5. **`SELECT ... FOR UPDATE SKIP LOCKED` for the queue.** Rejected: not portable
   to SQLite, and unnecessary at this scale; the conditional update is enough.
6. **Store prompts and completions in the run for debuggability.** Rejected: it
   duplicates sensitive payloads into operational tables and outlives the source
   record. Digests plus references are enough to reconstruct what happened.
7. **Auto-approve after a timeout so unattended runs can finish.** Rejected
   outright: it converts silence into authority (ADR-004 §6).

## Open questions (confirmable defaults, non-blocking)

| # | Question | Default until decided | Owner |
|---|---|---|---|
| W1 | Should a scheduled run that finds no eligible work create a `succeeded` run with zero steps, or no run at all? | Create the run with zero steps and reason `no_work`; an empty run is evidence the schedule fired | Product owner |
| W2 | Is the run deadline 15 minutes for every type, including turnover packages? | Yes for now; turnover may raise it to 30 minutes in the catalog when implemented | Engineering |
| W3 | May the initiating user cancel a run after approval was granted but before the step executes? | Yes — cancellation wins; the approval becomes `invalidated` | Product owner |
| W4 | Are run records readable by every member with `workflows:read`, or only the initiator and admins? | Squadron-scoped read for every member with `workflows:read`; summaries are payload-minimized | Product owner |
| W5 | Retention of terminal runs | Keep with the audit retention decision in ADR-011; do not delete before it lands | Records Manager |
| W6 | Should `task_capture_classification` create a personal task directly, or always produce a draft? | Draft for every scope until the capture UX lands; personal creation is a separate explicit confirm | Product owner |

## Validation

Documentation-only change: this ADR adds
`docs/adr/ADR-010-workflow-persistence.md`, flips its row in
`docs/adr/README.md` to Accepted, and adds the durable workflow invariants to
`AGENTS.md`. No application code, dependency, configuration default, test, or
migration was modified. The backend and frontend baselines were run before and
after the change; the exact commands and results are recorded on issue #12.

State-machine review performed for this ADR:

- Every non-terminal state has at least one outgoing transition.
- Every terminal state has none, and the only way back is a new run id.
- Every state is reachable from `queued`.
- No transition skips `waiting_approval` into execution.
- Every failure path names a `reason_code`, so no run ends unclassified.

## References

- `docs/SQUADRON_PLATFORM_EXPANSION.md` §10 (agent identity and delegation), §11
  (agentic workflows and the workflow list), "Agent/tool execution contract",
  "Approval model", Phase 5 exit criteria, acceptance scenarios 12 and 13
- `docs/adr/ADR-004-role-permission-matrix.md` §3 (`workflows:read`,
  `workflows:manage`, `approvals:read`, `approvals:decide`), §6 (ordered
  evaluation and `approval_required`), §7 (delegable capability classes)
- `docs/adr/ADR-005-data-isolation-migration.md` §1 (tenant key), §4 (migration
  sequence)
- `docs/adr/ADR-006-task-scope-sharing.md` §2 (ownership), §6 (acknowledgment is
  not completion)
- `docs/adr/ADR-008-agent-identity-delegation.md` (in review, PR #136) —
  approval binding, delegation expiry, agent audit fields
- `backend/app/adapters/persistence/sqlalchemy/models.py`,
  `backend/app/adapters/persistence/sqlalchemy/mappers.py` (mapper and
  persistence conventions)
- `backend/app/domain/tasks/urgency.py`, `backend/app/application/services/`
  (pure domain, no clock or I/O inside the rules)
