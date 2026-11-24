# WINGMAN — Autonomous Backlog Operating Model

This directory contains the planning and traceability artifacts for the READY
ROOM **Squadron Platform Expansion** (see
`docs/SQUADRON_PLATFORM_EXPANSION.md`, PR #1). GitHub Issues are the
**authoritative unit of work**; these documents explain how the backlog was
derived and how an autonomous session should consume it.

## Artifacts

| File | Purpose |
|---|---|
| `BASELINE_ASSESSMENT.md` | What already exists, verified against code and test runs |
| `REQUIREMENTS_TRACEABILITY.md` | Requirement inventory, status, and requirement → issue mapping |
| `BACKLOG_DECOMPOSITION.md` | Backlog summary, phases, metrics, critical path, risks, READY queue |
| `README.md` (this file) | How WINGMAN selects and completes a ticket |

## Source of truth

- Product/architecture requirements: `docs/SQUADRON_PLATFORM_EXPANSION.md` on
  branch `feature/squadron-platform-expansion` (PR #1). If a session does not
  see it on its branch, fetch it:
  `git fetch origin feature/squadron-platform-expansion`.
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

## How a scheduled session selects work

1. List open issues with label `ready` (oldest/highest priority first).
2. Prefer `P0-critical`, then `P1-high`, then `P2-normal`, then `P3-low`.
3. Verify every listed dependency is closed. If not, remove `ready`, add
   `blocked`, and select the next ticket.
4. Read the issue body completely; it is self-contained and includes the
   objective, scope, out-of-scope, guidance, files, acceptance criteria,
   validation, and handoff notes.
5. Execute exactly one primary ticket. Do not pull in another ticket's scope.

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
6. Open a PR against `main` that references the issue. Do not merge.
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

## Concurrency and conflicts

- Assume **one active implementation session** at a time. If two run, they must
  choose tickets with disjoint file sets and must not both edit the same
  migration.
- Explicit dependencies encode integration order. Do not parallelize dependent
  tickets.
- ADR tickets are intentionally unblocked and can be parallelized, but each
  writes one file and appends to the ADR index; coordinate the index edit.
- A migration ticket must land before any ticket that depends on its schema.

## Replenishment

The backlog covers Phases 0–6. When a ticket is found to be too large during
execution, split it into smaller issues and link them as `blocked_by` children;
do not expand the original ticket. When requirements change, add a new ADR and
re-ticket rather than silently changing acceptance criteria.
