from __future__ import annotations
"""Routes: assignments, exams, results, subjects, timetable"""
from fastapi import APIRouter, Request, HTTPException, Depends
from database import get_db
from middleware.auth import (
    get_current_user, require_role, require_owner_or_principal,
    require_owner_principal_or_management, require_exam_manager,
    require_exam_editor,
)
from datetime import datetime
from services.audit_service import write_audit_doc
from services.actor_context import actor_ctx_from_user
from services.substitution_service import initiate_substitution
from services.teacher_scope_service import compute_teacher_scope, empty_scope
from services.timetable_service import (
    TimetableConflictError,
    TimetableValidationError,
    ensure_timetable_slot_available,
    normalise_timetable_fields,
    validate_timetable_slot,
)
from services.academic_structure_service import (
    create_subject as svc_create_subject,
    update_subject as svc_update_subject,
    delete_subject as svc_delete_subject,
    AcademicStructureValidationError,
    AcademicStructureNotFoundError,
    AcademicStructureConflictError,
)
from tenant import get_school_id, scoped_query, scoped_filter
import re
import uuid

router = APIRouter(prefix="/api/academics", tags=["academics"])


def get_user(req: Request):
    return get_current_user(req)


def _academic_query(extra: dict | None = None) -> dict:
    return scoped_filter(extra or {}, get_school_id())  # branch-scope: intentional — this file's school-scope helper; it scopes to the school only, and callers pass branch_id through scoped_query where a query is branch-sensitive


async def _map_by_id(collection, ids, projection: dict | None = None) -> dict:
    """NEW-04/T7: one school-scoped ``$in`` read instead of a ``find_one`` per row.

    Returns ``{id: doc}``; empty input issues no query. Tenancy is composed the
    same way the per-row lookups did, via ``_academic_query``.
    """
    unique = sorted({i for i in ids if i})
    if not unique:
        return {}
    q = _academic_query({"id": {"$in": unique}})
    proj = projection if projection is not None else {"_id": 0}
    docs = await collection.find(q, proj).to_list(len(unique))
    return {d["id"]: d for d in docs if d.get("id")}


async def _teacher_can_access_class(db, user: dict, class_id: str | None) -> bool:
    """A teacher may act on a class only if the Academic Structure assigns it to
    them — as the class teacher OR by teaching a subject in it. Non-teachers and
    calls without a class_id pass through (their own gates apply)."""
    if user.get("role") != "teacher" or not class_id:
        return True
    scope = await compute_teacher_scope(db, user, get_school_id())
    return class_id in set(scope["all_class_ids"])


async def _require_teacher_class_access(db, user: dict, class_id: str | None):
    if not await _teacher_can_access_class(db, user, class_id):
        raise HTTPException(403, "Teacher can access only assigned classes")


@router.get("/my-teaching-scope")
async def my_teaching_scope(
    request: Request,
    user: dict = Depends(require_role("teacher", "admin", "owner")),
):
    """Classes & subjects the current teacher is assigned in the Academic Structure.

    Powers per-section filtering on the frontend (Attendance, Assignments, Student
    Performance, Curriculum, Class Analytics, Lesson Plans, PTM Notes). For a
    non-teacher this reports ``is_teacher: False`` with empty lists so the UI knows
    not to restrict anything.
    """
    db = get_db()
    if user.get("role") != "teacher":
        return {"success": True, "data": {"is_teacher": False, **empty_scope()}}
    scope = await compute_teacher_scope(db, user, get_school_id())
    return {"success": True, "data": {"is_teacher": True, **scope}}


def _can_manage_all(user: dict) -> bool:
    return user.get("role") in {"owner", "admin"}


# --- Assignments ---
@router.get("/assignments")
async def list_assignments(request: Request, class_id: str = None):
    db = get_db()
    user = get_user(request)
    query = {}
    if class_id:
        query["class_id"] = class_id
    if user["role"] == "teacher":
        query["teacher_id"] = user["id"]
    elif user["role"] == "student":
        student = await db.students.find_one(_academic_query({"user_id": user["id"]}), {"_id": 0})
        if student:
            query["class_id"] = student["class_id"]
    assignments = await db.assignments.find(_academic_query(query), {"_id": 0}).sort("created_at", -1).to_list(50)
    # NEW-04/T7: two batched lookups (were two find_one calls per assignment).
    subject_map = await _map_by_id(db.subjects, [a.get("subject_id") for a in assignments])
    class_map = await _map_by_id(db.classes, [a.get("class_id") for a in assignments])
    for a in assignments:
        subj = subject_map.get(a.get("subject_id"))
        a["subject_name"] = subj["name"] if subj else "N/A"
        cls = class_map.get(a.get("class_id"))
        a["class_name"] = f"{cls['name']}-{cls['section']}" if cls else "N/A"
    return {"success": True, "data": assignments}


@router.post("/assignments")
async def create_assignment(request: Request, user: dict = Depends(require_role("teacher", "admin", "owner"))):
    db = get_db()
    body = await request.json()
    await _require_teacher_class_access(db, user, body.get("class_id"))
    assignment = {
        "id": str(uuid.uuid4()),
        "class_id": body.get("class_id"),
        "subject_id": body.get("subject_id"),
        "teacher_id": user["id"],
        "title": body.get("title"),
        "description": body.get("description", ""),
        "due_date": body.get("due_date"),
        "is_ai_blocked": body.get("is_ai_blocked", True),
        "created_at": datetime.now().isoformat(),
    }
    await db.assignments.insert_one({**assignment, "_id": assignment["id"], "schoolId": get_school_id()})
    return {"success": True, "data": assignment}


