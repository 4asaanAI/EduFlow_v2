"""MongoDB-backed, per-owner memory store (Stories G.2, G.3, G.7, G.8).

Cloned from Odysseus `MemoryManager` (`src/memory.py`) and re-homed onto MongoDB,
scoped by **`(user_id, schoolId)`** so one Owner/Principal's memory is never visible
to another and never crosses tenants (FR34). Every write is PII-minimized via
`ai.redaction.redact_text_for_memory()` (DPDP, FR34) and audited via `write_audit`.

Collection: `ai_memories`. Document shape (EduFlow-customized from Odysseus):
    id, user_id, schoolId, text, category, source, confidence, uses,
    student_refs[], superseded(bool), created_at/created_at_ts, updated_at/updated_at_ts

All functions take the pinned `ActorContext` so the AI path and any future REST
path reach the store with identical authority context (AD7 parity spine).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional

from ai.redaction import redact_text_for_memory
from services.actor_context import ActorContext
from services.audit_service import write_audit
from services.memory.retrieval import score_memories
from services.memory.vector import get_memory_vector_store, vector_enabled

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"fact", "preference", "contact", "task", "concern"}
DEFAULT_CONFIDENCE = 0.7
RECALL_K = 6
# Retention: memories untouched for this long are pruned (G.7). 18 months mirrors a
# generous academic-records review cycle; a TTL index also enforces it server-side.
RETENTION_DAYS = 540
# R6.4 (XM10): a hard, DOCUMENTED per-owner memory cap. Recall scans all of an
# owner's memories, so an unbounded store is a latency/cost cliff. When the cap is
# exceeded the least-valuable memories (lowest confidence, then least-recently
# updated) are evicted — logged + audited, never a silent hard wall.
MAX_MEMORIES_PER_USER = 500
# Page size for full-collection sweeps (erase/purge) — replaces the old hard
# `.to_list(5000)` truncation that silently skipped memories past 5000 (XM5).
_SWEEP_PAGE = 1000


async def _paged_find(db, query: Dict[str, Any], projection: Dict[str, Any]) -> List[Dict]:
    """Fetch ALL docs matching `query`, page by page — no silent 5000 cap (XM5)."""
    out: List[Dict] = []
    skip = 0
    while True:
        page = await db.ai_memories.find(query, projection).skip(skip).limit(_SWEEP_PAGE).to_list(_SWEEP_PAGE)
        if not page:
            break
        out.extend(page)
        if len(page) < _SWEEP_PAGE:
            break
        skip += _SWEEP_PAGE
    return out


def _scope(ctx: ActorContext) -> Dict[str, str]:
    return {"schoolId": ctx.school_id, "user_id": ctx.user_id}


def _normalize_category(category: Optional[str]) -> str:
    cat = (category or "fact").strip().lower()
    return cat if cat in VALID_CATEGORIES else "fact"


async def add_memory(
    db,
    ctx: ActorContext,
    *,
    text: str,
    category: str = "fact",
    source: str = "auto",
    confidence: float = DEFAULT_CONFIDENCE,
    student_refs: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Persist a single memory for this owner. Returns the stored doc (or None).

    - Empty/whitespace text is ignored (returns None).
    - Text is redacted BEFORE persistence (DPDP) — raw Aadhaar/phone/email scrubbed.
    - Exact-text duplicates for the same owner are de-duplicated (uses bumped instead).
    """
    if not ctx.user_id:
        return None
    if not text or not text.strip():
        return None

    clean = redact_text_for_memory(text.strip())
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = DEFAULT_CONFIDENCE
    conf = min(1.0, max(0.0, conf))

    # Dedup: same owner + identical (post-redaction) text → bump uses, don't re-add.
    existing = await db.ai_memories.find_one(
        {**_scope(ctx), "text": clean, "superseded": {"$ne": True}}
    )
    if existing:
        await increment_uses(db, ctx, [existing["id"]])
        return existing

    now = ctx.now()
    now_ts = now.timestamp()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": ctx.user_id,
        "schoolId": ctx.school_id,
        "text": clean,
        "category": _normalize_category(category),
        "source": source or "auto",
        "confidence": conf,
        "uses": 0,
        "student_refs": list(student_refs or []),
        "superseded": False,
        "created_at": now.isoformat(),
        "created_at_ts": now_ts,
        "updated_at": now.isoformat(),
        "updated_at_ts": now_ts,
        # Date anchor for the TTL retention index (G.7).
        "expire_at": now + timedelta(days=RETENTION_DAYS),
    }
    await db.ai_memories.insert_one(doc)
    get_memory_vector_store().add(
        school_id=ctx.school_id, user_id=ctx.user_id, memory_id=doc["id"], text=clean
    )
    await _enforce_user_cap(db, ctx)
    await write_audit(
        db,
        action="ai_memory_save",
        entity_id=doc["id"],
        collection="ai_memories",
        changed_by=ctx.user_id,
        changed_by_role=ctx.role or "",
        school_id=ctx.school_id,
        branch_id=ctx.branch_id or "",
        changes={"source": source, "category": doc["category"]},
    )
    return {k: v for k, v in doc.items() if k != "_id"}


