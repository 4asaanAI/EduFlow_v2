"""R2-18 - undo your own change, on the same day.

Lalit types the school's day-to-day data all day and, by decision 4 of 2026-08-10, he
cannot delete anything. He will make mistakes. So he and Sonu get a way to put back what
they themselves changed, today. Anything older, or anybody else's change, goes to Adesh.

--------------------------------------------------------------------------------
Why this refuses more than it accepts, on purpose
--------------------------------------------------------------------------------

The plan said an undo is "a write-back of the previous value", because audit rows carry
``changes`` in the shape ``{field: {"previous": …, "new": …}}``. It also said to verify
that shape before designing around it. Verifying it found **at least eight different
shapes** across the write paths, and most of them cannot be reversed at all:

    {field: {"previous": …, "new": …}}          reversible - this is the one
    {"deleted": {…the whole document…}}          a restore, not an undo
    {"created": {…the whole document…}}          undoing it means deleting
    {"count_marked": 41, "date": …}              a summary. No before-value exists.
    {…the update dict as it was applied…}        new values only, no previous
    {"applied": {…}} / {"import_batch": …}       neither shape
    {"previous_state": {"previous": …}}          nested one level deeper

An undo written against an assumed shape would appear to work and silently do nothing on
most of those paths, which is worse than having no undo at all: the person believes the
mistake is fixed and walks away. So this module **reads the row and decides**, and when
it cannot honestly reverse something it says so in a sentence a person can act on.

It is deliberately narrow:

* only the person who made the change,
* only today,
* only the field/previous/new shape,
* only a student or staff record - the two things Lalit and Sonu type,
* never a field that carries money, an enrolment decision or a login,
* and an undo writes its OWN audit row, because reversing a change is itself a change
  and it has to appear in Aman's digest beside the original.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from services import audit_changes
from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_query


class UndoNotFoundError(Exception):
    """No such audit entry within the caller's scope → HTTP 404."""


class UndoRefusedError(Exception):
    """The change exists and cannot be undone. Carries a reason for a person."""


# The two records these two people type, and every name the platform's audit rows use
# for them. Deliberately not "anything with an audit row": an undo that can write back
# to any collection is a general-purpose write tool wearing a friendly name.
#
# The singular forms are not tidiness. `student_service` and `staff_service` write
# `entity_type: "student"` and `"staff"`, while the collections are `students` and
# `staff` - so an undo that matched only the collection names refused every real edit
# on the platform while passing its own tests, which used the plural. The lookup below
# is what makes the feature work rather than merely refuse safely.
_COLLECTION_BY_ENTITY = {
    "student": "students",
    "students": "students",
    "staff": "staff",
    "staff_member": "staff",
}
UNDOABLE_COLLECTIONS = set(_COLLECTION_BY_ENTITY)


def target_collection(entry: dict) -> str:
    """Which collection this audit row's record actually lives in, or "" if not ours."""
    for key in ("collection", "entity_type"):
        name = str(entry.get(key) or "").strip().lower()
        if name in _COLLECTION_BY_ENTITY:
            return _COLLECTION_BY_ENTITY[name]
    return ""

# Fields an undo will never write back, whatever the audit row says. Each is somebody
# else's decision, and a mistyped name is not a reason to reopen it.
#
# `fees`, `fee_*`, `salary`  - money. Decision 1: the management head never even sees
#                              these, so he certainly does not restore one.
# `status`, `is_active`, `enrolment_*` - whether a child is on the roll. Decision 4 puts
#                              that with the owner and the principal.
# `username`, `password*`, `role`, `sub_category` - who somebody is and what they may do.
# `rte_place`, `concessions`  - R2 audit, 2026-08-12. Both decide what a family is
#                              billed, and a Right to Education place decides whether
#                              they are billed at all. They are money by any reading, and
#                              they are also now the only writes that RE-WORK bills
#                              already raised; putting the field back would leave those
#                              re-worked bills describing a rule that no longer applies.
#                              Change them the way they were set, on the child's record
#                              or through Flo, which re-works the bills to match.
PROTECTED_FIELDS = {
    "fees", "fee_status", "fee_snapshot", "fee_structure_id", "salary", "amount",
    "rte_place", "concessions", "siblings",
    "status", "is_active", "enrolment_state", "enrolment_status",
    "username", "password", "password_hash", "role", "sub_category",
    "schoolId", "branch_id", "id", "_id",
}

