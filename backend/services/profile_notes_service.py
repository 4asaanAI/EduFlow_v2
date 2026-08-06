"""Private notes and remarks on a student, staff member or teacher.

Owner request 4, 2026-08-06. Aman asked for somewhere to keep notes and remarks on
every profile, with pictures attached. Nothing of the kind existed anywhere in the
product, which Flo confirmed herself in the screenshot he sent.

NOTES ARE PRIVATE TO THEIR AUTHOR. This is decision 3 of that night and it is
deliberate. The owner and the principal may both write notes on the same child, and
each sees ONLY their own: the principal cannot read a note the owner wrote, and the
owner cannot read the principal's. Abhimanyu was shown that consequence in plain words
- that the two of them cannot use this to talk to each other, and that neither can see
what the other has recorded about a child - and chose it over the shared option anyway.

Do not "fix" this into a shared feed. Every read in this module filters on
`author_id`, and there is no endpoint, tool or flag that widens it. A note Flo writes
belongs to whoever asked her for it, for the same reason.

WHY A SEPARATE COLLECTION rather than a field on the student. Notes are unlimited in
number, carry attachments, and are per-author; a field on the record would be one
shared blob, which is exactly the thing this is not. It also keeps a note out of every
student list response, where it has no business being.
"""

from __future__ import annotations

import uuid
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_filter

#: What a note can be attached to. Staff and teachers share one record type.
SUBJECT_TYPES = ("student", "staff")

#: The longest a single note may be. Long enough for a real account of an incident,
#: short enough that the box is a note rather than a document store.
MAX_BODY = 5000

#: The most pictures one note may carry.
MAX_ATTACHMENTS = 10


class ProfileNoteValidationError(Exception):
    """The request was malformed. Maps to 400."""


class ProfileNoteNotFoundError(Exception):
    """No such note, or it belongs to somebody else. Maps to 404 either way.

    Deliberately the same error for both: telling a caller "that note exists but is
    not yours" leaks that the other person wrote one, which is the whole thing this
    module is supposed to keep private.
    """


def _clean_attachments(raw) -> list:
    """Keep only the fields a screen needs to show a picture, and only ours.

    An attachment is a reference to a file already uploaded through
    `POST /api/upload`; nothing here trusts a caller-supplied URL beyond storing it,
    and the upload route is what decides who may read the file itself.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ProfileNoteValidationError("attachments must be a list")
    if len(raw) > MAX_ATTACHMENTS:
        raise ProfileNoteValidationError(f"a note may carry at most {MAX_ATTACHMENTS} pictures")
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            raise ProfileNoteValidationError("each attachment must be an object")
        file_id = str(item.get("file_id") or item.get("id") or "").strip()
        if not file_id:
            raise ProfileNoteValidationError("each attachment needs a file_id from the upload")
        cleaned.append({
            "file_id": file_id,
            "file_url": str(item.get("file_url") or "").strip() or None,
            "file_name": str(item.get("file_name") or "").strip() or None,
            "file_type": str(item.get("file_type") or "").strip() or None,
        })
    return cleaned


def _public(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "_id"}


def _validate_subject(subject_type: str, subject_id: str) -> None:
    if subject_type not in SUBJECT_TYPES:
        raise ProfileNoteValidationError(
            "subject_type must be one of: " + ", ".join(SUBJECT_TYPES)
        )
    if not subject_id:
        raise ProfileNoteValidationError("subject_id is required")


async def _audit(db, actor_ctx: ActorContext, *, action: str, note_id: str, changes: dict) -> None:
    await write_audit_doc(db, {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "entity_type": "profile_note",
        "entity_id": note_id,
        "action": action,
        "changed_by": actor_ctx.user_id,
        "changed_by_role": actor_ctx.role,
        "changes": changes,
        "created_at": actor_ctx.now_iso(),
    }, school_id=actor_ctx.school_id, branch_id=actor_ctx.branch_id)


async def add_note(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Write a note. It belongs to the person writing it and to nobody else."""
    subject_type = str(params.get("subject_type") or "").strip().lower()
    subject_id = str(params.get("subject_id") or "").strip()
    _validate_subject(subject_type, subject_id)

    body = str(params.get("body") or "").strip()
    if not body:
        raise ProfileNoteValidationError("A note needs something written in it")
    if len(body) > MAX_BODY:
        raise ProfileNoteValidationError(f"A note may be at most {MAX_BODY} characters")

    attachments = _clean_attachments(params.get("attachments"))

    note_id = str(uuid.uuid4())
    doc = {
        "_id": note_id,
        "id": note_id,
        "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        # The three author fields are written together and never changed afterwards.
        # `author_id` is the privacy boundary; the other two are so a note still reads
        # sensibly if the account is later renamed or retired.
        "author_id": actor_ctx.user_id,
        "author_name": actor_ctx.actor_name or actor_ctx.user_id,
        "author_role": actor_ctx.role,
        "body": body,
        "attachments": attachments,
        "created_at": actor_ctx.now_iso(),
        "updated_at": actor_ctx.now_iso(),
    }
    await db.profile_notes.insert_one(doc)
    # The body is deliberately NOT copied into the audit row. The log is readable by
    # the owner and the principal, and copying a private note into it would hand each
    # of them the other's notes through the back door.
    await _audit(db, actor_ctx, action="profile_note_added", note_id=note_id, changes={
        "subject_type": subject_type,
        "subject_id": subject_id,
        "length": len(body),
        "attachments": len(attachments),
    })
    return _public(doc)


