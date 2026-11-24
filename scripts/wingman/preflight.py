"""WINGMAN preflight — the mandatory handshake, executable and fail-closed.

A worker may not touch a ticket until every step below has succeeded:

    register -> discover -> reconcile -> exclude -> select -> claim + verify
             -> isolate workspace -> EXECUTING

`Handshake.run` raises `HandshakeError` on the first failure, and callers must treat
that as "do not implement". The steps are deliberately boring: this module adds no
new coordination mechanism, it drives `wingman.coordination` (create-only refs) and
reads GitHub issues/branches/PRs for reconciliation.

Why it exists: prose instructions cannot fail closed. A worker that forgets step 6
still looks busy, so the enforcement has to be code that refuses to return a plan.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from wingman.coordination import (
    CoordinationError,
    Coordinator,
    NotClaimOwner,
    NotRegistered,
    RunStatus,
    StoreError,
    build_store,
)

PRIORITY_ORDER = {"P0-critical": 0, "P1-high": 1, "P2-normal": 2, "P3-low": 3}
DEFAULT_PRIORITY = 9
BLOCKING_LABELS = frozenset({"blocked"})
DEPENDENCY_PATTERN = re.compile(r"(?:depends on|blocked by|requires)\s+#(\d+)", re.IGNORECASE)
BRANCH_TICKET_PATTERN = re.compile(r"issue-(\d+)", re.IGNORECASE)
PR_TICKET_PATTERN = re.compile(r"(?:closes|fixes|resolves|refs?|part of)\s+#(\d+)", re.IGNORECASE)


class HandshakeError(RuntimeError):
    """A handshake step failed; implementation must not begin."""


class WorkspaceError(HandshakeError):
    """The workspace is not isolated to this run."""


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    labels: tuple[str, ...] = ()
    body: str = ""
    state: str = "open"

    def priority(self) -> int:
        ranked = [PRIORITY_ORDER[label] for label in self.labels if label in PRIORITY_ORDER]
        return min(ranked) if ranked else DEFAULT_PRIORITY

    def dependencies(self) -> tuple[int, ...]:
        return tuple(sorted({int(match) for match in DEPENDENCY_PATTERN.findall(self.body)}))

    def is_blocked(self) -> bool:
        return bool(BLOCKING_LABELS.intersection(self.labels))


@dataclass(frozen=True)
class ReconcileNote:
    """A discrepancy found between the registry and GitHub. Advisory, never a write."""

    ticket: int
    kind: str
    detail: str


@dataclass(frozen=True)
class Plan:
    run_id: str
    ticket: int
    title: str
    branch: str
    worktree: str
    excluded: dict[int, str] = field(default_factory=dict)
    notes: tuple[ReconcileNote, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "ticket": self.ticket,
            "title": self.title,
            "branch": self.branch,
            "worktree": self.worktree,
            "reason": self.reason,
            "excluded": {str(k): v for k, v in sorted(self.excluded.items())},
            "reconcile_notes": [note.__dict__ for note in self.notes],
        }


class IssueSource(Protocol):
    def issues(self) -> list[Issue]:
        """Every issue (open and closed) that the selection may consider."""

    def prs_by_ticket(self) -> dict[int, list[int]]:
        """Open pull requests keyed by the ticket they deliver."""

    def branches_by_ticket(self) -> dict[int, list[str]]:
        """Remote branch names keyed by ticket."""


class StaticIssueSource:
    """Deterministic source for tests and dry runs from a captured snapshot."""

    def __init__(
        self,
        issues: list[Issue],
        prs: dict[int, list[int]] | None = None,
        branches: dict[int, list[str]] | None = None,
    ) -> None:
        self._issues = list(issues)
        self._prs = prs or {}
        self._branches = branches or {}

    def issues(self) -> list[Issue]:
        return list(self._issues)

    def prs_by_ticket(self) -> dict[int, list[int]]:
        return {ticket: list(prs) for ticket, prs in self._prs.items()}

    def branches_by_ticket(self) -> dict[int, list[str]]:
        return {ticket: list(branches) for ticket, branches in self._branches.items()}


class GitHubIssueSource:
    """Issues, open PRs and remote branches, read from GitHub + the local clone."""

    def __init__(self, repo: str, token: str, *, api_url: str = "https://api.github.com", timeout: float = 20.0) -> None:
        self._repo = repo
        self._token = token
        self._api_url = api_url.rstrip("/")
        self._timeout = timeout

    def _get(self, path: str, **params: Any) -> Any:
        query = "&".join(f"{key}={value}" for key, value in params.items())
        url = f"{self._api_url}/repos/{self._repo}{path}" + (f"?{query}" if query else "")
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            return json.loads(response.read())

    def issues(self) -> list[Issue]:
        found: list[Issue] = []
        page = 1
        while True:
            batch = self._get("/issues", state="all", per_page=100, page=page)
            if not batch:
                return found
            for item in batch:
                if "pull_request" in item:
                    continue
                found.append(
                    Issue(
                        number=item["number"],
                        title=item["title"],
                        labels=tuple(label["name"] for label in item["labels"]),
                        body=item.get("body") or "",
                        state=item["state"],
                    )
                )
            page += 1

    def prs_by_ticket(self) -> dict[int, list[int]]:
        found: dict[int, list[int]] = {}
        for pull in self._get("/pulls", state="open", per_page=100):
            tickets = {int(match) for match in BRANCH_TICKET_PATTERN.findall(pull["head"]["ref"])}
            tickets |= {int(match) for match in PR_TICKET_PATTERN.findall(pull.get("body") or "")}
            for ticket in tickets:
                found.setdefault(ticket, []).append(pull["number"])
        return found

    def branches_by_ticket(self) -> dict[int, list[str]]:
        output = subprocess.run(
            ["git", "ls-remote", "--heads", "origin"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        found: dict[int, list[str]] = {}
        for line in output.splitlines():
            _, _, name = line.partition("refs/heads/")
            for match in BRANCH_TICKET_PATTERN.findall(name):
                found.setdefault(int(match), []).append(name)
        return found


def exclusion_set(
    issues: list[Issue],
    source: IssueSource,
    coordinator: Coordinator,
    *,
    run_id: str,
) -> dict[int, str]:
    """Tickets this run must not select, with the reason for each.

    Labels alone are not enough: a ticket can be unclaimed but already delivered by a
    branch or PR, or claimed but expired (recovery required, not free).
    """
    excluded: dict[int, str] = dict(coordinator.excluded_tickets())
    prs = source.prs_by_ticket()
    branches = source.branches_by_ticket()
    closed = {issue.number for issue in issues if issue.state != "open"}

    for issue in issues:
        if issue.state != "open":
            continue
        if issue.is_blocked():
            excluded.setdefault(issue.number, "labelled blocked")
        missing = [number for number in issue.dependencies() if number not in closed]
        if missing:
            excluded.setdefault(issue.number, f"unsatisfied dependencies {missing}")
        if prs.get(issue.number):
            excluded.setdefault(issue.number, f"open PR(s) {sorted(prs[issue.number])}")
        others = [name for name in branches.get(issue.number, []) if run_id not in name]
        if others:
            excluded.setdefault(issue.number, f"existing branch(es) {sorted(others)}")
    return excluded


def select_ticket(
    issues: list[Issue],
    excluded: dict[int, str],
) -> tuple[Issue | None, str]:
    """Highest-value eligible ticket: priority, then unblocking value, then age."""
    open_issues = [issue for issue in issues if issue.state == "open"]
    eligible = [issue for issue in open_issues if issue.number not in excluded]
    if not eligible:
        return None, "every open ticket is excluded"

    dependents: dict[int, int] = {}
    for issue in open_issues:
        for dependency in issue.dependencies():
            dependents[dependency] = dependents.get(dependency, 0) + 1

    ranked = sorted(eligible, key=lambda issue: (issue.priority(), -dependents.get(issue.number, 0), issue.number))
    winner = ranked[0]
    reason = (
        f"priority {winner.priority()} label(s) {[label for label in winner.labels if label in PRIORITY_ORDER] or 'none'}, "
        f"unblocks {dependents.get(winner.number, 0)} ticket(s), {len(eligible)} eligible"
    )
    return winner, reason


def verify_workspace(path: str, branch: str, run_id: str) -> None:
    """Fail closed unless `path` is a worktree dedicated to this run and branch.

    The check is deliberately strict: a shared checkout is how one worker's HEAD
    switch or `reset --hard` destroyed another worker's run (incident B-008).
    """

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, check=True).stdout

    if not os.path.isdir(path):
        raise WorkspaceError(f"workspace {path} does not exist; create a worktree before implementing")
    try:
        if git("rev-parse", "--is-inside-work-tree").strip() != "true":
            raise WorkspaceError(f"{path} is not a git work tree")
        current = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    except subprocess.CalledProcessError as error:
        raise WorkspaceError(f"{path} is not a usable git work tree: {error.stderr.strip()}") from error
    if current != branch:
        raise WorkspaceError(f"{path} is on branch {current!r}, expected {branch!r}")

    listing = git("worktree", "list", "--porcelain").split("\n\n")
    entries = [block for block in listing if block.strip()]
    paths = [line.split(" ", 1)[1] for block in entries for line in block.splitlines() if line.startswith("worktree ")]
    if not paths:
        raise WorkspaceError(f"cannot determine worktrees for {path}")
    primary = os.path.realpath(paths[0])
    if os.path.realpath(path) == primary:
        raise WorkspaceError(f"{path} is the primary checkout; a run must work in its own worktree")
    shared = [
        block
        for block in entries
        if f"branch refs/heads/{branch}" in block and os.path.realpath(path) not in block
    ]
    if shared:
        raise WorkspaceError(f"branch {branch!r} is also checked out elsewhere")
    if run_id not in branch:
        raise WorkspaceError(f"branch {branch!r} does not identify run {run_id}")


class Handshake:
    """Runs the mandatory startup sequence for one run identity."""

    def __init__(
        self,
        coordinator: Coordinator,
        source: IssueSource,
        *,
        branch: str,
        worktree: str,
        session: int | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._source = source
        self._branch = branch
        self._worktree = worktree
        self._session = session

    @property
    def run_id(self) -> str:
        return self._coordinator.run_id

    def run(
        self,
        *,
        ticket: int | None = None,
        activity: str = "",
        dry_run: bool = False,
        verify_workspace_isolation: bool = True,
    ) -> Plan:
        # 1. register
        try:
            self._coordinator.register(
                session=self._session,
                branch=self._branch,
                worktree=self._worktree,
                activity="registered; running the mandatory handshake",
            )
        except StoreError as error:
            raise HandshakeError(f"step 1 register failed: {error}") from error

        # 2. discover runs (including this one, so its own claim is not a false positive)
        runs = self._coordinator.runs()

        # 3. reconcile registry against GitHub (advisory notes; never a write)
        notes = self._reconcile(runs)

        # 4. exclusion set
        issues = self._source.issues()
        excluded = exclusion_set(issues, self._source, self._coordinator, run_id=self.run_id)

        # 5. select
        if ticket is not None:
            chosen = next((issue for issue in issues if issue.number == ticket), None)
            if chosen is None:
                raise HandshakeError(f"step 5: ticket #{ticket} is not visible to this worker")
            if ticket in excluded and not dry_run:
                raise HandshakeError(f"step 5: ticket #{ticket} is excluded: {excluded[ticket]}")
            reason = f"explicitly requested; {'excluded: ' + excluded[ticket] if ticket in excluded else 'eligible'}"
        else:
            chosen, reason = select_ticket(issues, excluded)
            if chosen is None:
                raise HandshakeError(f"step 5 no eligible ticket: {reason}")

        plan = Plan(
            run_id=self.run_id,
            ticket=chosen.number,
            title=chosen.title,
            branch=self._branch,
            worktree=self._worktree,
            excluded=excluded,
            notes=notes,
            reason=reason,
        )
        if dry_run:
            return plan

        # 6. claim, then verify the read-back before any work
        try:
            result = self._coordinator.claim(
                chosen.number,
                branch=self._branch,
                worktree=self._worktree,
                activity=activity or f"implementing #{chosen.number}: {chosen.title}",
            )
            if not result.acquired:
                raise HandshakeError(f"step 6 claim refused ({result.outcome}): {result.detail}")
            verified = self._coordinator.claim_of(chosen.number)
        except HandshakeError:
            raise
        except CoordinationError as error:
            raise HandshakeError(f"step 6 claim failed ({error}); do not implement") from error
        if verified is None or verified.run_id != self.run_id:
            raise HandshakeError(
                f"step 6 claim on #{chosen.number} could not be verified; do not implement"
            )

        # 7. isolate the workspace
        if verify_workspace_isolation:
            try:
                verify_workspace(self._worktree, self._branch, self.run_id)
            except WorkspaceError as error:
                raise WorkspaceError(
                    f"step 7 workspace rejected ({error}); the claim on #{chosen.number} stays held "
                    "so no other worker starts the same ticket"
                ) from error

        # 8. only now may implementation begin
        try:
            self._coordinator.heartbeat(
                status=RunStatus.EXECUTING,
                phase="implementation",
                activity=plan.reason if not activity else activity,
                ticket=chosen.number,
            )
        except StoreError as error:
            raise HandshakeError(f"step 8 heartbeat failed ({error}); stop before implementing") from error
        return plan

    def _reconcile(self, runs: list[Any]) -> tuple[ReconcileNote, ...]:
        notes: list[ReconcileNote] = []
        now = self._coordinator.now()
        health = {run.run_id: self._coordinator.health(run, now) for run in runs}
        for claim in self._coordinator.claims():
            owner_health = health.get(claim.run_id)
            if owner_health is None:
                notes.append(
                    ReconcileNote(
                        claim.ticket,
                        "CLAIM_WITHOUT_RUN",
                        f"claim held by {claim.run_id} which has no registry entry; treat as recovery-required",
                    )
                )
            elif owner_health in {"stale", "abandoned"}:
                notes.append(
                    ReconcileNote(
                        claim.ticket,
                        "STALE_OWNER",
                        f"claim held by {claim.run_id} is {owner_health}; inspect before recovering",
                    )
                )
            if claim.expired(now):
                notes.append(
                    ReconcileNote(
                        claim.ticket,
                        "CLAIM_EXPIRED",
                        f"claim by {claim.run_id} expired at {claim.expires_at}; recovery inspection required",
                    )
                )
        return tuple(notes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wingman.preflight", description="WINGMAN mandatory startup handshake")
    parser.add_argument("--repo", default=os.environ.get("READY_ROOM_WINGMAN_REPO", "anotherhale/str-ready-room"))
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--run-id", default=os.environ.get("WINGMAN_RUN_ID", ""))
    parser.add_argument("--session", type=int)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--ticket", type=int)
    parser.add_argument("--activity", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    token = os.environ.get(args.token_env, "")
    if not token:
        raise SystemExit(f"{args.token_env} is not set")
    coordinator = Coordinator(build_store(args.repo, token), args.run_id)
    handshake = Handshake(
        coordinator,
        GitHubIssueSource(args.repo, token),
        branch=args.branch,
        worktree=args.worktree,
        session=args.session,
    )
    try:
        plan = handshake.run(ticket=args.ticket, activity=args.activity, dry_run=args.dry_run)
    except NotRegistered as error:
        print(f"handshake failed: {error}", file=sys.stderr)
        return 2
    except NotClaimOwner as error:
        print(f"handshake failed: {error}", file=sys.stderr)
        return 2
    except HandshakeError as error:
        print(f"handshake failed, do not implement: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"run      {plan.run_id}")
        print(f"ticket   #{plan.ticket} {plan.title}")
        print(f"reason   {plan.reason}")
        print(f"branch   {plan.branch}")
        print(f"worktree {plan.worktree}")
        print(f"excluded {len(plan.excluded)} ticket(s)")
        for note in plan.notes:
            print(f"note     #{note.ticket} {note.kind}: {note.detail}")
        print("\nNext: implement only in this worktree, heartbeat every ~5 minutes, release the claim at handoff.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
