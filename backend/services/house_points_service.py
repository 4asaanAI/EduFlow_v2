"""House-points domain service — the single shared write path for awarding (or
deducting) house points (AI Layer Hardening, AD7 / Epic B, Story B.3).

Both `POST /api/activities/houses/{id}/points` (REST) and the AI `award_house_points`
tool call `award_points(...)`, so an AI award updates the real standings identically
to the panel: it bumps `houses.points`, appends a `house_points_log` row, and writes
an audit row.

**Parity decision (case-by-case, canonical = REST):** the old AI `tool_award_house_points`
inserted into a different, un-audited `house_points` collection and never updated
`houses.points` — so AI-awarded points did not show in standings (found defect B.3).
The AI path now resolves the student's `house_id` and calls this service.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

from services.txn_context import session_kwargs as _txn_session_kwargs

import uuid
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit
from tenant import scoped_filter


class HousePointsValidationError(Exception):
    """Invalid input → HTTP 400."""


class HouseNotFoundError(Exception):
    """House does not exist (in scope) → HTTP 404."""


def _session_kwargs(session) -> dict:
    # AI Layer Hardening D.2: resolve the AMBIENT transaction session when the
    # caller passes none, so a service invoked inside the plan executor's txn
    # auto-enlists. Outside a txn this is {} (identical to pre-D.2 behavior).
    return _txn_session_kwargs(session)


async def award_points(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Award (or deduct) house points and keep standings + audit in sync.

    params: ``{house_id, delta, reason?}``
    returns: ``{"points": <new total>, "house_id": str, "house_name": str, "delta": int}``
    """
    school_id = actor_ctx.school_id
    house_id = params.get("house_id")
    delta = params.get("delta")
    reason = params.get("reason")
    if not house_id:
        raise HousePointsValidationError("house_id is required")
    if delta in (None, ""):
        raise HousePointsValidationError("delta is required")
    try:
        # D-review fix: a non-numeric delta must be a 400 (domain error), not an
        # uncaught ValueError → opaque 500.
        delta = int(delta)
    except (TypeError, ValueError):
        raise HousePointsValidationError("delta must be an integer")

    house = await db.houses.find_one(scoped_filter({"id": house_id}, school_id), {"_id": 0}, **_session_kwargs(session))
    if not house:
        raise HouseNotFoundError("House not found")

    new_points = max(0, house.get("points", 0) + delta)
    now_iso = actor_ctx.now().isoformat()
    await db.houses.update_one(
        scoped_filter({"id": house_id}, school_id),
        {"$set": {"points": new_points, "updated_at": now_iso}},
        **_session_kwargs(session),
    )
    log = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": school_id,
        "house_id": house_id,
        "house_name": house.get("name"),
        "delta": delta,
        "new_total": new_points,
        "reason": reason,
        "awarded_by": actor_ctx.user_id,
        "created_at": now_iso,
    }
    await db.house_points_log.insert_one(log, **_session_kwargs(session))
    await write_audit(
        db,
        action="house_points_award",
        entity_id=house_id,
        collection="houses",
        changed_by=actor_ctx.user_id or "",
        changed_by_role=actor_ctx.role or "",
        school_id=school_id,
        branch_id=actor_ctx.branch_id or "",
        changes={"delta": delta, "new_total": new_points, "reason": reason},
    )
    return {"points": new_points, "house_id": house_id, "house_name": house.get("name"), "delta": delta}
