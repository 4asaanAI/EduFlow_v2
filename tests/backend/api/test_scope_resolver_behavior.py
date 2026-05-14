"""Behavior tests for scope_resolver — Part 1.5 Patch H.

The existing 50 unit tests in tests/backend/services/test_scope_resolver.py
exercise `scope.filter()` shape only — they would still pass even if a future
refactor silently dropped `scope.filter()` from a production query path.

These tests close that gap: they seed a fake DB with rows belonging to
multiple classes / branches, resolve a role-restricted scope, apply
`scope.filter()` to the fake collection, and assert that ONLY rows
belonging to the user's scope come back. If filter() begins returning {}
for a restricted role (regression), these tests fail.
"""

from __future__ import annotations

import pytest

from ai.scope_resolver import resolve_scope
from tests.backend.conftest import FakeCollection, FakeDb


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean_scope_collections(fake_db):
    """fake_db is session-scoped; flush the collections we touch on each test."""
    names = ("classes", "students", "student_attendance", "fee_transactions",
             "subjects", "staff")
    snapshots = {n: list(getattr(fake_db, n).docs) for n in names if hasattr(fake_db, n)}
    yield
    for n, snap in snapshots.items():
        getattr(fake_db, n).docs[:] = snap


def _seed_two_class_world(db: FakeDb) -> None:
    """Populate db with class-A and class-B rows across students/attendance/fees."""
    db.classes.docs.extend([
        {"id": "class-A", "name": "Class 5A", "class_teacher_id": "u-ct-A"},
        {"id": "class-B", "name": "Class 5B", "class_teacher_id": "u-ct-B"},
    ])
    db.students.docs.extend([
        {"id": "stu-A1", "name": "Alice", "class_id": "class-A"},
        {"id": "stu-A2", "name": "Aaron", "class_id": "class-A"},
        {"id": "stu-B1", "name": "Bob",   "class_id": "class-B"},
        {"id": "stu-B2", "name": "Bella", "class_id": "class-B"},
    ])
    db.student_attendance.docs.extend([
        {"id": "att-A1", "student_id": "stu-A1", "class_id": "class-A", "status": "present"},
        {"id": "att-B1", "student_id": "stu-B1", "class_id": "class-B", "status": "present"},
    ])
    db.fee_transactions.docs.extend([
        {"id": "fee-A1", "student_id": "stu-A1", "amount": 1000},
        {"id": "fee-B1", "student_id": "stu-B1", "amount": 1500},
    ])


def _ensure_collections(db: FakeDb) -> None:
    """Make sure required collections exist and start empty for this test.

    The _clean_scope_collections fixture restores docs after the test runs.
    """
    for name in ("classes", "students", "student_attendance", "fee_transactions",
                 "subjects", "staff"):
        if not hasattr(db, name):
            setattr(db, name, FakeCollection())
        getattr(db, name).docs[:] = []


async def test_class_teacher_students_filter_is_class_scoped(fake_db):
    """A class_teacher for class-A must NOT see students of class-B."""
    _ensure_collections(fake_db)
    _seed_two_class_world(fake_db)
    fake_db.staff.docs.append({
        "id": "s-ct-A", "user_id": "u-ct-A", "is_active": True, "role": "teacher",
        "sub_category": "class_teacher", "class_teacher_of": "class-A",
    })

    scope = await resolve_scope({"id": "u-ct-A", "role": "teacher"}, fake_db)
    assert scope.type == "class_list"
    assert scope.class_ids == ["class-A"]

    # Behavior: applying scope.filter() to students yields only class-A.
    q = scope.filter(collection="students")
    rows = await fake_db.students.find(q).to_list(100)
    ids = sorted(r["id"] for r in rows)
    assert ids == ["stu-A1", "stu-A2"], f"class_teacher saw cross-class data: {ids}"


async def test_class_teacher_attendance_filter_is_class_scoped(fake_db):
    _ensure_collections(fake_db)
    _seed_two_class_world(fake_db)
    fake_db.staff.docs.append({
        "id": "s-ct-A", "user_id": "u-ct-A", "is_active": True, "role": "teacher",
        "sub_category": "class_teacher", "class_teacher_of": "class-A",
    })

    scope = await resolve_scope({"id": "u-ct-A", "role": "teacher"}, fake_db)
    q = scope.filter(collection="student_attendance")
    rows = await fake_db.student_attendance.find(q).to_list(100)
    assert [r["id"] for r in rows] == ["att-A1"]


