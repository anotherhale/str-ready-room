# Backlog Decomposition — Squadron Platform Expansion

**Generated:** 2026-11-24  
**Repository:** `anotherhale/str-ready-room`  
**GitHub Issues are authoritative for execution.** This document is a reporting and traceability artifact, synchronized with the issue set at the time of generation.

## Source documents reviewed

- `docs/SQUADRON_PLATFORM_EXPANSION.md` — product areas, phases, acceptance scenarios, non-goals, agent/approval contracts (branch `feature/squadron-platform-expansion`, PR #1).
- `README.md` — product behaviour, architecture, API, configuration, limitations.
- `AGENTS.md` — durable invariants, boundaries, runtime gotchas.
- `DECISIONS.md` / `AI-DECISIONS.md` — the first-cut engineering journal (D-001…D-039).
- `BUILD_STATUS.md` — verified milestones M0–M13 with evidence.
- `PREBRIEF.md` — discovery notes, assumptions, validation questions.
- Backend/frontend source and tests — implementation baseline.
- GitHub state — 1 open PR (#1), no existing issues, no milestones, default labels only.

## Implementation baseline

- The single-operator READY ROOM product is complete and validated: **206 backend tests passed**, `ruff` clean, **39 frontend tests passed**, typecheck/build clean on 2026-11-24.
- Existing foundations to preserve: DDD/hexagonal boundaries, persistence unit-of-work port, derived urgency, recurrence chain, identity/authorization seams, architecture tests, Docker runtime.
- The expansion is almost entirely **MISSING**: real auth/sessions, squadron/team/duty positions, scoping, shared tasks, acknowledgment, handoffs, audit, shared recurrence, Jev, agent runtime, approvals, notifications, turnover, search, and knowledge.
- Full evidence: `BASELINE_ASSESSMENT.md`.

## Requirements

- Total requirements identified: **134**.
- Already satisfied (COMPLETE): **14**.
- Partial: **9**; missing: **110**; blocked on decision: **1**.
- Requirements requiring work: **120**.
- Requirement domains: AI, AI / Audit, AI / Security, Architecture, Audit, Authorization, Briefing, Briefing / AI, DevOps, DevOps / Security, Handoff, Handoff / AI, Identity, Knowledge, Notifications, Notifications / Tasks, Operations, Persistence, QA, QA / AI, QA / Audit, QA / Security, Recurrence, Security, Squadron, Tasks.

## Backlog metrics

| Metric | Value |
|---|---:|
| Implementation tickets created | 100 |
| Tickets updated/reused | 0 |
| Initially READY (zero dependencies) | 11 |
| Initially BLOCKED | 89 |
| Total estimated agent minutes | 2290 |
| Average estimate | 22.9 minutes |
| Maximum estimate | 25 minutes |

### By phase

| Phase | Tickets | Estimated minutes |
|---|---:|---:|
| Phase 0 — Discovery & Engineering Foundation | 13 | 265 |
| Phase 1 — Squadron Foundation | 19 | 430 |
| Phase 2 — Shared Task Platform | 16 | 370 |
| Phase 3 — Recurring Responsibilities | 13 | 305 |
| Phase 4 — Jev Assistant | 10 | 235 |
| Phase 5 — Agent Runtime & Approvals | 14 | 330 |
| Phase 6 — Operational Continuity | 15 | 355 |

### By priority

| Priority | Tickets |
|---|---:|
| P0 | 27 |
| P1 | 60 |
| P2 | 9 |
| P3 | 4 |

### By work type

| Type | Tickets |
|---|---:|
| Backend | 51 |
| Frontend | 12 |
| Architecture | 11 |
| Security | 11 |
| AI | 7 |
| QA | 6 |
| DevOps | 1 |
| Docs | 1 |

## Dependency overview

- Dependency links recorded: **173**.
- Tickets with no dependencies: **11**.
- Longest dependency chain (by estimated time): **470 minutes** across 20 tickets.
- Dependency cycles: **none** (validated before creation).
- Every ticket body lists its dependencies and the rule that blocked tickets must not start.

### Critical path

```text
P0-05 #7 -> P1-01 #16 -> P1-02 #17 -> P2-01 #35 -> P3-01 #51 -> P3-02 #52 -> P3-03 #53 -> P3-05 #55 -> P3-06 #56 -> P3-07 #57 -> P3-08 #58 -> P3-09 #59 -> P4-02 #65 -> P4-03 #66 -> P4-04 #67 -> P4-07 #70 -> P6-05 #92 -> P6-09 #96 -> P6-10 #97 -> P6-14 #101
```

This is the longest estimate-weighted chain. It is the sequence to protect when scheduling: delay on any ticket in it delays the end-to-end capability.

## Blocking decisions

The following ADRs are prerequisites for dependent work. They are READY (no dependencies) and should be resolved first:

- #3 — ADR-001: Decide deployment, classification, and data-handling constraints
- #4 — ADR-002: Decide authentication provider, session storage, and cookie strategy
- #5 — ADR-003: Define squadron bootstrap, invitation, and membership lifecycle
- #6 — ADR-004: Define the role and scoped-permission matrix
- #7 — ADR-005: Decide squadron data isolation, owner migration, and schema evolution
- #8 — ADR-006: Define task scope, sharing, and accountable-ownership semantics
- #9 — ADR-007: Define shared recurrence, duty-position routing, and occurrence-exception semantics
- #10 — ADR-008: Define agent identity, delegation, and approval binding
- #11 — ADR-009: Decide Jev AI provider, context assembly, and failure strategy
- #12 — ADR-010: Decide workflow persistence, retries, cancellation, and idempotency
- #13 — ADR-011: Decide notification channels/preferences and audit retention

`ADR-001` (deployment/classification) is the one decision that cannot be fully made by an agent; it requires human/organizational input. Dependent production-authentication work is blocked until it is recorded, but local development can proceed with synthetic data and the demo identity guard.

## READY queue (initial)

Only zero-dependency tickets are marked `ready` at creation. Ordered by priority and enabling value:

| Order | Issue | Ticket | Title | Est. | Why it is next |
|---:|---|---|---|---:|---|
| 1 | #3 | P0-01 | ADR-001: Decide deployment, classification, and data-handling constraints | 20 | Constrains auth, hosting, and data handling; unblocks the production guard. |
| 2 | #6 | P0-04 | ADR-004: Define the role and scoped-permission matrix | 20 | Defines the permission matrix every scoped feature consumes. |
| 3 | #7 | P0-05 | ADR-005: Decide squadron data isolation, owner migration, and schema evolution | 20 | Defines isolation, tenant key, migration, and schema evolution. |
| 4 | #8 | P0-06 | ADR-006: Define task scope, sharing, and accountable-ownership semantics | 20 | Defines task scope and ownership semantics for Phase 2. |
| 5 | #14 | P0-12 | Build the multi-principal test harness and configurable test auth provider | 20 | Enables multi-user isolation tests before real login exists. |
| 6 | #5 | P0-03 | ADR-003: Define squadron bootstrap, invitation, and membership lifecycle | 15 | Defines bootstrap and membership lifecycle for Phase 1. |
| 7 | #11 | P0-09 | ADR-009: Decide Jev AI provider, context assembly, and failure strategy | 20 | Defines the offline-capable AI provider/context strategy. |
| 8 | #12 | P0-10 | ADR-010: Decide workflow persistence, retries, cancellation, and idempotency | 20 | Defines durable workflow state before the runtime. |
| 9 | #15 | P0-13 | Add a CI workflow that runs backend and frontend verification | 20 | Gives every future PR independent CI evidence. |
| 10 | #10 | P0-08 | ADR-008: Define agent identity, delegation, and approval binding | 25 | Defines agent delegation/approval before any agent code. |
| 11 | #13 | P0-11 | ADR-011: Decide notification channels/preferences and audit retention | 20 | Defines notification/audit policy before events are emitted. |

## Risks

- **Spec not merged.** The expansion spec lives on PR #1. Tickets carry enough context to start, and instruct sessions to fetch the branch. If PR #1 is abandoned, re-home the spec before Phase 1.
- **Classification/hosting unknown.** ADR-001 needs human input; do not store real sensitive data until it is resolved.
- **Migration risk.** Adding a tenant key and sharing to existing tables is the highest-risk change. ADR-005 and P1-17 must land before shared features; migrations must be reversible/tested against fixtures.
- **Authorization drift.** Visibility must be computed once and applied to list/detail/search/summary/notification/AI paths. P2-03, P6-09, P6-11, and P4-10 are the guard rails.
- **Agent over-reach.** The tool gateway and approval binding are the security boundary; P5-08/P5-11/P5-14 must not be shortcut.
- **Scope creep into enterprise features.** Non-goals are explicit: no multi-tenant admin, workflow designer, policy language, DMS, or outbound messaging. Tickets call this out in Out of Scope.
- **25-minute sizing.** Every ticket is 15–25 minutes. If a session finds one larger in practice, split it rather than overrunning the window.
- **Parallel conflicts.** Migrations and the ADR index are shared files; do not run dependent migration tickets concurrently.

## Requirements coverage statement

Every non-COMPLETE requirement maps to at least one issue, and every issue maps to at least one requirement. COMPLETE requirements are listed for traceability but intentionally have no implementation ticket. The one BLOCKED requirement (reference links/attachments) is tracked by a gated P3 ticket so the constraint remains visible.

## Recommendations

1. Resolve the Phase 0 ADRs first; they are cheap and unblock everything.
2. Land ADR-001 with explicit human sign-off before any real data or production auth work.
3. Implement Phase 1 strictly before Phase 2; shared tasks without squadron scoping are unsafe.
4. Treat P1-17 (data migration) as a release gate, not cleanup.
5. Keep the existing 206/39 test baseline green on every ticket.
6. Do not start Phase 4/5 until Phase 2/3 visibility and audit are proven.
7. Re-run the traceability generator whenever issues are added or split.

## Ambiguities and deferred items

- **Escalation/follow-up (R-REC-11)** is explicitly optional; P3-13 is P3-low and may be dropped if the product does not confirm it.
- **Notes/references (R-NOTES)** are optional later; P6-12/P6-13 are P3-low and must remain a small knowledge feature, not a DMS.
- **Reference links/attachments (R-TASK-07)** are blocked on storage and security controls; P6-15 is limited to URLs and may be closed if ADR-001 does not permit them.
- **Approval quorum** (single approver vs multiple) is left to ADR-008; no multi-approver ticket exists until the decision requires it.
- **OIDC vs local credentials** is decided by ADR-002 after ADR-001; the backlog supports either without changing the domain.
- **Notification channels beyond in-app** are out of scope until configured and tested; no email/push tickets exist.

## Issue index

| Ticket | Issue | Phase | Priority | Type | Est. | Dependencies | Title |
|---|---|---|---|---|---:|---|---|
| P0-01 | #3 | P0 | P0 | Architecture | 20 | — | ADR-001: Decide deployment, classification, and data-handling constraints |
| P0-02 | #4 | P0 | P0 | Architecture | 20 | #3 | ADR-002: Decide authentication provider, session storage, and cookie strategy |
| P0-03 | #5 | P0 | P1 | Architecture | 15 | — | ADR-003: Define squadron bootstrap, invitation, and membership lifecycle |
| P0-04 | #6 | P0 | P0 | Architecture | 20 | — | ADR-004: Define the role and scoped-permission matrix |
| P0-05 | #7 | P0 | P0 | Architecture | 20 | — | ADR-005: Decide squadron data isolation, owner migration, and schema evolution |
| P0-06 | #8 | P0 | P0 | Architecture | 20 | — | ADR-006: Define task scope, sharing, and accountable-ownership semantics |
| P0-07 | #9 | P0 | P1 | Architecture | 25 | #8 | ADR-007: Define shared recurrence, duty-position routing, and occurrence-exception semantics |
| P0-08 | #10 | P0 | P1 | Architecture | 25 | — | ADR-008: Define agent identity, delegation, and approval binding |
| P0-09 | #11 | P0 | P1 | Architecture | 20 | — | ADR-009: Decide Jev AI provider, context assembly, and failure strategy |
| P0-10 | #12 | P0 | P1 | Architecture | 20 | — | ADR-010: Decide workflow persistence, retries, cancellation, and idempotency |
| P0-11 | #13 | P0 | P2 | Architecture | 20 | — | ADR-011: Decide notification channels/preferences and audit retention |
| P0-12 | #14 | P0 | P0 | QA | 20 | — | Build the multi-principal test harness and configurable test auth provider |
| P0-13 | #15 | P0 | P1 | DevOps | 20 | — | Add a CI workflow that runs backend and frontend verification |
| P1-01 | #16 | P1 | P0 | Backend | 20 | #5, #7 | Domain: Squadron aggregate and membership lifecycle |
| P1-02 | #17 | P1 | P1 | Backend | 20 | #16 | Domain: Team and DutyPosition with holder history |
| P1-03 | #18 | P1 | P0 | Backend | 20 | #6 | Domain: Expand permissions and add role grants for the squadron roles |
| P1-04 | #19 | P1 | P0 | Security | 25 | #16, #17, #18 | Domain: Scope-aware authorization for squadron, team, and duty-position access |
| P1-05 | #20 | P1 | P0 | Backend | 25 | #16, #17, #7 | Persistence: Models, mappers, and migration for squadron, membership, team, and duty positions |
| P1-06 | #21 | P1 | P0 | Backend | 25 | #20 | Persistence: Squadron/team/duty-position repositories and DatabasePort wiring |
| P1-07 | #22 | P1 | P1 | Backend | 25 | #21, #19 | Application: SquadronService and MembershipService |
| P1-08 | #23 | P1 | P1 | Backend | 25 | #21, #19 | Application: TeamService and DutyPositionService |
| P1-09 | #24 | P1 | P0 | Security | 25 | #4, #21 | Identity: Credential store and password hashing for local authentication |
| P1-10 | #25 | P1 | P0 | Security | 25 | #4, #21, #24 | Identity: Server-side session entity, repository, and token lifecycle |
| P1-11 | #26 | P1 | P0 | Security | 20 | #25, #19 | Identity: SessionAuthProvider adapter and registry wiring |
| P1-12 | #27 | P1 | P0 | Backend | 20 | #26 | API: Authentication endpoints and secure session cookie |
| P1-13 | #28 | P1 | P1 | Backend | 20 | #22, #26 | API: Squadron and membership administration endpoints |
| P1-14 | #29 | P1 | P1 | Backend | 20 | #23, #26 | API: Team and duty-position administration endpoints |
| P1-15 | #30 | P1 | P0 | Frontend | 25 | #27 | Frontend: Login, logout, and session-aware API client |
| P1-16 | #31 | P1 | P1 | Frontend | 25 | #28, #29, #30 | Frontend: Squadron, team, membership, duty-position administration and profile |
| P1-17 | #32 | P1 | P0 | Backend | 25 | #20, #21, #22 | Migration: Map existing owner-scoped data into the bootstrap squadron and personal workspace |
| P1-18 | #33 | P1 | P1 | Backend | 20 | #22, #23, #32 | Seed and reset the squadron demo with a second member |
| P1-19 | #34 | P1 | P0 | QA | 20 | #27, #28, #29, #32 | Integration tests: two-user isolation and access denial across the API |
| P2-01 | #35 | P2 | P0 | Backend | 25 | #8, #16, #17 | Domain: Task scope and distinct accountable-owner, assignee, collaborator, and watcher roles |
| P2-02 | #36 | P2 | P1 | Backend | 20 | #35 | Domain: Assignment acknowledgment state machine separate from completion |
| P2-03 | #37 | P2 | P0 | Security | 25 | #19, #35 | Domain: Task visibility and sharing authorization rules |
| P2-04 | #38 | P2 | P1 | Backend | 20 | #35 | Domain: Task comments, activity, completion notes, and history events |
| P2-05 | #39 | P2 | P1 | Backend | 25 | #35, #36 | Domain: Task reassignment and handoff state machine |
| P2-06 | #40 | P2 | P0 | Backend | 20 | #13, #19 | Domain: Append-only audit entry and writer port |
| P2-07 | #41 | P2 | P0 | Backend | 25 | #35, #36, #38, #39, #40, #7 | Persistence: Task collaboration columns, share/handoff/comment/audit tables, and migration |
| P2-08 | #42 | P2 | P1 | Backend | 25 | #41, #37 | Persistence: Collaboration, handoff, comment, and audit repositories |
| P2-09 | #43 | P2 | P1 | Backend | 25 | #42, #37 | Application: Create and edit shared tasks with assignment and collaborators |
| P2-10 | #44 | P2 | P1 | Backend | 25 | #43, #39 | Application: Acknowledgment, reassignment/handoff, and completion-with-note use cases |
| P2-11 | #45 | P2 | P1 | Backend | 20 | #43, #42, #40 | Application: Comments, activity feed, and audit emission across task use cases |
| P2-12 | #46 | P2 | P0 | Backend | 25 | #43, #44, #45 | API: Task collaboration endpoints, visibility filtering, and integration tests |
| P2-13 | #47 | P2 | P1 | Frontend | 25 | #46 | Frontend: Shared-task creation and scope/ownership badges |
| P2-14 | #48 | P2 | P1 | Frontend | 25 | #46 | Frontend: Task detail drawer with comments, activity, acknowledgment, and handoff |
| P2-15 | #49 | P2 | P0 | QA | 20 | #46 | Integration test: shared-task journey from creation to completion with history |
| P2-16 | #50 | P2 | P2 | Frontend | 20 | #46 | Frontend: Dashboard sections for awaiting acknowledgment and pending handoffs |
| P3-01 | #51 | P3 | P1 | Backend | 25 | #9, #35 | Domain: Extend RecurrenceRule with scope, duty position, default assignment, due time, and pause/resume |
| P3-02 | #52 | P3 | P1 | Backend | 25 | #51 | Domain: Per-occurrence exceptions (due-date change, reassignment, skip/cancel) |
| P3-03 | #53 | P3 | P1 | Backend | 25 | #51, #52 | Domain: Series revision history and future-vs-single edit semantics |
| P3-04 | #54 | P3 | P1 | Backend | 25 | #51, #17 | Domain: Duty-position holder change routes future occurrences only |
| P3-05 | #55 | P3 | P1 | Backend | 25 | #51, #52, #53, #54, #7 | Persistence: Models, mappers, and migration for recurrence extensions, exceptions, and revisions |
| P3-06 | #56 | P3 | P1 | Backend | 20 | #55 | Persistence: Repositories for recurrence exceptions and revisions |
| P3-07 | #57 | P3 | P1 | Backend | 25 | #56, #43 | Application: Create and edit shared series with duty-position routing and acknowledgment requirements |
| P3-08 | #58 | P3 | P1 | Backend | 25 | #57, #52, #53 | Application: Occurrence exceptions, future-vs-single edit, pause/resume, and end-series use cases |
| P3-09 | #59 | P3 | P1 | Backend | 25 | #57, #58 | API: Recurrence endpoints for shared series, exceptions, revisions, and lifecycle |
| P3-10 | #60 | P3 | P1 | Frontend | 25 | #59 | Frontend: Recurrence editor with scope, duty position, and future-vs-single choice |
| P3-11 | #61 | P3 | P1 | Backend | 20 | #57 | Operational scan: recurring responsibilities at risk and duty-routing visibility |
| P3-12 | #62 | P3 | P1 | QA | 20 | #59 | Integration tests: shared recurrence idempotency, exception isolation, and holder-change routing |
| P3-13 | #63 | P3 | P3 | Backend | 20 | #57 | Optional: Series escalation and follow-up rules |
| P4-01 | #64 | P4 | P1 | AI | 25 | #11 | AI: Provider-neutral port, registry, and deterministic fake provider |
| P4-02 | #65 | P4 | P1 | AI | 25 | #64, #46, #59, #34 | AI: Authorization-aware context assembly for Jev |
| P4-03 | #66 | P4 | P1 | AI | 25 | #65, #10 | AI: Read-only tool catalog and tool gateway skeleton |
| P4-04 | #67 | P4 | P1 | AI | 25 | #66 | AI: Jev read-only conversation service with grounded answers and citations |
| P4-05 | #68 | P4 | P1 | Backend | 25 | #65, #32 | Briefings: Deterministic briefing service refactor and snapshot persistence |
| P4-06 | #69 | P4 | P1 | AI | 25 | #66, #68 | AI: Reviewable draft actions for tasks, assignments, and recurrence changes |
| P4-07 | #70 | P4 | P1 | Backend | 20 | #67, #69 | API: Jev chat and draft review endpoints |
| P4-08 | #71 | P4 | P2 | Frontend | 25 | #70 | Frontend: Jev chat panel with citations and draft review |
| P4-09 | #72 | P4 | P1 | AI | 20 | #70 | AI: Provider failure, timeout, and graceful degradation handling |
| P4-10 | #73 | P4 | P1 | QA | 20 | #70 | QA: Jev grounding and authorization test suite |
| P5-01 | #74 | P5 | P1 | Backend | 20 | #10 | Domain: Agent identity with stable identifier and version |
| P5-02 | #75 | P5 | P1 | Security | 25 | #74 | Domain: Delegation grant with purpose, scope, expiry, and revocation |
| P5-03 | #76 | P5 | P1 | Backend | 25 | #12, #74 | Domain: Durable workflow run state machine |
| P5-04 | #77 | P5 | P1 | Security | 25 | #74, #10 | Domain: Approval bound to exact action and parameters |
| P5-05 | #78 | P5 | P1 | Backend | 25 | #74, #75, #76, #77, #7 | Persistence: Tables, mappers, and migration for agents, delegations, runs, approvals, and tool invocations |
| P5-06 | #79 | P5 | P1 | Backend | 25 | #78, #40 | Persistence: Agent runtime repositories and audit linkage |
| P5-07 | #80 | P5 | P1 | Security | 20 | #79 | Security: Capability catalog and deterministic risk classification |
| P5-08 | #81 | P5 | P0 | Security | 25 | #80, #66, #79 | Tool gateway: Full execution contract with delegation, budgets, idempotency, and approval gate |
| P5-09 | #82 | P5 | P1 | Security | 20 | #81 | Application/API: Delegation grant, list, and revoke |
| P5-10 | #83 | P5 | P1 | Backend | 25 | #81 | Application/API: Durable workflow run service with retry, cancel, and recovery |
| P5-11 | #84 | P5 | P0 | Security | 25 | #81, #83 | Application/API: Human approval gate for consequential actions |
| P5-12 | #85 | P5 | P1 | AI | 25 | #82, #83, #84 | Jev: Execute low-risk actions and request approval for consequential ones |
| P5-13 | #86 | P5 | P2 | Frontend | 25 | #83, #84 | Frontend: Approval inbox and workflow run history |
| P5-14 | #87 | P5 | P0 | QA | 20 | #85 | QA: Agent runtime security test suite |
| P6-01 | #88 | P6 | P1 | Backend | 20 | #13 | Domain: In-app notification, preferences, and aggregation |
| P6-02 | #89 | P6 | P1 | Backend | 25 | #88, #45, #57 | Notifications: Event emission with strict failure isolation |
| P6-03 | #90 | P6 | P2 | Frontend | 25 | #89 | API + Frontend: Notification center and preferences |
| P6-04 | #91 | P6 | P1 | Backend | 25 | #5 | Domain: Duty turnover package and its states |
| P6-05 | #92 | P6 | P1 | Backend | 25 | #91, #70, #45, #59 | Turnover: Package builder from authorised records, with optional Jev drafting |
| P6-06 | #93 | P6 | P1 | Backend | 25 | #92 | Turnover workflow: Outgoing review, incoming acknowledgment, and explicit item acceptance |
| P6-07 | #94 | P6 | P2 | Frontend | 25 | #93 | Frontend: Turnover package review and acknowledgment view |
| P6-08 | #95 | P6 | P1 | Backend | 25 | #68, #59, #23 | Briefings: Team status, squadron weekly, recurring status, and turnover briefing |
| P6-09 | #96 | P6 | P1 | Backend | 25 | #46, #61, #89, #92, #40 | Operations: Multi-scope operational scan with ownership, handoff, approval, and recent-change attention items |
| P6-10 | #97 | P6 | P2 | Frontend | 25 | #96 | Frontend: Scope switcher and expanded operational scan sections |
| P6-11 | #98 | P6 | P2 | Backend | 25 | #96, #65 | Search: Authorization-aware search across tasks, series, briefings, and notes |
| P6-12 | #99 | P6 | P3 | Backend | 25 | #19, #40 | Knowledge: Scoped notes/references domain, persistence, and API |
| P6-13 | #100 | P6 | P3 | Frontend | 20 | #99 | Frontend: Notes/references view with authoritative distinction |
| P6-14 | #101 | P6 | P2 | Docs | 20 | #97 | Docs: Update README, AGENTS.md, and ADR index for the squadron platform |
| P6-15 | #102 | P6 | P3 | Backend | 20 | #3, #99 | Reference links for tasks and notes after security controls are confirmed |

