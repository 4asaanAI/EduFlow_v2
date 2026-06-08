"""Substitution service — the single shared write path for assigning a teacher
substitution (AI Layer Hardening, AD7 / Epic A, Story A.6).

Both `POST /api/academics/substitutions` (REST) and the AI `initiate_substitution`
tool call `initiate_substitution(...)`. Each adapter validates and resolves its own
input shape (REST takes `period_number` directly; the AI resolves it from a timetable
slot via `period_id`) and passes the canonical resolved fields; the service writes an
identical substitution record.

**Parity decision (case-by-case):**
- `status="assigned"` is written for both (the AI tool previously omitted it — a defect).
- Upsert-dedup on `(date, absent_teacher_id, class_id, period_number)` for both (the AI tool
  previously plain-inserted, allowing duplicate substitutions).
- Audit action canonicalized to `assign` (the AI tool wrote `initiate_substitution`).
- The substitute teacher is notified for both (the REST route previously sent no
  notification — additive so "notification fan-out matches"; the AI already notified).
- The AI tool's extra `period_id` field is dropped (REST never stored it).

Services raise domain exceptions, never `HTTPException`.
"""

from __future__ import annotations

import uuid
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.notification_service import create_notification
from tenant import scoped_query


def _session_kwargs(session) -> dict:
    return {"session": session} if session is not None else {}


async def initiate_substitution(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Assign a substitute teacher.

    params (resolved): ``{date, absent_teacher_id, substitute_teacher_id, class_id,
    subject_id, period_number}``
    returns: ``{"substitution": <doc>}``
    """
    substitution = {
        "id": str(uuid.uuid4()),
        "date": params["date"],
        "absent_teacher_id": params["absent_teacher_id"],
        "substitute_teacher_id": params["substitute_teacher_id"],
        "class_id": params["class_id"],
        "subject_id": params.get("subject_id") or "",
        "period_number": params.get("period_number"),
        "status": "assigned",
        "created_by": actor_ctx.user_id,
        "created_at": actor_ctx.now_iso(),
    }
    # Upsert-dedup. The filter is school-scoped automatically by ScopedCollection on
    # upsert in production (matches the REST route, which used the same raw filter).
    await db.substitutions.update_one(
        {
            "date": substitution["date"],
            "absent_teacher_id": substitution["absent_teacher_id"],
            "class_id": substitution["class_id"],
            "period_number": substitution["period_number"],
        },
        {"$set": {**substitution, "_id": substitution["id"]}},
        upsert=True,
        **_session_kwargs(session),
    )

    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "substitution",
            "entity_id": substitution["id"],
            "collection": "substitutions",
            "action": "assign",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"created": substitution},
            "created_at": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )

    substitute = await db.staff.find_one(
        scoped_query({"id": substitution["substitute_teacher_id"]}, branch_id=actor_ctx.branch_id),
        {"_id": 0},
    )
    await create_notification(
        db,
        user_id=(substitute or {}).get("user_id"),
        notification_type="substitution_assigned",
        title="Substitution assigned",
        message="You have been assigned as a substitute teacher.",
        source_id=substitution["id"],
        source_type="substitution",
    )
    return {"substitution": substitution}
