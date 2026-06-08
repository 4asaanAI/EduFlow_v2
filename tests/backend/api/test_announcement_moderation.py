"""Story 7-47: Announcement Moderation + Approval Gate tests."""

from __future__ import annotations

import pytest
from middleware.auth import hash_password

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean_announcements(fake_db):
    fake_db.announcements.docs[:] = []
    fake_db.notifications.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    yield
    fake_db.announcements.docs[:] = []
    fake_db.notifications.docs[:] = []
    fake_db.audit_logs.docs[:] = []


def _login(client, username, password):
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _login_owner(client):
    return _login(client, "admin", "admin123")


def _login_reception(client, fake_db):
    """Seed + log in a receptionist (admin/reception) — a creator WITHOUT the
    owner/principal broadcast-direct exemption (EC-9.1), so their teacher/
    student/all/class announcements are held for approval."""
    _seed_receptionist(fake_db)
    return _login(client, "reception", "rec123")


def _seed_receptionist(fake_db):
    fake_db.auth_users.docs.append({
        "id": "reception-1",
        "username": "reception",
        "username_lower": "reception",
        "password_hash": hash_password("rec123"),
        "is_active": True,
        "user_info": {"id": "reception-1", "role": "admin", "name": "Reception", "sub_category": "reception"},
    })


def _seed_principal(fake_db):
    fake_db.auth_users.docs.append({
        "id": "principal-1",
        "username": "principal",
        "username_lower": "principal",
        "password_hash": hash_password("prin123"),
        "is_active": True,
        "user_info": {"id": "principal-1", "role": "admin", "name": "Principal", "sub_category": "principal"},
    })


# ─── Creation flow ─────────────────────────────────────────────────────────


