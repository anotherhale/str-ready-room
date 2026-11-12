"""Demo data service: idempotent synthetic seed and reset.

Seed data is entirely synthetic (a fictional detachment, made-up names).  Due
dates are anchored relative to the operator's local today so the demonstration
always looks current.  Seeding is guarded by a ``seed_version`` marker *and* an
"any tasks exist?" check so restarting containers never duplicates data.
"""
from __future__ import annotations

from datetime import date, timedelta

from ...domain.authorization.permissions import Permission
from ...domain.settings.entities import (
    CURRENT_SEED_VERSION,
    DEFAULT_CATEGORIES,
    Category,
    OperatorSettings,
)
from ...domain.shared.clock import Clock
from ...domain.shared.errors import AuthorizationError
from ...domain.tasks.entities import RecurrenceRule, Task
from ...domain.tasks.enums import EndType, Frequency, Priority
from ...domain.tasks.recurrence import first_occurrence
from ..dto import ResetResultDTO
from ..ports.clock import IdGenerator
from ..ports.identity import AuthorizationPort
from ..ports.persistence import DatabaseFactoryPort, TaskQuery
from .category_service import CategoryService
from .integration_seed_service import IntegrationSeedService


class DemoService:
    def __init__(
        self,
        database: DatabaseFactoryPort,
        authorizer: AuthorizationPort,
        clock: Clock,
        ids: IdGenerator,
        *,
        integration_seed: IntegrationSeedService | None = None,
        calendar=None,  # noqa: ANN001 - CalendarService, optional integration
    ) -> None:
        self._database = database
        self._authorizer = authorizer
        self._clock = clock
        self._ids = ids
        self._categories = CategoryService(database, authorizer, clock, ids)
        # Optional integrations.  Both are best-effort and never raise, so the
        # base stack (no providers configured) is unaffected (see DECISIONS
        # D-028/D-034).
        self._integration_seed = integration_seed
        self._calendar = calendar

    def _authorize(self, principal, permission: Permission) -> None:
        decision = self._authorizer.authorize(principal, permission)
        if not decision.allowed:
            raise AuthorizationError(decision.reason, code=decision.code)

    # -- reset ---------------------------------------------------------
    def reset(self, principal) -> ResetResultDTO:
        """Clear application data, restore defaults, and reseed the scenario.

        The reset returns the operator to the *intended demonstration state*
        immediately, not an empty board: it clears data and restores default
        categories/settings, then repopulates the synthetic scenario so the
        dashboard is populated the moment the request returns.
        """
        self._authorize(principal, Permission.DEMO_RESET)
        now = self._clock.now_utc()
        with self._database.create() as uow:
            tasks = uow.tasks.list(TaskQuery(include_all_statuses=True), principal.id)
            for task in tasks:
                uow.tasks.delete(task.id, principal.id)

            rules = uow.recurrence_rules.list_all(principal.id)
            for rule in rules:
                uow.recurrence_rules.delete(rule.id, principal.id)

            # Clear cached integration data too, so a reset is a true clean slate.
            for event in uow.calendar_events.list(principal.id):
                uow.calendar_events.delete(event.id, principal.id)
            for source in uow.email_sources.list(principal.id):
                uow.email_sources.delete(source.id, principal.id)

            # Remove all categories, then restore the defaults.
            for category in uow.categories.list(principal.id, include_inactive=True):
                uow.categories.delete(category.id, principal.id)

            restored = 0
            for name in DEFAULT_CATEGORIES:
                uow.categories.save(
                    Category(
                        id=self._ids.new_id(),
                        owner_id=principal.id,
                        name=name,
                        created_at=now,
                        is_default=True,
                    )
                )
                restored += 1

            settings = uow.settings.get(principal.id) or OperatorSettings(owner_id=principal.id)
            settings.warning_window_days = 3
            settings.timezone = principal.timezone
            settings.seed_version = 0
            settings.calendar_seed_version = 0
            settings.email_seed_version = 0
            settings.updated_at = now
            uow.settings.save(settings)

            uow.commit()

        # Repopulate the demonstration scenario in its own transaction so the
        # reset leaves the board populated, not blank.  Seeding after the clear
        # commit keeps the two steps independent: a seed failure still leaves a
        # clean, empty state rather than a half-cleared one.
        self.seed(principal)

        # Restore the optional integrations too, so a reset returns the whole
        # demo to its intended state.  Both are best-effort and never raise.
        self._reseed_integrations(principal)

        return ResetResultDTO(
            tasks_deleted=len(tasks), rules_deleted=len(rules), categories_restored=restored
        )

    def _reseed_integrations(self, principal) -> None:  # noqa: ANN001
        """Best-effort: restore the demo calendar events and mailbox messages.

        The clear step above already removed the cached calendar events and the
        integration seed markers, so the seeders repopulate from scratch.  The
        mailbox seeder is additionally idempotent on the demo Message-IDs, so a
        reset can never duplicate mail that is still present in the mail server.
        """
        if self._integration_seed is None:
            return
        try:
            self._integration_seed.seed_calendar_if_needed(principal)
            self._integration_seed.seed_mailbox_if_needed(principal)
        except Exception:  # noqa: BLE001 - a reset must not fail on an optional service
            return
        # Refresh the calendar cache from the provider so the Calendar view is
        # populated immediately, without waiting for a manual sync.
        if self._calendar is not None:
            self._calendar.sync_quietly(principal)

    # -- seed ----------------------------------------------------------
    def seed_if_needed(self, principal) -> bool:
        """Seed only when the operator has no tasks and no seed marker."""
        with self._database.create() as uow:
            settings = uow.settings.get(principal.id)
            if settings is not None and settings.seed_version >= CURRENT_SEED_VERSION:
                return False
            if uow.tasks.exists_any(principal.id):
                return False
        self.seed(principal)
        return True

    def seed(self, principal) -> None:
        """Create the synthetic demonstration scenario for the operator."""
        now = self._clock.now_utc()
        today = self._clock.today(principal.timezone)

        with self._database.create() as uow:
            # Settings (create if missing) with the current seed marker.
            settings = uow.settings.get(principal.id)
            if settings is None:
                settings = OperatorSettings(owner_id=principal.id, timezone=principal.timezone)
            settings.seed_version = CURRENT_SEED_VERSION
            settings.updated_at = now
            uow.settings.save(settings)

            # Default categories if none exist.
            if uow.categories.count(principal.id) == 0:
                for name in DEFAULT_CATEGORIES:
                    uow.categories.save(
                        Category(
                            id=self._ids.new_id(),
                            owner_id=principal.id,
                            name=name,
                            created_at=now,
                            is_default=True,
                        )
                    )

            # --- recurring rules -------------------------------------
            monday_brief_rule = self._weekly_rule(
                principal, now, today, name="Monday morning detachment brief", weekday=0
            )
            uow.recurrence_rules.save(monday_brief_rule)
            monday_first = first_occurrence(monday_brief_rule)
            monday_rule_next = self._next_after(monday_brief_rule, monday_first)
            monday_brief_rule.occurrences_generated = 1
            monday_brief_rule.next_occurrence = monday_rule_next
            uow.recurrence_rules.save(monday_brief_rule)

            friday_rollup_rule = self._weekly_rule(
                principal, now, today, name="Friday status roll-up", weekday=4
            )
            uow.recurrence_rules.save(friday_rollup_rule)
            friday_first = first_occurrence(friday_rollup_rule)
            friday_rollup_rule.occurrences_generated = 1
            friday_rollup_rule.next_occurrence = self._next_after(friday_rollup_rule, friday_first)
            uow.recurrence_rules.save(friday_rollup_rule)

            currency_rule = RecurrenceRule(
                id=self._ids.new_id(),
                owner_id=principal.id,
                name="Quarterly currency paperwork",
                frequency=Frequency.QUARTERLY,
                interval=1,
                anchor_date=today + timedelta(days=12),
                end_type=EndType.NEVER,
                active=True,
                created_at=now,
                occurrences_generated=1,
            )
            currency_rule.next_occurrence = self._next_after(currency_rule, currency_rule.anchor_date)
            uow.recurrence_rules.save(currency_rule)

            # --- tasks ------------------------------------------------
            # Recurring occurrences (today / near-term)
            uow.tasks.save(
                self._task(
                    principal,
                    now,
                    title="Prepare Monday morning detachment brief",
                    category="Detachment Operations",
                    due_date=monday_first,
                    priority=Priority.HIGH,
                    description="Weekly brief for the detachment: flying schedule, maintenance status, admin items.",
                    rule=monday_brief_rule,
                    occurrence_number=1,
                )
            )
            uow.tasks.save(
                self._task(
                    principal,
                    now,
                    title="Publish Friday status roll-up",
                    category="Detachment Operations",
                    due_date=friday_first,
                    priority=Priority.NORMAL,
                    description="Consolidate the week's status for the ready room board.",
                    rule=friday_rollup_rule,
                    occurrence_number=1,
                )
            )
            uow.tasks.save(
                self._task(
                    principal,
                    now,
                    title="Prepare quarterly currency paperwork",
                    category="Flight Administration",
                    due_date=currency_rule.anchor_date,
                    priority=Priority.NORMAL,
                    description="Gather currency evidence for the quarter and route for review.",
                    rule=currency_rule,
                    occurrence_number=1,
                )
            )

            # One-off tasks relative to today
            uow.tasks.save(
                self._task(
                    principal,
                    now,
                    title="Review maintenance documentation requiring sign-off",
                    category="Maintenance",
                    due_date=today,
                    priority=Priority.HIGH,
                    description="Two discrepancy write-ups awaiting detachment officer signature.",
                )
            )
            uow.tasks.save(
                self._task(
                    principal,
                    now,
                    title="Submit updated detachment training records",
                    category="Personnel",
                    due_date=today - timedelta(days=2),
                    priority=Priority.CRITICAL,
                    description="Training jacket updates overdue to the squadron admin office.",
                )
            )
            uow.tasks.save(
                self._task(
                    principal,
                    now,
                    title="Contact machine shop regarding tow bar inspection",
                    category="Maintenance",
                    due_date=today + timedelta(days=2),
                    priority=Priority.HIGH,
                    description="Confirm inspection window for the tow bar before the next evolution.",
                )
            )
            uow.tasks.save(
                self._task(
                    principal,
                    now,
                    title="Review upcoming personnel qualification paperwork",
                    category="Personnel",
                    due_date=today + timedelta(days=3),
                    priority=Priority.NORMAL,
                    description="Two qualification packages need detachment officer review.",
                )
            )
            uow.tasks.save(
                self._task(
                    principal,
                    now,
                    title="Review next week's administrative requirements",
                    category="Flight Administration",
                    due_date=today + timedelta(days=10),
                    priority=Priority.NORMAL,
                    description="Scan the upcoming week for admin deadlines and dependencies.",
                )
            )
            uow.tasks.save(
                self._task(
                    principal,
                    now,
                    title="Inventory detachment logistics consumables",
                    category="Logistics",
                    due_date=today + timedelta(days=21),
                    priority=Priority.LOW,
                    description="Count consumables and flag anything below the reorder threshold.",
                )
            )

            # A recently completed task, so the dashboard shows healthy history.
            completed = self._task(
                principal,
                now,
                title="Update detachment leave plan for the coming month",
                category="Personnel",
                due_date=today - timedelta(days=1),
                priority=Priority.NORMAL,
                description="Leave plan reviewed and forwarded to the squadron.",
            )
            completed.complete(now - timedelta(days=1))
            uow.tasks.save(completed)

            uow.commit()

    # -- helpers -------------------------------------------------------
    def _weekly_rule(self, principal, now, today: date, *, name: str, weekday: int) -> RecurrenceRule:
        # Anchor the weekly rule so its first occurrence is today's week start.
        return RecurrenceRule(
            id=self._ids.new_id(),
            owner_id=principal.id,
            name=name,
            frequency=Frequency.WEEKLY,
            interval=1,
            day_of_week=weekday,
            anchor_date=today,
            end_type=EndType.NEVER,
            active=True,
            created_at=now,
        )

    @staticmethod
    def _next_after(rule: RecurrenceRule, current: date) -> date | None:
        from ...domain.tasks.recurrence import plan_next

        return plan_next(rule, current).date

    def _task(
        self, principal, now, *, title, category, due_date, priority, description, rule=None, occurrence_number=1
    ) -> Task:
        series_id = None
        rule_id = None
        if rule is not None:
            series_id = self._ids.new_id()
            rule_id = rule.id
        return Task.create(
            id=self._ids.new_id(),
            owner_id=principal.id,
            title=title,
            category=category,
            now=now,
            priority=priority,
            description=description,
            due_date=due_date,
            series_id=series_id,
            recurrence_rule_id=rule_id,
            occurrence_number=occurrence_number,
        )
