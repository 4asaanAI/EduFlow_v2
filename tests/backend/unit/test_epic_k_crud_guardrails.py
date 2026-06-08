"""Epic K — adversarial & edge-case regression guards for school-internals CRUD.

Covers Phase-1 Owner/Principal lockdown on every new write tool, destructive-flag
registration, validation/not-found edges, and no-op short-circuits across the
fee-config (K.1), academic-structure (K.2), and org-config (K.3) tools.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2
from ai.tool_functions_v2 import TOOL_REGISTRY
from routes.chat import _is_tool_authorized
from services.actor_context import actor_ctx_from_user
from services import fee_config_service, academic_structure_service, org_config_service

pytestmark = pytest.mark.asyncio

OWNER = {"id": "o1", "role": "owner", "name": "Owner"}
PRINCIPAL = {"id": "p1", "role": "admin", "sub_category": "principal", "name": "Principal"}
ACCOUNTANT = {"id": "a1", "role": "admin", "sub_category": "accountant", "name": "Acct"}
TEACHER = {"id": "t1", "role": "teacher", "name": "Teacher"}
STUDENT = {"id": "s1", "role": "student", "name": "Pupil"}

K1_TOOLS = [
    "create_fee_structure", "update_fee_structure",
    "create_discount_type", "update_discount_type", "delete_discount_type",
]
K2_TOOLS = [
    "create_class", "update_class", "delete_class",
    "create_house", "update_house", "delete_house",
]
# K.3 org-config tools are OWNER-ONLY (org config stays owner-only even in Phase 2, AD15).
K3_OWNER_ONLY_TOOLS = [
    "create_branch", "update_branch", "delete_branch",
    "update_school_settings", "year_end_transition",
]
K_OWNER_PRINCIPAL_TOOLS = K1_TOOLS + K2_TOOLS
K_TOOLS = K_OWNER_PRINCIPAL_TOOLS + K3_OWNER_ONLY_TOOLS
K_DESTRUCTIVE_TOOLS = ["delete_discount_type", "delete_class", "delete_house",
                       "delete_branch", "year_end_transition"]
K_NON_DESTRUCTIVE = [t for t in K_TOOLS if t not in K_DESTRUCTIVE_TOOLS]

# `fake_db` is a shared session-level singleton; the service edge-case tests below
# append rows. Save & restore the touched collections so nothing leaks into other
# tests (e.g. student counts consumed by fee summaries / year-end).
_MUTATED = ("fee_structures", "fee_discount_types", "classes", "houses",
            "branches", "students", "school_settings", "audit_logs")


@pytest.fixture(autouse=True)
def _restore_fake_db(fake_db):
    saved = {col: copy.deepcopy(getattr(fake_db, col).docs) for col in _MUTATED}
    yield
    for col, docs in saved.items():
        getattr(fake_db, col).docs[:] = docs


# ── Phase-1 lockdown: K.1/K.2 write tools are Owner+Principal ─────────────────
@pytest.mark.parametrize("tool_name", K_OWNER_PRINCIPAL_TOOLS)
def test_lockdown_allows_owner_and_principal(tool_name):
    tdef = TOOL_REGISTRY[tool_name]
    assert _is_tool_authorized(OWNER, tdef) is True
    assert _is_tool_authorized(PRINCIPAL, tdef) is True


# ── K.3 org-config write tools are Owner-ONLY (principal blocked) ─────────────
@pytest.mark.parametrize("tool_name", K3_OWNER_ONLY_TOOLS)
def test_org_config_is_owner_only(tool_name):
    tdef = TOOL_REGISTRY[tool_name]
    assert _is_tool_authorized(OWNER, tdef) is True
    assert _is_tool_authorized(PRINCIPAL, tdef) is False


@pytest.mark.parametrize("tool_name", K_TOOLS)
@pytest.mark.parametrize("actor", [ACCOUNTANT, TEACHER, STUDENT])
def test_lockdown_blocks_everyone_else(tool_name, actor):
    # Even accountant (whom the REST discount-type route permits) is blocked on
    # the AI surface during Phase 1 — widened only in Phase 2 (Epic H).
    tdef = TOOL_REGISTRY[tool_name]
    assert _is_tool_authorized(actor, tdef) is False


# ── Destructive registration (F.10/FR42) ─────────────────────────────────────
@pytest.mark.parametrize("tool_name", K_DESTRUCTIVE_TOOLS)
def test_destructive_tools_flagged(tool_name):
    assert TOOL_REGISTRY[tool_name].get("destructive") is True


@pytest.mark.parametrize("tool_name", K_NON_DESTRUCTIVE)
def test_non_destructive_tools_not_flagged(tool_name):
    assert not TOOL_REGISTRY[tool_name].get("destructive")


# ── Fee-config edge cases ─────────────────────────────────────────────────────
async def test_create_discount_type_missing_fields_raises(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(fee_config_service.FeeConfigValidationError):
        await fee_config_service.create_discount_type(fake_db, ctx, {"name": "X"})


async def test_create_discount_type_bad_value_type_raises(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(fee_config_service.FeeConfigValidationError):
        await fee_config_service.create_discount_type(fake_db, ctx, {
            "name": "X", "value": 5, "value_type": "bogus",
            "recurrence": "one-time", "reason_note": "n",
        })


async def test_update_discount_type_no_editable_fields_raises(fake_db):
    fake_db.fee_discount_types.docs.append(
        {"id": "dt-1", "schoolId": "aaryans-joya", "name": "Sib", "is_active": True})
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(fee_config_service.FeeConfigValidationError):
        await fee_config_service.update_discount_type(fake_db, ctx, {"discount_type_id": "dt-1", "value": 99})


async def test_update_discount_type_not_found_raises(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(fee_config_service.FeeConfigNotFoundError):
        await fee_config_service.update_discount_type(fake_db, ctx, {"discount_type_id": "nope", "name": "X"})


async def test_delete_discount_type_not_found_raises(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(fee_config_service.FeeConfigNotFoundError):
        await fee_config_service.delete_discount_type(fake_db, ctx, {"discount_type_id": "nope"})


async def test_update_fee_structure_not_found_raises(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(fee_config_service.FeeConfigNotFoundError):
        await fee_config_service.update_fee_structure(fake_db, ctx, {"structure_id": "nope", "name": "X"})


async def test_update_fee_structure_strips_immutable_keys(fake_db):
    fake_db.fee_structures.docs.append(
        {"_id": "fs-1", "id": "fs-1", "schoolId": "aaryans-joya", "name": "Orig"})
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    await fee_config_service.update_fee_structure(
        fake_db, ctx, {"structure_id": "fs-1", "name": "New", "schoolId": "evil", "id": "evil"})
    doc = fake_db.fee_structures.docs[0]
    assert doc["name"] == "New"
    assert doc["schoolId"] == "aaryans-joya"   # immutable key NOT overwritten
    assert doc["id"] == "fs-1"


# ── Academic-structure edge cases (K.2) ───────────────────────────────────────
async def test_create_class_requires_name(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(academic_structure_service.AcademicStructureValidationError):
        await academic_structure_service.create_class(fake_db, ctx, {"section": "A"})


async def test_principal_cannot_create_class_in_other_branch(fake_db):
    # NFR5: a branch-scoped principal must NOT escape their branch by passing an
    # arbitrary branch_id param — the service pins them to their own branch.
    ctx = actor_ctx_from_user(
        {"id": "p1", "role": "admin", "sub_category": "principal", "branch_id": "branch-a"},
        school_id="aaryans-joya",
    )
    result = await academic_structure_service.create_class(
        fake_db, ctx, {"name": "Sneaky 10", "branch_id": "branch-b"})
    assert result["class"]["branch_id"] == "branch-a"   # forced to own branch, not branch-b


async def test_owner_may_target_branch_on_create_class(fake_db):
    # Owner has cross-branch authority — an explicit branch_id is honored.
    ctx = actor_ctx_from_user(
        {"id": "o1", "role": "owner", "branch_id": None}, school_id="aaryans-joya")
    result = await academic_structure_service.create_class(
        fake_db, ctx, {"name": "Class 10", "branch_id": "branch-b"})
    assert result["class"]["branch_id"] == "branch-b"


async def test_delete_class_blocked_when_active_students_assigned(fake_db):
    fake_db.classes.docs.append({"id": "c-1", "schoolId": "aaryans-joya", "name": "C1", "branch_id": ""})
    fake_db.students.docs.append(
        {"id": "s-1", "schoolId": "aaryans-joya", "class_id": "c-1", "is_active": True})
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(academic_structure_service.AcademicStructureConflictError):
        await academic_structure_service.delete_class(fake_db, ctx, {"class_id": "c-1"})
    # class still present (deletion aborted)
    assert any(c["id"] == "c-1" for c in fake_db.classes.docs)


async def test_delete_house_blocked_when_active_students_assigned(fake_db):
    fake_db.houses.docs.append({"id": "h-1", "schoolId": "aaryans-joya", "name": "Red"})
    fake_db.students.docs.append(
        {"id": "s-2", "schoolId": "aaryans-joya", "house": "Red", "is_active": True})
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(academic_structure_service.AcademicStructureConflictError):
        await academic_structure_service.delete_house(fake_db, ctx, {"house_id": "h-1"})


async def test_update_class_noop_when_unchanged(fake_db):
    fake_db.classes.docs.append(
        {"id": "c-2", "schoolId": "aaryans-joya", "name": "C2", "room_number": "R1", "branch_id": ""})
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    result = await academic_structure_service.update_class(
        fake_db, ctx, {"class_id": "c-2", "room_number": "R1"})
    assert result["noop"] is True
    assert not [a for a in fake_db.audit_logs.docs if a.get("entity_type") == "class"]


async def test_update_class_not_found_raises(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(academic_structure_service.AcademicStructureNotFoundError):
        await academic_structure_service.update_class(fake_db, ctx, {"class_id": "nope", "name": "X"})


# ── Org-config edge cases (K.3) ───────────────────────────────────────────────
async def test_create_branch_requires_name(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(org_config_service.OrgConfigValidationError):
        await org_config_service.create_branch(fake_db, ctx, {"branch_code": "X"})


async def test_year_end_requires_new_year_name(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(org_config_service.OrgConfigValidationError):
        await org_config_service.year_end_transition(fake_db, ctx, {})


async def test_delete_branch_not_found_raises(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(org_config_service.OrgConfigNotFoundError):
        await org_config_service.delete_branch(fake_db, ctx, {"branch_id": "nope"})


async def test_delete_branch_blocked_when_active_students_assigned(fake_db):
    fake_db.branches.docs.append({"id": "br-x", "schoolId": "aaryans-joya", "name": "Old"})
    fake_db.students.docs.append(
        {"id": "s-9", "schoolId": "aaryans-joya", "branch_id": "br-x", "is_active": True})
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    with pytest.raises(org_config_service.OrgConfigConflictError):
        await org_config_service.delete_branch(fake_db, ctx, {"branch_id": "br-x"})


async def test_update_school_settings_strips_unknown_fields(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya")
    result = await org_config_service.update_school_settings(
        fake_db, ctx, {"school_name": "X", "evil_field": "drop me"})
    assert "evil_field" not in result["updated"]
    assert result["updated"]["school_name"] == "X"
