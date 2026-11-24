# WINGMAN — coordinator entry point

WINGMAN is the autonomous engineering coordinator for READY ROOM. It executes
GitHub issues, one primary ticket per scheduled session, and checkpoints state so
a fresh session can resume without chat history.

Start here, then read in this order:

1. [`docs/WINGMAN/STATE.md`](docs/WINGMAN/STATE.md) — current status, blockers, READY queue.
2. [`docs/WINGMAN/CHECKPOINT.json`](docs/WINGMAN/CHECKPOINT.json) — machine-readable state.
3. [`docs/WINGMAN/README.md`](docs/WINGMAN/README.md) — selection and execution protocol.
4. [`docs/WINGMAN/EXECUTION_LOG.md`](docs/WINGMAN/EXECUTION_LOG.md) — append-only session history.
5. [`docs/WINGMAN/DECISIONS.md`](docs/WINGMAN/DECISIONS.md) — coordination decisions and ADR index.
6. [`docs/WINGMAN/ARCHITECTURE_MAP.md`](docs/WINGMAN/ARCHITECTURE_MAP.md) — architecture as implemented.
7. [`docs/WINGMAN/AGENT_REGISTRY.md`](docs/WINGMAN/AGENT_REGISTRY.md) — delegable roles.

**GitHub Issues are the authoritative work queue.** These documents describe how
work is selected and what has been verified; they never override an open issue,
a failing test, or a merged pull request.

Durable repository invariants live in [`AGENTS.md`](AGENTS.md). Product
requirements live in
[`docs/SQUADRON_PLATFORM_EXPANSION.md`](docs/SQUADRON_PLATFORM_EXPANSION.md).
Architecture decisions live in [`docs/adr/`](docs/adr/).

## Mandatory startup handshake (not optional)

Every run, including a resumed or single-ticket run, executes this before touching
a ticket. The enforced entry point is `scripts/wingman/preflight.py`; it refuses to
return a plan when a step fails, and a run that has no verified claim must not
implement.

```bash
RUN_ID="$(date -u +%Y%m%dT%H%MZ)-$(openssl rand -hex 2)"
git worktree add -b "wingman/issue-<T>/run-$RUN_ID" /tmp/wm/issue-<T> origin/main
PYTHONPATH=scripts python3 -m wingman.preflight \
  --run-id "$RUN_ID" --session <N> \
  --branch "wingman/issue-<T>/run-$RUN_ID" --worktree "/tmp/wm/issue-<T>"
```

| # | Step | Fails closed when |
|---|---|---|
| 1 | register the run | the registry ref cannot be created |
| 2 | discover active runs | the registry is unreadable |
| 3 | reconcile registry vs GitHub (claims, branches, PRs) | a claim cannot be inspected |
| 4 | build the exclusion set | a ticket's state is unknown |
| 5 | select the highest-value eligible ticket | nothing is eligible |
| 6 | claim atomically, then read back and verify ownership | the claim was refused, unverified, or lost |
| 7 | verify the isolated worktree (own branch, not the primary checkout) | the workspace is shared or on the wrong branch |
| 8 | mark EXECUTING and start work | the heartbeat cannot be written |

Rules that follow from the handshake:

- **Claim before coding.** A ticket held by another run — or by an expired claim
  awaiting recovery — is not available. Recovery requires inspecting the branch,
  commits, and PR first; a claim never lapses silently into "free".
- **Isolate before modifying.** One worktree per run, on the run's own branch. Never
  switch `HEAD`, reset, clean, or commit in another run's workspace; that is how
  incident B-008 destroyed a run.
- **Persist before progressing.** Checkpoint after each meaningful transition
  (`heartbeat`, `renew`, run-state file), not at the end of the session.
- **Reconcile before releasing.** Release only after work has stopped; the release
  event is the last write to the ticket.

A ticket awaiting verification is a normal handoff state; do not reimplement it.

## Coordination reference

```bash
PYTHONPATH=scripts python3 -m wingman.coordination status   # runs, claims, exclusions
PYTHONPATH=scripts python3 -m wingman.coordination index    # regenerate docs/WINGMAN/RUNS.md
```

State is append-only on GitHub refs (`run-events/`, `claim-epochs/`, `leases/`,
`releases/`); ref creation is the only write primitive — see
`docs/WINGMAN/CONCURRENCY.md` for the atomicity and interruption matrix, and
`docs/WINGMAN/RUNS.md` for the generated snapshot (never edit it by hand).

Detailed procedures live in the `wingman-multi-session` skill
(`.agents/skills/wingman-multi-session/SKILL.md`); workspace lifecycle and recovery
live in `wingman-isolated-execution` (`#125`). Prefer the skill over this summary when
anything is ambiguous.
