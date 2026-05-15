"""Part 1 (Auth + RBAC) — direct unit tests for ai/scope_resolver.py.

Coverage target: every role × sub_category × scope-type combination,
every fallback path, every Scope helper method.

resolve_scope is async and hits the DB; we use the in-memory FakeDb from
conftest. Scope object methods are tested directly without any DB.
"""

from __future__ import annotations

import pytest

# Async resolve_scope tests get the asyncio marker; sync Scope-method tests
# do not (they don't touch the DB).
_async = pytest.mark.asyncio


def _import_resolver():
    from tests.backend.conftest import APP_AVAILABLE  # noqa: F401
    from ai import scope_resolver
    return scope_resolver


def _make_db(**overrides):
    """Build a fresh FakeDb pre-seeded with overrides for staff/students/classes."""
    from tests.backend.conftest import FakeDb, FakeCollection
    db = FakeDb()
    for attr, docs in overrides.items():
        col = getattr(db, attr, None)
        if col is None:
            col = FakeCollection()
            setattr(db, attr, col)
        col.docs[:] = list(docs)
    return db


# ─── resolve_scope: owner ──────────────────────────────────────────────────


@_async
async def test_resolve_owner_returns_type_all():
    rl = _import_resolver()
    db = _make_db()
    scope = await rl.resolve_scope({"id": "u1", "role": "owner"}, db)
    assert scope.type == "all"
    assert scope.role == "owner"
    assert scope.user_id == "u1"


@_async
async def test_resolve_owner_filter_returns_empty_dict():
    rl = _import_resolver()
    scope = rl.Scope(type="all", role="owner", user_id="u1")
    assert scope.filter() == {}
    assert scope.filter(collection="students") == {}


# ─── resolve_scope: student ────────────────────────────────────────────────


@_async
async def test_resolve_student_with_active_record():
    rl = _import_resolver()
    db = _make_db(students=[
        {"id": "stu-1", "user_id": "u-stu", "is_active": True, "class_id": "c-1"},
    ])
    scope = await rl.resolve_scope({"id": "u-stu", "role": "student"}, db)
    assert scope.type == "self_only"
    assert scope.role == "student"
    assert scope.student_id == "stu-1"


@_async
async def test_resolve_student_without_record_still_self_only():
    rl = _import_resolver()
    db = _make_db(students=[])
    scope = await rl.resolve_scope({"id": "u-orphan", "role": "student"}, db)
    assert scope.type == "self_only"
    assert scope.student_id is None


# ─── resolve_scope: admin sub_categories ───────────────────────────────────


@_async
async def test_resolve_admin_principal_returns_type_all():
    rl = _import_resolver()
    db = _make_db(staff=[
        {"id": "s-1", "user_id": "u-pri", "is_active": True, "role": "admin", "sub_category": "principal"},
    ])
    scope = await rl.resolve_scope({"id": "u-pri", "role": "admin"}, db)
    assert scope.type == "all"
    assert scope.sub_category == "principal"


@_async
async def test_resolve_admin_accountant_returns_financial_domain():
    rl = _import_resolver()
    db = _make_db(staff=[
        {"id": "s-2", "user_id": "u-acc", "is_active": True, "role": "admin", "sub_category": "accountant"},
    ])
    scope = await rl.resolve_scope({"id": "u-acc", "role": "admin"}, db)
    assert scope.type == "domain"
    assert scope.domain == "financial"
    assert scope.sub_category == "accountant"


@_async
async def test_resolve_admin_transport_head_returns_transport_domain():
    rl = _import_resolver()
    db = _make_db(staff=[
        {"id": "s-3", "user_id": "u-tr", "is_active": True, "role": "admin", "sub_category": "transport_head"},
    ])
    scope = await rl.resolve_scope({"id": "u-tr", "role": "admin"}, db)
    assert scope.type == "domain"
    assert scope.domain == "transport"


