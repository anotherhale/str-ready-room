"""WINGMAN multi-session coordination on immutable git refs.

Why immutable refs: GitHub's only atomic write is *creating* a ref
(`POST /git/refs` succeeds once; a second creator gets `422`). Updating a ref is
last-writer-wins, and conditional requests are refused outright —
`400 Conditional request headers are not allowed in unsafe requests` — verified
live, not assumed. So no coordination fact is ever mutated: every fact is a
create-only ref with a deterministic name, and current state is *derived* from the
set of refs.

    refs/wingman/runs/<RUN_ID>/e<N>                      run event N (owner-only, N monotonic)
    refs/wingman/claims/issue-<T>/e<K>                   claim epoch K (deterministic name => CAS)
    refs/wingman/leases/issue-<T>/e<K>/<RUN_ID>-<n>      renewal inside epoch K
    refs/wingman/releases/issue-<T>/e<K>                 release of epoch K (create-only, idempotent)
    refs/wingman/recoveries/issue-<T>/e<K>/<RUN_ID>-<n>  advisory recovery intent (never a lock)
    refs/wingman/observations/<RUN_ID>/<TARGET>-<n>      observation about another run (never mutates it)

Consequences pinned by tests:

* Competing claims target the *same* `e<K>` name, so exactly one create wins.
* A superseded owner cannot clobber the new owner: its writes land in epoch K's
  namespace and the derived state only reads epoch K+1.
* A stale observer cannot overwrite a resumed run: observations live in the
  observer's own namespace and are advisory.
* Partial failures are fail-closed: a missing lease can only make a claim look
  expired (which still requires recovery inspection), never available.
* The mutable layout from PR #129 (`runs/<RUN_ID>`, `claims/issue-<N>`) is still
  read as sequence/epoch 1 so the transition is safe, and is never treated as free.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

# The pre-hardening layout (PR #129) is still read: `runs/<RUN_ID>` and
# `claims/issue-<T>` are legacy *leaves*. Git forbids a ref being both a leaf and a
# directory, so the append-only layout must live in disjoint namespaces.
RUN_PREFIX = "refs/wingman/runs/"
RUN_EVENT_PREFIX = "refs/wingman/run-events/"
CLAIM_PREFIX = "refs/wingman/claims/issue-"
CLAIM_EPOCH_PREFIX = "refs/wingman/claim-epochs/issue-"
LEASE_PREFIX = "refs/wingman/leases/issue-"
RELEASE_PREFIX = "refs/wingman/releases/issue-"
RECOVERY_INTENT_PREFIX = "refs/wingman/recoveries/issue-"
OBSERVATION_PREFIX = "refs/wingman/observations/"

DEFAULT_LEASE = timedelta(minutes=25)
STALE_AFTER = timedelta(minutes=40)
HEARTBEAT_INTERVAL = timedelta(minutes=5)
MAX_APPEND_ATTEMPTS = 3
LEGACY_EPOCH = 1


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
    """The ref already exists; the caller lost the create race."""


class NotRegistered(CoordinationError):
    """This run has no registry entry."""


class NotClaimOwner(CoordinationError):
    """Another run owns the current claim epoch; this run may not act on it."""


class ClaimSuperseded(NotClaimOwner):
    """This run's epoch was taken over; it must stop modifying the ticket."""


class ClaimLost(CoordinationError):
    """There is no claim to renew or release."""


class ClaimUnverified(CoordinationError):
    """A create returned success but the read-back did not confirm it."""


class StoreError(CoordinationError):
    """The ref store could not be read or written."""


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


def _epoch_from(ref: str, prefix: str) -> int | None:
    """Parse `e<K>` from `.../e<K>` or `.../e<K>/<child>`; None when not epoch scoped."""
    suffix = ref[len(prefix) :].split("/", 1)[0]
    if not suffix.startswith("e"):
        return None
    try:
        return int(suffix[1:])
    except ValueError:
        return None


@dataclass(frozen=True)
class Run:
    """Immutable snapshot of a run at sequence `seq`."""

    run_id: str
    seq: int
    recorded_at: str = ""
    session: int | None = None
    ticket: int | None = None
    run_status: str = RunStatus.STARTING
    claim_status: str = ClaimStatus.NONE
    epoch: int | None = None
    branch: str = ""
    worktree: str = ""
    started_at: str = ""
    current_phase: str = ""
    current_activity: str = ""
    pr: int | None = None
    commit_sha: str | None = None
    latest_checkpoint: str | None = None
    attempt_number: int = 1
    recovery_status: str = "none"
    recovered_from: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Run:
        return cls(**_filtered(cls, payload))

    @classmethod
    def from_legacy(cls, payload: dict[str, Any], run_id: str) -> Run:
        return cls(
            run_id=payload.get("run_id", run_id),
            seq=1,
            recorded_at=payload.get("last_heartbeat") or payload.get("started_at") or _iso(utcnow()),
            session=payload.get("session"),
            ticket=payload.get("ticket"),
            run_status=payload.get("run_status", RunStatus.STARTING),
            claim_status=payload.get("claim_status", ClaimStatus.NONE),
            branch=payload.get("branch", ""),
            worktree=payload.get("worktree", ""),
            started_at=payload.get("started_at", ""),
            current_phase=payload.get("current_phase", ""),
            current_activity=payload.get("current_activity", ""),
            pr=payload.get("pr"),
            commit_sha=payload.get("commit_sha"),
            latest_checkpoint=payload.get("latest_checkpoint"),
            attempt_number=payload.get("attempt_number", 1),
            recovery_status=payload.get("recovery_status", "none"),
            recovered_from=payload.get("recovered_from"),
        )


    def to_payload(self) -> dict[str, Any]:
        return _payload(self)

    def heartbeat_age(self, now: datetime) -> int:
        return int((now - _parse(self.recorded_at)).total_seconds())