async def list_notes(db, actor_ctx: ActorContext, params: dict) -> list:
    """Your own notes on one person, newest first. Never anybody else's."""
    subject_type = str(params.get("subject_type") or "").strip().lower()
    subject_id = str(params.get("subject_id") or "").strip()
    _validate_subject(subject_type, subject_id)

    query = scoped_filter({
        "subject_type": subject_type,
        "subject_id": subject_id,
        "author_id": actor_ctx.user_id,
    }, actor_ctx.school_id)  # branch-scope: intentional — a note belongs to one named author about one named person; a branch filter could only hide their own note from them
    rows = await db.profile_notes.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return rows


async def count_notes(db, actor_ctx: ActorContext, subject_type: str, subject_ids: list) -> dict:
    """How many notes YOU have on each of these people. For a directory column.

    Batched on purpose: the directory shows hundreds of rows, and one query per row
    is the N+1 the project bans outright.
    """
    subject_type = str(subject_type or "").strip().lower()
    if subject_type not in SUBJECT_TYPES:
        raise ProfileNoteValidationError(
            "subject_type must be one of: " + ", ".join(SUBJECT_TYPES)
        )
    ids = [str(i).strip() for i in (subject_ids or []) if str(i).strip()]
    if not ids:
        return {}
    query = scoped_filter({
        "subject_type": subject_type,
        "subject_id": {"$in": ids},
        "author_id": actor_ctx.user_id,
    }, actor_ctx.school_id)  # branch-scope: intentional — pinned to this author's own notes about a named list of people
    rows = await db.profile_notes.find(query, {"_id": 0, "subject_id": 1}).to_list(5000)
    counts: dict = {}
    for row in rows:
        key = row.get("subject_id")
        counts[key] = counts.get(key, 0) + 1
    return counts


async def _own_note(db, actor_ctx: ActorContext, note_id: str) -> dict:
    doc = await db.profile_notes.find_one(
        scoped_filter({"id": note_id, "author_id": actor_ctx.user_id}, actor_ctx.school_id),  # branch-scope: intentional — pinned by a unique id and its author
        {"_id": 0},
    )
    if not doc:
        raise ProfileNoteNotFoundError("Note not found")
    return doc


async def update_note(db, actor_ctx: ActorContext, note_id: str, params: dict) -> dict:
    """Correct your own note. The author is never rewritten."""
    existing = await _own_note(db, actor_ctx, note_id)

    update: dict = {}
    if "body" in params:
        body = str(params.get("body") or "").strip()
        if not body:
            raise ProfileNoteValidationError("A note needs something written in it")
        if len(body) > MAX_BODY:
            raise ProfileNoteValidationError(f"A note may be at most {MAX_BODY} characters")
        update["body"] = body
    if "attachments" in params:
        update["attachments"] = _clean_attachments(params.get("attachments"))
    if not update:
        raise ProfileNoteValidationError("Nothing to change")

    update["updated_at"] = actor_ctx.now_iso()
    await db.profile_notes.update_one(
        scoped_filter({"id": note_id, "author_id": actor_ctx.user_id}, actor_ctx.school_id),  # branch-scope: intentional — pinned by a unique id and its author
        {"$set": update},
    )
    await _audit(db, actor_ctx, action="profile_note_updated", note_id=note_id, changes={
        "subject_type": existing.get("subject_type"),
        "subject_id": existing.get("subject_id"),
        "fields": sorted(k for k in update if k != "updated_at"),
    })
    return {**existing, **update}


async def delete_note(db, actor_ctx: ActorContext, note_id: str) -> None:
    """Delete your own note. Yours only."""
    existing = await _own_note(db, actor_ctx, note_id)
    await db.profile_notes.delete_one(
        scoped_filter({"id": note_id, "author_id": actor_ctx.user_id}, actor_ctx.school_id),  # branch-scope: intentional — pinned by a unique id and its author
    )
    await _audit(db, actor_ctx, action="profile_note_deleted", note_id=note_id, changes={
        "subject_type": existing.get("subject_type"),
        "subject_id": existing.get("subject_id"),
    })


async def purge_subject_notes(db, school_id: str, subject_type: str, subject_id: str) -> int:
    """Remove every note about one person, whoever wrote it.

    Called when the person's record is destroyed for good. Leaving notes behind would
    keep a written account of a child after the school had erased them, which is the
    opposite of what erasure means.
    """
    result = await db.profile_notes.delete_many(
        scoped_filter({"subject_type": subject_type, "subject_id": subject_id}, school_id),  # branch-scope: intentional — erasure covers the person everywhere, not one branch's copy
    )
    return getattr(result, "deleted_count", 0) or 0
