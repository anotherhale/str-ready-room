# WINGMAN — Autonomous Backlog Operating Model

This directory contains the planning and traceability artifacts for the READY
ROOM **Squadron Platform Expansion** (see
`docs/SQUADRON_PLATFORM_EXPANSION.md`, PR #1). GitHub Issues are the
**authoritative unit of work**; these documents explain how the backlog was
derived and how an autonomous session should consume it.

## Artifacts

| File | Purpose |
|---|---|
| `STATE.md` | Live status: what is verified, what is blocked, the READY queue, next ticket |
| `CHECKPOINT.json` | Machine-readable state for a fresh session |
| `EXECUTION_LOG.md` | Append-only per-session record of ticket, actions, evidence, commits |
| `DECISIONS.md` | Coordination decisions and the ADR index with status |
| `ARCHITECTURE_MAP.md` | Architecture as implemented, and the gaps the expansion fills |
| `AGENT_REGISTRY.md` | Delegable roles, their scope, and current assignment |
| `BASELINE_ASSESSMENT.md` | What already exists, verified against code and test runs |
| `REQUIREMENTS_TRACEABILITY.md` | Requirement inventory, status, and requirement → issue mapping |
| `BACKLOG_DECOMPOSITION.md` | Backlog summary, phases, metrics, critical path, risks, READY queue |
| `README.md` (this file) | How WINGMAN selects and completes a ticket |

## Source of truth

- Product/architecture requirements: `docs/SQUADRON_PLATFORM_EXPANSION.md`,
  merged to `main` (PR #1). A session whose clone predates that merge should
  `git fetch origin main` before selecting work.
- Durable repository invariants: `AGENTS.md`.
- Architecture decisions for the expansion: `docs/adr/ADR-*.md`.
- Current implementation facts: the repository and its tests, not the roadmap.

## Labels

Every WINGMAN ticket carries:

- `wingman` — managed by this process.
- One priority: `P0-critical`, `P1-high`, `P2-normal`, `P3-low`.
- One type: `architecture`, `backend`, `frontend`, `security`, `ai`, `qa`,
  `devops`, or `documentation`.
- One lifecycle label: `ready`, `in-progress`, `verification`, or `blocked`.

A ticket is **READY only when every dependency issue is closed**. Do not infer
readiness from the phase or from a comment. If a dependency is open, the ticket
stays `blocked`.

## Lifecycle

```text
BLOCKED (dependencies open)
   |
   v  all dependencies closed + issue re-read
READY
   |
   v  work starts
IN PROGRESS
   |
   v  implementation + tests + PR
VERIFICATION
   |
   v  PR merged + evidence recorded
DONE (issue closed)
```

Transitions are made by the executing session and the reviewer. Never close an
issue without validation evidence. Never mark a ticket `ready` by hand while a
dependency is open.

## How a session selects work

Selection is **claim-aware**, not label-aware. The mandatory handshake
(`WINGMAN.md`, enforced by `scripts/wingman/preflight.py`) does this in order:

1. Register the run in the shared registry (GitHub refs, `run-events/<RUN_ID>/e<N>`).
2. Discover every other run: its ticket, status, activity, branch, PR, heartbeat,
   and claim expiry.
3. Reconcile the registry against GitHub — claims without a live run, claims whose
   ticket already has a PR, PRs the registry does not know about. Discrepancies are
   recorded, never "fixed" by writing into another run's state.
4. Build the exclusion set: `blocked`, unsatisfied dependency, live claim, expired
   claim (recovery inspection first), open PR, foreign branch, `verification`.
5. From the remaining open tickets, pick the highest value: priority, then how many
   open tickets depend on it, then age. Roadmap phases are informational.
6. Claim atomically and verify ownership by read-back. Refused or unverified means
   **do not implement** — go back to step 4.
7. Verify the isolated worktree, mark `EXECUTING`, and only then write code.

Never treat a claim as advisory, and never assume the previous session finished.

## Session timebox (30 minutes hard limit)

| Window | Budget | Work |
|---|---|---|
| 0–4 min | recovery & reconciliation | handshake steps 1–4; inspect the registry and any expired claim |
| 4–6 min | selection & claim | steps 5–7; claim + verify + worktree |
| 6–21 min | engineering | the ticket's scope only |
| 21–26 min | validation & persistence | tests, lint, checkpoint, issue comment |
| 26–30 min | handoff | PR, release claim, next-ticket recommendation |

Recovery is bounded: if the workspace or coordination state cannot be reconstructed
by minute 4, stop, record the blocker, release or keep the claim deliberately, and
leave the work for the next run. Never exceed the box to "finish" a ticket.

## Execution protocol for one ticket

1. Re-run the baseline gates before editing:
   - `cd backend && .venv/bin/python -m pytest -q`
   - `cd frontend && npm run test:run && npm run typecheck`
   (create the venv/dependencies if absent).
2. If the baseline is red, stop and report it; do not layer changes on a broken
   baseline.
3. Implement only the Scope. Defer Out of Scope work to a new issue.
4. Add or update tests for the behaviour. Domain rules get unit tests;
   persistence/API/authorization behaviour gets integration tests.
5. Run the ticket's Validation commands and the full relevant suites.
6. Open a PR against `main` that references the issue. Do not merge. After a
   human merges it, verify the head branch was deleted (auto-delete is enabled).
7. Comment on the issue with the exact commands, results, and the PR link.
   Move the issue to `verification`; close it only after merge and re-check.
8. If the work cannot finish in the window: comment with the blocker, leave the
   issue `in-progress`, keep the branch building, and stop. Never leave a
   half-applied migration or failing tests on `main`.

## Definition of Ready

- All dependencies closed.
- Issue has an objective, explicit scope and out-of-scope, acceptance criteria,
  and validation commands.
- Estimated agent time ≤ 25 minutes.
- No unresolved product/architecture decision that the ticket depends on.

## Definition of Done

- Acceptance criteria satisfied.
- New behaviour has tests; relevant suites pass.
- No unrelated regressions.
- Authorization/ownership/scope checked where applicable.
- `AGENTS.md` updated if a durable invariant changed.
- Validation evidence recorded on the issue.
- PR reviewed and merged; issue closed.
- Head branch deleted after merge; no merged branch left on `origin`.

## Concurrency

Multiple WINGMAN runs may be active at once; the 10-minute stagger is a scheduling
target, **not** a safety mechanism.

- **Authority:** ticket claims are exclusive leases stored as immutable git refs.
  Only `claim-epochs/issue-<T>/e<K>` creation grants ownership, and only one creator
  can win epoch `K`. See `docs/WINGMAN/CONCURRENCY.md`.
- **Exclusion:** claimed, expired-but-unrecovered, in-progress, blocked, and
  `verification` tickets are unavailable. So is any ticket with an open PR or a
  foreign branch: the work is already delivered or in flight.
- **Isolation:** one worktree and one branch per run (`wingman/issue-<T>/run-<RUN_ID>`).
  A shared checkout is not a workspace; sharing one is how a run's HEAD, uncommitted
  changes, and branch were destroyed (incident B-008).
- **Recovery:** an expired claim is inspected, not reassigned. The recovering run
  records `recovered_from`, an incremented attempt number, and what it inspected.
- **Evidence:** PRs and git history are the delivery record; the registry is the
  ownership record. Neither replaces the other.
- **Rollout:** one implementation run at a time until the two-machine gate in #127
  passes. Concurrency is earned by validation, not enabled by a prompt change.
- Explicit dependencies still encode integration order; never parallelize dependent
  tickets, and never let two runs edit the same migration.

## Replenishment

The backlog covers Phases 0–6. When a ticket is found to be too large during
execution, split it into smaller issues and link them as `blocked_by` children;
do not expand the original ticket. When requirements change, add a new ADR and
re-ticket rather than silently changing acceptance criteria.
