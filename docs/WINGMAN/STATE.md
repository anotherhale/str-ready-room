# WINGMAN State

Live coordinator state. GitHub Issues remain authoritative for ticket status; this
file records what the last session actually verified and what the next session
should do. Update it at the end of every run.

**Last updated:** 2026-11-24 (session 1)

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

- **ADR-001 accepted** (deployment, classification, data handling). Chosen first
  target: self-hosted single host, controlled network. Classification ceiling:
  **unclassified, synthetic data only**. No-egress default. See
  `docs/adr/ADR-001-deployment-classification.md`.
- Seven organizational questions (Q1–Q7 in ADR-001) remain unanswered. They block
  *real data*, not the remaining ADRs, which decide an unclassified synthetic
  build.

## Blockers

| Blocker | Effect | Owner |
|---|---|---|
| ADR-001 organizational questions Q1–Q7 | Real operational/personnel data cannot be stored; cloud hosting unauthorized; retention/backup/secret policy undefined | Authorizing Official, Security Officer, Privacy/HR, Records Manager, Operations |
| PR #105 unmerged | Issue #3 stays in `verification`; **#4 (ADR-002) stays `blocked`** because #3 is not closed | Reviewer |
| PR for this state checkpoint unmerged | Coordinator state is not yet on `main`; the next session must read GitHub issues and this PR until merged | Reviewer |

## READY queue (dependency-satisfied, no open dependency issues)

Ordered by the selection hierarchy: critical architecture decisions first, then
security/authorization foundations, then prerequisites that unblock the most
downstream work.

| Order | Issue | Title | Priority | Est |
|---|---|---|---|---|
| 1 | [#5](https://github.com/anotherhale/str-ready-room/issues/5) | ADR-003: squadron bootstrap, invitation, membership lifecycle | P1-high | 15 min |
| 2 | [#6](https://github.com/anotherhale/str-ready-room/issues/6) | ADR-004: role and scoped-permission matrix | P0-critical | 20 min |
| 3 | [#7](https://github.com/anotherhale/str-ready-room/issues/7) | ADR-005: data isolation, owner migration, schema evolution | P0-critical | 20 min |
| 4 | [#8](https://github.com/anotherhale/str-ready-room/issues/8) | ADR-006: task scope, sharing, accountable ownership | P0-critical | 20 min |
| 5 | [#14](https://github.com/anotherhale/str-ready-room/issues/14) | Multi-principal test harness and configurable test auth provider | P0-critical | 25 min |
| 6 | [#15](https://github.com/anotherhale/str-ready-room/issues/15) | CI workflow running backend and frontend verification | P1-high | 20 min |
| 7 | [#10](https://github.com/anotherhale/str-ready-room/issues/10) | ADR-008: agent identity, delegation, approval binding | P1-high | 20 min |
| 8 | [#11](https://github.com/anotherhale/str-ready-room/issues/11) | ADR-009: Jev provider, context assembly, failure strategy | P1-high | 20 min |
| 9 | [#12](https://github.com/anotherhale/str-ready-room/issues/12) | ADR-010: workflow persistence, retries, cancellation, idempotency | P1-high | 20 min |
| 10 | [#13](https://github.com/anotherhale/str-ready-room/issues/13) | ADR-011: notification channels/preferences and audit retention | P2-normal | 20 min |

## Blocked queue

| Issue | Blocked on |
|---|---|
| [#4](https://github.com/anotherhale/str-ready-room/issues/4) ADR-002 | #3 (open until PR #105 merges) |
| [#9](https://github.com/anotherhale/str-ready-room/issues/9) ADR-007 | #8 |
| #16–#104 (implementation tickets) | Their ADR and foundation dependencies; see each issue |

## Next recommended ticket

**#5 — ADR-003 (squadron bootstrap, invitation, and membership lifecycle).**
Rationale: it is dependency-free, sized for one window, and defines the
membership record and lifecycle that ADR-004's role grants bind to. Doing it first
keeps ADR-004 from inventing membership states that ADR-003 then contradicts.

Alternative if #5 is already claimed: **#6 — ADR-004**, then **#7 — ADR-005**.

Do not start #4 (ADR-002) until #3 is closed, even though ADR-001's content is
final and validated on branch `wingman/adr-001-deployment-classification`.
