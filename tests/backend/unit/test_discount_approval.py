from __future__ import annotations

import pytest
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _owner_h():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "O"})
    return {"Authorization": f"Bearer {t}"}


def _accountant_h():
    t = create_jwt({"user_id": "a1", "role": "admin", "name": "A", "sub_category": "accounts"})
    return {"Authorization": f"Bearer {t}"}


def _principal_h():
    t = create_jwt({"user_id": "p1", "role": "admin", "name": "P", "sub_category": "principal"})
    return {"Authorization": f"Bearer {t}"}


def test_discount_below_threshold_applied_immediately(client, fake_db):
    """Small discount (500) applied immediately — no pending approval created."""
    fake_db.fee_discount_types.docs = [
        {
            "id": "dt-1",
            "schoolId": "aaryans-joya",
            "value_type": "flat",
            "value": 500,
            "name": "Small",
            "is_active": True,
        }
    ]
    resp = client.post(
        "/api/fees/discounts/apply",
        json={
            "student_id": "stu-1",
            "discount_type_id": "dt-1",
            "original_amount": 5000,
            "effective_from": "2026-05-01",
        },
        headers=_accountant_h(),
    )
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    assert data.get("success") is True
    assert data.get("pending_approval") is not True


def test_discount_above_threshold_creates_pending_approval(client, fake_db):
    """Large discount (50000 > 10000 threshold) routes to pending approval (202)."""
    fake_db.fee_discount_types.docs = [
        {
            "id": "dt-2",
            "schoolId": "aaryans-joya",
            "value_type": "flat",
            "value": 50000,
            "name": "Large",
            "is_active": True,
        }
    ]
    resp = client.post(
        "/api/fees/discounts/apply",
        json={"student_id": "stu-1", "discount_type_id": "dt-2"},
        headers=_accountant_h(),
    )
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data.get("pending_approval") is True


def test_owner_can_list_pending_approvals(client, fake_db):
    """Owner can view pending discount approval queue."""
    fake_db.pending_discount_approvals.docs = []
    resp = client.get("/api/fees/discounts/pending-approvals", headers=_owner_h())
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


def test_non_owner_cannot_list_pending_approvals(client):
    """Accountant cannot view pending approvals — owner-only endpoint."""
    resp = client.get("/api/fees/discounts/pending-approvals", headers=_accountant_h())
    assert resp.status_code == 403


def test_discount_missing_type_returns_404(client, fake_db):
    """Applying a non-existent discount type returns 404."""
    fake_db.fee_discount_types.docs = []
    resp = client.post(
        "/api/fees/discounts/apply",
        json={"student_id": "stu-1", "discount_type_id": "nonexistent"},
        headers=_owner_h(),
    )
    assert resp.status_code == 404


def test_discount_missing_fields_returns_400(client, fake_db):
    """Missing student_id/discount_type_id returns 400."""
    resp = client.post(
        "/api/fees/discounts/apply",
        json={"student_id": "stu-1"},
        headers=_owner_h(),
    )
    assert resp.status_code == 400


def test_owner_can_approve_pending_discount(client, fake_db):
    """Owner can approve a pending discount application."""
    fake_db.pending_discount_approvals.docs = [
        {
            "id": "pa-1",
            "schoolId": "aaryans-joya",
            "student_id": "stu-1",
            "discount_type_id": "dt-2",
            "discount_amount": 50000.0,
            "requested_by": "a1",
            "status": "pending",
            "created_at": "2026-05-16T00:00:00+00:00",
        }
    ]
    resp = client.patch(
        "/api/fees/discounts/pending-approvals/pa-1/approve",
        headers=_owner_h(),
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_owner_can_reject_pending_discount(client, fake_db):
    """Owner can reject a pending discount application."""
    fake_db.pending_discount_approvals.docs = [
        {
            "id": "pa-2",
            "schoolId": "aaryans-joya",
            "student_id": "stu-2",
            "discount_type_id": "dt-2",
            "discount_amount": 50000.0,
            "requested_by": "a1",
            "status": "pending",
            "created_at": "2026-05-16T00:00:00+00:00",
        }
    ]
    resp = client.patch(
        "/api/fees/discounts/pending-approvals/pa-2/reject",
        headers=_owner_h(),
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
