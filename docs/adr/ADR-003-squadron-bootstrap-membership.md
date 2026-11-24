# ADR-003: Squadron bootstrap, invitation, and membership lifecycle

- **Status:** Accepted — 2026-11-24
- **Date:** 2026-11-24
- **Ticket:** [#5](https://github.com/anotherhale/str-ready-room/issues/5) (`P0-03`)
- **Deciders:** READY ROOM engineering
- **Supersedes:** none
- **Constrained by:** ADR-001 (deployment and classification), ADR-002 (local
  credentials and server-side sessions), ADR-004 (roles, scopes, evaluation
  order), ADR-005 (tenant key and migration)
- **Constrains:** #16 (P1-01 squadron aggregate), #18 (P1-03 permissions),
  #19 (P1-04 scope authorization), #20/#21 (P1-05/P1-06 persistence),
  #22/#23 (P1-07/P1-08 services), #27/#28/#29 (P1-12..P1-14 endpoints),
  #30/#31 (P1-15/P1-16 UI), #33 (P1-18 seed and reset), #34 (P1-19 isolation tests)
- **Requirements:** R-SQDN-02, R-SQDN-12, R-ARCH-06

## Context

READY ROOM today has no squadron and no membership. Identity is a single
configured operator (`SingleUserAuthProvider`) and every row is filtered by one
`owner_id`. The expansion needs one squadron boundary, a membership lifecycle
(`INVITED`, `ACTIVE`, `SUSPENDED`, `REMOVED`), and a rule that removal and
revocation invalidate access — including sessions and caches.

Three neighbouring decisions already fix the surrounding shape:

- **ADR-002** makes sessions server-side rows and requires that a session is
  valid only while the user's membership is `ACTIVE`; a membership change is a
  revocation trigger.
- **ADR-004** makes membership state the *first* authorization step
  (`forbidden_membership`), keeps `members:invite` and `members:manage` at
  squadron scope and administrator-only, and forbids self-escalation.
- **ADR-005** gives the bootstrap squadron a deterministic `uuid5` id and maps
  existing owner-scoped rows into it, creating one `ACTIVE` membership per
  distinct owner and promoting exactly one to `squadron_admin`.

What is still undecided, and what this ADR settles, is *how the first
administrator comes into existence without a public admin endpoint*, *what an
invitation is*, *which membership transitions are legal and who may perform
them*, and *what happens to a person's owned work when their membership stops
being active*.

The deployment target is a self-hosted single host (ADR-001). There is no
external identity provider, no mail relay, and no public internet ingress
assumed. Every mechanism here must work with those constraints.

## Decision

### 1. One squadron per installation, with a deterministic identity

An installation holds **exactly one** squadron. Multi-squadron tenancy is out of
scope; the squadron is a security boundary, not a tenant selector. Consequences:

- There is no "choose your squadron" input anywhere in the request path.
- The squadron id is the deterministic `uuid5` value from ADR-005
  (`ready-room.bootstrap.squadron`), so a migration, a fixture, and a restored
  snapshot agree without a lookup.
- A user holds **at most one** membership, enforced by a unique constraint on
  `(squadron_id, user_id)` and by the singleton squadron itself. "The current
  squadron" is always resolved from the principal's membership, never from a
  request field and never from "the first row".
- A second squadron cannot be created through the API. Adding one later is an
  ADR, not a feature flag.

### 2. Bootstrap is an operator-run CLI command, never an HTTP route

The first administrator is created by an explicit, operator-invoked command run
inside the deployment, for example:

```text
python -m app.bootstrap --admin-id <user-id> --admin-name "<display name>"
```

There is **no** `POST /api/squadron/bootstrap`, no first-run admin web form, and
no "if no admin exists, let anyone register" fallback. An unauthenticated
endpoint that mints an administrator is a permanent privilege-escalation hole;
the deployment boundary is the correct place to establish the first principal.

**Bootstrap steps, in one transaction:**

1. Insert the squadron with its deterministic id if absent.
2. Ensure the administrator user exists (credential row per ADR-002's local
   credential store) and is not suspended.
3. Insert or reactivate the administrator's membership as `ACTIVE` with role
   `squadron_admin`.
4. Write an `audit` entry recording the bootstrap (actor `system:bootstrap`).

**Idempotency and restart safety.** The command is safe to re-run: an existing
squadron is reused, an existing active administrator is left alone, and the
command reports the resulting state instead of failing. It never creates a
second squadron or a second bootstrap administrator. Concurrency is resolved by
the deterministic primary key: the second writer's insert conflicts, and the
command then takes the "already bootstrapped" path.

**Demo profile.** `environment=demo` seeds a synthetic squadron and users during
seed (ADR-005 §5) instead of requiring the CLI. The demo path uses the same
bootstrap function, so there is one code path and one set of invariants. Seeding
remains guarded by `seed_version` and the "any tasks exist?" check.

**Uninitialized deployment.** If the application starts with no squadron or no
active administrator, every squadron-scoped endpoint returns `503` with the
typed code `not_bootstrapped`, and login refuses with the same code. It never
degrades into permissive behaviour, and `/api/health` still answers so an
operator can see the deployment is up. The state is a deployment condition, not
a credential error, which is why it is not `401`.

### 3. Invitations are records with hashed, single-use, expiring tokens

An invitation is the only way a new person joins the squadron. It is created by
a `squadron_admin` (the only role holding `members:invite`), and it carries:

| Field | Meaning |
|---|---|
| `squadron_id` | The singleton squadron; never supplied by the invitee |
| `invited_by` | The administrator who issued it |
| `role` | The role the invitee will hold on acceptance (default `member`) |
| `team_id` | Optional proposed team; may be assigned later |
| `token_hash` | SHA-256 of a 256-bit random token; the plaintext is never stored |
| `expires_at` | Default **7 days** after issue; configurable 1–30 days |
| `accepted_at`, `revoked_at`, `revoked_by` | Lifecycle timestamps |

**Token handling.** The plaintext token is returned exactly once, to the issuing
administrator, and is displayed in-app for out-of-band handover. Email delivery
is out of scope for this phase. Tokens are stored only as a hash, are
**single-use**, and are compared in constant time. Lookup is by hash, so an
attacker cannot enumerate invitations.

**Invitation states** are derived, not stored as a mutable status column:

```text
PENDING   accepted_at IS NULL AND revoked_at IS NULL AND expires_at > now
EXPIRED   accepted_at IS NULL AND revoked_at IS NULL AND expires_at <= now
ACCEPTED  accepted_at IS NOT NULL
REVOKED   revoked_at IS NOT NULL
```

Deriving expiry removes a background job as a correctness dependency: an
invitation becomes unusable the moment its timestamp passes, whether or not any
process has run.

**Acceptance** (`POST /api/invitations/accept`, unauthenticated but
invitation-token authorized) does all of the following in **one transaction**:

1. Resolve the invitation by token hash and reject any state other than
   `PENDING` with the uniform code `invalid_invitation` — no distinction between
   unknown, expired, revoked, and already-accepted tokens, so the endpoint is not
   an oracle.
2. Create the user's credential (or attach to an existing user with no
   membership) using the invitee-chosen password and display name.