@dataclass(frozen=True)
class Claim:
    """A claim epoch. The ref name is deterministic, so creating it *is* the CAS."""

    run_id: str
    ticket: int
    epoch: int
    claimed_at: str = ""
    expires_at: str = ""
    branch: str = ""
    worktree: str = ""
    current_activity: str = ""
    attempt_number: int = 1
    recovery_status: str = "none"
    recovered_from: str | None = None
    previous_branch: str | None = None
    previous_pr: int | None = None
    inspection: str | None = None
    pr: int | None = None
    commit_sha: str | None = None
    latest_checkpoint: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Claim:
        return cls(**_filtered(cls, payload))

    @classmethod
    def from_legacy(cls, payload: dict[str, Any], ticket: int) -> Claim:
        return cls(
            run_id=payload["run_id"],
            ticket=ticket,
            epoch=LEGACY_EPOCH,
            claimed_at=payload.get("claimed_at") or payload.get("last_heartbeat") or _iso(utcnow()),
            expires_at=payload.get("expires_at") or _iso(utcnow()),
            branch=payload.get("branch", ""),
            worktree=payload.get("worktree", ""),
            current_activity=payload.get("current_activity", ""),
            attempt_number=payload.get("attempt_number", 1),
            recovery_status=payload.get("recovery_status", "none"),
            recovered_from=payload.get("recovered_from"),
            previous_branch=payload.get("previous_branch"),
            previous_pr=payload.get("previous_pr"),
            pr=payload.get("pr"),
            commit_sha=payload.get("commit_sha"),
            latest_checkpoint=payload.get("latest_checkpoint"),
        )


    def to_payload(self) -> dict[str, Any]:
        return _payload(self)

    def expired(self, now: datetime) -> bool:
        return _parse(self.expires_at) <= now


@dataclass(frozen=True)
class Lease:
    """A renewal inside one claim epoch. Only that epoch's owner writes these."""

    run_id: str
    ticket: int
    epoch: int
    renewed_at: str = ""
    expires_at: str = ""
    current_activity: str = ""
    phase: str = ""
    run_status: str = ""
    pr: int | None = None
    commit_sha: str | None = None
    latest_checkpoint: str | None = None
    renewed_count: int = 0

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Lease:
        return cls(**_filtered(cls, payload))

    def expired(self, now: datetime) -> bool:
        return _parse(self.expires_at) <= now

    def to_payload(self) -> dict[str, Any]:
        return _payload(self)


@dataclass(frozen=True)
class TicketState:
    """Derived ownership state of a ticket — never stored, always computed."""

    ticket: int
    epoch: int
    claim: Claim | None
    last_claim: Claim | None
    released_at: str | None
    expires_at: str | None
    leases: list[Lease] = field(default_factory=list)
    recovery_intents: list[dict[str, Any]] = field(default_factory=list)
    legacy: bool = False

    def expired(self, now: datetime) -> bool:
        return self.claim is not None and self.expires_at is not None and _parse(self.expires_at) <= now

    def held(self, now: datetime) -> bool:
        return self.claim is not None and not self.expired(now)

    @property
    def available(self) -> bool:
        return self.claim is None

    @property
    def owner(self) -> str | None:
        return self.claim.run_id if self.claim else None

    def describe(self, now: datetime) -> str:
        if self.claim is None:
            return f"#{self.ticket} available (epoch {self.epoch})"
        if self.expired(now):
            return (
                f"#{self.ticket} expired claim held by {self.claim.run_id} "
                f"(expired {self.expires_at}); recovery inspection required"
            )
        return f"#{self.ticket} held by {self.claim.run_id} until {self.expires_at}: {self.claim.current_activity}"


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
    """Create-only storage for refs carrying JSON payloads.

    There is deliberately no `replace`: a mutable write cannot be made safe on
    this platform (no conditional update, no server-side precondition), so the
    port does not offer one.
    """

    def create(self, ref: str, payload: dict[str, Any]) -> None:
        """Create `ref` with `payload`; raise `RefExists` if it already exists."""

    def read(self, ref: str) -> dict[str, Any] | None:
        """Return the payload, or `None` when the ref is absent."""

    def delete(self, ref: str) -> bool:
        """Delete `ref`; return whether it existed."""

    def list_names(self, prefix: str) -> list[str]:
        """Return every ref name under `prefix`, without reading payloads."""

    def list(self, prefix: str) -> dict[str, dict[str, Any]]:
        """Return `{ref: payload}` for every ref under `prefix`."""


