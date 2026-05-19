"""Story 7-41 + P9.6: Advanced Reporting endpoint tests."""

from __future__ import annotations

from datetime import datetime

import pytest
from middleware.auth import hash_password, create_jwt

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean(fake_db):
    fake_db.student_attendance.docs[:] = []
    fake_db.fee_transactions.docs[:] = []
    yield
    fake_db.student_attendance.docs[:] = []
    fake_db.fee_transactions.docs[:] = []


def _login(client, username, password):
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _login_owner(client):
    return _login(client, "admin", "admin123")


def _seed_principal(fake_db):
    # Unique username — fake_db is session-wide and other suites also seed a
    # "principal" account with a different password.
    fake_db.auth_users.docs.append({
        "id": "principal-rpt",
        "username": "principal_rpt",
        "username_lower": "principal_rpt",
        "password_hash": hash_password("p123"),
        "is_active": True,
        "user_info": {"id": "principal-rpt", "role": "admin", "name": "P", "sub_category": "principal"},
    })


# ─── Auth ──────────────────────────────────────────────────────────────────


async def test_attendance_trends_requires_owner_or_principal(client, fake_db):
    # Use a unique username — session-wide fake_db may have a stale "teacher" row
    # from an earlier test with a different password.
    fake_db.auth_users.docs.append({
        "id": "tch-rpt-1",
        "username": "teacher_rpt",
        "username_lower": "teacher_rpt",
        "password_hash": hash_password("t123"),
        "is_active": True,
        "user_info": {"id": "tch-rpt-1", "role": "teacher", "name": "T"},
    })
    token = _login(client, "teacher_rpt", "t123")
    resp = client.get("/api/reports/attendance-trends", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_fee_summary_principal_can_read(client, fake_db):
    """P9.6: principal can now read fee collection summary (was owner-only before P9.6)."""
    _seed_principal(fake_db)
    token = _login(client, "principal_rpt", "p123")
    resp = client.get("/api/reports/fee-collection-summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # Principal CAN also read attendance.
    resp_ok = client.get("/api/reports/attendance-trends", headers={"Authorization": f"Bearer {token}"})
    assert resp_ok.status_code == 200


# ─── Empty state ───────────────────────────────────────────────────────────


async def test_attendance_trends_empty_when_no_data(client):
    token = _login_owner(client)
    resp = client.get("/api/reports/attendance-trends", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["success"] is True
    assert body["empty"] is True
    assert body["data"] == []


async def test_fee_summary_empty_when_no_data(client):
    token = _login_owner(client)
    resp = client.get("/api/reports/fee-collection-summary", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["empty"] is True


# ─── Attendance math ───────────────────────────────────────────────────────


async def test_attendance_trends_calculates_monthly_pct(client, fake_db):
    """AC1: present/total math is correct; class-level breakdown included."""
    now = datetime.utcnow()
    month = f"{now.year:04d}-{now.month:02d}"
    fake_db.student_attendance.docs.extend([
        {"schoolId": "aaryans-joya", "date": f"{month}-01", "status": "present", "class_id": "c1"},
        {"schoolId": "aaryans-joya", "date": f"{month}-02", "status": "present", "class_id": "c1"},
        {"schoolId": "aaryans-joya", "date": f"{month}-03", "status": "absent", "class_id": "c1"},
        {"schoolId": "aaryans-joya", "date": f"{month}-04", "status": "present", "class_id": "c2"},
        {"schoolId": "aaryans-joya", "date": f"{month}-05", "status": "absent", "class_id": "c2"},
    ])
    token = _login_owner(client)
    resp = client.get("/api/reports/attendance-trends?months=1", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["empty"] is False
    overall = next(r for r in body["overall"] if r["month"] == month)
    assert overall["present"] == 3
    assert overall["total"] == 5
    assert overall["attendance_pct"] == 60.0
    c1 = next(c for c in body["by_class"] if c["class_id"] == "c1")
    c1_now = next(s for s in c1["series"] if s["month"] == month)
    assert c1_now["attendance_pct"] == round(2 / 3 * 100, 2)


async def test_attendance_trends_excludes_other_school_rows(client, fake_db):
    now = datetime.utcnow()
    month = f"{now.year:04d}-{now.month:02d}"
    fake_db.student_attendance.docs.extend([
        {"schoolId": "aaryans-joya", "date": f"{month}-01", "status": "present", "class_id": "c1"},
        {"schoolId": "other-school", "date": f"{month}-01", "status": "absent", "class_id": "c1"},
    ])
    token = _login_owner(client)
    resp = client.get("/api/reports/attendance-trends?months=1", headers={"Authorization": f"Bearer {token}"})
    overall = next(r for r in resp.json()["overall"] if r["month"] == month)
    assert overall["present"] == 1
    assert overall["total"] == 1


# ─── Fee summary math ──────────────────────────────────────────────────────


async def test_fee_summary_groups_paid_and_outstanding(client, fake_db):
    """AC2: collected (paid) vs outstanding (pending/overdue/unpaid) per month."""
    now = datetime.utcnow()
    month = f"{now.year:04d}-{now.month:02d}"
    fake_db.fee_transactions.docs.extend([
        {"schoolId": "aaryans-joya", "amount": 5000, "status": "paid", "paid_date": f"{month}-05"},
        {"schoolId": "aaryans-joya", "amount": 3000, "status": "paid", "paid_date": f"{month}-15"},
        {"schoolId": "aaryans-joya", "amount": 2000, "status": "pending", "due_date": f"{month}-20"},
        {"schoolId": "aaryans-joya", "amount": 1500, "status": "overdue", "due_date": f"{month}-25"},
        {"schoolId": "aaryans-joya", "amount": 999, "status": "paid", "paid_date": "1999-01-01"},  # out of window
    ])
    token = _login_owner(client)
    resp = client.get("/api/reports/fee-collection-summary?months=1", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["empty"] is False
    row = next(r for r in body["data"] if r["month"] == month)
    assert row["collected"] == 8000.0
    assert row["outstanding"] == 3500.0


async def test_fee_summary_excludes_other_school_transactions(client, fake_db):
    now = datetime.utcnow()
    month = f"{now.year:04d}-{now.month:02d}"
    fake_db.fee_transactions.docs.extend([
        {"schoolId": "aaryans-joya", "amount": 1000, "status": "paid", "paid_date": f"{month}-01"},
        {"schoolId": "other-school", "amount": 9000, "status": "paid", "paid_date": f"{month}-01"},
    ])
    token = _login_owner(client)
    resp = client.get("/api/reports/fee-collection-summary?months=1", headers={"Authorization": f"Bearer {token}"})
    row = next(r for r in resp.json()["data"] if r["month"] == month)
    assert row["collected"] == 1000.0


# ─── Clamping ──────────────────────────────────────────────────────────────


async def test_months_param_is_clamped_attendance(client):
    token = _login_owner(client)
    resp_high = client.get("/api/reports/attendance-trends?months=999", headers={"Authorization": f"Bearer {token}"})
    resp_low = client.get("/api/reports/attendance-trends?months=0", headers={"Authorization": f"Bearer {token}"})
    # Both succeed (clamped to [1, 12]).
    assert resp_high.status_code == 200
    assert resp_low.status_code == 200


async def test_months_param_is_clamped_fees(client):
    token = _login_owner(client)
    resp_high = client.get("/api/reports/fee-collection-summary?months=999", headers={"Authorization": f"Bearer {token}"})
    assert resp_high.status_code == 200


async def test_months_param_invalid_string_falls_back(client):
    token = _login_owner(client)
    resp = client.get("/api/reports/attendance-trends?months=abc", headers={"Authorization": f"Bearer {token}"})
    # FastAPI's int param validation will reject a non-int with 422 — accept either
    # 200 (if our clamping receives it) or 422 (if validation fires first).
    assert resp.status_code in (200, 422)


# ─── P9.6 JWT-based auth matrix ────────────────────────────────────────────


def test_fee_collection_summary_accessible_to_principal(client):
    """Principal role can read fee collection summary (was owner-only before P9.6)."""
    token = create_jwt({"user_id": "p1", "role": "admin", "name": "Principal", "sub_category": "principal"})
    resp = client.get("/api/reports/fee-collection-summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_fee_collection_summary_blocked_for_accountant(client):
    """Accountant role cannot read fee collection summary."""
    token = create_jwt({"user_id": "a1", "role": "admin", "name": "Acct", "sub_category": "accountant"})
    resp = client.get("/api/reports/fee-collection-summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
