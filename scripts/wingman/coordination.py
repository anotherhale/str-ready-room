"""WINGMAN multi-session coordination.

The authoritative coordination mechanism is the GitHub repository itself, using
custom git refs. Ref creation is the only compare-and-set primitive available to
every WINGMAN session (regardless of conversation, workspace, branch, or start
time) without introducing new infrastructure: a ref can be created exactly once,
and a concurrent creator gets `422 Reference already exists`.

Layout::

    refs/wingman/runs/<RUN_ID>              one ref per run, written only by its owner
    refs/wingman/claims/issue-<N>           exclusive lease on ticket N
    refs/wingman/locks/recovery-issue-<N>   serialises recovery of an expired claim

Each ref points at an annotated tag whose message is the JSON record below, so a
single read returns both ownership and full run metadata. Per-run refs mean no
two sessions ever need to write the same object, so there is no merge conflict and
no lost update.

Ticket claims are leases, never locks held forever: an expired claim is **not**
free. It must be recovered (inspect branch, commits, PR) before another run may
take it over.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

RUN_PREFIX = "refs/wingman/runs/"
CLAIM_PREFIX = "refs/wingman/claims/issue-"
RECOVERY_LOCK_PREFIX = "refs/wingman/locks/recovery-issue-"

DEFAULT_LEASE = timedelta(minutes=25)
HEARTBEAT_INTERVAL = timedelta(minutes=5)
STALE_AFTER = timedelta(minutes=40)


class RunStatus(StrEnum):
    STARTING = "STARTING"
    RECONCILING = "RECONCILING"
    CLAIMING = "CLAIMING"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    CHECKPOINTING = "CHECKPOINTING"
    WAITING = "WAITING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    ABANDONED = "ABANDONED"
    FAILED = "FAILED"


TERMINAL_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.BLOCKED, RunStatus.ABANDONED, RunStatus.FAILED})


class ClaimStatus(StrEnum):
    NONE = "NONE"
    LEASED = "LEASED"
    RELEASED = "RELEASED"
    RECOVERED = "RECOVERED"
    ABANDONED = "ABANDONED"


class ClaimOutcome(StrEnum):
    ACQUIRED = "ACQUIRED"
    ALREADY_HELD = "ALREADY_HELD"
    HELD_BY_OTHER = "HELD_BY_OTHER"
    HELD_EXPIRED = "HELD_EXPIRED"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    NOT_EXPIRED = "NOT_EXPIRED"


class CoordinationError(RuntimeError):
    """Base class for coordination failures."""


class RefExists(CoordinationError):
    """The ref already exists; the caller lost the compare-and-set race."""


class RefMissing(CoordinationError):
    """The ref does not exist (or was deleted by its owner)."""


class NotRegistered(CoordinationError):
    """This run has no registry entry."""


class NotClaimOwner(CoordinationError):
    """Another run owns the claim; this run may not renew or release it."""


class ClaimLost(CoordinationError):
    """The claim being renewed or released no longer exists."""


class ClaimUnverified(CoordinationError):
    """A claim write succeeded but the read-back did not confirm ownership."""


def utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _payload(record: Any) -> dict[str, Any]:
    return {k: (str(v) if isinstance(v, StrEnum) else v) for k, v in asdict(record).items()}


def _filtered(cls: type, payload: dict[str, Any]) -> dict[str, Any]:
    known = {f.name for f in fields(cls)}
    return {k: v for k, v in payload.items() if k in known}


@dataclass(frozen=True)
class LeaseRecord:
    """Fields shared by a run registry entry and a ticket claim."""

    run_id: str
    branch: str = ""
    worktree: str = ""
    run_status: str = RunStatus.STARTING
    current_phase: str = ""
    current_activity: str = ""
    last_heartbeat: str = ""
    expires_at: str = ""
    attempt_number: int = 1
    latest_checkpoint: str | None = None
    pr: int | None = None
    commit_sha: str | None = None
    recovery_status: str = "none"
    recovered_from: str | None = None
    previous_branch: str | None = None
    previous_pr: int | None = None
    renewed_count: int = 0

    def expired(self, now: datetime) -> bool:
        return bool(self.expires_at) and _parse(self.expires_at) <= now

    def stale(self, now: datetime, threshold: timedelta = STALE_AFTER) -> bool:
        return bool(self.last_heartbeat) and _parse(self.last_heartbeat) <= now - threshold

    def heartbeat_age(self, now: datetime) -> int:
        return int((now - _parse(self.last_heartbeat)).total_seconds()) if self.last_heartbeat else -1

    def to_payload(self) -> dict[str, Any]:
        return _payload(self)


@dataclass(frozen=True)
class Claim(LeaseRecord):
    ticket: int = 0
    claimed_at: str = ""
    claim_status: str = ClaimStatus.LEASED

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Claim:
        return cls(**_filtered(cls, payload))


@dataclass(frozen=True)
class Run(LeaseRecord):
    session: int | None = None
    ticket: int | None = None
    claim_status: str = ClaimStatus.NONE
    started_at: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Run:
        return cls(**_filtered(cls, payload))


@dataclass(frozen=True)
class ClaimResult:
    outcome: ClaimOutcome
    ticket: int
    claim: Claim | None = None
    detail: str = ""

    @property
    def acquired(self) -> bool:
        return self.outcome is ClaimOutcome.ACQUIRED

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": str(self.outcome),
            "ticket": self.ticket,
            "detail": self.detail,
            "claim": _payload(self.claim) if self.claim else None,
        }


class RefStore(Protocol):
    """Compare-and-set storage for refs carrying JSON payloads."""

    def create(self, ref: str, payload: dict[str, Any]) -> None:
        """Create `ref` with `payload`; raise `RefExists` if it already exists."""

    def replace(self, ref: str, payload: dict[str, Any]) -> None:
        """Overwrite `ref`; raise `RefMissing` if it does not exist."""

    def read(self, ref: str) -> dict[str, Any] | None:
        """Return the payload, or `None` when the ref is absent."""

    def delete(self, ref: str) -> bool:
        """Delete `ref`; return whether it existed."""

    def list(self, prefix: str) -> dict[str, dict[str, Any]]:
        """Return `{ref: payload}` for every ref under `prefix`."""


class GitHubRefStore:
    """`RefStore` over the GitHub git-data API."""

    def __init__(
        self,
        repo: str,
        token: str,
        *,
        api_url: str = "https://api.github.com",
        anchor_ref: str = "heads/main",
        timeout: float = 20.0,
    ) -> None:
        self._repo = repo
        self._token = token
        self._api_url = api_url.rstrip("/")
        self._anchor_ref = anchor_ref
        self._timeout = timeout
        self._anchor: str | None = None

    def _call(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self._api_url}/repos/{self._repo}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raw = error.read()
            return error.code, json.loads(raw) if raw else None

    def _anchor_sha(self) -> str:
        if self._anchor is None:
            status, ref = self._call("GET", f"/git/ref/{self._anchor_ref}")
            if status != 200:
                raise CoordinationError(f"cannot resolve anchor ref {self._anchor_ref}: HTTP {status}")
            self._anchor = ref["object"]["sha"]
        return self._anchor

    def _tag_for(self, payload: dict[str, Any], name: str) -> str:
        status, tag = self._call(
            "POST",
            "/git/tags",
            {
                "tag": name,
                "message": json.dumps(payload, indent=2, sort_keys=True),
                "object": self._anchor_sha(),
                "type": "commit",
            },
        )
        if status != 201:
            raise CoordinationError(f"cannot create coordination tag: HTTP {status} {tag}")
        return tag["sha"]

    def _name(self, ref: str) -> str:
        return ref.removeprefix("refs/")

    def _read_by_sha(self, sha: str) -> dict[str, Any]:
        status, tag = self._call("GET", f"/git/tags/{sha}")
        if status != 200:
            raise CoordinationError(f"ref does not carry a coordination payload: HTTP {status}")
        return json.loads(tag["message"])

    def create(self, ref: str, payload: dict[str, Any]) -> None:
        sha = self._tag_for(payload, self._name(ref).replace("/", "-"))
        status, body = self._call("POST", "/git/refs", {"ref": ref, "sha": sha})
        if status in (409, 422):
            raise RefExists(ref)
        if status != 201:
            raise CoordinationError(f"cannot create {ref}: HTTP {status} {body}")

    def replace(self, ref: str, payload: dict[str, Any]) -> None:
        sha = self._tag_for(payload, self._name(ref).replace("/", "-"))
        status, body = self._call("PATCH", f"/git/refs/{self._name(ref)}", {"sha": sha, "force": True})
        if status == 422:
            raise RefMissing(ref)
        if status != 200:
            raise CoordinationError(f"cannot update {ref}: HTTP {status} {body}")

    def read(self, ref: str) -> dict[str, Any] | None:
        status, body = self._call("GET", f"/git/ref/{self._name(ref)}")
        if status == 404:
            return None
        if status != 200:
            raise CoordinationError(f"cannot read {ref}: HTTP {status} {body}")
        return self._read_by_sha(body["object"]["sha"])

    def delete(self, ref: str) -> bool:
        status, body = self._call("DELETE", f"/git/refs/{self._name(ref)}")
        if status in (204, 200):
            return True
        if status == 422:
            return False
        raise CoordinationError(f"cannot delete {ref}: HTTP {status} {body}")

    def list(self, prefix: str) -> dict[str, dict[str, Any]]:
        status, refs = self._call("GET", f"/git/matching-refs/{self._name(prefix)}")
        if status == 404:
            return {}
        if status != 200:
            raise CoordinationError(f"cannot list {prefix}: HTTP {status} {refs}")
        found: dict[str, dict[str, Any]] = {}
        for entry in refs or []:
            # matching-refs is a prefix search: `issue-1` also matches `issue-12`.
            if entry["ref"].startswith(prefix) and not entry["ref"][len(prefix) :].startswith("/"):
                found[entry["ref"]] = self._read_by_sha(entry["object"]["sha"])
        return found


class InMemoryRefStore:
    """Concurrency-safe in-memory `RefStore` (test double and dry-run adapter).

    Implements the same compare-and-set contract as GitHub: `create` succeeds for
    exactly one caller.
    """

    def __init__(self) -> None:
        self._refs: dict[str, dict[str, Any]] = {}
        import threading

        self._lock = threading.Lock()

    def create(self, ref: str, payload: dict[str, Any]) -> None:
        with self._lock:
            if ref in self._refs:
                raise RefExists(ref)
            self._refs[ref] = json.loads(json.dumps(payload))

    def replace(self, ref: str, payload: dict[str, Any]) -> None:
        with self._lock:
            if ref not in self._refs:
                raise RefMissing(ref)
            self._refs[ref] = json.loads(json.dumps(payload))

    def read(self, ref: str) -> dict[str, Any] | None:
        with self._lock:
            payload = self._refs.get(ref)
            return json.loads(json.dumps(payload)) if payload is not None else None

    def delete(self, ref: str) -> bool:
        with self._lock:
            return self._refs.pop(ref, None) is not None

    def list(self, prefix: str) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                ref: json.loads(json.dumps(payload))
                for ref, payload in self._refs.items()
                if ref.startswith(prefix) and not ref[len(prefix) :].startswith("/")
            }

    def drop(self, ref: str) -> None:
        """Remove a ref without the ownership checks (test setup only)."""
        with self._lock:
            self._refs.pop(ref, None)


class Coordinator:
    """Registry and claim operations for one run identity."""

    def __init__(
        self,
        store: RefStore,
        run_id: str,
        *,
        lease: timedelta = DEFAULT_LEASE,
        stale_after: timedelta = STALE_AFTER,
        clock=utcnow,
    ) -> None:
        if not run_id or "/" in run_id:
            raise ValueError("run_id must be a non-empty ref-safe identifier")
        self._store = store
        self.run_id = run_id
        self._lease = lease
        self._stale_after = stale_after
        self._clock = clock

    # ---------------------------------------------------------------- registry

    def register(
        self,
        *,
        ticket: int | None = None,
        session: int | None = None,
        branch: str = "",
        worktree: str = "",
        activity: str = "",
    ) -> Run:
        now = self._clock()
        run = Run(
            run_id=self.run_id,
            session=session,
            ticket=ticket,
            claim_status=ClaimStatus.NONE,
            branch=branch,
            worktree=worktree,
            run_status=RunStatus.STARTING,
            current_phase=RunStatus.STARTING,
            current_activity=activity or "registered; not yet executing",
            started_at=_iso(now),
            last_heartbeat=_iso(now),
            expires_at=_iso(now + self._lease),
        )
        self._store.create(RUN_PREFIX + self.run_id, run.to_payload())
        return run

    def heartbeat(
        self,
        *,
        status: RunStatus | None = None,
        phase: str | None = None,
        activity: str | None = None,
        ticket: int | None = None,
        pr: int | None = None,
        commit: str | None = None,
        checkpoint: str | None = None,
    ) -> Run:
        now = self._clock()
        run = self.run()
        updated = replace(
            run,
            last_heartbeat=_iso(now),
            expires_at=_iso(now + self._lease),
            run_status=str(status or run.run_status),
            current_phase=phase or run.current_phase,
            # An empty activity keeps the previous one: a heartbeat must never
            # erase the last meaningful description of what is being done.
            current_activity=activity or run.current_activity,
            ticket=ticket if ticket is not None else run.ticket,
            pr=pr if pr is not None else run.pr,
            commit_sha=commit or run.commit_sha,
            latest_checkpoint=checkpoint or run.latest_checkpoint,
        )
        self._store.replace(RUN_PREFIX + self.run_id, updated.to_payload())
        claim = self._claim_of(updated.ticket) if updated.ticket else None
        if claim is not None and claim.run_id == self.run_id:
            self._store.replace(
                CLAIM_PREFIX + str(updated.ticket),
                replace(
                    claim,
                    last_heartbeat=updated.last_heartbeat,
                    expires_at=updated.expires_at,
                    current_phase=updated.current_phase,
                    current_activity=updated.current_activity,
                    run_status=updated.run_status,
                    branch=updated.branch or claim.branch,
                    worktree=updated.worktree or claim.worktree,
                    pr=updated.pr,
                    commit_sha=updated.commit_sha,
                    latest_checkpoint=updated.latest_checkpoint,
                    renewed_count=claim.renewed_count + 1,
                ).to_payload(),
            )
        return updated

    def finish(self, status: RunStatus, *, activity: str = "", pr: int | None = None, commit: str | None = None) -> Run:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"{status} is not a terminal run status")
        return self.heartbeat(status=status, phase=str(status), activity=activity, pr=pr, commit=commit)

    def run(self) -> Run:
        payload = self._store.read(RUN_PREFIX + self.run_id)
        if payload is None:
            raise NotRegistered(f"run {self.run_id} is not registered")
        return Run.from_payload(payload)

    def mark_run(self, run_id: str, status: RunStatus, *, activity: str = "", force: bool = False) -> Run | None:
        """Update another run's registry entry — only while it is provably stale."""
        payload = self._store.read(RUN_PREFIX + run_id)
        if payload is None:
            return None
        run = Run.from_payload(payload)
        now = self._clock()
        if not force and run_id != self.run_id and not run.stale(now, self._stale_after):
            raise CoordinationError(f"run {run_id} is not stale; refusing to rewrite its registry entry")
        updated = replace(
            run,
            run_status=str(status),
            current_phase=str(status),
            current_activity=activity or run.current_activity,
            last_heartbeat=run.last_heartbeat,
        )
        self._store.replace(RUN_PREFIX + run_id, updated.to_payload())
        return updated

    def runs(self) -> list[Run]:
        return [Run.from_payload(p) for _, p in sorted(self._store.list(RUN_PREFIX).items())]

    # ------------------------------------------------------------------ claims

    def _claim_ref(self, ticket: int) -> str:
        return f"{CLAIM_PREFIX}{ticket}"

    def _claim_of(self, ticket: int | None) -> Claim | None:
        if ticket is None:
            return None
        payload = self._store.read(self._claim_ref(ticket))
        return Claim.from_payload(payload) if payload else None

    def claim_of(self, ticket: int) -> Claim | None:
        return self._claim_of(ticket)

    def claims(self) -> list[Claim]:
        return [Claim.from_payload(p) for _, p in sorted(self._store.list(CLAIM_PREFIX).items())]

    def claim(self, ticket: int, *, branch: str = "", worktree: str = "", activity: str = "") -> ClaimResult:
        now = self._clock()
        run = self.run()
        record = Claim(
            run_id=self.run_id,
            ticket=ticket,
            branch=branch or run.branch,
            worktree=worktree or run.worktree,
            run_status=RunStatus.CLAIMING,
            current_phase="claiming",
            current_activity=activity or f"claiming ticket #{ticket}",
            claimed_at=_iso(now),
            last_heartbeat=_iso(now),
            expires_at=_iso(now + self._lease),
            attempt_number=max(1, run.attempt_number),
            claim_status=ClaimStatus.LEASED,
        )
        try:
            self._store.create(self._claim_ref(ticket), record.to_payload())
        except RefExists:
            holder = self._claim_of(ticket)
            if holder is None:
                # The holder released between our create and our read; retry once.
                try:
                    self._store.create(self._claim_ref(ticket), record.to_payload())
                except RefExists:
                    holder = self._claim_of(ticket)
                    return self._claim_conflict(ticket, holder, now)
                return self._confirm(ticket, now, run)
            return self._claim_conflict(ticket, holder, now)
        return self._confirm(ticket, now, run)

    def _claim_conflict(self, ticket: int, holder: Claim | None, now: datetime) -> ClaimResult:
        if holder is None:
            return ClaimResult(ClaimOutcome.HELD_BY_OTHER, ticket, None, "claim vanished during verification; treat as held")
        if holder.run_id == self.run_id:
            return ClaimResult(ClaimOutcome.ALREADY_HELD, ticket, holder, "already held by this run")
        if holder.expired(now):
            return ClaimResult(
                ClaimOutcome.HELD_EXPIRED,
                ticket,
                holder,
                f"expired claim held by {holder.run_id} (last heartbeat {holder.last_heartbeat}); "
                "recovery inspection required before takeover",
            )
        return ClaimResult(
            ClaimOutcome.HELD_BY_OTHER,
            ticket,
            holder,
            f"held by {holder.run_id} until {holder.expires_at}: {holder.current_activity}",
        )

    def _confirm(self, ticket: int, now: datetime, run: Run) -> ClaimResult:
        held = self._claim_of(ticket)
        if held is None or held.run_id != self.run_id:
            raise ClaimUnverified(f"claim on #{ticket} was not confirmed for {self.run_id}")
        self._store.replace(
            RUN_PREFIX + self.run_id,
            replace(
                run,
                ticket=ticket,
                claim_status=ClaimStatus.LEASED,
                run_status=RunStatus.CLAIMING,
                current_phase="claiming",
                current_activity=held.current_activity,
                last_heartbeat=_iso(now),
                expires_at=held.expires_at,
            ).to_payload(),
        )
        return ClaimResult(ClaimOutcome.ACQUIRED, ticket, held, "claim acquired and verified")

    def renew(
        self,
        ticket: int,
        *,
        activity: str | None = None,
        phase: str | None = None,
        status: RunStatus | None = None,
        pr: int | None = None,
        commit: str | None = None,
    ) -> Claim:
        now = self._clock()
        claim = self._claim_of(ticket)
        if claim is None:
            raise ClaimLost(f"no claim on #{ticket}; stop modifying the ticket and checkpoint")
        if claim.run_id != self.run_id:
            raise NotClaimOwner(f"#{ticket} is held by {claim.run_id}; {self.run_id} may not renew it")
        updated = replace(
            claim,
            last_heartbeat=_iso(now),
            expires_at=_iso(now + self._lease),
            renewed_count=claim.renewed_count + 1,
            current_activity=activity or claim.current_activity,
            current_phase=phase or claim.current_phase,
            run_status=str(status or claim.run_status),
            pr=pr if pr is not None else claim.pr,
            commit_sha=commit or claim.commit_sha,
        )
        self._store.replace(self._claim_ref(ticket), updated.to_payload())
        self.heartbeat(
            status=status,
            phase=phase,
            activity=activity,
            ticket=ticket,
            pr=pr,
            commit=commit,
        )
        return updated

    def release(
        self,
        ticket: int,
        *,
        status: RunStatus = RunStatus.COMPLETED,
        activity: str = "",
        pr: int | None = None,
        commit: str | None = None,
    ) -> Run:
        claim = self._claim_of(ticket)
        if claim is not None and claim.run_id != self.run_id:
            raise NotClaimOwner(f"#{ticket} is held by {claim.run_id}; {self.run_id} may not release it")
        self._store.delete(self._claim_ref(ticket))
        run = self.heartbeat(
            status=status,
            phase=str(status),
            activity=activity or f"claim on #{ticket} released ({status})",
            pr=pr,
            commit=commit,
        )
        updated = replace(run, claim_status=ClaimStatus.RELEASED)
        self._store.replace(RUN_PREFIX + self.run_id, updated.to_payload())
        return updated

    def recover(
        self,
        ticket: int,
        *,
        branch: str = "",
        worktree: str = "",
        activity: str = "",
        inspect: str = "",
    ) -> ClaimResult:
        """Take over an expired claim, after the caller has inspected the old work.

        `inspect` records what was inspected (branch, commits, PR), so the takeover
        is auditable rather than a blind reassignment.
        """
        now = self._clock()
        lock = f"{RECOVERY_LOCK_PREFIX}{ticket}"
        try:
            self._store.create(
                lock,
                {
                    "run_id": self.run_id,
                    "ticket": ticket,
                    "started_at": _iso(now),
                    "expires_at": _iso(now + self._lease),
                },
            )
        except RefExists:
            holder = self._store.read(lock) or {}
            return ClaimResult(
                ClaimOutcome.RECOVERY_IN_PROGRESS,
                ticket,
                self._claim_of(ticket),
                f"recovery of #{ticket} already in progress by {holder.get('run_id', 'unknown')}",
            )
        try:
            holder = self._claim_of(ticket)
            if holder is None:
                result = self.claim(ticket, branch=branch, worktree=worktree, activity=activity)
            elif holder.run_id == self.run_id:
                result = ClaimResult(ClaimOutcome.ALREADY_HELD, ticket, holder, "already held by this run")
            elif not holder.expired(now):
                result = ClaimResult(
                    ClaimOutcome.NOT_EXPIRED,
                    ticket,
                    holder,
                    f"claim held by {holder.run_id} until {holder.expires_at}; nothing to recover",
                )
            else:
                self.mark_run(
                    holder.run_id,
                    RunStatus.ABANDONED,
                    activity=f"abandoned; ticket #{ticket} recovered by {self.run_id}",
                )
                recovered = replace(
                    holder,
                    run_id=self.run_id,
                    branch=branch or holder.branch,
                    worktree=worktree or holder.worktree,
                    run_status=RunStatus.RECOVERING,
                    current_phase="recovery",
                    current_activity=activity or f"recovering ticket #{ticket} from {holder.run_id}",
                    claimed_at=_iso(now),
                    last_heartbeat=_iso(now),
                    expires_at=_iso(now + self._lease),
                    attempt_number=holder.attempt_number + 1,
                    recovery_status="RECOVERED",
                    recovered_from=holder.run_id,
                    previous_branch=holder.branch,
                    previous_pr=holder.pr,
                    renewed_count=0,
                    claim_status=ClaimStatus.RECOVERED,
                )
                self._store.replace(self._claim_ref(ticket), recovered.to_payload())
                run = self.run()
                self._store.replace(
                    RUN_PREFIX + self.run_id,
                    replace(
                        run,
                        ticket=ticket,
                        claim_status=ClaimStatus.RECOVERED,
                        branch=recovered.branch,
                        worktree=recovered.worktree,
                        run_status=RunStatus.RECOVERING,
                        current_phase="recovery",
                        current_activity=recovered.current_activity,
                        attempt_number=recovered.attempt_number,
                        recovery_status="RECOVERED",
                        recovered_from=holder.run_id,
                        previous_branch=holder.branch,
                        previous_pr=holder.pr,
                        last_heartbeat=_iso(now),
                        expires_at=recovered.expires_at,
                    ).to_payload(),
                )
                result = ClaimResult(
                    ClaimOutcome.ACQUIRED,
                    ticket,
                    recovered,
                    f"recovered from {holder.run_id}"
                    + (f" ({inspect})" if inspect else "")
                    + (f"; previous PR #{holder.pr}" if holder.pr else "")
                    + (f"; previous branch {holder.branch}" if holder.branch else ""),
                )
            return result
        finally:
            self._store.delete(lock)

    # ------------------------------------------------------------------- views

    def excluded_tickets(self) -> dict[int, str]:
        """Tickets a run must not select: live claims *and* expired claims awaiting recovery."""
        now = self._clock()
        excluded: dict[int, str] = {}
        for claim in self.claims():
            state = "expired claim, recovery required" if claim.expired(now) else "claimed"
            excluded[claim.ticket] = f"#{claim.ticket} {state}: held by {claim.run_id} ({claim.current_activity})"
        return excluded

    def render_index(self, *, now: datetime | None = None) -> str:
        moment = now or self._clock()
        runs = self.runs()
        lines = [
            "<!-- generated by `python3 -m wingman.coordination index`; do not edit by hand -->",
            "",
            f"# WINGMAN run registry ({_iso(moment)})",
            "",
            "Authoritative source: `refs/wingman/runs/*` and `refs/wingman/claims/issue-*` on GitHub.",
            "This file is a derived snapshot; regenerate it instead of editing it.",
            "",
            "| Run | Ticket | Status | Activity | Branch | PR | Heartbeat | Expires |",
            "|---|---|---|---|---|---|---|---|",
        ]
        if not runs:
            lines.append("| — | — | — | no registered runs | — | — | — | — |")
        for run in sorted(runs, key=lambda r: r.started_at):
            health = "expired" if run.expired(moment) else ("stale" if run.stale(moment, self._stale_after) else "live")
            lines.append(
                "| {run} | {ticket} | {status} ({health}) | {activity} | {branch} | {pr} | {hb}m ago | {exp} |".format(
                    run=run.run_id,
                    ticket=f"#{run.ticket}" if run.ticket else "—",
                    status=run.run_status,
                    health=health,
                    activity=run.current_activity.replace("|", "/"),
                    branch=run.branch or "—",
                    pr=f"#{run.pr}" if run.pr else "—",
                    hb=max(0, run.heartbeat_age(moment)) // 60,
                    exp=run.expires_at or "—",
                )
            )
        claims = self.claims()
        lines += ["", "## Ticket claims", "", "| Ticket | Held by | Status | Activity | Expires | Attempt |", "|---|---|---|---|---|---|"]
        if not claims:
            lines.append("| — | — | — | no active claims | — | — |")
        for claim in sorted(claims, key=lambda c: c.ticket):
            lines.append(
                "| #{ticket} | {run} | {status} | {activity} | {expires} | {attempt} |".format(
                    ticket=claim.ticket,
                    run=claim.run_id,
                    status="EXPIRED" if claim.expired(moment) else claim.claim_status,
                    activity=claim.current_activity.replace("|", "/"),
                    expires=claim.expires_at or "—",
                    attempt=claim.attempt_number,
                )
            )
        return "\n".join(lines) + "\n"


