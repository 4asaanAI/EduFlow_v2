from __future__ import annotations
import pytest
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _principal_headers():
    t = create_jwt({"user_id": "p1", "role": "admin", "name": "Principal", "sub_category": "principal"})
    return {"Authorization": f"Bearer {t}"}


def _teacher_headers():
    t = create_jwt({"user_id": "t1", "role": "teacher", "name": "Teacher"})
    return {"Authorization": f"Bearer {t}"}


def test_class_summary_returns_200_for_principal(client):
    resp = client.get("/api/attendance/class-summary", headers=_principal_headers())
    assert resp.status_code == 200
    assert "data" in resp.json()


def test_class_summary_blocked_for_teacher(client):
    resp = client.get("/api/attendance/class-summary", headers=_teacher_headers())
    assert resp.status_code == 403


def test_staff_today_returns_200_for_principal(client):
    resp = client.get("/api/attendance/staff/today", headers=_principal_headers())
    assert resp.status_code == 200
    assert "data" in resp.json()


def test_staff_today_blocked_for_teacher(client):
    resp = client.get("/api/attendance/staff/today", headers=_teacher_headers())
    assert resp.status_code == 403
