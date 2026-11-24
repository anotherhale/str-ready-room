# WINGMAN State

Live coordinator state. GitHub Issues remain authoritative for ticket status; this
file records what the last session actually verified and what the next session
should do. Update it at the end of every run.

**Last updated:** 2026-11-24 (session 6)

## Artifact map

WINGMAN's required state files map onto the artifacts this repository already
uses. Do not create duplicate sources of truth.

| WINGMAN requirement | Where it lives |
|---|---|
| `STATE.md` | This file |
| `ROADMAP.md` | Phases in `docs/SQUADRON_PLATFORM_EXPANSION.md`; strategic summary in `BACKLOG_DECOMPOSITION.md` |
| `BACKLOG.md` | `BACKLOG_DECOMPOSITION.md` (derivation) + GitHub Issues (authoritative status) |
| `EXECUTION_LOG.md` | `EXECUTION_LOG.md` |
| `DECISIONS.md` | `DECISIONS.md` (coordination decisions + ADR index) |
| `ARCHITECTURE_MAP.md` | `ARCHITECTURE_MAP.md` |
| `AGENT_REGISTRY.md` | `AGENT_REGISTRY.md` |
| `CHECKPOINT.json` | `CHECKPOINT.json` |

## Current product status

READY ROOM is a working single-user operational-awareness demo: shared tasks with
derived urgency, recurrence as a chain of task rows, a briefing, calendar and
mailbox integrations, and demo seed/reset. It is verified green and
containerized. It has **no authentication**, **no squadron/membership model**, and
**no AI assistant**; those are the expansion.

| Area | State | Evidence |
|---|---|---|
| Backend (FastAPI, DDD + hexagonal) | Working | 206 tests pass, ruff clean |
| Frontend (React/TS SPA) | Working | 39 tests pass, typecheck clean, build succeeds |
| Deployment | Single-host Docker Compose, SQLite volume, Radicale + GreenMail | `docker-compose.yml` |
| Identity | `single_user` demo adapter only — no login, no session | `backend/app/adapters/identity/` |
| Authorization | Permission checks exist; no scope/ownership model for multiple principals | `backend/app/domain/authorization/` |
| Squadron / membership | Absent | — |
| Jev / agent runtime | Absent | — |

## Phase context

Phase 0 — decisions and foundations. No application behaviour changes until the
ADR set is settled; the ADR tickets are the only work in flight.

## Decisions in force