@_async
async def test_resolve_admin_receptionist_returns_enquiries_domain():
    rl = _import_resolver()
    db = _make_db(staff=[
        {"id": "s-4", "user_id": "u-rec", "is_active": True, "role": "admin", "sub_category": "receptionist"},
    ])
    scope = await rl.resolve_scope({"id": "u-rec", "role": "admin"}, db)
    assert scope.type == "domain"
    assert scope.domain == "enquiries"


@_async
async def test_resolve_admin_support_staff_is_self_only():
    rl = _import_resolver()
    db = _make_db(staff=[
        {"id": "s-5", "user_id": "u-sup", "is_active": True, "role": "admin", "sub_category": "support_staff"},
    ])
    scope = await rl.resolve_scope({"id": "u-sup", "role": "admin"}, db)
    assert scope.type == "self_only"
    assert scope.sub_category == "support_staff"


@_async
async def test_resolve_admin_legacy_no_sub_category_is_self_only():
    """Part 1 hardening: previously this fell through to type='all' (security bug). Now self_only."""
    rl = _import_resolver()
    db = _make_db(staff=[
        {"id": "s-leg", "user_id": "u-leg", "is_active": True, "role": "admin"},  # no sub_category, no designation
    ])
    scope = await rl.resolve_scope({"id": "u-leg", "role": "admin"}, db)
    assert scope.type == "self_only"
    assert scope.sub_category is None


@_async
async def test_resolve_admin_unknown_sub_category_is_self_only():
    rl = _import_resolver()
    db = _make_db(staff=[
        {"id": "s-x", "user_id": "u-x", "is_active": True, "role": "admin", "sub_category": "wizard"},
    ])
    scope = await rl.resolve_scope({"id": "u-x", "role": "admin"}, db)
    assert scope.type == "self_only"


@_async
async def test_resolve_admin_designation_no_longer_elevates():
    """Part 1.5 Patch J: designation is NOT a fallback path to type=all.

    Migration 016 promotes legacy designation values into sub_category
    before this resolver runs. Any admin row that still reaches the
    resolver with only designation set is treated as deny-by-default
    (self_only). Regression guard against the original bypass.
    """
    rl = _import_resolver()
    db = _make_db(staff=[
        {"id": "s-d", "user_id": "u-d", "is_active": True, "role": "admin",
         "designation": "Principal"},  # NB: no sub_category
    ])
    scope = await rl.resolve_scope({"id": "u-d", "role": "admin"}, db)
    assert scope.type == "self_only"
    assert scope.sub_category is None


# ─── resolve_scope: teacher sub_categories ─────────────────────────────────


@_async
async def test_resolve_teacher_class_teacher():
    rl = _import_resolver()
    db = _make_db(
        staff=[{"id": "s-ct", "user_id": "u-ct", "is_active": True, "role": "teacher",
                "sub_category": "class_teacher", "class_teacher_of": "c-1"}],
        classes=[{"id": "c-1", "name": "Class 1", "section": "A"}],
    )
    scope = await rl.resolve_scope({"id": "u-ct", "role": "teacher"}, db)
    assert scope.type == "class_list"
    assert "c-1" in scope.class_ids


@_async
async def test_resolve_teacher_subject_teacher_with_assigned_classes():
    rl = _import_resolver()
    db = _make_db(staff=[
        {"id": "s-st", "user_id": "u-st", "is_active": True, "role": "teacher",
         "sub_category": "subject_teacher",
         "assigned_class_ids": ["c-2", "c-3"]},
    ])
    scope = await rl.resolve_scope({"id": "u-st", "role": "teacher"}, db)
    assert scope.type == "class_list"
    assert set(scope.class_ids) >= {"c-2", "c-3"}


@_async
async def test_resolve_teacher_unknown_sub_category_is_self_only():
    rl = _import_resolver()
    db = _make_db(staff=[
        {"id": "s-?", "user_id": "u-?", "is_active": True, "role": "teacher", "sub_category": "principal_pet"},
    ])
    scope = await rl.resolve_scope({"id": "u-?", "role": "teacher"}, db)
    assert scope.type == "self_only"


