from __future__ import annotations
import pytest
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _principal_headers():
    t = create_jwt({"user_id": "prin-1", "role": "admin", "name": "P", "sub_category": "principal"})
    return {"Authorization": f"Bearer {t}"}


def _owner_headers():
    t = create_jwt({"user_id": "own-1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(autouse=True)
def _clean_staff(fake_db):
    """Reset staff docs before/after each test to avoid cross-test pollution."""
    original = list(fake_db.staff.docs)
    fake_db.staff.docs[:] = []
    fake_db.auth_users.docs[:] = [
        d for d in fake_db.auth_users.docs if d.get("username") == "admin"
    ]
    fake_db.audit_logs.docs[:] = []
    yield
    fake_db.staff.docs[:] = original
    fake_db.audit_logs.docs[:] = []


def test_principal_cannot_change_staff_role(client, fake_db):
    """UI-Sweep Story 1.1 — granting owner is a hard 403, not a silent strip.

    This test previously asserted 200-with-the-field-stripped. Silently dropping
    an escalation attempt leaves the caller believing it worked and leaves no
    record that they tried; the contract is now an explicit refusal.
    """
    fake_db.staff.docs = [{"id": "s1", "schoolId": "aaryans-joya", "name": "Alice", "role": "teacher"}]
    resp = client.patch(
        "/api/staff/s1",
        json={"name": "Alice Updated", "role": "owner"},
        headers=_principal_headers(),
    )
    assert resp.status_code == 403
    staff = next((s for s in fake_db.staff.docs if s["id"] == "s1"), None)
    assert staff["role"] == "teacher"      # role must not have changed
    assert staff["name"] == "Alice"        # and nothing else slipped through either


def test_principal_can_still_edit_ordinary_fields(client, fake_db):
    """The 403 above is about owner authority only — ordinary edits still work."""
    fake_db.staff.docs = [{"id": "s1b", "schoolId": "aaryans-joya", "name": "Alice", "role": "teacher"}]
    resp = client.patch("/api/staff/s1b", json={"name": "Alice Updated"}, headers=_principal_headers())
    assert resp.status_code == 200
    staff = next((s for s in fake_db.staff.docs if s["id"] == "s1b"), None)
    assert staff["name"] == "Alice Updated"


def test_principal_self_update_cannot_escalate(client, fake_db):
    """Story 1.1 — a principal cannot grant themselves owner via self-PATCH."""
    fake_db.staff.docs = [{
        "id": "prin-1", "schoolId": "aaryans-joya",
        "name": "P", "role": "admin", "sub_category": "principal",
    }]
    resp = client.patch(
        "/api/staff/prin-1",
        json={"sub_category": "owner"},
        headers=_principal_headers(),
    )
    assert resp.status_code == 403
    staff = next((s for s in fake_db.staff.docs if s["id"] == "prin-1"), None)
    assert staff.get("sub_category") == "principal"  # sub_category must not have changed


def test_owner_can_change_staff_role(client, fake_db):
    """Owner can update role and sub_category fields."""
    fake_db.staff.docs = [{"id": "s2", "schoolId": "aaryans-joya", "name": "Bob", "role": "teacher"}]
    resp = client.patch(
        "/api/staff/s2",
        json={"role": "admin", "sub_category": "receptionist"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 200
    staff = next((s for s in fake_db.staff.docs if s["id"] == "s2"), None)
    assert staff["role"] == "admin"
    assert staff.get("sub_category") == "receptionist"


def test_principal_cannot_change_salary(client, fake_db):
    """Principal PATCH with salary field — salary is silently stripped."""
    fake_db.staff.docs = [{"id": "s3", "schoolId": "aaryans-joya", "name": "Carol", "role": "teacher", "salary": 30000}]
    resp = client.patch(
        "/api/staff/s3",
        json={"name": "Carol Updated", "salary": 99999},
        headers=_principal_headers(),
    )
    assert resp.status_code == 200
    staff = next((s for s in fake_db.staff.docs if s["id"] == "s3"), None)
    assert staff.get("salary") == 30000  # salary must not have changed


def test_owner_can_change_salary(client, fake_db):
    """Owner can update salary."""
    fake_db.staff.docs = [{"id": "s4", "schoolId": "aaryans-joya", "name": "Dave", "role": "teacher", "salary": 30000}]
    resp = client.patch(
        "/api/staff/s4",
        json={"salary": 45000},
        headers=_owner_headers(),
    )
    assert resp.status_code == 200
    staff = next((s for s in fake_db.staff.docs if s["id"] == "s4"), None)
    assert staff.get("salary") == 45000


def test_delete_staff_erases_ai_memories(client, fake_db):
    """R6.4 (XM5, DPDP §12): deactivating a staff account erases that user's
    AI-learned memories AND skills — proves the erasure hooks are invoked."""
    fake_db.staff.docs = [{
        "id": "s5", "schoolId": "aaryans-joya", "name": "Eve",
        "role": "admin", "sub_category": "principal", "user_id": "u-eve", "is_active": True,
    }]
    fake_db.ai_memories.docs[:] = [
        {"id": "m1", "schoolId": "aaryans-joya", "user_id": "u-eve", "text": "Eve prefers X", "superseded": False},
    ]
    fake_db.ai_skills.docs[:] = [
        {"id": "sk1", "schoolId": "aaryans-joya", "user_id": "u-eve", "title": "monthly close"},
    ]
    resp = client.delete("/api/staff/s5", headers=_owner_headers())
    assert resp.status_code == 200
    assert [m for m in fake_db.ai_memories.docs if m.get("user_id") == "u-eve"] == []
    assert [s for s in fake_db.ai_skills.docs if s.get("user_id") == "u-eve"] == []
