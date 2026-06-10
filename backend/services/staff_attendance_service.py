"""Staff-attendance domain service — single shared write path for bulk staff
attendance marking (AI Layer Hardening, AD7).

Both `POST /api/attendance/staff/bulk` (REST) and the AI `mark_staff_attendance`
tool call `mark_staff_attendance(...)`, so an AI staff-attendance write is
byte-identical to the panel write: same upsert-per-staff semantics, same SSE
payload, plus ONE audit row per bulk call (EC-14.1 — matching the student bulk
path; the legacy REST handler wrote none, parity decision = add it to both).

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import uuid
from typing import Awaitable, Callable, Optional

from models.schemas import StaffAttendance
from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import scoped_filter

VALID_STATUSES = {"present", "absent", "late", "half_day", "leave"}


class StaffAttendanceValidationError(Exception):
    """Invalid input (missing records, bad status) → HTTP 400."""


def _serialize(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _session_kwargs(session) -> dict:
    return _txn_session_kwargs(session)


async def mark_staff_attendance(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    publish_fn: Optional[Callable[..., Awaitable]] = None,
) -> dict:
    """Bulk-mark staff attendance.

    params: ``{"date": str, "records": [{"staff_id", "status", "check_in"?, "check_out"?}]}``
    returns: ``{"date": str, "records": [...], "marked": int}``
    """
    target_date = params.get("date") or actor_ctx.now().strftime("%Y-%m-%d")
    records = params.get("records") or []
    if not records:
        raise StaffAttendanceValidationError("records is required and must be non-empty")
    for rec in records:
        if not rec.get("staff_id"):
            raise StaffAttendanceValidationError("every record needs a staff_id")
        if rec.get("status") not in VALID_STATUSES:
            raise StaffAttendanceValidationError(
                f"invalid status '{rec.get('status')}' — must be one of {sorted(VALID_STATUSES)}"
            )

    school_id = actor_ctx.school_id
    for rec in records:
        att = StaffAttendance(
            staff_id=rec["staff_id"],
            date=target_date,
            status=rec["status"],
            check_in=rec.get("check_in"),
            check_out=rec.get("check_out"),
        )
        await db.staff_attendance.update_one(
            # branch-scope: intentional — staff_attendance is keyed (staff_id, date)
            # school-wide, matching the legacy REST upsert.
            scoped_filter({"staff_id": rec["staff_id"], "date": target_date}, school_id),
            {"$set": {**_serialize(att), "_id": att.id, "schoolId": school_id}},
            upsert=True,
            **_session_kwargs(session),
        )

    # EC-14.1: ONE audit entry per bulk call (not N per staff member).
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": school_id,
            "entity_type": "staff_attendance",
            "entity_id": target_date,
            "action": "bulk_mark",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"date": target_date, "count": len(records), "records": records},
            "reason": None,
            "created_at": actor_ctx.now_iso(),
        },
        school_id=school_id,
        branch_id=actor_ctx.branch_id,
    )

    if publish_fn is not None:
        await publish_fn(
            "attendance",
            {
                "type": "staff_attendance_updated",
                "date": target_date,
                "records": records,
                "updated_at": actor_ctx.now_iso(),
            },
        )
    return {"date": target_date, "records": records, "marked": len(records)}
