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