def build_store(repo: str, token: str) -> GitHubRefStore:
    return GitHubRefStore(repo, token)


def _store_from_args(args: argparse.Namespace) -> GitHubRefStore:
    token = os.environ.get(args.token_env, "")
    if not token:
        raise SystemExit(f"{args.token_env} is not set; coordination requires repository write access")
    return build_store(args.repo, token)


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wingman.coordination", description="WINGMAN run registry and ticket claims")
    parser.add_argument("--repo", default=os.environ.get("READY_ROOM_WINGMAN_REPO", "anotherhale/str-ready-room"))
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--run-id", default=os.environ.get("WINGMAN_RUN_ID", ""))
    parser.add_argument("--lease-minutes", type=int, default=int(DEFAULT_LEASE.total_seconds() // 60))
    sub = parser.add_subparsers(dest="command", required=True)

    register = sub.add_parser("register", help="register this run in the shared registry")
    register.add_argument("--ticket", type=int)
    register.add_argument("--session", type=int)
    register.add_argument("--branch", default="")
    register.add_argument("--worktree", default="")
    register.add_argument("--activity", default="")

    beat = sub.add_parser("heartbeat", help="renew this run's lease and record activity")
    beat.add_argument("--status", choices=[str(s) for s in RunStatus])
    beat.add_argument("--phase")
    beat.add_argument("--activity")
    beat.add_argument("--pr", type=int)
    beat.add_argument("--commit")
    beat.add_argument("--checkpoint")

    for name, help_text in (("claim", "acquire an exclusive claim"), ("renew", "renew a held claim"), ("release", "release a held claim"), ("recover", "take over an expired claim after inspection")):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("ticket", type=int)
        command.add_argument("--activity", default="")
        if name == "recover":
            command.add_argument("--branch", default="")
            command.add_argument("--worktree", default="")
            command.add_argument("--inspect", default="")
        if name == "release":
            command.add_argument("--status", default=str(RunStatus.COMPLETED), choices=[str(s) for s in RunStatus])
            command.add_argument("--pr", type=int)
            command.add_argument("--commit")
        if name == "renew" or name == "claim":
            command.add_argument("--branch", default="")
            command.add_argument("--worktree", default="")
        if name == "renew":
            command.add_argument("--status", choices=[str(s) for s in RunStatus])
            command.add_argument("--phase")
            command.add_argument("--pr", type=int)
            command.add_argument("--commit")

    sub.add_parser("status", help="print the registry and claims")
    index = sub.add_parser("index", help="render the derived registry snapshot")
    index.add_argument("--out", default="docs/WINGMAN/RUNS.md")

    args = parser.parse_args(argv)
    coordinator = Coordinator(_store_from_args(args), args.run_id, lease=timedelta(minutes=args.lease_minutes))

    if args.command == "register":
        _print(_payload(coordinator.register(ticket=args.ticket, session=args.session, branch=args.branch, worktree=args.worktree, activity=args.activity)))
    elif args.command == "heartbeat":
        _print(
            _payload(
                coordinator.heartbeat(
                    status=args.status,
                    phase=args.phase,
                    activity=args.activity,
                    pr=args.pr,
                    commit=args.commit,
                    checkpoint=args.checkpoint,
                )
            )
        )
    elif args.command == "claim":
        result = coordinator.claim(args.ticket, branch=args.branch, worktree=args.worktree, activity=args.activity)
        _print(result.to_dict())
        return 0 if result.acquired else 3
    elif args.command == "renew":
        _print(_payload(coordinator.renew(args.ticket, activity=args.activity, phase=args.phase, status=args.status, pr=args.pr, commit=args.commit)))
    elif args.command == "release":
        _print(_payload(coordinator.release(args.ticket, status=args.status, activity=args.activity, pr=args.pr, commit=args.commit)))
    elif args.command == "recover":
        result = coordinator.recover(args.ticket, branch=args.branch, worktree=args.worktree, activity=args.activity, inspect=args.inspect)
        _print(result.to_dict())
        return 0 if result.acquired else 3
    elif args.command == "status":
        now = utcnow()
        _print(
            {
                "generated_at": _iso(now),
                "runs": [
                    {**_payload(run), "health": "expired" if run.expired(now) else ("stale" if run.stale(now) else "live")}
                    for run in coordinator.runs()
                ],
                "claims": [{**_payload(claim), "expired": claim.expired(now)} for claim in coordinator.claims()],
                "excluded_tickets": coordinator.excluded_tickets(),
            }
        )
    elif args.command == "index":
        text = coordinator.render_index()
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
