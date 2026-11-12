"""Seed idempotency and demo reset tests."""
from __future__ import annotations

from datetime import date, timedelta

from app.application.commands import ListTasksQuery
from app.application.ports.persistence import TaskQuery
from app.domain.settings.entities import DEFAULT_CATEGORIES


def test_seed_creates_scenario_and_is_idempotent(services):
    principal = services["principal"]
    assert services["demo"].seed_if_needed(principal) is True

    dash = services["dashboard"].build_dashboard(principal)
    # The scenario must produce today, watch, and horizon items.
    assert len(dash.today_tasks) >= 1
    assert len(dash.watch_tasks) >= 1
    assert len(dash.horizon_tasks) >= 1

    with services["database"].create() as uow:
        count_first = len(uow.tasks.list(TaskQuery(include_all_statuses=True), principal.id))

    # Seeding again is a no-op.
    assert services["demo"].seed_if_needed(principal) is False
    with services["database"].create() as uow:
        count_second = len(uow.tasks.list(TaskQuery(include_all_statuses=True), principal.id))
    assert count_first == count_second


def test_seed_skips_when_tasks_already_exist(services):
    principal = services["principal"]
    from app.application.commands import CreateTaskCommand

    services["tasks"].create_task(principal, CreateTaskCommand(title="Existing", category="General"))
    # Even without a seed marker, an existing task prevents reseeding.
    assert services["demo"].seed_if_needed(principal) is False


def test_seed_due_dates_are_relative_to_today(services):
    principal = services["principal"]
    services["demo"].seed_if_needed(principal)
    items = services["tasks"].list_tasks(principal, ListTasksQuery(status="all"))
    today = date(2026, 3, 10)
    # The overdue item must be two days in the past.
    overdue = [i for i in items if i.title.startswith("Submit updated detachment training records")]
    assert overdue and overdue[0].due_date == today - timedelta(days=2)


def test_reset_clears_data_and_restores_defaults(services):
    principal = services["principal"]
    services["demo"].seed_if_needed(principal)
    result = services["demo"].reset(principal)
    assert result.tasks_deleted >= 1
    assert result.rules_deleted >= 1
    assert result.categories_restored == len(DEFAULT_CATEGORIES)

    # Defaults restored, settings reset.
    settings = services["settings"].get_settings(principal)
    assert sorted(c.name for c in settings.categories) == sorted(DEFAULT_CATEGORIES)
    assert settings.warning_window_days == 3

    # Reset returns the operator to the intended demonstration state
    # immediately: the scenario is reseeded, not left blank.
    dash = services["dashboard"].build_dashboard(principal)
    assert len(dash.today_tasks) >= 1
    assert len(dash.watch_tasks) >= 1
    assert len(dash.horizon_tasks) >= 1


def test_reset_is_repeatable_and_does_not_accumulate(services):
    principal = services["principal"]
    services["demo"].seed_if_needed(principal)

    first = services["demo"].reset(principal)
    count_first = services["tasks"].list_tasks(principal, ListTasksQuery(status="all"))
    # A second reset clears the reseeded scenario and reseeds again: the board
    # returns to the same shape rather than growing.
    second = services["demo"].reset(principal)
    count_second = services["tasks"].list_tasks(principal, ListTasksQuery(status="all"))

    assert first.tasks_deleted >= 1
    assert second.tasks_deleted >= 1
    assert len(count_first) == len(count_second)
