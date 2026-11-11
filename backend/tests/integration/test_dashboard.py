"""Dashboard scan tests: Today/Watch/Horizon derived from real persisted tasks,
overdue visibility, completed exclusion, and configurable warning window."""
from __future__ import annotations

from datetime import date

from app.application.commands import CreateTaskCommand
from app.domain.tasks.enums import Urgency


def _mk(services, title, due):
    return services["tasks"].create_task(
        services["principal"], CreateTaskCommand(title=title, category="General", due_date=due)
    )


def test_dashboard_sections_derive_from_persisted_tasks(services):
    _mk(services, "Overdue", date(2026, 3, 8))
    _mk(services, "Due today", date(2026, 3, 10))
    _mk(services, "Watch", date(2026, 3, 12))
    _mk(services, "Horizon", date(2026, 3, 20))

    dash = services["dashboard"].build_dashboard(services["principal"])
    assert [t.title for t in dash.today_tasks] == ["Overdue", "Due today"]
    assert [t.title for t in dash.watch_tasks] == ["Watch"]
    assert [t.title for t in dash.horizon_tasks] == ["Horizon"]
    assert dash.counts.overdue == 1
    assert dash.counts.due == 1
    assert dash.counts.watch == 1
    assert dash.counts.horizon == 1
    assert dash.watch_label == "3-Day Watch"


def test_overdue_remains_visible_after_due_date_passes(services):
    _mk(services, "Old overdue", date(2026, 1, 1))
    dash = services["dashboard"].build_dashboard(services["principal"])
    assert any(t.title == "Old overdue" for t in dash.today_tasks)
    assert dash.today_tasks[0].urgency is Urgency.OVERDUE


def test_completed_tasks_excluded_from_active_sections(services):
    dto = _mk(services, "Finish me", date(2026, 3, 10))
    services["tasks"].complete_task(services["principal"], dto.id)
    dash = services["dashboard"].build_dashboard(services["principal"])
    all_titles = [t.title for t in dash.today_tasks + dash.watch_tasks + dash.horizon_tasks]
    assert "Finish me" not in all_titles
    assert dash.counts.completed_this_week == 1


def test_no_due_date_task_is_not_on_scan(services):
    services["tasks"].create_task(
        services["principal"], CreateTaskCommand(title="Someday", category="General")
    )
    dash = services["dashboard"].build_dashboard(services["principal"])
    all_titles = [t.title for t in dash.today_tasks + dash.watch_tasks + dash.horizon_tasks]
    assert "Someday" not in all_titles


def test_warning_window_changes_watch_label_and_membership(services):
    _mk(services, "Six days out", date(2026, 3, 16))
    dash = services["dashboard"].build_dashboard(services["principal"])
    assert any(t.title == "Six days out" for t in dash.horizon_tasks)

    # Widen the window to 7 days -> the task moves into Watch.
    from app.application.commands import UpdateSettingsCommand

    services["settings"].update_settings(services["principal"], UpdateSettingsCommand(warning_window_days=7))
    dash2 = services["dashboard"].build_dashboard(services["principal"])
    assert dash2.watch_label == "7-Day Watch"
    assert any(t.title == "Six days out" for t in dash2.watch_tasks)


def test_readiness_summary_reflects_counts(services):
    _mk(services, "Overdue", date(2026, 3, 1))
    dash = services["dashboard"].build_dashboard(services["principal"])
    assert "overdue" in dash.readiness_summary.lower()


def test_greeting_uses_principal_first_name(services):
    dash = services["dashboard"].build_dashboard(services["principal"])
    assert dash.greeting_name == "Maverick"
    assert dash.today == date(2026, 3, 10)
