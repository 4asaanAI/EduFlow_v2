"""Student CRUD service - the single shared write path for student records
(AI Layer Hardening, AD7 / AD15 / Epic J, Story J.1).

Both the REST routes (`POST /api/students/`, `PATCH /api/students/{id}`,
`PUT /api/students/{id}/guardians`) and the new AI tools (`create_student`,
`update_student`, `manage_student_guardians`, `set_student_status`) call into the
functions here, so an AI-created/edited student is byte-identical to the panel result.

Student **hard-delete** (`DELETE /students/{id}`) and **DPDP-erase**
(`/students/{id}/erase`) are deliberately NOT in this service's AI-reachable surface
- they stay UI-only (AD15). Photo upload (binary) stays a REST route; the assistant
sets `photo_url` through `update_student`.

Services raise domain exceptions, never `HTTPException`.
"""

from __future__ import annotations

import uuid
from typing import Optional

from models.schemas import Guardian, Student
from services import enrolment_status
from services.actor_context import ActorContext
from services.admission_charge_service import raise_joining_charges
from services.audit_service import write_audit_doc
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import scoped_filter

# Field whitelists - the SAME sets the REST route enforces (keep in lockstep).
UPDATABLE_FIELDS = {
    "name", "class_id", "admission_number", "roll_number", "dob", "gender",
    "blood_group", "height_cm", "weight_kg", "medical_notes", "emergency_contact",
    # Owner request 11 (2026-08-06): where the child lives. Editable by the same
    # people who may edit the rest of the profile.
    "address",
    "house", "photo_url", "uses_transport", "bus_route", "route_zone_id", "status",
}

# The 71 columns carried over from the school's previous system on 2026-08-06
# (`scripts/import_aaryans_extra_fields_2026_08_06.py`). Readable from the moment they
# were loaded, because the students routes return raw documents; this makes them
# EDITABLE too, so the office can correct an Aadhaar number or a category without a
# developer.
#
# What is deliberately NOT in here, and must stay out:
#   * id / schoolId / branch_id / academic_year_id / created_at - identity and audit
#     metadata. `created_at` especially: it means "when this record was made on
#     EduFlow", and the load had to rename the school's own column to
#     `source_created_at` to avoid destroying it. Making it editable would reopen that.
#   * source_sid / source_username / source_last_active - identifiers belonging to the
#     PREVIOUS system. They are a historical trail; editing them makes them a lie.
#   * fee_snapshot - a dated copy of what the school's export said, not the fee ledger.
#     It must not drift into a second, editable version of what a family owes.
#   * *_s3_key / *_s3_bytes - set by the photo migration, not by a person.
#   * is_active - REMOVED after review. It is derived from `status`; if both were
#     editable they could disagree, and a child who is status=active but
#     is_active=False disappears from every list while looking fine on their profile.
EXTRA_SOURCE_FIELDS = {
    # ── Added 2026-08-11 (Abhimanyu) ──────────────────────────────────────────
    # The rule he gave: carry a column across if it HOLDS data, or if it matters even
    # while empty, because the school intends to fill exactly these gaps through this
    # platform. A column that is blank today is not a column nobody wants. What is NOT
    # carried across is the previous vendor's empty filler, listed by name in
    # `data_import_service.DELIBERATELY_NOT_IMPORTED`.
    #
    # `stream` is the one that is urgently needed: 11th and 12th are charged 4,800 a
    # year apart depending on Commerce or Science, and the only place that fact is
    # recorded today is a class name inside the fee ledger.
    "stream",
    # These carry real data in the school's export and were loaded on 2026-08-06, but
    # were left out of this set, so nobody could correct one without a developer.
    # `source_created_at` is deliberately NOT here, for the reason given above: it
    # belongs to the previous system and editing it makes it a lie.
    "alternate_number", "apaar_id", "caste", "email", "medium", "pen_no",
    "place_of_birth", "religion", "rte_application_no",
    "father_occupation", "father_qualification", "mother_occupation",
    "mother_qualification", "father_residential_address",
    "mother_residential_address", "father_email", "father_official_address",
    "mother_email", "mother_official_address", "enrolled_year",
    "domicile_application_no", "income_application_no", "caste_application_no",
    "aadhaar_no", "account_holder", "admission_date", "admission_type",
    "attended_class", "attended_school", "bank_account_no", "bank_branch",
    "bank_ifsc", "bank_name", "category", "city",
    "country", "dob_application_no", "dropout", "enrolled_class",
    "enrolled_session", "father_aadhaar_no", "father_mobile", "father_name",
    "father_photo", "has_disability", "is_bpl_student",
    "is_rte_student", "last_session", "mother_aadhaar_no", "mother_mobile",
    "mother_name", "mother_photo", "nationality", "phone",
    "pincode", "registration_no", "remark", "route_id",
    "school_affiliated", "sr_no", "state", "tc_date",
    "tc_no", "transport_opted", "whatsapp",
}

UPDATABLE_FIELDS = UPDATABLE_FIELDS | EXTRA_SOURCE_FIELDS
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


