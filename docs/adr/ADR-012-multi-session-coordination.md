# ADR-012: Multi-session coordination authority

- **Status:** Accepted 2026-11-25
- **Ticket:** [#123](https://github.com/anotherhale/str-ready-room/issues/123) (ADR-012)
- **Requirements:** R-OPS-01 (continuity of coordination state), R-ARCH-06
  (architectural decisions are recorded, not implied)
- **Depends on:** [#122](https://github.com/anotherhale/str-ready-room/issues/122)
  (coordination foundation, merged by PR #129),
  [#131](https://github.com/anotherhale/str-ready-room/issues/131) (append-only
  epoch hardening, merged by PR #132)
- **Constrains:** #124 (startup handshake), #125 (worktree isolation), #126
  (run-scoped state), #127 (concurrency validation), #128 (scheduler rollout),
  and every future coordinator prompt or skill

## Context

READY ROOM is built by a coordinator that runs as **many independent sessions**
against **one repository**, with no shared memory between them. Each session
starts cold: it recovers state from files, GitHub issues, and pull requests, then
picks work.

Until PR #129 the only rule preventing two sessions from taking the same ticket
was prose in `docs/WINGMAN/AGENT_REGISTRY.md` ("one active implementation session
at a time"). Prose is not a mechanism, and it failed:

- **B-006** — two sessions ran against one workspace and both selected #8,
  because selection read a *merged* checkpoint and nothing serialised *select*
  with *claim*.
- **B-007** — two coordinator-state PRs edited the same three files
  (`STATE.md`, `CHECKPOINT.json`, `EXECUTION_LOG.md`) and had to be reconciled by
  hand; three or more sessions make that routine.
- **B-008** — one shared working directory let another session check out `main`
  under a running session's feet, so an unreviewed commit landed on `main`.
- **B-009** — a nested ref layout (`claims/issue-131/e2` under the existing leaf
  `claims/issue-131`) returned `422` for a ref that did not exist, which by
  status code alone is indistinguishable from losing a claim race.

Two questions had to be answered before concurrency could be turned on:

1. **What is the authoritative record of "who is running, and what do they own?"**
2. **What happens when a session dies holding that record?**

The alternative — keep one session at a time, forever — is not a decision, it is
an absence of one. The coordination foundation (#122) and its hardening (#131)
implemented a candidate answer; this ADR records it as the decision, with the
rejected alternatives and the residual risks.

## Decision

### 1. GitHub git refs are the coordination authority; issues stay the ticket authority

```
refs/wingman/run-events/<RUN_ID>/e<N>            run state event (append-only)
refs/wingman/claim-epochs/issue-<T>/e<K>         exclusive lease on ticket T
refs/wingman/leases/issue-<T>/e<K>/<RUN_ID>-<n>  heartbeat / renewal within K
refs/wingman/releases/issue-<T>/e<K>             release of epoch K
refs/wingman/recoveries/issue-<T>/e<K+1>/<RUN_ID>-<ts>-<n>  takeover intent (advisory)
refs/wingman/observations/<RUN_ID>/<TARGET>-<n>  staleness observation (advisory)
```

Scope of authority is split, and the split is normative:

| Question | Authority |
|---|---|
| Is ticket T done, blocked, or ready? What depends on what? | **GitHub issue + PR evidence** |
| Which session owns T right now, and until when? | **`refs/wingman/*`** |
| What did run `R` actually do? | `docs/WINGMAN/runs/<RUN_ID>.*` (run-scoped) |
| What is the current summary? | `STATE.md` / `CHECKPOINT.json` (derived) |

A local workspace file is never authoritative for run ownership. `refs/wingman/*`
is not a branch, is untouched by `delete_branch_on_merge`, and carries no product
data.

### 2. State is derived from create-only refs, never overwritten

Only one GitHub write primitive is treated as atomic: **creating** a ref.
`POST /git/refs` returns `201` to exactly one writer; concurrent creators get
`422`. `PATCH /git/refs/{ref}` is last-writer-wins, and conditional updates
(`If-Match`) are rejected by the API. Therefore a mutable ref cannot express
"newer than what I read", and the design uses uniquely named refs plus a
derivation rule instead:

| Fact | Selection rule |
|---|---|
| Run state | highest `N` in `run-events/<RUN_ID>/` |
| Claim | highest `K` in `claim-epochs/issue-<T>/` |
| Renewal | newest `renewed_at` within the current `K` |
| Release | a release event at the current `K` makes the ticket available |
| Recovery | intent at `K+1`; gates takeover, never grants ownership |
| Observation | advisory; never mutates its target |

Consequences that the implementation relies on:

- Competing claims race on the *same* `e<K>`, so exactly one create wins.
- A superseded owner cannot clobber the new owner: its writes land in epoch `K`
  and derivation reads only `K+1`. Renew returns `ClaimSuperseded`.
- A late release for `K` cannot free a ticket held at `K+1`.
- Legacy pre-hardening refs (`runs/<RUN_ID>`, `claims/issue-<N>`) are read as
  sequence/epoch 1 and are **never** treated as free; the namespaces stay
  disjoint because a ref cannot be both a leaf and a directory (B-009).

### 3. Claim before write, exclusively, with a lease

- A session **must** register a run and **must** acquire the ticket claim before
  it writes anything for that ticket. Selection without a claim is a race, not a
  decision.
- The claim carries `run_id`, `ticket`, `claimed_at`, `last_heartbeat`,
  `expires_at`, `branch`, `worktree`, `run_status`, `current_activity`,
  `attempt_number`, `latest_checkpoint`, `pr`, `commit_sha`, `recovery_status`.
- Default lease is **25 minutes**, extended by `heartbeat`/`renew` (roughly every
  five minutes). One heartbeat mirrors both the lease and the run event.
- Ownership is re-checked on renew and release; a non-owner gets
  `NotClaimOwner` and must not touch the ticket.
- A session that cannot renew (its run ref is gone, its workspace died) stops
  ticket modification and checkpoints.

### 4. Recovery rules are normative

1. **An expired claim is not free.** `claim` returns `HELD_EXPIRED`; only
   `recover` may proceed, and it takes
   `refs/wingman/locks/recovery-issue-<N>` atomically so exactly one reclaimer
   acts.
2. **Inspect before takeover.** The reclaimer records what it inspected — branch,
   commits, pull request — and the provenance of the previous attempt
   (`recovered_from`, `previous_branch`, `previous_pr`, `attempt_number`).
3. **Never discard work because a heartbeat lapsed.** Adopt usable work and say
   so in the handoff; record abandonment explicitly if it is unusable.
4. **Never claim to finish work the driver did not produce.** A recovery that
   cannot verify a PR or commit records `WAITING` or `BLOCKED`, not `COMPLETED`.

### 5. Interruption is fail-closed

Every mutation is one create (plus one run event for heartbeat), ordered so a
crash can only make a claim look *expired*, never *available*:

- heartbeat writes the lease **before** the run event, so a lost run event leaves
  a live claim;
- release writes the release event **after** any work has stopped, so a lost run
  event leaves an available ticket, which is safe.

A release that lands without its run event is the documented fail-open case for a
clean release; it is recovered by reading the run's own record.

### 6. Run records are run-scoped

Each run writes only `docs/WINGMAN/runs/<RUN_ID>.md` and
`docs/WINGMAN/runs/<RUN_ID>.json`; the shared `STATE.md`, `CHECKPOINT.json`, and
`EXECUTION_LOG.md` are **derived** summaries reconciled at checkpoint, never the
record of what a run did. `docs/WINGMAN/RUNS.md` is generated by
`coordination index` and is never hand-edited. This is what removes the B-007
merge conflict: two runs never append to one file.

### 7. No new service

The authority is the repository every session already has push access to. There
is no coordination database, cache, queue, or broker to deploy, secure, monitor,
or lose. Dereferenced tag objects are garbage, not state.

### 8. Rollout is gated, not assumed

Concurrency is **enabled by evidence**, not by configuration. Until #127 exercises
two live sessions racing a real ticket, the rollout stays at **Phase A: one
implementation session**. #128 may not raise the cap before #127 passes.

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Issue labels, assignment, or comments as the claim | Last-writer-wins: two sessions both read "claimed" and both start. This is B-006 with extra API calls. |
| A state branch holding `claims/<N>.json` | Not atomic; concurrent pushes conflict, and force-pushing to resolve destroys the race record. |
| A single "lock issue" edited by everyone | Same last-writer-wins defect, with more API surface. |
| OpenHands automation KV store | Reachable only from sessions inside that runtime, so it cannot be the shared authority for every session. Useful for cache, not for truth. |
| Redis / Postgres / etcd / a coordination service | New infrastructure, new credentials, new failure mode, and no operator to run it — disproportionate for a single-repository coordinator. |
| Keep "one session at a time" as prose | Not a mechanism. It already failed three times (B-006, B-007, B-008). |
| Mutable refs updated with `PATCH` | Silently overwrites a newer payload; `If-Match` is unavailable, so no conditional update exists. |

## Consequences

**Positive**

- Exactly one session can own a ticket, and the loser learns it lost instead of
  duplicating work.
- A crashed session's ticket is recoverable without losing its branch or PR, and
  the takeover is recorded.
- State files no longer collide between sessions, so merges stop being hand
  serialised.
- The authority is auditable: a claim, renewal, release, or takeover is an
  immutable ref a human can read.

**Negative / accepted costs**

- Ref growth is linear in heartbeats (≈10–20 refs per run) with no compaction.
  Discovery costs one payload read per run plus one listing. #128 adds metrics;
  revisit if a run routinely exceeds ~100 events.
- Every session pays two extra API round trips (register, claim) before writing.
- The mechanism is coordination, not security: a session with push access can
  violate it. Enforcement is the honour system plus review of the ref history,
  and that is accepted for a single-maintainer repository.
- Ref-name constraints (leaf vs directory) cannot be reproduced by the in-memory
  test double, so adapter shape must be exercised against the real API (B-009).

## As built

| Concern | Code / artefact |
|---|---|
| Ref store, epochs, derivation, lease policy | `scripts/wingman/coordination.py` |
| CLI: `register`, `heartbeat`, `claim`, `renew`, `release`, `recover`, `observe`, `status`, `index` | `python -m wingman.coordination <command>` (with `PYTHONPATH=scripts`) |
| Tests, including concurrent-claim and concurrent-recovery races | `scripts/wingman/tests/test_coordination.py` |
| Design and incident record | `docs/WINGMAN/CONCURRENCY.md` |
| Generated registry snapshot | `docs/WINGMAN/RUNS.md` |

Operational entry point for a session:

```bash
PYTHONPATH=scripts python3 -m wingman.coordination status
PYTHONPATH=scripts python3 -m wingman.coordination --run-id "$RUN_ID" register \
  --session N --ticket T --branch BRANCH --activity "what I am about to do"
PYTHONPATH=scripts python3 -m wingman.coordination --run-id "$RUN_ID" claim T --branch BRANCH
```

## Open questions

- **Compaction.** When, if ever, do superseded epochs get pruned? Deleting them
  destroys audit history, so this needs a retention rule, not an implementer's
  choice.
- **Scheduler-side enforcement.** #124 covers the prompt-level handshake; a
  scheduler that starts a session without it can still bypass the claim. Whether
  #128 should refuse to launch on "no handshake evidence" is undecided.
- **Cross-repository coordination.** Out of scope here; if a second repository
  joins the same queue, the run registry would need a repository dimension.
