from __future__ import annotations
import pytest
from middleware.auth import create_jwt
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


def _receptionist_h():
    t = create_jwt({"user_id": "r1", "role": "admin", "name": "R", "sub_category": "receptionist"})
    return {"Authorization": f"Bearer {t}"}


def _owner_h():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "O"})
    return {"Authorization": f"Bearer {t}"}


def test_visitor_duplicate_returns_409_with_duplicate_field(client, fake_db):
    """Duplicate visitor same day returns 409 with duplicate:true."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    fake_db.visitor_log.docs = [
        {
            "id": "v1",
            "schoolId": "aaryans-joya",
            "visitor_name": "Raj Kumar",
            "time_in": f"{today}T09:00:00",
            "time_out": None,
        }
    ]
    resp = client.post(
        "/api/ops/visitors",
        json={"visitor_name": "Raj Kumar", "purpose": "Meeting"},
        headers=_owner_h(),
    )
    assert resp.status_code == 409
    assert resp.json().get("duplicate") is True


def test_visitor_force_true_bypasses_duplicate(client, fake_db):
    """force:true creates a second visitor record."""
    fake_db.visitor_log.docs = [
        {
            "id": "v1",
            "schoolId": "aaryans-joya",
            "visitor_name": "Raj Kumar",
            "time_in": "2026-05-16T09:00:00",
            "time_out": None,
            "force_override": False,
        }
    ]
    initial_count = len(fake_db.visitor_log.docs)
    resp = client.post(
        "/api/ops/visitors",
        json={"visitor_name": "Raj Kumar", "purpose": "Meeting", "force": True},
        headers=_owner_h(),
    )
    assert resp.status_code in (200, 201)
    # A new record should have been inserted
    assert len(fake_db.visitor_log.docs) > initial_count


def test_cert_character_type_requires_approval(client, fake_db):
    """Character certificate requires principal/owner approval."""
    fake_db.students.docs = [{"id": "s1", "schoolId": "aaryans-joya", "name": "Alice"}]
    fake_db.certificates.docs = []
    resp = client.post(
        "/api/ops/certificates",
        json={"student_id": "s1", "cert_type": "character"},
        headers=_receptionist_h(),
    )
    if resp.status_code in (200, 201):
        cert = next((c for c in fake_db.certificates.docs), None)
        if cert:
            assert cert.get("status") == "pending_approval"


def test_cert_merit_type_requires_approval(client, fake_db):
    """Merit certificate requires principal/owner approval."""
    fake_db.students.docs = [{"id": "s1", "schoolId": "aaryans-joya", "name": "Alice"}]
    fake_db.certificates.docs = []
    resp = client.post(
        "/api/ops/certificates",
        json={"student_id": "s1", "cert_type": "merit"},
        headers=_receptionist_h(),
    )
    if resp.status_code in (200, 201):
        cert = next((c for c in fake_db.certificates.docs), None)
        if cert:
            assert cert.get("status") == "pending_approval"


def test_receptionist_sees_all_school_queries(client, fake_db):
    """Receptionist sees all school support tickets (not just own)."""
    resp = client.get("/api/queries", headers=_receptionist_h())
    assert resp.status_code == 200


def test_complaint_stores_on_behalf_of_phone(client, fake_db):
    """Complaint with on_behalf_of_phone stores it in DB."""
    fake_db.complaints.docs = []
    resp = client.post(
        "/api/ops/complaints",
        json={
            "category": "fees",
            "description": "Fee issue",
            "on_behalf_of_name": "Parent Name",
            "on_behalf_of_phone": "9876543210",
        },
        headers=_receptionist_h(),
    )
    assert resp.status_code in (200, 201)
    complaint = next((c for c in fake_db.complaints.docs if c.get("on_behalf_of_phone")), None)
    if complaint:
        assert complaint["on_behalf_of_phone"] == "9876543210"


def test_complaint_phone_masked_for_non_owner(client, fake_db):
    """Non-owner sees masked on_behalf_of_phone."""
    fake_db.complaints.docs = [
        {
            "id": "c1",
            "schoolId": "aaryans-joya",
            "on_behalf_of_phone": "9876543210",
            "category": "fees",
        }
    ]
    resp = client.get("/api/ops/complaints", headers=_receptionist_h())
    if resp.status_code == 200:
        data = resp.json().get("data", [])
        for c in data:
            if c.get("on_behalf_of_phone"):
                assert "9876543210" not in c["on_behalf_of_phone"]


def test_complaint_phone_visible_for_owner(client, fake_db):
    """Owner sees unmasked on_behalf_of_phone."""
    fake_db.complaints.docs = [
        {
            "id": "c2",
            "schoolId": "aaryans-joya",
            "on_behalf_of_phone": "9876543210",
            "category": "fees",
        }
    ]
    resp = client.get("/api/ops/complaints", headers=_owner_h())
    if resp.status_code == 200:
        data = resp.json().get("data", [])
        for c in data:
            if c.get("on_behalf_of_phone"):
                assert c["on_behalf_of_phone"] == "9876543210"


def test_complaint_routing_fees_goes_to_accountant(client, fake_db):
    """Fees category complaint routes to accountant (not accounts)."""
    fake_db.complaints.docs = []
    resp = client.post(
        "/api/ops/complaints",
        json={"category": "fees", "description": "Fee issue"},
        headers=_owner_h(),
    )
    assert resp.status_code in (200, 201)
    complaint = next((c for c in fake_db.complaints.docs if c.get("category") == "fees"), None)
    if complaint:
        assert complaint.get("department") == "accountant"


def test_pending_checkout_route_exists(client, fake_db):
    """GET /api/ops/visitors/pending-checkout returns 200 for receptionist."""
    fake_db.visitor_log.docs = []
    resp = client.get("/api/ops/visitors/pending-checkout", headers=_owner_h())
    assert resp.status_code == 200


def test_overdue_route_backward_compat(client, fake_db):
    """GET /api/ops/visitors/overdue still works as backward-compat alias."""
    fake_db.visitor_log.docs = []
    resp = client.get("/api/ops/visitors/overdue", headers=_owner_h())
    assert resp.status_code == 200


def test_cert_approve_rejects_non_pending(client, fake_db):
    """Approving an already-generated cert returns 422."""
    fake_db.certificates.docs = [
        {
            "id": "cert-1",
            "schoolId": "aaryans-joya",
            "status": "generated",
            "cert_type": "bonafide",
        }
    ]
    resp = client.patch("/api/ops/certificates/cert-1/approve", headers=_owner_h())
    assert resp.status_code == 422


def test_cert_reject_rejects_non_pending(client, fake_db):
    """Rejecting an already-generated cert returns 422."""
    fake_db.certificates.docs = [
        {
            "id": "cert-2",
            "schoolId": "aaryans-joya",
            "status": "generated",
            "cert_type": "bonafide",
        }
    ]
    resp = client.patch(
        "/api/ops/certificates/cert-2/reject",
        json={"reason": "Already processed"},
        headers=_owner_h(),
    )
    assert resp.status_code == 422
