# ADR-004: Role and scoped-permission matrix

- **Status:** Accepted
- **Date:** 2026-11-24
- **Ticket:** [#6](https://github.com/anotherhale/str-ready-room/issues/6) (`P0-04`)
- **Deciders:** READY ROOM engineering
- **Supersedes:** none
- **Constrains:** [#18](https://github.com/anotherhale/str-ready-room/issues/18) (`P1-03` permission enum and role grants),
  [#19](https://github.com/anotherhale/str-ready-room/issues/19) (`P1-04` scope evaluation),
  [#21](https://github.com/anotherhale/str-ready-room/issues/21) (`P1-06` repository scoping),
  [#35](https://github.com/anotherhale/str-ready-room/issues/35) (`P2-01` task scope and roles),
  [#84](https://github.com/anotherhale/str-ready-room/issues/84) (`P5-05` approval gate)
- **Depends on:** [ADR-001](ADR-001-deployment-classification.md) (single squadron, unclassified synthetic data, no runtime egress)

## Context

Authorization today is a role-to-permission map with owner-only ownership:

- `Permission` (`backend/app/domain/authorization/permissions.py`) has 20 task,
  settings, and integration verbs.
- `OPERATOR_PERMISSIONS` grants every permission; `VIEWER_PERMISSIONS` grants a
  read subset.
- `AuthorizationPolicyService.decide` checks a role permission, then
  `owner_id == principal.id`, and returns `forbidden` or
  `forbidden_ownership`.
- `default_policy()` wires `operator` and `viewer` for the single-user demo.

That model cannot express the expansion. The spec (product areas 3 and 12)
requires the roles Squadron Administrator, Officer/Coordinator, Team Lead,
Member, and Read-only, "complemented by scoped permissions", with squadron and
team scope as a security boundary, duty-position access as an additional scope,
explicit resource shares, and an explicit deny for revoked or suspended
membership. The spec also states the rule that makes a role-only design
unacceptable: **avoid role-only checks where team or squadron scope matters**.

Three consequences follow, and this ADR settles all three:

1. A permission must carry **where** it applies, not only **whether** the actor
   holds it.
2. Team leads and duty-position holders need authority over their own
   responsibilities **without** permanent squadron-wide role escalation.
3. Agents act through delegated, attenuated capability — never through a human
   role — so the matrix must say which permissions can be delegated and which
   always require a human.

ADR-001 fixes the environment: one squadron, no multi-tenancy, synthetic data
only, no runtime egress. That keeps this matrix small on purpose.

## Decision

### 1. Roles

Five roles, each a named grant set. A principal may hold more than one role in a
squadron; effective permissions are the union, and the **narrowest** applicable
scope ceiling still governs any single grant.

| Role key | Display name | Intent |
|---|---|---|
| `squadron_admin` | Squadron Administrator | Administers the squadron boundary: membership, roles, teams, duty positions, settings, integrations, audit, agent identities. Full operational write. |
| `officer` | Officer / Coordinator | Squadron-wide operational authority: tasks, recurrence, briefings, turnover, notifications, approvals. No membership, team, duty-position, settings, audit, or agent-identity administration. |
| `team_lead` | Team Lead | The officer's operational set, **ceilinged at team scope**. Leads a team without squadron administration. |
| `member` | Member | Participates in their own and their team's work: create, comment, acknowledge, complete, hand off. Reads shared, team, and squadron resources. No coordination authority over other people's work. |
| `read_only` | Read-only | Reads everything they are entitled to see. Mutates nothing. |

**Compatibility aliases.** `operator` and `viewer` remain valid role keys for the
existing demo. `operator` maps to the `squadron_admin` grant set *plus* the
`demo:*` permissions, and exists only inside `default_policy()`.
`viewer` maps to the `read_only` grant set. No production role grant contains a
`demo:*` permission (ADR-001 requires the demo profile to be explicit and
unavailable outside `environment=demo`).

**Agents hold no roles.** An agent identity receives an explicit delegation grant
(ADR-008), never a role. This keeps "who a human is" and "what a machine may do"
separable, and it is what makes revocation meaningful.

### 2. Permission catalog

Naming stays `resource:verb`. The 20 existing values keep their names. New values
are added up front by `P1-03` so later phases do not churn the enum.

**Scope ceiling** is the widest resource scope at which the permission can ever
apply. `sq-only` means the permission is squadron-level by nature (administration)
and has no personal, team, or duty-position form.

| Permission | New | Scope ceiling |
|---|---|---|
| **Tasks and collaboration** | | |
| `tasks:read` | | squadron |
| `tasks:create` | | team |
| `tasks:update` | | team |
| `tasks:complete` | | team |
| `tasks:reopen` | | team |
| `tasks:delete` | | squadron |
| `tasks:assign` | new | squadron |
| `tasks:share` | new | team |
| `tasks:comment` | new | team |
| `tasks:acknowledge` | new | team |
| `tasks:handoff` | new | team |
| **Operations and briefings** | | |
| `dashboard:read` | | squadron |
| `briefing:read` | | squadron |
| `briefing:write` | new | squadron |
| **Recurrence** | | |
| `recurrence:read` | | squadron |
| `recurrence:write` | | team |
| `recurrence:override` | new | team |
| **Squadron, membership, teams, duty positions** | | |
| `squadron:read` | new | squadron |
| `squadron:manage` | new | sq-only |
| `members:read` | new | squadron |
| `members:invite` | new | sq-only |
| `members:manage` | new | sq-only |
| `teams:read` | new | squadron |
| `teams:manage` | new | sq-only |
| `duty_positions:read` | new | squadron |
| `duty_positions:manage` | new | sq-only |
| **Settings and categories** | | |
| `settings:read` | | squadron |
| `settings:update` | | sq-only |
| `categories:manage` | | sq-only |
| **Integrations** | | |
| `calendar:read` | | squadron |
| `calendar:sync` | | squadron |
| `calendar:write` | | squadron |
| `email:read` | | squadron |
| `email:capture` | | team |
| **Notifications** | | |
| `notifications:read` | new | squadron |
| `notifications:send` | new | squadron |
| **Turnover** | | |
| `turnover:read` | new | squadron |
| `turnover:build` | new | squadron |
| `turnover:acknowledge` | new | duty position |
| **Knowledge** | | |
| `notes:read` | new | squadron |
| `notes:write` | new | team |
| `notes:share` | new | team |
| **Audit** | | |
| `audit:read` | new | sq-only |
| **Approvals and workflows** | | |
| `approvals:read` | new | squadron |
| `approvals:decide` | new | squadron |
| `workflows:read` | new | squadron |
| `workflows:manage` | new | sq-only |
| **Agents and delegation** | | |
| `agents:read` | new | sq-only |
| `agents:manage` | new | sq-only |
| `delegations:read` | new | sq-only |
| `delegations:grant` | new | sq-only |
| `delegations:revoke` | new | sq-only |
| **Demo (demo policy only)** | | |
| `demo:reset` | | sq-only |
| `demo:simulate` | | sq-only |

That is 54 permissions: the 20 existing values plus 34 new ones.

### 3. Role × permission matrix

`✓` = granted; `–` = denied. A grant is still subject to the scope check in
§4 — a `team_lead` holding `tasks:assign` may assign inside their team and
nowhere else.

| Permission | admin | officer | team_lead | member | read_only |
|---|:--:|:--:|:--:|:--:|:--:|
| `tasks:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `tasks:create` | ✓ | ✓ | ✓ | ✓ | – |
| `tasks:update` | ✓ | ✓ | ✓ | ✓ | – |
| `tasks:complete` | ✓ | ✓ | ✓ | ✓ | – |
| `tasks:reopen` | ✓ | ✓ | ✓ | ✓ | – |
| `tasks:delete` | ✓ | – | – | – | – |
| `tasks:assign` | ✓ | ✓ | ✓ | – | – |
| `tasks:share` | ✓ | ✓ | ✓ | ✓ | – |
| `tasks:comment` | ✓ | ✓ | ✓ | ✓ | – |
| `tasks:acknowledge` | ✓ | ✓ | ✓ | ✓ | – |
| `tasks:handoff` | ✓ | ✓ | ✓ | ✓ | – |
| `dashboard:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `briefing:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `briefing:write` | ✓ | ✓ | ✓ | – | – |
| `recurrence:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `recurrence:write` | ✓ | ✓ | ✓ | – | – |
| `recurrence:override` | ✓ | ✓ | ✓ | ✓ | – |
| `squadron:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `squadron:manage` | ✓ | – | – | – | – |
| `members:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `members:invite` | ✓ | – | – | – | – |
| `members:manage` | ✓ | – | – | – | – |
| `teams:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `teams:manage` | ✓ | – | – | – | – |
| `duty_positions:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `duty_positions:manage` | ✓ | – | – | – | – |
| `settings:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `settings:update` | ✓ | – | – | – | – |
| `categories:manage` | ✓ | – | – | – | – |
| `calendar:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `calendar:sync` | ✓ | ✓ | ✓ | – | – |
| `calendar:write` | ✓ | ✓ | – | – | – |
| `email:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `email:capture` | ✓ | ✓ | ✓ | ✓ | – |
| `notifications:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `notifications:send` | ✓ | ✓ | ✓ | – | – |
| `turnover:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `turnover:build` | ✓ | ✓ | ✓ | – | – |
| `turnover:acknowledge` | ✓ | ✓ | ✓ | ✓ | – |
| `notes:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `notes:write` | ✓ | ✓ | ✓ | ✓ | – |
| `notes:share` | ✓ | ✓ | ✓ | ✓ | – |
| `audit:read` | ✓ | – | – | – | – |
| `approvals:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `approvals:decide` | ✓ | ✓ | ✓ | – | – |
| `workflows:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `workflows:manage` | ✓ | – | – | – | – |
| `agents:read` | ✓ | ✓ | – | – | – |
| `agents:manage` | ✓ | – | – | – | – |
| `delegations:read` | ✓ | ✓ | – | – | – |
| `delegations:grant` | ✓ | ✓ | – | – | – |
| `delegations:revoke` | ✓ | ✓ | – | – | – |
| `demo:reset` | demo only | – | – | – | – |
| `demo:simulate` | demo only | – | – | – | – |

Checks the matrix must keep passing (they are `P1-03`'s acceptance criteria):

- `read_only` holds no mutating permission at all.
- `team_lead` holds no `*:manage` permission and no `sq-only` permission.
- `member` cannot assign, delete, or alter a recurrence rule.
- Only `squadron_admin` can change membership, roles, teams, duty positions,
  settings, categories, agent identities, or read the audit log.
- Only `squadron_admin` and `officer` can grant or revoke a delegation.
- No production role holds `demo:*`.

### 4. Scope model and evaluation order

Five scopes, matching the spec:

| Scope | Resource is visible to |
|---|---|
| `personal` | The owner, plus anyone the owner explicitly shared it with |
| `shared` | The named recipients of an explicit share |
| `team` | Active members of the owning team |
| `squadron` | Active members of the squadron |
| `duty_position` | The current holder(s) of the duty position a resource is routed to |

**Evaluation is ordered, deny-by-default, and short-circuiting.** The first
failing step decides; later steps never widen a decision.

1. **Identity.** A principal must exist. No principal, no decision.
2. **Membership.** The actor must have an `ACTIVE` membership in the resource's
   squadron. `INVITED`, `SUSPENDED`, `REMOVED`, or absent membership denies with
   `forbidden_membership` — even when the role grant would otherwise allow the
   action. Suspension and removal therefore take effect on the next request, not
   on the next login.
3. **Permission.** The union of the actor's role grants in that squadron must
   contain the permission. Otherwise deny with `forbidden`.
4. **Scope.** The resource's scope must be within the grant's scope ceiling *and*
   the actor must hold the matching entitlement:
   - `personal`: the actor is the owner, or holds an explicit share that carries
     the verb (a read share never authorizes a write).
   - `shared`: the actor is a named recipient of the share.
   - `team`: the actor is an active member of that team; write verbs additionally
     require the actor's grant ceiling to reach team scope.
   - `squadron`: the actor is an active squadron member and the grant ceiling
     reaches squadron scope.
   - `duty_position`: the actor currently holds that position, and the position's
     capability set contains the permission.

   Failure denies with `forbidden_scope`. A personal-scope denial keeps the
   existing `forbidden_ownership` code so today's API responses and tests stay
   stable.
5. **Resource relationship.** Resource-specific rules (owner, assignee,
   collaborator, watcher, requester) may only *narrow* the decision. They are
   defined by ADR-006 (task scope, sharing, and accountable ownership,
   [#8](https://github.com/anotherhale/str-ready-room/issues/8)) for tasks; this
   ADR only fixes that they can never widen scope.
6. **Approval.** If the action is approval-gated (§6) and the actor is an agent,
   or the action crosses the approval threshold, a valid approval bound to the
   exact action and parameters is required. Absent one, deny with
   `approval_required`. Approval and execution stay separate operations.

**Defaults.**

- A decision with no scope information is treated as `personal` with owner-only
  access. This preserves current single-user behaviour and existing tests.
- An unknown or missing scope never means "allow".
- A permission is denied unless a grant explicitly includes it.

**Denial codes** (stable API contract):

| Code | Meaning | HTTP |
|---|---|---|
| `forbidden` | The actor holds no grant for the permission | 403 |
| `forbidden_membership` | Membership is not `ACTIVE`, or does not exist | 403 |
| `forbidden_scope` | The permission is granted, but not at this scope | 403 |
| `forbidden_ownership` | Personal-scope ownership denial (retained for compatibility) | 403 |
| `approval_required` | The action is consequential and has no valid approval | 409 |

### 5. Team-lead and duty-position authority

Neither mechanism escalates a role. Both are **bounded authority derived from a
relationship**, and both are checked after the role grant:

**Team Lead.** The role grant carries the operational permissions with a `team`
ceiling. Authority exists only for teams where the principal is an active member
with the `team_lead` role (or is the recorded lead of the team). Leading a team
grants no squadron administration, no membership change, no approval of
squadron-wide actions, and nothing outside the team. Removing the team-lead role
revokes the authority immediately because the check reads current membership.

**Duty position.** A duty position is a time-bounded assignment separate from
permanent roles. A position type declares a capability set drawn from the
non-administrative catalog, and the holder gains exactly that set at
`duty_position` scope — the resources routed to that position, not the squadron.

A duty position may carry, at most: `briefing:write`, `turnover:build`,
`turnover:acknowledge`, `notifications:send`, `tasks:assign`,
`recurrence:override`, `notes:write`.

A duty position may **never** carry: `squadron:manage`, `members:invite`,
`members:manage`, `teams:manage`, `duty_positions:manage`, `settings:update`,
`categories:manage`, `audit:read`, `agents:manage`, `delegations:grant`,
`delegations:revoke`, `approvals:decide`, `tasks:delete`, or `demo:*`.

The concrete position catalog (which positions exist and which capability each
carries) is a squadron-organizational input and lands with Phase 3. This ADR fixes
the rule that bounds it.

### 6. Approval-gated and agent-delegable permissions

The spec requires that an agent's permission is an explicit attenuated grant, that
agents never reuse human session credentials, and that agents cannot approve their
own work.

| Class | Permissions | Rule |
|---|---|---|
| **Delegable read-only** | Every `*:read` permission, `dashboard:read` | An agent may hold these through a delegation without further approval; every call is audited. |
| **Low-risk attributed write** | `tasks:comment` | Delegable without approval; the comment is attributed to the agent identity and its run. |
| **Draft, human executes** | `tasks:create`, `tasks:update`, `tasks:assign`, `tasks:share`, `tasks:handoff`, `tasks:complete`, `recurrence:write`, `recurrence:override`, `briefing:write`, `notifications:send`, `turnover:build`, `notes:write`, `notes:share`, `calendar:write`, `email:capture` | The agent produces a reviewable draft; the human confirms; the use case executes. A changed proposal invalidates the approval. |
| **Never delegable** | `tasks:acknowledge`, `turnover:acknowledge`, `approvals:decide`, `members:invite`, `members:manage`, `squadron:manage`, `teams:manage`, `duty_positions:manage`, `settings:update`, `categories:manage`, `audit:read` (as a grant), `agents:manage`, `delegations:grant`, `delegations:revoke`, `workflows:manage`, `demo:*` | These record human accountability or change authority. An agent may not perform them for a person. |

**Always approval-gated, whoever proposes them:**

- assignment at squadron scope;
- widening a share beyond the current scope;
- creating, editing, or ending a shared recurrence rule;
- squadron-wide notification broadcast;
- membership, role, team, duty-position, and delegation changes.

**Delegation invariants.**

- A delegation is a subset of the delegator's effective permissions *and* scope;
  it can never widen either.
- Delegations expire and are revocable; revocation denies the next tool call.
- An agent cannot approve its own proposal, and the approver cannot be the
  requester.
- `read_only` cannot be a source of any delegation.

### 7. Invariants this ADR establishes

- **Deny by default.** An unlisted permission is denied.
- **Scope never widens a grant.** A permission is valid only inside its ceiling.
- **Permission and relationship are both required.** Ownership, assignment, or
  team membership never replaces a permission check.
- **Membership state precedes everything.** Suspended or removed means denied,
  even with a valid role.
- **No self-escalation.** A principal cannot change its own role or membership;
  `members:manage` cannot target the acting principal.
- **No privilege amplification through delegation.** A delegator cannot grant
  what it does not hold.
- **Agents hold no roles** and never satisfy a human-accountability permission.
- **The frontend is never the enforcement point.** UI visibility only reflects
  server decisions.

## Consequences

**Positive**

- `P1-03` can implement the enum and grants mechanically: 54 values, five grant
  sets, one scope ceiling per grant.
- `P1-04` has an ordered evaluation algorithm and a stable set of denial codes,
  with explicit backward compatibility for personal tasks.
- Scope becomes a security boundary in queries (`P1-06`) rather than a UI filter,
  satisfying R-SQDN-09.
- Team leads and duty holders get the authority they need without permanent role
  escalation, satisfying R-SQDN-10.
- The agent runtime has a pre-agreed delegation and approval boundary, so `P5`
  tickets do not need to invent policy.

**Negative / accepted trade-offs**

- Every new permission must be added deliberately; the catalog grows with each
  phase. That is intended friction.
- A role change requires a second administrator, which is mildly inconvenient for
  a very small squadron. It is the price of preventing self-escalation.
- `member` cannot assign work to others, so a member who needs coordination must
  be given `team_lead`. This keeps accountability legible.

**Risks**

- If a squadron needs a role this matrix lacks (for example a dedicated auditor),
  adding it is a new grant set, not a permission redesign. Amending this ADR is
  the correct path.
- Duty-position capability sets could drift into administration over time. The
  never-list in §5 is the guard, and it should be tested when Phase 3 lands.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Keep `operator` / `viewer` and add a few flags | Cannot express team or duty-position scope; `operator` grants everything including `demo:*`, which must never reach production |
| Role-only checks with no scope | Rejected by the spec (R-SQDN-10); a team lead would either be powerless or squadron-wide |
| Hierarchical role inheritance (admin ⊃ officer ⊃ lead ⊃ member) | Implies authorities the spec does not grant (for example, officers inheriting membership administration); explicit grants are easier to audit |
| General-purpose policy language or policy engine | Over-engineering for five roles and five scopes; violates the "no overengineered policy languages" guidance |
| Per-resource ACL rows for every object | Duplicates scope logic, complicates queries, and adds a table per resource; scope + explicit shares covers the spec |
| Give agents the initiating human's permissions | Explicitly forbidden: an agent grant must be attenuated, revocable, and distinct |
| Make duty positions a role | Time-bounded assignment would become permanent role escalation |

## Unresolved questions (confirmable defaults, non-blocking)

| # | Question | Default taken here | Owner |
|---|---|---|---|
| Q1 | Is a team lead an accountable approver for team-scoped actions? | Yes, at team scope only | Squadron Commander |
| Q2 | Should officers be able to delete tasks? | No; deletion is administrator-only | Squadron Commander |
| Q3 | Which duty positions exist, and what does each carry? | Position catalog deferred to Phase 3 within the §5 bound | Squadron Commander / Operations |
| Q4 | Should Read-only users see the audit log? | No | Security Officer |
| Q5 | Is a squadron-wide notification broadcast officer-level or administrator-level? | Officer-level, approval-gated | Squadron Commander |

Each default is safe to implement now and cheap to amend; none blocks `P1-03` or
`P1-04`.

**Confirmation status (2026-11-24):** the product owner accepted Q1–Q5 as
written. Named-owner confirmations remain non-blocking and can amend these
defaults later.

## Validation

Documentation-only change. No application code, configuration, dependency, or
test was modified; `git diff --stat` confirms only files under `docs/adr/` plus
the authorization invariants in `AGENTS.md`. The backend and frontend baseline
suites were run before and after the change and remained green; commands and
results are recorded on issue
[#6](https://github.com/anotherhale/str-ready-room/issues/6).

## References

- `docs/SQUADRON_PLATFORM_EXPANSION.md` — product areas 3 and 12, approval model,
  priority order
- [ADR-001](ADR-001-deployment-classification.md) — deployment, classification,
  and data-handling constraints
- `backend/app/domain/authorization/permissions.py`, `policies.py`,
  `authorization_service.py` — current implementation
- `AGENTS.md` — identity/authorization invariants