# Actions whose audit rows describe something other than a field edit, so there is no
# previous value to put back.
#
# `import` is deliberately NOT here any more. A spreadsheet import is the one thing Lalit
# does in bulk and the most likely to need putting back, and since 2026-08-11 it records
# what each field held before it ran, so it can be. What is left are the three that
# genuinely cannot be reversed by writing a value back: creating a record (undoing that
# means deleting, which decision 4 keeps with the owner and the principal), removing one,
# and erasing one.
NON_FIELD_ACTIONS = {"delete", "erase", "create"}


def _is_reversible_shape(changes: Any) -> bool:
    """Does this ``changes`` value actually carry a before AND an after per field?

    R4-1: this used to hand-check one shape, ``{field: {"previous", "new"}}``, and refuse
    everything else - including two shapes that DO carry a before-value in different
    words (``{"before":…, "after":…}`` and the nested ``previous_state`` form). So it
    refused changes it could honestly have reversed, and a person was sent to the
    principal for no reason.

    It now asks ``audit_changes``, which reads every shape the platform has ever written
    and, crucially, reports a field whose earlier value was NEVER RECORDED as
    irreversible rather than as one that used to be empty. Writing an unrecorded
    before-value back would erase a real value while reporting success - the single most
    damaging thing an undo could do - so widening the reader does not widen the risk.
    """
    return bool(audit_changes.reversible_fields(changes))


