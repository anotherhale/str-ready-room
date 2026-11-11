"""API integration tests through the real FastAPI app and real adapters.

Uses an isolated temporary SQLite database per test and the fixed clock, so the
whole HTTP surface is exercised end-to-end without mocks.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/api_test.db",
        operator_id="maverick",
        operator_display_name="Maverick",
        default_timezone="America/New_York",
        seed_on_startup=True,
        fixed_now_utc="2026-03-10T13:00:00",
    )
    import app.config as config_module
    import app.main as main_module

    # Patch before building the app so both app construction and the lifespan
    # use the isolated settings/database.
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)

    app = main_module.create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_me_returns_single_user_principal(client):
    resp = client.get("/api/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "maverick"
    assert body["display_name"] == "Maverick"


def test_dashboard_requires_no_login_and_returns_scan(client):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["greeting_name"] == "Maverick"
    assert "watch_label" in body
    # Seeded scenario produces content.
    assert len(body["today_tasks"]) >= 1


def test_create_update_complete_reopen_delete_flow(client):
    create = client.post(
        "/api/tasks",
        json={"title": "API task", "category": "General", "due_date": "2026-03-10", "priority": "high"},
    )
    assert create.status_code == 201, create.text
    task = create.json()
    task_id = task["id"]
    assert task["urgency"] == "due"

    patch = client.patch(f"/api/tasks/{task_id}", json={"title": "API task edited", "priority": "critical"})
    assert patch.status_code == 200
    assert patch.json()["title"] == "API task edited"

    complete = client.post(f"/api/tasks/{task_id}/complete")
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"

    reopen = client.post(f"/api/tasks/{task_id}/reopen")
    assert reopen.status_code == 200
    assert reopen.json()["status"] == "open"

    delete = client.delete(f"/api/tasks/{task_id}")
    assert delete.status_code == 204

    missing = client.get(f"/api/tasks/{task_id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_list_status_all_sentinel(client):
    client.post("/api/tasks", json={"title": "One", "category": "General"})
    resp = client.get("/api/tasks", params={"status": "all"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_validation_error_is_typed_422(client):
    resp = client.post("/api/tasks", json={"title": "", "category": "General"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "request_validation_error"


def test_bad_status_filter_is_400(client):
    resp = client.get("/api/tasks", params={"status": "bogus"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


def test_settings_and_categories_endpoints(client):
    get_settings = client.get("/api/settings")
    assert get_settings.status_code == 200
    assert get_settings.json()["warning_window_days"] == 3

    patch = client.patch("/api/settings", json={"warning_window_days": 5})
    assert patch.status_code == 200
    assert patch.json()["warning_window_days"] == 5

    create_cat = client.post("/api/categories", json={"name": "New Cat"})
    assert create_cat.status_code == 201
    dup = client.post("/api/categories", json={"name": "new cat"})
    assert dup.status_code == 409


def test_briefing_endpoint(client):
    resp = client.get("/api/briefing")
    assert resp.status_code == 200
    body = resp.json()
    assert "look_ahead" in body
    assert body["date"] == "2026-03-10"


def test_demo_reset_endpoint(client):
    resp = client.post("/api/demo/reset")
    assert resp.status_code == 200
    assert resp.json()["categories_restored"] >= 1
    # After reset, no tasks remain.
    tasks = client.get("/api/tasks", params={"status": "all"})
    assert tasks.json()["total"] == 0


def test_recurrence_preview_endpoint(client):
    resp = client.post(
        "/api/recurrence/preview",
        json={"frequency": "weekly", "day_of_week": 0, "anchor_date": "2026-03-09", "count": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["dates"] == ["2026-03-09", "2026-03-16", "2026-03-23"]
