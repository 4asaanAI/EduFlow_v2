"""Admission-enquiry domain service - single shared write path for enquiry
creation and pipeline-stage updates (AI Layer Hardening, AD7 - drift-gate
remediation for the `create_enquiry` / `update_enquiry_status` AI tools).

Both the REST routes (`POST/PATCH /api/ops/enquiries*`) and the AI tools call
these functions, so an AI enquiry write is byte-identical to a panel write:
same field set, same stage-transition guard, same timeline entries.

**Parity decision (case-by-case, canonical = REST):** the legacy AI tool wrote
extra fields (`notes`, `created_by`, `updated_at`) and skipped the transition
guard entirely - an AI call could jump an enquiry to any stage. Both now share
the REST behavior: owner may move stages freely (except reverting `enrolled`
with a linked student), everyone else follows `ALLOWED_TRANSITIONS`.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import uuid

from services import audit_changes
from services.actor_context import ActorContext
from services.audit_service import write_audit
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import scoped_query


class EnquiryValidationError(Exception):
    """Invalid input or stage transition → HTTP 400."""


class EnquiryNotFoundError(Exception):
    """Unknown enquiry id within the caller's scope → HTTP 404."""


class EnquiryConflictError(Exception):
    """Reverting an enrolled enquiry with a linked student record → HTTP 409."""


# A2: `enrolled` is NOT a stage anybody picks. It appears on an enquiry only when that
# family's admission application creates the child record, which `enroll_application`
# does in one transaction and writes to the enquiry itself. Before this, `fee_paid` to
# `enrolled` was an ordinary move with no check that a child existed, so the funnel could
# report an enrolment that had never happened and nobody looking could tell the
# difference. `enrolled` stays a key here because enquiries are already in that state.
ENROLLED = "enrolled"

# The one refusal, said the same way wherever a person tries it: a screen, the REST API,
# the CRM lead route, or Flo.
ENROLLED_IS_NOT_A_CHOICE = (
    "An enquiry cannot be moved to enrolled by hand. A family becomes enrolled when "
    "their admission application creates the child's record. Start an application for "
    "this enquiry and enrol from there."
)

# Aligned with frontend pipeline stages (+ legacy backward-compat stages).
ALLOWED_TRANSITIONS = {
    "new": {"contacted", "lost"},
    "contacted": {"visit_scheduled", "lost"},
    "visit_scheduled": {"visited", "lost"},
    "visited": {"documents_submitted", "lost"},
    "documents_submitted": {"fee_paid", "lost"},
    "fee_paid": {"lost"},
    "enrolled": {"lost"},
    "lost": set(),
    "applied": {"admitted", "lost"},
    "admitted": {"lost"},
    "closed": set(),
}

# A3. The school's own admission form asks for the mother and the father separately, and
# their records fill both in on essentially every enquiry. The platform held ONE
# `parent_name`, so starting an application carried one of the two parents across with no
# way to tell which. It also asks for the child's date of birth, gender and previous
# school at enquiry time, all of which were then retyped onto the application.
#
# `parent_name` STAYS. It is the contact the office deals with, it is what messaging and
# every export already read, and 102 existing records carry it. The new fields sit
# alongside it rather than replacing it.
#
# Deliberately NOT added: Aadhaar, religion, category and family income. They are on the
# paper form and are effectively never filled in, and storing them is a decision about a
# duty of care, not a form-matching exercise. See
# `_bmad-output/implementation-artifacts/admissions-funnel/the-schools-own-admission-form-2026-08-14.md`.
FAMILY_FIELDS = ("mother_name", "father_name", "dob", "gender", "previous_school")

_MUTABLE_FIELDS = {
    "status", "assigned_to", "source", "class_applying", "phone", "parent_name",
    *FAMILY_FIELDS,
}


def _session_kwargs(session) -> dict:
    return _txn_session_kwargs(session)


async def create_enquiry(db, actor_ctx: ActorContext, params: dict, *, session=None,
                         extra_fields: dict | None = None) -> dict:
    """Create an admission enquiry.

    params: {student_name, parent_name?, phone?, class_applying?, source?,
             mother_name?, father_name?, dob?, gender?, previous_school?}
    """
    if not params.get("student_name"):
        raise EnquiryValidationError("student_name is required")
    enquiry = {
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id,
        "student_name": params.get("student_name"),
        "parent_name": params.get("parent_name"),
        "phone": params.get("phone"),
        "class_applying": params.get("class_applying", ""),
        "status": "new",
        "source": params.get("source", "walk_in"),
        # A3. Stored as None when not given rather than left off the document, so a
        # record that was never asked for the mother's name looks different from a
        # record written before these fields existed.
        **{field: params.get(field) or None for field in FAMILY_FIELDS},
        "assigned_to": actor_ctx.user_id,
        "created_at": actor_ctx.now_iso(),
        **(extra_fields or {}),
    }
    await db.enquiries.insert_one({**enquiry, "_id": enquiry["id"]}, **_session_kwargs(session))
    # R4-2: a family enquiring about a place is the first record the school holds about
    # a child, and it recorded nothing. When two people take the same call, or an
    # enquiry goes missing, there was no way to see who entered what.
    await write_audit(
        db,
        action="enquiry_create",
        entity_id=enquiry["id"],
        collection="enquiries",
        changed_by=actor_ctx.user_id or "",
        changed_by_role=actor_ctx.role or "",
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id or "",
        changes=audit_changes.created(enquiry),
        reason=f"Enquiry for {enquiry.get('student_name')}",
    )
    return {"enquiry": enquiry}


async def update_enquiry(db, actor_ctx: ActorContext, params: dict, *, session=None,
                         extra_fields: dict | None = None) -> dict:
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
    update.update(extra_fields or {})
    new_status = update.get("status")
    if new_status and new_status != existing.get("status"):
        current = existing.get("status", "new")
        # A2. This sits ABOVE the owner branch on purpose. The owner may move an enquiry
        # anywhere else, but not here: an enrolment is a child on the roll, and no role
        # gets to assert one by typing.
        if new_status == ENROLLED:
            raise EnquiryValidationError(ENROLLED_IS_NOT_A_CHOICE)
        # EC-11.2: owner moves stages freely, except reverting an enrolled enquiry
        # that already has a linked student record.
        if actor_ctx.role == "owner":
            if existing.get("status") == "enrolled":
                linked_student = await db.students.find_one(
                    scoped_query({"enquiry_id": enquiry_id}, branch_id=bid), **_session_kwargs(session)
                )
                if linked_student:
                    raise EnquiryConflictError(
                        "Cannot revert enrolled enquiry - student record exists. Delete the student record first."
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
    # R4-2. `existing` was read at the top of this function, so this is one of the paths
    # that can honestly record what the enquiry said BEFORE the change, not only after.
    await write_audit(
        db,
        action="enquiry_update",
        entity_id=enquiry_id,
        collection="enquiries",
        changed_by=actor_ctx.user_id or "",
        changed_by_role=actor_ctx.role or "",
        school_id=actor_ctx.school_id,
        branch_id=bid or "",
        changes=audit_changes.edit(existing, update),
        reason=params.get("note") or "",
    )
    return {"enquiry": updated}
