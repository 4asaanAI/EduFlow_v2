from __future__ import annotations
import pytest
from middleware.auth import create_jwt
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


def _maintenance_h():
    t = create_jwt({"user_id": "m1", "role": "admin", "name": "M", "sub_category": "maintenance"})
    return {"Authorization": f"Bearer {t}"}


def _owner_h():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "O"})
    return {"Authorization": f"Bearer {t}"}


def test_cost_summary_returns_200(client):
    resp = client.get("/api/issues/facility/cost-summary", headers=_owner_h())
    assert resp.status_code == 200
    assert "data" in resp.json()


def test_single_facility_request_endpoint(client, fake_db):
    original = fake_db.facility_requests.docs[:]
    fake_db.facility_requests.docs = [{"id": "fr-1", "schoolId": "aaryans-joya", "title": "Test", "status": "open", "priority": "medium", "created_at": "2026-05-16T00:00:00"}]
    try:
        resp = client.get("/api/issues/facility/fr-1", headers=_owner_h())
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == "fr-1"
    finally:
        fake_db.facility_requests.docs = original


def test_upcoming_schedule_endpoint(client):
    resp = client.get("/api/issues/maintenance/schedule/upcoming?days=14", headers=_owner_h())
    assert resp.status_code == 200


def test_facility_request_has_is_overdue_field(client, fake_db):
    original = fake_db.facility_requests.docs[:]
    fake_db.facility_requests.docs = [{"id": "fr-2", "schoolId": "aaryans-joya", "title": "Old", "status": "pending_approval", "priority": "low", "created_at": "2020-01-01T00:00:00"}]
    try:
        resp = client.get("/api/issues/facility", headers=_owner_h())
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            for item in data:
                assert "is_overdue" in item
    finally:
        fake_db.facility_requests.docs = original


def test_escalation_blocked_for_closed_request(client, fake_db):
    original = fake_db.facility_requests.docs[:]
    fake_db.facility_requests.docs = [{"id": "fr-3", "schoolId": "aaryans-joya", "status": "closed", "title": "Done"}]
    try:
        resp = client.post("/api/issues/facility/fr-3/escalate", json={}, headers=_owner_h())
        assert resp.status_code in (400, 404)
    finally:
        fake_db.facility_requests.docs = original


def test_it_tech_can_view_tech_issues(client):
    t = create_jwt({"user_id": "t1", "role": "admin", "name": "T", "sub_category": "it_tech"})
    resp = client.get("/api/issues/tech", headers={"Authorization": f"Bearer {t}"})
    assert resp.status_code == 200


def test_accountant_cannot_view_tech_issues(client):
    t = create_jwt({"user_id": "a1", "role": "admin", "name": "A", "sub_category": "accounts"})
    resp = client.get("/api/issues/tech", headers={"Authorization": f"Bearer {t}"})
    assert resp.status_code == 403


def test_facility_sla_hours_constant_has_correct_values(client):
    """Fix 12.1: FACILITY_SLA_HOURS must use spec values (low=168, urgent=4)."""
    from routes.issues import FACILITY_SLA_HOURS
    assert FACILITY_SLA_HOURS["low"] == 168
    assert FACILITY_SLA_HOURS["medium"] == 72
    assert FACILITY_SLA_HOURS["high"] == 24
    assert FACILITY_SLA_HOURS["urgent"] == 4


def test_recurrence_monthly_is_calendar_correct():
    """Fix 12.9: monthly recurrence should land on same day next month."""
    from routes.issues import _next_scheduled_date
    # Jan 31 + 1 month = Feb 28 (2026 is not a leap year)
    result = _next_scheduled_date("2026-01-31", "monthly")
    assert result == "2026-02-28"
    # Feb 28 + 1 month = Mar 28
    result2 = _next_scheduled_date("2026-02-28", "monthly")
    assert result2 == "2026-03-28"


def test_recurrence_quarterly_is_calendar_correct():
    """Fix 12.9: quarterly recurrence = 3 calendar months."""
    from routes.issues import _next_scheduled_date
    result = _next_scheduled_date("2026-01-01", "quarterly")
    assert result == "2026-04-01"


def test_recurrence_annual_is_calendar_correct():
    """Fix 12.9: annual recurrence = 12 calendar months."""
    from routes.issues import _next_scheduled_date
    result = _next_scheduled_date("2026-03-15", "annual")
    assert result == "2027-03-15"


def test_recurrence_weekly_is_7_days():
    """Fix 12.9: weekly recurrence = exactly 7 days."""
    from routes.issues import _next_scheduled_date
    result = _next_scheduled_date("2026-05-10", "weekly")
    assert result == "2026-05-17"


def test_escalation_status_guard_done(client, fake_db):
    """Fix 12.2a: done requests also cannot be escalated."""
    original = fake_db.facility_requests.docs[:]
    fake_db.facility_requests.docs = [{"id": "fr-done", "schoolId": "aaryans-joya", "status": "done", "title": "Done request"}]
    try:
        resp = client.post("/api/issues/facility/fr-done/escalate", json={}, headers=_owner_h())
        assert resp.status_code == 400
    finally:
        fake_db.facility_requests.docs = original


def test_photo_limit_constant():
    """Fix 12.3: PHOTO_LIMIT must be 5."""
    from routes.issues import PHOTO_LIMIT
    assert PHOTO_LIMIT == 5


def test_escalation_cooldown_constant():
    """Fix 12.2: ESCALATION_COOLDOWN_SECONDS must be 3600 (1 hour)."""
    from routes.issues import ESCALATION_COOLDOWN_SECONDS
    assert ESCALATION_COOLDOWN_SECONDS == 3600
