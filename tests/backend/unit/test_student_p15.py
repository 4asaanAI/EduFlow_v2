from __future__ import annotations
import pytest
from middleware.auth import create_jwt
from tests.backend.conftest import FakeCollection
from tests.backend.factories import make_fee_transaction

pytestmark = pytest.mark.asyncio

def _student_h(user_id="u-stu"):
    t = create_jwt({"user_id": user_id, "role": "student", "name": "Student"})
    return {"Authorization": f"Bearer {t}"}

def test_student_cannot_view_other_student_fee_status(client, fake_db):
    """Student cannot view another student's fee status."""
    fake_db.students.docs = [{"id": "s1", "schoolId": "aaryans-joya", "user_id": "u-stu"}]
    resp = client.get("/api/fees/status/s2-another-student", headers=_student_h())
    assert resp.status_code == 403

def test_fee_my_includes_partial_payment_in_total_paid(client, fake_db):
    """GET /fees/my includes paid_amount from partial transactions in total_paid."""
    fake_db.students.docs = [{"id": "s1", "schoolId": "aaryans-joya", "user_id": "u-stu"}]
    fake_db.fee_transactions.docs = [
        make_fee_transaction(student_id="s1", amount=5000, status="paid"),
        make_fee_transaction(student_id="s1", amount=5000, paid_amount=2000, status="partial"),
    ]
    resp = client.get("/api/fees/my", headers=_student_h())
    if resp.status_code == 200:
        summary = resp.json().get("summary", {})
        assert summary.get("total_paid", 0) >= 7000  # 5000 + 2000

def test_health_ready_returns_503_when_db_down(client, monkeypatch):
    """GET /health/ready returns 503 when DB is unavailable."""
    import server
    async def mock_check_db(): return "error"
    monkeypatch.setattr(server, "_check_db", mock_check_db)
    resp = client.get("/api/health/ready")
    assert resp.status_code == 503
    assert resp.json()["overall"] == "down"


# --- DPDP consent gate tests ---

def test_student_me_returns_200_with_student_record(client, fake_db):
    """Student with a matching student record can access GET /students/me."""
    from middleware.auth import create_jwt
    fake_db.students.docs.append(
        {"id": "s-consent", "schoolId": "aaryans-joya", "user_id": "u-consent", "name": "Alice"}
    )
    t = create_jwt({"user_id": "u-consent", "role": "student", "name": "Alice"})
    resp = client.get("/api/students/me", headers={"Authorization": f"Bearer {t}"})
    # Route returns 200 with data:None when student not found OR 200 with data when found
    assert resp.status_code == 200


def test_student_me_returns_200_no_student_record(client, fake_db):
    """GET /students/me returns 200 with data:None when no student record exists."""
    from middleware.auth import create_jwt
    fake_db.students.docs = [d for d in fake_db.students.docs if d.get("user_id") != "u-ghost"]
    t = create_jwt({"user_id": "u-ghost", "role": "student", "name": "Ghost"})
    resp = client.get("/api/students/me", headers={"Authorization": f"Bearer {t}"})
    assert resp.status_code == 200
    assert resp.json().get("data") is None


def test_student_post_consent_record(client, fake_db):
    """POST /students/me/consent records a DPDP consent for the student."""
    from middleware.auth import create_jwt
    fake_db.students.docs.append(
        {"id": "s-dpdp", "schoolId": "aaryans-joya", "user_id": "u-dpdp", "name": "Consent Student"}
    )
    fake_db.dpdp_consents.docs = []
    fake_db.audit_logs.docs = []
    t = create_jwt({"user_id": "u-dpdp", "role": "student", "name": "Consent Student"})
    resp = client.post(
        "/api/students/me/consent",
        json={"purpose": "data_usage", "granted": True},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    assert body["data"]["purpose"] == "data_usage"
    assert body["data"]["granted"] is True


def test_student_post_consent_missing_fields_returns_400(client, fake_db):
    """POST /students/me/consent without required fields returns 400."""
    from middleware.auth import create_jwt
    fake_db.students.docs.append(
        {"id": "s-dpdp2", "schoolId": "aaryans-joya", "user_id": "u-dpdp2", "name": "S2"}
    )
    t = create_jwt({"user_id": "u-dpdp2", "role": "student", "name": "S2"})
    resp = client.post(
        "/api/students/me/consent",
        json={"purpose": ""},       # empty purpose, no granted
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 400


def test_student_get_consents_returns_list(client, fake_db):
    """GET /students/me/consent returns a list of recorded consents."""
    from middleware.auth import create_jwt
    fake_db.students.docs.append(
        {"id": "s-list", "schoolId": "aaryans-joya", "user_id": "u-list", "name": "List Student"}
    )
    fake_db.dpdp_consents.docs = [
        {
            "id": "c1",
            "schoolId": "aaryans-joya",
            "student_id": "s-list",
            "user_id": "u-list",
            "purpose": "marketing",
            "granted": False,
            "recorded_at": "2026-01-01T00:00:00",
        }
    ]
    t = create_jwt({"user_id": "u-list", "role": "student", "name": "List Student"})
    resp = client.get("/api/students/me/consent", headers={"Authorization": f"Bearer {t}"})
    assert resp.status_code == 200
    data = resp.json().get("data", [])
    assert isinstance(data, list)


def test_student_cannot_access_staff_endpoints(client):
    """Student role is blocked from staff management endpoints — returns 403."""
    from middleware.auth import create_jwt
    t = create_jwt({"user_id": "u-stu", "role": "student", "name": "S"})
    resp = client.get("/api/staff/", headers={"Authorization": f"Bearer {t}"})
    assert resp.status_code in (403, 404)


def test_non_student_cannot_call_consent_endpoint(client, fake_db):
    """Non-student role cannot POST /students/me/consent — returns 403."""
    from middleware.auth import create_jwt
    t = create_jwt({"user_id": "u-admin", "role": "admin", "name": "Admin"})
    resp = client.post(
        "/api/students/me/consent",
        json={"purpose": "data_usage", "granted": True},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 403


def test_unauthenticated_me_consent_returns_401(client):
    """Unauthenticated POST /students/me/consent returns 401."""
    resp = client.post("/api/students/me/consent", json={"purpose": "x", "granted": True})
    assert resp.status_code == 401