3. Insert the membership as `ACTIVE` with the role recorded on the invitation.
   The invitee **cannot** choose or change the role, the squadron, or the team.
4. Mark the invitation accepted.
5. Write an audit entry.

**Inviter bounds.** An administrator may not issue an invitation at a role whose
grant set exceeds their own, and may not invite on behalf of another squadron.
Only `squadron_admin` holds `members:invite`, so in the current matrix this
bound is trivially satisfied; it is stated so that a later role grant cannot
silently widen it.

**Revocation.** An administrator revokes a `PENDING` invitation with
`members:manage`. Revocation is idempotent. Expired and revoked invitations are
retained for audit and never deleted.

### 4. Membership states and legal transitions

A membership has exactly one state. Only `ACTIVE` authorizes anything.

| From | To | Actor | Trigger | Side effects |
|---|---|---|---|---|
| — | `INVITED` | `squadron_admin` | Invitation issued | Invitation row created; no access |
| `INVITED` | `ACTIVE` | The invitee | Invitation accepted | Credential created; role assigned; audit |
| `INVITED` | `REMOVED` | `squadron_admin` | Invitation revoked | Invitation revoked; retained for audit |
| `ACTIVE` | `SUSPENDED` | `squadron_admin` | Suspension | All sessions revoked; work retained; reassignment flagged |
| `SUSPENDED` | `ACTIVE` | `squadron_admin` | Reinstatement | Shares and duty authority restored; new login required |
| `ACTIVE` | `REMOVED` | `squadron_admin` | Removal | All sessions revoked; duty positions vacated; reassignment required |
| `SUSPENDED` | `REMOVED` | `squadron_admin` | Removal | Same as above |
| `REMOVED` | `ACTIVE` | `squadron_admin` via a **new invitation** | Re-invitation and acceptance | Role from the new invitation; history retained |

