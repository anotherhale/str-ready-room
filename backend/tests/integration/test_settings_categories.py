"""Settings and category integration tests."""
from __future__ import annotations

from datetime import date

import pytest

from app.application.commands import (
    CreateCategoryCommand,
    CreateTaskCommand,
    RecurrenceInput,
    UpdateCategoryCommand,
    UpdateSettingsCommand,
)
from app.domain.settings.entities import DEFAULT_CATEGORIES
from app.domain.shared.errors import ConflictError, ValidationError
from app.domain.tasks.enums import Frequency


def test_default_categories_seeded(services):
    settings = services["settings"].get_settings(services["principal"])
    names = [c.name for c in settings.categories]
    assert sorted(names) == sorted(DEFAULT_CATEGORIES)


def test_update_warning_window_and_timezone(services):
    dto = services["settings"].update_settings(
        services["principal"], UpdateSettingsCommand(warning_window_days=10, timezone="America/Chicago")
    )
    assert dto.warning_window_days == 10
    assert dto.timezone == "America/Chicago"


def test_invalid_warning_window_rejected(services):
    with pytest.raises(ValidationError):
        services["settings"].update_settings(
            services["principal"], UpdateSettingsCommand(warning_window_days=0)
        )


def test_invalid_timezone_rejected(services):
    with pytest.raises(ValidationError):
        services["settings"].update_settings(
            services["principal"], UpdateSettingsCommand(timezone="Not/AZone")
        )


def test_create_category_normalizes_and_rejects_duplicates(services):
    created = services["categories"].create_category(
        services["principal"], CreateCategoryCommand(name="  Flight   Ops ")
    )
    assert created.name == "Flight Ops"
    with pytest.raises(ConflictError):
        services["categories"].create_category(services["principal"], CreateCategoryCommand(name="flight ops"))


def test_rename_category_and_detect_conflict(services):
    a = services["categories"].create_category(services["principal"], CreateCategoryCommand(name="Alpha"))
    services["categories"].create_category(services["principal"], CreateCategoryCommand(name="Beta"))
    renamed = services["categories"].update_category(
        services["principal"], a.id, UpdateCategoryCommand(name="Gamma")
    )
    assert renamed.name == "Gamma"
    with pytest.raises(ConflictError):
        services["categories"].update_category(services["principal"], a.id, UpdateCategoryCommand(name="Beta"))


def test_delete_default_category_deactivates_it(services):
    settings = services["settings"].get_settings(services["principal"])
    default = next(c for c in settings.categories if c.is_default)
    services["categories"].delete_category(services["principal"], default.id)
    active = services["categories"].list_categories(services["principal"])
    assert all(c.name != default.name for c in active)  # hidden from active list
    # but still present when inactive included
    all_cats = services["categories"].list_categories(services["principal"], include_inactive=True)
    assert any(c.name == default.name and not c.active for c in all_cats)


def test_delete_custom_category_removes_it(services):
    custom = services["categories"].create_category(services["principal"], CreateCategoryCommand(name="Custom"))
    services["categories"].delete_category(services["principal"], custom.id)
    all_cats = services["categories"].list_categories(services["principal"], include_inactive=True)
    assert all(c.name != "Custom" for c in all_cats)


def test_recurrence_preview_endpoint_logic(services):
    from app.application.commands import RecurrenceInput

    dates = services["recurrence"].preview(
        services["principal"],
        RecurrenceInput(
            name="Weekly", frequency=Frequency.WEEKLY, day_of_week=0, anchor_date=date(2026, 3, 9)
        ),
        count=3,
    )
    assert dates == [date(2026, 3, 9), date(2026, 3, 16), date(2026, 3, 23)]


def test_recurrence_overview_lists_rules(services):
    services["tasks"].create_task(
        services["principal"],
        CreateTaskCommand(
            title="Weekly", category="General", due_date=date(2026, 3, 9),
            recurrence=RecurrenceInput(name="Weekly", frequency=Frequency.WEEKLY, day_of_week=0, anchor_date=date(2026, 3, 9)),
        ),
    )
    overview = services["recurrence"].overview(services["principal"])
    assert len(overview.rules) == 1
    assert overview.rules[0].name == "Weekly"


def test_settings_update_persists_every_mapped_field(services):
    """Regression: ``save`` must persist *all* mapped settings columns.

    The update branch previously assigned fields by hand, so a newly added
    settings field (``demo_arrival_seq``) was silently dropped on update.  This
    guards against that class of bug for any future field.
    """
    from app.domain.settings.entities import OperatorSettings

    principal = services["principal"]
    database = services["database"]

    with database.create() as uow:
        settings = uow.settings.get(principal.id) or OperatorSettings(owner_id=principal.id)
        settings.demo_arrival_seq = 7
        settings.seed_version = 2
        uow.settings.save(settings)
        uow.commit()

    with database.create() as uow:
        reloaded = uow.settings.get(principal.id)
    assert reloaded is not None
    assert reloaded.demo_arrival_seq == 7
    assert reloaded.seed_version == 2
