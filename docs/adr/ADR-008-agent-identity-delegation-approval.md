# ADR-008: Agent identity, delegation, and approval binding

- **Status:** Accepted 2026-11-24
- **Ticket:** [#10](https://github.com/anotherhale/str-ready-room/issues/10) (`P0-08`)
- **Requirements:** R-AGENT-01..R-AGENT-07, R-ARCH-04, R-ARCH-06, R-ARCH-07
- **Depends on:** ADR-001 (classification, no egress by default), ADR-002
  (human authentication and sessions), ADR-004 (roles, scopes, approval classes),
  ADR-005 (tenant key and schema evolution), ADR-006 (task scope and relationships)
- **Constrains:** `P5-01`..`P5-04` (agent identity, delegation, workflow state,
  approval), `P5-08` (tool gateway), `P5-11` (approval service), and ADR-009
  (Jev provider and context) and ADR-010 (workflow persistence)

## Context

Humans, agents, and delegated authority are distinct, and nothing in the codebase
represents the second or third. Today an agent would have to borrow a human
session to do anything, which the spec forbids: "Agents never reuse or impersonate
human session credentials" and "Agent permission is not automatically equivalent
to the initiating user's permission; it is an explicit attenuated grant."

ADR-004 already fixes the surrounding rules this record must not reopen:

- agents hold **no** roles; they act only through explicit, revocable delegation;
- a delegation is a subset of the delegator's permissions *and* scope;
- delegations expire and are revocable; revocation denies the next tool call;
- agents may never satisfy a human-accountability permission
  (`tasks:acknowledge`, `turnover:acknowledge`, `approvals:decide`);
- four permission classes exist: delegable read-only, low-risk attributed write,
  draft-then-human-executes, and never delegable;
- approval is required for consequential actions and must bind to the exact
  action and parameters.

What is missing is the *shape*: what an agent identity is, what a delegation
record contains, the exact order in which the checks run, how an approval binds
to a proposal so a changed parameter invalidates it, and which tools may exist at
all. Phase 5 cannot start without those answers, and ADR-009 (Jev) and ADR-010
(workflow state) both need the identifiers and hashes defined here.

Three spec statements drive every decision below:

1. "An approval must bind to the exact proposed action and parameters. If the
   proposal changes, approval is invalidated or revalidated."
2. "Agents cannot approve their own work or satisfy human approval requirements."
3. "No unrestricted shell, arbitrary filesystem, direct SQL, generic HTTP, or
   generic CRUD tool access."

## Decision

### 1. Three records, and an agent is never a role

Four concepts are kept apart, each with its own table:

| Record | Answers | Owner of the write |
|---|---|---|
| `agent_identities` | *what* is acting (stable id, version, declared capabilities) | `agents:manage` (human) |
| `delegations` | *what it may do, for whom, for how long* | `delegations:grant` (human) |
| `approvals` | *who accepted this exact action* | `approvals:decide` (human) |
| `workflow_runs` | *what happened during one execution* | the runtime (ADR-010) |

An agent has **no** role, no membership, and no session. `AuthorizationPolicyService`
returns an empty permission set for an agent principal; agent authority is only
ever read from a delegation. This makes "agent got a role by accident" a type
error rather than a policy question.

**Agent identity (`agent_identities`).**

| Field | Type | Rule |
|---|---|---|
| `id` | `String(36)` | Row identity (surrogate) |
| `squadron_id` | `String(36)` | Tenant key (ADR-005); never from a request |
| `agent_id` | text | Stable logical identity, e.g. `jev`; unique per squadron |
| `version` | text | Immutable declaration version, e.g. `2026-11-24.1` |
| `name` | text | Display name |
| `declared_capabilities` | JSON list of permission values | The **maximum** set this version may ever be delegated |
| `registrar_id` | text | Human who registered it (`agents:manage`); never the agent |
| `status` | `active` \| `retired` | Retired means no new delegation; existing delegations still die at expiry |
| `created_at` / `retired_at` | naive UTC | ADR-001 time rules |

A version bump is a **new row**, never an edit: `(squadron_id, agent_id, version)`
is unique and a delegation pins the version it was granted against. An agent
whose declared capabilities change is a different version, so a delegation can
never silently widen. The audit trail therefore names `agent_id@version`, which
is what acceptance scenario 13 requires.

**Delegation (`delegations`).**

| Field | Type | Rule |
|---|---|---|
| `id` | `String(36)` | |
| `squadron_id` | `String(36)` | Must equal the agent's and the delegator's active-membership squadron |
| `agent_identity_id` | FK → `agent_identities.id` | Pins agent **and** version |
| `delegator_id` | text | Human user; must hold `delegations:grant` and an `ACTIVE` membership |
| `purpose` | text, required | Human-readable reason; recorded in every audit entry |
| `scope_ceiling` | `personal` \| `shared` \| `team` \| `squadron` \| `duty_position` | The widest scope the grant may reach |
| `capabilities` | JSON list of permission values | Must be a subset of the agent's declared capabilities *and* the delegator's effective permissions |
| `resource_bounds` | JSON object | `{kind: "all_in_scope"}` or `{kind: "ids", task_ids: [], series_ids: [], team_ids: [], duty_position_ids: []}` |
| `issued_at` | naive UTC | |
| `expires_at` | naive UTC, required | Default 4 h, hard maximum 24 h |
| `revoked_at` / `revoked_by` / `revocation_reason` | nullable | Set once; revocation is terminal |

No delegation-to-delegation: `delegator_id` must be a **human**. Agent-to-agent
chains are an explicit non-goal, and forbidding them by construction costs nothing.

**Approval (`approvals`).**

| Field | Type | Rule |
|---|---|---|
| `id` | `String(36)` | |
| `squadron_id` | `String(36)` | Tenant key |
| `action_type` | text | Catalog identifier, e.g. `tasks.assign`, `recurrence.write` |
| `target_type` / `target_id` | text | What the action applies to |
| `parameters_hash` | `String(64)` | SHA-256 hex of the canonical encoding (§5) |
| `parameters_excerpt` | JSON | Minimised, non-secret rendering for the approver; never the full payload |
| `proposer_kind` / `proposer_id` | `human` \| `agent` / text | For an agent proposal, `proposer_id` is `agent_id@version` |
| `initiating_human_id` | text, nullable | Present when an agent acted for a person |
| `run_id` | text, nullable | The `workflow_runs.id` that proposed it |
| `state` | `pending` \| `approved` \| `rejected` \| `expired` \| `consumed` \| `invalidated` | Lifecycle only, never deleted |
| `approver_id` | text, nullable | A human with `approvals:decide`; never the proposer |
| `created_at` / `expires_at` / `decided_at` / `consumed_at` | naive UTC | Default expiry 30 min, hard maximum 24 h |
| `decision_note` | text, nullable | |

Every state change also appends an `approval_events` row (`approval_id`, `seq`,
`event`, `actor_kind`, `actor_id`, `at`, `detail`). The approval row is a
projection of that append-only trail, so "who approved what, when, and what
changed afterwards" survives any later edit.

### 2. The authorization order, extended for agents

ADR-004's order (membership → permission → scope → relationship → approval) is
preserved and the agent steps are inserted so that **no agent check can run
before the human check it derives from**. Evaluation is ordered,
deny-by-default, and short-circuiting; the first failure decides and later steps
never widen it.

| # | Step | Failure code |
|---|---|---|
| 1 | **Principal exists** and its kind is known (`human` \| `agent`) | `forbidden` |
| 2 | **Membership.** For a human, their own `ACTIVE` membership in the resource's squadron. For an agent, the **delegator's** and (if present) the **initiating human's** `ACTIVE` membership in that squadron. | `forbidden_membership` |
| 3 | **Human permission (attenuation).** The requested permission must be in the delegator's *current* effective permissions, recomputed at call time, not cached at grant time. | `forbidden` |
| 4 | **Agent identity.** Identity exists, `status = active`, and the pinned `agent_id@version` matches the delegation. | `forbidden_agent` |
| 5 | **Delegation.** Not expired, not revoked, `purpose` recorded, `squadron_id` matches, and `initiating_human_id` (when the agent acts for a person) is the delegator or is covered by the grant. | `forbidden_delegation` |
| 6 | **Capability.** The requested permission is in `delegation.capabilities`, which is in turn a subset of the agent's `declared_capabilities`. | `forbidden_capability` |
| 7 | **Resource scope.** The resource scope is within `scope_ceiling` and the resource id is inside `resource_bounds`; the duty-position and team rules of ADR-004 §4 still apply. | `forbidden_scope` |
| 8 | **Resource relationship.** ADR-006 rules may only *narrow* (owner, assignee, collaborator, watcher). | `forbidden_ownership` |
| 9 | **Approval.** If the permission's class requires approval (§4), a valid approval bound to this exact action and these exact parameters must exist. | `approval_required` / `approval_invalid` |
| 10 | **Record.** The `tool_invocations` row and the audit entry are written in the same transaction as the effect. | — |

Two consequences worth stating explicitly:

- **Revocation and expiry are checked per call, not per run.** A run that
  authorised a tool at T0 re-authorises at T1; revoking at T0:30 denies the next
  call (acceptance scenario 11). A call already past step 9 completes and is
  audited — half-executed effects are worse than a slightly stale grant.
- **Authority is an intersection recomputed on every call:**
  `effective = delegation.capabilities ∩ agent.declared_capabilities ∩ delegator.effective_permissions`,
  and `scope = min(delegation.scope_ceiling, delegator's ceiling)`. If the
  delegator is suspended or loses a permission, the delegation silently loses it
  too. Nothing has to be re-issued for that to take effect, and nothing can be
  cached into a widening.

### 3. Two operating modes, and what an agent may do unattended

| Mode | Initiating human | Authority | May execute a draft? |
|---|---|---|---|
| **Interactive** (Jev in a session) | present | `delegation ∩ agent ∩ initiating human` | Yes, after that human confirms the draft |
| **Scheduled** (no human present) | absent | `delegation ∩ agent` only | No. It may read and it may *propose*; execution waits for a human |

A scheduled run therefore cannot launder a draft into an effect: with no
initiating human there is no one to confirm, so the proposal becomes a `pending`
approval and stops. This is what makes "agents cannot satisfy human approval
requirements" a property of the design rather than a rule someone remembers.

**Confirmation is not approval.** Two distinct gates, deliberately not merged:

- **Draft confirmation** — the human who asked for a draft accepts *their own*
  proposal. The human is the accountable actor; no second person is required.
- **Approval** — a consequential action (ADR-004 §6) requires a *different*
  human holding `approvals:decide` at a scope covering the target. The
  `approvals:decide` permission is never delegable, so an agent can never be the
  approver, and `approver_id ≠ proposer_id` is enforced even when both are human.

### 4. Permission classes, as the gateway enforces them

ADR-004 §6 fixes the four classes. The tool gateway materialises them as a
`risk_class` on each tool, and the class decides whether step 9 applies:

| `risk_class` | Classes from ADR-004 | Approval |
|---|---|---|
| `read` | delegable read-only | none; every call audited |
| `attributed_write` | low-risk attributed write (`tasks:comment`) | none; attributed to `agent_id@version` and the run |
| `draft` | draft, human executes | the human confirms the draft; a changed parameter invalidates it |
| `consequential` | always approval-gated list (squadron-scope assignment, widening a share, shared recurrence create/edit/end, squadron broadcast, membership/role/team/duty-position/delegation changes) | `approvals` row required |
| `forbidden` | never delegable | the tool does not exist for agents |

### 5. Approval binding: canonical parameters and invalidation

The binding must be testable, so it is defined mechanically.

**Canonical encoding.** A proposal's parameters are encoded as JSON with:
keys sorted by code point at every level, no insignificant whitespace
(`separators=(",", ":")`), `null` retained, booleans and integers as-is,
decimals as strings, dates as `YYYY-MM-DD`, datetimes as RFC 3339 in UTC with a
trailing `Z` and no sub-second part, and identifiers as strings. `parameters_hash`
is the lowercase hex SHA-256 of the UTF-8 encoding of that string.

**Binding rules.**

1. Approval stores `action_type`, `target_type`, `target_id`, and
   `parameters_hash`. Execution recomputes the hash from the *actual* command it
   is about to run and compares. A mismatch fails with `approval_invalid` and
   marks the approval `invalidated`; it never silently re-requests.
2. An approval is single-use: successful execution sets `consumed_at` and state
   `consumed`. A retry after an unknown outcome reuses the same idempotency key
   (ADR-010) rather than a second approval.
3. `approved` expires at `expires_at` (default 30 min). Expiry, rejection,
   cancellation of the run, or a target that no longer exists all end in a state
   that cannot be executed.
4. **No implicit approval.** A timeout, a missing approver, a notification
   failure, or a model apology never yields an approval. `pending` is not
   permission (acceptance scenario 14 generalised to approvals).
5. The approver sees `parameters_excerpt`, a minimised rendering — enough to
   judge the action, never a secret or a bulk payload. The hash, not the
   excerpt, is the binding.

### 6. Tools: an allow-list of typed operations, never a generic surface

The gateway exposes **only** catalogued operations, each declaring `tool_name`,
`tool_version`, typed input schema, exactly one `capability` (one permission
value), `risk_class`, and whether it is idempotent. By design there is no tool
for:

- shell or process execution;
- arbitrary filesystem read or write;
- direct SQL or an ORM/session handle;
- generic HTTP or arbitrary URL fetch;
- generic CRUD over an arbitrary table or entity.

A new capability requires a new typed tool plus a catalog entry; it cannot be
reached by parameterising an existing one. Tools call **application use cases**
and never repositories or adapters directly, so every effect passes the same
authorization, ownership, and audit path as a human action.

Per-run budgets are enforced in the gateway, not requested from the model: a
maximum tool-call count, a maximum row/record count per call, a maximum context
size, and a wall-clock deadline. Exceeding a budget ends the run with a recorded
outcome; it never degrades into an unaudited partial state.

### 7. Credential separation, and how reuse is detected

- An agent authenticates as an **agent principal**: `agent_identity_id` plus a
  run-scoped token minted by the runtime, recorded only as a SHA-256 hash.
- Human sessions (ADR-002) never hold an agent subject, and the agent token store
  is a separate table from `sessions`. There is no code path that copies a
  session token into a run.
- `Principal.kind` is explicit and part of every authorization decision, every
  audit entry, and every tool invocation.
- Detection, not just prohibition: a request whose actor kind is `agent` that
  carries a human session identifier, a delegation whose `delegator_id` is not a
  human, an `approvals` row whose `approver_id` equals `proposer_id`, or a
  `tool_invocations` row with no `delegation_id` are each **hard failures** —
  denied, audited as a security event, and covered by `P5-14`'s test suite. These
  are cheap invariants to assert and they are exactly the failure modes that
  matter.

### 8. Persistence, tenancy, and secrets

New tables, all carrying `squadron_id NOT NULL` with indexes leading with it
(ADR-005): `agent_identities`, `delegations`, `approvals`, `approval_events`,
`tool_invocations`. `workflow_runs` belongs to ADR-010; `tool_invocations` and
`approvals` reference `run_id` rather than owning it.

- Child rows inherit `squadron_id` from their parent inside the same transaction.
- Every read takes a `ScopeCriteria`; there is no "list all delegations" method.
- Append-only tables (`approval_events`, `tool_invocations`, audit) are never
  updated or deleted by the application.
- **No credential material is stored here.** Provider keys, SMTP credentials, and
  agent tokens live in configuration or a secret store, referenced by name. An
  approval excerpt and a tool invocation result are both minimised; neither
  carries a secret.
- Delegation and approval tables grow only with human decisions, so a retention
  policy (ADR-011) can reason about them without a payload dump.

### 9. Check against the acceptance scenarios

| Scenario | How this ADR satisfies it |
|---|---|
| 10 — an agent cannot access data outside its delegated scope, even if prompted | Steps 5–7 run per call, from records, not from the model's request; `resource_bounds` narrows further; repository criteria are built from the delegation, so an over-broad prompt returns an empty result |
| 11 — a revoked delegation cannot be used for subsequent actions | Step 5 re-reads the delegation on every call; `revoked_at` is terminal; the next call denies with `forbidden_delegation` |
| 12 — a consequential action is not executed before approval | `risk_class = consequential` requires a valid, unexpired, unconsumed approval bound to the canonical hash |
| 13 — execution history records actor, agent, tool, action, result without leaking payloads | `tool_invocations` + `approval_events` + audit record `agent_id@version`, `run_id`, `delegation_id`, `capability`, `input_hash`, and a minimised result summary |

## Consequences

**Positive**

- `P5-01`..`P5-04` implement value objects and a table set with no open design
  questions; the hash, the check order, and the state machine are all fixed.
- Attenuation is computed, not copied, so a suspended delegator cannot leave a
  live grant behind.
- Because approval binds to a hash, "the approver approved something else" is a
  detectable bug rather than a review miss.
- The tool allow-list makes prompt injection a data problem: the model can ask
  for anything, and the gateway will still refuse a tool that does not exist.

**Negative / costs**

- Per-call re-authorisation adds two reads per tool call. Acceptable: tool calls
  are interactive or scheduled, not high-frequency.
- Canonical encoding must be implemented once and reused. Two encoders would
  produce two hashes and a false `approval_invalid`; this is the main
  implementation hazard and belongs in a single module with round-trip tests.
- A version bump invalidates in-flight delegations pinned to the old version.
  That is intended: it forces a deliberate re-grant.

**Neutral**

- No agent-to-agent delegation, no generic tool builder, no cryptographic audit
  ledger. Each is a non-goal of the first expansion, and each can be added later
  without changing the records defined here.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Give an agent a role and attenuate it | Roles are squadron-wide bundles; attenuation would have to be re-implemented per request, and "which role is this agent" has no accountable human |
| Let the agent inherit the initiating human's session | Explicitly forbidden by the spec; makes revocation impossible without ending the human's session and destroys attribution |
| Bind approval to the proposal *text* or an LLM summary | Not canonical; two renderings of one action would differ, and a summary can omit the parameter that matters |
| Approve once per run instead of per action | A run proposes several actions; approving the run would approve the ones nobody read |
| Store approval state only on the run | Loses the append-only trail and lets a later state overwrite who decided what |
| Expose a generic `crud(entity, op)` tool with a permission check | Turns one authorization bug into a whole-database exposure, and defeats the typed-input guarantee |
| Require a second human to confirm every draft | Conflates confirmation with approval and makes routine capture unusable; the distinction in §3 keeps accountability with the person who asked |

## Open questions (confirmable defaults, non-blocking)

| # | Question | Default adopted |
|---|---|---|
| A1 | Delegation lifetime | 4 h default, 24 h maximum, renewable by the delegator only |
| A2 | Approval lifetime | 30 min default, 24 h maximum, single-use |
| A3 | Whether an initiating human must equal the delegator | No; the grant may cover a team or squadron, and the initiating human must be inside `resource_bounds` and an active member |
| A4 | Whether `tasks:comment` needs approval | No — attributed write, audited (ADR-004 §6) |
| A5 | Whether an agent may ever see `audit:read` | No, as a delegation. Execution history is surfaced to humans through the run/approval views |
| A6 | Run budget defaults | 50 tool calls, 200 records per call, 32k context tokens, 10-minute wall clock per run |

## Validation

Documentation-only change: no application code, schema, or migration is touched.
The design is checked against spec area 10 ("Agent identity, authentication, and
delegation"), area 11 ("Agentic workflows"), the "Agent/tool execution contract",
the "Approval model", and acceptance scenarios 10–13. The repository baseline was
run before and after the change and is unchanged.

## References

- `docs/SQUADRON_PLATFORM_EXPANSION.md` — areas 10, 11, 12, 13; agent/tool
  execution contract; approval model; acceptance scenarios 10–13
- [`ADR-002`](ADR-002-authentication-session.md) — human sessions and credential
  handling
- [`ADR-004`](ADR-004-role-permission-matrix.md) — roles, scopes, denial codes,
  approval-gated and never-delegable permissions
- [`ADR-005`](ADR-005-data-isolation-migration.md) — tenant key, repositories,
  migration runner
- [`ADR-006`](ADR-006-task-scope-sharing.md) — task scope and relationships
- [`AGENTS.md`](../../AGENTS.md) — identity and authorization invariants
