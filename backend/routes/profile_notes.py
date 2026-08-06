from __future__ import annotations

"""Notes and remarks on a student, staff member or teacher (owner request 4).

Owner and principal only, and PRIVATE TO EACH AUTHOR: each of them sees only the
notes they wrote themselves. See `services/profile_notes_service.py` for why that is
deliberate rather than an oversight.

Pictures ride on the existing `POST /api/upload` with `entity_type=profile-note`;
a note stores the file ids that came back, and the upload route stays the one place
that decides who may read a stored file.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from middleware.auth import require_owner_or_principal
from services.actor_context import actor_ctx_from_user
from services.profile_notes_service import (
    ProfileNoteNotFoundError,
    ProfileNoteValidationError,
    add_note,
    count_notes,
    delete_note,
    list_notes,
    update_note,
)
from tenant import get_school_id

router = APIRouter(prefix="/api/profile-notes", tags=["profile-notes"])


def _ctx(user: dict):
    return actor_ctx_from_user(user, school_id=get_school_id())


@router.get("")
async def list_profile_notes(
    request: Request,
    subject_type: str = None,
    subject_id: str = None,
    user: dict = Depends(require_owner_or_principal),
):
    """Your own notes about one person, newest first."""
    db = get_db()
    try:
        rows = await list_notes(db, _ctx(user), {"subject_type": subject_type, "subject_id": subject_id})
    except ProfileNoteValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.get("/counts")
async def profile_note_counts(
    request: Request,
    subject_type: str = None,
    subject_ids: str = "",
    user: dict = Depends(require_owner_or_principal),
):
    """How many notes YOU have on each of these people, for a directory column.

    `subject_ids` is a comma-separated list. Batched deliberately: the directory
    shows hundreds of rows and one request per row is the N+1 the project bans.
    """
    db = get_db()
    ids = [part.strip() for part in (subject_ids or "").split(",") if part.strip()]
    try:
        counts = await count_notes(db, _ctx(user), subject_type, ids)
    except ProfileNoteValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": counts, "meta": {"count": len(counts)}}


@router.post("")
async def create_profile_note(request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    body = await request.json()
    try:
        note = await add_note(db, _ctx(user), body)
    except ProfileNoteValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": note}


@router.patch("/{note_id}")
async def edit_profile_note(note_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    body = await request.json()
    try:
        note = await update_note(db, _ctx(user), note_id, body)
    except ProfileNoteNotFoundError as e:
        raise HTTPException(404, str(e))
    except ProfileNoteValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": note}


@router.delete("/{note_id}")
async def remove_profile_note(note_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    try:
        await delete_note(db, _ctx(user), note_id)
    except ProfileNoteNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"success": True}
