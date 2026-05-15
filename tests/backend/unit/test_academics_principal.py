from __future__ import annotations
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")

from middleware.auth import create_jwt


def _principal_headers():
    t = create_jwt({"user_id": "p1", "role": "admin", "name": "Principal", "sub_category": "principal"})
    return {"Authorization": f"Bearer {t}"}


def _teacher_headers():
    t = create_jwt({"user_id": "t1", "role": "teacher", "name": "Teacher"})
    return {"Authorization": f"Bearer {t}"}


def test_lesson_plan_completion_returns_200_for_principal(client):
    resp = client.get("/api/academics/lesson-plan-completion", headers=_principal_headers())
    assert resp.status_code == 200
    assert "data" in resp.json()


def test_lesson_plan_completion_blocked_for_teacher(client):
    resp = client.get("/api/academics/lesson-plan-completion", headers=_teacher_headers())
    assert resp.status_code == 403


def test_exam_results_accessible_to_principal(client):
    """Principal can access exam results (not owner-only)."""
    resp = client.get("/api/academics/results", headers=_principal_headers())
    assert resp.status_code in (200, 404)  # 404 if no results, but not 403
    assert resp.status_code != 403


def test_lesson_plan_completion_meta_shape(client):
    """Response contains success flag and meta with count and month keys."""
    resp = client.get("/api/academics/lesson-plan-completion", headers=_principal_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "meta" in body
    assert "count" in body["meta"]
    assert "month" in body["meta"]


def test_lesson_plan_completion_accepts_month_param(client):
    """Endpoint accepts a ?month= query parameter without error."""
    resp = client.get("/api/academics/lesson-plan-completion?month=2026-03", headers=_principal_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["month"] == "2026-03"


def test_lesson_plan_completion_blocked_for_unauthenticated(client):
    """No token → 401."""
    resp = client.get("/api/academics/lesson-plan-completion")
    assert resp.status_code == 401


def test_exams_accessible_to_principal(client):
    """Principal (admin role) can access the exams list — endpoint has no auth guard."""
    resp = client.get("/api/academics/exams", headers=_principal_headers())
    assert resp.status_code == 200
    assert "data" in resp.json()