@_async
async def test_resolve_teacher_no_staff_record_is_self_only():
    rl = _import_resolver()
    db = _make_db(staff=[])
    scope = await rl.resolve_scope({"id": "u-ghost", "role": "teacher"}, db)
    assert scope.type == "self_only"


# ─── resolve_scope: input validation ───────────────────────────────────────


@_async
async def test_resolve_rejects_missing_id():
    rl = _import_resolver()
    with pytest.raises(ValueError):
        await rl.resolve_scope({"role": "owner"}, _make_db())


@_async
async def test_resolve_rejects_missing_role():
    rl = _import_resolver()
    with pytest.raises(ValueError):
        await rl.resolve_scope({"id": "u"}, _make_db())


@_async
async def test_resolve_rejects_empty_user():
    rl = _import_resolver()
    with pytest.raises(ValueError):
        await rl.resolve_scope({}, _make_db())


# ─── Scope.filter() — per-collection behaviour ─────────────────────────────


def test_scope_filter_all_type_returns_empty():
    rl = _import_resolver()
    scope = rl.Scope(type="all", role="owner", user_id="u")
    assert scope.filter(collection="students") == {}
    assert scope.filter(collection="fee_transactions") == {}


def test_scope_filter_self_only_student_uses_student_id():
    rl = _import_resolver()
    scope = rl.Scope(type="self_only", role="student", user_id="u", student_id="stu-1")
    assert scope.filter(collection="students") == {"id": "stu-1"}
    assert scope.filter(collection="student_attendance") == {"student_id": "stu-1"}
    assert scope.filter(collection="fee_transactions") == {"student_id": "stu-1"}


def test_scope_filter_self_only_staff_uses_user_id():
    rl = _import_resolver()
    scope = rl.Scope(type="self_only", role="admin", user_id="u-sup",
                     sub_category="support_staff")
    assert scope.filter(collection="staff") == {"user_id": "u-sup"}


def test_scope_filter_class_list_restricts_by_class_id():
    rl = _import_resolver()
    scope = rl.Scope(type="class_list", role="teacher", user_id="u",
                     class_ids=["c-1", "c-2"])
    assert scope.filter(collection="students") == {"class_id": {"$in": ["c-1", "c-2"]}}
    assert scope.filter(collection="student_attendance") == {"class_id": {"$in": ["c-1", "c-2"]}}
    assert scope.filter(collection="classes") == {"id": {"$in": ["c-1", "c-2"]}}


def test_scope_filter_class_list_empty_falls_to_self_only():
    """Defensive: class_list with no classes resolved is effectively self-only."""
    rl = _import_resolver()
    scope = rl.Scope(type="class_list", role="teacher", user_id="u-empty", class_ids=[])
    result = scope.filter(collection="students")
    assert result == {"user_id": "u-empty"}


def test_scope_filter_subject_type_with_class_ids():
    rl = _import_resolver()
    scope = rl.Scope(type="subject", role="teacher", user_id="u",
                     subject="Mathematics", class_ids=["c-9", "c-10"])
    assert scope.filter(collection="subjects") == {"name": "Mathematics"}
    assert scope.filter(collection="students") == {"class_id": {"$in": ["c-9", "c-10"]}}


def test_scope_filter_domain_returns_empty_within_allowed_collection():
    rl = _import_resolver()
    scope = rl.Scope(type="domain", role="admin", user_id="u",
                     domain="financial", sub_category="accountant")
    assert scope.filter(collection="fee_transactions") == {}


# ─── Scope.can_see_personal_info ───────────────────────────────────────────


def test_can_see_own_info_always_true():
    rl = _import_resolver()
    scope = rl.Scope(type="self_only", role="student", user_id="u-1")
    assert scope.can_see_personal_info({"id": "u-1", "role": "student"}) is True


def test_owner_can_see_all_personal_info():
    rl = _import_resolver()
    scope = rl.Scope(type="all", role="owner", user_id="o-1")
    assert scope.can_see_personal_info({"id": "other", "role": "teacher"}) is True


def test_principal_can_see_all_personal_info():
    rl = _import_resolver()
    scope = rl.Scope(type="all", role="admin", sub_category="principal", user_id="p-1")
    assert scope.can_see_personal_info({"id": "other", "role": "student"}) is True


