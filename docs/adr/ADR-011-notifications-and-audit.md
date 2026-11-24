# ADR-011: Notification channels, preferences, and audit retention

- **Status:** Accepted 2026-11-24
- **Ticket:** [#13](https://github.com/anotherhale/str-ready-room/issues/13) (`P0-11`)
- **Requirements:** R-NOTIF-01, R-NOTIF-02, R-NOTIF-03, R-NOTIF-04,
  R-AUDIT-01, R-AUDIT-02, R-AUDIT-03, R-AUDIT-04, R-ARCH-06
- **Depends on:** ADR-001 (deployment, classification, retention defaults),
  ADR-002 (sessions and revocation), ADR-004 (roles, scopes, permissions),
  ADR-005 (tenant key and migration), ADR-006 (task scope and relationships),
  ADR-007 (recurrence events and exceptions)
- **Constrains:** `P2-06`/`#88` (notification domain), `#89` (emission), `#90`
  (API and frontend), `P6-01`/`#40` (audit entry and writer port), `#42`, `#45`,
  `#79`, `#83`, `#84`, `#85`

## Context

The first cut has no notifications and no audit trail. `OperatorSettings` holds
per-operator demo settings only. Every action today is a direct service call
that commits and returns; nothing records who did what, and nothing tells a
person that work arrived.

The expansion needs two things that look similar and must not be built the same
way:

1. **Notifications** — tell the right person that something needs their
   attention, without flooding them, and without ever letting a delivery problem
   change the underlying work.
2. **Audit** — a trustworthy, access-controlled, append-oriented record of
   consequential actions, including agent and workflow actions.

The spec fixes four constraints this ADR must satisfy:

- "Begin with in-app notifications. Add email or other channels only when
  configured and tested."
- "Notification failure must not silently change task/workflow state."
- "Use append-oriented history and avoid storing secrets or unnecessary
  sensitive payloads."
- "The records must be trustworthy and access-controlled."

Acceptance scenario 14 is the sharpest test: a notification failure must not
mark a task acknowledged, approved, or complete. Scenario 15 requires squadron
and team boundaries to hold in notification paths exactly as in query paths.

ADR-004 already fixes `notifications:read`, `notifications:send` and
`audit:read` with scope ceilings, the ordered deny-by-default evaluation, and
the rule that agents may never hold `audit:read`. ADR-006 fixes what a task's
scope means and that visibility is computed once and emits repository filter
keys. This ADR does not revisit either; it decides how events become
notifications, and what an audit record contains.

## Decision

### 1. Two records, two guarantees, two transaction boundaries

| | Audit entry | Notification |
|---|---|---|
| Purpose | Prove what happened | Tell a person what needs attention |
| Written | **Inside** the state change's transaction | **After** that transaction commits |
| On failure | The whole action rolls back; it did not happen | Logged and counted; the action stands |
| Mutability | Append-only | Read state changes; content does not |
| Retention | Indefinite, explicit authorized deletion | Bounded, purged on a schedule |
| Reader | `audit:read` holders (squadron admin only) | The recipient, and nobody else |

This split is the whole design. Audit is a correctness requirement, so it is
synchronous and fail-closed. Notifications are an availability requirement, so
they are asynchronous and best-effort. Building them on one mechanism would
force one of the two guarantees to be wrong.

### 2. Audit: one append-only table, written through one port

`audit_entries` (domain record `AuditEntry`, port `AuditWriter`, adapter in
`adapters/persistence/sqlalchemy/`) is append-only. No update or delete method
exists on the repository. Rows are written by the use case inside the same unit
of work as the change, so a commit that contains a state change also contains
its audit entry.

| Field | Type | Meaning |
|---|---|---|
| `id` | text | ULID-style sortable identifier |
| `squadron_id` | text | Tenant key (ADR-005); indexed first |
| `occurred_at` | datetime | Naive UTC, from the clock port |
| `actor_kind` | `user` \| `agent` \| `system` | Who acted |
| `actor_id` | text | User id, agent id, or `system` |
| `agent_version` | text, nullable | Agent identity version (ADR-008) |
| `initiating_user_id` | text, nullable | The human behind an agent action |
| `correlation_id` | text | Ties one request, workflow run, or agent run together |
| `action` | text | Stable verb from the ADR-004 catalog, e.g. `tasks:complete` |
| `target_kind` | text | `task`, `series`, `membership`, `duty_position`, `approval`, `delegation`, `workflow_run`, `notification`, `audit` |
| `target_id` | text | Identifier of the affected record |
| `scope` | text | `personal` \| `shared` \| `team` \| `squadron` \| `duty_position` |
| `outcome` | `succeeded` \| `denied` \| `failed` | Result of the attempt |
| `source` | `api` \| `workflow` \| `agent` \| `seed` \| `system` | Entry point |
| `changes` | JSON, nullable | Allowlisted field deltas (§5) |
| `request_id` | text, nullable | Transport correlation, never a payload |

`action` reuses the permission-catalog verb where one exists. A write that is
not itself a permission (`tasks:acknowledge` is one; "occurrence generated" is
not) is recorded under the owning verb with a `changes` note, so the audit
vocabulary cannot drift from the authorization vocabulary.

**Fail-closed.** If the audit entry cannot be written, the transaction rolls
back and the caller receives `503` with the typed error code `audit_unavailable`.
This is an operational failure, not an authorization denial, and is distinct
from ADR-004's stable denial codes. It is safe to retry because the mutations it
guards are idempotent (completion, acknowledgment) or safe to re-attempt after a
re-read.

### 3. Audit coverage: writes and denials, not reads

Audited, per spec area 13:

| Area | Actions |
|---|---|
| Membership and roles | invite, activate, suspend, remove, role change, duty-position assignment |
| Tasks | create, update, share/unshare, assign, reassign, acknowledge, hand off, accept, complete, cancel, comment |
| Recurrence | series create/edit/pause/resume/end, occurrence exception, successor generated |
| Duty positions | create, holder change, capability change, deactivate |
| Approvals | request, approve, reject, expire, execute |
| Delegation | grant, revoke, expire |
| Workflow runs | start, retry, cancel, complete, fail, consequential tool action |
| Demo and admin | seed, reset, settings change, integration configuration |
| Audit itself | every read of the audit log, and every authorized deletion |

Also audited: **every denied write attempt** (`outcome = denied`) with the
ADR-004 denial code in `changes`, and every `approval_required` rejection.
Denials are the security signal; without them the log answers "what happened"
but not "who tried".

**Reads are not audited** except audit-log reads. Auditing every task read
would multiply row volume by orders of magnitude and duplicate operational
payloads for no security gain, because read authorization is already enforced
in SQL (ADR-006 §8).

### 4. Notification event catalog and envelope

Seven event kinds, matching the spec's examples. Each is a domain event with a
stable name; adding one is an ADR amendment, not a code-only change.

| Event | Fired when | Default recipients |
|---|---|---|
| `task.assigned` | assignee set or changed | The new assignee (user), or each current holder (team/duty position) |
| `task.updated` | material field change on a shared/team/squadron task | Accountable owner + collaborators, minus the actor |
| `acknowledgment.requested` | a task requires acknowledgment and is assigned | The assignee only |
| `handoff.awaiting_acceptance` | a handoff is proposed | The incoming accountable owner |
| `task.deadline_approaching` | daily scan finds due date inside the warning window | Accountable owner + assignee |
| `recurrence.occurrence_generated` | a successor is created | Accountable owner + assignee of the new occurrence |
| `attention.required` | an approval, workflow, or unowned work item needs a human | Approvers, or squadron admins for unowned work |

Envelope columns: `id`, `squadron_id`, `recipient_id`, `event_kind`,
`target_kind`, `target_id`, `title_key`, `body_params` (JSON, enumerated values
only), `scope`, `aggregated_count`, `first_occurred_at`, `last_occurred_at`,
`read_at`, `aggregation_key`.

`title_key` is a translation/label key, not prose: the frontend renders the
text, so wording changes never require a data migration. `body_params` carries
identifiers and dates, never free text, never a task description, never an email
or calendar body.

### 5. Recipient resolution reuses the visibility policy

Recipients are computed by the same pure policy that decides visibility
(ADR-006 §8), at emission time, in the resource's squadron:

1. Resolve candidate relationships (owner, assignee, collaborators, watchers)
   from the resource itself — never from the request body.
2. Drop any candidate who cannot currently read the resource.
3. Drop the actor. A person is not notified of their own action.
4. Drop any candidate without an `ACTIVE` membership (ADR-006: inert shares are
   retained but produce no delivery).
5. Drop any candidate whose preferences disable the category (§7), except
   mandatory events.

The resulting recipient set is therefore always a subset of the set that could
read the resource. A cross-squadron notification is unrepresentable: step 2
fails for any principal outside the squadron, and `squadron_id` is on every
row.

Watchers (read shares) receive `task.updated` only. They never receive
`acknowledgment.requested`, `handoff.awaiting_acceptance`, or any event that
implies a duty, because a read share never authorizes a verb (ADR-006 §2).

### 6. Aggregation, deduplication, and read state

`aggregation_key = hash(recipient_id, event_kind, target_kind, target_id, bucket)`
where `bucket` is the aggregation window start, or the date for daily events
(`task.deadline_approaching` uses the recipient's local date, so one task
produces at most one reminder per person per day).

- Default window: **15 minutes**, per-user configurable 0–1440 minutes. `0`
  means no aggregation.
- A duplicate inside the window increments `aggregated_count` and moves
  `last_occurred_at`; it does not insert a row.
- An **unread** aggregate absorbs new occurrences; a **read** one starts a new
  row, so a person who cleared an item is told again when it recurs.
- Read state is `read_at` on the recipient's own row. Mark-one and
  mark-all-read are the only mutations. There is no shared read state and no
  "read by team".

### 7. Preferences

`notification_preferences`, one row per user per squadron:
`enabled_kinds` (set), `aggregation_minutes`, `quiet_hours_start`/`_end` (local
time in the user's effective zone), `digest_mode` (`immediate` \| `daily`).

Defaults: every in-app kind enabled, 15-minute aggregation, quiet hours off,
immediate delivery. Quiet hours defer delivery; they never discard an event.

**Mandatory events** cannot be disabled: `attention.required` for an approval
awaiting a human decision, and `acknowledgment.requested`. They record human
accountability; letting a preference suppress them would let a user opt out of
their own duty. Quiet hours still apply to delivery, but the row is created.

### 8. Failure isolation (acceptance scenario 14)

Emission runs **after** the unit of work commits, in its own unit of work:

1. The use case commits the state change and its audit entry.
2. Control returns to the caller only after the notification attempt is
   finished or abandoned.
3. Emission failures are caught, logged with the correlation id, and counted.
   They never propagate, never retry the state change, and never touch task,
   acknowledgment, approval, or workflow state.
4. A bounded in-process retry (3 attempts, short backoff) absorbs a transient
   adapter error. After that the event is **dropped and logged** — there is no
   durable outbox in this increment.

The consequence is explicit: a notification can be lost, and the log says so.
That is acceptable for in-app attention signals and unacceptable for audit, and
the split in §1 is what makes the trade honest. A durable outbox becomes
worthwhile only when an outbound channel (email/webhook) is added; it is listed
as an extension point, not built here.

**Nothing derives state from notifications.** No query joins task state to
notification state; "acknowledged" is never inferred from "the notification was
read". This is the structural reason scenario 14 cannot regress.

### 9. Minimisation: what is never stored

Neither table stores:

- credentials, tokens, session identifiers, or password material;
- task descriptions, comments, or notes bodies;
- email subjects/bodies or calendar event payloads;
- Jev prompts, completions, or retrieved context;
- free-text user input of any kind.

`changes` in an audit entry is an allowlisted delta over enumerated fields:
`status`, `scope`, `assignee_id`, `accountable_owner_id`, `due_date`,
`due_at_utc`, `priority`, `is_active`, `team_id`, `duty_position_id`,
`holder_id`, `role`, `membership_status`, `decision`, `revision`. Each value is
stored only if it is an identifier, enum, date, or boolean. A title change is
recorded as `{"title": "changed"}`, never as the before/after text.

### 10. Retention and access control

| Data | Retention | Deletion |
|---|---|---|
| Audit entries | Indefinite (ADR-001 Q5 default) | Explicit authorized deletion only, itself audited |
| Notifications, unread | 90 days | Scheduled purge |
| Notifications, read | 30 days after `read_at` | Scheduled purge |
| Preferences | Life of the membership | Removed with the membership |

Retention values are operator settings with the defaults above; the purge job
is a scheduled application task, not a database trigger, so it is portable and
observable.

Access control:

- **Notifications** are personal-scope records. A user reads only rows where
  `recipient_id` is themselves, in a squadron where their membership is
  `ACTIVE`. `notifications:read` is the permission; the row filter is the
  boundary. Cross-squadron or cross-user reads return `404`, consistent with
  ADR-005.
- **Audit** requires `audit:read`, which only `squadron_admin` holds, with a
  `sq-only` ceiling. Reads are squadron-scoped and every read is itself audited.
  `read_only` users do not see the audit log (ADR-004 Q4).
- **Agents** can never hold `audit:read` and can never delete audit rows
  (ADR-004 §6, never-delegable list). An agent may cause an audit entry; it may
  not read or erase the log.
- A squadron-wide announcement is the only user-composed notification. It
  requires `notifications:send`, is approval-gated at officer level (ADR-004
  Q5), and is audited like any other consequential action. System-emitted
  events need no user permission because no user is acting.

### 11. Channels: in-app now, an explicit seam for later

In scope: the in-app notification center, its API, and its read state.
Out of scope: email, SMS, push, chat webhooks, and any external delivery.

The seam is a `NotificationChannel` port with one implementation
(`InAppChannel`). Adding a channel means adding an adapter and a preference
field, not changing recipient resolution or the event catalog. Until a channel
exists and is tested, it is not configurable — the spec's "only when configured
and tested" rule.

### 12. Migration and compatibility

Three new tables — `notifications`, `notification_preferences`,
`audit_entries` — added by the versioned forward-only runner (ADR-005 §4). Each
carries `squadron_id` and leads its indexes with it. No existing table changes,
no row is rewritten, and there is nothing to backfill: no historical action has
an audit entry, and inventing one would be a lie.

Current behaviour is unchanged. The single-user demo has one principal, so the
actor-exclusion rule (§5 step 3) means the operator's own actions produce no
notifications; the notification center is empty until a second principal exists.
No existing endpoint gains a notification side effect that could change its
response.

### 13. Check against the acceptance scenarios

| Scenario | Result |
|---|---|
| 14. Notification failure does not silently mark a task acknowledged, approved, or complete | Emission is post-commit, best-effort, and never writes task/workflow state; no state is ever derived from notification state (§1, §8) |
| 15. Squadron and team boundaries are enforced in API, query, search, notification, and AI-context paths | Recipient resolution is a subset of the visibility policy at emission time; every row carries `squadron_id`; cross-squadron reads return `404` (§5, §10) |

## Consequences

**Positive**

- The one guarantee each mechanism needs is structural, not conventional: audit
  cannot be silently skipped, and notification failure cannot corrupt work.
- Audit vocabulary is the permission vocabulary, so "what is audited" and "what
  is authorized" cannot drift apart.
- Minimisation is a schema property. There is no free-text column to leak into.
- The notification center needs no new authorization model: it is personal-scope
  rows plus an existing permission.

**Negative / costs**

- A notification can be lost with no automatic redelivery. The log is the only
  record. Adding an outbound channel forces a durable outbox.
- Fail-closed audit means an audit-table problem is a write outage. That is the
  intended trade, but it must be monitored as a first-class failure.
- Denials are audited, so a hostile client can inflate the log. Volume controls
  (rate limiting at the API edge) belong to the security lane, not here.
- `body_params` and `title_key` push wording into the frontend; the backend
  cannot send a fully-rendered sentence.

## Alternatives considered

1. **Emit notifications in the same transaction as the change.** Rejected: a
   notification adapter failure would roll back a valid completion, which is
   exactly the coupling scenario 14 forbids.
2. **Make audit best-effort to avoid write outages.** Rejected: an audit log
   that can silently miss entries is not evidence. The spec requires
   trustworthiness before volume.
3. **One `events` table for both audit and notifications.** Rejected: opposite
   retention, mutability, and reader rules in one table force per-row type
   checks in every query and make "who may read this row" ambiguous.
4. **Audit every read.** Rejected: order-of-magnitude volume growth, duplicate
   operational payloads, and no security gain over SQL-enforced read
   authorization.
5. **Resolve recipients from the request or the UI's current view.** Rejected:
   it makes the notification path a second authorization implementation, and
   scenario 15 fails the first time the two disagree.
6. **A durable outbox now.** Rejected as premature: in-app delivery is a
   single-process write, the failure mode is a lost attention signal, and the
   outbox only pays for itself once an external channel exists.
7. **Let users disable every notification kind.** Rejected: a person could opt
   out of an approval request or an acknowledgment duty, which is a
   human-accountability control, not a preference.

## Open questions (confirmable defaults, non-blocking)

| # | Question | Default until decided | Owner |
|---|---|---|---|
| N1 | Should a watcher (read share) receive `task.deadline_approaching`? | Yes — it is a read-only awareness signal, and watchers can already read the task | Product owner |
| N2 | Is the daily reminder sent once per task or once per task per assignee change? | Once per task per recipient per day; an assignee change starts a new bucket | Product owner |
| N3 | Should quiet hours delay `attention.required` for approvals? | Yes, delivery is delayed, but the row is created and the approval inbox is unaffected | Squadron Commander |
| N4 | Are audit entries visible to the accountable owner for their own personal resources? | No. `audit:read` is the only path; ownership is not an audit grant | Security Officer |
| N5 | Should notification purge run per squadron or globally? | Per squadron, so one tenant's volume cannot delay another's retention | Engineering |
| N6 | Do squadron admins receive `attention.required` for every unowned task? | Only for tasks flagged by the operational scan, aggregated daily, never one row per task | Product owner |

## Validation

Documentation-only change: this ADR adds
`docs/adr/ADR-011-notifications-and-audit.md`, flips its row in
`docs/adr/README.md` to Accepted, and records the durable notification and audit
invariants in `AGENTS.md`. No application code, configuration default,
dependency, test, or migration is modified.

The backend baseline was run before and after the change. It is **red on `main`
for an unrelated, pre-existing defect** ([#137](https://github.com/anotherhale/str-ready-room/issues/137),
fixed by PR #138): `InMemoryMailboxProvider` does not implement
`MailboxProvider.purge`, so every integration test that builds the double errors
at setup with `TypeError: Can't instantiate abstract class
InMemoryMailboxProvider without an implementation for abstract method 'purge'`.
This change touches no Python file, so the failure count is identical before and
after; the exact commands and results are recorded on issue #13.

| Acceptance criterion | Section |
|---|---|
| Notification events, recipients, aggregation, and preferences are specified | §4, §5, §6, §7 |
| Failure isolation semantics are explicit | §1, §8 |
| Audit record shape, coverage, and minimisation are specified | §2, §3, §9 |
| Retention and access control are specified | §10 |
| `P2-06`, `P6-01`, and `P6-02` can implement directly | §2–§12 plus the open-question defaults |

## References

- `docs/SQUADRON_PLATFORM_EXPANSION.md` §7 (notifications and acknowledgment),
  §13 (audit and activity history), acceptance scenarios 14 and 15
- `docs/adr/ADR-001-deployment-classification.md` — retention and
  data-handling defaults (Q5)
- `docs/adr/ADR-004-role-permission-matrix.md` §2 (`notifications:read`,
  `notifications:send`, `audit:read`), §4 (scope model and evaluation order),
  §6 (agent-delegable and never-delegable permissions), Q4, Q5
- `docs/adr/ADR-005-data-isolation-migration.md` §1 (tenant key), §4
  (migration sequence)
- `docs/adr/ADR-006-task-scope-sharing.md` §2 (relationships), §5 (scope
  inheritance), §8 (single visibility policy and filter keys)
- `docs/adr/ADR-007-shared-recurrence.md` §3 (holder changes), §4 (exceptions)
