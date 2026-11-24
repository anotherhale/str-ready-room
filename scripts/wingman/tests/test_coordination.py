"""Coordination contract, race, and fault-injection tests.

`InMemoryRefStore` is a genuine second adapter for the ref-store port: it enforces
the same create-only compare-and-set contract (exactly one creator wins) as
GitHub, so the races below exercise real claim code. `FaultStore` and `RaceStore`
are adapters too — they inject a failure or a competing write at a chosen ref,
which is how the crash-consistency guarantees are tested deterministically
without sleeps or mocks of the coordination logic.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from wingman.coordination import (
    CLAIM_EPOCH_PREFIX,
    CLAIM_PREFIX,
    LEASE_PREFIX,
    RECOVERY_INTENT_PREFIX,
    RELEASE_PREFIX,
    RUN_EVENT_PREFIX,
    RUN_PREFIX,
    Claim,
    ClaimLost,
    ClaimOutcome,
    ClaimStatus,
    ClaimSuperseded,
    ClaimUnverified,
    Coordinator,
    InMemoryRefStore,
    Lease,
    NotClaimOwner,
    Run,
    RunStatus,
    StoreError,
    _iso,
)

START = datetime(2026, 11, 24, 19, 0, tzinfo=UTC)


class Clock:
    def __init__(self, moment: datetime = START) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, **kwargs: float) -> None:
        self.moment = self.moment + timedelta(**kwargs)


class FaultStore(InMemoryRefStore):
    """Fails creates whose ref matches `predicate`, like a crash or dropped request."""

    def __init__(self, predicate, times: int = 1000) -> None:
        super().__init__()
        self._predicate = predicate
        self._remaining = times
        self.failures = 0

    def create(self, ref: str, payload: dict) -> None:
        if self._remaining > 0 and self._predicate(ref):
            self._remaining -= 1
            self.failures += 1
            raise StoreError(f"injected failure creating {ref}")
        super().create(ref, payload)


class RaceStore(InMemoryRefStore):
    """Runs a hook immediately before a create, to force a competing writer to win."""

    def __init__(self) -> None:
        super().__init__()
        self.hook = None

    def create(self, ref: str, payload: dict) -> None:
        hook, self.hook = self.hook, None
        if hook is not None:
            hook(ref)
        super().create(ref, payload)


def coordinator(store, run_id: str, clock: Clock | None = None) -> Coordinator:
    return Coordinator(store, run_id, lease=timedelta(minutes=25), clock=clock or Clock())


def registered(store, run_id: str = "run-a", clock: Clock | None = None) -> Coordinator:
    coord = coordinator(store, run_id, clock)
    coord.register(session=1, branch=f"wingman/issue-5/run-{run_id}", worktree=f"/tmp/{run_id}")
    return coord


def claim_refs(store) -> list[str]:
    return store.list_names(CLAIM_EPOCH_PREFIX)


# ----------------------------------------------------------------- creation CAS


def test_claim_is_exclusive_under_concurrent_attempts() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    contenders = [registered(store, f"run-{index}", clock) for index in range(8)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda c: c.claim(5, activity="implementing ADR-012"), contenders))

    winners = [result for result in results if result.acquired]
    assert len(winners) == 1
    assert all(result.outcome is ClaimOutcome.HELD_BY_OTHER for result in results if not result.acquired)
    # Exactly one epoch ref exists, so only one writer can ever be authoritative.
    assert claim_refs(store) == [f"{CLAIM_EPOCH_PREFIX}5/e1"]
    assert winners[0].claim.epoch == 1


def test_loser_is_told_who_holds_the_claim_and_keeps_no_ticket_state() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    first = registered(store, "run-first", clock)
    second = registered(store, "run-second", clock)
    first.claim(9, activity="Implementing ADR-007 ownership decision")

    result = second.claim(9, activity="implementing something else")

    assert result.outcome is ClaimOutcome.HELD_BY_OTHER
    assert "run-first" in result.detail
    assert second.run().ticket is None
    assert second.run().claim_status == ClaimStatus.NONE


def test_simultaneous_startup_allocates_distinct_tickets_without_duplicating_work() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    a = registered(store, "run-a", clock)
    b = registered(store, "run-b", clock)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pair: pair[0].claim(pair[1]), [(a, 5), (b, 5)]))

    assert len([r for r in results if r.acquired]) == 1
    loser = b if results[0].acquired else a
    assert loser.claim(6).acquired
    assert loser.excluded_tickets().keys() == {5, 6} or 6 in loser.excluded_tickets()


def test_expired_claim_is_not_automatically_free() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    first = registered(store, "run-first", clock)
    second = registered(store, "run-second", clock)
    first.claim(9)
    clock.advance(minutes=26)

    result = second.claim(9)

    assert result.outcome is ClaimOutcome.HELD_EXPIRED
    assert second.claim_of(9 ).run_id == "run-first"
    assert "recovery inspection required" in second.excluded_tickets()[9]


def test_unverified_claim_is_rejected_before_any_work_begins() -> None:
    class LyingStore(InMemoryRefStore):
        def create(self, ref: str, payload: dict) -> None:
            super().create(ref, {**payload, "run_id": "run-someone-else"})

    store = LyingStore()
    run = registered(store, "run-a", Clock())

    with pytest.raises(ClaimUnverified):
        run.claim(5)


# ------------------------------------------------------- lifecycle and recovery


def test_recovery_takes_over_expired_claim_with_provenance() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    stale = registered(store, "run-stale", clock)
    stale.claim(9, activity="Implementing ADR-007")
    stale.renew(9, pr=119, activity="Writing ADR-007 draft")
    clock.advance(minutes=41)
    fresh = coordinator(store, "run-fresh", clock)
    fresh.register(session=2, branch="wingman/issue-9/run-run-fresh", worktree="/tmp/fresh")

    result = fresh.recover(9, inspect="PR #119 read; draft usable")

    assert result.acquired
    claim = fresh.claim_of(9)
    assert claim.epoch == 2
    assert claim.attempt_number == 2
    assert claim.recovery_status == "RECOVERED"
    assert claim.recovered_from == "run-stale"
    assert claim.previous_pr == 119
    assert "inspection" in (claim.inspection or "") or claim.inspection == "PR #119 read; draft usable"
    # The takeover is one immutable event; the previous epoch is still auditable.
    assert store.read(f"{CLAIM_EPOCH_PREFIX}9/e1")["run_id"] == "run-stale"


def test_only_one_concurrent_recovery_wins() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    registered(store, "run-stale", clock).claim(9)
    clock.advance(minutes=41)
    contenders = [registered(store, f"run-{index}", clock) for index in range(6)]

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda c: c.recover(9), contenders))

    winners = [result for result in results if result.acquired]
    assert len(winners) == 1
    assert claim_refs(store) == [f"{CLAIM_EPOCH_PREFIX}9/e1", f"{CLAIM_EPOCH_PREFIX}9/e2"]
    for loser in (result for result in results if not result.acquired):
        assert loser.outcome in {ClaimOutcome.RECOVERY_IN_PROGRESS, ClaimOutcome.NOT_EXPIRED}
        assert loser.claim is not None and loser.claim.epoch == 2


def test_recovery_refuses_a_live_claim() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    registered(store, "run-first", clock).claim(9)
    other = registered(store, "run-second", clock)

    result = other.recover(9)

    assert result.outcome is ClaimOutcome.NOT_EXPIRED
    assert other.claim_of(9).run_id == "run-first"


def test_abandoned_recovery_intent_does_not_block_takeover() -> None:
    """The process that announced a recovery can die; the intent must not become a lock."""
    store = FaultStore(lambda ref: ref.startswith(CLAIM_EPOCH_PREFIX) and "/e2" in ref, times=1)
    clock = Clock()
    registered(store, "run-stale", clock).claim(9)
    clock.advance(minutes=41)
    dying = registered(store, "run-dying", clock)

    with pytest.raises(StoreError):
        dying.recover(9, inspect="branch inspected")

    assert store.list_names(f"{RECOVERY_INTENT_PREFIX}9/e2/"), "intent should be recorded before the takeover"
    assert dying.claim_of(9).run_id == "run-stale", "no ownership was granted by the intent"

    survivor = coordinator(store, "run-survivor", clock)
    survivor.register(session=3)
    result = survivor.recover(9, inspect="checked the abandoned attempt's intent and the branch")

    assert result.acquired
    assert survivor.claim_of(9).epoch == 2
    assert survivor.claim_of(9).recovered_from == "run-stale"


def test_recovery_intent_alone_grants_nothing() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    run = registered(store, "run-a", clock)
    store.create(
        f"{RECOVERY_INTENT_PREFIX}5/e1/run-other-0",
        {"run_id": "run-other", "ticket": 5, "target_epoch": 1, "at": _iso(clock())},
    )

    state = run.ticket_state(5)

    assert state.claim is None and state.epoch == 0
    assert state.recovery_intents, "intent is visible"
    assert run.claim(5).acquired


def test_non_owner_cannot_renew_or_release() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    registered(store, "run-first", clock).claim(9)
    other = registered(store, "run-second", clock)

    with pytest.raises(NotClaimOwner):
        other.renew(9, activity="hijack")
    with pytest.raises(NotClaimOwner):
        other.release(9)

    assert other.claim_of(9).run_id == "run-first"


def test_superseded_owner_cannot_renew_after_takeover() -> None:
    """A zombie from epoch 1 must not be able to extend or touch epoch 2."""
    store = InMemoryRefStore()
    clock = Clock()
    zombie = registered(store, "run-zombie", clock)
    zombie.claim(9)
    clock.advance(minutes=41)
    taker = registered(store, "run-taker", clock)
    assert taker.recover(9).acquired

    with pytest.raises(ClaimSuperseded):
        zombie.renew(9, activity="still working, honest")
    with pytest.raises(NotClaimOwner):
        zombie.release(9)

    assert taker.claim_of(9).run_id == "run-taxer".replace("taxer", "taker")


def test_superseded_release_event_cannot_free_the_ticket() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    zombie = registered(store, "run-zombie", clock)
    zombie.claim(9)
    clock.advance(minutes=41)
    taker = registered(store, "run-taker", clock)
    taker.recover(9)
    # A stale process writes its release for the *old* epoch, after the takeover.
    store.create(
        f"{RELEASE_PREFIX}9/e1",
        {"run_id": "run-zombie", "ticket": 9, "epoch": 1, "released_at": _iso(clock())},
    )

    state = taker.ticket_state(9)

    assert state.epoch == 2
    assert state.claim is not None and state.claim.run_id == "run-taker"
    assert taker.claim_of(9) is not None


def test_release_frees_the_ticket_and_the_next_claim_takes_the_next_epoch() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    first = registered(store, "run-first", clock)
    first.claim(5)
    first.release(5, status=RunStatus.BLOCKED, activity="blocked on missing environment")

    state = first.ticket_state(5)
    assert state.claim is None and state.released_at is not None
    assert first.run().claim_status == ClaimStatus.RELEASED

    second = registered(store, "run-second", clock)
    result = second.claim(5)
    assert result.acquired and result.claim.epoch == 2


def test_release_is_idempotent() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    run = registered(store, "run-a", clock)
    run.claim(5)
    run.release(5)

    run.release(5)  # must not raise, must not create a second event

    assert store.list_names(f"{RELEASE_PREFIX}5/") == [f"{RELEASE_PREFIX}5/e1"]


# ------------------------------------------------ heartbeat and crash consistency


def test_heartbeat_renews_lease_and_preserves_activity() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    run = registered(store, "run-a", clock)
    run.claim(5, activity="Writing authorization tests for task sharing")
    before = run.ticket_state(5).expires_at

    clock.advance(minutes=5)
    run.heartbeat(status=RunStatus.EXECUTING, phase="implementation", activity="Validating backend task endpoints")
    after = run.ticket_state(5)

    assert after.expires_at > before
    assert after.claim.expires_at == after.expires_at
    # The live view follows the newest lease; the epoch event stays immutable.
    assert after.claim.current_activity == "Validating backend task endpoints"
    assert after.leases[-1].current_activity == "Validating backend task endpoints"
    assert store.read(f"{CLAIM_EPOCH_PREFIX}5/e1")["current_activity"] == "Writing authorization tests for task sharing"
    assert run.run().current_activity == "Validating backend task endpoints"


def test_heartbeat_failure_before_the_lease_is_fail_closed() -> None:
    """A lease write that never lands can only let the claim expire - never free it."""
    clock = Clock()
    store = FaultStore(lambda ref: ref.startswith(LEASE_PREFIX) or "/e3" in ref)
    run = registered(store, "run-a", clock)
    run.claim(5)
    clock.advance(minutes=20)

    with pytest.raises(StoreError):
        run.heartbeat(activity="tests running")
    assert store.failures >= 1, "the lease write must have been attempted and failed"

    clock.advance(minutes=10)  # past the original 25-minute lease
    other = registered(store, "run-b", clock)
    assert other.claim(5).outcome is ClaimOutcome.HELD_EXPIRED
    assert other.ticket_state(5).available is False


def test_heartbeat_failure_after_the_lease_keeps_the_claim_live() -> None:
    """A lost run event leaves the claim live; it can never look free."""
    clock = Clock()
    store = FaultStore(lambda ref: ref.startswith(RUN_EVENT_PREFIX) and "/e3" in ref)
    run = registered(store, "run-a", clock)
    run.claim(5)
    clock.advance(minutes=20)

    with pytest.raises(StoreError):
        run.heartbeat(activity="tests running")

    state = run.ticket_state(5)
    assert state.claim is not None and state.claim.run_id == "run-a"
    assert state.expires_at > _iso(clock())  # the lease did land
    other = registered(store, "run-b", clock)
    assert other.claim(5).outcome is ClaimOutcome.HELD_BY_OTHER


def test_release_interrupted_before_the_event_leaves_the_claim_held() -> None:
    clock = Clock()
    store = FaultStore(lambda ref: ref.startswith(RELEASE_PREFIX))
    run = registered(store, "run-a", clock)
    run.claim(5)

    with pytest.raises(StoreError):
        run.release(5)

    assert run.ticket_state(5).claim is not None
    other = registered(store, "run-b", clock)
    assert other.claim(5).outcome is ClaimOutcome.HELD_BY_OTHER


def test_release_interrupted_after_the_event_is_available_and_work_already_stopped() -> None:
    """The release event is the last write to the ticket; the run record is cosmetic."""
    clock = Clock()
    store = FaultStore(lambda ref: ref.startswith(RUN_EVENT_PREFIX) and "/e3" in ref)
    run = registered(store, "run-a", clock)
    run.claim(5)

    with pytest.raises(StoreError):
        run.release(5, activity="handing off")

    state = run.ticket_state(5)
    assert state.claim is None and state.released_at is not None
    other = registered(store, "run-b", clock)
    assert other.claim(5).acquired


def test_run_event_race_never_overwrites_newer_state() -> None:
    """Two writers of one run id both try seq 2; the loser re-reads and appends seq 3."""
    store = RaceStore()
    clock = Clock()
    first = registered(store, "run-a", clock)
    second = Coordinator(store, "run-a", lease=timedelta(minutes=25), clock=clock)
    store.hook = lambda ref: second.heartbeat(activity="writer two heartbeat")

    first.heartbeat(activity="writer one heartbeat")

    events = first.run_events()
    assert [event.seq for event in events] == [1, 2, 3]
    assert events[-1].current_activity == "writer one heartbeat"
    # Both facts survive: nothing was overwritten.
    assert {event.current_activity for event in events[1:]} == {"writer two heartbeat", "writer one heartbeat"}


# --------------------------------------------------------- observation / staleness


def test_observation_cannot_mask_a_resumed_run() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    target = registered(store, "run-target", clock)
    target.claim(5, activity="Implementing ADR-007")
    target.heartbeat(status=RunStatus.EXECUTING, phase="implementation", activity="Implementing ADR-007")
    clock.advance(minutes=45)  # target looks stale
    observer = registered(store, "run-observer", clock)

    observed = observer.mark_run("run-target", RunStatus.ABANDONED, activity="no heartbeat for 45m")

    assert observed is not None
    assert observed.run_status == RunStatus.EXECUTING, "the target's own record is not rewritten"
    assert observer.observations_of("run-target")[0]["observed_status"] == "ABANDONED"

    clock.advance(minutes=1)
    target.heartbeat(status=RunStatus.EXECUTING, activity="Resumed: writing persistence tests")

    latest = next(run for run in observer.runs() if run.run_id == "run-target")
    assert latest.run_status == RunStatus.EXECUTING
    assert latest.current_activity == "Resumed: writing persistence tests"
    assert observer.health(latest) == "live"
    # The observation is retained as history, not as authority.
    assert len(observer.observations_of("run-target")) == 1


def test_concurrent_observations_are_all_preserved() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    target = registered(store, "run-target", clock)
    clock.advance(minutes=45)
    observers = [registered(store, f"run-observer-{index}", clock) for index in range(5)]

    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda c: c.observe("run-target", RunStatus.ABANDONED, reason="stale"), observers))

    assert len(target.observations_of("run-target")) == 5


# ------------------------------------------------------------- registry and state


def test_registry_records_every_run_without_lost_updates() -> None:
    store = InMemoryRefStore()
    clock = Clock()

    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(lambda index: registered(store, f"run-{index}", clock), range(10)))

    observer = registered(store, "run-observer", clock)
    assert len(observer.runs()) == 11


def test_discovery_reports_status_activity_branch_and_expiry() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    run = registered(store, "run-worker", clock)
    run.claim(15)
    run.heartbeat(status=RunStatus.EXECUTING, phase="implementation", activity="Validating backend task endpoints", pr=131)
    clock.advance(minutes=3)

    [view] = [item for item in run.runs() if item.run_id == "run-worker"]
    assert view.run_status == RunStatus.EXECUTING
    assert view.current_activity == "Validating backend task endpoints"
    assert view.pr == 131
    assert view.branch == "wingman/issue-5/run-run-worker"
    assert view.heartbeat_age(clock()) == 180
    assert run.health(view) == "live"
    assert str(run.ticket_state(15).expires_at).endswith("Z")


def test_index_snapshot_is_derived_and_stable() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    run = registered(store, "run-a", clock)
    run.claim(5, activity="Implementing ADR-012 ownership decision")
    run.heartbeat(status=RunStatus.EXECUTING, phase="implementation", pr=130)

    assert run.render_index() == run.render_index()
    assert "do not edit by hand" in run.render_index()
    assert "#5" in run.render_index() and "run-a" in run.render_index()


# ------------------------------------------------------------- legacy transition


def test_legacy_claim_is_visible_and_never_free() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    store.create(
        f"{CLAIM_PREFIX}9",
        {
            "run_id": "run-legacy",
            "ticket": 9,
            "claimed_at": _iso(clock()),
            "expires_at": _iso(clock() + timedelta(minutes=25)),
            "branch": "wingman/issue-9/run-legacy",
            "current_activity": "legacy session writing ADR-007",
            "attempt_number": 1,
        },
    )
    fresh = registered(store, "run-fresh", clock)

    state = fresh.ticket_state(9)
    assert state.legacy is True and state.epoch == 1
    assert fresh.claim(9).outcome is ClaimOutcome.HELD_BY_OTHER

    clock.advance(minutes=26)
    assert fresh.claim(9).outcome is ClaimOutcome.HELD_EXPIRED
    assert fresh.recover(9, inspect="legacy branch inspected").acquired
    assert fresh.claim_of(9).epoch == 2


def test_legacy_run_ref_is_discovered() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    store.create(
        f"{RUN_PREFIX}run-legacy",
        {
            "run_id": "run-legacy",
            "session": 10,
            "ticket": 15,
            "run_status": "EXECUTING",
            "last_heartbeat": _iso(clock()),
            "current_activity": "pushing CI workflow",
            "branch": "wingman/issue-15/ci-workflow",
        },
    )
    observer = registered(store, "run-observer", clock)

    [legacy] = [run for run in observer.runs() if run.run_id == "run-legacy"]
    assert legacy.run_status == "EXECUTING"
    assert legacy.ticket == 15
    assert legacy.seq == 1


def test_claim_and_run_records_round_trip_unknown_fields() -> None:
    claim = Claim.from_payload({"run_id": "run-a", "ticket": 5, "epoch": 2, "expires_at": "x", "future": 1})
    run = Run.from_payload({"run_id": "run-a", "seq": 3, "recorded_at": "x", "future": 1})
    lease = Lease.from_payload({"run_id": "run-a", "ticket": 5, "epoch": 2, "expires_at": "x", "future": 1})
    assert (claim.epoch, run.seq, lease.epoch) == (2, 3, 2)
    assert Claim.from_payload(claim.to_payload()) == claim
    assert Run.from_payload(run.to_payload()) == run


def test_renewing_a_released_claim_reports_lost_not_ownership_error() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    run = registered(store, "run-a", clock)
    run.claim(5)
    run.release(5)

    with pytest.raises(ClaimLost):
        run.renew(5)