def test_accountant_sees_students_not_staff():
    rl = _import_resolver()
    scope = rl.Scope(type="domain", role="admin", sub_category="accountant", user_id="a-1")
    assert scope.can_see_personal_info({"id": "stu", "role": "student"}) is True
    assert scope.can_see_personal_info({"id": "tch", "role": "teacher"}) is False


def test_support_staff_cannot_see_others_personal_info():
    rl = _import_resolver()
    scope = rl.Scope(type="self_only", role="admin", sub_category="support_staff", user_id="s-1")
    assert scope.can_see_personal_info({"id": "other", "role": "student"}) is False


def test_teacher_sees_students_in_their_classes():
    rl = _import_resolver()
    scope = rl.Scope(type="class_list", role="teacher", user_id="t-1",
                     class_ids=["c-1"])
    assert scope.can_see_personal_info({"id": "stu", "role": "student", "class_id": "c-1"}) is True
    assert scope.can_see_personal_info({"id": "stu", "role": "student", "class_id": "c-other"}) is False


def test_teacher_cannot_see_other_teachers():
    rl = _import_resolver()
    scope = rl.Scope(type="class_list", role="teacher", user_id="t-1", class_ids=["c-1"])
    assert scope.can_see_personal_info({"id": "other-t", "role": "teacher"}) is False


# ─── Scope.can_see_financial_data ──────────────────────────────────────────


def test_owner_can_see_financial():
    rl = _import_resolver()
    assert rl.Scope(type="all", role="owner", user_id="o").can_see_financial_data() is True


def test_principal_can_see_financial():
    rl = _import_resolver()
    s = rl.Scope(type="all", role="admin", sub_category="principal", user_id="p")
    assert s.can_see_financial_data() is True


def test_accountant_can_see_financial():
    rl = _import_resolver()
    s = rl.Scope(type="domain", role="admin", sub_category="accountant", user_id="a")
    assert s.can_see_financial_data() is True


def test_transport_head_cannot_see_financial():
    rl = _import_resolver()
    s = rl.Scope(type="domain", role="admin", sub_category="transport_head", user_id="t")
    assert s.can_see_financial_data() is False


def test_receptionist_cannot_see_financial():
    rl = _import_resolver()
    s = rl.Scope(type="domain", role="admin", sub_category="receptionist", user_id="r")
    assert s.can_see_financial_data() is False


def test_support_staff_cannot_see_financial():
    rl = _import_resolver()
    s = rl.Scope(type="self_only", role="admin", sub_category="support_staff", user_id="s")
    assert s.can_see_financial_data() is False


def test_legacy_admin_no_sub_category_cannot_see_financial():
    """Part 1 hardening: previously this leaked financial access via legacy fallback."""
    rl = _import_resolver()
    s = rl.Scope(type="self_only", role="admin", sub_category=None, user_id="leg")
    assert s.can_see_financial_data() is False


def test_teacher_cannot_see_financial():
    rl = _import_resolver()
    s = rl.Scope(type="class_list", role="teacher", user_id="t", class_ids=["c-1"])
    assert s.can_see_financial_data() is False


def test_student_can_see_own_financial():
    """Self-only filter at the query level enforces 'own data'."""
    rl = _import_resolver()
    s = rl.Scope(type="self_only", role="student", user_id="u", student_id="stu")
    assert s.can_see_financial_data() is True


# ─── Scope.is_restricted_to_self ───────────────────────────────────────────


def test_is_restricted_to_self_true_for_self_only():
    rl = _import_resolver()
    assert rl.Scope(type="self_only", role="student", user_id="u").is_restricted_to_self() is True


def test_is_restricted_to_self_false_for_all():
    rl = _import_resolver()
    assert rl.Scope(type="all", role="owner", user_id="o").is_restricted_to_self() is False


def test_is_restricted_to_self_false_for_class_list():
    rl = _import_resolver()
    s = rl.Scope(type="class_list", role="teacher", user_id="t", class_ids=["c"])
    assert s.is_restricted_to_self() is False


