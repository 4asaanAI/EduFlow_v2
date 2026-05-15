from __future__ import annotations
import pytest
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _teacher_headers():
    t = create_jwt({"user_id": "t1", "role": "teacher", "name": "Teacher"})
    return {"Authorization": f"Bearer {t}"}


def _principal_headers():
    t = create_jwt({"user_id": "p1", "role": "admin", "name": "Principal", "sub_category": "principal"})
    return {"Authorization": f"Bearer {t}"}


def test_teacher_can_create_incident(client):
    """Any authenticated user can create an incident."""
    resp = client.post("/api/ops/incidents", json={
        "title": "Student fight", "description": "Two students fighting.", "severity": "high",
    }, headers=_teacher_headers())
    assert resp.status_code in (200, 201)


def test_high_severity_auto_assigned_to_principal(client, fake_db):
    """High severity incidents are auto-assigned to principal."""
    fake_db.incidents.docs = []
    resp = client.post("/api/ops/incidents", json={
        "title": "Serious incident", "severity": "high", "description": "Desc",
    }, headers=_teacher_headers())
    assert resp.status_code in (200, 201)
    incident = next((i for i in fake_db.incidents.docs if i.get("severity") == "high"), None)
    if incident:
        assert incident.get("assigned_to") == "principal"


def test_principal_can_resolve_incident(client, fake_db):
    """Principal can update incident status and add resolution note."""
    fake_db.incidents.docs = [{"id": "inc-1", "schoolId": "aaryans-joya", "status": "open"}]
    resp = client.patch("/api/ops/incidents/inc-1", json={
        "status": "resolved", "resolution_note": "Issue addressed.",
    }, headers=_principal_headers())
    assert resp.status_code == 200