class StudentAuthorizationError(Exception):
    """This profile may not do that → HTTP 403."""


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
    guardian_*, annual_income?}`` - mirrors `StudentCreate`.
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
        address=params.get("address"),
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

    # Abhimanyu, 2026-08-12: the school's registration and admission fees are raised
    # automatically when a child joins. The caller passes `raise_joining_charges=False`
    # when it is LOADING existing children rather than admitting new ones - a bulk import
    # of the roll must never bill 1,842 families for joining years ago. See
    # `services/admission_charge_service.py`, which is deliberately its own file so that
    # rule is written down in one place rather than implied by a call site.
    joining = {"raised": [], "skipped_because": "not requested"}
    if params.get("raise_joining_charges", True):
        joining = await raise_joining_charges(db, actor_ctx, student_doc, session=session)

    return {"student": student_doc, "joining_charges": joining}


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
    `update_student` with a single `status` field - NOT the DELETE route.

    params: ``{student_id, status}``

    ⚠️  This writes the LABEL only. For anything that should change whether the student
    is on the roll or on the daily register, call `set_enrolment_state` below instead -
    writing `status` on its own leaves `is_active` behind and the two disagree.
    """
    status = params.get("status")
    if not status:
        raise StudentValidationError("status is required")
    return await update_student(
        db, actor_ctx, {"student_id": params.get("student_id"), "status": status},
        session=session, idempotency_key=idempotency_key,
    )


async def set_enrolment_state(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Move a student between active, NSO and TC issued - and back.

    params: ``{student_id, state, reason?}``
    returns: ``{"student": <updated_doc>, "noop": bool, "previous_state": str}``

    THE ONE WRITER of `is_active` on a student, and it always writes `status` in the
    same breath. See services/enrolment_status.py for what the three states mean and
    why NSO could not be expressed with `is_active` alone.

    This is also the route back. Until it existed nothing in the product could set
    `is_active` to True: it was absent from UPDATABLE_FIELDS, so a student marked
    inactive - as one was during the demo on 2026-08-05 - was unreachable by every
    endpoint and every AI tool, and the only visible symptom was a headcount one short
    (owner request 9, 2026-08-06). Do not remove this without providing another way
    back, or the same trap reopens.

    `reason` is optional here on purpose. It is compulsory only for permanent erasure,
    which destroys the record and lives in its own owner-only route. Moving a student
    between these three is reversible, and demanding a paragraph for a reversible act
    is how people learn to type "x" into the box.
    """
    student_id = params.get("student_id")
    if not student_id:
        raise StudentValidationError("student_id is required")

    state = str(params.get("state") or "").strip().lower()
    if state not in enrolment_status.SETTABLE_STATES:
        raise StudentValidationError(
            "state must be one of: " + ", ".join(enrolment_status.SETTABLE_STATES)
        )

    school_id = actor_ctx.school_id
    existing = await db.students.find_one(
        scoped_filter({"id": student_id}, school_id), {"_id": 0}
    )
    if not existing:
        raise StudentNotFoundError("Student not found")

    previous_state = enrolment_status.normalise(existing)
    update = enrolment_status.fields_for(state)
    changes = {
        key: {"previous": existing.get(key), "new": value}
        for key, value in update.items()
        if existing.get(key) != value
    }
    if not changes:
        return {"student": existing, "noop": True, "previous_state": previous_state}

    update["updated_at"] = actor_ctx.now_iso()
    # A leaving date belongs to the TC, not to NSO - an NSO student has not left, they
    # have stopped turning up. Clearing it on the way back matters: without that, a
    # restored student carries a withdrawal date that reports would still believe.
    if state == enrolment_status.TC_ISSUED:
        update["withdrawal_date"] = actor_ctx.now_iso()[:10]
    elif state == enrolment_status.ACTIVE:
        update["withdrawal_date"] = None

    await db.students.update_one(
        scoped_filter({"id": student_id}, school_id), {"$set": update},
        **_session_kwargs(session),
    )
    await _write_student_audit(
        db, actor_ctx,
        # A distinct action so the log answers "who put this child back on the roll,
        # and when" without anyone reading a diff to work it out.
        action=f"enrolment_{state}",
        student_id=student_id,
        changes={**changes, "previous_state": {"previous": previous_state, "new": state}},
        reason=(params.get("reason") or "").strip() or None,
        session=session,
    )
    updated = await db.students.find_one(
        scoped_filter({"id": student_id}, school_id), {"_id": 0}
    )
    return {"student": updated, "noop": False, "previous_state": previous_state}


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


async def delete_student(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Take a student off the roll - the shared path behind `DELETE /api/students/{id}`
    and the AI `delete_student` tool.

    Owner instruction 2026-08-07 - Flo could add a student but had no way to remove one.

    **This does not destroy anything.** It records that the child has left, exactly as
    the delete button on the screen always did, and `set_enrolment_state` puts them back.
    Permanent erasure is a different act with a different door: it demands a written
    reason, anonymises attendance history and purges notes, and stays on the screen,
    owner or principal only, where a person is looking at the record they are erasing.
    Chat is not the place to destroy a child's record beyond recovery.

    params: ``{student_id, reason?}``
    returns: ``{"student": <doc>, "noop": bool, "previous_state": str}``
    """
    if not params.get("student_id"):
        raise StudentValidationError("student_id is required")
    # R2-4 / decision 4, 2026-08-10: the management head adds and edits students; he
    # does not take them off the roll. The guard lives HERE rather than on the route
    # because the route and the Flo `delete_student` tool both come through this
    # function - a check on the route alone would leave the chat door open, which is
    # exactly the drift the shared-service pattern exists to prevent.
    from services.profile_matrix import may_delete_people, user_from_actor

    if not may_delete_people(user_from_actor(actor_ctx)):
        raise StudentAuthorizationError(
            "Only the school's owner or the principal can take a student off the roll"
        )
    return await set_enrolment_state(
        db,
        actor_ctx,
        {
            "student_id": params["student_id"],
            "state": enrolment_status.TC_ISSUED,
            "reason": params.get("reason"),
        },
        session=session,
        idempotency_key=idempotency_key,
    )
