"""Preflight handshake tests: exclusion, selection, fail-closed claim, isolation.

The workspace tests build a real repository with a real linked worktree — the rule
being enforced ("never work in the primary checkout") is a git fact, not a mock.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta

import pytest
from wingman.coordination import (
    CLAIM_EPOCH_PREFIX,
    Coordinator,
    InMemoryRefStore,
    RunStatus,
)
from wingman.preflight import (
    Handshake,
    HandshakeError,
    Issue,
    StaticIssueSource,
    WorkspaceError,
    exclusion_set,
    select_ticket,
    verify_workspace,
)

START = datetime(2026, 11, 24, 20, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.moment = START

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, **kwargs: float) -> None:
        self.moment = self.moment + timedelta(**kwargs)


BRANCH = "wingman/issue-124/run-run-a"


def coordinator(store, run_id: str = "run-a", clock: Clock | None = None) -> Coordinator:
    return Coordinator(store, run_id, lease=timedelta(minutes=25), clock=clock or Clock())


def handshake(store, source, clock: Clock | None = None, run_id: str = "run-a", worktree: str = "/tmp/wm/run-a") -> Handshake:
    return Handshake(
        coordinator(store, run_id, clock),
        source,
        branch=f"wingman/issue-124/run-{run_id}",
        worktree=worktree,
        session=1,
    )


# ------------------------------------------------------------------- exclusion


def test_blocked_and_verification_labels_are_excluded() -> None:
    store = InMemoryRefStore()
    issues = [
        Issue(5, "blocked work", labels=("blocked",)),
        Issue(6, "delivered, awaiting review", labels=("verification",)),
    ]
    excluded = exclusion_set(issues, StaticIssueSource(issues), coordinator(store), run_id="run-a")
    assert excluded[5] == "labelled blocked"
    assert excluded[6] == "labelled verification"


def test_unsatisfied_dependency_is_excluded_and_satisfied_one_is_not() -> None:
    store = InMemoryRefStore()
    issues = [
        Issue(9, "needs 8", body="Depends on #8"),
        Issue(8, "prerequisite", state="closed"),
        Issue(10, "needs 11", body="Blocked by #11"),
        Issue(11, "still open", body="Depends on #8"),
    ]
    excluded = exclusion_set(issues, StaticIssueSource(issues), coordinator(store), run_id="run-a")
    assert 9 not in excluded
    assert "unsatisfied dependencies [11]" in excluded[10]
    assert 11 not in excluded


def test_open_pr_or_foreign_branch_is_excluded_but_own_branch_is_not() -> None:
    store = InMemoryRefStore()
    issues = [Issue(5, "a"), Issue(6, "b"), Issue(7, "c")]
    source = StaticIssueSource(
        issues,
        prs={5: [130]},
        branches={6: ["wingman/issue-6/run-run-other"], 7: ["wingman/issue-7/run-run-a"]},
    )
    excluded = exclusion_set(issues, source, coordinator(store), run_id="run-a")
    assert "open PR(s) [130]" in excluded[5]
    assert "existing branch(es)" in excluded[6]
    assert 7 not in excluded


def test_live_claim_is_excluded_and_expired_claim_requires_recovery() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    registered = coordinator(store, "run-other", clock)
    registered.register(session=9)
    registered.claim(5)
    clock.advance(minutes=30)
    registered2 = coordinator(store, "run-third", clock)
    registered2.register(session=10)
    registered2.claim(6)

    excluded = exclusion_set([Issue(5, "a"), Issue(6, "b")], StaticIssueSource([Issue(5, "a"), Issue(6, "b")]), coordinator(store, "run-a", clock), run_id="run-a")

    assert "held by run-other" in excluded[5]
    assert "recovery inspection required" in excluded[5]
    assert "held by run-third" in excluded[6]
    assert "recovery" not in excluded[6]


# ------------------------------------------------------------------- selection


def test_selection_prefers_priority_then_unblocking_value() -> None:
    issues = [
        Issue(1, "low", labels=("P3-low",)),
        Issue(2, "normal", labels=("P2-normal",)),
        Issue(3, "critical", labels=("P0-critical",)),
        Issue(4, "unblocker", labels=("P1-high",), body="Depends on #1"),
        Issue(5, "depends on 4", body="Depends on #4"),
        Issue(6, "depends on 4 too", body="Depends on #4"),
    ]
    winner, reason = select_ticket(issues, {})
    assert winner.number == 3
    assert "unblocks 0" in reason


def test_selection_uses_unblocking_value_within_a_priority() -> None:
    issues = [
        Issue(1, "plain", labels=("P1-high",)),
        Issue(2, "unblocker", labels=("P1-high",)),
        Issue(3, "needs 2", body="Depends on #2"),
        Issue(4, "needs 2 as well", body="Depends on #2"),
    ]
    winner, reason = select_ticket(issues, {})
    assert winner.number == 2
    assert "unblocks 2" in reason


def test_selection_is_deterministic_and_reports_empty_backlog() -> None:
    issues = [Issue(9, "a", labels=("P2-normal",)), Issue(3, "b", labels=("P2-normal",))]
    assert select_ticket(issues, {})[0].number == 3
    assert select_ticket(issues, {9: "x", 3: "y"}) == (None, "every open ticket is excluded")


# ------------------------------------------------------------------- handshake


def test_handshake_claims_verifies_and_starts_executing() -> None:
    store = InMemoryRefStore()
    plan = handshake(store, StaticIssueSource([Issue(5, "the work", labels=("P1-high",))])).run(
        activity="implementing the handshake", verify_workspace_isolation=False
    )
    assert plan.ticket == 5
    state = coordinator(store).ticket_state(5)
    assert state.owner == "run-a" and state.epoch == 1
    run = coordinator(store).run()
    assert run.run_status == RunStatus.EXECUTING
    assert run.current_activity == "implementing the handshake"


def test_dry_run_makes_no_claim() -> None:
    store = InMemoryRefStore()
    plan = handshake(store, StaticIssueSource([Issue(5, "x")])).run(dry_run=True)
    assert plan.ticket == 5
    assert store.list_names(CLAIM_EPOCH_PREFIX) == []
    assert coordinator(store).run().run_status == RunStatus.STARTING


def test_lost_claim_race_fails_closed_without_entering_execution() -> None:
    """The winner may appear between the exclusion scan and this run's create."""

    class RaceStore(InMemoryRefStore):
        armed = True

        def create(self, ref: str, payload: dict) -> None:
            if self.armed and "claim-epochs" in ref:
                self.armed = False
                other = coordinator(self, "run-other")
                other.register(session=9)
                other.claim(5)
            super().create(ref, payload)

    store = RaceStore()
    with pytest.raises(HandshakeError, match="claim refused"):
        handshake(store, StaticIssueSource([Issue(5, "x")])).run(verify_workspace_isolation=False)
    assert coordinator(store).run().run_status == RunStatus.STARTING
    assert coordinator(store, "run-other").claim_of(5).run_id == "run-other"


