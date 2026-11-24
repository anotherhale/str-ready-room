# Architecture Map — as implemented

Verified against the working tree, not the roadmap. Update when a durable boundary
changes. Invariants that must not regress are stated in `AGENTS.md`; this file is
the structural view.

## Shape

Modular monolith. Backend is FastAPI with domain / application / adapters / api
layers; frontend is a React + TypeScript SPA. One deployable unit, one database.

```text
frontend/src/features/*  ──HTTP──>  backend/app/api/routers/*
                                        │
                                        v
                              backend/app/application/services/*
                                        │
                          ┌─────────────┴─────────────┐
                          v                           v
                backend/app/domain/*        application/ports/*
                (pure business rules)       (clock, identity, mail, persistence)
                                                      │
                                                      v
                                            backend/app/adapters/*
                                        (sqlalchemy, identity, authorization)
```

## Backend

| Path | Responsibility |
|---|---|
| `backend/app/domain/tasks/` | Task entity, enums, value objects, events, recurrence chain rules, derived urgency |
| `backend/app/domain/identity/` | `Principal`, identity ports/types |
| `backend/app/domain/authorization/` | Permission catalog, policies, authorization service |
| `backend/app/domain/settings/` | Operator settings entity |
| `backend/app/domain/shared/` | Clock port, shared errors |
| `backend/app/application/services/` | Use cases: tasks, recurrence, briefing, dashboard, settings, categories, demo, calendar, email, integration seeding |
| `backend/app/application/ports/` | `DatabasePort`, clock, identity, mail ports |
| `backend/app/application/dto/`, `commands/` | Use-case inputs and outputs |
| `backend/app/adapters/persistence/sqlalchemy/` | `models.py`, `mappers.py`, `repositories.py`, `database.py` (unit of work), `migrations.py` (additive, idempotent) |
| `backend/app/adapters/persistence/registry.py` | Dialect selection from `READY_ROOM_DATABASE_URL` |
| `backend/app/adapters/identity/` | `SingleUserAuthProvider` (demo identity) |
| `backend/app/adapters/authorization/` | Permission checks against the domain policies |
| `backend/app/api/routers/` | `tasks`, `operational`, `settings`, `calendar`, `email`, `system` (health, timezones) |
| `backend/app/api/dependencies/` | Principal resolution and dependency wiring |
| `backend/app/calendar/`, `backend/app/mailbox/` | Provider registries and adapters (CalDAV/Radicale, IMAP/SMTP/GreenMail) plus in-memory doubles |
| `backend/app/schemas/` | Request/response transport schemas |
| `backend/app/composition.py` | Composition root — the one place concrete adapters are chosen |
| `backend/app/config.py` | Environment settings (`READY_ROOM_*`) |

Dependency direction is inward: `domain` ← `application` ← `adapters`/`api`.
Architecture tests in `backend/tests/architecture/` enforce it, including that
`sqlalchemy` appears only under `adapters/persistence/sqlalchemy/`.

## Frontend

| Path | Responsibility |
|---|---|
| `frontend/src/features/tasks`, `dashboard`, `briefing`, `calendar`, `mailbox`, `settings` | Feature views |
| `frontend/src/components/` | `TaskCard`, `TaskDialog`, `QuickCapture`, `CaptureToTaskDialog`, `SectionPanel`, `UrgencyBadge` |
| `frontend/src/services/`, `lib/`, `types/` | API client, helpers, shared types |
| `frontend/src/styles/` | Tailwind entry |

The frontend maps server-derived states to labels, icons, and styles. It does not
reimplement urgency or recurrence rules.

## Persistence and runtime

- One `DatabasePort` unit of work owns the transaction boundary; repositories never
  commit. Multi-step workflows (complete + create successor) run in one
  transaction.
- Datetimes are naive UTC; due dates are plain `date`s. `today` comes from the
  clock port in the operator's zone, never inline `datetime.now()`.
- Schema evolution is additive and idempotent (`migrations.py`); no destructive
  migration exists.
- Runtime: `docker-compose.yml` — frontend (nginx, proxies `/api` to
  `backend:8000`), backend, Radicale, GreenMail. SQLite volume by default;
  `READY_ROOM_DATABASE_URL` selects the dialect, `READY_ROOM_TEST_DATABASE_URL`
  runs the suite against PostgreSQL.

## Gaps the expansion must fill

| Gap | Consequence today |
|---|---|
| No authentication — `single_user` adapter | Every request is one synthetic principal; there is no session, login, or revocation |
| No squadron/team/membership/duty-position model | Tasks are owner-scoped to that one principal; no shared accountability |
| No scope or ownership filtering beyond owner | Two real users cannot coexist safely |
| No audit/activity stream | Handoffs and privileged actions are not recorded |
| No Jev, no agent runtime | No conversational assistance, delegation, or approval gate |
| Notifications absent | No in-app signal for assignment, handoff, or approval |

These are tracked as issues #16–#104, gated by ADR-002…ADR-011.
