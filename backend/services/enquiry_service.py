"""Admission-enquiry domain service — single shared write path for enquiry
creation and pipeline-stage updates (AI Layer Hardening, AD7 — drift-gate
remediation for the `create_enquiry` / `update_enquiry_status` AI tools).

Both the REST routes (`POST/PATCH /api/ops/enquiries*`) and the AI tools call
these functions, so an AI enquiry write is byte-identical to a panel write:
same field set, same stage-transition guard, same timeline entries.

**Parity decision (case-by-case, canonical = REST):** the legacy AI tool wrote
extra fields (`notes`, `created_by`, `updated_at`) and skipped the transition
guard entirely — an AI call could jump an enquiry to any stage. Both now share
the REST behavior: owner may move stages freely (except reverting `enrolled`
with a linked student), everyone else follows `ALLOWED_TRANSITIONS`.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import uuid

from services.actor_context import ActorContext
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import scoped_query


class EnquiryValidationError(Exception):
    """Invalid input or stage transition → HTTP 400."""


class EnquiryNotFoundError(Exception):
    """Unknown enquiry id within the caller's scope → HTTP 404."""


class EnquiryConflictError(Exception):
    """Reverting an enrolled enquiry with a linked student record → HTTP 409."""


# Aligned with frontend pipeline stages (+ legacy backward-compat stages).
ALLOWED_TRANSITIONS = {
    "new": {"contacted", "lost"},
    "contacted": {"visit_scheduled", "lost"},
    "visit_scheduled": {"visited", "lost"},
    "visited": {"documents_submitted", "lost"},
    "documents_submitted": {"fee_paid", "lost"},
    "fee_paid": {"enrolled", "lost"},
    "enrolled": {"lost"},
    "lost": set(),
    "applied": {"admitted", "enrolled", "lost"},
    "admitted": {"enrolled", "lost"},
    "closed": set(),
}

_MUTABLE_FIELDS = {"status", "assigned_to", "source", "class_applying", "phone", "parent_name"}


def _session_kwargs(session) -> dict:
    return _txn_session_kwargs(session)


async def create_enquiry(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Create an admission enquiry. params: {student_name, parent_name?, phone?, class_applying?, source?}"""
    if not params.get("student_name"):
        raise EnquiryValidationError("student_name is required")
    enquiry = {
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "student_name": params.get("student_name"),
        "parent_name": params.get("parent_name"),
        "phone": params.get("phone"),
        "class_applying": params.get("class_applying", ""),
        "status": "new",
        "source": params.get("source", "walk_in"),
        "assigned_to": actor_ctx.user_id,
        "created_at": actor_ctx.now_iso(),
    }
    await db.enquiries.insert_one({**enquiry, "_id": enquiry["id"]}, **_session_kwargs(session))
    return {"enquiry": enquiry}


async def update_enquiry(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Update an enquiry / advance its pipeline stage.

    params: {enquiry_id, status?, assigned_to?, source?, class_applying?, phone?, parent_name?, note?}
    """
    enquiry_id = params.get("enquiry_id")
    if not enquiry_id:
        raise EnquiryValidationError("enquiry_id is required")
    bid = actor_ctx.branch_id
    existing = await db.enquiries.find_one(
        scoped_query({"id": enquiry_id}, branch_id=bid), {"_id": 0}, **_session_kwargs(session)
    )
    if not existing:
        raise EnquiryNotFoundError(enquiry_id)

    update = {k: v for k, v in params.items() if k in _MUTABLE_FIELDS and v is not None}
    new_status = update.get("status")
    if new_status and new_status != existing.get("status"):
        current = existing.get("status", "new")
        # EC-11.2: owner moves stages freely, except reverting an enrolled enquiry
        # that already has a linked student record.
        if actor_ctx.role == "owner":
            if existing.get("status") == "enrolled":
                linked_student = await db.students.find_one(
                    scoped_query({"enquiry_id": enquiry_id}, branch_id=bid), **_session_kwargs(session)
                )
                if linked_student:
                    raise EnquiryConflictError(
                        "Cannot revert enrolled enquiry — student record exists. Delete the student record first."
                    )
        elif new_status not in ALLOWED_TRANSITIONS.get(current, set()):
            raise EnquiryValidationError(f"Invalid enquiry transition from {current} to {new_status}")

    if params.get("note") or new_status:
        await db.enquiries.update_one(
            scoped_query({"id": enquiry_id}, branch_id=bid),
            {"$push": {"timeline": {
                "id": str(uuid.uuid4()),
                "author_id": actor_ctx.user_id,
                "from_status": existing.get("status"),
                "to_status": new_status or existing.get("status"),
                "note": params.get("note", ""),
                "created_at": actor_ctx.now_iso(),
            }}},
            **_session_kwargs(session),
        )
    update["updated_at"] = actor_ctx.now_iso()
    await db.enquiries.update_one(
        scoped_query({"id": enquiry_id}, branch_id=bid), {"$set": update}, **_session_kwargs(session)
    )
    updated = await db.enquiries.find_one(
        scoped_query({"id": enquiry_id}, branch_id=bid), {"_id": 0}, **_session_kwargs(session)
    )
    return {"enquiry": updated}
