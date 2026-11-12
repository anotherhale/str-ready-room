"""Permissions: the verbs a principal may perform.

Permissions are framework-independent value objects.  Policies map principals
to permissions; application use cases check permissions before doing work.
"""
from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    TASKS_READ = "tasks:read"
    TASKS_CREATE = "tasks:create"
    TASKS_UPDATE = "tasks:update"
    TASKS_COMPLETE = "tasks:complete"
    TASKS_REOPEN = "tasks:reopen"
    TASKS_DELETE = "tasks:delete"
    DASHBOARD_READ = "dashboard:read"
    BRIEFING_READ = "briefing:read"
    SETTINGS_READ = "settings:read"
    SETTINGS_UPDATE = "settings:update"
    CATEGORIES_MANAGE = "categories:manage"
    RECURRENCE_READ = "recurrence:read"
    RECURRENCE_WRITE = "recurrence:write"
    CALENDAR_READ = "calendar:read"
    CALENDAR_SYNC = "calendar:sync"
    CALENDAR_WRITE = "calendar:write"
    EMAIL_READ = "email:read"
    EMAIL_CAPTURE = "email:capture"
    DEMO_RESET = "demo:reset"
    DEMO_SIMULATE = "demo:simulate"


#: Permissions granted to the single demo operator.  A future policy adapter can
#: replace this set without touching application services.
OPERATOR_PERMISSIONS: frozenset[Permission] = frozenset(Permission)

VIEWER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.TASKS_READ,
        Permission.DASHBOARD_READ,
        Permission.BRIEFING_READ,
        Permission.SETTINGS_READ,
        Permission.RECURRENCE_READ,
        Permission.CALENDAR_READ,
        Permission.EMAIL_READ,
    }
)
