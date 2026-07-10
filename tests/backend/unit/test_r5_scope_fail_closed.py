"""Epic R5 — Tenancy & Scope Fail-Closed (scope_resolver tier).

Covers X6/L6:
  * Coordinator class-range regex is anchored — "Class 1" never widens into
    "Class 10/11/12" (AC1).
  * A HOD/coordinator whose scope resolves to ZERO classes gets the fail-closed
    impossible filter and no student visibility, never `{}` / school-wide (AC2).
  * class_list scope over fee/exam collections fails closed (AC3).
  * Regex interpolation is re.escaped — a subject like "C++" does not crash (AC4).
  * HOD/coordinator/class_teacher lookups are branch-scoped; class_teacher
    resolution accepts BOTH the staff id and the login user_id (AC5 / L6).
"""

from __future__ import annotations

import pytest

_async = pytest.mark.asyncio


def _import_resolver():
    from ai import scope_resolver
    return scope_resolver


def _make_db(**overrides):
    from tests.backend.conftest import FakeDb, FakeCollection
    db = FakeDb()
    for attr, docs in overrides.items():
        col = getattr(db, attr, None)
        if col is None:
            col = FakeCollection()
            setattr(db, attr, col)
        col.docs[:] = list(docs)
    return db


# ── AC1: coordinator range regex is anchored ───────────────────────────────

@_async
async def test_coordinator_range_1_5_excludes_class_10_11_12():
    rl = _import_resolver()
    db = _make_db(
        staff=[{"id": "s-co", "user_id": "u-co", "is_active": True, "role": "teacher",
                "sub_category": "coordinator", "coordinator_range": "1-5"}],
        classes=[
            {"id": "c1", "name": "Class 1", "section": "A"},
            {"id": "c5", "name": "Class 5", "section": "A"},
            {"id": "c10", "name": "Class 10", "section": "A"},
            {"id": "c12", "name": "Class 12", "section": "A"},
        ],
    )
    scope = await rl.resolve_scope({"id": "u-co", "role": "teacher"}, db)
    assert set(scope.class_ids) == {"c1", "c5"}
    assert "c10" not in scope.class_ids
    assert "c12" not in scope.class_ids


@_async
async def test_coordinator_range_matches_suffixed_class_names():
    """Anchoring on \\b must still admit "Class 1-A" / "Class 1 Rose"."""
    rl = _import_resolver()
    db = _make_db(
        staff=[{"id": "s-co", "user_id": "u-co", "is_active": True, "role": "teacher",
                "sub_category": "coordinator", "coordinator_range": "1-5"}],
        classes=[
            {"id": "c1a", "name": "Class 1-A", "section": "A"},
            {"id": "c10", "name": "Class 10", "section": "A"},
        ],
    )
    scope = await rl.resolve_scope({"id": "u-co", "role": "teacher"}, db)
    assert scope.class_ids == ["c1a"]


# ── AC2: zero resolved classes fail closed ─────────────────────────────────

@_async
async def test_hod_zero_classes_yields_impossible_filter():
    rl = _import_resolver()
    db = _make_db(
        staff=[{"id": "s-hod", "user_id": "u-hod", "is_active": True, "role": "teacher",
                "sub_category": "hod", "subject": "Astrophysics"}],
        subjects=[],  # nothing carries this subject → zero classes
    )
    scope = await rl.resolve_scope({"id": "u-hod", "role": "teacher"}, db)
    assert scope.class_ids == []
    # Fail closed: no students, never {}.
    assert scope.filter(collection="students") == {"id": {"$in": []}}
    # And no personal-info visibility for a HOD who resolved to nothing.
    assert scope.can_see_personal_info({"role": "student", "id": "x", "class_id": "c9"}) is False


# ── AC3: class_list over fee/exam fails closed ─────────────────────────────

def test_class_list_fee_exam_fail_closed():
    rl = _import_resolver()
    scope = rl.Scope(type="class_list", role="teacher", user_id="u", class_ids=["c1"])
    assert scope.filter(collection="fee_transactions") == {"id": {"$in": []}}
    assert scope.filter(collection="exam_results") == {"id": {"$in": []}}


# ── AC4: regex interpolation is re.escaped ─────────────────────────────────

@_async
async def test_hod_subject_with_regex_metacharacters_does_not_crash():
    rl = _import_resolver()
    db = _make_db(
        staff=[{"id": "s-hod", "user_id": "u-hod", "is_active": True, "role": "teacher",
                "sub_category": "hod", "subject": "C++"}],
        subjects=[{"id": "sub1", "name": "C++", "class_id": "c1"}],
    )
    # Without re.escape this raises re.error ("multiple repeat") inside the lookup.
    scope = await rl.resolve_scope({"id": "u-hod", "role": "teacher"}, db)
    assert scope.class_ids == ["c1"]


# ── AC5 / L6: class_teacher matches staff id OR user_id, branch-scoped ──────

@_async
async def test_class_teacher_fallback_matches_staff_id():
    """class_teacher_id may hold the staff record id (not the login user_id)."""
    rl = _import_resolver()
    db = _make_db(
        staff=[{"id": "s-ct", "user_id": "u-ct", "is_active": True, "role": "teacher",
                "sub_category": "class_teacher"}],  # no class_teacher_of → fallback
        classes=[{"id": "c1", "name": "Class 3", "section": "B", "class_teacher_id": "s-ct"}],
    )
    scope = await rl.resolve_scope({"id": "u-ct", "role": "teacher"}, db)
    assert scope.class_ids == ["c1"]


@_async
async def test_coordinator_lookup_is_branch_scoped():
    rl = _import_resolver()
    db = _make_db(
        staff=[{"id": "s-co", "user_id": "u-co", "is_active": True, "role": "teacher",
                "sub_category": "coordinator", "coordinator_range": "1-5"}],
        classes=[
            {"id": "cA", "name": "Class 2", "section": "A", "branch_id": "branch-A"},
            {"id": "cB", "name": "Class 2", "section": "B", "branch_id": "branch-B"},
        ],
    )
    scope = await rl.resolve_scope(
        {"id": "u-co", "role": "teacher", "branch_id": "branch-A"}, db
    )
    assert scope.class_ids == ["cA"]