async def _enforce_user_cap(db, ctx: ActorContext) -> int:
    """R6.4 (XM10): keep an owner's active memory count at/under MAX_MEMORIES_PER_USER.

    Evicts the least-valuable surplus (lowest confidence, then least-recently
    updated) — logged + audited so eviction is never silent. Returns count evicted.
    """
    q = {**_scope(ctx), "superseded": {"$ne": True}}
    total = await db.ai_memories.count_documents(q)
    if total <= MAX_MEMORIES_PER_USER:
        return 0
    surplus = total - MAX_MEMORIES_PER_USER
    active = await _paged_find(db, q, {"_id": 0, "id": 1, "confidence": 1, "updated_at_ts": 1})
    # Least valuable first: lowest confidence, then oldest update.
    active.sort(key=lambda m: (m.get("confidence", 0), m.get("updated_at_ts", 0)))
    victims = active[:surplus]
    for m in victims:
        await db.ai_memories.delete_one({**_scope(ctx), "id": m["id"]})
        get_memory_vector_store().remove(
            school_id=ctx.school_id, user_id=ctx.user_id, memory_id=m["id"]
        )
    if victims:
        logger.info(
            "ai_memory cap reached (user=%s, cap=%d): evicted %d least-valuable memories",
            ctx.user_id, MAX_MEMORIES_PER_USER, len(victims),
        )
        await write_audit(
            db, action="ai_memory_evict", entity_id=ctx.user_id, collection="ai_memories",
            changed_by="system", changed_by_role="system", school_id=ctx.school_id,
            branch_id=ctx.branch_id or "", changes={"evicted": len(victims), "cap": MAX_MEMORIES_PER_USER},
        )
    return len(victims)


async def list_memories(db, ctx: ActorContext, *, include_superseded: bool = False) -> List[Dict]:
    if not ctx.user_id:
        return []
    q: Dict[str, Any] = dict(_scope(ctx))
    if not include_superseded:
        q["superseded"] = {"$ne": True}
    return await db.ai_memories.find(q, {"_id": 0}).to_list(2000)


async def increment_uses(db, ctx: ActorContext, ids: List[str]) -> None:
    """Bump `uses` for memories actually injected into context (Odysseus parity)."""
    if not ids or not ctx.user_id:
        return
    for mid in set(ids):
        await db.ai_memories.update_one(
            {**_scope(ctx), "id": mid}, {"$inc": {"uses": 1}}
        )


