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

import hashlib
import json
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


def tools_signature(tool_names: Optional[List[str]]) -> str:
    """Stable hash of the CURRENT registry schemas for `tool_names` (R10.3 AC3).

    A skill stores this at save time; on recall the store recomputes it. A mismatch
    means the underlying tool schema drifted (a tool was renamed/removed or its
    params/roles changed), so the routine is surfaced as 'needs updating' instead of
    silently replaying a stale plan. Returns "" when the skill referenced no tools
    (nothing to drift-check).
    """
    names = sorted({str(t) for t in (tool_names or []) if t})
    if not names:
        return ""
    try:
        from ai.tool_functions_v2 import TOOL_REGISTRY
    except Exception:
        return ""
    parts: List[str] = []
    for name in names:
        entry = TOOL_REGISTRY.get(name)
        if not entry:
            parts.append(f"{name}:MISSING")  # removed/renamed → drift
            continue
        sig = {
            "roles": sorted(entry.get("roles", []) or []),
            "params": entry.get("params_schema", {}) or {},
            "description": entry.get("description", "") or "",
        }
        parts.append(f"{name}:" + json.dumps(sig, sort_keys=True, default=str))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


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
    tool_names: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Persist a learned skill. Drops below-threshold and duplicate-title skills.

    `tool_names` are the tools the routine relied on; they anchor the R10.3 AC3
    drift check (a `tool_signature` snapshot is stored and rechecked on recall).
    """
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
        # R10.3 AC3: versioning + tool-schema drift anchor.
        "version": 1,
        "tool_names": [str(t) for t in (tool_names or []) if t],
        "tool_signature": tools_signature(tool_names),
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
    top = scored[:k]
    # R10.3 AC3: recompute the tool-schema signature; flag drifted routines so the
    # recall block can say "this routine needs updating" instead of replaying a
    # stale plan. Empty stored signature (skill referenced no tools) → no check.
    for s in top:
        stored = s.get("tool_signature") or ""
        current = tools_signature(s.get("tool_names") or [])
        s["needs_update"] = bool(stored and current and stored != current)
    return top


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


async def delete_skill(db, ctx: ActorContext, skill_id: str) -> bool:
    """R10.4 AC1: delete one skill/routine the owner controls. Returns True iff removed."""
    if not ctx.user_id or not skill_id:
        return False
    res = await db.ai_skills.delete_one({**_scope(ctx), "id": skill_id})
    removed = bool(getattr(res, "deleted_count", 0))
    if removed:
        await write_audit(
            db, action="ai_skill_delete", entity_id=skill_id, collection="ai_skills",
            changed_by=ctx.user_id, changed_by_role=ctx.role or "",
            school_id=ctx.school_id, branch_id=ctx.branch_id or "",
            changes={"deleted": 1},
        )
    return removed


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
