"""Subject CRUD service tests — Academic Structure section (classes + subjects).

Covers the new `create_subject` / `update_subject` / `delete_subject` service
functions: validation, class-existence FK, teacher linking, no-op short-circuit,
and the exam-results referential-integrity guard on delete.
"""

from __future__ import annotations

import copy

import pytest

from services.actor_context import actor_ctx_from_user
from services import academic_structure_service as svc

pytestmark = pytest.mark.asyncio

OWNER = {"id": "o1", "role": "owner", "name": "Owner"}
SCHOOL = "aaryans-joya"

_MUTATED = ("subjects", "exam_results", "classes", "audit_logs")


@pytest.fixture(autouse=True)
def _restore_fake_db(fake_db):
    saved = {col: copy.deepcopy(getattr(fake_db, col).docs) for col in _MUTATED}
    yield
    for col, docs in saved.items():
        getattr(fake_db, col).docs[:] = docs


def _seed_class(fake_db, cid="c-sub-1"):
    fake_db.classes.docs.append({"id": cid, "schoolId": SCHOOL, "name": "Class 9", "section": "A", "branch_id": ""})
    return cid


async def test_create_subject_requires_name(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    with pytest.raises(svc.AcademicStructureValidationError):
        await svc.create_subject(fake_db, ctx, {"class_id": "c-x"})


async def test_create_subject_requires_class_id(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    with pytest.raises(svc.AcademicStructureValidationError):
        await svc.create_subject(fake_db, ctx, {"name": "Math"})


async def test_create_subject_unknown_class_raises_not_found(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    with pytest.raises(svc.AcademicStructureNotFoundError):
        await svc.create_subject(fake_db, ctx, {"name": "Math", "class_id": "does-not-exist"})


async def test_create_subject_success_with_teacher_and_defaults(fake_db):
    cid = _seed_class(fake_db)
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    result = await svc.create_subject(
        fake_db, ctx, {"name": "  Mathematics  ", "class_id": cid, "teacher_id": "user-teacher-001"})
    subj = result["subject"]
    assert subj["name"] == "Mathematics"          # trimmed
    assert subj["class_id"] == cid
    assert subj["teacher_id"] == "user-teacher-001"
    assert subj["max_marks"] == 100               # default
    assert subj["pass_marks"] == 33               # default
    assert subj["schoolId"] == SCHOOL
    assert any(s["id"] == subj["id"] for s in fake_db.subjects.docs)
    assert any(a.get("action") == "subject_create" for a in fake_db.audit_logs.docs)


async def test_update_subject_relinks_teacher(fake_db):
    cid = _seed_class(fake_db)
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    created = await svc.create_subject(fake_db, ctx, {"name": "Science", "class_id": cid})
    sid = created["subject"]["id"]
    updated = await svc.update_subject(fake_db, ctx, {"subject_id": sid, "teacher_id": "user-teacher-002", "pass_marks": 40})
    assert updated["noop"] is False
    assert updated["subject"]["teacher_id"] == "user-teacher-002"
    assert updated["subject"]["pass_marks"] == 40


async def test_update_subject_noop_when_unchanged(fake_db):
    cid = _seed_class(fake_db)
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    created = await svc.create_subject(fake_db, ctx, {"name": "English", "class_id": cid})
    sid = created["subject"]["id"]
    res = await svc.update_subject(fake_db, ctx, {"subject_id": sid, "name": "English"})
    assert res["noop"] is True


async def test_update_subject_unknown_raises_not_found(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    with pytest.raises(svc.AcademicStructureNotFoundError):
        await svc.update_subject(fake_db, ctx, {"subject_id": "nope", "name": "X"})


async def test_delete_subject_success(fake_db):
    cid = _seed_class(fake_db)
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    created = await svc.create_subject(fake_db, ctx, {"name": "Hindi", "class_id": cid})
    sid = created["subject"]["id"]
    res = await svc.delete_subject(fake_db, ctx, {"subject_id": sid})
    assert res["deleted"] is True
    assert not any(s["id"] == sid for s in fake_db.subjects.docs)


async def test_create_class_defaults_to_current_academic_year(fake_db):
    # When no academic_year_id is passed, the service ties the class to the
    # current academic year (seeded "year-1"/is_current) so panel-created classes
    # match seeded ones.
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    result = await svc.create_class(fake_db, ctx, {"name": "Class 11", "section": "C"})
    assert result["class"]["academic_year_id"] == "year-1"


async def test_create_class_honors_explicit_academic_year(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    result = await svc.create_class(fake_db, ctx, {"name": "Class 12", "academic_year_id": "year-custom"})
    assert result["class"]["academic_year_id"] == "year-custom"


async def test_delete_subject_blocked_when_exam_results_exist(fake_db):
    cid = _seed_class(fake_db)
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    created = await svc.create_subject(fake_db, ctx, {"name": "SST", "class_id": cid})
    sid = created["subject"]["id"]
    fake_db.exam_results.docs.append({"id": "er-1", "schoolId": SCHOOL, "subject_id": sid})
    with pytest.raises(svc.AcademicStructureConflictError):
        await svc.delete_subject(fake_db, ctx, {"subject_id": sid})
    assert any(s["id"] == sid for s in fake_db.subjects.docs)   # deletion aborted