class GitHubRefStore:
    """`RefStore` over the GitHub git-data API (create/read/delete/list only)."""

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
                raise StoreError(f"cannot resolve anchor ref {self._anchor_ref}: HTTP {status}")
            self._anchor = ref["object"]["sha"]
        return self._anchor

    def _anchor_tag(self, payload: dict[str, Any], name: str) -> str:
        status, tag = self._call(
            "POST",
            "/git/tags",
            {
                "tag": name[:100],
                "message": json.dumps(payload, indent=2, sort_keys=True),
                "object": self._anchor_sha(),
                "type": "commit",
            },
        )
        if status != 201:
            raise StoreError(f"cannot create coordination tag: HTTP {status} {tag}")
        return tag["sha"]

    @staticmethod
    def _name(ref: str) -> str:
        return ref.removeprefix("refs/")

    def create(self, ref: str, payload: dict[str, Any]) -> None:
        sha = self._anchor_tag(payload, self._name(ref).replace("/", "-"))
        status, body = self._call("POST", "/git/refs", {"ref": ref, "sha": sha})
        if status in (409, 422):
            raise RefExists(ref)
        if status != 201:
            raise StoreError(f"cannot create {ref}: HTTP {status} {body}")

    def read(self, ref: str) -> dict[str, Any] | None:
        status, body = self._call("GET", f"/git/ref/{self._name(ref)}")
        if status == 404:
            return None
        if status != 200:
            raise StoreError(f"cannot read {ref}: HTTP {status} {body}")
        return self._read_tag(body["object"]["sha"])

    def _read_tag(self, sha: str) -> dict[str, Any]:
        status, tag = self._call("GET", f"/git/tags/{sha}")
        if status != 200:
            raise StoreError(f"ref does not carry a coordination payload: HTTP {status}")
        return json.loads(tag["message"])

    def delete(self, ref: str) -> bool:
        status, body = self._call("DELETE", f"/git/refs/{self._name(ref)}")
        if status in (200, 204):
            return True
        if status == 422:
            return False
        raise StoreError(f"cannot delete {ref}: HTTP {status} {body}")

    def list_names(self, prefix: str) -> list[str]:
        status, refs = self._call("GET", f"/git/matching-refs/{self._name(prefix)}")
        if status == 404:
            return []
        if status != 200:
            raise StoreError(f"cannot list {prefix}: HTTP {status} {refs}")
        return sorted(entry["ref"] for entry in refs or [] if entry["ref"].startswith(prefix))

    def list(self, prefix: str) -> dict[str, dict[str, Any]]:
        return {ref: payload for ref in self.list_names(prefix) if (payload := self.read(ref)) is not None}


class InMemoryRefStore:
    """Concurrency-safe in-memory `RefStore` with the same create-only contract."""

    def __init__(self) -> None:
        self._refs: dict[str, dict[str, Any]] = {}
        import threading

        self._lock = threading.Lock()

    def create(self, ref: str, payload: dict[str, Any]) -> None:
        with self._lock:
            if ref in self._refs:
                raise RefExists(ref)
            self._refs[ref] = json.loads(json.dumps(payload))

    def read(self, ref: str) -> dict[str, Any] | None:
        with self._lock:
            payload = self._refs.get(ref)
            return json.loads(json.dumps(payload)) if payload is not None else None

    def delete(self, ref: str) -> bool:
        with self._lock:
            return self._refs.pop(ref, None) is not None

    def list_names(self, prefix: str) -> list[str]:
        with self._lock:
            return sorted(ref for ref in self._refs if ref.startswith(prefix))

    def list(self, prefix: str) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                ref: json.loads(json.dumps(payload))
                for ref, payload in sorted(self._refs.items())
                if ref.startswith(prefix)
            }

    def drop(self, ref: str) -> None:
        """Remove a ref without ownership checks (test setup only)."""
        with self._lock:
            self._refs.pop(ref, None)


