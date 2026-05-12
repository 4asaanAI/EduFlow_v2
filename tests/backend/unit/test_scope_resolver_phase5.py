"""
Unit Tests: Phase 5 scope resolver role matrix.
"""

import pytest

from ai.scope_resolver import resolve_scope
from tests.backend.conftest import FakeCollection


@pytest.fixture
def scope_db():
    return type(
        "ScopeDb",
        (),
        {
            "students": FakeCollection(),
            "staff": FakeCollection(),
            "classes": FakeCollection(),
            "subjects": FakeCollection(),
        },
    )()


@pytest.mark.asyncio
async def test_owner_scope_is_unrestricted(scope_db):
    scope = await resolve_scope({"id": "owner-1", "role": "owner"}, scope_db)

    assert scope.type == "all"
    assert scope.filter(collection="students") == {}
    assert scope.can_see_financial_data() is True
    assert scope.allowed_collections() is None


@pytest.mark.asyncio
async def test_admin_sub_categories_resolve_to_expected_domains(scope_db):
    scope_db.staff.docs[:] = [
        {"id": "staff-principal", "user_id": "principal-1", "is_active": True, "sub_category": "principal"},
        {"id": "staff-accountant", "user_id": "accountant-1", "is_active": True, "sub_category": "accountant"},
        {"id": "staff-transport", "user_id": "transport-1", "is_active": True, "sub_category": "transport_head"},
        {"id": "staff-support", "user_id": "support-1", "is_active": True, "sub_category": "support_staff"},
    ]

    principal = await resolve_scope({"id": "principal-1", "role": "admin"}, scope_db)
    accountant = await resolve_scope({"id": "accountant-1", "role": "admin"}, scope_db)
    transport = await resolve_scope({"id": "transport-1", "role": "admin"}, scope_db)
    support = await resolve_scope({"id": "support-1", "role": "admin"}, scope_db)

    assert principal.type == "all"
    assert principal.can_see_financial_data() is True
    assert accountant.type == "domain"
    assert accountant.domain == "financial"
    assert "fee_transactions" in accountant.allowed_collections()
    assert accountant.can_see_personal_info({"id": "student-1", "role": "student"}) is True
    assert accountant.can_see_personal_info({"id": "staff-2", "role": "teacher"}) is False
    assert transport.type == "domain"
    assert transport.domain == "transport"
    assert transport.can_see_financial_data() is False
    assert support.type == "self_only"
    assert support.filter(collection="staff") == {"user_id": "support-1"}


@pytest.mark.asyncio
async def test_teacher_class_scope_limits_filters_and_personal_info(scope_db):
    scope_db.staff.docs[:] = [
        {
            "id": "staff-teacher",
            "user_id": "teacher-1",
            "is_active": True,
            "sub_category": "class_teacher",
            "class_teacher_of": "class-1",
        }
    ]

    scope = await resolve_scope({"id": "teacher-1", "role": "teacher"}, scope_db)

    assert scope.type == "class_list"
    assert scope.filter(collection="students") == {"class_id": {"$in": ["class-1"]}}
    assert scope.filter(collection="classes") == {"id": {"$in": ["class-1"]}}
    assert scope.can_see_personal_info({"id": "student-1", "role": "student", "class_id": "class-1"}) is True
    assert scope.can_see_personal_info({"id": "student-2", "role": "student", "class_id": "class-2"}) is False
    assert scope.can_see_financial_data() is False


@pytest.mark.asyncio
async def test_student_scope_is_self_only_by_student_record(scope_db):
    scope_db.students.docs[:] = [
        {
            "id": "student-1",
            "user_id": "student-user-1",
            "is_active": True,
            "name": "Demo Student",
        }
    ]

    scope = await resolve_scope({"id": "student-user-1", "role": "student"}, scope_db)

    assert scope.type == "self_only"
    assert scope.student_id == "student-1"
    assert scope.filter(collection="students") == {"id": "student-1"}
    assert scope.filter(collection="fee_transactions") == {"student_id": "student-1"}
    assert scope.can_see_personal_info({"id": "student-user-1", "role": "student"}) is True
    assert scope.can_see_personal_info({"id": "student-user-2", "role": "student"}) is False


@pytest.mark.asyncio
async def test_unrecognized_role_or_subcategory_denies_to_self_only(scope_db):
    scope_db.staff.docs[:] = [
        {"id": "staff-unknown", "user_id": "admin-unknown", "is_active": True, "sub_category": "mystery_admin"}
    ]

    unknown_admin = await resolve_scope({"id": "admin-unknown", "role": "admin"}, scope_db)
    unknown_role = await resolve_scope({"id": "guest-1", "role": "guest"}, scope_db)

    assert unknown_admin.type == "self_only"
    assert unknown_admin.filter(collection="students") == {"user_id": "admin-unknown"}
    assert unknown_role.type == "self_only"
    assert unknown_role.filter(collection="students") == {"user_id": "guest-1"}
