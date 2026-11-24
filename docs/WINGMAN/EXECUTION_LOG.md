# WINGMAN Execution Log

Append-only record of scheduled sessions. Newest entry last. Never rewrite an
entry; correct a later entry instead.

---

## Session 1 — 2026-11-24

**Selected ticket:** [#3](https://github.com/anotherhale/str-ready-room/issues/3) — ADR-001: decide deployment, classification, and data-handling constraints (P0-critical, architecture, est 20 min)

### Reorientation

- Local clone was a shallow checkout at `5fdae63`; `origin/main` had advanced to
  `1185ce9` (PR #1 spec merge, PR #103 WINGMAN docs merge). Reconciled before
  branching: ADR work branched from `5fdae63` (confirmed ancestor of `main`, so
  PR #105 merges cleanly), state work branched from current `origin/main`.
- Open issues: 102. Open PRs at start: 0 (PR #103 was merged). Issue #1 closed.
- Verified the WINGMAN instructions' "Issue #100 / ADR-1" pointer against the
  actual backlog: **#100 is a frontend Notes/references view ticket**, not an
  ADR. The ADR set is #3–#13, and ADR-001 is **#3**. Treated #3 as the initial
  ticket and recorded the correction here rather than inventing a decision.

### Baseline before editing

```text
backend:  .venv/bin/python -m pytest -q   -> 206 passed, 1 warning (exit 0)
          .venv/bin/ruff check app tests  -> All checks passed! (exit 0)
frontend: npm run test:run                -> 10 files, 39 tests passed (exit 0)
          npm run typecheck               -> clean (exit 0)
          npm run build                   -> built (exit 0)
```

### Work accomplished

- Wrote `docs/adr/ADR-001-deployment-classification.md`:
  - Chosen first deployment target: self-hosted single host, controlled network.
    Local Docker Compose stays the demo/dev profile. Air-gapped is a design
    target. Cloud is not authorized.
  - Maximum classification: unclassified, synthetic non-sensitive data only, with
    four explicit conditions required to raise it.
  - Hosting/backup/retention/residency/secrets/transport constraints.
  - Binding constraints on ADR-002 (self-contained local auth, server-side
    revocable sessions, cookie flags, demo provider refused outside `demo`) and
    on the data model (no secrets in tables/audit, no sensitive audit payloads,
    classification is a deployment property).
  - Seven unresolved organizational questions with owners and impact.
- Wrote `docs/adr/README.md` as the ADR index for ADR-001…ADR-011 with the owning
  issue for each.

### Files changed

- `docs/adr/ADR-001-deployment-classification.md` (new)
- `docs/adr/README.md` (new)

### Validation after editing

Same commands, same results (documentation-only change):

```text
backend: 206 passed, 1 warning (exit 0); ruff All checks passed! (exit 0)
frontend: 10 files / 39 tests passed; typecheck clean; build succeeded
git diff --name-only vs main: docs/adr/ADR-001-deployment-classification.md, docs/adr/README.md
```

### Git

- Branch: `wingman/adr-001-deployment-classification`
- Commit: `5feed2c` — `docs(adr): add ADR-001 deployment, classification, and data-handling constraints`
- PR: [#105](https://github.com/anotherhale/str-ready-room/pull/105) (open, not merged)

### GitHub updates

- Issue #3: validation-evidence comment posted; labels changed `ready` → `verification`; left open pending merge.
- No dependency promoted to `ready`: `docs/WINGMAN/README.md` forbids it while a
  dependency issue is open, and #3 is still open. #4 stays `blocked` until #3
  closes.

### Dependency reconciliation

- #4 (ADR-002) — dependency #3 is *implemented and validated* but not *closed*, so
  the label stays `blocked` per the repository's own rule. Unblock action: merge
  PR #105, close #3, then relabel #4 `blocked` → `ready`.
- #9 (ADR-007) remains blocked on #8 (ADR-006), which is READY.
- Everything else is unchanged.

### Checkpoint

- `STATE.md`, `EXECUTION_LOG.md`, `DECISIONS.md`, `ARCHITECTURE_MAP.md`,
  `AGENT_REGISTRY.md`, `CHECKPOINT.json`, root `WINGMAN.md` written on branch
  `wingman/coordinator-state` and opened as a PR against `main`.

### Next

**#5 — ADR-003 (squadron bootstrap, invitation, membership lifecycle).**

---

## Session 2 — 2026-11-24

**Selected ticket:** [#3](https://github.com/anotherhale/str-ready-room/issues/3) —
close ADR-001 by answering its organizational questions (P0-critical,
architecture, est 15 min)

### Trigger

The product owner directed that all open ADR-001 questions be answered with
recommended defaults and the tickets updated. Scope was limited to recording those
decisions and reconciling the queue — no new architecture decisions were invented
beyond the seven questions already listed in the ADR.

### Work

- ADR-001: replaced "Unresolved questions requiring organizational input" with
  "Organizational questions and adopted defaults" — a default, the confirming
  official, and the consequence for each of Q1–Q7, plus an explicit
  "What these defaults do not authorize" section (no real data, no cloud, no
  default egress, no compliance claim).
- Consistency edits in the same ADR: §2 now blocks real data on "organizational
  confirmations" rather than "open questions"; §3's retention bullet and the
  Consequences risk paragraph now reflect the adopted retain-indefinitely default.
- `docs/adr/README.md`: ADR-001 status and a stale spec-branch pointer corrected.
- Ticket updates: resolution record on #3; constraint notes on #11 (ADR-009
  egress), #13 (ADR-011 retention), #104 (profile field boundary); #4 relabelled
  `blocked` → `ready`.
- Merged PR #105 (merge commit `90decc5`), which closed #3 by its `Closes #3`
  reference. Verified #3 `state=closed` afterwards.

### Validation

- Documentation-only change: `git diff --stat` limited to `docs/adr/` and
  `docs/WINGMAN/`.
- The backend and frontend suites were **not** re-run this session. The workspace
  was recreated from scratch mid-session (the original run directory was removed),
  so neither `backend/.venv` nor `frontend/node_modules` exists here. The green
  baseline from session 1 (206 backend tests, 39 frontend tests, ruff, typecheck,
  build) remains the evidence for the code, and no code file changed in this
  session or the last one.

### Git

- Branch `wingman/adr-001-deployment-classification` — commit `e125a71`, merged
  as `90decc5`.
- `origin/main` now at `90decc5`.

### Dependency reconciliation

- **#4 (ADR-002) unblocked** and promoted to READY position 1: #3 is closed and
  ADR-001 §4 supplies its constraints.
- **#11 and #13** gained recorded input constraints, so they need no further
  discovery before implementation.
- **#9 (ADR-007)** still blocked on #8.

### Next

**#4 — ADR-002 (authentication provider, session storage, cookie strategy).**

## 2026-11-24 — ADR-004 role and scoped-permission matrix (#6), session 3

### Ticket

#6, `architecture`, P0-critical, status `verification`, PR #108.

### Work

- `docs/adr/ADR-004-role-permission-matrix.md`: five roles, 54-permission
  catalog (20 existing + 34 new), full grant matrix with a scope ceiling per
  grant, ordered evaluation, denial codes, team-lead and duty-position bounds,
  approval-gated vs agent-delegable classification, and a mapping table from
  matrix row to owning issue.
- `AGENTS.md`: nine authorization invariants that survive implementation drift.
- `docs/adr/README.md`: ADR-004 index row flipped to Accepted.

### Validation

- Backend `pytest`: 206 passed, 1 warning. `ruff check app tests`: clean.
- Frontend `vitest run`: 10 files / 39 tests passed. `tsc --noEmit`: clean.
  `vite build`: succeeded (184.64 kB JS, 11.74 kB CSS).
- ADR self-consistency script: 54 catalog rows, 34 new, 54 matrix rows,
  identical sets, no malformed cells, no write permission for `read_only`, no
  `:manage` for `team_lead`, no escalation for `member`, no `demo:*` granted to
  any role.

### Git

- `2a75665` on `wingman/adr-004-role-permission-matrix`, cut from `main` after
  ADR-001 merged. PR #108: 3 files, +465/-1.

### Failures and recovery

- PR #107 was opened against the pre-merge ADR-001 branch. #105 merged
  mid-session, so #107 would have replayed ADR-001. The change was rebuilt on
  `main` and pushed to the same branch name; #107 closed automatically. No
  force-push, and nothing from #105 was altered.
- The run workspace was deleted by the harness mid-session, after the frontend
  checks and before the checkpoint. The ADR was recreated in a fresh clone and
  **every** check was re-run on the new base; the numbers above are from the
  re-run.

### Deviation from the previous plan

Session 2 recommended #4 (ADR-002). Session 3 took #6 instead because #6 was
already `in-progress` with work to land and it gates #18, #19, #35, and #37.
#4 remains READY at position 1.

### Dependency reconciliation

- Nothing unblocked yet: #18, #19 stay `blocked` until PR #108 merges.
- #9 stays `blocked` on #8.
- #4, #5, #7, #8, #10, #11, #12, #13, #14, #15 remain READY.

### Next

**#7 — ADR-005 (squadron data isolation, owner migration, schema evolution).**
#4 turned out to be claimed: a parallel session opened PR #109 for ADR-002 while
this one was running, so the recommendation moved to the next unclaimed
priority order. Alternatives: #8 (ADR-006), #14 (test harness).

## 2026-11-24 — ADR-002 authentication, session, and cookie strategy (#4), session 4

### Ticket

#4, `architecture`, P0-critical, status `in-progress`, PR #109.
Recovered as `BLOCKED` with a stale `ready` label even though #3 had closed, so
the first action was dependency reconciliation rather than implementation.

### Dependency reconciliation at start

- `origin/main` had advanced to `6b48e66`: PR #106 (coordinator state) **merged**,
  so checkpoint blocker **B-003 is resolved**.
- #3 closed by PR #105 (`90decc5`); ADR-001 is on `main`. The dependency was
  therefore satisfied on evidence. #4 moved `BLOCKED` -> `IN PROGRESS` and
  `ready` -> `in-progress`; the body's status row was corrected.
- #5 (ADR-003) closed while this session ran; #6 (ADR-004) sits in `verification`
  with PR #108. Both were left untouched.

### Work

- `docs/adr/ADR-002-authentication-session.md`: local credentials plus
  server-side sessions as the first mechanism, OIDC as a documented extension
  seam; stdlib `scrypt` credential hashing with a self-describing hash string;
  256-bit opaque session tokens with only the SHA-256 persisted; `sessions`
  table through the persistence port; 30-minute idle and 12-hour absolute
  expiry; rotation on login, privilege change, and password change; nine
  enumerated revocation triggers with membership-active coupling; cookie
  attributes including the `__Host-` prefix when secure; a required custom
  header plus `Origin` check for CSRF; and a three-point fail-closed guard that
  makes `SingleUserAuthProvider` unselectable outside `demo`/`test`.
- `docs/adr/README.md`: ADR-002 index row flipped to Accepted.
- Five open questions (A1-A5) recorded with defaults so they do not block the
  Phase 1 tickets.

### Validation

- Backend `pytest`: **206 passed, 1 warning** (68.08s) — run in this session in a
  freshly created `.venv` (`uv venv --python 3.12`).
- Backend `ruff check app tests`: **All checks passed!**
- `git status --porcelain`: only `docs/adr/README.md` (modified) and
  `docs/adr/ADR-002-authentication-session.md` (added). `git diff --stat`:
  1 file, +1/-1.
- Frontend not run: no frontend file or dependency changed, and `node_modules`
  is absent in this workspace. No frontend claim is made.

### Git

- Branch `wingman/adr-002-authentication-session` cut from `90decc5`, commit
  `4a6a599`, pushed. PR #109: 2 files, +384/-1.
- This state entry lands on `wingman/state-session-3` (PR #110), which session 3
  opened for the same artifact, rather than opening a competing state PR.

### Failures and recovery

- None blocking. The workspace was a shallow graft at `1185ce9`, one commit
  behind `main`; `git fetch --unshallow` was needed before branch reconciliation
  could be reasoned about.

### Dependency reconciliation at end

- #24 (P1-09), #25 (P1-10), #26 (P1-11), #27 (P1-12), #30 (P1-15) each had `#4`
  satisfied in their dependency lists. None were relabelled, because each still
  carries unmet dependencies (#21, #19, #104) that this session did not touch.
  Promoting them would have been a false unblock.
- #9 (ADR-007) stays blocked on #8. #16-#104 stay blocked on their own chains.

### Next

**#7 — ADR-005 (squadron data isolation, owner migration, schema evolution).**
It is the highest-priority READY ADR, P0-critical, and gates #20-#22 and #32.
ADR-002 §3 (session table) and §8 (membership coupling) give it inputs it would
otherwise have had to decide. Alternatives: #8 (ADR-006), #14 (test harness).

---

## Session 5 — 2026-11-24

**Selected ticket:** [#7](https://github.com/anotherhale/str-ready-room/issues/7) — ADR-005: squadron data isolation, owner migration, schema evolution (P0-critical, architecture, est 20 min)

### Reorientation

- Local clone at `main` = `6b48e66` (grafted shallow checkout); no working-tree
  changes. No `wingman/*` ADR branches existed locally at start; PRs #108
  (ADR-004), #109 (ADR-002), #110 (state) were open on the remote.
- Read `STATE.md`, `CHECKPOINT.json`, `AGENTS.md`, `WINGMAN.md`, ADR-001/002/004,
  `REQUIREMENTS_TRACEABILITY.md`, and the permission matrix before selecting.
- Confirmed #7 was still `ready`/`open` and that no branch or PR had claimed it.
- Confirmed the instruction's "ADR-1 / Issue #100" pointer remains stale (as
  recorded in C-001): ADR-005 is #7, and #3 (ADR-001) is merged.

### Survey of the persistence layer (inputs to the decision)

Six tables, all owner-scoped: `tasks`, `recurrence_rules`, `operator_settings`
(`owner_id` is the PK), `categories`, `calendar_events`, `email_sources`. Every
repository method takes `owner_id: str` explicitly, and
`AuthorizationPolicyService` allows a write only when `owner_id == principal.id`.
Schema evolution is `create_all` plus `run_additive_migrations`, a fixed
add-only `ALTER TABLE` tuple with no record of what ran (`AI-DECISIONS` D-009).

### Baseline before editing

```text
backend: uv venv --python 3.12 (fresh) ; uv pip install -e ".[dev]"
         .venv/bin/python -m pytest -q  -> 206 passed, 0 failed (24.1s)
         .venv/bin/ruff check app tests -> All checks passed!
frontend: not run — no frontend file changed, node_modules absent in this workspace
```

### Work accomplished

- Wrote `docs/adr/ADR-005-data-isolation-migration.md` (accepted). It decides:
  - `squadron_id` on every squadron-scoped table with `owner_id` retained;
    every owner-leading index becomes tenant-leading.
  - Three enforcement layers: ADR-004 authorization, a `ScopeCriteria` built in
    exactly one place from the resolved principal, tenant-leading DB indexes.
    Cross-squadron reads return `404`; in-squadron scope denials return `403`.
  - A versioned, forward-only, idempotent migration runner recorded in
    `schema_migrations`, replacing the fixed add-only tuple; Alembic deferred
    with the reasoning recorded.
  - Expand → backfill → startup guard (fails closed on a null tenant key) →
    `NOT NULL` contract in a later release.
  - An explicit per-table backfill mapping, deterministic `uuid5` bootstrap
    squadron and personal-workspace ids, `scope='personal'` for every existing
    row (today's exact visibility), one `member` membership per distinct owner
    and one configurable `squadron_admin`. Nothing is widened.
  - Demo compatibility (one artifact set, seed writes the new columns, reset
    preserves squadron/membership rows, volume wipe last resort) and an operator
    recovery procedure.
  - A 14-path isolation test matrix covering aggregates, calendar cache, mailbox
    provenance, turnover packages, and Jev context assembly.
- Marked ADR-005 Accepted in `docs/adr/README.md`.
- Recorded the durable persistence invariants in `AGENTS.md` (tenant boundary in
  queries, cross-squadron `404`, versioned runner, expand/backfill/guard/contract).

### Files changed

- `docs/adr/ADR-005-data-isolation-migration.md` (new)
- `docs/adr/README.md` (+1/−1)
- `AGENTS.md` (+13/−1)

### Validation after editing

```text
.venv/bin/python -m pytest -q  -> 206 passed, 0 failed (identical to baseline)
.venv/bin/ruff check app tests -> All checks passed!
git diff --stat                -> 2 files changed, 14 insertions(+), 2 deletions(-)
                                  plus the new ADR (untracked before commit)
```

Documentation-only change: no application code, configuration, default,
dependency, or test was modified.

### Git and GitHub

- Branch `wingman/adr-005-data-isolation-migration`, commit `61c6621`.
- PR [#111](https://github.com/anotherhale/str-ready-room/pull/111) opened against
  `main`; issue #7 labelled `in-progress` and commented with the decision summary
  and validation evidence. #7 closes on merge.

### Dependency reconciliation

- **Unblocked:** #20 (`P1-05` models + migration), #21 (`P1-06` repositories +
  `DatabasePort`), #32 (`P1-17` backfill) — the tenant key, criteria shape,
  migration mechanism, and backfill mapping are all decided.
- **New follow-ups recorded rather than absorbed:** the `NOT NULL` contract step
  (ADR-005 I1), and the versioned SQL fixtures `#20` must add under
  `backend/tests/fixtures/schema/`.
- **R-ARCH-05** in the traceability matrix moved MISSING → PARTIAL with ADR-005
  as the evidence.

### Queue state

- READY: #8 (ADR-006), #14 (test harness), #5 (ADR-003), #15 (CI), #10, #11, #12,
  #13. #7 has left the queue.
- Next recommended: **#8 — ADR-006**; alternative **#14** if #8 is claimed.
- Environment note: `gh` CLI is not installed here; GitHub operations used the
  REST API via `curl`/`urllib` with `GITHUB_TOKEN`.

### Coordinator state

`STATE.md`, `DECISIONS.md`, `CHECKPOINT.json`, `REQUIREMENTS_TRACEABILITY.md`, and
this log updated on the state branch (PR #110), so the ADR branch stays a
documentation-only change.

### Post-run reconciliation (same session)

`main` advanced to `4b72868` while the session ran (PRs #108, #109, #110 merged),
which made PR #111 conflict on `docs/adr/README.md`. Resolved by merging `main`
into the ADR branch and keeping both accepted rows (ADR-004 and ADR-005); pushed
as `28155f2`. Re-ran the backend suite at the merged head: 206 tests, exit 0, ruff clean.

PR #110 was already merged, so the session-5 state commit was re-applied on top of
merged `main` and opened as PR #112 (`wingman/state-session-5`).

The workspace directory was deleted mid-session by the runtime. Recovery: re-clone
from origin, `cherry-pick 65187ce` (the state commit already pushed), redo the
merge in the ADR branch, and re-run validation. Nothing was lost.

### Merge of PR #111

The owner merged PR #111 at 18:09Z; `main` is now `dc98f8d` and issue #7 closed
automatically. `ready`/`in-progress` labels removed. ADR-005 is Accepted in the
repository, so the tenant key and scoping contract are now binding rather than
proposed. Next READY ticket: #8 (ADR-006 squadron and membership model).

## Session 6 — 2026-11-24

**Ticket:** #8 `P0-06` — ADR-006: task scope, sharing, and accountable-ownership
semantics (P0-critical, architecture, 20 min).

### Reorientation correction

The checkpoint this session inherited (`session 4`, `main_sha 6b48e66`) was two
merges stale. `origin/main` was at `dc98f8d` (PR #111) and **ADR-005 was already
written and merged** (PR #111, issue #7) — the recommended "next ticket" in
`CHECKPOINT.json` was done. An ADR-005 draft produced before that discovery was
discarded uncommitted rather than opened as a duplicate.

Lesson applied: verify `git fetch` + `git ls-remote` before trusting a checkpoint
recommendation. The READY queue in this file is recomputed from live issue state,
not from the previous checkpoint.

### Work

- `docs/adr/ADR-006-task-scope-sharing.md` — new, 351 lines. Four scopes on a
  strict ladder with `personal` as the only default; exactly one accountable
  owner and at most one typed assignee; collaborators and watchers; user-only,
  additive, non-transitive, soft-revoked shares; a single visibility predicate;
  a per-scope permission matrix mapped onto ADR-004 permissions and denial codes;
  occurrence snapshotting for ADR-007.
- `docs/adr/README.md` — ADR-006 row: Pending -> Accepted.
- `AGENTS.md` — five durable task-scope invariants added to the Domain section.

### Validation

- Backend `pytest`: **206 passed, 1 warning in 23.93s** (unchanged from baseline).
- Backend `ruff check app tests`: **All checks passed!**
- Frontend not run: `node_modules` absent in this workspace and no frontend file
  changed. No frontend claim is made.

### Git

- Branch `wingman/adr-006-task-scope-sharing` from `dc98f8d`, one commit,
  pushed. PR **#114**.

### Failure and recovery

- The run workspace directory was **deleted mid-session**, losing the working
  tree. The same repository contents were found relocated under a new run
  directory with the changes intact; work resumed there without re-cloning.
  (Second occurrence of this failure mode — recorded in `CHECKPOINT.json`.)

### Dependency reconciliation

- #9 (ADR-007) stays `blocked` on #8 until PR #114 merges; its dependency is
  satisfied by decision but not by merge, so no relabel.
- #35-#39 gain a fixed implementation contract but stay gated on the Phase-1
  chain (#16-#21), so no relabel.
- #4, #6, #7 are merged; their issues are ready to close on verification.

### Next

**#14 — multi-principal test harness** (P0-critical). Alternatives: #5 (ADR-003),
#15 (CI). Do not start #9 before #8 closes.

---

## Session 6 (continued) — post-merge reconciliation, 2026-11-24T18:19Z-18:32Z

### What changed since the checkpoint above

PR **#114 merged** into `main` as **`3d6efd6`** at 18:19:20Z, and **#8 was
closed** and relabelled `verification`. The checkpoint written minutes earlier
said `in-review`, so it was corrected in the same PR (#116) rather than left
stale for the next run to trust.

### Concurrent-session collision (new failure mode, B-006)

A second WINGMAN session was working in the same workspace and selected the same
ticket. It committed the working tree (which contained this session's ADR-006
draft), pushed `wingman/adr-006-task-scope-sharing`, opened PR #114, wrote the
issue comment, and produced the session-6 state branch — all while this session
was still writing. Nothing was lost: the committed ADR is the same 351-line file
this session authored, and both sessions independently measured 206 passed /
ruff clean.

What did go wrong is drift: the PR #114 body described a section layout that the
committed file does not have (it cited "§5/§6", invariants `I1`-`I9`, and
soft-revoked shares; the file actually has `§1`-`§10`, seven invariants in `§2`,
one `task_shares` table with `read`/`write`, and open questions `T1`-`T5`). The
description was rewritten against the file, with a note that it had been
corrected.

**Mitigation for future runs:** before writing to a ticket, check whether a
sibling branch or PR for that ticket already exists. If it does, verify and
correct it instead of re-implementing.

### Also lost and recovered

The run directory was deleted a second time mid-session, taking this session's
uncommitted `STATE.md` edit with it. The repository was re-cloned into a fresh
directory and the state edits were re-applied there. The failure mode is now
recorded twice; work in progress must be committed early rather than batched at
the end of the run.

### Dependency reconciliation

- **#9 (ADR-007) promoted `blocked` -> `ready`.** Its only dependency, #8, is
  merged. Nothing else in the queue moved.
- #35-#39 still gated on the Phase-1 domain/persistence chain (#16-#21), not on
  ADR-006.
- No new blockers discovered beyond B-006.

### Next

**#9 — ADR-007** (P1-high, 20 min): the last unmerged ADR that gates a whole
implementation lane. Alternatives: #14 (P0-critical test harness), #15 (CI).

## Session 7 — 2026-11-24

**Selected ticket:** #14 / P0-12 — multi-principal test harness and
configurable test auth provider (P0-critical, ~25 min, no open dependencies).

**Starting state:** `main` @ `4e0abbd` (PR #116 merged); clean tree; #14 carried
`ready, in-progress`; the only other READY tickets were ADRs #5, #9–#13 and #15.

**Actions**

1. Read the P0-12 ticket, `STATE.md`, and decisions C-001–C-006; inspected
   `composition.py`, `api/dependencies/__init__.py`, `error_handlers.py`,
   `tests/conftest.py`, `tests/doubles.py`.
2. The run workspace directory was deleted mid-session and the validated,
   uncommitted implementation was lost with it. Re-implemented from scratch in
   the relocated workspace, then committed and pushed **before** writing docs.
3. Implemented the harness: `MembershipState` / `TestMember` / `TestAuthProvider`
   in `tests/doubles.py`; `squadron_roster`, `test_auth_provider`,
   `test_container` fixtures; `AuthenticationError` (`unauthenticated`) in the
   domain with a 401 mapping in `api/error_handlers.py`.
4. Wrote nine tests covering roster shape, two principals in one test,
   per-request selection, refusal of unselected and suspended identities, the
   401-vs-403 split, read-only denial, and ownership-isolated task lists.
5. Recorded DECISIONS C-007 (do not pre-authorize the ADR-004 matrix).

**Validation**

| Command | Result |
|---|---|
| `python -m pytest -q` | 215 passed, 0 failed, 0 errors (206 baseline + 9 new) |
| `ruff check app tests` | All checks passed |
| `mypy app` | Success: no issues found in 84 source files |

**Git:** branch `wingman/p0-12-multi-principal-test-harness`, commit `e42f06a`,
PR [#117](https://github.com/anotherhale/str-ready-room/pull/117) open against
`main`. Not merged — WINGMAN does not self-merge.

**GitHub:** #14 commented with implementation and validation evidence;
`ready` removed, `in-progress` retained; ticket closes on merge.

**Dependency reconciliation**

- #34 (two-user isolation tests) now has a concrete prerequisite artifact; it
  becomes READY when PR #117 merges (fixtures must exist on `main`).
- #16 remains blocked on #5 only (#7 merged) — so #5 is now the highest-value
  READY ticket.
- No ticket was closed to unblock anything.

**Failures:** one test failed on first run —
`test_two_principals_get_isolated_task_lists` used `viper` (`member`), who holds
no `tasks:read` grant under C-007. Fixed by asserting the empty list with
`iceman` (`read_only`, which does hold `tasks:read`), so the assertion proves
ownership filtering rather than a permission denial.

---

## Session 8 — 2026-11-24T18:40Z–19:20Z

**Ticket:** #9 — ADR-007: shared recurrence, duty-position routing, occurrence
exceptions (P1-high, architecture, 20 min). **Status:** implemented, in review.

### Context recovered

- Run workspace `.../automation-runs/ad8dcd7c-.../str-ready-room` **was deleted**
  mid-session (third occurrence of this failure). Work moved to a clone at
  `~/wingman/adr-007` (branch `main` = `4e0abbd`, merge of #116).
- The clone's `origin` pointed at the deleted path, so `git push origin`
  reported success against a dead remote; the branch was pushed to an explicit
  GitHub remote instead and verified with `git ls-remote`.
- Sibling sessions were live: PR **#117** (#14 multi-principal test harness) and
  PR **#118** (coordinator state, session 7). #14 was **not** touched.
- The inherited tracker named #14 as the session ticket; #14 was already owned by
  the sibling (#117), so it was abandoned rather than duplicated (B-006).

### Work

`docs/adr/ADR-007-shared-recurrence.md` — 12 sections, consequences, 6 rejected
alternatives, 6 open questions with defaults. Core decisions:

- Chain of `Task` rows kept; **no** `TaskOccurrence` table.
- Rule becomes a versioned series definition (scope, duty position, default
  assignee/collaborators, start date, timezone + due time, pause/resume,
  revision, escalation extension point).
- Occurrences snapshot schedule and assignment; revisions and exceptions are
  append-only tables keyed by `(series_id, occurrence_number, kind)`.
- "This occurrence" vs "this and future": two endpoints, two permissions
  (`recurrence:override` / `recurrence:write`); `scope=past|all` → 422.
- Duty-position holder change routes open + future occurrences; closed rows,
  owner, and assignee history untouched; vacancy falls back to the owner.
- `TaskStatus.CANCELLED` is closed but never counted as completion.
- Due time as `due_at_utc` (naive UTC) computed in the series' stored zone.

Also: ADR README row → Accepted; five durable invariants added to `AGENTS.md`.

### Validation

| Command | Result |
|---|---|
| `backend/.venv/bin/python -m pytest` | 206 passed, 1 warning (17.85s) — identical to baseline |
| `backend/.venv/bin/ruff check app tests` | All checks passed |
| `git diff --stat` | docs only |

Frontend not run: no frontend file changed.

### Git

- Work branch `wingman/p0-07-adr-007-shared-recurrence`, commit `e5ff56f`
  (+ a follow-up correcting the escalation ticket reference).
- PR **#119** → `main`, open, not merged.

### Dependency reconciliation

- **#9 → in review** (PR #119).
- **#51 (P3-01) promoted blocked → READY**: its only dependency was #9, and
  ADR-007 now specifies every field it must add.
- #52/#53/#54 become dependency-satisfied once #51 lands; #55–#62 follow.
- No new blockers. B-006 (concurrent sessions) re-confirmed with a new
  mitigation: verify the push remote.

### Next

**#51 — P3-01** (P1-high, 25 min). Alternatives: #15 (CI), #5 (ADR-003).

## Merge reconciliation — 2026-11-24

All four open PRs were merged at the coordinator's request, in dependency order:

| Order | PR | Content | Merge commit |
|---|---|---|---|
| 1 | #117 | P0-12 multi-principal test harness (issue #14) | `937a899` |
| 2 | #118 | Coordinator state, session 7 | `7a033d0` |
| 3 | #119 | ADR-007 (issue #9) | `4c413a8` |
| 4 | #120 | Coordinator state, session 8 (this PR) | rebased onto `4c413a8` |

PR #120 was rebased rather than force-merged: its conflicts with #118 were in
`STATE.md`, `EXECUTION_LOG.md` and `CHECKPOINT.json`. Resolution was additive —
the session-7 log entry and notes above are kept intact, and stale "in review"
claims written before #117/#119 merged are corrected in the live state files.

## Session 16 — 2026-11-24T22:33Z (run `20261124T2235Z-30d0`)

**Ticket:** #12 / ADR-010 (P1, architecture, READY, XS-S) — claimed at epoch 1 via
`coordination.py claim` before any writing.

**Branch:** `wingman/issue-12/adr-010-workflow-persistence` from `main` @ `a99f2dc`.

**Actions**

1. Recovered state from `main`, `STATE.md`, `CHECKPOINT.json` (stale at session 8)
   and live GitHub; confirmed no claim existed for #12 and no sibling branch/PR.
2. Wrote `docs/adr/ADR-010-workflow-persistence.md`: run record shape, the fixed
   seven-type catalog, the six-state machine with a legal-transition table, durable
   digest-bound approvals, two-level idempotency by plain unique constraints,
   bounded retries (3 attempts/step, 5 s/30 s, 20 steps, 15 min, 1 recovery),
   cooperative cancellation, heartbeat recovery, payload minimization, portable
   `active_key` concurrency, and the `P5-10` API surface.
3. Flipped the ADR-010 row in `docs/adr/README.md` to Accepted and added a
   "Workflow runs (ADR-010)" durable-invariant section to `AGENTS.md`.
4. **Found `main` red.** `a99f2dc` added abstract `MailboxProvider.purge()` but not
   the implementation in `tests/doubles.py::InMemoryMailboxProvider`, so 11
   integration tests errored at setup. Filed #146 and fixed it under that ticket in
   the same branch, with three new unit tests.

**Commits**

| SHA | Message |
|---|---|
| `b01db47` | docs(adr): ADR-010 workflow persistence, retries, cancellation, idempotency (#12) |
| `8f20394` | test(double): implement MailboxProvider.purge in the in-memory mailbox (#146) |

**Validation**

- `cd backend && python -m pytest` → **223 passed**, 1 warning, 14.98 s
  (baseline before the #146 fix: 11 setup errors)
- `cd backend && ruff check app tests` → **All checks passed!**
- Frontend not run: no frontend file changed.

**GitHub**

- PR **#147** opened (base `main`), not merged.
- #12 and #146 each received a progress comment with evidence.

**Dependency reconciliation**

- `P5-03` (run domain) and `P5-10` (run service/API) become READY once #147 merges;
  until then they are decision-satisfied but unmerged.
- #146 is a new XS ticket discovered this run; it blocked every integration test,
  so it took priority over any further product work in the remaining window.
- No new blockers. B-007 (workspace deletion) did not recur; commits were pushed
  immediately after each validated slice.

**Next**

#13 (ADR-011) is the only unclaimed architecture decision left in the ADR lane;
#5/#10/#11 remain in review. Product-lane recommendation is unchanged (#51, after
#147 lands, since #51 is already claimed/being worked in the recurrence lane).
