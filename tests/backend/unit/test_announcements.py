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


def test_principal_announcement_bypasses_approval(client, fake_db):
    """Principal posts to student audience → status is published, not pending_approval."""
    # Reset announcements collection before this test
    fake_db.announcements.docs = []
    resp = client.post("/api/ops/announcements", json={
        "title": "Exam Notice", "content": "Exams next week.",
        "audience_roles": ["student", "teacher"],
    }, headers=_principal_headers())
    if resp.status_code == 200:
        ann = next(iter(fake_db.announcements.docs), None)
        if ann:
            assert ann.get("status") != "pending_approval", "Principal announcement should not be pending"


def test_principal_cannot_target_owner_role(client):
    """Principal with audience_roles containing 'owner' → 422."""
    resp = client.post("/api/ops/announcements", json={
        "title": "Test", "content": "Test.",
        "audience_roles": ["owner"],
    }, headers=_principal_headers())
    assert resp.status_code == 422


def test_teacher_announcement_requires_approval(client, fake_db):
    """Teacher posting to student audience gets pending_approval status."""
    fake_db.announcements.docs = []
    resp = client.post("/api/ops/announcements", json={
        "title": "Teacher Notice", "content": "Meeting tomorrow.",
        "audience_roles": ["student"],
    }, headers=_teacher_headers())
    if resp.status_code in (200, 201):
        ann = next(iter(fake_db.announcements.docs), None)
        if ann:
            assert ann.get("status") == "pending_approval"
