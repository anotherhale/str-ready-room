"""Recurrence application service: overview and preview.

Read-only views over recurrence rules and their upcoming occurrences.  The
authoritative arithmetic lives in the pure domain module.
"""
from __future__ import annotations

from datetime import date, timedelta

from ...domain.authorization.permissions import Permission
from ...domain.shared.clock import Clock
from ...domain.shared.errors import AuthorizationError
from ...domain.tasks.recurrence import preview as preview_dates
from ..commands import RecurrenceInput
from ..dto import RecurrenceOverviewDTO, RecurrenceSummary
from ..ports.identity import AuthorizationPort
from ..ports.persistence import DatabaseFactoryPort


class RecurrenceService:
    def __init__(self, database: DatabaseFactoryPort, authorizer: AuthorizationPort, clock: Clock) -> None:
        self._database = database
        self._authorizer = authorizer
        self._clock = clock

    def _authorize(self, principal, permission: Permission) -> None:
        decision = self._authorizer.authorize(principal, permission)
        if not decision.allowed:
            raise AuthorizationError(decision.reason, code=decision.code)

    def overview(self, principal) -> RecurrenceOverviewDTO:
        self._authorize(principal, Permission.RECURRENCE_READ)
        with self._database.create() as uow:
            rules = uow.recurrence_rules.list_all(principal.id)
            summaries = [
                RecurrenceSummary(
                    rule_id=r.id,
                    name=r.name,
                    frequency=r.frequency,
                    interval=r.interval,
                    day_of_week=r.day_of_week,
                    end_type=r.end_type,
                    active=r.active,
                    occurrences_generated=r.occurrences_generated,
                    next_occurrence=r.next_occurrence,
                )
                for r in rules
            ]
            upcoming: list[tuple[str, date]] = []
            for r in rules:
                if not r.active:
                    continue
                dates = preview_dates(r, count=1, after_date=self._clock.today(principal.timezone))
                if dates:
                    upcoming.append((r.name, dates[0]))
            upcoming.sort(key=lambda pair: pair[1])
            return RecurrenceOverviewDTO(rules=summaries, upcoming=upcoming)

    def preview(self, principal, recurrence: RecurrenceInput, *, count: int = 5) -> list:
        self._authorize(principal, Permission.RECURRENCE_READ)
        from ...domain.tasks.entities import RecurrenceRule

        anchor = recurrence.anchor_date or self._clock.today(principal.timezone)
        rule = RecurrenceRule(
            id="preview",
            owner_id=principal.id,
            name=recurrence.name,
            frequency=recurrence.frequency,
            interval=recurrence.interval,
            day_of_week=recurrence.day_of_week,
            anchor_date=anchor,
            end_type=recurrence.end_type,
            end_count=recurrence.end_count,
            end_date=recurrence.end_date,
            active=recurrence.active,
            created_at=self._clock.now_utc(),
        )
        # Inclusive of the anchor: preview the anchor date plus the following
        # occurrences, which is what the operator expects to see before saving.
        return preview_dates(rule, count=count, after_date=anchor - timedelta(days=1))