Everything else is rejected with `409` and a typed code. In particular:

- **Removal is terminal for access, not for data.** There is no direct
  `REMOVED → ACTIVE` action. A removed person returns only through a fresh
  invitation and acceptance, so re-entry is always an explicit, audited
  administrative act. The membership row and its history are reused, so shares
  and historical accountability stay attached to the same identity.
- **`INVITED` is not a weak `ACTIVE`.** An invited person cannot authenticate,
  cannot read, and holds no role in any decision.
- **No self-transition.** An actor may never change its own membership, and
  `members:manage` cannot target the acting principal (ADR-004 §7).
- **Last-administrator guard.** A transition that would leave the squadron with
  zero `ACTIVE` `squadron_admin` members is rejected with `409
  last_administrator`. Recovery from a genuinely locked-out installation is the
  operator procedure in ADR-005 §6, not a route.
- **Role changes** are membership updates, not transitions. They revoke the
  affected user's sessions (ADR-002) and take effect on the next request.

### 5. Access effects, and what happens to owned work

**Authorization.** Membership state is evaluated before any permission
(ADR-004 §4). `INVITED`, `SUSPENDED`, `REMOVED`, and absent membership all deny
with `forbidden_membership`, and an unauthenticated or inactive session resolves
to `401` per ADR-002. Suspension and removal therefore take effect on the **next
request**, not at the next login.

**Sessions and caches.** Suspension, removal, and role change revoke every
session for that user with reason `membership_inactive` (ADR-002). No separate
cache invalidation is required because authorization reads membership per
request; any future cache must key on membership state and be cleared by the
same event.

**Owned work is never deleted.** Nothing in this ADR removes a task, series,
note, or audit record. What changes is that the person no longer *is* an active
member:

| Record | On suspension | On removal |
|---|---|---|
| Tasks where they are accountable owner | Retained; the task reports **no accountable owner** to the operational scan (AGENTS.md definition: owner membership not `ACTIVE`) and stays reachable by `squadron_admin` and the owning team lead | Same |
| Recurring series they own | Retained; generation continues per ADR-007 | Retained; generation continues |
| Duty positions they hold | Cleared to vacant; ADR-007 fallback routes to the accountable owner and flags for the scan | Cleared to vacant |
| Team membership | Retained but inert (no team-scope authority) | Retained but inert |
| Shares held (`task_shares`) | Retained and inert; restored on reinstatement | Retained and inert; restored if re-invited |
| Collaborator/watcher rows | Retained and inert | Retained and inert |
| Audit history | Unchanged | Unchanged |

**Reassignment requirement.** Suspension and removal create a
`reassignment_required` attention item naming every task and series whose
accountable owner is the affected member, visible to `squadron_admin` and the
owning team lead. It is **advisory, not blocking**: the platform does not silently
reassign a person's accountability to someone else, and it does not hide the
work. Silent reassignment would falsify accountability, which is the one thing
this product must not do. An administrator completes the handoff through the
ordinary reassignment path (ADR-006), which records who moved the work and why.

**Vacancy is not deletion.** A vacated duty position is a routing gap, not a
reason to stop generating occurrences. The existing ADR-007 fallback applies:
open and future occurrences route to the accountable owner and are flagged.

### 6. Invariants this ADR establishes

- One squadron per installation; no request path selects a squadron.
- The first administrator exists only by operator bootstrap (or demo seed) —
  never through a public endpoint.
- Bootstrap is idempotent and restart-safe; it cannot create a second squadron or
  a second bootstrap administrator.
- Membership state precedes every permission decision; only `ACTIVE` authorizes.
- Invitation tokens are random, hashed at rest, single-use, expiring, and
  non-enumerable; acceptance errors are uniform.
- An invitee cannot choose its role, squadron, or team.
- Removal is terminal for access and reversible only through a new invitation.
- No self-transition, and the last active administrator cannot be suspended or
  removed.
- Suspension and removal revoke sessions and never delete or silently reassign
  owned work; reassignment is an explicit, audited act.

