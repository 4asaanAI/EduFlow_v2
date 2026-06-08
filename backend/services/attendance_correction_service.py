"""Attendance-correction service — the single shared write path for correcting a
student attendance record (AI Layer Hardening, AD7 / Epic A, Story A.7).

Both `PATCH /api/attendance/{id}/correct` (REST) and the AI `correct_attendance`
tool call `correct_attendance(...)`. The two collection writes — inserting the
`attendance_corrections` snapshot and updating `student_attendance` — are
encapsulated in this single service call (true transactional atomicity arrives when
the executor wraps services in a Motor transaction, Epic D; `session=` is already
threaded for that).

**Parity decision (case-by-case, canonical = REST):**
- Audit action canonicalized to `correct` (the AI tool wrote `correct_attendance`).
- Scoping is school-wide via `scoped_filter` (attendance carries no branch_id; the unique
  index is (student_id, date) school-wide). This also fixes a latent AI bug: the tool's
  `scoped_query(branch_id=...)` could never match a branch-less attendance doc for a
  branch-scoped principal, so corrections silently failed for them.
- The mandatory `correction_type` + `reason`, the full `original_record` snapshot, and
  `previous_status`/`new_status` are written identically.

Services raise domain exceptions, never `HTTPException`.
"""

from __future__ import annotations

from services.txn_context import session_kwargs as _txn_session_kwargs

import uuid
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_filter


class AttendanceCorrectionValidationError(Exception):
    """Missing correction_type/reason → HTTP 400."""


class AttendanceCorrectionNotFoundError(Exception):
    """Attendance record not found (in tenant scope) → HTTP 404."""


def _session_kwargs(session) -> dict:
    # AI Layer Hardening D.2: resolve the AMBIENT transaction session when the
    # caller passes none, so a service invoked inside the plan executor's txn
    # auto-enlists. Outside a txn this is {} (identical to pre-D.2 behavior).
    return _txn_session_kwargs(session)


async def correct_attendance(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Correct a student attendance record (snapshot + status update + audit).

    params: ``{attendance_id, correction_type, reason, status?}``
    returns: ``{"correction": <correction doc without _id>}``
    """
    attendance_id = params.get("attendance_id")
    correction_type = params.get("correction_type")
    reason = params.get("reason")
    if not correction_type or not reason:
        raise AttendanceCorrectionValidationError("correction_type and reason are required")
    if not attendance_id:
        raise AttendanceCorrectionValidationError("attendance_id is required")

    # branch-scope: intentional — student_attendance carries no branch_id (school-wide).
    original = await db.student_attendance.find_one(
        scoped_filter({"id": attendance_id}, actor_ctx.school_id), {"_id": 0}
    )
    if not original:
        raise AttendanceCorrectionNotFoundError("Attendance record not found")

    new_status = params.get("status") or correction_type
    corrected_at = actor_ctx.now_iso()
    correction = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "attendance_id": attendance_id,
        "original_record": original,
        "previous_status": original.get("status"),
        "new_status": new_status,
        "correction_type": correction_type,
        "reason": reason,
        "corrected_by": actor_ctx.user_id,
        "corrected_at": corrected_at,
    }
    await db.attendance_corrections.insert_one(correction, **_session_kwargs(session))
    await db.student_attendance.update_one(
        # branch-scope: intentional — see above (school-wide attendance).
        scoped_filter({"id": attendance_id}, actor_ctx.school_id),
        {"$set": {"status": new_status, "corrected": True, "updated_at": corrected_at}},
        **_session_kwargs(session),
    )

    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "student_attendance",
            "entity_id": attendance_id,
            "action": "correct",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"status": {"previous": original.get("status"), "new": new_status}},
            "reason": reason,
            "created_at": corrected_at,
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )

    return {"correction": {k: v for k, v in correction.items() if k != "_id"}}
