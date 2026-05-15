"""Part 2 Patch P1 — verify v1 tools in `ai/tool_functions.py` enforce
branch tenancy when given a Scope.

Two branches (A and B) under one school; a teacher scoped to branch A must
only see branch-A data from `tool_search_students` and aggregate tools
like `tool_get_school_pulse`.
"""

from __future__ import annotations

import pytest

_async = pytest.mark.asyncio


def _seeded_db():
    """Build a FakeDb with two-branch students + attendance + staff."""
    from tests.backend.conftest import FakeDb, FakeCollection

    db = FakeDb()
    # Replace students with two-branch dataset.
    db.students = FakeCollection([
        {"id": "s-a1", "name": "Alpha One", "is_active": True,
         "schoolId": "aaryans-joya", "branch_id": "branch-A",
         "class_id": "c-a", "admission_number": "A001"},
        {"id": "s-a2", "name": "Alpha Two", "is_active": True,
         "schoolId": "aaryans-joya", "branch_id": "branch-A",
         "class_id": "c-a", "admission_number": "A002"},
        {"id": "s-b1", "name": "Beta One", "is_active": True,
         "schoolId": "aaryans-joya", "branch_id": "branch-B",
         "class_id": "c-b", "admission_number": "B001"},
    ])
    db.classes = FakeCollection([
        {"id": "c-a", "schoolId": "aaryans-joya", "branch_id": "branch-A",
         "name": "Class 5", "section": "A"},
        {"id": "c-b", "schoolId": "aaryans-joya", "branch_id": "branch-B",
         "name": "Class 5", "section": "B"},
    ])
    db.staff = FakeCollection([
        {"id": "st-a1", "name": "Teacher A", "is_active": True,
         "schoolId": "aaryans-joya", "branch_id": "branch-A",
         "user_id": "u-a", "staff_type": "teacher"},
        {"id": "st-b1", "name": "Teacher B", "is_active": True,
         "schoolId": "aaryans-joya", "branch_id": "branch-B",
         "user_id": "u-b", "staff_type": "teacher"},
    ])
    today = __import__("datetime").date.today().strftime("%Y-%m-%d")
    db.student_attendance = FakeCollection([
        {"id": "att-a1", "schoolId": "aaryans-joya", "branch_id": "branch-A",
         "student_id": "s-a1", "class_id": "c-a", "date": today, "status": "present"},
        {"id": "att-b1", "schoolId": "aaryans-joya", "branch_id": "branch-B",
         "student_id": "s-b1", "class_id": "c-b", "date": today, "status": "absent"},
    ])
    db.staff_attendance = FakeCollection()
    db.fee_transactions = FakeCollection()
    db.leave_requests = FakeCollection()
    return db


def _branch_a_scope():
    from ai.scope_resolver import Scope
    return Scope(
        type="all",
        role="admin",
        sub_category="principal",
        user_id="u-a",
        branch_id="branch-A",
    )


def _owner_scope():
    from ai.scope_resolver import Scope
    return Scope(type="all", role="owner", user_id="u-owner", branch_id=None)


@_async
async def test_search_students_isolates_branch_a(monkeypatch):
    """Teacher in branch-A must not see branch-B students."""
    db = _seeded_db()
    from ai import tool_functions as tf_mod
    monkeypatch.setattr(tf_mod, "get_db", lambda: db)

    from ai.tool_functions import tool_search_students
    result = await tool_search_students({"query": ""}, {"id": "u-a", "role": "admin"}, _branch_a_scope())
    names = {s["name"] for s in result["students"]}
    assert names == {"Alpha One", "Alpha Two"}, f"branch leak: got {names}"
    assert result["total"] == 2


@_async
async def test_search_students_owner_sees_all_branches(monkeypatch):
    """Owner (no branch_id) sees every branch."""
    db = _seeded_db()
    from ai import tool_functions as tf_mod
    monkeypatch.setattr(tf_mod, "get_db", lambda: db)

    from ai.tool_functions import tool_search_students
    result = await tool_search_students({"query": ""}, {"id": "u-owner", "role": "owner"}, _owner_scope())
    assert result["total"] == 3


@_async
async def test_school_pulse_aggregates_only_branch_a(monkeypatch):
    """Aggregations (counts, attendance) are also branch-scoped."""
    db = _seeded_db()
    from ai import tool_functions as tf_mod
    monkeypatch.setattr(tf_mod, "get_db", lambda: db)

    from ai.tool_functions import tool_get_school_pulse
    result = await tool_get_school_pulse({}, {"id": "u-a", "role": "admin"}, _branch_a_scope())

    # 2 branch-A students, 1 branch-A staff, 1 attendance record (present).
    assert result["summary"]["total_students"] == 2
    assert result["summary"]["total_staff"] == 1
    assert result["summary"]["present_today"] == 1
    assert result["summary"]["absent_today"] == 0


@_async
async def test_school_pulse_owner_sees_all(monkeypatch):
    db = _seeded_db()
    from ai import tool_functions as tf_mod
    monkeypatch.setattr(tf_mod, "get_db", lambda: db)

    from ai.tool_functions import tool_get_school_pulse
    result = await tool_get_school_pulse({}, {"id": "u-owner", "role": "owner"}, _owner_scope())
    assert result["summary"]["total_students"] == 3
    assert result["summary"]["total_staff"] == 2
    # 1 present (branch-A) + 1 absent (branch-B) = 2 marked
    assert result["summary"]["present_today"] == 1
    assert result["summary"]["absent_today"] == 1


@_async
async def test_approve_leave_rejects_cross_branch(monkeypatch):
    """A branch-A admin must not approve a branch-B leave."""
    db = _seeded_db()
    db.leave_requests.docs.append({
        "id": "lr-b1", "schoolId": "aaryans-joya", "branch_id": "branch-B",
        "staff_id": "st-b1", "status": "pending",
        "leave_type": "sick", "start_date": "2026-05-15", "end_date": "2026-05-16",
    })
    from ai import tool_functions as tf_mod
    monkeypatch.setattr(tf_mod, "get_db", lambda: db)

    from ai.tool_functions import tool_approve_leave
    result = await tool_approve_leave(
        {"leave_id": "lr-b1", "action": "approve"},
        {"id": "u-a", "role": "admin"},
        _branch_a_scope(),
    )
    # Don't leak existence: must be "not found", not "approved".
    assert result.get("success") is False
    assert "not found" in result.get("error", "").lower()
    # Original leave still pending.
    assert db.leave_requests.docs[0]["status"] == "pending"
