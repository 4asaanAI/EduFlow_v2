"""AI feedback store (R10.2) — Helpful/Improve verdicts + candidate corrections.

Every 👍 Helpful / 👎 Improve click on an assistant reply is persisted here as a
tenant-scoped record. An "Improve" click may carry a one-line reason; when it does,
the reason + turn context is parked as a **candidate correction** (`status="pending"`)
— it is NOT auto-activated and is NOT recalled into any reply. Owner/Principal
activate or reject pending corrections via the "What I've learned" surface (R10.4);
only an activated correction becomes a real (fenced, per R6.3) memory.

DPDP: feedback is tenant-scoped and erasable — `erase_owner_feedback` is wired into
the same lifecycle-end path as memories/skills.

Collection: `ai_feedback`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from tenant import get_school_id

logger = logging.getLogger(__name__)

VERDICT_HELPFUL = 1
VERDICT_IMPROVE = 0
_MAX_REASON_LEN = 500
_MAX_TOOLS = 20


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def record_feedback(
    db,
    user: Dict[str, Any],
    *,
    verdict: int,
    conversation_id: Optional[str] = None,
    message_id: Optional[str] = None,
    reason: str = "",
    tool_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Persist one feedback record (R10.2 AC1). Returns the stored doc.

    On an "Improve" verdict WITH a reason, the reason is parked as a pending
    candidate correction (AC2) — never auto-active, never recalled until an
    owner/principal activates it via the R10.4 surface.
    """
    school_id = get_school_id()
    reason = (reason or "").strip()[:_MAX_REASON_LEN]
    tools = [str(t) for t in (tool_names or [])][:_MAX_TOOLS]
    is_improve = int(verdict) == VERDICT_IMPROVE
    doc = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": school_id,
        "user_id": user.get("id", ""),
        "branch_id": user.get("branch_id", ""),
        "conversation_id": conversation_id or None,
        "message_id": message_id or None,
        "verdict": VERDICT_IMPROVE if is_improve else VERDICT_HELPFUL,
        "tool_names": tools,
        # Candidate correction: pending only when there's an actual Improve reason.
        "candidate_correction": reason if (is_improve and reason) else None,
        "status": "pending" if (is_improve and reason) else "none",
        "created_at": _now_iso(),
    }
    try:
        await db.ai_feedback.insert_one(doc)
    except Exception:
        logger.warning("ai_feedback insert failed", exc_info=True)

    # AC5: emit a per-verdict metric row so the per-school helpful-rate
    # (`ai_feedback_ratio`) is computable and alarmable from ai_metrics.
    try:
        from services.ai_metrics import record_ai_metric
        await record_ai_metric(
            db, event="ai_feedback", status=("helpful" if not is_improve else "improve"),
            user_id=user.get("id", ""), school_id=school_id, branch_id=user.get("branch_id", ""),
        )
    except Exception:
        logger.warning("ai_feedback metric emit failed", exc_info=True)
    return doc


async def list_pending_corrections(db, *, school_id: str, user_id: Optional[str] = None) -> List[Dict]:
    """Pending candidate corrections for the R10.4 'What I've learned' surface.

    `user_id=None` returns the whole school's pending queue (the owner/principal
    review view); a `user_id` narrows it to one author.
    """
    q: Dict[str, Any] = {"schoolId": school_id, "status": "pending"}
    if user_id:
        q["user_id"] = user_id
    return await db.ai_feedback.find(q, {"_id": 0}).to_list(500)


async def activate_correction(db, actor: Dict[str, Any], *, feedback_id: str) -> Optional[Dict]:
    """R10.2 AC3: promote a pending candidate correction into an ACTIVE, FENCED memory.

    The correction text becomes a real memory for the reviewer who authored it
    (source='correction', high confidence) so it benefits *their* future turns. On
    recall it is injected inside the R6.3 instruction-inert fence — it can NEVER
    override role permissions, confirm/kill-switch/lockdown gates, tenancy scope, or
    school policy. The feedback row is marked 'activated' (leaves the pending queue)
    ONLY when a memory was actually created. Returns the created memory, or None.

    `actor` is the reviewing owner/principal; the correction is scoped to the actor's
    OWN pending queue — an owner/principal reviews the corrections THEY flagged, so
    another staff member's free-text notes are never exposed cross-user. Route enforces
    role.
    """
    school_id = get_school_id()
    actor_id = (actor or {}).get("id", "")
    row = await db.ai_feedback.find_one(
        {"schoolId": school_id, "id": feedback_id, "user_id": actor_id, "status": "pending"}
    )
    text = ((row or {}).get("candidate_correction") or "").strip()
    if not row or not text:
        return None

    from services.actor_context import actor_ctx_from_user
    from services.audit_service import write_audit
    from services.memory import store as memory_store

    ctx = actor_ctx_from_user(actor or {}, school_id=school_id,
                              branch_id=(actor or {}).get("branch_id") or row.get("branch_id") or "")
    saved = await memory_store.add_memory(
        db, ctx, text=text, category="preference", source="correction", confidence=0.95,
    )
    # Only leave the pending queue when a memory was actually created — a
    # redacted-empty or otherwise-dropped correction must NOT be silently consumed.
    if not saved:
        return None
    await db.ai_feedback.update_one(
        {"schoolId": school_id, "id": feedback_id, "user_id": actor_id, "status": "pending"},
        {"$set": {"status": "activated", "activated_at": _now_iso(),
                  "activated_by": actor_id, "memory_id": saved.get("id")}},
    )
    try:
        await write_audit(
            db, action="ai_correction_activate", entity_id=feedback_id, collection="ai_feedback",
            changed_by=actor_id or "system", changed_by_role=(actor or {}).get("role", ""),
            school_id=school_id, changes={"memory_id": saved.get("id"), "author": row.get("user_id")},
        )
    except Exception:
        logger.warning("ai_correction_activate audit failed", exc_info=True)
    return saved


async def reject_correction(db, actor: Dict[str, Any], *, feedback_id: str) -> bool:
    """R10.2 AC3: reject a pending candidate correction — it never becomes a memory.

    Scoped to the actor's OWN pending queue (parity with activate)."""
    school_id = get_school_id()
    actor_id = (actor or {}).get("id", "")
    res = await db.ai_feedback.update_one(
        {"schoolId": school_id, "id": feedback_id, "user_id": actor_id, "status": "pending"},
        {"$set": {"status": "rejected", "rejected_at": _now_iso(), "rejected_by": actor_id}},
    )
    return bool(getattr(res, "modified_count", 0))


async def feedback_ratio(db, *, school_id: str) -> Dict[str, Any]:
    """Per-school helpful-rate (AC5). {helpful, total, ratio} — ratio None if no data."""
    total = await db.ai_feedback.count_documents({"schoolId": school_id})
    helpful = await db.ai_feedback.count_documents({"schoolId": school_id, "verdict": VERDICT_HELPFUL})
    return {"helpful": helpful, "total": total,
            "ratio": round(helpful / total, 4) if total else None}


async def erase_owner_feedback(db, *, school_id: str, user_id: str, changed_by: str = "system") -> int:
    """DPDP: delete all feedback for a retired user (R10.2 AC4)."""
    try:
        res = await db.ai_feedback.delete_many({"schoolId": school_id, "user_id": user_id})
        deleted = getattr(res, "deleted_count", 0) or 0
        if deleted:
            logger.info("erased %d ai_feedback rows for user=%s (by %s)", deleted, user_id, changed_by)
        return deleted
    except Exception:
        logger.warning("erase_owner_feedback failed for user=%s", user_id, exc_info=True)
        return 0
