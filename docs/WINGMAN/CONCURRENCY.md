# WINGMAN concurrency: audit, authority, and risks

Status: coordination foundation ([#122](https://github.com/anotherhale/str-ready-room/issues/122))
was hardened to an append-only design in
[#131](https://github.com/anotherhale/str-ready-room/issues/131) after review found
that its mutable ref updates were not compare-and-swap. The operating-model upgrade is
tracked in [#121](https://github.com/anotherhale/str-ready-room/issues/121).

**Layout note.** The pre-hardening refs (`runs/<RUN_ID>`, `claims/issue-<T>`) are still
read as sequence/epoch 1; the append-only layout uses *separate* namespaces
(`run-events/`, `claim-epochs/`) because git forbids a ref being both a leaf and a
directory (incident B-009).

## 1. Audit of the pre-upgrade system

What existed before this document was written:

| Capability | How it worked | Verdict |
|---|---|---|
| Ticket queue | GitHub issues, labels (`ready`, `in-progress`, `verification`, `blocked`) | Reusable: issues stay authoritative for *ticket* state |
| Coordinator state | `docs/WINGMAN/CHECKPOINT.json`, `STATE.md`, `EXECUTION_LOG.md`, committed on a per-session branch and merged by PR | Reusable as *derived* state; unsafe as the coordination authority |
| Session start | Operator/scheduler starts an OpenHands session; the session reads `WINGMAN.md` and follows `docs/WINGMAN/README.md` | Reusable |
| Run identity | None. A run was identified only by "session N" written into `CHECKPOINT.json` | Missing |
| Run discovery | None. A new run read the last merged checkpoint | Missing |
| Ticket claim | None. "One active session at a time" was an instruction, not a mechanism | Missing |
| Workspace | Whatever directory the session was launched in | Missing isolation |
| Heartbeat / staleness | None | Missing |
| Recovery | Ad-hoc: re-read the checkpoint, re-inspect the repo by hand | Partially missing |

The one existing concurrency rule was prose in `AGENT_REGISTRY.md` ("one active
implementation session at a time"). Prose is not a mechanism.

### Observed failure B-006

Two sessions ran against one workspace during session 6 and both selected #8.

- **Root cause:** ticket selection read a *merged* checkpoint, and nothing serialised
  "select ticket" with "claim ticket". Both sessions were correct by their own
  information.
- **Contributing factors:** no run identity (so the second session could not see the
  first), no shared claim, one shared workspace, and state written only at end of run.
- **Impact:** no work lost (identical content), but PR #114's description drifted from
  the committed file, one session overwrote the other's uncommitted `STATE.md`, and the
  run workspace directory was deleted twice mid-run.
- **Prevention now:** exclusive claim before any ticket write
  (`coordination.py claim`), one append-only event stream per run, per-run worktree
  (#125), immediate checkpointing (#126).
- **Recovery mechanism:** expired claim → recovery inspection (branch, commits, PR)
  before takeover; the reclaimer records `recovered_from`, `previous_branch`,
  `previous_pr`, and bumps `attempt_number`.
- **Validation evidence:** the primitive was exercised live during session 9
  (`POST /git/refs` → `201` for the owner, `422` for a second run 40 seconds later) and
  is regression-tested in `scripts/wingman/tests/test_coordination.py`
  (`test_claim_is_exclusive_under_concurrent_attempts`,
  `test_only_one_concurrent_recovery_wins`).

### Observed failure B-007 (new, session 9)

Two coordinator-state PRs (#118 from session 7, #120 from session 8) were open at the
same time and edited the same three files (`STATE.md`, `CHECKPOINT.json`,
`EXECUTION_LOG.md`). They could not both merge unreconciled, so the owner resolved them
by hand. With three or more sessions the same pattern guarantees repeated conflicts.

- **Root cause:** state persisted by appending to shared mutable files at end of run.
- **Impact:** state merges are serialised by hand and can be dropped; the recovery
  source of truth drifts from what sessions actually did.
- **Prevention:** run-scoped artifacts `docs/WINGMAN/runs/<RUN_ID>.json`, a generated
  `RUNS.md`, and registry refs as the source of truth (#126). This session already
  writes only run-scoped files for its own state.

### Observed failure B-008 (new, session 9)

The run workspace was shared with another session, which fetched and checked `main`
out under this run mid-execution. The next commit therefore landed on `main` instead of
the ticket branch and was pushed there before the branch state was re-checked.

- **Root cause:** one working directory shared by independent runs; `HEAD` is workspace
  state, not run state.
- **Contributing factors:** branch identity was never *verified* before committing, and
  the run had no dedicated worktree (the isolation ticket, #125, was still open).
- **Impact:** one unreviewed commit reached `main`; no other session's work was lost.
  Remediated by reverting it on `main` and re-applying the same tree on
  `wingman/issue-122/run-<RUN_ID>` for review.
- **Prevention:** one worktree per run (#125), plus a pre-commit check that the current
  branch matches the claimed branch and that `origin/main` is untouched.
- **Recovery mechanism:** revert on `main` (never force-push), re-apply on the ticket
  branch, disclose in the PR.

## 2. Coordination authority

**Decision: GitHub custom git refs are the coordination authority.**

```
refs/wingman/runs/<RUN_ID>              run registry entry, written only by its owner
refs/wingman/claims/issue-<N>           exclusive lease on ticket N
refs/wingman/locks/recovery-issue-<N>   serialises takeover of an expired claim
```

Each ref points at an annotated tag whose message is the JSON record, so one read
returns both ownership and the full run/claim metadata. (Tag objects are immutable;
a renewal writes a new tag object and moves the ref. Unreferenced tag objects are
garbage, not state.)

Why refs:

- **Atomic acquisition.** `POST /git/refs` succeeds once. A concurrent creator gets
  `422 Reference already exists`. That is a compare-and-set, which labels, comments,
  issue assignment, and any number of `PATCH`-based APIs are not.
- **Universal reach.** Every session has push access to the repository it works on; no
  session-scoped service, database, or in-memory store is required.
- **No shared mutable file.** Each run owns its own ref, so two runs never contend for
  one object and there is nothing to merge.
- **Cheap.** A claim is one read plus one write; least privilege is the token the
  session already holds to push a branch.

Rejected alternatives:

| Alternative | Why rejected |
|---|---|
| Issue labels / assignment / comments | Last-writer-wins; two sessions both see "claimed" and both start |
| State branch holding `claims/<N>.json` | Not atomic; concurrent pushes conflict, and a force-push to resolve loses the race record |
| OpenHands automation KV store | Reachable only from sessions running in that stack; not a repository primitive, so it cannot be the shared authority for every session |
| Redis / Postgres / etcd | New infrastructure, new credentials, new failure mode, no operator to run it |
| A single "lock issue" edited by everyone | Same last-writer-wins problem with extra API calls |

`refs/wingman/*` is not a branch and is not touched by `delete_branch_on_merge`.

## 3. Atomicity: verified, not assumed

Only one GitHub write primitive is used for coordination state: **creating** a ref.

| Operation | GitHub semantics (verified live) | Verdict |
|---|---|---|
| `POST /git/refs` (create) | `201` once; a second creator gets `422 Reference update failed` | **Atomic** — used for every state write |
| `PATCH /git/refs/{ref}` (update) | `200`, last-writer-wins; a stale writer silently overwrites a newer payload | **Not atomic** — not used for state |
| `PATCH` with `If-Match` | `400 Conditional request headers are not allowed in unsafe requests unless supported by the endpoint` | **Unavailable** — no conditional update exists |
| `DELETE /git/refs/{ref}` | `204`; `422` when absent | Atomic, idempotent |

Evidence (live, this repository, 2026-11-24): writers A and B both observed `seq 1`;
B wrote `seq 2`; A then wrote `seq 2` with its stale payload → `200`, final payload was
A's. The same payload sequence with the create-only layout cannot express that write at
all, because A's target name is already taken.

Therefore each coordination fact is an immutable, uniquely named ref and the current
state is **derived**:

| Fact | Ref (create-only) | Selection rule |
|---|---|---|
| Run state event | `run-events/<RUN_ID>/e<N>` | highest `N` per run |
| Claim | `claim-epochs/issue-<T>/e<K>` | highest `K` per ticket |
| Renewal | `leases/issue-<T>/e<K>/<RUN_ID>-<n>` | newest by `renewed_at` within the current `K` |
| Release | `releases/issue-<T>/e<K>` | a release at the current `K` makes the ticket available |
| Recovery intent | `recoveries/issue-<T>/e<K+1>/<RUN_ID>-<ts>-<n>` | advisory only; never grants or blocks |
| Observation | `observations/<RUN_ID>/<TARGET>-<n>` | advisory only; never mutates the target |

Consequences:

- **Competing claims** race on the *same* `e<K>`, so exactly one create wins; the
  loser gets a typed result and retries nothing.
- **A superseded owner cannot clobber the new owner.** Its writes land in epoch `K`,
  and derivation only reads `K+1`. Renew is refused with `ClaimSuperseded`; a late
  release event for `K` cannot free a ticket held at `K+1`.
- **A stale observer cannot overwrite a resumed run.** Observations live in the
  observer's namespace; a run that heartbeats afterwards is simply not stale.
- **Run events are append-only per sequence number**, so a duplicate writer either
  takes the next sequence or loses to `422` and re-reads. Nothing is overwritten.

## 4. Interruption matrix

Every write is a single create, except the two-write heartbeat (lease, then run event).
The order is chosen so a failure is **fail-closed**: it can make a claim look expired,
never available.

| Operation | Steps | Crash before step 1 | Crash between steps | Resulting state |
|---|---|---|---|---|
| `register` | create run event `e1` | no registry entry | n/a | run not discoverable; nothing was claimed |
| `claim` | derive → create `e<K>` → verify → append run event | no claim | claim exists, run record stale | claim held (authoritative); activity may lag until next heartbeat |
| `heartbeat` | create lease → create run event | claim keeps its previous expiry | lease landed, run event lost | claim **live**, ticket not available; run activity stale (health tolerates a live lease) |
| `renew` | create lease → append run event | previous expiry stands | as heartbeat | same |
| `release` | create release event → append run event | claim still held → recovery path | release landed, run record stale | ticket available; work had already stopped (ordering invariant) |
| `recover` | create intent → create `e<K+1>` → verify → append run event | nothing happened | intent exists, no ownership | intent is advisory; the next contender wins the epoch create |
| `observe` | create observation | nothing happened | n/a | no effect on authority |

The heartbeat order (lease first) is deliberate: a lost run event leaves a *live* claim,
while a lost lease leaves a claim that expires and then requires recovery inspection.

## 5. Lease and recovery protocol

- A claim carries `run_id`, `ticket`, `claimed_at`, `last_heartbeat`, `expires_at`,
  `branch`, `worktree`, `run_status`, `current_activity`, `attempt_number`,
  `latest_checkpoint`, `pr`, `commit_sha`, `recovery_status`.
- Default lease is 25 minutes, renewed by `heartbeat`/`renew` (about every 5 minutes;
  the same call mirrors the run ref, so one heartbeat covers both).
- **An expired claim is not free.** `claim` returns `HELD_EXPIRED` and `recover` is the
  only path forward. `recover` takes `refs/wingman/locks/recovery-issue-<N>`
  atomically, so exactly one reclaimer proceeds; it records what it inspected
  (`--inspect`) and the provenance of the previous attempt.
- Never discard work because a heartbeat lapsed. Inspect the branch, commits, and PR
  first; adopt the work if it is usable, otherwise record abandonment.
- Ownership is checked on renew and release: a non-owner gets `NotClaimOwner` and must
  not touch the ticket.
- A run whose ref disappears (workspace/session loss) cannot renew; it must stop
  ticket modifications and checkpoint.

## 6. Run status vocabulary

`STARTING`, `RECONCILING`, `CLAIMING`, `EXECUTING`, `VALIDATING`, `CHECKPOINTING`,
`WAITING`, `RECOVERING`, `COMPLETED`, `BLOCKED`, `ABANDONED`, `FAILED`. Terminal:
`COMPLETED`, `BLOCKED`, `ABANDONED`, `FAILED`.

Activity strings must name the work, not the mood: "Writing authorization tests for
task sharing", not "working". Another session reads them to decide whether a ticket is
contested.

## 7. Precedence of state

```
GitHub issues                  ticket status, dependencies, delivery evidence (PRs, commits)
refs/wingman/*                 who is running, what they own, since when, until when
docs/WINGMAN/runs/<RUN_ID>*    one run's own record (append-only, no shared file)
docs/WINGMAN/RUNS.md           generated snapshot of the registry (never hand-edited)
STATE.md / CHECKPOINT.json     derived summary, reconciled, never authoritative over a live claim
```

A local workspace file is never authoritative for run ownership.

## 8. Residual risks (open work)

| Risk | Mitigation ticket |
|---|---|
| Sessions can still be *started* without following the handshake | #124 — mandatory handshake in the prompt + skill |
| No worktree isolation yet; sessions share a directory (B-008) | #125 |
| State still merged through shared files during the transition | #126 |
| Claim/recovery is unit- and fault-tested but not yet exercised by two *live* sessions racing a real ticket | #127 |
| Concurrency is enabled by scheduler, not earned | #128 gates Phase B/C on #127 |
| Ref growth is linear in heartbeats (≈10–20 refs/run; no compaction). Discovery reads one payload per run, so cost is O(runs) reads and one listing | #128 adds metrics; revisit if a run routinely exceeds ~100 events |
| Legacy leaf refs (`runs/<RUN_ID>`, `claims/issue-<N>`) linger read-only until their owners release them | #126 / #124 document the migration; they are never treated as free |
| Coordination tests are not run by CI | #15 (blocked on the token's Workflows scope) |

Until #127 passes, the rollout stays at **Phase A: one implementation session**.

## 9. Reconciliation log

- **Run `20261124T1851Z-5efb` (session 9)**: at start, #9 (PR #119) and #14 (PR #117)
  were in progress with state PRs #118/#120 open, so both tickets were excluded. During
  the run all four merged, so at handoff #9 and #14 are done and the READY queue was
  recomputed from live issue state. The registry held only this run's entry; no stale
  claims were found.

- **Run `20261124T1921Z-5d70` (session 11)**: claim for #131 was taken with the
  pre-hardening layout, then migrated in place — `release` of the legacy epoch, then
  `claim` at epoch 2 — which also served as the live adapter test. During the
  migration the first new-layout write failed: git cannot create `runs/<RUN_ID>/e2`
  while `runs/<RUN_ID>` exists (a ref is either a leaf or a directory), which is why
  the append-only layout lives in `run-events/` and `claim-epochs/` and legacy refs
  are read-only. That failure also reproduced the release interrupt: the release event
  landed and the run event did not, so the ticket read as available while the run
  record still said EXECUTING — the documented, intended fail-open direction for a
  clean release.

### Incident B-009 — a ref cannot be both a leaf and a directory

- **Root cause:** the hardened layout nested epoch refs under the legacy leaf refs
  (`claims/issue-131/e2` while `claims/issue-131` exists).
- **Impact:** `POST /git/refs` returned `422 Reference update failed` for a ref that
  did not exist — indistinguishable, by status code alone, from losing a claim race.
- **Prevention:** disjoint namespaces for legacy and append-only layouts; the store
  only maps `422`/`409` on create to `RefExists`, so a schema-level failure surfaces
  as an error rather than a phantom loss.
- **Lesson:** the in-memory adapter cannot reproduce ref-name constraints. Adapter
  shape must be exercised against the real protocol (as `AGENTS.md` already warns).
