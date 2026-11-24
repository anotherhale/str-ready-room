"""Permissions: the verbs a principal may perform.

Permissions are framework-independent value objects.  Policies map principals
to permissions; application use cases check permissions before doing work.
"""
from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    """The permission catalog of ADR-004 §2 (54 values).

    Values are added up front so later phases do not churn the enum.  Which
    role holds which permission, and at what scope, is decided elsewhere.
    """

    TASKS_READ = "tasks:read"
    TASKS_CREATE = "tasks:create"
    TASKS_UPDATE = "tasks:update"
    TASKS_COMPLETE = "tasks:complete"
    TASKS_REOPEN = "tasks:reopen"
    TASKS_DELETE = "tasks:delete"
    TASKS_ASSIGN = "tasks:assign"
    TASKS_SHARE = "tasks:share"
    TASKS_COMMENT = "tasks:comment"
    TASKS_ACKNOWLEDGE = "tasks:acknowledge"
    TASKS_HANDOFF = "tasks:handoff"
    DASHBOARD_READ = "dashboard:read"
    BRIEFING_READ = "briefing:read"
    BRIEFING_WRITE = "briefing:write"
    SETTINGS_READ = "settings:read"
    SETTINGS_UPDATE = "settings:update"
    CATEGORIES_MANAGE = "categories:manage"
    RECURRENCE_READ = "recurrence:read"
    RECURRENCE_WRITE = "recurrence:write"
    RECURRENCE_OVERRIDE = "recurrence:override"
    SQUADRON_READ = "squadron:read"
    SQUADRON_MANAGE = "squadron:manage"
    MEMBERS_READ = "members:read"
    MEMBERS_INVITE = "members:invite"
    MEMBERS_MANAGE = "members:manage"
    TEAMS_READ = "teams:read"
    TEAMS_MANAGE = "teams:manage"
    DUTY_POSITIONS_READ = "duty_positions:read"
    DUTY_POSITIONS_MANAGE = "duty_positions:manage"
    CALENDAR_READ = "calendar:read"
    CALENDAR_SYNC = "calendar:sync"
    CALENDAR_WRITE = "calendar:write"
    EMAIL_READ = "email:read"
    EMAIL_CAPTURE = "email:capture"
    NOTIFICATIONS_READ = "notifications:read"
    NOTIFICATIONS_SEND = "notifications:send"
    TURNOVER_READ = "turnover:read"
    TURNOVER_BUILD = "turnover:build"
    TURNOVER_ACKNOWLEDGE = "turnover:acknowledge"
    NOTES_READ = "notes:read"
    NOTES_WRITE = "notes:write"
    NOTES_SHARE = "notes:share"
    AUDIT_READ = "audit:read"
    APPROVALS_READ = "approvals:read"
    APPROVALS_DECIDE = "approvals:decide"
    WORKFLOWS_READ = "workflows:read"
    WORKFLOWS_MANAGE = "workflows:manage"
    AGENTS_READ = "agents:read"
    AGENTS_MANAGE = "agents:manage"
    DELEGATIONS_READ = "delegations:read"
    DELEGATIONS_GRANT = "delegations:grant"
    DELEGATIONS_REVOKE = "delegations:revoke"
    DEMO_RESET = "demo:reset"
    DEMO_SIMULATE = "demo:simulate"


#: Every catalogued permission, including the demo-only verbs.
ALL_PERMISSIONS: frozenset[Permission] = frozenset(Permission)

#: What a read-only principal may do: every `*:read` verb except the ones that
#: expose authority rather than operational content (ADR-004 §3).
READ_ONLY_PERMISSIONS: frozenset[Permission] = frozenset(
    permission
    for permission in Permission
    if permission.value.endswith(":read")
    and permission
    not in {Permission.AUDIT_READ, Permission.AGENTS_READ, Permission.DELEGATIONS_READ}
)

#: Demo aliases.  `operator` and `viewer` exist only inside `default_policy()`;
#: no production role grant contains a `demo:*` permission.
OPERATOR_PERMISSIONS: frozenset[Permission] = ALL_PERMISSIONS

VIEWER_PERMISSIONS: frozenset[Permission] = READ_ONLY_PERMISSIONS