async def test_owner_sees_all_students(fake_db):
    _ensure_collections(fake_db)
    _seed_two_class_world(fake_db)
    scope = await resolve_scope({"id": "owner-1", "role": "owner"}, fake_db)
    assert scope.type == "all"
    q = scope.filter(collection="students")
    rows = await fake_db.students.find(q).to_list(100)
    assert len(rows) == 4


async def test_student_self_only_filter_isolates_records(fake_db):
    """A student must only see their own student row + attendance + fees."""
    _ensure_collections(fake_db)
    _seed_two_class_world(fake_db)
    fake_db.students.docs.append({
        "id": "stu-self", "user_id": "u-student", "is_active": True,
        "class_id": "class-A", "name": "Self",
    })
    fake_db.student_attendance.docs.append(
        {"id": "att-self", "student_id": "stu-self", "class_id": "class-A"}
    )
    fake_db.fee_transactions.docs.append(
        {"id": "fee-self", "student_id": "stu-self", "amount": 500}
    )

    scope = await resolve_scope({"id": "u-student", "role": "student"}, fake_db)
    assert scope.type == "self_only"
    # students: filtered by student id == self
    rows = await fake_db.students.find(scope.filter(collection="students")).to_list(100)
    assert [r["id"] for r in rows] == ["stu-self"]
    # attendance: filtered by student_id == self
    rows = await fake_db.student_attendance.find(
        scope.filter(collection="student_attendance")
    ).to_list(100)
    assert [r["id"] for r in rows] == ["att-self"]
    # fee_transactions: filtered by student_id == self
    rows = await fake_db.fee_transactions.find(
        scope.filter(collection="fee_transactions")
    ).to_list(100)
    assert [r["id"] for r in rows] == ["fee-self"]


async def test_subject_teacher_scoped_to_assigned_classes(fake_db):
    _ensure_collections(fake_db)
    _seed_two_class_world(fake_db)
    fake_db.staff.docs.append({
        "id": "s-st-A", "user_id": "u-st-A", "is_active": True, "role": "teacher",
        "sub_category": "subject_teacher", "assigned_class_ids": ["class-A"],
    })

    scope = await resolve_scope({"id": "u-st-A", "role": "teacher"}, fake_db)
    assert scope.type == "class_list"
    assert scope.class_ids == ["class-A"]

    rows = await fake_db.students.find(scope.filter(collection="students")).to_list(100)
    assert sorted(r["id"] for r in rows) == ["stu-A1", "stu-A2"]


async def test_admin_support_staff_self_only(fake_db):
    """An admin with sub_category=support_staff must see only self-scoped records."""
    _ensure_collections(fake_db)
    _seed_two_class_world(fake_db)
    fake_db.staff.docs.append({
        "id": "s-sup", "user_id": "u-sup", "is_active": True, "role": "admin",
        "sub_category": "support_staff",
    })

    scope = await resolve_scope({"id": "u-sup", "role": "admin"}, fake_db)
    assert scope.type == "self_only"
    # No student record matches user_id=u-sup → empty result.
    rows = await fake_db.students.find(scope.filter(collection="students")).to_list(100)
    assert rows == []


async def test_admin_legacy_no_sub_category_is_denied_by_default(fake_db):
    """Regression guard for Part 1 + 1.5 hardening: legacy admin row with no
    sub_category MUST get self_only, not full access."""
    _ensure_collections(fake_db)
    _seed_two_class_world(fake_db)
    fake_db.staff.docs.append({
        "id": "s-legacy", "user_id": "u-legacy", "is_active": True, "role": "admin",
        # NB: no sub_category, no designation
    })

    scope = await resolve_scope({"id": "u-legacy", "role": "admin"}, fake_db)
    assert scope.type == "self_only"
    rows = await fake_db.students.find(scope.filter(collection="students")).to_list(100)
    assert rows == [], "legacy admin must NOT see students by default"


async def test_admin_with_only_designation_principal_no_longer_elevates(fake_db):
    """Part 1.5 Patch J behavior test: designation alone does NOT grant type=all."""
    _ensure_collections(fake_db)
    _seed_two_class_world(fake_db)
    fake_db.staff.docs.append({
        "id": "s-des", "user_id": "u-des", "is_active": True, "role": "admin",
        "designation": "Principal",  # NB: sub_category still missing
    })

    scope = await resolve_scope({"id": "u-des", "role": "admin"}, fake_db)
    assert scope.type == "self_only"
    rows = await fake_db.students.find(scope.filter(collection="students")).to_list(100)
    assert rows == []