def test_unverified_claim_fails_closed() -> None:
    class LyingStore(InMemoryRefStore):
        def create(self, ref: str, payload: dict) -> None:
            super().create(ref, {**payload, "run_id": "run-imposter"})

    store = LyingStore()
    with pytest.raises(HandshakeError, match="do not implement"):
        handshake(store, StaticIssueSource([Issue(5, "x")])).run(verify_workspace_isolation=False)


def test_excluded_ticket_requested_explicitly_is_refused_before_claiming() -> None:
    store = InMemoryRefStore()
    issues = [Issue(5, "blocked", labels=("blocked",))]
    with pytest.raises(HandshakeError, match="excluded"):
        handshake(store, StaticIssueSource(issues)).run(ticket=5, verify_workspace_isolation=False)
    assert store.list_names(CLAIM_EPOCH_PREFIX) == []


def test_workspace_failure_keeps_the_claim_held_so_nobody_duplicates_the_work() -> None:
    store = InMemoryRefStore()
    hs = handshake(store, StaticIssueSource([Issue(5, "x")]), worktree="/tmp/wm/does-not-exist")
    with pytest.raises(WorkspaceError, match="stays held"):
        hs.run()
    assert coordinator(store).claim_of(5).run_id == "run-a"
    assert coordinator(store).run().run_status != RunStatus.EXECUTING


def test_own_claim_never_produces_a_reconcile_note() -> None:
    store = InMemoryRefStore()
    hs = handshake(store, StaticIssueSource([Issue(5, "x"), Issue(6, "y")]))
    hs.run(activity="working", verify_workspace_isolation=False)

    plan = hs.run(dry_run=True)

    assert [note for note in plan.notes if note.ticket == 5] == []


def test_reconcile_flags_claims_without_runs_and_expired_claims() -> None:
    store = InMemoryRefStore()
    clock = Clock()
    ghost = coordinator(store, "run-ghost", clock)
    ghost.register(session=3)
    ghost.claim(5)
    for ref in store.list_names("refs/wingman/run-events/run-ghost/"):
        store.drop(ref)  # registry entry lost while the claim survives
    expired = coordinator(store, "run-expired", clock)
    expired.register(session=4)
    expired.claim(6)
    clock.advance(minutes=30)

    plan = handshake(store, StaticIssueSource([Issue(5, "a"), Issue(6, "b"), Issue(7, "c")]), clock).run(dry_run=True)

    kinds = {(note.ticket, note.kind) for note in plan.notes}
    assert (5, "CLAIM_WITHOUT_RUN") in kinds
    assert (6, "CLAIM_EXPIRED") in kinds
    assert plan.excluded[5] and plan.excluded[6]


# ------------------------------------------------------------------- workspace


def _git(*args: str, cwd) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.fixture()
def repo(tmp_path):
    primary = tmp_path / "primary"
    primary.mkdir()
    _git("init", "-q", "-b", "main", cwd=primary)
    (primary / "README.md").write_text("x\n")
    _git("add", "-A", cwd=primary)
    _git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "init", cwd=primary)
    linked = tmp_path / "linked"
    _git("worktree", "add", "-q", "-b", BRANCH, str(linked), "main", cwd=primary)
    return primary, linked


def test_primary_checkout_is_rejected(repo) -> None:
    primary, _ = repo
    with pytest.raises(WorkspaceError, match="primary checkout"):
        verify_workspace(str(primary), "main", "run-a")


def test_linked_worktree_on_the_run_branch_is_accepted(repo) -> None:
    _, linked = repo
    verify_workspace(str(linked), BRANCH, "run-a")


def test_worktree_on_the_wrong_branch_is_rejected(repo) -> None:
    _, linked = repo
    with pytest.raises(WorkspaceError, match="expected"):
        verify_workspace(str(linked), "wingman/issue-124/run-other", "run-a")


def test_branch_without_the_run_identity_is_rejected(repo) -> None:
    _, linked = repo
    with pytest.raises(WorkspaceError, match="does not identify run"):
        verify_workspace(str(linked), BRANCH, "run-b")


def test_missing_worktree_is_rejected(tmp_path) -> None:
    with pytest.raises(WorkspaceError, match="does not exist"):
        verify_workspace(str(tmp_path / "nope"), BRANCH, "run-a")
