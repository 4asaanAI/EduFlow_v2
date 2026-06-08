"""Student CRUD service — the single shared write path for student records
(AI Layer Hardening, AD7 / AD15 / Epic J, Story J.1).

Both the REST routes (`POST /api/students/`, `PATCH /api/students/{id}`,
`PUT /api/students/{id}/guardians`) and the new AI tools (`create_student`,
`update_student`, `manage_student_guardians`, `set_student_status`) call into the
functions here, so an AI-created/edited student is byte-identical to the panel result.

Student **hard-delete** (`DELETE /students/{id}`) and **DPDP-erase**
(`/students/{id}/erase`) are deliberately NOT in this service's AI-reachable surface
— they stay UI-only (AD15). Photo upload (binary) stays a REST route; the assistant
sets `photo_url` through `update_student`.

Services raise domain exceptions, never `HTTPException`.
"""

from __future__ import annotations

import uuid
from typing import Optional

from models.schemas import Guardian, Student
from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import scoped_filter

# Field whitelists — the SAME sets the REST route enforces (keep in lockstep).
UPDATABLE_FIELDS = {
    "name", "class_id", "admission_number", "roll_number", "dob", "gender",
    "blood_group", "height_cm", "weight_kg", "medical_notes", "emergency_contact",
    "house", "photo_url", "uses_transport", "bus_route", "route_zone_id", "status",
}
TRANSPORT_HEAD_FIELDS = {"route_zone_id", "uses_transport", "bus_route"}


class StudentValidationError(Exception):
    """Bad/empty input → HTTP 400."""


class StudentNotFoundError(Exception):
    """Student id not found in tenant → HTTP 404."""


class StudentConflictError(Exception):
    """Duplicate admission number → HTTP 409."""


class ClassNotFoundError(Exception):
    """class_id not found in tenant → HTTP 404."""


class ClassValidationError(Exception):
    """Class not in current academic year → HTTP 400."""


def _session_kwargs(session) -> dict:
    return _txn_session_kwargs(session)


def _serialize(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _is_transport_head(actor_ctx: ActorContext) -> bool:
    return actor_ctx.role == "admin" and actor_ctx.sub_category == "transport_head"


async def _validate_class(db, school_id: str, class_id: str) -> dict:
    cls = await db.classes.find_one(scoped_filter({"id": class_id}, school_id), {"_id": 0})
    if not cls:
        raise ClassNotFoundError("Class not found")
    current_year = await db.academic_years.find_one(
        scoped_filter({"is_current": True}, school_id), {"_id": 0}
    )
    class_year = cls.get("academic_year_id")
    if current_year and class_year and class_year != current_year.get("id"):
        raise ClassValidationError("Class does not belong to the current academic year")
    return cls


async def _write_student_audit(
    db, actor_ctx: ActorContext, *, action: str, student_id: str,
    changes: Optional[dict] = None, reason: Optional[str] = None, session=None,
) -> None:
    record = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "entity_type": "student",
        "entity_id": student_id,
        "action": action,
        "changed_by": actor_ctx.user_id,
        "changed_by_role": actor_ctx.role,
        "changes": changes or {},
        "reason": reason,
        "created_at": actor_ctx.now_iso(),
    }
    await write_audit_doc(
        db, record, school_id=actor_ctx.school_id, branch_id=actor_ctx.branch_id,
    )


