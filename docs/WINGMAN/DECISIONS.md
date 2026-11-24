# WINGMAN Decisions

Coordination and engineering decisions that are not already captured in an ADR or
in `AGENTS.md`. ADRs live in `docs/adr/`; `AGENTS.md` holds durable repository
invariants. This file records *how the coordinator works* and *why*.

## Architecture decision records

| ADR | Title | Status | Issue |
|---|---|---|---|
| [ADR-001](../adr/ADR-001-deployment-classification.md) | Deployment, classification, data handling | **Accepted and merged** (`90decc5`); Q1–Q7 defaults adopted, formal confirmation outstanding | #3 |
| ADR-002 | Authentication provider, session storage, cookies | READY | #4 |
| ADR-003 | Squadron bootstrap, invitation, membership lifecycle | READY | #5 |
| ADR-004 | Role and scoped-permission matrix | READY | #6 |
| ADR-005 | Data isolation, owner migration, schema evolution | READY | #7 |
| ADR-006 | Task scope, sharing, accountable ownership | READY | #8 |
| ADR-007 | Shared recurrence, duty routing, occurrence exceptions | Blocked on #8 | #9 |
| ADR-008 | Agent identity, delegation, approval binding | READY | #10 |
| ADR-009 | Jev provider, context assembly, failure strategy | READY | #11 |
| ADR-010 | Workflow persistence, retries, cancellation, idempotency | READY | #12 |
| ADR-011 | Notification channels/preferences and audit retention | READY | #13 |

## Coordination decisions

### C-001 — The WINGMAN instruction's "Issue #100 / ADR-1" is stale

**Decision:** treat **#3 (ADR-001)** as the initial ticket. #100 in this repository
is a frontend Notes/references view ticket, and the ADR set is #3–#13.

**Why:** the instruction's intent is "start with the first architecture decision".
The backlog is authoritative for what that ticket is. Executing #100 instead would
have skipped the prerequisite the spec calls for.

**Consequence:** when the instruction and the backlog disagree about identifiers,
the backlog wins and the discrepancy is recorded here.

### C-002 — ADRs precede application code in Phase 0

**Decision:** do not implement identity, squadron, task-sharing, Jev, or agent
runtime code until the ADR that governs it is accepted.

**Why:** each of those changes what data the system may hold and who may see it.
The spec makes classification and authorization prerequisites, not follow-ups.

**Consequence:** Phase 0 work is documentation, but it is not filler — it decides
the shapes later tickets must implement.

### C-003 — Unresolved organizational questions do not block the ADR set

**Decision:** ADR-001's Q1–Q7 block *real data* and *cloud deployment*, not the
remaining ADRs. Continue with #5–#13.

**Why:** the remaining ADRs decide an unclassified, synthetic-data build. Their
answers are engineering decisions and do not depend on classification approval.
Blocking them would stall the whole backlog on an external answer.

**Consequence:** if Q1/Q2/Q3 resolve differently (for example, approved egress),
ADR-002 and ADR-009 are amended rather than restarted.

### C-004 — Readiness follows closed dependencies, not finished work

**Decision:** a ticket moves `blocked` → `ready` only when every dependency issue
is **closed**, per `docs/WINGMAN/README.md` — not when the dependency's PR is open
and validated.

**Why:** the repository's own protocol says so, and a single rule is cheaper to
follow than a judgement call per ticket. The ADR-001 content is final, so merging
PR #105 and closing #3 unblocks #4 immediately.

**Consequence:** the unblocking step is explicit in `STATE.md` so the next session
does not have to rediscover it.

### C-005 — Coordinator state is reviewed like code

**Decision:** state artifacts are committed on a branch and opened as a PR, never
pushed to `main`.

**Why:** WINGMAN's git rules forbid direct pushes to `main`, and a reviewed state
file is a check on false claims of progress.

**Consequence:** until the state PR merges, GitHub issues are the recovery source
of truth. `CHECKPOINT.json` is written to be self-sufficient for that case.

### C-006 — Answer the ADR-001 organizational questions with adopted defaults

**Decision:** on 2026-11-24 the product owner directed that every open ADR-001
question be answered with a recommended default rather than left open. The
defaults adopted are:

| # | Default |
|---|---|
| Q1 | Controlled-network single host administered by unit IT; accreditation via the unit's existing security review; cloud out of scope |
| Q2 | UNCLASSIFIED only for the first release; synthetic data until confirmed |
| Q3 | No internet egress by default; internal controlled-network endpoint allowed per integration |
| Q4 | Minimal personnel fields: display name, membership, duty position, one optional work contact |
| Q5 | Retain indefinitely; explicit authorized deletion only; audit outlives its subject |
| Q6 | Operator nightly snapshot, 30-day retention, quarterly restore drill; RPO 24h / RTO 4h |
| Q7 | Env-injected secrets from an operator-managed store; never committed, logged, or returned by API |

**Why:** leaving all seven open kept the ADR in a permanent "unresolved" state and
made every downstream ADR argue from uncertainty. A recorded default gives
engineering a position to build against and gives each official a concrete
proposal to accept or overturn, which is faster than an open question.

**Boundary this decision does not cross:** these are project decisions, **not**
accreditation. No real operational or personnel data may be stored, no cloud
hosting is authorized, no default egress is permitted, and nothing here may be
cited as an authorization to operate. Each row is reversible by its named owner,
and overturning one is an amendment to ADR-001 — not silent configuration drift.

**Consequences:** #4 (ADR-002) unblocked and promoted to the front of the queue;
#11 (ADR-009) must default to a local/internal provider; #13 (ADR-011) can close
on Q5's basis; #104's profile fields are bounded by Q4.