## Consequences

**Positive.** There is no privileged unauthenticated surface, and the first
administrator is created where the deployment boundary already is. Membership
transitions are a small, auditable table rather than an open state machine.
Derived invitation expiry removes a scheduler from the correctness path.
Retaining owned work while flagging it for reassignment keeps both continuity and
accountability truthful.

**Costs.** An operator must run one command (or use the demo profile) before the
application is usable, and the failure mode is `503 not_bootstrapped` rather than
a friendly setup wizard. Invitation handover is manual until email delivery is
authorized. The single-squadron decision must be revisited deliberately if
multi-tenancy is ever required.

**Risks accepted.** An operator with container access can create an
administrator; that is already equivalent to full control of the deployment, and
is recorded in audit. A leaked invitation token grants one membership at the
invited role until it expires or is revoked, which is why tokens are single-use
and expiry is short by default.

## Alternatives considered

| Alternative | Verdict | Why |
|---|---|---|
| First-run web setup wizard that creates the admin | Rejected | Requires a privileged unauthenticated endpoint; a race or a misconfiguration leaves an admin-minting route live |
| Environment-variable admin with automatic creation at startup | Rejected as the primary path | Hides a privileged write in ordinary startup, cannot express a password safely, and is hard to audit; the demo seed may still call the same bootstrap function |
| Auto-promote the first registered user | Rejected | Turns "be first" into an authorization rule and is trivially raced |
| Email-delivered invitation links | Deferred | ADR-001 forbids assuming a mail relay; the token is surfaced in-app until delivery is separately reviewed |
| Storing invitation status as a mutable column with a cleanup job | Rejected | Correctness would depend on a background job; expiry is a timestamp comparison |
| Deleting a removed member's tasks or reassigning them automatically | Rejected | Destroys continuity and falsifies accountability; reassignment must name an actor |
| Multi-squadron tenancy from day one | Rejected | Not required by the product; the squadron is a security boundary first |

## Unresolved questions (confirmable defaults, non-blocking)

| # | Question | Default taken here | Owner |
|---|---|---|---|
| Q1 | Invitation lifetime | 7 days, configurable 1–30 | Squadron Administrator |
| Q2 | Can an invitation propose a non-`member` role? | Yes, up to the inviter's own grant set; `member` is the default | Squadron Administrator |
| Q3 | Does acceptance require the invitee to set a password, or may an existing user be attached? | Invitee sets a password; an existing credential with no membership may be reused | Security Officer |
| Q4 | Should a suspended member keep team visibility? | No — all non-`ACTIVE` states deny access | Squadron Commander |
| Q5 | Is the `reassignment_required` item blocking? | No; advisory, surfaced in the scan and briefing | Squadron Commander |
| Q6 | Do invitations expire on squadron rename or admin change? | No; they expire on time or explicit revocation | Squadron Administrator |

Each default is safe to implement now and cheap to amend; none blocks #16, #18,
or #19.

## Validation

Documentation-only change. No application code, configuration, dependency, or
test was modified; `git diff --stat` confirms only `docs/adr/`, the ADR index,
and the membership invariants in `AGENTS.md`. The state table in §4 was reviewed
for unreachable and ambiguous states: every state has at least one exit except
`REMOVED`, whose only exit is a new invitation, which is deliberate. The backend
suite was run before and after the change and remained green; commands and
results are recorded on issue
[#5](https://github.com/anotherhale/str-ready-room/issues/5).

## References

- [ADR-001](ADR-001-deployment-classification.md) — deployment, classification,
  no-egress default
- [ADR-002](ADR-002-authentication-session.md) — local credentials, server-side
  sessions, membership coupling and revocation reasons
- [ADR-004](ADR-004-role-permission-matrix.md) — roles, scopes, evaluation order,
  `members:invite`/`members:manage`, no self-escalation
- [ADR-005](ADR-005-data-isolation-migration.md) — tenant key, deterministic
  bootstrap id, backfill and membership creation, operator recovery
- [ADR-006](ADR-006-task-scope-sharing.md) — accountable ownership, shares,
  reassignment
- [ADR-007](ADR-007-shared-recurrence.md) — duty-position routing and vacancy
  fallback
- `docs/SQUADRON_PLATFORM_EXPANSION.md` §3 (squadron, teams, duty positions) and
  Phase 1 exit criteria