async def recall(db, ctx: ActorContext, query: str, *, k: int = RECALL_K) -> List[Dict]:
    """Hybrid recall: vector candidates ∪ keyword scoring, best-first (FR33).

    Always scores via keyword (zero-dep, always available). If the vector store is
    healthy it contributes additional semantic candidates; results are merged and
    re-ranked by keyword score so behavior is deterministic and never *worse* than
    keyword-only. `uses` is incremented for whatever is actually returned.
    """
    if not ctx.user_id or not query or not query.strip():
        return []
    all_mems = await list_memories(db, ctx)
    if not all_mems:
        return []

    by_id = {m["id"]: m for m in all_mems}
    vstore = get_memory_vector_store()
    if not vstore.healthy:
        # R6.4 (XM10): make degraded (keyword-only) recall VISIBLE rather than
        # silent so operators can see when the semantic index is unavailable.
        # Only WARN when vectors are meant to be on but the index is down (a real
        # degradation); when the path is intentionally disabled (the default),
        # keyword-only is expected — log at debug so we don't spam every turn.
        if vector_enabled():
            logger.warning(
                "memory recall degraded to keyword-only (MEMORY_VECTOR_ENABLED "
                "is on but the vector index is unavailable)"
            )
        else:
            logger.debug("memory recall keyword-only (vector path disabled by config)")
    if vstore.healthy:
        # Pull vector hits and ensure they're in the candidate pool (they already are,
        # since list_memories returns all). Vector mainly helps when lexical overlap is
        # low; we still re-rank by the deterministic keyword score for stability.
        try:
            vhits = vstore.search(
                school_id=ctx.school_id, user_id=ctx.user_id, query=query, k=k * 2
            )
            for h in vhits:
                mem = by_id.get(h["memory_id"])
                if mem is not None:
                    mem.setdefault("_vector_score", h["score"])
        except Exception as e:  # never let recall fail a chat turn
            logger.warning("vector recall degraded to keyword-only: %s", e)

    now = ctx.now().timestamp()
    scored = score_memories(query, all_mems, now=now)
    # Fold in vector candidates that keyword missed (low lexical overlap, high semantic).
    if vstore.healthy:
        keyword_ids = {m["id"] for m in scored}
        for mem in all_mems:
            if mem["id"] not in keyword_ids and mem.get("_vector_score", 0) >= 0.6:
                scored.append({**mem, "_score": round(mem["_vector_score"] * 0.5, 5)})
        scored.sort(key=lambda m: m["_score"], reverse=True)

    top = scored[:k]
    await increment_uses(db, ctx, [m["id"] for m in top])
    return top


