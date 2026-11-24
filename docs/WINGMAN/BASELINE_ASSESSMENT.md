# READY ROOM — Implementation Baseline Assessment

**Assessment date:** 2026-11-24
**Repository:** `anotherhale/str-ready-room`
**Baseline commit:** `5fdae63` (`main`, "Prepare for delivery: minimal build contexts and cold-start verification")
**Expansion specification:** `docs/SQUADRON_PLATFORM_EXPANSION.md` on branch
`feature/squadron-platform-expansion` (PR #1). The spec is **not yet merged** into
`main`.

This document records what actually exists, verified against the code and the
test suites, so the WINGMAN backlog does not re-implement completed work.

## Verification evidence

Commands were run in a clean local checkout on 2026-11-24:

| Gate | Command | Result |
|---|---|---|
| Backend unit + integration + architecture | `cd backend && .venv/bin/python -m pytest -q` | **206 passed** (1 third-party deprecation warning) |
| Backend lint | `cd backend && .venv/bin/ruff check .` | **All checks passed** |
| Frontend tests | `cd frontend && npm run test:run` | **39 passed** across 10 files |
| Frontend typecheck | `cd frontend && npm run typecheck` | clean (run as part of the documented gate) |
| Frontend build | `cd frontend && npm run build` | succeeds |

The environment was created with `uv venv .venv --python 3.12` and
`uv pip install -e ".[dev]"`; `npm ci` installed the frontend dependencies.
`BUILD_STATUS.md` records the prior live Docker verification (M0–M13), including
the four-service cold start, nginx origin checks, restart persistence, and the
calendar/mailbox integrations.

## Capability matrix

Status legend: **COMPLETE** (implemented and validated), **PARTIAL** (some
implementation), **MISSING**, **BROKEN**, **NEEDS VALIDATION**, **BLOCKED**.

### Core product (pre-expansion)

| Capability | Status | Evidence / notes |
|---|---|---|
| Dashboard-first operational scan (Today / Watch / Horizon, counts, readiness summary) | COMPLETE | `application/services/dashboard_service.py`; `tests/integration/test_dashboard.py`; live UI verified in BUILD_STATUS M4/M5 |
| Urgency derived, never stored | COMPLETE | `domain/tasks/urgency.py`; boundary tests in `tests/unit/domain/test_urgency.py` |
| Personal task CRUD, complete/reopen/delete | COMPLETE | `api/routers/tasks.py`, `application/services/task_service.py`; lifecycle tests |
| Idempotent completion and exactly one successor | COMPLETE | `domain/tasks/entities.py`, `tests/integration/test_recurrence_flow.py` |
| Recurrence chain (`series_id`, `recurrence_rule_id`, `occurrence_number`), no occurrence table | COMPLETE | `domain/tasks/entities.py`, `domain/tasks/recurrence.py`; month-end/leap-year/bounded no-backfill tests |
| Personal daily briefing from persisted data | COMPLETE | `application/services/briefing_service.py`; briefing tests |
| Quick capture, inventory filter/search/sort | COMPLETE | `frontend/src/components/QuickCapture`, `features/tasks/InventoryView`; Vitest |
| Categories, warning window, timezone settings | COMPLETE | `application/services/settings_service.py`, `category_service.py`; API + UI tests |
| Demo seeding and reset (idempotent, reseeds immediately) | COMPLETE | `application/services/demo_service.py`; `tests/integration/test_seed_reset.py` |
| Calendar cache-first integration + capture | COMPLETE | CalDAV adapter, `calendar_service.py`; live Radicale verification (M11–M13) |
| Read-only mailbox + capture | COMPLETE | IMAP adapter, `email_service.py`; GreenMail verification |
| Identity/authorization seams (`Principal`, `AuthProvider`, `Permission`, `Policy`, ownership) | COMPLETE (single-user only) | `domain/identity`, `domain/authorization`, `adapters/identity/single_user_provider.py` |
| Persistence port/unit of work, SQLAlchemy adapter, SQLite + PostgreSQL | COMPLETE | `application/ports/persistence.py`, `adapters/persistence/sqlalchemy/`; M8 shared suite |
| Architecture boundary enforcement | COMPLETE | `tests/architecture/test_boundaries.py` |
| Docker Compose one-command runtime | COMPLETE | `docker-compose.yml`; M0/M13 cold-start evidence |

### Squadron platform expansion

| Requirement area | Status | Gap |
|---|---|---|
| Real authentication + revocable server-side sessions | MISSING | Only `SingleUserAuthProvider`; no credentials, sessions, login, or cookie handling |
| Squadron, membership lifecycle, teams, roles | MISSING | No squadron/team/membership entities or persistence |
| Duty positions and holder history | MISSING | No duty-position model; needed for recurrence routing |
| Squadron/team scoping in queries | MISSING | All repositories scope by a single `owner_id` |
| Shared tasks (personal/shared/team/squadron) | MISSING | Tasks are owner-only; no `scope` column |
| Accountable owner vs assignee vs collaborators vs watchers | MISSING | Single `owner_id` only |
| Assignment acknowledgment separate from completion | MISSING | Status is only `open`/`completed` |
| Comments/activity, completion notes/evidence | MISSING | No comment/activity entity; completion only sets status |
| Reassignment and handoff | MISSING | No handoff workflow |
| General task audit/history | PARTIAL | Recurrence chain preserves occurrences; no audit trail for other actions |
| Shared recurrence, duty-position routing | MISSING | Rules are owner-only and edited in place |
| Per-occurrence exceptions and series revisions | MISSING | No exception/revision model |
| Multi-scope operational scan (unowned, awaiting ack, handoffs, at-risk, recent changes) | MISSING | Dashboard is owner-only |
| Team/squadron/recurring/turnover briefings + snapshots | PARTIAL | Personal briefing only; no snapshot store |
| Duty turnover workflow | MISSING | No turnover package |
| In-app notifications + preferences + failure isolation | MISSING | No notification model |
| Jev conversational assistant + grounded context | MISSING | No AI port, tools, or UI |
| Agent identity, delegation, approvals, durable workflows | MISSING | No agent runtime |
| Scoped notes/references | MISSING | No knowledge model |
| Scoped search across resources | MISSING | Task list has a `search` filter only |
| Data migration from owner-scoped records | MISSING | No tenant key or backfill |
| Production guard for demo identity | MISSING | `single_user` can be selected by env var with no environment guard |
| Deployment/classification decision record | MISSING | No ADR directory for the expansion |

## Baseline conclusions

1. The **single-operator product is genuinely complete and validated**; the backlog
   must not rebuild it.
2. The expansion requires a **new security and organisational foundation**
   (ADR-001…011, squadron/team models, scoping, real authentication) before any
   shared-work feature can be safely implemented.
3. The existing ports, architecture tests, and test harness are strong
   foundations; most work is additive.
4. The spec on PR #1 is the source of truth. It is not on `main`; WINGMAN tickets
   instruct agents to fetch it from the feature branch if needed and also carry
   enough context to start.

## How this assessment was produced

- Read `README.md`, `AGENTS.md`, `DECISIONS.md`, `AI-DECISIONS.md`,
  `BUILD_STATUS.md`, `PREBRIEF.md`, and `docs/SQUADRON_PLATFORM_EXPANSION.md`.
- Inspected the backend domain, application services, API routers, adapters,
  persistence models/migrations, composition root, and tests.
- Inspected the frontend app shell, views, components, services, and types.
- Ran the backend and frontend verification gates listed above.
- Inspected GitHub state (1 open PR, no issues, no milestones, default labels
  only) before creating the backlog.
