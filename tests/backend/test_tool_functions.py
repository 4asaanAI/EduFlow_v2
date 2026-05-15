"""
P4-3.1 integration tests: branch_id enforcement in AI tool layer.

These tests verify that:
1. Per-branch tool functions pass branch_id through to MongoDB queries.
2. School-wide tools (like get_class_list used as dropdown) intentionally
   omit branch_id when the caller has no branch scope.

All tests use the FakeCollection / in-memory DB from conftest so no real
MongoDB connection is required.
"""
from __future__ import annotations

import pytest

from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(**collections):
    """Return a minimal fake DB namespace with the given collections."""
    db = type("FakeDb", (), {})()
    defaults = [
        "students", "staff", "classes", "leave_requests",
        "fee_transactions", "student_attendance", "staff_attendance",
        "houses", "house_points", "library_books", "library_issues",
        "student_council", "fee_structures", "audit_logs", "notifications",
    ]
    for name in defaults:
        setattr(db, name, FakeCollection())
    for name, col in collections.items():
        setattr(db, name, col)
    return db


# ---------------------------------------------------------------------------
# test_get_students_tool_passes_branch_id
# ---------------------------------------------------------------------------

async def test_get_students_tool_passes_branch_id(monkeypatch):
    """tool_get_student_database must scope students query to user's branch_id."""
    from ai import tool_functions_v2

    # Prepare two students in different branches but same school
    branch_a_student = {
        "id": "s-a1",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-a",
        "name": "Alice Brancha",
        "class_id": "cls-1",
        "is_active": True,
        "status": "active",
        "roll_number": "R1",
        "admission_number": "ADM1",
        "gender": "F",
    }
    branch_b_student = {
        "id": "s-b1",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-b",
        "name": "Bob Branchb",
        "class_id": "cls-2",
        "is_active": True,
        "status": "active",
        "roll_number": "R2",
        "admission_number": "ADM2",
        "gender": "M",
    }
    class_doc = {
        "id": "cls-1",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-a",
        "name": "Class 5",
        "section": "A",
    }

    students_col = FakeCollection([branch_a_student, branch_b_student])
    classes_col = FakeCollection([class_doc])
    db = _make_db(students=students_col, classes=classes_col)

    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: db)
    monkeypatch.setenv("SCHOOL_ID", "aaryans-joya")

    user = {"id": "u1", "role": "admin", "branch_id": "branch-a"}
    scope = {"branch_id": "branch-a"}

    result = await tool_functions_v2.tool_get_student_database({}, user, scope)

    assert result["success"] is True
    # Only branch-a student should appear
    names = [r["name"] for r in result["data"]]
    assert "Alice Brancha" in names, f"branch-a student missing, got: {names}"
    assert "Bob Branchb" not in names, f"branch-b student leaked into result: {names}"


# ---------------------------------------------------------------------------
# test_get_attendance_tool_passes_branch_id
# ---------------------------------------------------------------------------

async def test_get_attendance_tool_passes_branch_id(monkeypatch):
    """tool_get_leave_requests must scope leave_requests query to user's branch_id."""
    from ai import tool_functions_v2

    leave_a = {
        "id": "lr-a1",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-a",
        "staff_id": "staff-a1",
        "leave_type": "sick",
        "start_date": "2026-05-10",
        "end_date": "2026-05-11",
        "status": "pending",
        "reason": "illness",
    }
    leave_b = {
        "id": "lr-b1",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-b",
        "staff_id": "staff-b1",
        "leave_type": "annual",
        "start_date": "2026-05-10",
        "end_date": "2026-05-12",
        "status": "pending",
        "reason": "vacation",
    }
    staff_a = {
        "id": "staff-a1",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-a",
        "name": "Staff Alpha",
        "staff_type": "teacher",
    }
    staff_b = {
        "id": "staff-b1",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-b",
        "name": "Staff Beta",
        "staff_type": "teacher",
    }

    leave_col = FakeCollection([leave_a, leave_b])
    staff_col = FakeCollection([staff_a, staff_b])
    db = _make_db(leave_requests=leave_col, staff=staff_col)

    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: db)
    monkeypatch.setenv("SCHOOL_ID", "aaryans-joya")

    user = {"id": "u1", "role": "admin", "branch_id": "branch-a"}
    scope = {"branch_id": "branch-a"}

    result = await tool_functions_v2.tool_get_leave_requests({}, user, scope)

    assert result["success"] is True
    names = [r["staff_name"] for r in result["data"]]
    assert "Staff Alpha" in names, f"branch-a leave missing, got: {names}"
    assert "Staff Beta" not in names, f"branch-b leave leaked into result: {names}"


# ---------------------------------------------------------------------------
# test_school_wide_tool_no_branch_filter
# ---------------------------------------------------------------------------

async def test_school_wide_tool_no_branch_filter(monkeypatch):
    """tool_get_class_list is school-wide by design (owner with no branch_id).

    When user has no branch_id (owner role), all classes across the school
    should be returned regardless of branch. Branch isolation is not applied
    per the architecture ADR for class-list lookups used as dropdowns.
    """
    from ai import tool_functions_v2

    class_a = {
        "id": "cls-a1",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-a",
        "name": "Class 1",
        "section": "A",
    }
    class_b = {
        "id": "cls-b1",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-b",
        "name": "Class 2",
        "section": "B",
    }

    classes_col = FakeCollection([class_a, class_b])
    students_col = FakeCollection([])
    staff_col = FakeCollection([])
    db = _make_db(classes=classes_col, students=students_col, staff=staff_col)

    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: db)
    monkeypatch.setenv("SCHOOL_ID", "aaryans-joya")

    # Owner has no branch_id — school-wide scope
    user = {"id": "owner-1", "role": "owner"}
    scope = None

    result = await tool_functions_v2.tool_get_class_list({}, user, scope)

    assert result["success"] is True
    class_names = [r["class_name"] for r in result["data"]]
    # Owner sees all classes across branches — branch_id is NOT filtered
    assert "Class 1" in class_names, f"Class 1 missing from owner view: {class_names}"
    assert "Class 2" in class_names, f"Class 2 missing from owner view: {class_names}"
