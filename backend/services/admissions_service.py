"""Applicant-to-student admissions lifecycle.

The workflow is additive: existing enquiry rows remain untouched until an operator
explicitly starts an application. Enrollment creates the student and guardians in one
database transaction and permanently links the application/enquiry to that record.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.student_service import create_student
from services.txn_context import session_kwargs
from tenant import scoped_query


class AdmissionValidationError(Exception):
    pass


class AdmissionNotFoundError(Exception):
    pass


class AdmissionConflictError(Exception):
    pass


TERMINAL = {"enrolled", "rejected", "withdrawn"}
TRANSITIONS = {
    "draft": {"submitted", "withdrawn"},
    "submitted": {"under_review", "rejected", "withdrawn"},
    "under_review": {"assessment_scheduled", "offered", "rejected", "withdrawn"},
    "assessment_scheduled": {"assessed", "rejected", "withdrawn"},
    "assessed": {"offered", "rejected", "withdrawn"},
    "offered": {"accepted", "rejected", "withdrawn"},
    "accepted": {"enrolled", "withdrawn"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public(doc: dict) -> dict:
    return {key: value for key, value in doc.items() if key != "_id"}


def _required_text(params: dict, key: str) -> str:
    value = str(params.get(key) or "").strip()
    if not value:
        raise AdmissionValidationError(f"{key} is required")
    return value


async def _audit(db, actor_ctx: ActorContext, action: str, application_id: str,
                 changes: dict, *, session=None) -> None:
    audit_id = str(uuid.uuid4())
    await write_audit_doc(db, {
        "_id": audit_id,
        "id": audit_id,
        "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id,
        "entity_type": "admission_application",
        "entity_id": application_id,
        "action": action,
        "changed_by": actor_ctx.user_id,
        "changed_by_role": actor_ctx.role,
        "changes": changes,
        "created_at": actor_ctx.now().isoformat(),
    }, school_id=actor_ctx.school_id, branch_id=actor_ctx.branch_id)


async def create_application(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    enquiry_id = params.get("enquiry_id")
    enquiry = None
    if enquiry_id:
        enquiry = await db.enquiries.find_one(
            scoped_query({"id": enquiry_id}, branch_id=actor_ctx.branch_id),
            {"_id": 0}, **session_kwargs(session),
        )
        if not enquiry:
            raise AdmissionNotFoundError("Enquiry not found")
        existing = await db.admission_applications.find_one(
            scoped_query({"enquiry_id": enquiry_id}, branch_id=actor_ctx.branch_id),
            {"_id": 0}, **session_kwargs(session),
        )
        if existing:
            return {"application": existing, "existing": True}

    applicant_name = str(params.get("applicant_name") or (enquiry or {}).get("student_name") or "").strip()
    if not applicant_name:
        raise AdmissionValidationError("applicant_name is required")
    class_id = str(params.get("class_id") or (enquiry or {}).get("class_id") or "").strip()
    class_applying = str(params.get("class_applying") or (enquiry or {}).get("class_applying") or "").strip()
    if not class_id and not class_applying:
        raise AdmissionValidationError("class_id or class_applying is required")

    application_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": application_id,
        "id": application_id,
        "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id,
        "enquiry_id": enquiry_id,
        "applicant_name": applicant_name,
        "dob": params.get("dob"),
        "gender": params.get("gender"),
        "class_id": class_id or None,
        "class_applying": class_applying or None,
        "academic_year": params.get("academic_year"),
        "guardian_name": params.get("guardian_name") or (enquiry or {}).get("parent_name"),
        "guardian_phone": params.get("guardian_phone") or (enquiry or {}).get("phone"),
        "guardian_email": params.get("guardian_email"),
        "address": params.get("address"),
        "previous_school": params.get("previous_school"),
        "documents": [],
        "assessment": None,
        "offer": None,
        "status": "draft",
        "student_id": None,
        "created_by": actor_ctx.user_id,
        "created_at": now,
        "updated_at": now,
    }
    await db.admission_applications.insert_one(doc, **session_kwargs(session))
    if enquiry_id:
        await db.enquiries.update_one(
            scoped_query({"id": enquiry_id}, branch_id=actor_ctx.branch_id),
            {"$set": {"application_id": application_id, "updated_at": now}},
            **session_kwargs(session),
        )
    await _audit(db, actor_ctx, "application_created", application_id, {"created": _public(doc)}, session=session)
    return {"application": _public(doc), "existing": False}


async def transition_application(db, actor_ctx: ActorContext, application_id: str,
                                 params: dict, *, session=None) -> dict:
    target = str(params.get("status") or "").strip()
    application = await db.admission_applications.find_one(
        scoped_query({"id": application_id}, branch_id=actor_ctx.branch_id),
        {"_id": 0}, **session_kwargs(session),
    )
    if not application:
        raise AdmissionNotFoundError("Application not found")
    current = application.get("status", "draft")
    if target == current:
        return {"application": application, "noop": True}
    if target not in TRANSITIONS.get(current, set()):
        raise AdmissionConflictError(f"Invalid admission transition from {current} to {target}")
    if target == "submitted":
        missing = [field for field in ("guardian_name", "guardian_phone") if not application.get(field)]
        if missing:
            raise AdmissionValidationError(f"Missing required application fields: {', '.join(missing)}")
    if target == "assessed" and not application.get("assessment"):
        raise AdmissionValidationError("Assessment result is required")
    if target == "accepted" and not application.get("offer"):
        raise AdmissionValidationError("Admission offer is required")
    if target == "enrolled":
        raise AdmissionValidationError("Use the enrollment endpoint to create the student")

    now = _now()
    history = {"from": current, "to": target, "at": now, "by": actor_ctx.user_id, "note": params.get("note")}
    await db.admission_applications.update_one(
        scoped_query({"id": application_id, "status": current}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": target, "updated_at": now}, "$push": {"status_history": history}},
        **session_kwargs(session),
    )
    updated = await db.admission_applications.find_one(
        scoped_query({"id": application_id}, branch_id=actor_ctx.branch_id), {"_id": 0},
        **session_kwargs(session),
    )
    await _audit(db, actor_ctx, "application_status_changed", application_id, history, session=session)
    return {"application": updated, "noop": False}


async def add_application_document(db, actor_ctx: ActorContext, application_id: str,
                                   params: dict) -> dict:
    document_type = _required_text(params, "document_type")
    file_id = _required_text(params, "file_id")
    application = await db.admission_applications.find_one(
        scoped_query({"id": application_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not application:
        raise AdmissionNotFoundError("Application not found")
    if application.get("status") in TERMINAL:
        raise AdmissionConflictError("A terminal application cannot be changed")
    document = {
        "id": str(uuid.uuid4()), "document_type": document_type, "file_id": file_id,
        "filename": params.get("filename"), "verified": False,
        "uploaded_at": _now(), "uploaded_by": actor_ctx.user_id,
    }
    await db.admission_applications.update_one(
        scoped_query({"id": application_id}, branch_id=actor_ctx.branch_id),
        {"$push": {"documents": document}, "$set": {"updated_at": _now()}},
    )
    await _audit(db, actor_ctx, "application_document_added", application_id, {"document": document})
    return {"document": document}


async def record_assessment(db, actor_ctx: ActorContext, application_id: str,
                            params: dict) -> dict:
    score = params.get("score")
    maximum = params.get("maximum")
    try:
        score, maximum = float(score), float(maximum)
    except (TypeError, ValueError):
        raise AdmissionValidationError("score and maximum must be numbers")
    if maximum <= 0 or score < 0 or score > maximum:
        raise AdmissionValidationError("Assessment score must be between zero and maximum")
    assessment = {
        "score": score, "maximum": maximum,
        "percentage": round(score / maximum * 100, 2),
        "assessed_on": params.get("assessed_on") or date.today().isoformat(),
        "notes": params.get("notes"), "recorded_by": actor_ctx.user_id, "recorded_at": _now(),
    }
    result = await db.admission_applications.update_one(
        scoped_query({"id": application_id, "status": {"$in": ["under_review", "assessment_scheduled", "assessed"]}}, branch_id=actor_ctx.branch_id),
        {"$set": {"assessment": assessment, "updated_at": _now()}},
    )
    if result.matched_count == 0:
        raise AdmissionConflictError("Application is not ready for assessment")
    await _audit(db, actor_ctx, "assessment_recorded", application_id, {"assessment": assessment})
    return {"assessment": assessment}


async def issue_offer(db, actor_ctx: ActorContext, application_id: str, params: dict) -> dict:
    class_id = _required_text(params, "class_id")
    valid_until = _required_text(params, "valid_until")
    try:
        if date.fromisoformat(valid_until) < date.today():
            raise AdmissionValidationError("Offer validity cannot be in the past")
    except ValueError:
        raise AdmissionValidationError("valid_until must be YYYY-MM-DD")
    class_doc = await db.classes.find_one(
        scoped_query({"id": class_id}, branch_id=actor_ctx.branch_id), {"_id": 0, "id": 1}
    )
    if not class_doc:
        raise AdmissionValidationError("Class not found")
    offer = {
        "class_id": class_id, "valid_until": valid_until,
        "admission_fee": float(params.get("admission_fee") or 0),
        "terms": params.get("terms"), "issued_by": actor_ctx.user_id, "issued_at": _now(),
    }
    result = await db.admission_applications.update_one(
        scoped_query({"id": application_id, "status": {"$in": ["under_review", "assessed", "offered"]}}, branch_id=actor_ctx.branch_id),
        {"$set": {"offer": offer, "class_id": class_id, "status": "offered", "updated_at": _now()},
         "$push": {"status_history": {"to": "offered", "at": _now(), "by": actor_ctx.user_id}}},
    )
    if result.matched_count == 0:
        raise AdmissionConflictError("Application is not ready for an offer")
    await _audit(db, actor_ctx, "offer_issued", application_id, {"offer": offer})
    return {"offer": offer}


async def enroll_application(db, actor_ctx: ActorContext, application_id: str,
                             params: dict, *, session=None) -> dict:
    application = await db.admission_applications.find_one(
        scoped_query({"id": application_id}, branch_id=actor_ctx.branch_id),
        {"_id": 0}, **session_kwargs(session),
    )
    if not application:
        raise AdmissionNotFoundError("Application not found")
    if application.get("student_id"):
        student = await db.students.find_one({"id": application["student_id"]}, {"_id": 0}, **session_kwargs(session))
        return {"student": student, "application": application, "existing": True}
    if application.get("status") != "accepted":
        raise AdmissionConflictError("Only an accepted application can be enrolled")
    offer = application.get("offer") or {}
    class_id = params.get("class_id") or offer.get("class_id") or application.get("class_id")
    student_result = await create_student(db, actor_ctx, {
        "name": application["applicant_name"], "class_id": class_id,
        "admission_number": params.get("admission_number"),
        "roll_number": params.get("roll_number"), "dob": application.get("dob"),
        "gender": application.get("gender"),
        "guardian_name": application.get("guardian_name"),
        "guardian_phone": application.get("guardian_phone"),
    }, session=session)
    student = student_result["student"]
    now = _now()
    await db.students.update_one(
        {"id": student["id"]},
        {"$set": {"branch_id": actor_ctx.branch_id, "admission_application_id": application_id}},
        **session_kwargs(session),
    )
    update = {
        "status": "enrolled", "student_id": student["id"], "enrolled_at": now,
        "enrolled_by": actor_ctx.user_id, "updated_at": now,
    }
    await db.admission_applications.update_one(
        scoped_query({"id": application_id, "status": "accepted"}, branch_id=actor_ctx.branch_id),
        {"$set": update, "$push": {"status_history": {"from": "accepted", "to": "enrolled", "at": now, "by": actor_ctx.user_id}}},
        **session_kwargs(session),
    )
    if application.get("enquiry_id"):
        await db.enquiries.update_one(
            scoped_query({"id": application["enquiry_id"]}, branch_id=actor_ctx.branch_id),
            {"$set": {"status": "enrolled", "student_id": student["id"], "updated_at": now}},
            **session_kwargs(session),
        )
    await _audit(db, actor_ctx, "application_enrolled", application_id, {"student_id": student["id"]}, session=session)
    enrolled = {**application, **update}
    return {"student": {**student, "branch_id": actor_ctx.branch_id}, "application": enrolled, "existing": False}
