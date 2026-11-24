# WINGMAN State

Live coordinator state. GitHub Issues remain authoritative for ticket status; this
file records what the last session actually verified and what the next session
should do. Update it at the end of every run.

**Last updated:** 2026-11-24 (session 3)

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
- **ADR-004 accepted, awaiting merge** (PR #108, issue #6). Fixes five roles
  (`squadron_admin`, `officer`, `team_lead`, `member`, `read_only`), a
  54-permission catalog (20 existing + 34 new), a role x permission grant matrix
  with an explicit scope ceiling per grant, and an ordered deny-by-default
  evaluation: membership -> permission -> scope -> relationship -> approval.
  Agents hold no roles and act only by revocable delegation; they never record
  human accountability. See `docs/adr/ADR-004-role-permission-matrix.md`.
- Those defaults are **project decisions, not accreditation**. The named official
  must still confirm each one before real data is stored, and none of them
  authorizes cloud hosting, default egress, or any compliance claim.

## Blockers

| Blocker | Effect | Owner |
|---|---|---|
| Formal confirmation of the Q1–Q7 defaults | Real operational/personnel data cannot be stored until confirmed. Does **not** block the unclassified synthetic build or the remaining ADRs. | Authorizing Official, Security Officer, Privacy/HR, Records Manager, Operations |
| ADR-004 (#6) awaiting merge in PR #108 | #18 and #19 stay `blocked`; the Phase 2/3 domain lanes cannot start | Reviewer |

Nothing currently blocks ticket execution.

## READY queue (dependency-satisfied, no open dependency issues)

Ordered by the selection hierarchy: critical architecture decisions first, then
security/authorization foundations, then prerequisites that unblock the most
downstream work.

| Order | Issue | Title | Priority | Est |
|---|---|---|---|---|
| 1 | [#4](https://github.com/anotherhale/str-ready-room/issues/4) | ADR-002: authentication provider, session storage, cookie strategy | P0-critical | 20 min |
| 2 | [#5](https://github.com/anotherhale/str-ready-room/issues/5) | ADR-003: squadron bootstrap, invitation, membership lifecycle | P1-high | 15 min |
| 3 | [#6](https://github.com/anotherhale/str-ready-room/issues/6) | ADR-004: role and scoped-permission matrix | P0-critical | 20 min |
| 4 | [#7](https://github.com/anotherhale/str-ready-room/issues/7) | ADR-005: data isolation, owner migration, schema evolution | P0-critical | 20 min |
| 5 | [#8](https://github.com/anotherhale/str-ready-room/issues/8) | ADR-006: task scope, sharing, accountable ownership | P0-critical | 20 min |
| 6 | [#14](https://github.com/anotherhale/str-ready-room/issues/14) | Multi-principal test harness and configurable test auth provider | P0-critical | 25 min |
| 7 | [#15](https://github.com/anotherhale/str-ready-room/issues/15) | CI workflow running backend and frontend verification | P1-high | 20 min |
| 8 | [#10](https://github.com/anotherhale/str-ready-room/issues/10) | ADR-008: agent identity, delegation, approval binding | P1-high | 20 min |
| 9 | [#11](https://github.com/anotherhale/str-ready-room/issues/11) | ADR-009: Jev provider, context assembly, failure strategy | P1-high | 20 min |
| 10 | [#12](https://github.com/anotherhale/str-ready-room/issues/12) | ADR-010: workflow persistence, retries, cancellation, idempotency | P1-high | 20 min |
| 11 | [#13](https://github.com/anotherhale/str-ready-room/issues/13) | ADR-011: notification channels/preferences and audit retention | P2-normal | 20 min |

## Blocked queue

| Issue | Blocked on |
|---|---|
| [#9](https://github.com/anotherhale/str-ready-room/issues/9) ADR-007 | #8 |
| #16–#104 (implementation tickets) | Their ADR and foundation dependencies; see each issue |

## Next recommended ticket

**#4 — ADR-002 (authentication provider, session storage, and cookie strategy).**
Rationale: ADR-001 §4 already fixes its inputs — a self-contained auth path with
no assumed IdP, server-side revocable sessions, `HttpOnly`/`SameSite`/`Secure`
cookies, and a demo provider that startup must refuse outside the demo
environment. It is P0-critical and gates every identity-dependent ticket, and the
questions are settled enough to decide in one window.

Alternative if #4 is already claimed: **#5 — ADR-003**, then **#6 — ADR-004**.
Do not start #9 (ADR-007) until #8 is closed.