- **ADR-002 accepted and merged** (PR #109, issue #4; now on `main`). First mechanism: local
  credentials plus server-side sessions; OIDC is an extension seam only. stdlib
  `scrypt` hashing, opaque 256-bit tokens with only the SHA-256 stored, 30-minute
  idle / 12-hour absolute expiry, nine enumerated revocation triggers, and a
  fail-closed guard that refuses `SingleUserAuthProvider` outside `demo`/`test`.
  See `docs/adr/ADR-002-authentication-session.md`.
- **ADR-001 accepted and merged to `main`** (`90decc5`, PR #105). Target:
  self-hosted single host inside a controlled network. Classification ceiling:
  **unclassified, synthetic data only**. No-egress default. See
  `docs/adr/ADR-001-deployment-classification.md`.
- **Q1–Q7 answered with adopted working defaults** (product-owner decision,
  2026-11-24): controlled-network single host; UNCLASSIFIED ceiling; no internet
  egress by default, with an internal controlled-network endpoint allowed per
  integration; minimal personnel fields only; retain indefinitely with explicit
  authorized deletion; operator nightly backups with 30-day retention
  (RPO 24h / RTO 4h); secrets injected as environment variables from an
  operator-managed store.
- **Non-blocking ADR defaults accepted as written** (product owner,
  2026-11-24): ADR-002 A1–A5, ADR-004 Q1–Q5, ADR-005 I1–I5. Named-owner
  confirmations remain non-blocking and can amend these defaults later.
- **ADR-004 accepted and merged** (PR #108, issue #6; now on `main`). Fixes five roles
  (`squadron_admin`, `officer`, `team_lead`, `member`, `read_only`), a
  54-permission catalog (20 existing + 34 new), a role x permission grant matrix
  with an explicit scope ceiling per grant, and an ordered deny-by-default
  evaluation: membership -> permission -> scope -> relationship -> approval.
  Agents hold no roles and act only by revocable delegation; they never record
  human accountability. See `docs/adr/ADR-004-role-permission-matrix.md`.
- **ADR-005 accepted and merged** (PR #111, issue #7, `main` @ `dc98f8d`).
  `squadron_id` is a required positional argument on every squadron-scoped
  repository method and is filtered in SQL; repositories never commit; a
  versioned forward-only migration runner with a `schema_migrations` ledger
  replaces the additive helper; every existing table backfills to one
  deterministic bootstrap squadron; Alembic is deferred.
  See `docs/adr/ADR-005-data-isolation-migration.md`.
- **ADR-006 accepted and merged** (PR #114 -> `3d6efd6`, issue #8 closed).
  Four task scopes (`personal`/`shared`/`team`/`squadron`) with `personal` as the
  default for every capture path; exactly one accountable owner (a user), at most
  one typed assignee (user/team/duty position), many collaborators and watchers.
  Sharing is **one** `task_shares` table with `read`/`write`: a write share *is* a
  collaborator, a read share *is* a watcher, so access and the people-list cannot
  drift. `duty_position` is an assignee kind, never a fifth task scope. "No
  accountable owner" means the owner's membership is not `ACTIVE`, not a null
  column. Visibility is computed once and emits the repository filter keys.
  See `docs/adr/ADR-006-task-scope-sharing.md`.
- Those defaults are **project decisions, not accreditation**. The named official
  must still confirm each one before real data is stored, and none of them
  authorizes cloud hosting, default egress, or any compliance claim.

## Blockers

| Blocker | Effect | Owner |
|---|---|---|
| Formal confirmation of the Q1–Q7 defaults (product owner accepted defaults 2026-11-24; official sign-off outstanding, tracked in [#113](https://github.com/anotherhale/str-ready-room/issues/113)) | Real operational/personnel data cannot be stored until confirmed. Does **not** block the unclassified synthetic build or the remaining ADRs. | Authorizing Official, Security Officer, Privacy/HR, Records Manager, Operations |

Nothing currently blocks the remaining READY ADRs or the test harness.

## READY queue (dependency-satisfied, no open dependency issues)

Ordered by the selection hierarchy: critical architecture decisions first, then
security/authorization foundations, then prerequisites that unblock the most
downstream work.

| Order | Issue | Title | Priority | Est |
|---|---|---|---|---|
| 1 | [#9](https://github.com/anotherhale/str-ready-room/issues/9) | ADR-007: shared recurrence, duty-position routing, occurrence exceptions | P1-high | 20 min |
| 2 | [#14](https://github.com/anotherhale/str-ready-room/issues/14) | Multi-principal test harness and configurable test auth provider | P0-critical | 25 min |
| 3 | [#15](https://github.com/anotherhale/str-ready-room/issues/15) | CI workflow running backend and frontend verification | P1-high | 20 min |
| 4 | [#5](https://github.com/anotherhale/str-ready-room/issues/5) | ADR-003: squadron bootstrap, invitation, membership lifecycle | P1-high | 15 min |
| 5 | [#10](https://github.com/anotherhale/str-ready-room/issues/10) | ADR-008: agent identity, delegation, approval binding | P1-high | 20 min |
| 6 | [#11](https://github.com/anotherhale/str-ready-room/issues/11) | ADR-009: Jev provider, context assembly, failure strategy | P1-high | 20 min |
| 7 | [#12](https://github.com/anotherhale/str-ready-room/issues/12) | ADR-010: workflow persistence, retries, cancellation, idempotency | P1-high | 20 min |
| 8 | [#13](https://github.com/anotherhale/str-ready-room/issues/13) | ADR-011: notification channels/preferences and audit retention | P2-normal | 20 min |

## Blocked queue

| Issue | Blocked on |
|---|---|
| #16–#104 (implementation tickets) | Their ADR and foundation dependencies; see each issue |

## Next recommended ticket

**#9 — ADR-007: shared recurrence, duty-position routing, occurrence exceptions**
(P1-high). Rationale: its only dependency (#8, ADR-006) merged in `3d6efd6`, so
it is newly READY, and it is the last unmerged ADR that gates a whole
implementation lane (#38 recurrence). ADR-006 fixed the two inputs it needs:
occurrences inherit the series scope, and `duty_position` is an assignee kind
rather than a task scope.

Alternatives if #9 is claimed: **#14 — multi-principal test harness**
(P0-critical; ADR-002 and ADR-004 already give it its contracts), then
**#15 — CI workflow**, then **#5 — ADR-003**.

In flight: none.