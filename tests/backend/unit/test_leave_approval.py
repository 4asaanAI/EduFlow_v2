from __future__ import annotations
import pytest
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _principal_headers():
    t = create_jwt({"user_id": "prin-1", "role": "admin", "name": "Principal", "sub_category": "principal"})
    return {"Authorization": f"Bearer {t}"}


def _accountant_headers():
    t = create_jwt({"user_id": "acct-1", "role": "admin", "name": "Accountant", "sub_category": "accountant"})
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(autouse=True)
def _clean_leave(fake_db):
    """Reset leave_requests and notifications before/after each test."""
    fake_db.leave_requests.docs[:] = []
    fake_db.notifications.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    yield
    fake_db.leave_requests.docs[:] = []
    fake_db.notifications.docs[:] = []
    fake_db.audit_logs.docs[:] = []


def test_approve_leave_creates_notification(client, fake_db):
    """Approving a leave creates a notification for the staff member."""
    fake_db.leave_requests.docs = [{
        "id": "lr-1", "schoolId": "aaryans-joya", "status": "pending",
        "staff_id": "s1", "user_id": "u1",
        "start_date": "2026-06-01", "end_date": "2026-06-03",
    }]
    resp = client.patch("/api/staff/leaves/lr-1", json={"status": "approved"}, headers=_principal_headers())
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # A notification should have been created for user u1
    notif = next((n for n in fake_db.notifications.docs if n.get("user_id") == "u1"), None)
    assert notif is not None
    assert "approved" in notif["message"].lower()


def test_reject_leave_creates_notification(client, fake_db):
    """Rejecting a leave creates a notification for the staff member."""
    fake_db.leave_requests.docs = [{
        "id": "lr-2", "schoolId": "aaryans-joya", "status": "pending",
        "staff_id": "s2", "user_id": "u2",
        "start_date": "2026-06-05", "end_date": "2026-06-05",
    }]
    resp = client.patch(
        "/api/staff/leaves/lr-2",
        json={"status": "rejected", "rejection_reason": "Staff needed"},
        headers=_principal_headers(),
    )
    assert resp.status_code == 200
    notif = next((n for n in fake_db.notifications.docs if n.get("user_id") == "u2"), None)
    assert notif is not None
    assert "rejected" in notif["message"].lower()


def test_double_approve_returns_409(client, fake_db):
    """Approving an already-approved leave returns 409."""
    fake_db.leave_requests.docs = [{
        "id": "lr-3", "schoolId": "aaryans-joya", "status": "approved",
        "staff_id": "s3", "user_id": "u3",
        "start_date": "2026-06-10", "end_date": "2026-06-10",
    }]
    resp = client.patch("/api/staff/leaves/lr-3", json={"status": "approved"}, headers=_principal_headers())
    assert resp.status_code == 409


def test_approve_missing_leave_returns_404(client, fake_db):
    """Approving a non-existent leave returns 404."""
    resp = client.patch("/api/staff/leaves/no-such-id", json={"status": "approved"}, headers=_principal_headers())
    assert resp.status_code == 404


def test_accountant_cannot_approve_leave(client, fake_db):
    """Accountant sub_category cannot approve leaves — only owner/principal."""
    fake_db.leave_requests.docs = [{"id": "lr-4", "schoolId": "aaryans-joya", "status": "pending"}]
    resp = client.patch("/api/staff/leaves/lr-4", json={"status": "approved"}, headers=_accountant_headers())
    assert resp.status_code == 403
