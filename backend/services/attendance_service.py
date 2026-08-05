"""Attendance domain service — the single shared write path for bulk student
attendance (AI Layer Hardening, AD7 / Epic A reference implementation).

Both `POST /api/attendance/student/bulk` (REST) and the AI `mark_attendance`
tool call `mark_attendance(...)`, so an AI-marked class is byte-identical to a
panel-marked class (records + the one bulk audit row).

Services raise domain exceptions, never `HTTPException`, and never read
`Request`/`Depends`. Auth (role + teacher class-access) stays in the adapters.
"""

from __future__ import annotations

from services.txn_context import session_kwargs as _txn_session_kwargs

import logging
import uuid
from datetime import datetime
from typing import Optional

from models.schemas import StudentAttendance
from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_filter, scoped_query

logger = logging.getLogger(__name__)
VALID_STATUSES = {"present", "absent", "late", "holiday"}


class AttendanceValidationError(Exception):
    """The requested attendance batch violates a domain invariant."""


async def validate_attendance_batch(db, actor_ctx: ActorContext, params: dict) -> None:
    class_id = params.get("class_id")
    target_date = params.get("date")
    records = params.get("records") or []
    if not class_id:
        raise AttendanceValidationError("class_id is required")
    try:
        datetime.strptime(str(target_date), "%Y-%m-%d")
    except (TypeError, ValueError):
        raise AttendanceValidationError("date must be in YYYY-MM-DD format")

    class_doc = await db.classes.find_one(
        scoped_query({"id": class_id}, branch_id=actor_ctx.branch_id),
        {"_id": 0, "id": 1},
    )
    if not class_doc:
        raise AttendanceValidationError("class not found")

    student_ids = []
    for record in records:
        student_id = record.get("student_id")
        status = record.get("status")
        if not student_id:
            raise AttendanceValidationError("every attendance record needs a student_id")
        if status not in VALID_STATUSES:
            raise AttendanceValidationError(
                f"invalid attendance status '{status}' — must be one of {sorted(VALID_STATUSES)}"
            )
        student_ids.append(student_id)

    if len(student_ids) != len(set(student_ids)):
        raise AttendanceValidationError("a student may appear only once in an attendance batch")
    if not student_ids:
        return

    members = await db.students.find(
        scoped_query(
            {"id": {"$in": student_ids}, "class_id": class_id, "is_active": {"$ne": False}},
            branch_id=actor_ctx.branch_id,
        ),
        {"_id": 0, "id": 1},
    ).to_list(len(student_ids))
    member_ids = {student["id"] for student in members}
    invalid_ids = sorted(set(student_ids) - member_ids)
    if invalid_ids:
        raise AttendanceValidationError(
            "students do not belong to the selected class: " + ", ".join(invalid_ids)
        )


def _session_kwargs(session) -> dict:
    # AI Layer Hardening D.2: resolve the AMBIENT transaction session when the
    # caller passes none, so a service invoked inside the plan executor's txn
    # auto-enlists. Outside a txn this is {} (identical to pre-D.2 behavior).
    return _txn_session_kwargs(session)


async def mark_attendance(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Bulk-mark student attendance.

    params: ``{"class_id": str, "date": str, "records": [{"student_id", "status"}]}``
    returns: ``{"results": [{"student_id", "status"[, "error"]}], "idempotent": bool}``
    """
    class_id = params["class_id"]
    target_date = params["date"]
    records = params.get("records") or []
    school_id = actor_ctx.school_id

    # Idempotency replay (REST Idempotency-Key header): return the cached response,
    # do not re-write or re-audit. The AI path passes no key (idempotency lands in Epic D).
    if idempotency_key:
        existing = await db.attendance_bulk_keys.find_one(
            # branch-scope: intentional — attendance_bulk_keys has no branch_id; the
            # client-supplied Idempotency-Key is unique within the school.
            scoped_filter({"key": idempotency_key, "class_id": class_id, "date": target_date}, school_id),
            {"_id": 0},
        )
        if existing:
            return {"results": existing.get("response", []), "idempotent": True}

    await validate_attendance_batch(db, actor_ctx, params)

    results = []
    for record in records:
        att = StudentAttendance(
            student_id=record["student_id"],
            class_id=class_id,
            date=target_date,
            status=record["status"],
            marked_by=actor_ctx.user_id,
        )
        doc = {**att.model_dump(), "_id": att.id, "schoolId": school_id, "source": "bulk"}
        try:
            await db.student_attendance.update_one(
                # branch-scope: intentional — student_attendance carries no branch_id;
                # its unique index is (student_id, date) school-wide.
                scoped_filter({"student_id": record["student_id"], "date": target_date}, school_id),
                {"$set": doc},
                upsert=True,
                **_session_kwargs(session),
            )
            results.append({"student_id": record["student_id"], "status": "saved"})
        except Exception as e:
            logger.warning(
                "attendance bulk record write failed",
                extra={"student_id": record.get("student_id"), "class_id": class_id, "date": target_date},
                exc_info=True,
            )
            # AI Layer Hardening D-review: under the plan executor's transaction
            # (ambient/explicit session) a per-record failure MUST abort the whole
            # batch — all-or-nothing (AD4). The REST path (no session) preserves the
            # original per-record error-reporting so its characterization test holds.
            if _session_kwargs(session):
                raise
            results.append({"student_id": record["student_id"], "status": "error", "error": str(e)})

    if idempotency_key:
        # D-review: thread the session so the idempotency claim is part of the txn
        # (else a later abort leaves a key that falsely rejects a legitimate retry).
        await db.attendance_bulk_keys.insert_one({
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": school_id,
            "key": idempotency_key,
            "class_id": class_id,
            "date": target_date,
            "response": results,
            "created_at": actor_ctx.now_iso(),
        }, **_session_kwargs(session))

    # EC-14.1: ONE audit entry per bulk call (not N per student).
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": school_id,
            "entity_type": "student_attendance",
            "entity_id": class_id,
            "action": "attendance_bulk",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"count_marked": len(results), "date": target_date, "class_id": class_id},
            "created_at": actor_ctx.now_iso(),
        },
        school_id=school_id,
        branch_id=actor_ctx.branch_id or "",
    )

    return {"results": results, "idempotent": False}
