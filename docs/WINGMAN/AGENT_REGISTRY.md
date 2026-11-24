# Agent Registry

Roles WINGMAN may delegate to. Delegation is bounded: every task maps to one
GitHub issue, has explicit scope and acceptance criteria, has a single owner, and
fits the execution window. WINGMAN keeps coordination, architecture, integration,
validation, GitHub updates, and checkpointing.

## Rules

- One active implementation session at a time unless file sets are provably
  disjoint. Never parallelize tickets joined by a dependency.
- ADR tickets are safe to parallelize *only* if each writes its own file and the
  edit to `docs/adr/README.md` is serialized.
- Limit: 3 major and 8 minor agents. Prefer one focused agent over many.
- A delegated agent never pushes to `main`, never merges, and never weakens
  authorization to make a test pass.

## Roles

| Role | Scope | Primary tickets | Verification |
|---|---|---|---|
| **ARCHITECT** | ADRs, boundary decisions, migration strategy. Writes `docs/adr/ADR-*.md` and the index. | #3–#13 | Decision is complete, alternatives recorded, consequences stated, no code changed |
| **BACKEND** | Domain, application services, adapters, API. Respects the inward dependency rule and the SQLAlchemy confinement rule. | #16–#29, #32–#46, #51–#59, #61–#70, #74–#79, #83–#85, #88–#89, #91–#93, #95–#96, #98–#99 | `pytest`, `ruff`, architecture tests |
| **FRONTEND** | React/TS views, components, API client. Maps server states; never re-derives urgency or recurrence. | #30–#31, #47–#48, #50, #60, #71, #86, #90, #94, #97, #100 | `npm run test:run`, `npm run typecheck`, `npm run build` |
| **AI PLATFORM** | Jev port/registry, context assembly, tool gateway, provider failure handling. No new vendor SDK in the domain. | #64–#67, #69, #72 | Provider-neutral fake provider tests; no network in tests |
| **SECURITY** | Permission matrix, scope enforcement, session/token lifecycle, agent delegation and approval binding. | #18, #19, #24–#27, #37, #75, #77, #80–#82, #84 | Denial-path tests; ownership *and* permission both enforced |
| **QA** | Multi-principal harness, isolation and denial suites, end-to-end journeys. | #14, #34, #49, #62, #73, #87 | Tests fail for the right reason before the fix |
| **DEVOPS** | CI workflow, container health, startup ordering. | #15 | Workflow runs both suites on push and PR |

## Current assignment

| Role | Ticket | Status |
|---|---|---|
| ARCHITECT | #3 ADR-001 | In verification (PR #105) |
| — | #5 ADR-003 | Unassigned, next recommended |