async def test_admin_only_announcement_bypasses_approval_gate(client):
    """AC1 / AC5: target_roles excluding teacher/student → status=active immediately."""
    token = _login_owner(client)
    resp = client.post(
        "/api/ops/announcements",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Admin notice", "content": "FYI", "target_roles": ["admin"]},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "active"


async def test_teacher_targeted_announcement_lands_in_pending(client, fake_db):
    """AC1: a non-owner/principal targeting teacher → status=pending_approval.
    (EC-9.1: owner/principal would broadcast directly — see admin-only test.)"""
    token = _login_reception(client, fake_db)
    resp = client.post(
        "/api/ops/announcements",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Exam schedule", "content": "Next week.", "target_roles": ["teacher"]},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "pending_approval"


async def test_student_targeted_also_lands_in_pending(client, fake_db):
    token = _login_reception(client, fake_db)
    resp = client.post(
        "/api/ops/announcements",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Sports day", "content": "Friday.", "target_roles": ["student"]},
    )
    assert resp.json()["data"]["status"] == "pending_approval"


async def test_all_audience_requires_approval_and_expands_roles(client, fake_db):
    token = _login_reception(client, fake_db)
    resp = client.post(
        "/api/ops/announcements",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "All hands", "content": "Read this.", "audience_type": "all", "target_roles": []},
    )
    data = resp.json()["data"]
    assert data["status"] == "pending_approval"
    assert set(data["target_roles"]) == {"teacher", "student", "admin", "parent"}


async def test_class_audience_requires_approval_and_targets_students(client, fake_db):
    token = _login_reception(client, fake_db)
    resp = client.post(
        "/api/ops/announcements",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Class notice", "content": "For class.", "audience_type": "class", "audience_classes": ["5 A"]},
    )
    data = resp.json()["data"]
    assert data["status"] == "pending_approval"
    assert data["target_roles"] == ["student"]


async def test_mixed_admin_teacher_still_pending(client, fake_db):
    """Any inclusion of teacher/student forces approval (non-owner/principal creator)."""
    token = _login_reception(client, fake_db)
    resp = client.post(
        "/api/ops/announcements",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Mixed", "content": "x", "target_roles": ["admin", "teacher"]},
    )
    assert resp.json()["data"]["status"] == "pending_approval"


# ─── Pending list ──────────────────────────────────────────────────────────


async def test_pending_list_requires_owner_or_principal(client, fake_db):
    """AC2: non-principal admin gets 403."""
    fake_db.auth_users.docs.append({
        "id": "accountant-1",
        "username": "acc",
        "username_lower": "acc",
        "password_hash": hash_password("a123"),
        "is_active": True,
        "user_info": {"id": "accountant-1", "role": "admin", "name": "Acc", "sub_category": "accountant"},
    })
    token = _login(client, "acc", "a123")
    resp = client.get("/api/ops/announcements/pending", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_pending_list_returns_only_pending(client, fake_db):
    """AC2: returns rows in pending_approval only, sorted newest first."""
    fake_db.announcements.docs.extend([
        {"_id": "a1", "id": "a1", "title": "A", "schoolId": "aaryans-joya", "status": "pending_approval", "created_at": "2026-05-15T10:00:00"},
        {"_id": "a2", "id": "a2", "title": "B", "schoolId": "aaryans-joya", "status": "active", "created_at": "2026-05-15T11:00:00"},
        {"_id": "a3", "id": "a3", "title": "C", "schoolId": "aaryans-joya", "status": "pending_approval", "created_at": "2026-05-15T12:00:00"},
    ])
    token = _login_owner(client)
    resp = client.get("/api/ops/announcements/pending", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()["data"]]
    assert ids == ["a3", "a1"]  # newest first; "B" excluded


# ─── Approve flow ──────────────────────────────────────────────────────────


async def test_approve_transitions_to_active(client, fake_db):
    """AC3: pending → active with approved_by stamp; audit row written."""
    fake_db.announcements.docs.append({
        "_id": "a1", "id": "a1", "title": "X", "schoolId": "aaryans-joya", "status": "pending_approval",
        "target_roles": ["teacher"], "created_by": "reception-1",
    })
    token = _login_owner(client)
    resp = client.patch(
        "/api/ops/announcements/a1/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    row = next(r for r in fake_db.announcements.docs if r["id"] == "a1")
    assert row["status"] == "active"
    assert row.get("approved_by") == "admin-1"
    # AC6: audit row
    audit_rows = [r for r in fake_db.audit_logs.docs if r.get("action") == "announcement_approved"]
    assert len(audit_rows) == 1
    assert audit_rows[0]["entity_id"] == "a1"


async def test_approve_rejected_for_non_pending(client, fake_db):
    fake_db.announcements.docs.append({"_id": "a1", "id": "a1", "schoolId": "aaryans-joya", "status": "active"})
    token = _login_owner(client)
    resp = client.patch("/api/ops/announcements/a1/approve", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


async def test_approve_404_for_missing(client):
    token = _login_owner(client)
    resp = client.patch("/api/ops/announcements/nope/approve", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


# ─── Reject flow ───────────────────────────────────────────────────────────


async def test_reject_requires_reason(client, fake_db):
    """AC4: empty/missing reason → 400."""
    fake_db.announcements.docs.append({
        "_id": "a1", "id": "a1", "schoolId": "aaryans-joya", "status": "pending_approval", "title": "X", "created_by": "reception-1",
    })
    token = _login_owner(client)
    resp = client.patch(
        "/api/ops/announcements/a1/reject",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "   "},
    )
    assert resp.status_code == 400


async def test_reject_transitions_to_rejected_and_notifies_author(client, fake_db):
    """AC4 + AC6: status→rejected, audit row written, author notified with reason."""
    _seed_receptionist(fake_db)
    fake_db.announcements.docs.append({
        "_id": "a1", "id": "a1", "schoolId": "aaryans-joya", "status": "pending_approval", "title": "Big bash",
        "target_roles": ["teacher"], "created_by": "reception-1",
    })
    token = _login_owner(client)
    resp = client.patch(
        "/api/ops/announcements/a1/reject",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Inappropriate wording"},
    )
    assert resp.status_code == 200
    row = next(r for r in fake_db.announcements.docs if r["id"] == "a1")
    assert row["status"] == "rejected"
    assert row.get("rejection_reason") == "Inappropriate wording"

    audit_rows = [r for r in fake_db.audit_logs.docs if r.get("action") == "announcement_rejected"]
    assert len(audit_rows) == 1
    assert audit_rows[0].get("reason") == "Inappropriate wording"

    notif_rows = [n for n in fake_db.notifications.docs if n.get("user_id") == "reception-1"]
    assert len(notif_rows) == 1
    assert "Inappropriate wording" in notif_rows[0]["message"]
    assert notif_rows[0]["source_record_id"] == "a1"


# ─── Read filter / backward compatibility ──────────────────────────────────


async def test_list_announcements_filters_out_pending_and_rejected(client, fake_db):
    """AC5: GET /announcements returns active + legacy-no-status only."""
    fake_db.announcements.docs.extend([
        {"_id": "a-act", "id": "a-act", "title": "Active", "schoolId": "aaryans-joya", "status": "active", "audience_type": "all", "audience_roles": [], "is_draft": False, "created_at": "2026-05-15T10:00:00"},
        {"_id": "a-pen", "id": "a-pen", "title": "Pending", "schoolId": "aaryans-joya", "status": "pending_approval", "audience_type": "all", "audience_roles": [], "is_draft": False, "created_at": "2026-05-15T11:00:00"},
        {"_id": "a-rej", "id": "a-rej", "title": "Rejected", "schoolId": "aaryans-joya", "status": "rejected", "audience_type": "all", "audience_roles": [], "is_draft": False, "created_at": "2026-05-15T12:00:00"},
        {"_id": "a-legacy", "id": "a-legacy", "title": "Legacy", "schoolId": "aaryans-joya", "audience_type": "all", "audience_roles": [], "is_draft": False, "created_at": "2026-05-15T13:00:00"},
    ])
    token = _login_owner(client)
    resp = client.get("/api/ops/announcements", headers={"Authorization": f"Bearer {token}"})
    titles = {r["title"] for r in resp.json()["data"]}
    assert titles == {"Active", "Legacy"}
