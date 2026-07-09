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


async def list_pending_corrections(db, *, school_id: str, user_id: str) -> List[Dict]:
    """Pending candidate corrections for the R10.4 'What I've learned' surface."""
    return await db.ai_feedback.find(
        {"schoolId": school_id, "user_id": user_id, "status": "pending"},
        {"_id": 0},
    ).to_list(500)


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
