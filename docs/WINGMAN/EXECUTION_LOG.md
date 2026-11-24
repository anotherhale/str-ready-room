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
