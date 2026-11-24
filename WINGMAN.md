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

## Live coordination state

Before selecting a ticket, read the authoritative registry (requires `GITHUB_TOKEN`):

```bash
PYTHONPATH=scripts python3 -m wingman.coordination status
```

Ticket claims live in `refs/wingman/claims/issue-<N>`, run entries in
`refs/wingman/runs/<RUN_ID>` on GitHub. A ticket with a live claim — or an expired
claim awaiting recovery — is not available. `docs/WINGMAN/RUNS.md` is a generated
snapshot; never edit it by hand. Design, audit, and incident record:
`docs/WINGMAN/CONCURRENCY.md`.
