# WINGMAN State

Live coordinator state. GitHub Issues remain authoritative for ticket status; this
file records what the last session actually verified and what the next session
should do. Update it at the end of every run.

**Last updated:** 2026-11-24 (session 13 — ADR-008 agent runtime contract, PR #136)

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

## Session 13 snapshot (2026-11-24)

- **ADR-008 accepted** in PR #136: agent identity, delegation, and approval
  binding. Docs only — no code, schema, or migration.
- Phase 5 is now contractually unblocked: `P5-01`..`P5-04` and `P5-08` have fixed
  records, a fixed check order, a fixed hash, and fixed denial codes.
- **The backend integration suite is red on `main`** (13 failed, 22 errors) for a
  reason unrelated to that PR: `tests/doubles.py::InMemoryMailboxProvider` is
  missing `purge()`, added to the `MailboxProvider` ABC in a99f2dc. Tracked as
  **#137** (XS, ready) and recommended as the next ticket, because it restores the
  only integration regression signal.

## Multi-session coordination (upgrade in progress)

Run identity, exclusive ticket claims, and run discovery now live in the GitHub
repository itself. No workspace file is authoritative for run ownership.

```bash
PYTHONPATH=scripts python3 -m wingman.coordination status
```

| Artifact | Purpose |
|---|---|
| `refs/wingman/claims/issue-<N>` | exclusive lease on a ticket (atomic create = lock) |
| `refs/wingman/runs/<RUN_ID>` | one registry entry per run, written only by its owner |
| `docs/WINGMAN/runs/<RUN_ID>.{json,md}` | one run's own record (no shared mutable file) |
| `docs/WINGMAN/RUNS.md` | generated snapshot of the registry — never hand-edited |
| `docs/WINGMAN/CONCURRENCY.md` | audit, authority decision, incidents, residual risks |

A ticket with a live claim — or an expired claim awaiting recovery — is **not**
available. Expired claims require inspection (branch, commits, PR) before takeover.

Upgrade backlog: #121 (tracking), #122 (implemented, PR #129) -> #124 (handshake) ->
#125 (worktrees) -> #126 (run-scoped state) -> #127 (validation suite) -> #128
(scheduler). **Rollout stays at Phase A (one implementation session) until #127
passes.**

## Current product status

READY ROOM is a working single-user operational-awareness demo: shared tasks with
derived urgency, recurrence as a chain of task rows, a briefing, calendar and
mailbox integrations, and demo seed/reset. It is verified green and
containerized. It has **no authentication**, **no squadron/membership model**, and
**no AI assistant**; those are the expansion.

| Area | State | Evidence |
|---|---|---|
| Backend (FastAPI, DDD + hexagonal) | Working | 215 tests pass, ruff clean |
| Frontend (React/TS SPA) | Working | 39 tests pass, typecheck clean, build succeeds |
| Deployment | Single-host Docker Compose, SQLite volume, Radicale + GreenMail | `docker-compose.yml` |
| Identity | `single_user` demo adapter only — no login, no session; a **test-only** multi-principal provider is on `main` (P0-12, PR #117 merged) | `backend/app/adapters/identity/`, `backend/tests/doubles.py` |
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
- **ADR-007 accepted and merged** (PR #119 -> `4c413a8`, issue #9 closed).
  The chain of `Task` rows is kept — **no** `TaskOccurrence` table. The rule
  becomes a versioned series definition (`scope`, `responsible_duty_position_id`,
  `default_assignee`, `default_collaborator_ids`, `start_date`, `timezone` +
  `due_time_local`, `paused_at`, `revision`). Occurrences **snapshot** their
  schedule and assignment; `recurrence_rule_revisions` and
  `recurrence_exceptions` are append-only. "This occurrence" and "this and
  future" are two endpoints with different permissions (`recurrence:override` vs
  `recurrence:write`) and there is no edit-the-past. A duty-position holder
  change routes open and future occurrences forward and never rewrites closed
  rows or the owner. `cancelled` is closed but never counted as completion.
  See `docs/adr/ADR-007-shared-recurrence.md`.
- Those defaults are **project decisions, not accreditation**. The named official
  must still confirm each one before real data is stored, and none of them
  authorizes cloud hosting, default egress, or any compliance claim.

## Blockers

| Blocker | Effect | Owner |
|---|---|---|
| Formal confirmation of the Q1–Q7 defaults (product owner accepted defaults 2026-11-24; official sign-off outstanding, tracked in [#113](https://github.com/anotherhale/str-ready-room/issues/113)) | Real operational/personnel data cannot be stored until confirmed. Does **not** block the unclassified synthetic build or the remaining ADRs. | Authorizing Official, Security Officer, Privacy/HR, Records Manager, Operations |

Nothing currently blocks the remaining READY ADRs.

**In review:** nothing. #14 (P0-12, PR #117), ADR-007 (#9, PR #119), and the
session-7 state PR #118 are all merged to `main`.

## READY queue (dependency-satisfied, no open dependency issues)

Ordered by the selection hierarchy: critical architecture decisions first, then
security/authorization foundations, then prerequisites that unblock the most
downstream work.

| Order | Issue | Title | Priority | Est |
|---|---|---|---|---|
| 1 | [#51](https://github.com/anotherhale/str-ready-room/issues/51) | P3-01: extend `RecurrenceRule` with scope, duty position, default assignment, due time, pause/resume | P1-high | 25 min |
| 2 | [#15](https://github.com/anotherhale/str-ready-room/issues/15) | CI workflow running backend and frontend verification | P1-high | 20 min |
| 3 | [#5](https://github.com/anotherhale/str-ready-room/issues/5) | ADR-003: squadron bootstrap, invitation, membership lifecycle | P1-high | 15 min |
| 4 | [#10](https://github.com/anotherhale/str-ready-room/issues/10) | ADR-008: agent identity, delegation, approval binding | P1-high | 20 min |
| 5 | [#11](https://github.com/anotherhale/str-ready-room/issues/11) | ADR-009: Jev provider, context assembly, failure strategy | P1-high | 20 min |
| 6 | [#12](https://github.com/anotherhale/str-ready-room/issues/12) | ADR-010: workflow persistence, retries, cancellation, idempotency | P1-high | 20 min |
| 7 | [#13](https://github.com/anotherhale/str-ready-room/issues/13) | ADR-011: notification channels/preferences and audit retention | P2-normal | 20 min |

#9 (ADR-007) and #14 (multi-principal test harness) left this queue: both are
merged (PR #119 and PR #117). #52/#53/#54 are dependency-satisfied by ADR-007
but remain blocked on #51, so they are not queued yet.

## Blocked queue

| Issue | Blocked on |
|---|---|
| #16 (squadron aggregate) | #5 (ADR-003) — #7 already merged |
| #52–#54 (P3-02..P3-04) | #51 (P3-01) |
| #34 (two-user isolation tests) | #27, #28, #29, #32 (the P0-12 harness from #117 is merged) |
| #18–#21, #32, #35–#41, #46, #49 (squadron foundation chain) | #16, and their ADRs |
| #50, #71, #86, #90, #94, #97, #98, #101 (frontend/docs) | Their backend and ADR dependencies |

## Next recommended ticket

**#51 — P3-01: extend `RecurrenceRule`** (P1-high, 25 min). Rationale: ADR-007
fixed every field and invariant it needs, so it is the highest-value
dependency-satisfied ticket and it unblocks #52, #53, #54 and the whole
persistence/API lane (#55–#62).

Alternatives if #51 is claimed: **#15 — CI workflow** (nothing depends on it, but
it makes every later validation trustworthy), then **#5 — ADR-003**.

## Session 7 notes (operational)

- The run workspace directory was deleted mid-session (third occurrence). Work
  that had been validated but not committed was lost with it and was
  re-implemented from scratch in the relocated workspace. Lesson applied:
  commit and push as soon as a slice validates, before writing documentation.
- Only today's live demo grants are mapped in the test harness (`squadron_admin`
  → `operator`, `read_only` → `viewer`). `member` and `team_lead` deliberately
  hold no permission until ADR-004's matrix is implemented (DECISIONS C-007), so
  no test can pass against grants the role will never have.

## Session 8 notes (operational)

- The run workspace `.../automation-runs/ad8dcd7c-.../str-ready-room` was deleted
  mid-session again (third occurrence). Work continued in a clone at
  `~/wingman/adr-007`; its `origin` pointed at the deleted path, so a push to
  `origin` silently succeeded against a dead remote. **Push to the GitHub remote
  explicitly and verify with `git ls-remote`.**
- Two sibling sessions were live (`#117`, `#118`). Check for a sibling branch/PR
  for the selected ticket before writing (B-006).

## Session 9 notes (operational)

- Ran while sessions 7 and 8 were live (#9 / PR #119, #14 / PR #117, state PRs
  #118/#120): excluded both tickets and selected coordination work instead. All four
  merged during this run, so the exclusion set was recomputed at handoff from live
  issue state rather than from the inherited checkpoint.
- Claimed #122 through the new ref-CAS primitive **before** writing code, and verified
  the live race on github.com (owner `201`, second run `422`).
- `STATE.md` / `CHECKPOINT.json` / `EXECUTION_LOG.md` were deliberately not touched
  while #118/#120 were open; this run's state lives in `docs/WINGMAN/runs/20261124T1851Z-5efb.json`
  and `refs/wingman/runs/20261124T1851Z-5efb`.
- **B-008:** a sibling session checked `main` out in this shared working directory
  mid-run, so one commit landed on `main` and was pushed. It was reverted on `main`
  (`b774e22`, no force-push) and re-applied on the ticket branch for review. Durable
  fix: worktree isolation (#125).
- **Next recommended ticket: #124** (mandatory handshake + skill), then #125, then
  #127. Product-lane next recommendation is unchanged from session 8 (#51).