class Coordinator:
    """Registry and claim lifecycle for one run identity."""

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
        if self._latest_run(self.run_id) is not None:
            return self.run()
        now = self._clock()
        return self._append_run(
            session=session,
            ticket=ticket,
            branch=branch,
            worktree=worktree,
            run_status=str(RunStatus.STARTING),
            phase=str(RunStatus.STARTING),
            activity=activity or "registered; not yet executing",
            started_at=_iso(now),
        )

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
        run = self.run()
        ticket = ticket if ticket is not None else run.ticket
        state = self._ticket_state(ticket) if ticket else None
        # Lease first: the lease is the safety-critical fact. If the run event
        # below fails, the claim still looks live and can never look available.
        if state is not None and state.claim is not None and state.claim.run_id == self.run_id:
            self._append_lease(
                state,
                activity=activity,
                phase=phase,
                status=status,
                pr=pr,
                commit=commit,
                checkpoint=checkpoint,
            )
        return self._append_run(
            status=status,
            phase=phase,
            activity=activity,
            ticket=ticket,
            pr=pr,
            commit=commit,
            checkpoint=checkpoint,
        )

    def finish(self, status: RunStatus, *, activity: str = "", pr: int | None = None, commit: str | None = None) -> Run:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"{status} is not a terminal run status")
        return self.heartbeat(status=status, phase=str(status), activity=activity, pr=pr, commit=commit)

    def run(self) -> Run:
        run = self._latest_run(self.run_id)
        if run is None:
            raise NotRegistered(f"run {self.run_id} is not registered")
        return run

    def run_events(self, run_id: str | None = None) -> list[Run]:
        run_id = run_id or self.run_id
        prefix = f"{RUN_EVENT_PREFIX}{run_id}/"
        events: list[Run] = []
        for ref in self._store.list_names(prefix):
            if not ref[len(prefix) :].startswith("e"):
                continue
            payload = self._store.read(ref)
            if payload:
                events.append(Run.from_payload(payload))
        return sorted(events, key=lambda event: event.seq)

    def runs(self) -> list[Run]:
        """Latest event per run, selected by ref name (one payload read per run)."""
        best: dict[str, tuple[int, str]] = {}
        for prefix, is_event in ((RUN_EVENT_PREFIX, True), (RUN_PREFIX, False)):
            for ref in self._store.list_names(prefix):
                suffix = ref[len(prefix) :]
                if is_event:
                    run_id, _, seq_text = suffix.partition("/e")
                    try:
                        seq = int(seq_text)
                    except ValueError:
                        continue
                else:
                    run_id, seq = suffix, 0
                if run_id not in best or seq > best[run_id][0]:
                    best[run_id] = (seq, ref)
        runs: list[Run] = []
        for run_id in sorted(best):
            seq, ref = best[run_id]
            payload = self._store.read(ref)
            if not payload:
                continue
            runs.append(Run.from_payload(payload) if seq else Run.from_legacy(payload, run_id))
        return runs

    def _latest_run(self, run_id: str) -> Run | None:
        prefix = f"{RUN_EVENT_PREFIX}{run_id}/"
        best: tuple[int, str] | None = None
        for ref in self._store.list_names(prefix):
            suffix = ref[len(prefix) :]
            if not suffix.startswith("e"):
                continue
            try:
                seq = int(suffix[1:])
            except ValueError:
                continue
            if best is None or seq > best[0]:
                best = (seq, ref)
        if best is not None:
            payload = self._store.read(best[1])
            return Run.from_payload(payload) if payload else None
        legacy = self._store.read(RUN_PREFIX + run_id)
        if legacy is not None:
            return Run.from_legacy(legacy, run_id)
        return None

    def _append_run(
        self,
        *,
        status: RunStatus | str | None = None,
        run_status: RunStatus | str | None = None,
        phase: str | None = None,
        activity: str | None = None,
        ticket: int | None = None,
        pr: int | None = None,
        commit: str | None = None,
        checkpoint: str | None = None,
        branch: str | None = None,
        worktree: str | None = None,
        session: int | None = None,
        claim_status: ClaimStatus | str | None = None,
        epoch: int | None = None,
        attempt_number: int | None = None,
        recovery_status: str | None = None,
        recovered_from: str | None = None,
        started_at: str | None = None,
    ) -> Run:
        now = self._clock()
        current = self._latest_run(self.run_id)
        base = current or Run(run_id=self.run_id, seq=0, recorded_at=_iso(now), started_at=_iso(now))
        seq = base.seq + 1
        for _attempt in range(MAX_APPEND_ATTEMPTS):
            candidate = Run(
                run_id=self.run_id,
                seq=seq,
                recorded_at=_iso(now),
                session=session if session is not None else base.session,
                ticket=ticket if ticket is not None else base.ticket,
                run_status=str(status or run_status or base.run_status),
                claim_status=str(claim_status or base.claim_status),
                epoch=epoch if epoch is not None else base.epoch,
                branch=branch if branch is not None else base.branch,
                worktree=worktree if worktree is not None else base.worktree,
                started_at=started_at or base.started_at,
                current_phase=phase or base.current_phase,
                # An absent activity never erases the last meaningful description.
                current_activity=activity or base.current_activity,
                pr=pr if pr is not None else base.pr,
                commit_sha=commit or base.commit_sha,
                latest_checkpoint=checkpoint or base.latest_checkpoint,
                attempt_number=attempt_number if attempt_number is not None else base.attempt_number,
                recovery_status=recovery_status or base.recovery_status,
                recovered_from=recovered_from or base.recovered_from,
            )
            try:
                self._store.create(f"{RUN_EVENT_PREFIX}{self.run_id}/e{candidate.seq}", candidate.to_payload())
                return candidate
            except RefExists:
                # Another writer of this run id took that sequence: re-read, retry.
                latest = self._latest_run(self.run_id)
                seq = (latest.seq + 1) if latest else 1
        raise StoreError(f"could not append a run event for {self.run_id} after {MAX_APPEND_ATTEMPTS} attempts")

    # ------------------------------------------------------------------ claims

    def ticket_state(self, ticket: int) -> TicketState:
        return self._ticket_state(ticket)

    def _ticket_state(self, ticket: int) -> TicketState:
        claim_refs = self._store.list(f"{CLAIM_EPOCH_PREFIX}{ticket}/")
        release_refs = self._store.list(f"{RELEASE_PREFIX}{ticket}/")
        lease_refs = self._store.list(f"{LEASE_PREFIX}{ticket}/")

        claims: dict[int, Claim] = {}
        for ref, payload in claim_refs.items():
            epoch = _epoch_from(ref, f"{CLAIM_EPOCH_PREFIX}{ticket}/")
            if epoch is not None:
                claims[epoch] = Claim.from_payload(payload)
        releases: dict[int, dict[str, Any]] = {}
        for ref, payload in release_refs.items():
            epoch = _epoch_from(ref, f"{RELEASE_PREFIX}{ticket}/")
            if epoch is not None:
                releases[epoch] = payload

        legacy = False
        if not claims and not releases:
            legacy_payload = self._store.read(f"{CLAIM_PREFIX}{ticket}")
            if legacy_payload:
                claims[LEGACY_EPOCH] = Claim.from_legacy(legacy_payload, ticket)
                legacy = True

        epoch = max([*claims, *releases], default=0)
        last_claim = claims.get(epoch)
        released_at = releases.get(epoch, {}).get("released_at")
        leases = [
            Lease.from_payload(payload)
            for ref, payload in lease_refs.items()
            if _epoch_from(ref, f"{LEASE_PREFIX}{ticket}/") == epoch
        ]
        effective = last_claim
        if last_claim is not None and leases:
            newest = max(leases, key=lambda lease: (_parse(lease.renewed_at), lease.renewed_count))
            effective = replace(
                last_claim,
                current_activity=newest.current_activity or last_claim.current_activity,
                pr=newest.pr if newest.pr is not None else last_claim.pr,
                commit_sha=newest.commit_sha or last_claim.commit_sha,
                latest_checkpoint=newest.latest_checkpoint or last_claim.latest_checkpoint,
            )
        expires_at = None
        if effective is not None and not released_at:
            moments = [_parse(effective.expires_at)] + [_parse(lease.expires_at) for lease in leases]
            expires_at = _iso(max(moments))
        intents = [
            payload
            for payload in self._store.list(f"{RECOVERY_INTENT_PREFIX}{ticket}/").values()
            if payload.get("target_epoch") == epoch + 1
        ]
        return TicketState(
            ticket=ticket,
            epoch=epoch,
            claim=None if released_at else effective,
            last_claim=effective,
            released_at=released_at,
            expires_at=expires_at,
            leases=leases,
            recovery_intents=intents,
            legacy=legacy,
        )

    def claim_of(self, ticket: int) -> Claim | None:
        return self._ticket_state(ticket).claim

    def _tickets_with_claims(self) -> list[int]:
        tickets: set[int] = set()
        for prefix in self._claimed_tickets():
            for ref in self._store.list_names(prefix):
                head = ref[len(prefix) :].split("/")[0]
                if head.isdigit():
                    tickets.add(int(head))
        return sorted(tickets)

    def claims(self) -> list[Claim]:
        holders = [state.claim for state in map(self._ticket_state, self._tickets_with_claims())]
        return [claim for claim in holders if claim is not None]

    @staticmethod
    def _claimed_tickets() -> tuple[str, ...]:
        return (CLAIM_EPOCH_PREFIX, CLAIM_PREFIX)

    def claim(self, ticket: int, *, branch: str = "", worktree: str = "", activity: str = "") -> ClaimResult:
        now = self._clock()
        state = self._ticket_state(ticket)
        if state.claim is not None:
            if state.claim.run_id == self.run_id:
                return ClaimResult(ClaimOutcome.ALREADY_HELD, ticket, state.claim, "already held by this run")
            if state.expired(now):
                return ClaimResult(
                    ClaimOutcome.HELD_EXPIRED,
                    ticket,
                    state.claim,
                    f"{state.describe(now)}; run `recover` only after inspecting branch, commits and PR",
                )
            return ClaimResult(ClaimOutcome.HELD_BY_OTHER, ticket, state.claim, self._describe_holder(state, now))

        run = self.run()
        epoch = state.epoch + 1
        record = Claim(
            run_id=self.run_id,
            ticket=ticket,
            epoch=epoch,
            claimed_at=_iso(now),
            expires_at=_iso(now + self._lease),
            branch=branch or run.branch,
            worktree=worktree or run.worktree,
            current_activity=activity or f"claimed ticket #{ticket}",
        )
        try:
            self._store.create(f"{CLAIM_EPOCH_PREFIX}{ticket}/e{epoch}", record.to_payload())
        except RefExists:
            return self._conflict(ticket, now)
        return self._confirm(ticket, epoch, now)

    def _conflict(self, ticket: int, now: datetime) -> ClaimResult:
        state = self._ticket_state(ticket)
        if state.claim is None:
            return ClaimResult(
                ClaimOutcome.HELD_BY_OTHER, ticket, None, "claim state changed during acquisition; re-read before acting"
            )
        if state.claim.run_id == self.run_id:
            return ClaimResult(ClaimOutcome.ALREADY_HELD, ticket, state.claim, "already held by this run")
        if state.expired(now):
            return ClaimResult(
                ClaimOutcome.HELD_EXPIRED,
                ticket,
                state.claim,
                f"{state.describe(now)}; run `recover` only after inspection",
            )
        return ClaimResult(ClaimOutcome.HELD_BY_OTHER, ticket, state.claim, self._describe_holder(state, now))

    @staticmethod
    def _describe_holder(state: TicketState, now: datetime) -> str:
        assert state.claim is not None
        return (
            f"held by {state.claim.run_id} at epoch {state.epoch} until {state.expires_at}: "
            f"{state.claim.current_activity}"
        )

    def _confirm(self, ticket: int, epoch: int, now: datetime) -> ClaimResult:
        payload = self._store.read(f"{CLAIM_EPOCH_PREFIX}{ticket}/e{epoch}")
        held = Claim.from_payload(payload) if payload else None
        if held is None or held.run_id != self.run_id or held.epoch != epoch:
            raise ClaimUnverified(f"claim on #{ticket} epoch {epoch} was not confirmed for {self.run_id}")
        self._append_run(
            ticket=ticket,
            epoch=epoch,
            claim_status=ClaimStatus.LEASED,
            status=RunStatus.CLAIMING,
            phase="claiming",
            activity=held.current_activity,
            branch=held.branch,
            worktree=held.worktree,
            attempt_number=held.attempt_number,
        )
        return ClaimResult(ClaimOutcome.ACQUIRED, ticket, held, f"claim acquired and verified at epoch {epoch}")

    def renew(
        self,
        ticket: int,
        *,
        activity: str | None = None,
        phase: str | None = None,
        status: RunStatus | None = None,
        pr: int | None = None,
        commit: str | None = None,
        checkpoint: str | None = None,
    ) -> Claim:
        state = self._ticket_state(ticket)
        if state.claim is None:
            if state.released_at:
                raise ClaimLost(f"claim on #{ticket} was already released; nothing to renew")
            raise ClaimLost(f"no claim on #{ticket}; stop modifying the ticket and checkpoint")
        if state.claim.run_id != self.run_id:
            raise ClaimSuperseded(
                f"#{ticket} is held by {state.claim.run_id} at epoch {state.epoch}; this run's epoch was "
                "superseded - stop modifying the ticket"
            )
        lease = self._append_lease(
            state, activity=activity, phase=phase, status=status, pr=pr, commit=commit, checkpoint=checkpoint
        )
        self._append_run(
            ticket=ticket,
            epoch=state.epoch,
            claim_status=ClaimStatus.LEASED,
            status=status,
            phase=phase,
            activity=activity,
            pr=pr,
            commit=commit,
            checkpoint=checkpoint,
        )
        assert state.claim is not None
        return Claim(
            run_id=lease.run_id,
            ticket=ticket,
            epoch=lease.epoch,
            claimed_at=state.claim.claimed_at,
            expires_at=lease.expires_at,
            branch=state.claim.branch,
            worktree=state.claim.worktree,
            current_activity=lease.current_activity,
            attempt_number=state.claim.attempt_number,
            recovery_status=state.claim.recovery_status,
            recovered_from=state.claim.recovered_from,
            previous_branch=state.claim.previous_branch,
            previous_pr=state.claim.previous_pr,
            inspection=state.claim.inspection,
            pr=lease.pr if lease.pr is not None else state.claim.pr,
            commit_sha=lease.commit_sha or state.claim.commit_sha,
            latest_checkpoint=lease.latest_checkpoint or state.claim.latest_checkpoint,
        )

    def _append_lease(
        self,
        state: TicketState,
        *,
        activity: str | None = None,
        phase: str | None = None,
        status: RunStatus | str | None = None,
        pr: int | None = None,
        commit: str | None = None,
        checkpoint: str | None = None,
    ) -> Lease:
        assert state.claim is not None
        now = self._clock()
        prefix = f"{LEASE_PREFIX}{state.ticket}/e{state.epoch}/"
        existing = self._store.list_names(prefix)
        for attempt in range(MAX_APPEND_ATTEMPTS):
            seq = len(existing) + 1 + attempt
            candidate = Lease(
                run_id=self.run_id,
                ticket=state.ticket,
                epoch=state.epoch,
                renewed_at=_iso(now),
                expires_at=_iso(now + self._lease),
                current_activity=activity or state.claim.current_activity,
                phase=phase or "",
                run_status=str(status or ""),
                pr=pr if pr is not None else state.claim.pr,
                commit_sha=commit,
                latest_checkpoint=checkpoint,
                renewed_count=seq,
            )
            try:
                self._store.create(f"{prefix}{self.run_id}-{seq}", candidate.to_payload())
                return candidate
            except RefExists:
                existing = self._store.list_names(prefix)
        raise StoreError(f"could not append a lease for #{state.ticket} after {MAX_APPEND_ATTEMPTS} attempts")

    def release(
        self,
        ticket: int,
        *,
        status: RunStatus = RunStatus.COMPLETED,
        activity: str = "",
        pr: int | None = None,
        commit: str | None = None,
    ) -> Run:
        """Stop work, then create one release event. That event is the only write.

        Ordering invariant: a caller releases only after it has stopped modifying
        the ticket. A crash before the create leaves the claim held (recoverable);
        a crash after it leaves the ticket available with the work already stopped.
        """
        now = self._clock()
        state = self._ticket_state(ticket)
        if state.claim is None:
            if state.released_at is None:
                raise ClaimLost(f"no claim on #{ticket}; nothing to release")
            return self._append_run(
                ticket=ticket,
                claim_status=ClaimStatus.RELEASED,
                status=status,
                phase=str(status),
                activity=activity or f"claim on #{ticket} already released",
                pr=pr,
                commit=commit,
            )
        if state.claim.run_id != self.run_id:
            raise NotClaimOwner(f"#{ticket} is held by {state.claim.run_id}; {self.run_id} may not release it")
        try:
            self._store.create(
                f"{RELEASE_PREFIX}{ticket}/e{state.epoch}",
                {
                    "run_id": self.run_id,
                    "ticket": ticket,
                    "epoch": state.epoch,
                    "released_at": _iso(now),
                    "status": str(status),
                    "activity": activity or f"claim on #{ticket} released ({status})",
                    "pr": pr if pr is not None else state.claim.pr,
                    "commit_sha": commit or state.claim.commit_sha,
                },
            )
        except RefExists:
            pass  # idempotent release
        return self._append_run(
            ticket=ticket,
            epoch=state.epoch,
            claim_status=ClaimStatus.RELEASED,
            status=status,
            phase=str(status),
            activity=activity or f"claim on #{ticket} released ({status})",
            pr=pr,
            commit=commit,
        )

    def recover(
        self,
        ticket: int,
        *,
        branch: str = "",
        worktree: str = "",
        activity: str = "",
        inspect: str = "",
    ) -> ClaimResult:
        """Take over an expired claim. The takeover is atomic; the intent is advisory.

        There is no recovery lock to abandon: the contested operation is the
        creation of claim epoch K+1, which exactly one contender can win. The
        intent ref only shows *who is inspecting what*; it never grants or blocks
        ownership.
        """
        now = self._clock()
        state = self._ticket_state(ticket)
        if state.claim is not None and state.claim.run_id == self.run_id:
            return ClaimResult(ClaimOutcome.ALREADY_HELD, ticket, state.claim, "already held by this run")
        if state.claim is not None and not state.expired(now):
            return ClaimResult(
                ClaimOutcome.NOT_EXPIRED,
                ticket,
                state.claim,
                f"held by {state.claim.run_id} until {state.expires_at}; nothing to recover",
            )

        epoch = state.epoch + 1
        self._record_recovery_intent(ticket, epoch, inspect)
        previous = state.claim
        record = Claim(
            run_id=self.run_id,
            ticket=ticket,
            epoch=epoch,
            claimed_at=_iso(now),
            expires_at=_iso(now + self._lease),
            branch=branch or (previous.branch if previous else ""),
            worktree=worktree or (previous.worktree if previous else ""),
            current_activity=activity or f"recovering ticket #{ticket} at epoch {epoch}",
            attempt_number=(previous.attempt_number + 1) if previous else 1,
            recovery_status="RECOVERED" if previous else "none",
            recovered_from=previous.run_id if previous else None,
            previous_branch=previous.branch if previous else None,
            previous_pr=previous.pr if previous else None,
            inspection=inspect or None,
            pr=previous.pr if previous else None,
            commit_sha=previous.commit_sha if previous else None,
            latest_checkpoint=previous.latest_checkpoint if previous else None,
        )
        try:
            self._store.create(f"{CLAIM_EPOCH_PREFIX}{ticket}/e{epoch}", record.to_payload())
        except RefExists:
            holder = self._ticket_state(ticket).claim
            detail = (
                f"recovery of #{ticket} epoch {epoch} already won by {holder.run_id}"
                if holder
                else f"recovery of #{ticket} epoch {epoch} lost the create race"
            )
            return ClaimResult(ClaimOutcome.RECOVERY_IN_PROGRESS, ticket, holder, detail)

        payload = self._store.read(f"{CLAIM_EPOCH_PREFIX}{ticket}/e{epoch}")
        confirmed = Claim.from_payload(payload) if payload else None
        if confirmed is None or confirmed.run_id != self.run_id:
            raise ClaimUnverified(f"recovery claim on #{ticket} was not confirmed for {self.run_id}")
        self._append_run(
            ticket=ticket,
            epoch=epoch,
            claim_status=ClaimStatus.RECOVERED,
            status=RunStatus.RECOVERING,
            phase="recovery",
            activity=record.current_activity,
            branch=record.branch,
            worktree=record.worktree,
            attempt_number=record.attempt_number,
            recovery_status=record.recovery_status,
            recovered_from=record.recovered_from,
        )
        detail = f"recovered epoch {epoch} from {record.recovered_from}" if record.recovered_from else f"claimed epoch {epoch}"
        if inspect:
            detail += f"; inspected: {inspect}"
        return ClaimResult(ClaimOutcome.ACQUIRED, ticket, confirmed, detail)

    def _record_recovery_intent(self, ticket: int, epoch: int, inspect: str) -> None:
        now = self._clock()
        prefix = f"{RECOVERY_INTENT_PREFIX}{ticket}/e{epoch}/"
        for attempt in range(MAX_APPEND_ATTEMPTS):
            try:
                self._store.create(
                    f"{prefix}{self.run_id}-{int(now.timestamp())}-{attempt}",
                    {
                        "run_id": self.run_id,
                        "ticket": ticket,
                        "target_epoch": epoch,
                        "at": _iso(now),
                        "expires_at": _iso(now + self._lease),
                        "inspection": inspect,
                    },
                )
                return
            except RefExists:
                continue
        # Advisory only: failing to record an intent must never block recovery.

    # ------------------------------------------------------------- observability

    def mark_run(self, run_id: str, status: RunStatus, *, activity: str = "", force: bool = False) -> Run | None:
        """Record an observation about another run; never mutate its registry entry.

        `force` is kept for API compatibility and has no effect: an observer cannot
        write into another run's namespace at all.
        """
        target = self._latest_run(run_id)
        if target is None:
            return None
        self.observe(run_id, status, reason=activity or f"observed stale by {self.run_id}")
        return target

    def observe(
        self, target_run_id: str, status: RunStatus = RunStatus.ABANDONED, *, reason: str = ""
    ) -> dict[str, Any]:
        now = self._clock()
        target = self._latest_run(target_run_id)
        prefix = f"{OBSERVATION_PREFIX}{self.run_id}/"
        existing = self._store.list_names(prefix)
        for attempt in range(MAX_APPEND_ATTEMPTS):
            seq = len(existing) + 1 + attempt
            record = {
                "observer": self.run_id,
                "target_run_id": target_run_id,
                "observed_status": str(status),
                "observed_at": _iso(now),
                "target_last_seen": target.recorded_at if target else None,
                "reason": reason,
                "seq": seq,
            }
            try:
                self._store.create(f"{prefix}{target_run_id}-{seq}", record)
                return record
            except RefExists:
                existing = self._store.list_names(prefix)
        raise StoreError(f"could not record observation about {target_run_id}")

    def observations(self) -> list[dict[str, Any]]:
        return list(self._store.list(OBSERVATION_PREFIX).values())

    def observations_of(self, target_run_id: str) -> list[dict[str, Any]]:
        return [item for item in self.observations() if item.get("target_run_id") == target_run_id]

    def health(self, run: Run, now: datetime | None = None) -> str:
        moment = now or self._clock()
        freshest = _parse(run.recorded_at)
        if run.ticket:
            state = self._ticket_state(run.ticket)
            if state.claim is not None and state.claim.run_id == run.run_id and state.expires_at:
                freshest = max(freshest, _parse(state.expires_at) - self._lease)
        if freshest <= moment - self._stale_after * 2:
            return "abandoned"
        if freshest <= moment - self._stale_after:
            return "stale"
        return "live"

    def excluded_tickets(self) -> dict[int, str]:
        """Tickets a run must not select: live claims *and* expired claims awaiting recovery."""
        now = self._clock()
        excluded: dict[int, str] = {}
        for ticket in self._tickets_with_claims():
            state = self._ticket_state(ticket)
            if state.claim is not None:
                excluded[ticket] = state.describe(now)
        return excluded

    def render_index(self, *, now: datetime | None = None) -> str:
        moment = now or self._clock()
        runs = self.runs()
        lines = [
            "<!-- generated by `python3 -m wingman.coordination index`; do not edit by hand -->",
            "",
            f"# WINGMAN run registry ({_iso(moment)})",
            "",
            "Authoritative source: the immutable `refs/wingman/*` events on GitHub (runs, claim",
            "epochs, leases, releases). This file is a derived snapshot; regenerate it instead of",
            "editing it.",
            "",
            "| Run | Ticket | Status | Health | Activity | Branch | PR | Last event |",
            "|---|---|---|---|---|---|---|---|",
        ]
        if not runs:
            lines.append("| — | — | — | — | no registered runs | — | — | — |")
        for run in runs:
            lines.append(
                "| {run} | {ticket} | {status} | {health} | {activity} | {branch} | {pr} | {age}m ago |".format(
                    run=run.run_id,
                    ticket=f"#{run.ticket}" if run.ticket else "—",
                    status=run.run_status,
                    health=self.health(run, moment),
                    activity=run.current_activity.replace("|", "/"),
                    branch=run.branch or "—",
                    pr=f"#{run.pr}" if run.pr else "—",
                    age=max(0, run.heartbeat_age(moment)) // 60,
                )
            )
        states = [self._ticket_state(ticket) for ticket in sorted(self.excluded_tickets())]
        lines += [
            "",
            "## Ticket claims",
            "",
            "| Ticket | Epoch | Held by | State | Activity | Expires | Attempt |",
            "|---|---|---|---|---|---|---|",
        ]
        if not states:
            lines.append("| — | — | — | no active claims | — | — | — |")
        for state in states:
            assert state.claim is not None
            lines.append(
                "| #{ticket} | {epoch} | {owner} | {state} | {activity} | {expires} | {attempt} |".format(
                    ticket=state.ticket,
                    epoch=state.epoch,
                    owner=state.claim.run_id,
                    state="EXPIRED - recovery required" if state.expired(moment) else "LEASED",
                    activity=state.claim.current_activity.replace("|", "/"),
                    expires=state.expires_at or "—",
                    attempt=state.claim.attempt_number,
                )
            )
        observations = self.observations()
        if observations:
            lines += [
                "",
                "## Observations (advisory, never authoritative)",
                "",
                "| Observer | Target | Observed | At |",
                "|---|---|---|---|",
            ]
            for item in sorted(observations, key=lambda entry: str(entry.get("observed_at"))):
                lines.append(
                    f"| {item.get('observer')} | {item.get('target_run_id')} | "
                    f"{item.get('observed_status')} | {item.get('observed_at')} |"
                )
        return "\n".join(lines) + "\n"