async def create_student(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Create a student (+ derived guardians) identically to `POST /api/students/`.

    params: ``{name, class_id, admission_number?, roll_number?, dob?, gender?,
    blood_group?, height_cm?, weight_kg?, medical_notes?, father_*, mother_*,
    guardian_*, annual_income?}`` — mirrors `StudentCreate`.
    returns: ``{"student": <student_doc>}``
    """
    school_id = actor_ctx.school_id
    name = (params.get("name") or "").strip()
    class_id = params.get("class_id")
    if not name or not class_id:
        raise StudentValidationError("name and class_id are required")

    await _validate_class(db, school_id, class_id)

    admission_number = params.get("admission_number") or (
        f"ADM{actor_ctx.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:4].upper()}"
    )
    existing = await db.students.find_one(
        scoped_filter({"admission_number": admission_number}, school_id), {"_id": 0}
    )
    if existing:
        raise StudentConflictError("Admission number already exists")

    student = Student(
        class_id=class_id,
        name=name,
        admission_number=admission_number,
        roll_number=params.get("roll_number"),
        dob=params.get("dob"),
        gender=params.get("gender"),
        blood_group=params.get("blood_group"),
        height_cm=params.get("height_cm"),
        weight_kg=params.get("weight_kg"),
        medical_notes=params.get("medical_notes"),
    )
    student_doc = _serialize(student)
    await db.students.insert_one({**student_doc, "_id": student.id}, **_session_kwargs(session))

    guardians_to_create = []
    if params.get("father_name") and params.get("father_phone"):
        guardians_to_create.append(Guardian(
            student_id=student.id, name=params["father_name"], relation="Father",
            phone=params["father_phone"], whatsapp_phone=params["father_phone"],
            occupation=params.get("father_occupation"), annual_income=params.get("annual_income"),
            is_primary=True,
        ))
    if params.get("mother_name") and params.get("mother_phone"):
        guardians_to_create.append(Guardian(
            student_id=student.id, name=params["mother_name"], relation="Mother",
            phone=params["mother_phone"], whatsapp_phone=params["mother_phone"],
            occupation=params.get("mother_occupation"),
            is_primary=not params.get("father_name"),
        ))
    if not guardians_to_create and params.get("guardian_name") and params.get("guardian_phone"):
        guardians_to_create.append(Guardian(
            student_id=student.id, name=params["guardian_name"], relation="Parent",
            phone=params["guardian_phone"], whatsapp_phone=params["guardian_phone"],
            is_primary=True,
        ))
    for g in guardians_to_create:
        g_doc = _serialize(g)
        await db.guardians.insert_one({**g_doc, "_id": g.id}, **_session_kwargs(session))

    await _write_student_audit(
        db, actor_ctx, action="create", student_id=student.id,
        changes={"created": student_doc}, session=session,
    )
    return {"student": student_doc}


async def update_student(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Update a student identically to `PATCH /api/students/{id}`.

    params: ``{student_id, <updatable fields>}``
    returns: ``{"student": <updated_doc>, "noop": bool}``
    """
    school_id = actor_ctx.school_id
    student_id = params.get("student_id")
    if not student_id:
        raise StudentValidationError("student_id is required")

    existing = await db.students.find_one(
        scoped_filter({"id": student_id}, school_id), {"_id": 0}
    )
    if not existing:
        raise StudentNotFoundError("Student not found")

    update = {k: v for k, v in params.items() if k in UPDATABLE_FIELDS}
    if not update:
        raise StudentValidationError("No updatable fields provided")

    if _is_transport_head(actor_ctx):
        blocked = set(update) - TRANSPORT_HEAD_FIELDS
        if blocked:
            raise StudentValidationError(
                "Transport Head can only update transport assignment fields"
            )

    if "class_id" in update and update["class_id"] != existing.get("class_id"):
        await _validate_class(db, school_id, update["class_id"])
    if "admission_number" in update and update["admission_number"] != existing.get("admission_number"):
        duplicate = await db.students.find_one(
            scoped_filter({"admission_number": update["admission_number"]}, school_id), {"_id": 0}
        )
        if duplicate and duplicate.get("id") != student_id:
            raise StudentConflictError("Admission number already exists")

    changes = {
        key: {"previous": existing.get(key), "new": value}
        for key, value in update.items()
        if existing.get(key) != value
    }
    if not changes:
        return {"student": existing, "noop": True}

    update["updated_at"] = actor_ctx.now_iso()
    await db.students.update_one(
        scoped_filter({"id": student_id}, school_id), {"$set": update},
        **_session_kwargs(session),
    )
    await _write_student_audit(
        db, actor_ctx, action="update", student_id=student_id,
        changes=changes, session=session,
    )
    updated = await db.students.find_one(
        scoped_filter({"id": student_id}, school_id), {"_id": 0}
    )
    return {"student": updated, "noop": False}


async def set_student_status(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Soft status change (e.g. active → withdrawn). Thin wrapper over
    `update_student` with a single `status` field — NOT the DELETE route.

    params: ``{student_id, status}``
    """
    status = params.get("status")
    if not status:
        raise StudentValidationError("status is required")
    return await update_student(
        db, actor_ctx, {"student_id": params.get("student_id"), "status": status},
        session=session, idempotency_key=idempotency_key,
    )


async def upsert_guardians(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Replace all guardians for a student identically to
    `PUT /api/students/{id}/guardians`.

    params: ``{student_id, guardians: [<guardian objects>]}``
    returns: ``{"guardians": [<saved>]}``
    """
    school_id = actor_ctx.school_id
    student_id = params.get("student_id")
    if not student_id:
        raise StudentValidationError("student_id is required")
    guardians = params.get("guardians")
    if not isinstance(guardians, list):
        raise StudentValidationError("guardians must be a list of guardian objects")

    student = await db.students.find_one(
        scoped_filter({"id": student_id}, school_id), {"_id": 0}
    )
    if not student:
        raise StudentNotFoundError("Student not found")

    existing = await db.guardians.find(
        scoped_filter({"student_id": student_id}, school_id), {"_id": 0}
    ).to_list(10)
    existing_by_relation = {g["relation"].lower(): g for g in existing}

    saved = []
    for item in guardians:
        relation = (item.get("relation") or "Parent").strip()
        name = (item.get("name") or "").strip()
        phone = (item.get("phone") or "").strip()
        if not name or not phone:
            continue
        existing_g = existing_by_relation.get(relation.lower())
        update_doc = {
            "name": name,
            "phone": phone,
            "whatsapp_phone": item.get("whatsapp_phone") or phone,
            "alt_phone": item.get("alt_phone"),
            "email": item.get("email"),
            "occupation": item.get("occupation"),
            "annual_income": item.get("annual_income"),
            "is_primary": item.get("is_primary", False),
            "updated_at": actor_ctx.now_iso(),
        }
        if existing_g:
            await db.guardians.update_one(
                scoped_filter({"id": existing_g["id"]}, school_id), {"$set": update_doc},
                **_session_kwargs(session),
            )
            saved.append({**existing_g, **update_doc})
        else:
            new_g = Guardian(
                student_id=student_id, name=name, relation=relation, phone=phone,
                whatsapp_phone=item.get("whatsapp_phone") or phone,
                alt_phone=item.get("alt_phone"), email=item.get("email"),
                occupation=item.get("occupation"), annual_income=item.get("annual_income"),
                is_primary=item.get("is_primary", False),
            )
            g_doc = _serialize(new_g)
            await db.guardians.insert_one({**g_doc, "_id": new_g.id}, **_session_kwargs(session))
            saved.append(g_doc)

    await _write_student_audit(
        db, actor_ctx, action="guardians_update", student_id=student_id,
        changes={"count": len(saved)}, session=session,
    )
    return {"guardians": saved}