async def correct_memory(
    db, ctx: ActorContext, *, memory_id: Optional[str] = None,
    match_text: Optional[str] = None, new_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Correct or remove a wrong auto-saved memory (G.8 anti-poisoning).

    If `new_text` is given the matched memory is replaced (text updated, confidence
    reset high since it's now user-confirmed, recency refreshed). If `new_text` is
    None the memory is removed. Matching is by id, else by exact/substring text.
    Returns {updated, removed, matched_ids}.
    """
    if not ctx.user_id:
        return {"updated": 0, "removed": 0, "matched_ids": []}

    candidates = await list_memories(db, ctx)
    matched: List[Dict] = []
    if memory_id:
        matched = [m for m in candidates if m["id"] == memory_id]
    elif match_text:
        ml = match_text.strip().lower()
        matched = [m for m in candidates if ml and ml in (m.get("text") or "").lower()]

    if not matched:
        return {"updated": 0, "removed": 0, "matched_ids": []}

    matched_ids = [m["id"] for m in matched]
    if new_text and new_text.strip():
        clean = redact_text_for_memory(new_text.strip())
        now = ctx.now()
        for mid in matched_ids:
            await db.ai_memories.update_one(
                {**_scope(ctx), "id": mid},
                {"$set": {
                    "text": clean,
                    "confidence": 0.95,
                    "source": "corrected",
                    "superseded": False,
                    "updated_at": now.isoformat(),
                    "updated_at_ts": now.timestamp(),
                    "expire_at": now + timedelta(days=RETENTION_DAYS),
                }},
            )
            get_memory_vector_store().add(
                school_id=ctx.school_id, user_id=ctx.user_id, memory_id=mid, text=clean
            )
        action, updated, removed = "ai_memory_correct", len(matched_ids), 0
    else:
        for mid in matched_ids:
            await db.ai_memories.delete_one({**_scope(ctx), "id": mid})
            get_memory_vector_store().remove(
                school_id=ctx.school_id, user_id=ctx.user_id, memory_id=mid
            )
        action, updated, removed = "ai_memory_forget", 0, len(matched_ids)

    await write_audit(
        db, action=action, entity_id=matched_ids[0], collection="ai_memories",
        changed_by=ctx.user_id, changed_by_role=ctx.role or "",
        school_id=ctx.school_id, branch_id=ctx.branch_id or "",
        changes={"matched": len(matched_ids), "removed": removed},
    )
    return {"updated": updated, "removed": removed, "matched_ids": matched_ids}


async def find_memories_matching(db, ctx: ActorContext, match_text: str) -> List[Dict]:
    """R6.2: return the memories whose text contains `match_text` (case-insensitive).

    Discovery-only — used by the two-step forget flow to SHOW the owner exactly
    what would be deleted before anything is removed. Never mutates.
    """
    if not ctx.user_id or not match_text or not match_text.strip():
        return []
    ml = match_text.strip().lower()
    return [m for m in await list_memories(db, ctx) if ml in (m.get("text") or "").lower()]


async def delete_memories(db, ctx: ActorContext, ids: List[str]) -> int:
    """R6.2: delete a SPECIFIC set of memories by id (never a broad substring sweep).

    This is the second step of the destructive forget flow — the ids come from a
    set the owner was shown and explicitly confirmed.
    """
    if not ctx.user_id or not ids:
        return 0
    removed = 0
    for mid in ids:
        res = await db.ai_memories.delete_one({**_scope(ctx), "id": mid})
        if getattr(res, "deleted_count", 1):
            removed += 1
        get_memory_vector_store().remove(
            school_id=ctx.school_id, user_id=ctx.user_id, memory_id=mid
        )
    if removed:
        await write_audit(
            db, action="ai_memory_forget", entity_id=ids[0], collection="ai_memories",
            changed_by=ctx.user_id, changed_by_role=ctx.role or "",
            school_id=ctx.school_id, branch_id=ctx.branch_id or "",
            changes={"removed": removed, "confirmed": True},
        )
    return removed


async def erase_owner_memories(db, *, school_id: str, user_id: str, changed_by: str = "system") -> int:
    """DPDP §12 right-to-erasure: delete ALL memories for one owner (G.7)."""
    q = {"schoolId": school_id, "user_id": user_id}
    # XM5: page through ALL ids (was capped at 5000, silently skipping the rest).
    ids = [m["id"] for m in await _paged_find(db, q, {"_id": 0, "id": 1})]
    res = await db.ai_memories.delete_many(q)
    vstore = get_memory_vector_store()
    for mid in ids:
        vstore.remove(school_id=school_id, user_id=user_id, memory_id=mid)
    if ids:
        await write_audit(
            db, action="ai_memory_erase_owner", entity_id=user_id, collection="ai_memories",
            changed_by=changed_by, changed_by_role="system", school_id=school_id,
            changes={"deleted": len(ids)},
        )
    return getattr(res, "deleted_count", len(ids))


async def purge_student_references(db, *, school_id: str, student_id: str, changed_by: str = "system") -> int:
    """When a student's records are erased (DPDP §12), purge any memory that
    references that student (G.7). Owner-agnostic: scans the whole school's memories.
    """
    # Filter in Python on array membership so behavior is identical on the FakeDb
    # tier (which doesn't model Mongo array-contains) and real Mongo.
    # XM5: page through ALL of the school's memories (was capped at 5000).
    candidates = await _paged_find(db, {"schoolId": school_id}, {"_id": 0})
    docs = [m for m in candidates if student_id in (m.get("student_refs") or [])]
    vstore = get_memory_vector_store()
    for m in docs:
        await db.ai_memories.delete_one({"schoolId": school_id, "id": m["id"]})
        vstore.remove(school_id=school_id, user_id=m.get("user_id"), memory_id=m["id"])
    if docs:
        await write_audit(
            db, action="ai_memory_purge_student", entity_id=student_id, collection="ai_memories",
            changed_by=changed_by, changed_by_role="system", school_id=school_id,
            changes={"purged": len(docs)},
        )
    return len(docs)


async def prune_expired(db, ctx: ActorContext) -> int:
    """Application-side retention sweep (the TTL index is the primary enforcer).

    Deletes this owner's memories untouched for > RETENTION_DAYS. Safe to call
    opportunistically; returns the number pruned.
    """
    if not ctx.user_id:
        return 0
    cutoff = ctx.now().timestamp() - RETENTION_DAYS * 24 * 3600
    stale = await _paged_find(
        db, {**_scope(ctx), "updated_at_ts": {"$lt": cutoff}}, {"_id": 0, "id": 1}
    )
    for m in stale:
        await db.ai_memories.delete_one({**_scope(ctx), "id": m["id"]})
        get_memory_vector_store().remove(
            school_id=ctx.school_id, user_id=ctx.user_id, memory_id=m["id"]
        )
    return len(stale)
