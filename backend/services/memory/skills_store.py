"""MongoDB-backed skills store (Story G.6) — cloned from Odysseus `skills.py`.

A "skill" is a distilled, reusable procedure the assistant learned from a complex
run (>=2 rounds or >=2 tool calls). Scoped by `(user_id, schoolId)` like memories
(FR34). No UI (FR32) — extraction is automatic, feedback is an in-chat signal.

Collection: `ai_skills`. Document shape:
    id, user_id, schoolId, title, problem, solution, steps[], tags[],
    source, confidence, uses, helpful, not_helpful,
    created_at/created_at_ts, updated_at/updated_at_ts
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from ai.redaction import redact_text_for_memory
from services.actor_context import ActorContext
from services.audit_service import write_audit
from services.memory.retrieval import score_memories

# Below this the extractor's own reliability estimate reads as a one-off — drop it.
MIN_CONFIDENCE = 0.6


def _scope(ctx: ActorContext) -> Dict[str, str]:
    return {"schoolId": ctx.school_id, "user_id": ctx.user_id}


async def list_skills(db, ctx: ActorContext) -> List[Dict]:
    if not ctx.user_id:
        return []
    return await db.ai_skills.find(dict(_scope(ctx)), {"_id": 0}).to_list(1000)


async def _has_duplicate_title(db, ctx: ActorContext, title: str) -> bool:
    wanted = (title or "").strip().lower()
    if not wanted:
        return False
    for s in await list_skills(db, ctx):
        if (s.get("title") or "").strip().lower() == wanted:
            return True
    return False


async def add_skill(
    db, ctx: ActorContext, *,
    title: str, problem: str = "", solution: str = "",
    steps: Optional[List[str]] = None, tags: Optional[List[str]] = None,
    source: str = "learned", confidence: float = 0.7,
) -> Optional[Dict[str, Any]]:
    """Persist a learned skill. Drops below-threshold and duplicate-title skills."""
    if not ctx.user_id:
        return None
    title = (title or "").strip()
    if not title:
        return None
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = 0.7
    if conf < MIN_CONFIDENCE:
        return None
    if await _has_duplicate_title(db, ctx, title):
        return None

    # A skill is replayed back into the LLM context on recall, so PII-minimize its
    # free-text fields (DPDP hard control) the same way memories are scrubbed.
    now = ctx.now()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": ctx.user_id,
        "schoolId": ctx.school_id,
        "title": redact_text_for_memory(title),
        "problem": redact_text_for_memory(problem or ""),
        "solution": redact_text_for_memory(solution or ""),
        "steps": [redact_text_for_memory(str(s)) for s in (steps or [])],
        "tags": list(tags or []),
        "source": source or "learned",
        "confidence": min(1.0, max(0.0, conf)),
        "uses": 0,
        "helpful": 0,
        "not_helpful": 0,
        "created_at": now.isoformat(),
        "created_at_ts": now.timestamp(),
        "updated_at": now.isoformat(),
        "updated_at_ts": now.timestamp(),
    }
    await db.ai_skills.insert_one(doc)
    await write_audit(
        db, action="ai_skill_save", entity_id=doc["id"], collection="ai_skills",
        changed_by=ctx.user_id, changed_by_role=ctx.role or "",
        school_id=ctx.school_id, branch_id=ctx.branch_id or "",
        changes={"title": title, "confidence": doc["confidence"]},
    )
    return {k: v for k, v in doc.items() if k != "_id"}


async def recall_skills(db, ctx: ActorContext, query: str, *, k: int = 3) -> List[Dict]:
    """Keyword-match relevant skills for the query (reuses memory scoring)."""
    if not ctx.user_id or not query or not query.strip():
        return []
    skills = await list_skills(db, ctx)
    # Score against a synthetic "text" = title + tags + problem so the same scorer works.
    enriched = [
        {**s, "text": " ".join(filter(None, [s.get("title", ""), " ".join(s.get("tags", [])), s.get("problem", "")]))}
        for s in skills
    ]
    now = ctx.now().timestamp()
    scored = score_memories(query, enriched, now=now)
    return scored[:k]


async def record_feedback(db, ctx: ActorContext, *, skill_id: str, helpful: bool) -> bool:
    """In-chat feedback signal — mark a recalled skill helpful/not (G.6, no UI)."""
    if not ctx.user_id or not skill_id:
        return False
    field = "helpful" if helpful else "not_helpful"
    existing = await db.ai_skills.find_one({**_scope(ctx), "id": skill_id})
    if not existing:
        return False
    await db.ai_skills.update_one(
        {**_scope(ctx), "id": skill_id},
        {"$inc": {field: 1}, "$set": {"updated_at_ts": ctx.now().timestamp()}},
    )
    return True


async def erase_owner_skills(db, *, school_id: str, user_id: str, changed_by: str = "system") -> int:
    """Delete all skills for one owner (G.7 erasure parity with memories)."""
    q = {"schoolId": school_id, "user_id": user_id}
    count = await db.ai_skills.count_documents(q)
    await db.ai_skills.delete_many(q)
    if count:
        await write_audit(
            db, action="ai_skill_erase_owner", entity_id=user_id, collection="ai_skills",
            changed_by=changed_by, changed_by_role="system", school_id=school_id,
            changes={"deleted": count},
        )
    return count