# ─── Scope.allowed_collections ─────────────────────────────────────────────


def test_owner_allowed_collections_unrestricted():
    rl = _import_resolver()
    s = rl.Scope(type="all", role="owner", user_id="o")
    assert s.allowed_collections() is None


def test_accountant_allowed_collections_financial_only():
    rl = _import_resolver()
    s = rl.Scope(type="domain", role="admin", sub_category="accountant",
                 domain="financial", user_id="a")
    cols = s.allowed_collections()
    assert cols is not None
    assert "fee_transactions" in cols
    # Accountant cannot see staff_attendance (not financial domain)
    assert "staff_attendance" not in cols


def test_transport_head_allowed_collections_transport_only():
    rl = _import_resolver()
    s = rl.Scope(type="domain", role="admin", sub_category="transport_head",
                 domain="transport", user_id="t")
    cols = s.allowed_collections()
    assert cols is not None
    assert any("transport" in c or "vehicle" in c for c in cols)


def test_scope_rejects_empty_user_id():
    """Part 1.5 Patch E: empty-string user_id must fail closed at construction.

    Without this guard `can_see_personal_info` matched empty-vs-empty and the
    self-only filter became {"user_id": ""} — a permissive oracle.
    """
    rl = _import_resolver()
    with pytest.raises(ValueError):
        rl.Scope(type="all", role="owner", user_id="")


def test_scope_can_see_personal_info_guards_empty_target_id():
    rl = _import_resolver()
    scope = rl.Scope(type="all", role="owner", user_id="real-user")
    # Target dict missing "id" must NOT match owner.user_id by empty-string fall-through.
    assert scope.can_see_personal_info({"role": "student"}) is True  # owner sees all
    # Non-owner (admin/support_staff) without target id should not get a self-match.
    self_scope = rl.Scope(type="self_only", role="admin",
                          sub_category="support_staff", user_id="staff-1")
    assert self_scope.can_see_personal_info({"role": "student"}) is False


# ─── Part 2 Patch P1 ────────────────────────────────────────────────────────

@_async
async def test_resolve_scope_propagates_branch_id_from_jwt():
    """Non-owner users must get scope.branch_id populated from the JWT claim.

    Prior to Patch P1 the field was declared but never set, making
    `_apply_branch_filter` a permanent no-op across the v2 tool surface.
    """
    rl = _import_resolver()
    db = _make_db(staff=[
        {"id": "s-1", "user_id": "u-1", "is_active": True, "role": "teacher",
         "sub_category": "class_teacher", "class_teacher_of": "c-1"},
    ], classes=[{"id": "c-1", "name": "Class 1A"}])
    scope = await rl.resolve_scope(
        {"id": "u-1", "role": "teacher", "branch_id": "branch-A"}, db
    )
    assert scope.branch_id == "branch-A"


@_async
async def test_resolve_scope_owner_branch_id_is_none():
    """Owner intentionally crosses branches — branch_id stays None."""
    rl = _import_resolver()
    db = _make_db()
    scope = await rl.resolve_scope(
        {"id": "u-owner", "role": "owner", "branch_id": "branch-A"}, db
    )
    assert scope.branch_id is None


def test_scope_filter_injects_branch_id_for_type_all():
    """type=all + branch_id should still emit branch_id (was a no-op pre-P1)."""
    rl = _import_resolver()
    s = rl.Scope(type="all", role="admin", sub_category="principal",
                 user_id="p-1", branch_id="branch-A")
    f = s.filter(collection="students")
    assert "branch-A" in str(f), f"expected branch_id in filter, got {f!r}"


def test_scope_filter_injects_branch_id_for_self_only():
    rl = _import_resolver()
    s = rl.Scope(type="self_only", role="admin", sub_category="support_staff",
                 user_id="u-1", branch_id="branch-A")
    f = s.filter(collection="students")
    # Filter has user_id from self-only + branch_id from P1.
    flat = str(f)
    assert "branch-A" in flat
    assert "u-1" in flat