def _same_day(created_at: Any, now: datetime) -> bool:
    """Was this written today?

    Audit timestamps are UTC-aware (L2). The school is in Uttar Pradesh, so "today" for
    a person there is not the same window as "today" in UTC: a change made at 3am IST is
    the previous UTC day, and an undo that refused it would look broken to the person
    who had just made it. The comparison is therefore done in India Standard Time,
    which is what "the same day" means to everyone using this.
    """
    if not created_at:
        return False
    try:
        stamp = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    ist_offset = 5.5 * 3600
    local_stamp = stamp.timestamp() + ist_offset
    local_now = now.timestamp() + ist_offset
    return int(local_stamp // 86400) == int(local_now // 86400)


def explain_refusal(entry: dict, actor_ctx: ActorContext, now: datetime) -> str:
    """Why this change cannot be undone, in words a person can act on. "" means it can.

    The order matters: the first true sentence is the one a person is told, so it goes
    from "this is not yours" outward to "this kind of change cannot be reversed".
    """
    if entry.get("changed_by") != actor_ctx.user_id:
        return (
            "This change was made by somebody else. Ask the principal to put it back."
        )
    if not _same_day(entry.get("created_at"), now):
        return (
            "This change was not made today. Same-day mistakes can be put back by the "
            "person who made them; anything older goes to the principal."
        )
    collection = target_collection(entry)
    if not collection:
        named = entry.get("collection") or entry.get("entity_type") or "something else"
        return (
            f"Only a student or staff record can be put back this way, and this change "
            f"was to {named}. Ask the principal."
        )
    action = str(entry.get("action") or "").lower()
    if any(word in action for word in NON_FIELD_ACTIONS):
        return (
            "This change added or removed a record rather than editing a field, so "
            "there is no earlier value to put back. Ask the principal."
        )
    changes = entry.get("changes")
    reversible = audit_changes.reversible_fields(changes)
    if not reversible:
        return (
            "The record of this change does not include what the value was before, so "
            "there is nothing to put back. Ask the principal to correct it by hand."
        )
    # Read the field names off the CANONICAL form, not the raw row. On a
    # `{"before":…, "after":…}` row the raw keys are the words "before" and "after",
    # so the old code compared those against PROTECTED_FIELDS and named them back to
    # the user in the refusal message.
    restorable = {f for f in reversible if f not in PROTECTED_FIELDS}
    if not restorable:
        blocked = ", ".join(sorted(reversible))
        return (
            f"This change is to {blocked}, which cannot be put back this way. Fees, "
            "salary, whether somebody is on the roll and login details are the owner's "
            "and the principal's."
        )
    return ""


def undoable_fields(entry: dict) -> Dict[str, Any]:
    """The fields this undo would write back, and the value each would return to.

    Two filters, and both are load-bearing. ``audit_changes`` drops fields whose earlier
    value was never recorded, because putting None back would erase rather than restore.
    ``PROTECTED_FIELDS`` then drops money, enrolment and login fields, because those are
    somebody else's decision and a mistyped name is not a reason to reopen one.
    """
    restorable = audit_changes.reversible_fields(entry.get("changes") or {})
    return {
        field: previous
        for field, previous in restorable.items()
        if field not in PROTECTED_FIELDS
    }


def _user_from(actor_ctx: ActorContext) -> dict:
    """The shape `undo_scope` and the permission table expect."""
    return {
        "role": actor_ctx.role,
        "sub_category": actor_ctx.sub_category,
        "id": actor_ctx.user_id,
    }


def help_for(entry: dict) -> Dict[str, Any]:
    """R4-4: how to put this change back by hand, when the platform will not do it.

    Decision 4 is two halves and this is the larger one. Without it, everything outside
    the narrow automatic path gets "ask the principal", which throws away the before
    value the platform already holds and sends somebody who is fixing their own mistake
    to interrupt a colleague.
    """
    from services import undo_scope

    return undo_scope.guidance(entry)


async def list_my_undoable_changes(db, actor_ctx: ActorContext, limit: int = 20) -> dict:
    """Today's changes by this person, each marked as reversible or not, with a reason.

    Rows that cannot be undone are RETURNED, not filtered out. A person who has just
    made a mistake goes looking for it, and a list that quietly omits it teaches them
    the platform has forgotten what they did.
    """
    now = datetime.now(timezone.utc)
    rows = await db.audit_logs.find(
        scoped_query({"changed_by": actor_ctx.user_id}, branch_id=actor_ctx.branch_id),
        {"_id": 0},
    ).sort("created_at", -1).to_list(200)

    out = []
    for entry in rows:
        if not _same_day(entry.get("created_at"), now):
            continue
        reason = explain_refusal(entry, actor_ctx, now)
        out.append({
            "audit_id": entry.get("id"),
            "action": entry.get("action"),
            "entity_type": entry.get("entity_type") or entry.get("collection"),
            "entity_id": entry.get("entity_id"),
            "created_at": entry.get("created_at"),
            "can_undo": not reason,
            "reason": reason,
            "would_restore": undoable_fields(entry) if not reason else {},
            # R4-4 / decision 4: where the platform will not reverse it, say how to do
            # it by hand. Attached to the REFUSED rows specifically, because those are
            # the ones a person is stuck on and the only ones this can help with.
            "how_to_undo_by_hand": help_for(entry) if reason else None,
        })
        if len(out) >= limit:
            break
    return {"changes": out, "count": len(out)}


async def undo_change(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Put back one of your own changes from today. params: {audit_id}"""
    audit_id = str(params.get("audit_id") or "").strip()
    if not audit_id:
        raise UndoRefusedError("audit_id is required")

    bid = actor_ctx.branch_id
    entry = await db.audit_logs.find_one(scoped_query({"id": audit_id}, branch_id=bid), {"_id": 0})
    if not entry:
        raise UndoNotFoundError(audit_id)

    now = datetime.now(timezone.utc)
    refusal = explain_refusal(entry, actor_ctx, now)
    if refusal:
        raise UndoRefusedError(refusal)

    restore = undoable_fields(entry)
    if not restore:
        raise UndoRefusedError(
            "There is nothing in this change that can be put back this way."
        )

    collection = target_collection(entry)
    entity_id = entry.get("entity_id")
    target = getattr(db, collection)
    current = await target.find_one(scoped_query({"id": entity_id}, branch_id=bid), {"_id": 0})
    if not current:
        raise UndoRefusedError(
            "That record no longer exists, so there is nothing to put the value back on."
        )

    await target.update_one(
        scoped_query({"id": entity_id}, branch_id=bid), {"$set": restore}
    )

    # An undo is itself a change and has to be visible as one. Without this row, Aman's
    # digest would show the mistake and not the correction, which is the more misleading
    # of the two halves to be missing.
    await write_audit_doc(
        db,
        {
            "id": str(uuid.uuid4()),
            "entity_type": collection,
            "collection": collection,
            "entity_id": entity_id,
            "action": "undo",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {
                field: {"previous": current.get(field), "new": value}
                for field, value in restore.items()
            },
            "reason": f"Same-day undo of {entry.get('action')} ({audit_id})",
            "undo_of": audit_id,
            "created_at": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=bid or "",
    )
    return {
        "undone": True,
        "audit_id": audit_id,
        "entity_type": collection,
        "entity_id": entity_id,
        "restored": restore,
    }
