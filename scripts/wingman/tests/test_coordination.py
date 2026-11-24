"""Coordination contract tests.

`InMemoryRefStore` is a genuine second adapter for the ref store port: it enforces
the same compare-and-set contract (one winner per `create`) as GitHub, so the
race behaviour below is exercised by real claim code, not by a mock.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from wingman.coordination import (
    CLAIM_PREFIX,
    RECOVERY_LOCK_PREFIX,
    RUN_PREFIX,
    Claim,
    ClaimOutcome,
    ClaimStatus,
    ClaimUnverified,
    CoordinationError,
    Coordinator,
    InMemoryRefStore,
    NotClaimOwner,
    Run,
    RunStatus,
    _iso,
)

START = datetime(2026, 11, 24, 18, 0, tzinfo=UTC)


class Clock:
    def __init__(self, moment: datetime = START) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, **kwargs: float) -> None:
        self.moment = self.moment + timedelta(**kwargs)


def coordinator(store: InMemoryRefStore, run_id: str, clock: Clock | None = None, lease_minutes: int = 25) -> Coordinator:
    return Coordinator(store, run_id, lease=timedelta(minutes=lease_minutes), clock=clock or Clock())


def registered(store: InMemoryRefStore, run_id: str = "run-a", clock: Clock | None = None) -> Coordinator:
    coord = coordinator(store, run_id, clock)
    coord.register(ticket=None, session=1, branch=f"wingman/issue-5/run-{run_id}", worktree=f"/tmp/{run_id}")
    return coord


def test_claim_is_exclusive_under_concurrent_attempts() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    coordinators = [registered(store, f"run-{index}", clock) for index in range(8)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda c: c.claim(5, activity="implementing ADR-012"), coordinators))

    winners = [result for result in results if result.acquired]
    assert len(winners) == 1
    assert all(result.outcome is ClaimOutcome.HELD_BY_OTHER for result in results if not result.acquired)
    assert {result.claim.run_id for result in results if not result.acquired} == {winners[0].claim.run_id}
    # The registry mirrors exactly one ownership.
    assert [run.ticket for run in coordinators[0].runs() if run.ticket == 5] == [5]
    assert len([claim for claim in coordinators[0].claims() if claim.ticket == 5]) == 1


def test_loser_is_told_who_holds_the_claim_and_keeps_no_ticket_state() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    first = registered(store, "run-first", clock)
    second = registered(store, "run-second", clock)
    first.claim(9, activity="Implementing ADR-007 ownership decision")

    result = second.claim(9, activity="implementing something else")

    assert result.outcome is ClaimOutcome.HELD_BY_OTHER
    assert "run-first" in result.detail
    assert result.claim is not None and result.claim.ticket == 9
    assert second.run().ticket is None
    assert second.run().claim_status == ClaimStatus.NONE


def test_expired_claim_is_not_automatically_free() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    first = registered(store, "run-first", clock)
    second = registered(store, "run-second", clock)
    first.claim(9)
    clock.advance(minutes=26)

    result = second.claim(9)

    assert result.outcome is ClaimOutcome.HELD_EXPIRED
    assert second.claim_of(9).run_id == "run-first"
    assert 9 in second.excluded_tickets()
    assert "recovery required" in second.excluded_tickets()[9]


def test_recovery_takes_over_expired_claim_and_records_provenance() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    stale = registered(store, "run-stale", clock)
    stale.claim(9, activity="Implementing ADR-007")
    store.replace(
        CLAIM_PREFIX + "9",
        {**store.read(CLAIM_PREFIX + "9"), "pr": 119, "branch": "wingman/p0-07-adr-007-shared-recurrence"},
    )
    clock.advance(minutes=41)
    fresh = registered(store, "run-fresh", clock)

    result = fresh.recover(9, branch="wingman/issue-9/run-run-fresh", inspect="PR #119 inspected; ADR draft usable")

    assert result.acquired
    claim = fresh.claim_of(9)
    assert claim.run_id == "run-fresh"
    assert claim.attempt_number == 2
    assert claim.recovery_status == "RECOVERED"
    assert claim.recovered_from == "run-stale"
    assert claim.previous_pr == 119
    assert claim.previous_branch == "wingman/p0-07-adr-007-shared-recurrence"
    assert claim.branch == "wingman/issue-9/run-run-fresh"
    # The stale run's registry entry is closed rather than left looking alive.
    abandoned = next(run for run in fresh.runs() if run.run_id == "run-stale")
    assert abandoned.run_status == RunStatus.ABANDONED


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
    winner = winners[0].claim.run_id
    for loser in (result for result in results if not result.acquired):
        # A loser either collided with the recovery lock or arrived after the
        # takeover completed and saw the new, live claim.
        assert loser.outcome in {ClaimOutcome.RECOVERY_IN_PROGRESS, ClaimOutcome.NOT_EXPIRED}
        assert loser.claim is not None and loser.claim.run_id == winner
    assert store.read(RECOVERY_LOCK_PREFIX + "9") is None


def test_recovery_refuses_a_live_claim() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    registered(store, "run-first", clock).claim(9)
    other = registered(store, "run-second", clock)

    result = other.recover(9)

    assert result.outcome is ClaimOutcome.NOT_EXPIRED
    assert other.claim_of(9).run_id == "run-first"


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


def test_release_frees_the_ticket_and_keeps_run_history() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    first = registered(store, "run-first", clock)
    first.claim(5)
    first.release(5, status=RunStatus.BLOCKED, activity="blocked on missing environment")

    assert first.claim_of(5) is None
    assert first.run().run_status == RunStatus.BLOCKED
    assert first.run().claim_status == ClaimStatus.RELEASED
    second = registered(store, "run-second", clock)
    assert second.claim(5).acquired


def test_heartbeat_renews_lease_and_preserves_last_activity() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    run = registered(store, "run-a", clock)
    run.claim(5, activity="Writing authorization tests for task sharing")
    before = run.claim_of(5)

    clock.advance(minutes=5)
    run.heartbeat()
    after = run.claim_of(5)

    assert after.current_activity == "Writing authorization tests for task sharing"
    assert after.renewed_count == before.renewed_count + 1
    assert after.expires_at > before.expires_at
    assert run.run().current_activity == "Writing authorization tests for task sharing"


def test_registry_records_every_run_without_lost_updates() -> None:
    store = InMemoryRefStore()
    clock = Clock()

    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(lambda index: registered(store, f"run-{index}", clock), range(10)))

    assert len(registered(store, "run-observer", clock).runs()) == 11
    assert len(store.list(RUN_PREFIX)) == 11


def test_discovery_reports_status_activity_branch_and_expiry() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    worker = registered(store, "run-worker", clock)
    worker.claim(15)
    worker.heartbeat(status=RunStatus.EXECUTING, phase="implementation", activity="Validating backend task endpoints", pr=131)
    clock.advance(minutes=3)

    [run] = [run for run in worker.runs() if run.run_id == "run-worker"]
    assert run.run_status == RunStatus.EXECUTING
    assert run.current_activity == "Validating backend task endpoints"
    assert run.pr == 131
    assert run.heartbeat_age(clock()) == 180
    assert run.expired(clock()) is False
    assert run.branch == "wingman/issue-5/run-run-worker"


def test_unverified_claim_is_rejected_before_any_work_begins() -> None:
    class LyingStore(InMemoryRefStore):
        def create(self, ref: str, payload: dict) -> None:
            super().create(ref, {**payload, "run_id": "run-someone-else"})

    store = LyingStore()
    clock = Clock()
    run = registered(store, "run-a", clock)

    with pytest.raises(ClaimUnverified):
        run.claim(5)


def test_mark_run_refuses_to_rewrite_a_live_run() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    registered(store, "run-live", clock)
    observer = registered(store, "run-observer", clock)

    with pytest.raises(CoordinationError):
        observer.mark_run("run-live", RunStatus.ABANDONED)

    clock.advance(minutes=41)
    updated = observer.mark_run("run-live", RunStatus.ABANDONED, activity="stale after 40m")
    assert updated is not None and updated.run_status == RunStatus.ABANDONED


def test_index_snapshot_is_derived_and_stable() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    run = registered(store, "run-a", clock)
    run.claim(5, activity="Implementing ADR-012 ownership decision")
    run.heartbeat(status=RunStatus.EXECUTING, phase="implementation", pr=130)

    first = run.render_index()
    second = run.render_index()

    assert first == second
    assert "do not edit by hand" in first
    assert "#5" in first and "run-a" in first and "#130" in first


def test_claim_and_run_records_round_trip_unknown_fields() -> None:
    claim = Claim.from_payload({"run_id": "run-a", "ticket": 5, "future_field": "ignored"})
    run = Run.from_payload({"run_id": "run-a", "session": 9, "future_field": "ignored"})
    assert claim.ticket == 5 and claim.run_id == "run-a"
    assert run.session == 9
    assert Claim.from_payload(claim.to_payload()) == claim
    assert Run.from_payload(run.to_payload()) == run


def test_expiry_boundary_is_closed() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    run = registered(store, "run-a", clock)
    run.claim(5)
    claim = run.claim_of(5)
    assert claim is not None
    assert claim.expired(datetime.fromisoformat(_iso(clock() + timedelta(minutes=24)))) is False
    assert claim.expired(datetime.fromisoformat(_iso(clock() + timedelta(minutes=25)))) is True
