# ADR-006: Task scope, sharing, and accountable-ownership semantics

- **Status:** Accepted 2026-11-24
- **Ticket:** [#8](https://github.com/anotherhale/str-ready-room/issues/8) (`P0-06`)
- **Requirements:** R-TASK-01, R-TASK-03, R-TASK-12, R-AUTHZ-03, R-ARCH-06
- **Depends on:** ADR-001 (deployment and classification), ADR-002 (sessions),
  ADR-004 (roles and scopes), ADR-005 (tenant key and migration)
- **Constrains:** `P2-01`/`#35` (domain), `P2-02`/`#36` (acknowledgment),
  `P2-03`/`#37` (visibility rules), `P2-04`..`P2-12`, and ADR-007 (`#9`)

## Context

A `Task` today has one `owner_id`, and that id is also the acting user. Every
repository read and write filters on it (`TaskRepository.get_by_id(task_id,
owner_id)`, `list(criteria, owner_id)`). `AuthorizationPolicyService.decide()`
then rejects any resource whose owner is not the principal, with the code
`forbidden_ownership`. The model therefore has exactly one relationship: "this
is mine".

The expansion needs four visibility scopes (personal, shared, team, squadron)
and four distinct relationships — accountable owner, assignee, collaborators,
watchers. The specification is explicit that "shared tasks should not imply that
every member is individually responsible" and that accountable ownership,
assignment, collaboration, and watching are different things.

ADR-004 already fixes the ordered, deny-by-default evaluation
(membership → permission → scope → relationship → approval), the five scope
values, the per-grant scope ceiling, the stable denial codes, and the rule that
resource relationships may only **narrow** a decision. ADR-005 fixes
`squadron_id` as the tenant key, retains `owner_id`, and requires visibility to
be expressed as a `ScopeCriteria` built in exactly one place. What is still
undecided, and what this ADR settles, is what a task's scope *means*, who holds
which relationship, and exactly who may do what at each scope.

Two spec statements need reconciling before implementation:

- "Exactly one accountable owner" (a task is never nobody's job) versus
- "Which shared tasks have no accountable owner?" (the operational scan must be
  able to report unowned work).

§7 resolves this without weakening either statement.

## Decision

### 1. Four task scopes; duty position is a relationship, not a fifth scope

A task carries exactly one `scope` from `TaskScope`:

| Scope | Who can find it | Intended use |
|---|---|---|
| `personal` | The accountable owner, plus named share recipients | Default for capture. One person's own work; a share is an explicit exception |
| `shared` | The accountable owner, plus named share recipients | Work explicitly distributed to named people with no team or squadron audience |
| `team` | Active members of the owning team, plus the accountable owner and named shares | Team work that every team member may see |
| `squadron` | Active members of the squadron | Work the whole squadron may see |

**`duty_position` is not a task visibility scope.** The specification lists four
task visibility scopes, and lists a duty position as one *kind of assignee*. A
duty-routed responsibility is a normal task with a `team` or `squadron` scope
whose assignee is the duty position; the current holder gains authority through
the ADR-004 §5 duty-position capability path, not through a fifth visibility
rule. This keeps one access rule per scope instead of two overlapping ones.
ADR-004's `duty_position` scope remains authoritative for genuinely duty-scoped
resources (for example turnover packages in Phase 6).

**`personal` and `shared` have the same access shape and are still distinct.**
Both are "owner plus explicit shares", because ADR-004 defines personal scope as
"the owner, plus anyone the owner explicitly shared it with". They differ in
declaration and discovery:

- `personal` is the default, is listed only in the owner's own views, and may
  carry zero shares.
- `shared` requires at least one collaborator (a write share). A `shared` task
  with no recipient is a contradiction and is rejected at validation time.
- Neither is ever returned by a team or squadron scan.

Implementing them as two declarations over **one** access computation is
deliberate: there is exactly one place where task visibility can be wrong.

### 2. The four relationships

| Relationship | Cardinality | Target | Meaning |
|---|---|---|---|
| **Accountable owner** | exactly 1 | user | The person answerable for the outcome. Retained from `owner_id` |
| **Assignee** | 0 or 1 | typed target: user, team, or duty position | The person or body expected to do the work now |
| **Collaborator** | many | user | Named participant who may write |
| **Watcher** | many | user | Named observer who may read and be notified |

Invariants, all enforced in the domain entity and unit-tested in `#35`:

1. `accountable_owner_id` is always set. It is never null, never empty, and
   never changes as a side effect of assignment, handoff, or scope change —
   changing it is an explicit `tasks:assign`/`tasks:update` action that is
   audited.
2. At most one assignee. A second assignment replaces the first; it does not
   accumulate.
3. The assignee target must exist in the same squadron. A duty-position target
   must have a current holder or the assignment is rejected — routing work to an
   empty position would create invisible work.
4. Collaborator and watcher ids are unique per task. A user is at most one of
   the two: promoting a watcher to collaborator upgrades the existing grant
   rather than adding a second row.
5. The accountable owner and the assignee are implicitly participants. They are
   not stored as collaborators or watchers, and adding them is rejected rather
   than silently ignored.
6. A `personal` or `shared` task cannot have a team or duty-position assignee:
   those targets only exist for a team or squadron audience. It may have a user
   assignee, who must also hold a share on the task.
7. Collaborators and watchers must be members of the task's squadron. Their
   membership state does not delete the row (history is kept) but a
   non-`ACTIVE` member's share is inert (§7).

### 3. One share table, two access levels

Explicit sharing is stored once, as `task_shares(task_id, squadron_id,
user_id, access)` where `access ∈ {read, write}`, primary key
`(task_id, user_id)`.

- A `write` share **is** a collaborator. A `read` share **is** a watcher.
- There is no second "collaborators" table and no separate "shared with" list.
  Storing the same person in two places is how "the UI says she can edit but the
  API says no" bugs happen.
- A read share never authorizes a write (ADR-004 §4). Promotion to `write` is a
  distinct, audited grant.
- Revoking a share deletes the row; revoking the last share on a `shared` task
  is rejected until the scope is narrowed to `personal` in the same operation.

### 4. Who may do what, per scope

These rules apply **after** the ADR-004 permission gate and scope-ceiling check
and can only narrow the outcome. A `member` holding `tasks:update` still cannot
update a personal task they do not own.

| Verb | `personal` | `shared` | `team` | `squadron` |
|---|---|---|---|---|
| `tasks:read` | owner, read/write share | owner, read/write share | owner, shares, active team members | owner, shares, active squadron members |
| `tasks:comment` | same as read | same as read | same as read | same as read |
| `tasks:update` | owner, write share | owner, write share | owner, write share, owning team lead | owner, write share, `officer`, `squadron_admin` |
| `tasks:assign` | owner | owner, write share | owner, write share, owning team lead | owner, write share, `officer`, `squadron_admin` |
| `tasks:share` | owner | owner | owner, write share, owning team lead | owner, write share, `officer`, `squadron_admin` |
| `tasks:acknowledge` | assignee | assignee | assignee, or a member of the assigned team / current holder of the assigned position | same as `team` |
| `tasks:complete` | owner, assignee, write share | owner, assignee, write share | owner, assignee, write share, owning team lead | owner, assignee, write share, `officer`, `squadron_admin` |
| `tasks:reopen` | owner | owner | owner, owning team lead | owner, `officer`, `squadron_admin` |
| `tasks:handoff` | owner, assignee | owner, assignee | owner, assignee, owning team lead | owner, assignee, `officer`, `squadron_admin` |
| `tasks:delete` | owner **and** `squadron_admin` | owner **and** `squadron_admin` | owning team lead **and** `squadron_admin` | `squadron_admin` |

Notes that prevent the table from being misread:

- The "and `squadron_admin`" cells mean `tasks:delete` is granted to
  `squadron_admin` only (ADR-004 §3). A team lead therefore cannot delete a task
  despite the row; the row states the scope condition, not a grant.
- `read_only` appears nowhere in a mutating column. It holds `tasks:read` only.
- A watcher never gains a mutating verb. Watching is not collaborating.
- The **accountable owner never loses read access** to their own task, at any
  scope, and while their membership is `ACTIVE`.
- Denial codes are unchanged: `forbidden` when the permission is absent,
  `forbidden_scope` when the scope or relationship does not reach,
  `forbidden_ownership` for personal-scope denials, and `404` for any id in
  another squadron (ADR-005 §2).

### 5. Scope defaults and inheritance

| Origin | Scope |
|---|---|
| Quick capture, manual creation with no scope given | `personal` |
| Creation naming a team, by a grant whose ceiling reaches `team` | `team` |
| Creation naming the squadron, by a grant whose ceiling reaches `squadron` | `squadron` |
| Calendar event capture, mailbox capture | `personal` — the capture belongs to the capturing user |
| Recurrence occurrence | Inherits the series' scope at creation |
| Successor from completion | Inherits the predecessor's scope and tenant key |
| Handoff / reassignment | Scope is unchanged; only relationships move |
| Jev or agent draft | Whatever the human confirms; an agent never selects a wider scope than the delegating grant allows |

An unknown, missing, or unparsable scope is `personal` with owner-only access.
No implicit widening exists: there is no "public" default, and a team or squadron
task is only that scope when the creator explicitly asked for it.

**Narrowing is allowed; widening is deliberate.** A scope change requires
`tasks:share`. Widening additionally requires the actor's grant ceiling to reach
the target scope, and is rejected with `forbidden_scope` otherwise. Narrowing a
task keeps its explicit shares — the people who were told about the work keep
their access — so narrowing never silently hides work from a collaborator who
was working on it.

### 6. Acknowledgment, reassignment, and handoff

Acknowledgment is separate from completion, and this ADR fixes only the
authority and the invariants; `#36` implements the state machine and `#39` the
handoff states.

- Acknowledgment is performed by **one human user** and recorded with that user
  id. An agent may never acknowledge (ADR-004 §6).
- Permitted acknowledger: the user assignee; or, for a team or duty-position
  assignee, an active member of that team or the current holder of that position.
- Acknowledging never changes `status`, and completing never implies
  acknowledgment. A task may be completed without ever being acknowledged, and
  the scan reports the difference.
- Reassignment (any change of assignee) clears `acknowledged_at` and
  `acknowledged_by`, because the new assignee has not accepted the work.
- Handoff never changes the accountable owner implicitly. If the outgoing
  person's accountability ends, the same operation must name the incoming
  accountable owner; an operation that would leave a handoff with no accountable
  owner is rejected. Responsibility history is append-only and keeps the
  outgoing party.

### 7. "No accountable owner" is a state of membership, not a null column

`accountable_owner_id` is never null. The scan's "tasks without an owner" item
means **"tasks whose accountable owner is not an `ACTIVE` member"** — the owner
was suspended, removed, or never had their membership activated. This satisfies
both spec statements without a nullable owner:

- The task is surfaced prominently as needing reassignment.
- Until reassigned it is readable and writable by `squadron_admin` and by the
  owning team lead at `team` scope, so the work does not become unreachable.
- No other actor gains access because the owner is inactive. Inert is not
  "everyone can see it now".
- Reassignment is the documented fix, and it is audited.

Shares held by non-`ACTIVE` members are likewise **inert**: retained for history,
granting nothing, restored on reactivation. This is the same fail-closed rule
ADR-004 applies to membership, applied to shares.

### 8. Enforcement: one policy, one criterion

- **`TaskAccessPolicy`** (or equivalent, `#37`) is the single pure rule set
  answering read/update/assign/acknowledge/complete/reopen/delete for an actor
  and a task. It lives in the domain, imports no framework, and returns a
  decision plus a denial code.
- **List paths do not post-filter.** The policy also emits the visibility keys
  (owner, assignee, share, team, squadron) that the application places into the
  ADR-005 `ScopeCriteria`; the repository filters in SQL. A list endpoint that
  fetches rows and filters in Python is a defect, because it leaks through
  counts, pagination, and timing.
- **Every read path uses it**: task list, detail, dashboard and scan sections,
  briefing, search, recurrence series, calendar/mail provenance, notifications,
  turnover packages, exports, and Jev context assembly. ADR-005 §7 lists the
  matrix; this ADR adds task relationships to it.
- **The frontend never decides visibility.** It maps a server-derived state to a
  label, badge, or disabled control. It does not compute scope.
- **Every relationship change is audited**: scope change, share grant, share
  revoke, assignment, reassignment, acknowledgment, handoff, and owner change.
  The audit entry records actor, task, before, and after. `#40` owns the audit
  domain; this ADR only requires that these transitions emit entries.

### 9. Compatibility and migration

- `owner_id` remains, and remains the column every existing query uses, until
  `#35`/`#41` introduce `accountable_owner_id`; the two are kept equal during
  migration and `owner_id` becomes a compatibility alias for reads.
- Backfill: every existing task becomes `scope = 'personal'`,
  `accountable_owner_id = owner_id`, no assignee, no shares. Today's visibility
  is preserved exactly, so `forbidden_ownership` behaviour and the existing
  single-user tests stay valid.
- No existing demo data is deleted or rewritten into shared scope. ADR-005 §4
  already maps each table into the bootstrap squadron; this ADR adds no second
  backfill.

### 10. Check against the acceptance scenarios

| Scenario | Result |
|---|---|
| 1. Two members see authorized squadron-shared tasks but not each other's private tasks | `squadron` scope grants read to active members; `personal` grants read to the owner and shares only (§1, §4) |
| 2. A team lead creates a shared task, assigns an accountable owner, adds collaborators | `tasks:create` + `tasks:assign` + `tasks:share` at `team` ceiling; owner is explicit, collaborators are `write` shares (§2, §3, §4) |
| 3. An assignee acknowledges without completing | `tasks:acknowledge` by the assignee changes no status (§6) |
| 4. A task is handed off and accepted, preserving history and original responsibility | Handoff requires a named incoming accountable owner; responsibility history is append-only (§6) |

## Consequences

**Positive**

- One visibility computation for every read path, so list, detail, search, and
  AI context cannot disagree.
- Accountable ownership is structural, not a convention: shared work always has
  one answerable person.
- One share table removes the drift between "who is listed" and "who can act".
- The duty-position decision keeps Phase 2 free of a fifth visibility rule and
  keeps ADR-004's duty-scope path for the resources that need it.
- Backfill is a no-op behaviourally: existing tasks are personal and owner-only.

**Negative / costs**

- Two declarations (`personal`, `shared`) over one rule need a documented
  rationale or a future reader will "simplify" one away.
- Requiring a recipient for `shared` tasks is a validation rule the API must
  surface clearly.
- The "inert share" and "inactive owner" rules add branches to the policy and
  must be covered by negative tests, not just happy-path ones.
- `tasks:delete` becomes practically admin-only, which will surprise a team lead
  who created the task. That is the ADR-004 matrix, not a new restriction.

## Alternatives considered

1. **Replace `owner_id` with a polymorphic `owner` (user/team/position).**
   Rejected: it collapses four relationships into one field, and the spec
   explicitly forbids "shared implies everyone is responsible". It also breaks
   every existing query and test for no product gain.
2. **A separate `task_collaborators` and `task_watchers` table.** Rejected: the
   same person then has two sources of truth for access, and the UI lists and
   the authorization check drift. One share row with an access level is smaller
   and cannot disagree with itself.
3. **Add `duty_position` as a fifth task scope.** Rejected for tasks: the
   specification names four task visibility scopes and treats duty position as
   an assignee kind. Two overlapping scope mechanisms would produce two
   different answers to "can this person see this task".
4. **Nullable `accountable_owner_id` so the scan can find unowned tasks.**
   Rejected: nullable ownership makes "nobody is responsible" a representable
   state with no repair path, and every read path then needs a null branch. §7
   gets the same operational signal from membership state.
5. **A generic ACL or policy language.** Out of scope by the ticket and by
   ADR-004. Four scopes and one share table do not need an engine.

## Open questions (confirmable defaults, non-blocking)

| # | Question | Default until decided | Owner |
|---|---|---|---|
| T1 | Should a `team`-scoped task be visible to `officer`/`squadron_admin` outside the owning team? | Yes for `officer` and `squadron_admin` write authority per §4, read for all active members only at `squadron` scope. Revisit if squadron leadership needs read across teams | Product owner |
| T2 | Does a `squadron` task ever need an explicit-share-only mode? | No. `shared` covers that; a squadron task is squadron-visible | Product owner |
| T3 | Should watchers receive notifications by default in Phase 6? | Yes, subject to per-user notification preferences (`#90`); watching is meaningless without it | Product owner |
| T4 | Can a `read_only` member be a collaborator? | No: a collaborator must be able to write, and `read_only` holds no mutating grant. They can be a watcher | Engineering |
| T5 | Is the accountable owner ever a team or duty position? | No. Accountability is human and individual (ADR-004 §6: agents and bodies do not hold human accountability). A team or position can be the *assignee* | Product owner |

## Validation

Documentation-only change: this ADR adds
`docs/adr/ADR-006-task-scope-sharing.md`, flips its row in `docs/adr/README.md`
to Accepted, and records the durable task-visibility invariants in `AGENTS.md`.
No application code, configuration default, dependency, or test was modified. The
backend baseline was run before and after the change and stayed green; the exact
commands and results are recorded on issue #8.

| Acceptance criterion | Section |
|---|---|
| Scope semantics and defaults are unambiguous | §1, §5 |
| The four ownership roles and their invariants are defined | §2, §3 |
| Permission rules per scope are specified | §4 |
| Share grant/revoke semantics are specified | §3, §5, §7 |
| `P2-01` and `P2-03` can implement directly | §1–§8, plus the open-question defaults |

## References

- `docs/SQUADRON_PLATFORM_EXPANSION.md` §2 (tasks and collaboration), §1
  (operations), acceptance scenarios 1–4
- `docs/adr/ADR-004-role-permission-matrix.md` §3 (task permissions), §4 (scope
  model and evaluation order), §5 (team-lead and duty-position authority), §6
  (approval-gated and non-delegable permissions)
- `docs/adr/ADR-005-data-isolation-migration.md` §1 (tenant key), §2 (enforcement
  and `ScopeCriteria`), §7 (isolation test matrix)
- `backend/app/domain/authorization/authorization_service.py` (current
  permission + ownership decision and `forbidden_ownership`)
- `backend/app/application/ports/persistence.py` (`TaskRepository`, currently
  owner-scoped)
