"""Epic R10.4 — "What I've learned" transparency & control surface.

Owner/Principal-only endpoints that expose (and let the owner control) everything the
assistant has learned about them: active memories, saved routines (skills), and
pending candidate corrections from 👎 Improve feedback. Every mutation is audited
inside the store layer; bulk deletes are two-step (F.10). All reads/writes are
`(user_id, schoolId)`-scoped via the pinned ActorContext, so one school/owner can
never see or touch another's learned data (FR34).

Routing note: this is the FIRST HTTP surface for memory/skills. Earlier phases had
none by design (FR32); it is introduced here deliberately for the R10.4 control panel
and stays gated to Owner/Principal (the Phase-1 memory subjects).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from middleware.auth import get_current_user, require_owner_or_principal
from services.actor_context import actor_ctx_from_user
from services.memory import feedback_store, skills_store
from services.memory import store as memory_store
from tenant import get_school_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/learning", tags=["learning"])

_MAX_BULK_DELETE = 100


def _ctx(user: dict):
    return actor_ctx_from_user(user, branch_id=user.get("branch_id"))


@router.get("/overview")
async def overview(request: Request, user: dict = Depends(require_owner_or_principal)):
    """AC1: active + deactivated memories, skills, and this reviewer's pending corrections."""
    db = get_db()
    ctx = _ctx(user)
    all_mems = await memory_store.list_memories(db, ctx, include_superseded=True)
    memories = [m for m in all_mems if not m.get("superseded")]
    deactivated = [m for m in all_mems if m.get("superseded")]
    skills = await skills_store.list_skills(db, ctx)
    # AC1 drift status per skill (same check recall uses) so the panel can flag
    # routines that need updating.
    for s in skills:
        stored = s.get("tool_signature") or ""
        current = skills_store.tools_signature(s.get("tool_names") or [])
        s["needs_update"] = bool(stored and current and stored != current)
    # Only THIS reviewer's own pending queue — never expose another staff member's
    # free-text "Improve" notes cross-user (DPDP; owner/principal review what they flagged).
    pending = await feedback_store.list_pending_corrections(db, school_id=get_school_id(), user_id=user.get("id"))
    return {
        "success": True,
        "data": {
            "memories": memories,
            "deactivated_memories": deactivated,
            "skills": skills,
            "pending_corrections": pending,
        },
        "meta": {"memories": len(memories), "deactivated": len(deactivated),
                 "skills": len(skills), "pending": len(pending)},
    }


@router.post("/corrections/{feedback_id}/activate")
async def activate_correction(feedback_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    """AC1 / R10.2 AC3: promote a pending correction into an active fenced memory."""
    db = get_db()
    saved = await feedback_store.activate_correction(db, user, feedback_id=feedback_id)
    if not saved:
        raise HTTPException(404, "No pending correction found for that id")
    return {"success": True, "data": {"memory": saved}}


@router.post("/corrections/{feedback_id}/reject")
async def reject_correction(feedback_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    ok = await feedback_store.reject_correction(db, user, feedback_id=feedback_id)
    if not ok:
        raise HTTPException(404, "No pending correction found for that id")
    return {"success": True}


@router.patch("/memories/{memory_id}")
async def edit_memory(memory_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    """AC1: edit a memory's text (re-confirms it: confidence reset high, source='corrected')."""
    db = get_db()
    try:
        body = await request.json()
    except Exception:
        body = {}
    new_text = (body.get("text") or "").strip()
    if not new_text:
        raise HTTPException(400, "text is required")
    result = await memory_store.correct_memory(db, _ctx(user), memory_id=memory_id, new_text=new_text)
    if not result.get("updated"):
        raise HTTPException(404, "Memory not found")
    return {"success": True, "data": result}


@router.post("/memories/{memory_id}/deactivate")
async def deactivate_memory(memory_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    """AC1: soft-deactivate (or reactivate) a memory — excluded from recall, kept for history."""
    db = get_db()
    try:
        body = await request.json()
    except Exception:
        body = {}
    superseded = bool(body.get("superseded", True))
    ok = await memory_store.deactivate_memory(db, _ctx(user), memory_id, superseded=superseded)
    if not ok:
        raise HTTPException(404, "Memory not found")
    return {"success": True, "data": {"superseded": superseded}}


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    """AC1: hard-delete a single memory."""
    db = get_db()
    removed = await memory_store.delete_memories(db, _ctx(user), [memory_id])
    if not removed:
        raise HTTPException(404, "Memory not found")
    return {"success": True, "data": {"removed": removed}}


@router.post("/memories/bulk-delete")
async def bulk_delete_memories(request: Request, user: dict = Depends(require_owner_or_principal)):
    """AC1: two-step bulk delete (F.10). Without `confirm: true` it returns a PREVIEW of
    exactly what would be deleted and removes nothing; the client re-sends with
    `confirm: true` to actually delete."""
    db = get_db()
    try:
        body = await request.json()
    except Exception:
        body = {}
    raw_ids = body.get("ids")
    if not isinstance(raw_ids, list):
        raise HTTPException(400, "ids must be a list")
    ids = [str(i) for i in raw_ids if i]
    if not ids:
        raise HTTPException(400, "ids is required")
    # No silent truncation (XM10 ethos) — tell the caller if they exceeded the cap.
    if len(ids) > _MAX_BULK_DELETE:
        raise HTTPException(400, f"too many ids (max {_MAX_BULK_DELETE} per request)")
    ctx = _ctx(user)
    if not body.get("confirm"):
        existing = await memory_store.list_memories(db, ctx)
        preview = [{"id": m["id"], "text": m.get("text")} for m in existing if m["id"] in set(ids)]
        return {"success": True, "data": {"confirm_required": True, "would_delete": preview,
                                          "count": len(preview)}}
    removed = await memory_store.delete_memories(db, ctx, ids)
    return {"success": True, "data": {"removed": removed}}


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    """AC1: delete a saved routine."""
    db = get_db()
    removed = await skills_store.delete_skill(db, _ctx(user), skill_id)
    if not removed:
        raise HTTPException(404, "Routine not found")
    return {"success": True, "data": {"removed": True}}
