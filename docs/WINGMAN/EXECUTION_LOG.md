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
