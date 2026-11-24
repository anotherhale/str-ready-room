---
name: wingman-multi-session
description: Coordinate WINGMAN work across concurrent runs — register a run, discover other workers, build the exclusion set, claim a ticket atomically and verify ownership, heartbeat, renew, release, recover an expired claim, and resolve conflicts. Use at the start of every WINGMAN session and whenever coordination state (runs, claims, leases, releases) is read or changed.
---

# WINGMAN multi-session coordination

Coordination state lives on GitHub git refs and is **append-only**. Ref creation is
the only write primitive; there is no update path, because GitHub `PATCH` is
last-writer-wins and refuses conditional requests. Never reintroduce a
read-modify-write on a coordination ref.

## State model (memorise this)

| Ref | Meaning | Written by |
|---|---|---|
| `run-events/<RUN_ID>/e<N>` | run snapshot N | the run itself |
| `claim-epochs/issue-<T>/e<K>` | exclusive claim, epoch K | whoever wins the create |
| `leases/issue-<T>/e<K>/<RUN_ID>-<n>` | renewal inside epoch K | epoch K's owner |
| `releases/issue-<T>/e<K>` | release of epoch K | epoch K's owner |
| `recoveries/issue-<T>/e<K>/…` | advisory "I am inspecting" | any run |
| `observations/<RUN_ID>/<TARGET>-<n>` | advisory note about another run | any run |

Derivation, in one sentence: **the highest claim epoch wins; a release at that
epoch makes the ticket available; a lease only extends that epoch's expiry; a
release/lease/intent for an older epoch is history, not authority.**

Legacy refs from before this design (`runs/<RUN_ID>`, `claims/issue-<T>`) are read
as sequence/epoch 1 and are never treated as free.

## Run statuses

`STARTING → RECONCILING → CLAIMING → EXECUTING → VALIDATING → CHECKPOINTING →
WAITING → RECOVERING → COMPLETED` (or `BLOCKED` / `ABANDONED` / `FAILED`).
`COMPLETED`, `BLOCKED`, `ABANDONED` and `FAILED` are terminal for the run.

Activity descriptions must be specific enough for another worker to act on:
"Implementing ADR-007 ownership decision", "Writing authorization tests for task
sharing", "Investigating failing integration test" — never "working".

## Startup (mandatory, in order)

1. `RUN_ID="$(date -u +%Y%m%dT%H%MZ)-$(openssl rand -hex 2)"` — one per session.
2. `git worktree add -b wingman/issue-<T>/run-$RUN_ID /tmp/wm/issue-<T> origin/main`
   (never work in the primary checkout; see `wingman-isolated-execution`).
3. `python3 -m wingman.coordination --run-id "$RUN_ID" register --session <N>
   --branch … --worktree … --activity "reconciling registry"`
4. `python3 -m wingman.coordination --run-id "$RUN_ID" status` — read every run,
   every claim, and the exclusion set before selecting anything.
5. Reconcile: for each claim, check the owner's registry entry, its branch, commits
   and PR. Record discrepancies; do not "fix" another run's claim by writing.
6. Build the exclusion set (below), select the highest-value eligible ticket.
7. `claim <T>` — must print `ACQUIRED`, then confirm with `status` that the epoch's
   `owner` is your `RUN_ID`. Anything else means **do not implement**.
8. `heartbeat --status EXECUTING --phase implementation --activity "<specific>"`.

`python3 -m wingman.preflight --run-id "$RUN_ID" --branch … --worktree …` performs
steps 1 and 5–8 in one fail-closed call and is the preferred entry point.

## Exclusion set

A ticket is unavailable when **any** of these holds:

- labelled `blocked`, or a `Depends on #N` / `Blocked by #N` dependency is open;
- another run holds a claim (live **or** expired — expired means recovery first);
- an open PR already delivers it;
- a branch other than your run's represents ongoing implementation;
- it is awaiting verification (`verification` label) or otherwise unsafe to touch.

Labels alone are not enough: derive the set from the registry **and** GitHub.

## Claim, renew, release

```bash
claim  <T> [--activity "…"]                  # ACQUIRED | ALREADY_HELD | HELD_BY_OTHER | HELD_EXPIRED
renew  <T> --activity "…" --pr N             # extends the lease; refused if superseded
release <T> --status VALIDATING|COMPLETED …  # after work stops; idempotent
```

- Renew every ~5 minutes of work and at every phase change; the default lease is
  25 minutes and a session is 30.
- `ClaimSuperseded` means another run owns a **newer epoch**: stop touching the
  ticket immediately, checkpoint, and report. Do not retry, do not delete refs.
- Release is the **last** write to the ticket. A crash before it leaves the claim
  held (recoverable); a crash after it is a clean handoff.
- Never delete or rewrite another run's refs. Branch history is never rewritten.

## Expired claims and recovery

An expired claim is **not** free.

1. Inspect: the previous branch, its commits, any PR, the run's last checkpoint.
2. Decide: usable work → recover and continue it; unusable → recover and say so.
3. `recover <T> --inspect "<what you read>"` — creates epoch `K+1` atomically. If two
   runs recover at once, exactly one wins; the loser gets `RECOVERY_IN_PROGRESS` and
   must pick another ticket.
4. Record `recovered_from`, `attempt_number`, and the inspection note on the issue.

A dead recovery attempt blocks nothing: the intent ref is advisory and the takeover
is the atomic create. Never treat an intent as a lock.

## Stale runs

Judge a run by its own events plus its live lease. `stale` (≈40 min quiet) or
`abandoned` (≈80 min) is a *reason to inspect*, not a licence to take over.
Mark it with an observation (`observe <RUN_ID> --status ABANDONED --reason …`); never
write into another run's refs.

## Conflicts

- Two claim attempts: exactly one wins. The loser must verify failure, touch
  nothing, and select another ticket.
- Conflicting edits to the same files: stop, keep both sets of work, reconcile
  ownership from the claims and PRs before resolving.
- Coordination unreadable or unverifiable: **stop**. Do not implement on an
  unverified claim.

## Persistence and handoff

Persist after each transition: `heartbeat`/`renew` for the registry, a run-scoped
checkpoint under `docs/WINGMAN/runs/<RUN_ID>.{json,md}`, and a comment on the issue.
Do not batch state to the end of the session, and do not rewrite shared files another
run may be editing (`STATE.md`, `CHECKPOINT.json`) as part of a ticket PR.

Handoff: release the claim with the PR link and the next recommendation, set the
issue to `verification`, and leave the worktree in place until the PR merges.