@router.patch("/assignments/{assignment_id}")
async def update_assignment(assignment_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin", "owner"))):
    db = get_db()
    existing = await db.assignments.find_one(_academic_query({"id": assignment_id}), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Assignment not found")
    if user["role"] == "teacher" and existing.get("teacher_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    if "class_id" in body:
        await _require_teacher_class_access(db, user, body.get("class_id"))
    update = {k: v for k, v in body.items() if k in ["title", "description", "due_date", "subject_id", "class_id"]}
    update["updated_at"] = datetime.now().isoformat()
    result = await db.assignments.update_one(_academic_query({"id": assignment_id}), {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Assignment not found")
    return {"success": True}


@router.delete("/assignments/{assignment_id}")
async def delete_assignment(assignment_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin", "owner"))):
    db = get_db()
    existing = await db.assignments.find_one(_academic_query({"id": assignment_id}), {"_id": 0})
    if existing and user["role"] == "teacher" and existing.get("teacher_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    result = await db.assignments.delete_one(_academic_query({"id": assignment_id}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Assignment not found")
    return {"success": True}


# --- Exams ---
@router.get("/exams")
async def list_exams(request: Request, user: dict = Depends(require_role("admin", "owner", "teacher", "staff"))):
    db = get_db()
    exams = await db.exams.find(_academic_query(), {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"success": True, "data": exams}


@router.post("/exams")
async def create_exam(request: Request, user: dict = Depends(require_exam_manager)):
    db = get_db()
    body = await request.json()
    if not (body.get("name") or "").strip():
        raise HTTPException(400, "Exam name is required")
    class_id = body.get("class_id") or None
    if user.get("role") == "teacher" and class_id:
        scope = await compute_teacher_scope(db, user, get_school_id())
        if class_id not in set(scope["all_class_ids"]):
            raise HTTPException(403, "Teacher can only create exams for assigned classes")
    ay = await db.academic_years.find_one(_academic_query({"is_current": True}), {"_id": 0})
    exam = {
        "id": str(uuid.uuid4()),
        "academic_year_id": ay["id"] if ay else None,
        "name": body.get("name").strip(),
        "exam_type": body.get("exam_type", "unit_test"),
        "class_id": class_id,
        "subject_id": body.get("subject_id") or None,
        "start_date": body.get("start_date"),
        "end_date": body.get("end_date"),
        "created_by": user["id"],
        "created_at": datetime.now().isoformat(),
    }
    await db.exams.insert_one({**exam, "_id": exam["id"], "schoolId": get_school_id()})
    return {"success": True, "data": exam}


@router.patch("/exams/{exam_id}")
async def update_exam(exam_id: str, request: Request, user: dict = Depends(require_exam_manager)):
    db = get_db()
    existing = await db.exams.find_one(_academic_query({"id": exam_id}), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Exam not found")
    if user.get("role") == "teacher" and existing.get("created_by") != user["id"]:
        raise HTTPException(403, "Teachers can only edit their own exams")
    body = await request.json()
    allowed = {"name", "exam_type", "class_id", "subject_id", "start_date", "end_date"}
    update = {k: v for k, v in body.items() if k in allowed}
    if "class_id" in update and user.get("role") == "teacher" and update["class_id"]:
        scope = await compute_teacher_scope(db, user, get_school_id())
        if update["class_id"] not in set(scope["all_class_ids"]):
            raise HTTPException(403, "Teacher can only assign exams to their own classes")
    update["updated_at"] = datetime.now().isoformat()
    await db.exams.update_one(_academic_query({"id": exam_id}), {"$set": update})
    updated = await db.exams.find_one(_academic_query({"id": exam_id}), {"_id": 0})
    return {"success": True, "data": updated}


@router.delete("/exams/{exam_id}")
async def delete_exam(exam_id: str, request: Request, user: dict = Depends(require_owner_principal_or_management)):
    db = get_db()
    result = await db.exams.delete_one(_academic_query({"id": exam_id}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Exam not found")
    return {"success": True}


# --- Exam Results ---
@router.get("/results")
async def get_results(request: Request, exam_id: str = None, student_id: str = None, class_id: str = None):
    db = get_db()
    user = get_user(request)
    query = {}
    if exam_id:
        query["exam_id"] = exam_id
    if class_id:
        await _require_teacher_class_access(db, user, class_id)
        class_students = await db.students.find(_academic_query({"class_id": class_id}), {"_id": 0, "id": 1}).to_list(200)
        query["student_id"] = {"$in": [s["id"] for s in class_students]}
    if student_id:
        if user["role"] == "student":
            own = await db.students.find_one(_academic_query({"user_id": user["id"]}), {"_id": 0})
            if not own or own["id"] != student_id:
                raise HTTPException(403, "Forbidden")
        elif user["role"] == "teacher":
            # A teacher may only pull a student's results if that student is in one
            # of their assigned classes (Academic Structure).
            target = await db.students.find_one(_academic_query({"id": student_id}), {"_id": 0})
            await _require_teacher_class_access(db, user, (target or {}).get("class_id"))
        query["student_id"] = student_id
    elif user["role"] == "student" and not class_id:
        own = await db.students.find_one(_academic_query({"user_id": user["id"]}), {"_id": 0})
        if own:
            query["student_id"] = own["id"]
    elif user["role"] == "teacher" and not class_id:
        # No explicit class filter — restrict to students in the teacher's assigned
        # classes so the school-wide results set never leaks across classes.
        scope = await compute_teacher_scope(db, user, get_school_id())
        if not scope["all_class_ids"]:
            return {"success": True, "data": []}
        scoped_students = await db.students.find(
            _academic_query({"class_id": {"$in": scope["all_class_ids"]}}), {"_id": 0, "id": 1},
        ).to_list(2000)
        query["student_id"] = {"$in": [s["id"] for s in scoped_students]}
    if user["role"] == "student":
        query["published"] = True
    results = await db.exam_results.find(_academic_query(query), {"_id": 0}).to_list(500)
    enriched = []
    # NEW-04/T7: two batched lookups (were two find_one calls per result row —
    # up to 1,000 round trips for one screen).
    subject_map = await _map_by_id(db.subjects, [r.get("subject_id") for r in results])
    student_map = await _map_by_id(db.students, [r.get("student_id") for r in results])
    for r in results:
        subj = subject_map.get(r.get("subject_id"))
        student = student_map.get(r.get("student_id"))
        enriched.append({**r, "subject_name": subj["name"] if subj else "N/A", "student_name": student["name"] if student else "N/A"})
    return {"success": True, "data": enriched}


@router.post("/results/bulk")
async def bulk_enter_results(request: Request, user: dict = Depends(require_role("teacher", "admin", "owner"))):
    db = get_db()
    body = await request.json()
    results_data = body.get("results", [])

    if not isinstance(results_data, list) or not results_data:
        raise HTTPException(400, "results array is required")

    exam_map = await _map_by_id(db.exams, [row.get("exam_id") for row in results_data])
    student_map = await _map_by_id(db.students, [row.get("student_id") for row in results_data])
    subject_map = await _map_by_id(db.subjects, [row.get("subject_id") for row in results_data])
    exam_subjects = await db.exam_subjects.find(
        _academic_query({"exam_id": {"$in": list(exam_map)}}), {"_id": 0}
    ).to_list(2000)
    schedule_map = {(row.get("exam_id"), row.get("subject_id")): row for row in exam_subjects}
    existing_rows = await db.exam_results.find(
        _academic_query({
            "exam_id": {"$in": list(exam_map)},
            "student_id": {"$in": list(student_map)},
        }),
        {"_id": 0},
    ).to_list(5000)
    existing_map = {
        (row.get("exam_id"), row.get("student_id"), row.get("subject_id")): row
        for row in existing_rows
    }
    teacher_class_ids = None
    if user.get("role") == "teacher":
        teacher_scope = await compute_teacher_scope(db, user, get_school_id())
        teacher_class_ids = set(teacher_scope["all_class_ids"])

    saved = 0
    errors = []

    for i, r in enumerate(results_data):
        exam_id = r.get("exam_id")
        student_id = r.get("student_id")
        subject_id = r.get("subject_id")
        exam = exam_map.get(exam_id)
        student = student_map.get(student_id)
        subject = subject_map.get(subject_id) if subject_id else None
        if not exam:
            errors.append({"row": i + 1, "student_id": student_id, "reason": "Exam not found"})
            continue
        if not student:
            errors.append({"row": i + 1, "student_id": student_id, "reason": "Student not found"})
            continue
        if exam.get("class_id") and student.get("class_id") != exam.get("class_id"):
            errors.append({"row": i + 1, "student_id": student_id, "reason": "Student is not enrolled in the exam class"})
            continue
        if subject_id and (not subject or subject.get("class_id") != student.get("class_id")):
            errors.append({"row": i + 1, "student_id": student_id, "reason": "Subject does not belong to the student's class"})
            continue
        if exam.get("subject_id") and subject_id != exam.get("subject_id"):
            errors.append({"row": i + 1, "student_id": student_id, "reason": "Subject does not belong to this exam"})
            continue
        if teacher_class_ids is not None and student.get("class_id") not in teacher_class_ids:
            errors.append({"row": i + 1, "student_id": student_id, "reason": "Teacher can only enter results for assigned classes"})
            continue

        marks_value = r["marks_obtained"] if "marks_obtained" in r else r.get("marks", 0)

        # Fetch exam to get max_marks
        schedule = schedule_map.get((exam_id, subject_id), {})
        try:
            marks = float(marks_value)
            max_marks = float(schedule.get("max_marks") or exam.get("max_marks") or r.get("max_marks") or 100)
        except (TypeError, ValueError):
            errors.append({"row": i + 1, "student_id": student_id, "reason": "Marks and max_marks must be numeric"})
            continue

        # Validate marks ceiling — collect error, don't abort
        if max_marks <= 0 or marks < 0 or marks > max_marks:
            errors.append({
                "row": i + 1,
                "student_id": student_id,
                "reason": f"marks {marks} must be between 0 and max_marks {max_marks}",
            })
            continue  # Skip this row, continue processing others

        key = (exam_id, student_id, subject_id)
        existing = existing_map.get(key)
        if existing and (existing.get("is_published") or existing.get("published")):
            errors.append({"row": i + 1, "student_id": student_id, "reason": "Published result requires the correction workflow"})
            continue
        now = datetime.now().isoformat()
        doc = {
            "id": existing.get("id") if existing else str(uuid.uuid4()),
            "exam_id": exam_id,
            "student_id": student_id,
            "subject_id": subject_id,
            "marks_obtained": marks,
            "max_marks": max_marks,
            "grade": r.get("grade", (existing or {}).get("grade")),
            "remarks": r.get("remarks", (existing or {}).get("remarks", "")),
            "is_published": False,  # Results require explicit publish (P14.6)
            "published": False,
            "entered_by": user["id"],
            "created_at": (existing or {}).get("created_at", now),
            "updated_at": now,
        }
        await db.exam_results.update_one(
            _academic_query({"exam_id": exam_id, "student_id": student_id, "subject_id": subject_id}),
            {"$set": {**doc, "schoolId": get_school_id()}, "$setOnInsert": {"_id": doc["id"]}},
            upsert=True,
        )
        existing_map[key] = doc
        saved += 1

    if errors and saved == 0:
        return {"success": False, "saved": 0, "errors": errors}
    elif errors:
        return {"success": "partial", "saved": saved, "errors": errors}
    else:
        return {"success": True, "data": {"saved": saved}}


@router.patch("/results/{result_id}/publish")
async def publish_result(result_id: str, request: Request,
                         user: dict = Depends(require_owner_or_principal)):
    """Admin/owner can publish exam results — makes them visible to students."""
    from datetime import timezone
    db = get_db()
    bid = user.get("branch_id")
    result = await db.exam_results.update_one(
        scoped_query({"id": result_id}, branch_id=bid),
        {"$set": {
            "is_published": True,
            "published": True,
            "published_by": user["id"],
            "published_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Result not found")
    return {"success": True}


@router.patch("/results/{result_id}/correct")
async def correct_published_result(result_id: str, request: Request,
                                   user: dict = Depends(require_owner_or_principal)):
    """Correct a published mark while preserving an immutable before/after record."""
    from datetime import timezone
    import math

    db = get_db()
    bid = user.get("branch_id")
    existing = await db.exam_results.find_one(
        scoped_query({"id": result_id}, branch_id=bid), {"_id": 0}
    )
    if not existing:
        raise HTTPException(404, "Result not found")
    if not (existing.get("is_published") or existing.get("published")):
        raise HTTPException(409, "Only published results require the correction workflow")

    body = await request.json()
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 5:
        raise HTTPException(400, "A correction reason of at least 5 characters is required")
    try:
        marks = float(body.get("marks_obtained", existing.get("marks_obtained")))
        max_marks = float(existing.get("max_marks") or 100)
    except (TypeError, ValueError):
        raise HTTPException(400, "marks_obtained must be numeric")
    if not math.isfinite(marks) or not math.isfinite(max_marks) or marks < 0 or marks > max_marks:
        raise HTTPException(400, f"marks_obtained must be between 0 and {max_marks}")

    now = datetime.now(timezone.utc).isoformat()
    revision = int(existing.get("revision") or 0) + 1
    new_values = {
        "marks_obtained": marks,
        "grade": body.get("grade", existing.get("grade")),
        "remarks": body.get("remarks", existing.get("remarks", "")),
    }
    correction = {
        "id": str(uuid.uuid4()),
        "result_id": result_id,
        "revision": revision,
        "reason": reason,
        "before": {
            "marks_obtained": existing.get("marks_obtained"),
            "grade": existing.get("grade"),
            "remarks": existing.get("remarks", ""),
        },
        "after": new_values,
        "corrected_by": user["id"],
        "corrected_at": now,
        "branch_id": bid,
    }
    from database import get_txn_session
    from services.txn_context import reset_current_session, set_current_session
    session = await get_txn_session()
    token = set_current_session(session)
    try:
        async with session:
            async with session.start_transaction():
                await db.exam_result_corrections.insert_one({
                    **correction, "_id": correction["id"], "schoolId": get_school_id()
                }, session=session)
                revision_filter = {"revision": existing.get("revision")} if "revision" in existing else {
                    "revision": {"$exists": False}
                }
                update_result = await db.exam_results.update_one(
                    scoped_query({"id": result_id, **revision_filter}, branch_id=bid),
                    {"$set": {
                        **new_values,
                        "revision": revision,
                        "last_correction_reason": reason,
                        "corrected_by": user["id"],
                        "corrected_at": now,
                    }},
                    session=session,
                )
                if update_result.matched_count == 0:
                    raise HTTPException(409, "Result changed; refresh before correcting it")
    finally:
        reset_current_session(token)
    updated = await db.exam_results.find_one(
        scoped_query({"id": result_id}, branch_id=bid), {"_id": 0}
    )
    return {"success": True, "data": {"result": updated, "correction": correction}}


@router.get("/results/{result_id}/corrections")
async def list_result_corrections(result_id: str, request: Request,
                                  user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    bid = user.get("branch_id")
    result = await db.exam_results.find_one(
        scoped_query({"id": result_id}, branch_id=bid), {"_id": 0, "id": 1}
    )
    if not result:
        raise HTTPException(404, "Result not found")
    rows = await db.exam_result_corrections.find(
        scoped_query({"result_id": result_id}, branch_id=bid), {"_id": 0}
    ).sort("revision", -1).to_list(100)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


# --- Exam class sheet (auto-fetch subjects + students from Academic Structure) ---
def _is_exam_admin(user: dict) -> bool:
    """Admin sub-roles allowed to manage every subject's exam (Principal/Management)."""
    return user.get("role") == "admin" and user.get("sub_category") in ("principal", "management")


async def _exam_editable_subjects(db, user: dict, class_id: str):
    """Which subjects of ``class_id`` the user may edit for an exam.

    Returns a tuple ``(editable_all, editable_subject_ids)``:
      * owner               → (False, set())            — view only
      * principal/management → (True, None)             — all subjects
      * class teacher        → (True, None)             — all subjects of their class
      * subject teacher      → (False, {their subj ids})
    """
    role = user.get("role")
    if role == "owner":
        return False, set()
    if _is_exam_admin(user):
        return True, None
    if role == "teacher":
        scope = await compute_teacher_scope(db, user, get_school_id())
        if class_id in set(scope["class_teacher_class_ids"]):
            return True, None
        return False, {s["id"] for s in scope["subjects"] if s.get("class_id") == class_id}
    # any other admin sub-role — no edit
    return False, set()


@router.get("/exams/{exam_id}/class/{class_id}/sheet")
async def get_exam_class_sheet(
    exam_id: str, class_id: str, request: Request,
    user: dict = Depends(require_role("admin", "owner", "teacher")),
):
    """Full marks sheet for one exam + one class.

    Subjects and students are auto-fetched from the Academic Structure (the
    single source of truth) so the sheet always reflects the current class roster
    and curriculum even before any marks exist. Each subject carries its
    per-exam schedule (exam_date + max_marks) and a ``can_edit`` flag computed
    from the caller's teaching scope. Owner is always view-only.
    """
    db = get_db()
    exam = await db.exams.find_one(_academic_query({"id": exam_id}), {"_id": 0})
    if not exam:
        raise HTTPException(404, "Exam not found")
    cls = await db.classes.find_one(_academic_query({"id": class_id}), {"_id": 0})
    if not cls:
        raise HTTPException(404, "Class not found")
    await _require_teacher_class_access(db, user, class_id)

    editable_all, editable_subject_ids = await _exam_editable_subjects(db, user, class_id)

    # Subjects from the Academic Structure for this class.
    subjects = await db.subjects.find(_academic_query({"class_id": class_id}), {"_id": 0}).to_list(200)
    sched_docs = await db.exam_subjects.find(
        _academic_query({"exam_id": exam_id, "class_id": class_id}), {"_id": 0},
    ).to_list(200)
    sched_map = {d.get("subject_id"): d for d in sched_docs}
    subject_out = []
    for s in subjects:
        sd = sched_map.get(s["id"], {})
        can_edit_subject = bool(editable_all or (editable_subject_ids and s["id"] in editable_subject_ids))
        subject_out.append({
            "id": s["id"],
            "name": s.get("name"),
            "exam_date": sd.get("exam_date"),
            "max_marks": sd.get("max_marks", 100),
            "can_edit": can_edit_subject,
        })

    # Students from the Academic Structure for this class (active roster only).
    students = await db.students.find(
        _academic_query({"class_id": class_id, "is_active": True}), {"_id": 0, "coordinates": 0},
    ).to_list(500)
    students.sort(key=lambda st: (str(st.get("roll_number") or "~"), str(st.get("name") or "")))
    student_out = [{
        "id": st["id"], "name": st.get("name"),
        "admission_number": st.get("admission_number"), "roll_number": st.get("roll_number"),
    } for st in students]

    student_ids = [st["id"] for st in students]
    results = await db.exam_results.find(
        _academic_query({"exam_id": exam_id, "student_id": {"$in": student_ids}}), {"_id": 0},
    ).to_list(5000) if student_ids else []
    result_out = [{
        "id": r.get("id"), "student_id": r.get("student_id"), "subject_id": r.get("subject_id"),
        "marks_obtained": r.get("marks_obtained"), "max_marks": r.get("max_marks", 100),
        "grade": r.get("grade"), "remarks": r.get("remarks", ""),
        "is_published": bool(r.get("is_published") or r.get("published")),
        "revision": int(r.get("revision") or 0),
    } for r in results]

    return {"success": True, "data": {
        "exam": exam,
        "class": {"id": cls["id"], "name": cls.get("name"), "section": cls.get("section")},
        "subjects": subject_out,
        "students": student_out,
        "results": result_out,
        "can_edit": bool(editable_all or editable_subject_ids),
        "is_owner_view": user.get("role") == "owner",
    }}


@router.put("/exams/{exam_id}/class/{class_id}/schedule")
async def save_exam_schedule(
    exam_id: str, class_id: str, request: Request,
    user: dict = Depends(require_exam_editor),
):
    """Upsert per-subject exam dates + max marks for one exam + class.

    Owner is excluded by ``require_exam_editor``. Teachers may only schedule the
    subjects they teach (class teachers may schedule all subjects of their class).
    """
    db = get_db()
    exam = await db.exams.find_one(_academic_query({"id": exam_id}), {"_id": 0})
    if not exam:
        raise HTTPException(404, "Exam not found")
    cls = await db.classes.find_one(_academic_query({"id": class_id}), {"_id": 0})
    if not cls:
        raise HTTPException(404, "Class not found")
    await _require_teacher_class_access(db, user, class_id)

    editable_all, editable_subject_ids = await _exam_editable_subjects(db, user, class_id)

    class_subjects = await db.subjects.find(_academic_query({"class_id": class_id}), {"_id": 0}).to_list(200)
    valid_ids = {s["id"] for s in class_subjects}

    body = await request.json()
    rows = body.get("subjects", [])
    saved = 0
    for r in rows:
        sid = r.get("subject_id")
        if sid not in valid_ids:
            continue  # ignore subjects that don't belong to this class
        if not (editable_all or (editable_subject_ids and sid in editable_subject_ids)):
            raise HTTPException(403, "You can only schedule your own subjects")
        raw_max = r.get("max_marks")
        try:
            max_marks = float(raw_max) if raw_max not in (None, "") else 100.0
        except (TypeError, ValueError):
            raise HTTPException(400, "max_marks must be a number")
        if max_marks <= 0:
            raise HTTPException(400, "max_marks must be positive")
        new_id = str(uuid.uuid4())
        set_fields = {
            "exam_id": exam_id,
            "class_id": class_id,
            "subject_id": sid,
            "exam_date": (r.get("exam_date") or None),
            "max_marks": max_marks,
            "updated_by": user["id"],
            "updated_at": datetime.now().isoformat(),
            "schoolId": get_school_id(),
        }
        await db.exam_subjects.update_one(
            _academic_query({"exam_id": exam_id, "class_id": class_id, "subject_id": sid}),
            {"$set": set_fields, "$setOnInsert": {"_id": new_id, "id": new_id}},
            upsert=True,
        )
        saved += 1
    return {"success": True, "data": {"saved": saved}}


@router.post("/lesson-plans")
async def create_lesson_plan(request: Request, user: dict = Depends(require_role("teacher", "admin"))):
    db = get_db()
    body = await request.json()
    plan = {
        "id": str(uuid.uuid4()),
        "teacher_id": user["id"],
        "subject_id": body.get("subject_id"),
        "class_id": body.get("class_id"),
        "chapter": body.get("chapter"),
        "content": body.get("content", {}),
        "week": body.get("week"),
        "status": "pending_review" if user.get("role") == "teacher" else body.get("status", "approved"),
        "created_at": datetime.now().isoformat(),
    }
    await _require_teacher_class_access(db, user, plan.get("class_id"))
    await db.lesson_plans.insert_one({**plan, "_id": plan["id"], "schoolId": get_school_id()})
    return {"success": True, "data": plan}


@router.get("/lesson-plans")
async def list_lesson_plans(request: Request):
    db = get_db()
    user = get_user(request)
    query = {}
    if user["role"] == "teacher":
        query["teacher_id"] = user["id"]
    plans = await db.lesson_plans.find(_academic_query(query), {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"success": True, "data": plans}


@router.patch("/lesson-plans/{plan_id}")
async def update_lesson_plan(plan_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin"))):
    db = get_db()
    existing = await db.lesson_plans.find_one(_academic_query({"id": plan_id}), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Not found")
    if user["role"] == "teacher" and existing.get("teacher_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in ["chapter", "subject_id", "class_id", "content", "week"]}
    if user["role"] == "teacher":
        update["status"] = "pending_review"
    update["updated_at"] = datetime.now().isoformat()
    result = await db.lesson_plans.update_one(_academic_query({"id": plan_id}), {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.patch("/lesson-plans/{plan_id}/review")
async def review_lesson_plan(plan_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    body = await request.json()
    status = body.get("status")
    if status not in {"approved", "rejected"}:
        raise HTTPException(400, "status must be approved or rejected")
    existing = await db.lesson_plans.find_one(_academic_query({"id": plan_id}), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Not found")
    update = {
        "status": status,
        "reviewed_by": user["id"],
        "reviewed_at": datetime.now().isoformat(),
        "review_note": body.get("note", ""),
    }
    await db.lesson_plans.update_one(_academic_query({"id": plan_id}), {"$set": update})
    await write_audit_doc(db, {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "entity_type": "lesson_plan",
        "entity_id": plan_id,
        "action": f"lesson_plan_{status}",
        "changed_by": user.get("id"),
        "changed_by_role": user.get("role"),
        "changes": update,
        "created_at": datetime.now().isoformat(),
    }, school_id=get_school_id(), branch_id=user.get("branch_id"))
    return {"success": True, "data": {**existing, **update}}


@router.delete("/lesson-plans/{plan_id}")
async def delete_lesson_plan(plan_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin"))):
    db = get_db()
    existing = await db.lesson_plans.find_one(_academic_query({"id": plan_id}), {"_id": 0})
    if existing and user["role"] == "teacher" and existing.get("teacher_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    result = await db.lesson_plans.delete_one(_academic_query({"id": plan_id}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.get("/lesson-plan-completion")
async def get_lesson_plan_completion(
    request: Request,
    month: str = None,
    user: dict = Depends(require_owner_or_principal),
):
    """Returns per-class lesson plan completion stats for a given month (YYYY-MM)."""
    from datetime import datetime as _dt
    db = get_db()
    bid = user.get("branch_id")

    current_month = month or _dt.now().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", current_month):
        raise HTTPException(400, "month must be in YYYY-MM format")

    # Get all classes
    classes = await db.classes.find(
        scoped_query({}, branch_id=bid), {"_id": 0, "id": 1, "name": 1, "section": 1, "class_teacher_id": 1}
    ).to_list(100)

    result = []
    for cls in classes:
        class_id = cls["id"]

        # Count lesson plans for this class this month
        total_plans = await db.lesson_plans.count_documents(
            scoped_query({"class_id": class_id, "week": {"$regex": f"^{re.escape(current_month)}"}}, branch_id=bid)
        )

        # Count completed plans (those with content or marked_complete)
        completed = await db.lesson_plans.count_documents(
            scoped_query({
                "class_id": class_id,
                "week": {"$regex": f"^{re.escape(current_month)}"},
                "$or": [{"is_complete": True}, {"content": {"$exists": True, "$ne": ""}}]
            }, branch_id=bid)
        )

        # Get teacher name
        teacher_name = "Unassigned"
        if cls.get("class_teacher_id"):
            staff = await db.staff.find_one(scoped_query({"id": cls["class_teacher_id"]}, branch_id=bid))
            if staff:
                teacher_name = staff.get("name", "Unknown")

        pct = round(completed / total_plans * 100, 1) if total_plans > 0 else 0
        result.append({
            "class_id": class_id,
            "class_name": f"{cls.get('name', '')} {cls.get('section', '')}".strip(),
            "teacher_name": teacher_name,
            "total_plans": total_plans,
            "completed": completed,
            "completion_pct": pct,
            "month": current_month,
        })

    result.sort(key=lambda x: x["class_name"])
    return {"success": True, "data": result, "meta": {"count": len(result), "month": current_month}}


@router.post("/question-papers/generate")
async def generate_question_paper(request: Request, user: dict = Depends(require_role("teacher", "admin", "owner"))):
    """Use LLM to generate a question paper."""
    from ai.builtin_skills import with_builtin_habits
    from ai.llm_client import llm_client
    body = await request.json()
    subject = body.get("subject", "Mathematics")
    chapters = body.get("chapters", "all chapters")
    total_marks = body.get("total_marks", 100)
    easy_pct = body.get("easy", 30)
    medium_pct = body.get("medium", 50)
    hard_pct = body.get("hard", 20)
    exam_type = body.get("exam_type", "Unit Test")
    board = "CBSE"

    prompt = f"""Generate a complete {board} {exam_type} question paper for {subject}.
Topics/Chapters: {chapters}
Total Marks: {total_marks}
Difficulty: Easy {easy_pct}%, Medium {medium_pct}%, Hard {hard_pct}%

Format the paper with:
- Section A: Multiple Choice Questions (1 mark each)
- Section B: Short Answer Questions (2-3 marks each)  
- Section C: Long Answer Questions (5-6 marks each)

Include time duration, general instructions, and clear question numbering.
Make questions appropriate for Classes 9-12 CBSE standard."""

    import uuid
    session_id = f"qp-{uuid.uuid4()}"
    try:
        # R1.7 AC2: chat() returns an LLMResult — persist/return result.text ONLY
        # (audit X1: the raw tuple/dict was previously saved as paper content),
        # and surface a real 503 when the model was unavailable.
        result = await llm_client.chat(
            # Owner request 17, 2026-08-06: a generated document is printed and handed
            # to children, so it follows the same plain-language habit as Flo's replies.
            # This prompt is assembled here rather than in ai/prompts.py, which is why
            # it was the one user-facing prose path the habit never reached.
            with_builtin_habits(
                "You are an expert CBSE question paper setter. Generate well-structured, "
                "academically accurate question papers."
            ),
            [{"role": "user", "content": prompt}],
            session_id
        )
        if not result.ok:
            raise HTTPException(503, "AI is temporarily unavailable — could not generate the question paper. Please try again.")
        paper_text = result.text
        # Save to DB
        db = get_db()
        import re as _re
        subj = await db.subjects.find_one({"name": {"$regex": _re.escape(subject), "$options": "i"}}, {"_id": 0})
        qp = {
            "id": str(uuid.uuid4()),
            "teacher_id": user["id"],
            "subject_id": subj["id"] if subj else None,
            "class_id": body.get("class_id"),
            "title": f"{subject} - {exam_type}",
            "chapters": [chapters] if isinstance(chapters, str) else chapters,
            "difficulty_mix": {"easy": easy_pct, "medium": medium_pct, "hard": hard_pct},
            "generated_content": paper_text,
            "total_marks": total_marks,
            "created_at": datetime.now().isoformat(),
        }
        await db.question_papers.insert_one({**qp, "_id": qp["id"], "schoolId": get_school_id()})
        return {"success": True, "data": qp}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {str(e)}")


@router.get("/question-papers")
async def list_question_papers(request: Request):
    user = get_user(request)
    db = get_db()
    query: dict = {}
    if user["role"] == "teacher":
        query["teacher_id"] = user["id"]
    papers = await db.question_papers.find(_academic_query(query), {"_id": 0, "generated_content": 0}).sort("created_at", -1).to_list(20)
    return {"success": True, "data": papers}


@router.get("/question-papers/{paper_id}")
async def get_question_paper(paper_id: str, request: Request):
    user = get_user(request)
    db = get_db()
    paper = await db.question_papers.find_one(_academic_query({"id": paper_id}), {"_id": 0})
    if not paper:
        raise HTTPException(404, "Not found")
    return {"success": True, "data": paper}


@router.patch("/question-papers/{paper_id}")
async def update_question_paper(paper_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin", "owner"))):
    db = get_db()
    existing = await db.question_papers.find_one(_academic_query({"id": paper_id}), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Not found")
    # Teacher ownership check: teachers can only update their own papers
    if user["role"] == "teacher" and existing.get("teacher_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in ["title", "generated_content"]}
    update["updated_at"] = datetime.now().isoformat()
    result = await db.question_papers.update_one(_academic_query({"id": paper_id}), {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/question-papers/{paper_id}")
async def delete_question_paper(paper_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin", "owner"))):
    db = get_db()
    existing = await db.question_papers.find_one(_academic_query({"id": paper_id}), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Not found")
    # Teacher ownership check: teachers can only delete their own papers
    if user["role"] == "teacher" and existing.get("teacher_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    result = await db.question_papers.delete_one(_academic_query({"id": paper_id}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# --- Subjects ---
@router.get("/subjects")
async def list_subjects(request: Request, class_id: str = None, user: dict = Depends(require_role("admin", "owner", "teacher", "staff"))):
    db = get_db()
    query = {}
    if class_id:
        query["class_id"] = class_id
    # Teachers only ever see the subjects the Academic Structure assigns to them
    # (subjects.teacher_id == their user_id). Enforced server-side so every
    # tool/section is scoped regardless of frontend filtering.
    if user.get("role") == "teacher":
        scope = await compute_teacher_scope(db, user, get_school_id())
        if not scope["subject_ids"]:
            return {"success": True, "data": []}
        query["id"] = {"$in": scope["subject_ids"]}
    subjects = await db.subjects.find(_academic_query(query), {"_id": 0}).to_list(100)
    return {"success": True, "data": subjects}


@router.post("/subjects")
async def create_subject(request: Request, user: dict = Depends(require_owner_principal_or_management)):
    """Create a subject under a class (Principal/Management/Owner). Service-backed."""
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_create_subject(db, actor_ctx, body)
    except AcademicStructureValidationError as e:
        raise HTTPException(400, str(e))
    except AcademicStructureNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"success": True, "data": result["subject"]}


@router.patch("/subjects/{subject_id}")
async def update_subject(subject_id: str, request: Request, user: dict = Depends(require_owner_principal_or_management)):
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_update_subject(db, actor_ctx, {**body, "subject_id": subject_id})
    except AcademicStructureNotFoundError as e:
        raise HTTPException(404, str(e))
    except AcademicStructureValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["subject"]}


@router.delete("/subjects/{subject_id}")
async def delete_subject(subject_id: str, request: Request, user: dict = Depends(require_owner_principal_or_management)):
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_delete_subject(db, actor_ctx, {"subject_id": subject_id})
    except AcademicStructureNotFoundError as e:
        raise HTTPException(404, str(e))
    except AcademicStructureConflictError as e:
        raise HTTPException(409, str(e))
    return {"success": True, "data": result}


# --- Timetable ---
@router.get("/timetable/availability")
async def teacher_availability(request: Request, teacher_id: str = None, date: str = None, day_of_week: int = None, user: dict = Depends(require_role("admin", "owner", "teacher"))):
    """Check which periods a teacher is free on a given day."""
    db = get_db()
    query = {}
    if teacher_id:
        query["teacher_id"] = teacher_id
    if day_of_week is not None:
        if not 0 <= day_of_week <= 6:
            raise HTTPException(400, "day_of_week must be from 0 to 6")
        query["day_of_week"] = day_of_week
    elif date:
        from datetime import datetime as dt
        try:
            d = dt.fromisoformat(date)
            query["day_of_week"] = d.weekday()  # 0=Monday
        except ValueError:
            raise HTTPException(400, "Invalid date format; use YYYY-MM-DD")
    slots = await db.timetable_slots.find(query, {"_id": 0}).to_list(50)
    return {"success": True, "data": slots}


@router.get("/timetable/{class_id}")
async def get_timetable(class_id: str, request: Request, user: dict = Depends(require_role("admin", "owner", "teacher", "staff"))):
    db = get_db()
    slots = await db.timetable_slots.find({"class_id": class_id}, {"_id": 0}).sort("day_of_week", 1).to_list(100)
    enriched = []
    # NEW-04/T7: batched (was one subject find_one per timetable slot).
    subject_map = await _map_by_id(db.subjects, [s.get("subject_id") for s in slots])
    for s in slots:
        subj = subject_map.get(s.get("subject_id"))
        s["subject_name"] = subj["name"] if subj else "N/A"
        enriched.append(s)
    return {"success": True, "data": enriched}


@router.post("/timetable")
async def add_timetable_slot(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    body = await request.json()
    target = await db.timetable_slots.find_one({
        "class_id": body.get("class_id"),
        "day_of_week": body.get("day_of_week"),
        "period_number": body.get("period_number"),
    }, {"_id": 0, "id": 1})
    try:
        validated = await validate_timetable_slot(
            db, body, exclude_slot_id=target.get("id") if target else None
        )
    except TimetableValidationError as exc:
        raise HTTPException(400, str(exc))
    except TimetableConflictError as exc:
        raise HTTPException(409, str(exc))
    slot = {"id": target.get("id") if target else str(uuid.uuid4()), **validated}
    await db.timetable_slots.update_one(
        {"class_id": slot["class_id"], "day_of_week": slot["day_of_week"], "period_number": slot["period_number"]},
        {"$set": slot, "$setOnInsert": {"_id": slot["id"]}}, upsert=True
    )
    return {"success": True, "data": slot}


@router.patch("/timetable/{slot_id}")
async def update_timetable_slot(slot_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    body = await request.json()
    existing = await db.timetable_slots.find_one({"id": slot_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Timetable slot not found")
    patch = {key: value for key, value in body.items() if key in {
        "class_id", "subject_id", "teacher_id", "day_of_week", "period_number",
        "start_time", "end_time", "room",
    }}
    if not patch:
        raise HTTPException(400, "No timetable fields supplied")
    try:
        validated = await validate_timetable_slot(db, {**existing, **patch}, exclude_slot_id=slot_id)
    except TimetableValidationError as exc:
        raise HTTPException(400, str(exc))
    except TimetableConflictError as exc:
        raise HTTPException(409, str(exc))
    await db.timetable_slots.update_one({"id": slot_id}, {"$set": validated})
    slot = await db.timetable_slots.find_one({"id": slot_id}, {"_id": 0})
    return {"success": True, "data": slot}


@router.delete("/timetable/{slot_id}")
async def delete_timetable_slot(slot_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    result = await db.timetable_slots.delete_one({"id": slot_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Timetable slot not found")
    return {"success": True}


@router.put("/timetable/import")
async def bulk_import_timetable(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    """Bulk import timetable entries — duplicates (same class+period+day) are replaced."""
    db = get_db()
    body = await request.json()
    entries = body if isinstance(body, list) else body.get("entries", [])
    if not entries:
        raise HTTPException(400, "entries array is required")
    created = replaced = skipped = 0
    # NEW-04/T7: validate referential integrity from two batched reads instead of
    # a class lookup plus a teacher lookup on every imported row.
    valid_class_ids = set(await _map_by_id(db.classes, [e.get("class_id") for e in entries], {"_id": 0, "id": 1}))
    valid_teacher_ids = set(await _map_by_id(db.staff, [e.get("teacher_id") for e in entries], {"_id": 0, "id": 1}))
    subject_docs = await db.subjects.find(
        {"id": {"$in": [e.get("subject_id") for e in entries if e.get("subject_id")]}},
        {"_id": 0, "id": 1, "class_id": 1},
    ).to_list(len(entries))
    valid_subject_classes = {(row.get("id"), row.get("class_id")) for row in subject_docs}
    for entry in entries:
        try:
            slot = normalise_timetable_fields(entry)
        except TimetableValidationError:
            skipped += 1
            continue
        class_id = slot["class_id"]
        day = slot["day_of_week"]
        period = slot["period_number"]
        # Referential integrity: class must exist
        if class_id not in valid_class_ids:
            skipped += 1
            continue
        if (slot["subject_id"], class_id) not in valid_subject_classes:
            skipped += 1
            continue
        # Teacher must exist if provided
        teacher_id = slot["teacher_id"]
        if teacher_id and teacher_id not in valid_teacher_ids:
            skipped += 1
            continue
        # NEW-04/T7 audit: NOT an N+1 to batch away — this is the read-before-write of
        # an upsert loop and must see rows written earlier in this same import.
        existing = await db.timetable_slots.find_one({"class_id": class_id, "day_of_week": day, "period_number": period})
        try:
            await ensure_timetable_slot_available(
                db, slot, exclude_slot_id=existing.get("id") if existing else None
            )
        except TimetableConflictError:
            skipped += 1
            continue
        slot = {
            "id": existing.get("id") if existing else str(uuid.uuid4()),
            **slot,
            "updated_at": datetime.now().isoformat(),
        }
        if existing:
            await db.timetable_slots.update_one(
                {"class_id": class_id, "day_of_week": day, "period_number": period},
                {"$set": slot}
            )
            replaced += 1
        else:
            await db.timetable_slots.insert_one({**slot, "_id": slot["id"]})
            created += 1
    return {"success": True, "data": {"created_count": created, "replaced_count": replaced, "skipped_count": skipped}}


# --- PTM Notes ---
@router.get("/ptm-notes")
async def list_ptm_notes(request: Request, student_id: str = None):
    db = get_db()
    user = get_user(request)
    query = {}
    if student_id:
        query["student_id"] = student_id
    elif user["role"] == "student":
        own = await db.students.find_one(_academic_query({"user_id": user["id"]}), {"_id": 0})
        if own:
            query["student_id"] = own["id"]
            query["shared_with_student"] = True
    elif user["role"] == "teacher":
        query["teacher_id"] = user["id"]
    notes = await db.ptm_notes.find(_academic_query(query), {"_id": 0}).sort("created_at", -1).to_list(50)
    # NEW-04/T7: batched (was one student find_one per note).
    note_student_map = await _map_by_id(db.students, [n.get("student_id") for n in notes])
    for n in notes:
        student = note_student_map.get(n.get("student_id"))
        n["student_name"] = student["name"] if student else "N/A"
        if user["role"] == "student":
            n["notes"] = n.get("student_summary") or n.get("notes")
    return {"success": True, "data": notes}


@router.post("/ptm-notes")
async def create_ptm_note(request: Request, user: dict = Depends(require_role("teacher", "admin", "owner"))):
    db = get_db()
    body = await request.json()
    student = await db.students.find_one(_academic_query({"id": body.get("student_id")}), {"_id": 0})
    await _require_teacher_class_access(db, user, (student or {}).get("class_id"))
    note = {
        "id": str(uuid.uuid4()),
        "student_id": body.get("student_id"),
        "teacher_id": user["id"],
        "notes": body.get("notes"),
        "student_summary": body.get("student_summary", ""),
        "shared_with_student": bool(body.get("shared_with_student", False)),
        "summary_sent": False,
        "created_at": datetime.now().isoformat(),
    }
    await db.ptm_notes.insert_one({**note, "_id": note["id"], "schoolId": get_school_id()})
    return {"success": True, "data": note}


@router.patch("/ptm-notes/{note_id}")
async def update_ptm_note(note_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin", "owner"))):
    db = get_db()
    existing = await db.ptm_notes.find_one(_academic_query({"id": note_id}), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Not found")
    if user["role"] == "teacher" and existing.get("teacher_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in ["notes", "student_id", "student_summary", "shared_with_student"]}
    update["updated_at"] = datetime.now().isoformat()
    result = await db.ptm_notes.update_one(_academic_query({"id": note_id}), {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/ptm-notes/{note_id}")
async def delete_ptm_note(note_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin", "owner"))):
    db = get_db()
    existing = await db.ptm_notes.find_one(_academic_query({"id": note_id}), {"_id": 0})
    if existing and user["role"] == "teacher" and existing.get("teacher_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    result = await db.ptm_notes.delete_one(_academic_query({"id": note_id}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.get("/worksheets")
async def list_worksheets(request: Request):
    db = get_db()
    user = get_user(request)
    query = {}
    if user["role"] == "teacher":
        query["teacher_id"] = user["id"]
    elif user["role"] == "student":
        own = await db.students.find_one(_academic_query({"user_id": user["id"]}), {"_id": 0})
        if own:
            query["class_id"] = own["class_id"]
    worksheets = await db.worksheets.find(_academic_query(query), {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"success": True, "data": worksheets}


@router.post("/worksheets")
async def create_worksheet(request: Request, user: dict = Depends(require_role("teacher", "admin"))):
    db = get_db()
    body = await request.json()
    await _require_teacher_class_access(db, user, body.get("class_id"))
    ws = {
        "id": str(uuid.uuid4()),
        "teacher_id": user["id"],
        "subject_id": body.get("subject_id"),
        "class_id": body.get("class_id"),
        "topic": body.get("topic"),
        "type": body.get("type", "practice"),
        "content": body.get("content", ""),
        "is_ai_blocked": False,
        "created_at": datetime.now().isoformat(),
    }
    await db.worksheets.insert_one({**ws, "_id": ws["id"], "schoolId": get_school_id()})
    return {"success": True, "data": ws}


@router.patch("/worksheets/{ws_id}")
async def update_worksheet(ws_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin"))):
    db = get_db()
    existing = await db.worksheets.find_one(_academic_query({"id": ws_id}), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Not found")
    if user["role"] == "teacher" and existing.get("teacher_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in ["topic", "subject_id", "class_id", "type", "content"]}
    update["updated_at"] = datetime.now().isoformat()
    result = await db.worksheets.update_one(_academic_query({"id": ws_id}), {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/worksheets/{ws_id}")
async def delete_worksheet(ws_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin"))):
    db = get_db()
    existing = await db.worksheets.find_one(_academic_query({"id": ws_id}), {"_id": 0})
    if existing and user["role"] == "teacher" and existing.get("teacher_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    result = await db.worksheets.delete_one(_academic_query({"id": ws_id}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.get("/substitutions")
async def list_substitutions(request: Request, date: str = None, teacher_id: str = None):
    db = get_db()
    user = get_user(request)
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        day_of_week = datetime.fromisoformat(target_date).weekday()
    except ValueError:
        raise HTTPException(400, "Invalid date format; use YYYY-MM-DD")

    if user["role"] == "teacher":
        staff = await db.staff.find_one({"user_id": user["id"]}, {"_id": 0})
        if not staff:
            return {"success": True, "data": []}
        teacher_id = staff["id"]

    if teacher_id:
        assigned = await db.substitutions.find(
            {"substitute_teacher_id": teacher_id, "date": target_date},
            {"_id": 0},
        ).sort("period_number", 1).to_list(50)
        return {"success": True, "data": assigned}

    # auth: teachers see their own substitutions above (early-return);
    # full grid view is owner/admin only.
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    absent_records = await db.staff_attendance.find(
        {"date": target_date, "status": {"$in": ["absent", "leave", "on_leave"]}},
        {"_id": 0},
    ).to_list(100)
    absent_staff_ids = [r.get("staff_id") for r in absent_records if r.get("staff_id")]
    absent_staff = await db.staff.find({"id": {"$in": absent_staff_ids}}, {"_id": 0}).to_list(len(absent_staff_ids)) if absent_staff_ids else []
    absent_by_id = {s["id"]: s for s in absent_staff}
    existing_subs = await db.substitutions.find({"date": target_date}, {"_id": 0}).to_list(200)
    sub_by_slot = {(s.get("absent_teacher_id"), s.get("period_number"), s.get("class_id")): s for s in existing_subs}
    busy_teacher_periods = {(s.get("substitute_teacher_id"), s.get("period_number")) for s in existing_subs if s.get("substitute_teacher_id")}

    slots = await db.timetable_slots.find(
        {"teacher_id": {"$in": absent_staff_ids}, "day_of_week": day_of_week},
        {"_id": 0},
    ).sort("period_number", 1).to_list(200)
    all_teachers = await db.staff.find(
        {"staff_type": "teacher", "is_active": {"$ne": False}, "id": {"$nin": absent_staff_ids}},
        {"_id": 0, "id": 1, "name": 1, "subject": 1},
    ).to_list(300)

    result = []
    # NEW-04/T7: three batched reads replace three queries per slot. The busy-teacher
    # map is built once for every period on this day; classes and subjects are `$in`ed.
    needed_periods = sorted({s.get("period_number") for s in slots if s.get("period_number") is not None})
    busy_by_period: dict = {}
    if needed_periods:
        busy_rows = await db.timetable_slots.find(
            {"day_of_week": day_of_week, "period_number": {"$in": needed_periods}, "teacher_id": {"$ne": ""}},
            {"_id": 0, "teacher_id": 1, "period_number": 1},
        ).to_list(20000)
        for b in busy_rows:
            busy_by_period.setdefault(b.get("period_number"), set()).add(b.get("teacher_id"))
    slot_class_map = await _map_by_id(db.classes, [s.get("class_id") for s in slots])
    slot_subject_map = await _map_by_id(db.subjects, [s.get("subject_id") for s in slots])

    for slot in slots:
        period = slot.get("period_number")
        busy_ids = set(busy_by_period.get(period, set())) | {tid for tid, p in busy_teacher_periods if p == period}
        candidates = [t for t in all_teachers if t["id"] not in busy_ids][:5]
        cls = slot_class_map.get(slot.get("class_id"))
        subj = slot_subject_map.get(slot.get("subject_id"))
        existing = sub_by_slot.get((slot.get("teacher_id"), period, slot.get("class_id")))
        result.append({
            "date": target_date,
            "day_of_week": day_of_week,
            "absent_teacher_id": slot.get("teacher_id"),
            "absent_teacher_name": absent_by_id.get(slot.get("teacher_id"), {}).get("name", slot.get("teacher_id")),
            "period_number": period,
            "class_id": slot.get("class_id"),
            "class_name": f"{cls.get('name', '')}-{cls.get('section', '')}" if cls else slot.get("class_id"),
            "subject_id": slot.get("subject_id"),
            "subject_name": subj.get("name") if subj else slot.get("subject_id", ""),
            "room": slot.get("room", ""),
            "assigned_substitute": existing,
            "candidate_substitutes": candidates,
        })
    return {"success": True, "data": result, "meta": {"date": target_date, "absent_teacher_count": len(absent_staff_ids), "uncovered_period_count": len([r for r in result if not r.get("assigned_substitute")])}}


@router.post("/substitutions")
async def create_substitution(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    body = await request.json()
    required = ["date", "absent_teacher_id", "substitute_teacher_id", "class_id", "period_number"]
    if any(not body.get(field) for field in required):
        raise HTTPException(400, "date, absent_teacher_id, substitute_teacher_id, class_id, and period_number are required")
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    params = {
        "date": body["date"],
        "absent_teacher_id": body["absent_teacher_id"],
        "substitute_teacher_id": body["substitute_teacher_id"],
        "class_id": body["class_id"],
        "subject_id": body.get("subject_id", ""),
        "period_number": body["period_number"],
    }
    result = await initiate_substitution(db, actor_ctx, params)
    return {"success": True, "data": result["substitution"]}


# --- Curriculum Progress ---
@router.get("/curriculum")
async def list_curriculum(request: Request, class_id: str = None, subject_id: str = None):
    db = get_db()
    user = get_user(request)
    query = {}
    if user["role"] == "teacher":
        query["updated_by"] = user["id"]
    if class_id:
        query["class_id"] = class_id
    if subject_id:
        query["subject_id"] = subject_id
    progress = await db.curriculum_progress.find(query, {"_id": 0}).to_list(100)
    return {"success": True, "data": progress}


@router.post("/curriculum")
async def update_curriculum(request: Request, user: dict = Depends(require_role("teacher", "admin"))):
    db = get_db()
    body = await request.json()
    doc = {
        "id": str(uuid.uuid4()),
        "class_id": body.get("class_id"),
        "subject_id": body.get("subject_id"),
        "topic": body.get("topic"),
        "status": body.get("status", "not_started"),
        "updated_by": user["id"],
        "updated_at": datetime.now().isoformat(),
    }
    await db.curriculum_progress.update_one(
        {"class_id": doc["class_id"], "subject_id": doc["subject_id"], "topic": doc["topic"]},
        {"$set": {**doc, "_id": doc["id"]}}, upsert=True
    )
    return {"success": True, "data": doc}


@router.patch("/curriculum/{item_id}")
async def patch_curriculum(item_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin"))):
    db = get_db()
    body = await request.json()
    update = {k: v for k, v in body.items() if k in ["topic", "status", "class_id", "subject_id"]}
    update["updated_at"] = datetime.now().isoformat()
    result = await db.curriculum_progress.update_one({"id": item_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/curriculum/{item_id}")
async def delete_curriculum(item_id: str, request: Request, user: dict = Depends(require_role("teacher", "admin"))):
    db = get_db()
    result = await db.curriculum_progress.delete_one({"id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}
