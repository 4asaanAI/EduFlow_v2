"""Epic J — adversarial & edge-case regression guards for student/staff CRUD tools.

Covers the STEP-4 review findings: privilege-escalation blocks, OWNER_ONLY_FIELDS
silent-strip on the AI path, no-op short-circuits, duplicate detection, and the
Phase-1 Owner/Principal lockdown on every new write tool.
"""

from __future__ import annotations

import pytest

from ai import tool_functions_v2
from ai.tool_functions_v2 import TOOL_REGISTRY
from routes.chat import _is_tool_authorized
from services.actor_context import actor_ctx_from_user
from services import student_service, staff_service

pytestmark = pytest.mark.asyncio

OWNER = {"id": "o1", "role": "owner", "name": "Owner"}
PRINCIPAL = {"id": "p1", "role": "admin", "sub_category": "principal", "name": "Principal"}
ACCOUNTANT = {"id": "a1", "role": "admin", "sub_category": "accountant", "name": "Acct"}
TEACHER = {"id": "t1", "role": "teacher", "name": "Teacher"}
STUDENT = {"id": "s1", "role": "student", "name": "Pupil"}

J_TOOLS = [
    "create_student", "update_student", "set_student_status",
    "manage_student_guardians", "create_staff", "update_staff",
]


# ── Phase-1 lockdown: every J write tool is Owner/Principal-only ───────────────
@pytest.mark.parametrize("tool_name", J_TOOLS)
def test_phase1_lockdown_allows_owner_and_principal(tool_name):
    tdef = TOOL_REGISTRY[tool_name]
    assert _is_tool_authorized(OWNER, tdef) is True
    assert _is_tool_authorized(PRINCIPAL, tdef) is True


@pytest.mark.parametrize("tool_name", J_TOOLS)
@pytest.mark.parametrize("actor", [ACCOUNTANT, TEACHER, STUDENT])
def test_phase1_lockdown_blocks_everyone_else(tool_name, actor):
    tdef = TOOL_REGISTRY[tool_name]
    assert _is_tool_authorized(actor, tdef) is False


# ── Staff: privilege-escalation block (principal cannot mint admin/owner) ─────
async def test_principal_cannot_create_privileged_staff(fake_db):
    ctx = actor_ctx_from_user(PRINCIPAL, school_id="aaryans-joya")
    with pytest.raises(staff_service.StaffAuthorizationError):
        await staff_service.create_staff(
            fake_db, ctx, {"name": "Sneaky", "staff_type": "admin", "role": "admin"}
        )
    with pytest.raises(staff_service.StaffAuthorizationError):
        await staff_service.create_staff(
            fake_db, ctx, {"name": "Sneaky", "staff_type": "teacher", "sub_category": "accountant"}
        )


async def test_principal_owner_only_fields_silently_stripped_on_update(fake_db):
    fake_db.staff.docs.append({
        "id": "stf-1", "schoolId": "aaryans-joya", "name": "Bob", "staff_type": "teacher",
        "role": "teacher", "sub_category": None, "salary": 100, "is_active": True, "user_id": None,
    })
    ctx = actor_ctx_from_user(PRINCIPAL, school_id="aaryans-joya")
    # Principal sends only owner-only fields → silent strip → no-op success (no change).
    result = await staff_service.update_staff(
        fake_db, ctx, {"staff_id": "stf-1", "salary": 999, "role": "owner"}
    )
    assert result["noop"] is True
    assert fake_db.staff.docs[0]["salary"] == 100
    assert fake_db.staff.docs[0]["role"] == "teacher"


# ── Student edge cases ────────────────────────────────────────────────────────
async def test_update_student_no_updatable_fields_raises(fake_db):
    fake_db.students.docs.append({"id": "stu-1", "schoolId": "aaryans-joya", "name": "Kid", "class_id": "class-1"})
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(student_service.StudentValidationError):
        await student_service.update_student(fake_db, ctx, {"student_id": "stu-1", "not_a_field": 1})


async def test_set_student_status_noop_when_unchanged(fake_db):
    fake_db.students.docs.append({"id": "stu-2", "schoolId": "aaryans-joya", "name": "Kid", "status": "active", "class_id": "class-1"})
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    result = await student_service.set_student_status(fake_db, ctx, {"student_id": "stu-2", "status": "active"})
    assert result["noop"] is True
    # no audit row written for a no-op
    assert not [a for a in fake_db.audit_logs.docs if a.get("entity_type") == "student"]


async def test_create_student_duplicate_admission_raises(fake_db):
    fake_db.students.docs.append({"id": "stu-3", "schoolId": "aaryans-joya", "name": "Existing", "admission_number": "DUP-1", "class_id": "class-1"})
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(student_service.StudentConflictError):
        await student_service.create_student(
            fake_db, ctx, {"name": "New Kid", "class_id": "class-1", "admission_number": "DUP-1"}
        )


async def test_manage_guardians_non_list_rejected(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_manage_student_guardians(
        {"student_id": "stu-x", "guardians": "not-a-list"}, OWNER, None
    )
    assert out["success"] is False
