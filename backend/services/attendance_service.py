"""Attendance domain service — the single shared write path for bulk student
attendance (AI Layer Hardening, AD7 / Epic A reference implementation).

Both `POST /api/attendance/student/bulk` (REST) and the AI `mark_attendance`
tool call `mark_attendance(...)`, so an AI-marked class is byte-identical to a
panel-marked class (records + the one bulk audit row).

Services raise domain exceptions, never `HTTPException`, and never read
`Request`/`Depends`. Auth (role + teacher class-access) stays in the adapters.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from models.schemas import StudentAttendance
from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_filter

logger = logging.getLogger(__name__)


def _session_kwargs(session) -> dict:
    # Pass session= to Mongo ops only when set (always None until Epic D).
    # FakeCollection in tests has no session= param, so omit it when None.
    return {"session": session} if session is not None else {}


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
        except Exception as e:  # preserved-from-REST: per-record error is reported, not swallowed
            logger.warning(
                "attendance bulk record write failed",
                extra={"student_id": record.get("student_id"), "class_id": class_id, "date": target_date},
                exc_info=True,
            )
            results.append({"student_id": record["student_id"], "status": "error", "error": str(e)})

    if idempotency_key:
        await db.attendance_bulk_keys.insert_one({
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": school_id,
            "key": idempotency_key,
            "class_id": class_id,
            "date": target_date,
            "response": results,
            "created_at": actor_ctx.now_iso(),
        })

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