def build_store(repo: str, token: str) -> GitHubRefStore:
    return GitHubRefStore(repo, token)


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

    claim = sub.add_parser("claim", help="acquire an exclusive claim")
    claim.add_argument("ticket", type=int)
    claim.add_argument("--activity", default="")
    claim.add_argument("--branch", default="")
    claim.add_argument("--worktree", default="")

    renew = sub.add_parser("renew", help="renew a held claim")
    renew.add_argument("ticket", type=int)
    renew.add_argument("--activity", default="")
    renew.add_argument("--phase")
    renew.add_argument("--status", choices=[str(s) for s in RunStatus])
    renew.add_argument("--pr", type=int)
    renew.add_argument("--commit")
    renew.add_argument("--checkpoint")

    release = sub.add_parser("release", help="release a held claim")
    release.add_argument("ticket", type=int)
    release.add_argument("--status", default=str(RunStatus.COMPLETED), choices=[str(s) for s in RunStatus])
    release.add_argument("--activity", default="")
    release.add_argument("--pr", type=int)
    release.add_argument("--commit")

    recover = sub.add_parser("recover", help="take over an expired claim after inspection")
    recover.add_argument("ticket", type=int)
    recover.add_argument("--branch", default="")
    recover.add_argument("--worktree", default="")
    recover.add_argument("--activity", default="")
    recover.add_argument("--inspect", default="")

    observe = sub.add_parser("observe", help="record an observation about another run")
    observe.add_argument("run_id")
    observe.add_argument("--status", default=str(RunStatus.ABANDONED), choices=[str(s) for s in RunStatus])
    observe.add_argument("--reason", default="")

    sub.add_parser("status", help="print the registry and derived claim states")
    index = sub.add_parser("index", help="render the derived registry snapshot")
    index.add_argument("--out", default="docs/WINGMAN/RUNS.md")

    args = parser.parse_args(argv)
    token = os.environ.get(args.token_env, "")
    if not token:
        raise SystemExit(f"{args.token_env} is not set; coordination requires repository write access")
    coordinator = Coordinator(build_store(args.repo, token), args.run_id, lease=timedelta(minutes=args.lease_minutes))

    if args.command == "register":
        _print(
            _payload(
                coordinator.register(
                    ticket=args.ticket,
                    session=args.session,
                    branch=args.branch,
                    worktree=args.worktree,
                    activity=args.activity,
                )
            )
        )
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
        _print(
            _payload(
                coordinator.renew(
                    args.ticket,
                    activity=args.activity,
                    phase=args.phase,
                    status=args.status,
                    pr=args.pr,
                    commit=args.commit,
                    checkpoint=args.checkpoint,
                )
            )
        )
    elif args.command == "release":
        _print(
            _payload(
                coordinator.release(args.ticket, status=args.status, activity=args.activity, pr=args.pr, commit=args.commit)
            )
        )
    elif args.command == "recover":
        result = coordinator.recover(
            args.ticket, branch=args.branch, worktree=args.worktree, activity=args.activity, inspect=args.inspect
        )
        _print(result.to_dict())
        return 0 if result.acquired else 3
    elif args.command == "observe":
        _print(coordinator.observe(args.run_id, args.status, reason=args.reason))
    elif args.command == "status":
        now = utcnow()
        tickets = sorted(coordinator.excluded_tickets())
        _print(
            {
                "generated_at": _iso(now),
                "runs": [{**_payload(run), "health": coordinator.health(run, now)} for run in coordinator.runs()],
                "ticket_states": [
                    {
                        "ticket": state.ticket,
                        "epoch": state.epoch,
                        "owner": state.owner,
                        "expires_at": state.expires_at,
                        "legacy": state.legacy,
                        "recovery_intents": len(state.recovery_intents),
                        "detail": state.describe(now),
                    }
                    for state in (coordinator.ticket_state(ticket) for ticket in tickets)
                ],
                "excluded_tickets": coordinator.excluded_tickets(),
                "observations": coordinator.observations(),
            }
        )
    elif args.command == "index":
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(coordinator.render_index())
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
