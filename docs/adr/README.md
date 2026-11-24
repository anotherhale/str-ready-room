# Architecture Decision Records

Decisions that materially constrain future work on the READY ROOM squadron
platform expansion. Each record states the context, the decision, its
consequences, and the questions it leaves open. When a decision changes, amend the
record rather than deleting it.

| ADR | Title | Status |
|---|---|---|
| [ADR-001](ADR-001-deployment-classification.md) | Deployment, classification, and data-handling constraints | Accepted; working defaults adopted for Q1-Q7, formal authorization for real data outstanding ([#113](https://github.com/anotherhale/str-ready-room/issues/113)) |
| [ADR-002](ADR-002-authentication-session.md) | Authentication provider, session storage, and cookie strategy | Accepted 2026-11-24 ([#4](https://github.com/anotherhale/str-ready-room/issues/4)) |
| ADR-003 | Squadron bootstrap, invitation, and membership lifecycle | Pending ([#5](https://github.com/anotherhale/str-ready-room/issues/5)) |
| [ADR-004](ADR-004-role-permission-matrix.md) | Role and scoped-permission matrix | Accepted 2026-11-24 ([#6](https://github.com/anotherhale/str-ready-room/issues/6)) |
| [ADR-005](ADR-005-data-isolation-migration.md) | Data isolation, owner migration, and schema evolution | Accepted 2026-11-24 ([#7](https://github.com/anotherhale/str-ready-room/issues/7)) |
| [ADR-006](ADR-006-task-scope-sharing.md) | Task scope, sharing, and accountable-ownership semantics | Accepted 2026-11-24 ([#8](https://github.com/anotherhale/str-ready-room/issues/8)) |
| [ADR-007](ADR-007-shared-recurrence.md) | Shared recurrence, duty-position routing, occurrence exceptions | Accepted 2026-11-24 ([#9](https://github.com/anotherhale/str-ready-room/issues/9)) |
| ADR-008 | Agent identity, delegation, and approval binding | Pending ([#10](https://github.com/anotherhale/str-ready-room/issues/10)) |
| ADR-009 | Jev AI provider, context assembly, and failure strategy | Pending ([#11](https://github.com/anotherhale/str-ready-room/issues/11)) |
| ADR-010 | Workflow persistence, retries, cancellation, and idempotency | Pending ([#12](https://github.com/anotherhale/str-ready-room/issues/12)) |
| ADR-011 | Notification channels/preferences and audit retention | Pending ([#13](https://github.com/anotherhale/str-ready-room/issues/13)) |

Product requirements live in `docs/SQUADRON_PLATFORM_EXPANSION.md` (merged to
`main` by PR #1). Durable repository invariants live in `AGENTS.md`.
