"""One registry of every kind of approval on this platform.

Approvals workflow, 2026-08-15. Abhimanyu's decisions 21 to 31 of that date.

**Why this exists.** R3-2 gave the transport head things he must ask permission for, and
then a check found there was no screen anywhere for the school's owner or the principal to
approve or reject anything. `getApprovalRequests` and `decideApprovalRequest` sat in the
frontend and nothing called them. The platform could ask for permission and could not
receive it.

**What this is, and what it deliberately is NOT.** It is one shared way of asking six
existing, working approval systems the same four questions: what is waiting on me, what
have I raised, may this person decide this, and decide it. It is NOT a new store that the
six were migrated into. Nothing about how a certificate or a leave request is recorded has
changed. Moving six live systems' data onto a new shape is where an access accident would
come from, and the gain would have been tidiness.

**The rule that makes this safe, and it must not be relaxed.** A kind's `decide` calls the
SAME service function its own screen calls, and its `may_decide` mirrors the gate its own
route already carries. The registry never invents a permission. So the worst a mistake in
here can do is HIDE a row from somebody entitled to see it, which is visible and
complainable. It can never hand somebody a decision they do not hold, because the service
underneath refuses them regardless.

**Adding a seventh kind is one entry in `APPROVAL_KINDS`.** The screen, the counts, the
notifications and Flo all read this dictionary and none of them names a kind. That was
Abhimanyu's explicit requirement: "even if we plan or make any more approvals in future
then those should also be covered like these 6 itself automatically."

**Every kind keeps the approvers it has today** (decision 22). Nobody gains the ability to
approve anything they could not approve on 2026-08-15. Cover for absence, which is what
Abhimanyu actually wants from flattening the rules, is a separate later item and is NOT
built here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from middleware.auth import is_owner_or_principal
from tenant import scoped_filter, scoped_query


class ApprovalKindUnknown(Exception):
    """No such kind of approval -> HTTP 404."""


class ApprovalNotVisible(Exception):
    """This person may not see or decide this record -> HTTP 403."""


# How long a request may sit before the screen calls it overdue. Nothing is ever decided
# automatically (decision 28); this only changes how a row is drawn. Two working days is
# the school's own rhythm and is deliberately generous, because a flag that fires too
# early is one people stop reading.
DEFAULT_OVERDUE_HOURS = 48


def _parse(value: Any) -> Optional[datetime]:
    """Read one of the several date shapes this codebase has written over the years."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _hours_waiting(raised_at: Any, now: Optional[datetime] = None) -> Optional[float]:
    started = _parse(raised_at)
    if started is None:
        return None
    reference = now or datetime.now(timezone.utc)
    # Rows written before this platform settled on UTC carry a naive local timestamp.
    # Comparing the two raises, so the naive one is read as if it were already UTC.
    # That can be out by the offset and never by a day, which is inside the tolerance
    # of a 48-hour flag.
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return (reference - started).total_seconds() / 3600.0


# ── The six kinds ─────────────────────────────────────────────────────────────
#
# Each entry answers, in one place: what it is called in ordinary words, who may decide
# it and in how many steps, who is in its conversation by default, and what agreeing to
# it actually does.


def _may_decide_general(user: dict, doc: dict) -> bool:
    """Mirrors `approvals_service.decide_approval_request`, which is where it is enforced.

    The owner decides any request. The principal decides only those routed to both of
    them. Written out here so the QUEUE shows a principal exactly the rows they can act
    on; the refusal itself still comes from the service.
    """
    if user.get("role") == "owner":
        return True
    if user.get("role") == "admin" and user.get("sub_category") == "principal":
        return doc.get("routing") == "owner_and_principal"
    return False


async def _decide_general(db, actor_ctx, doc, decision, reason):
    from services.approvals_service import decide_approval_request

    return await decide_approval_request(db, actor_ctx, {
        "approval_id": doc.get("id"),
        "status": "approved" if decision == "approve" else "rejected",
        "reason": reason,
    })


async def _decide_certificate(db, actor_ctx, doc, decision, reason):
    from services.certificate_service import approve_certificate, reject_certificate

    if decision == "approve":
        return await approve_certificate(db, actor_ctx, {"cert_id": doc.get("id")})
    return await reject_certificate(
        db, actor_ctx, {"cert_id": doc.get("id"), "reason": reason}
    )


async def _decide_staff_leave(db, actor_ctx, doc, decision, reason):
    from services.leave_service import decide_leave_request

    return await decide_leave_request(db, actor_ctx, {
        "leave_id": doc.get("id"),
        "status": "approved" if decision == "approve" else "rejected",
        "reason": reason,
    })


async def _decide_announcement(db, actor_ctx, doc, decision, reason):
    from services.announcement_service import decide_announcement

    return await decide_announcement(db, actor_ctx, {
        "announcement_id": doc.get("id"),
        "decision": decision,
        "reason": reason,
    })


def _may_decide_profile_change(user: dict, doc: dict) -> bool:
    """Owner or principal, and never your own.

    The second half is not a nicety. A principal is an administrator, so without it they
    could ask for a change to their own record and wave it through in one click, which is
    the exact self-editing the feature exists to prevent.
    """
    if not is_owner_or_principal(user):
        return False
    return doc.get("user_id") != user.get("id")


async def _decide_profile_change(db, actor_ctx, doc, decision, reason):
    from services.profile_change_service import decide_profile_change

    return await decide_profile_change(db, actor_ctx, {
        "request_id": doc.get("id"),
        "status": "approved" if decision == "approve" else "rejected",
        "rejection_reason": reason,
    })


async def _may_decide_student_leave(db, user: dict, doc: dict) -> bool:
    """The only two-step kind on the platform, and the only one a teacher decides.

    A class teacher decides the first step for their own class. The owner or the
    principal decides either step. A teacher who is not that child's class teacher
    decides nothing, and a teacher may not touch a request that has already moved up to
    the principal.

    This is a re-statement of `student_leave_service.decide_request`, which remains the
    thing that actually refuses. It is async because "is this your class" is a database
    question, not a property of the token.
    """
    if is_owner_or_principal(user):
        return True
    if user.get("role") != "teacher":
        return False
    if doc.get("status") != "pending_teacher":
        return False
    branch_id = user.get("branch_id")
    staff = await db.staff.find_one(
        scoped_query({"user_id": user.get("id")}, branch_id=branch_id), {"_id": 0, "id": 1}
    )
    if not staff:
        return False
    class_doc = await db.classes.find_one(
        scoped_query({"id": doc.get("class_id")}, branch_id=branch_id),
        {"_id": 0, "class_teacher_id": 1},
    )
    return bool(class_doc and class_doc.get("class_teacher_id") == staff.get("id"))


async def _decide_student_leave(db, actor_ctx, doc, decision, reason):
    from services.student_leave_service import decide_request

    return await decide_request(db, actor_ctx, doc.get("id"), {
        "decision": decision,
        "note": reason,
    })


"""Role shorthands for "who is in this conversation by default" (decision 26)."""
OWNER = {"role": "owner"}
PRINCIPAL = {"role": "admin", "sub_category": "principal"}
ACCOUNTANT_HEAD = {"role": "admin", "sub_category": "accountant"}


def _general_extra_roles(doc: dict) -> tuple:
    """A repair cost includes the accountant head, because he is the one who pays it.

    Abhimanyu's own example of what "a default per kind" means. It reads off the action
    the request carries rather than off who raised it, so the same rule holds whoever
    asks for the money.
    """
    action = (doc.get("pending_action") or {}).get("kind")
    return (ACCOUNTANT_HEAD,) if action == "agree_a_repair_cost" else ()


async def _student_leave_extra_people(db, doc: dict, branch_id) -> List[str]:
    """The child's class teacher, who decides the first step and is not found by role."""
    class_doc = await db.classes.find_one(
        scoped_query({"id": doc.get("class_id")}, branch_id=branch_id),
        {"_id": 0, "class_teacher_id": 1},
    )
    if not class_doc or not class_doc.get("class_teacher_id"):
        return []
    staff = await db.staff.find_one(
        scoped_query({"id": class_doc["class_teacher_id"]}, branch_id=branch_id),
        {"_id": 0, "user_id": 1},
    )
    return [staff["user_id"]] if staff and staff.get("user_id") else []


def _dates(doc: dict) -> str:
    start, end = doc.get("start_date"), doc.get("end_date")
    if not start and isinstance(doc.get("date_range"), dict):
        start, end = doc["date_range"].get("start"), doc["date_range"].get("end")
    if start and end and start != end:
        return f"{start} to {end}"
    return start or end or ""


APPROVAL_KINDS: Dict[str, Dict[str, Any]] = {
    # 1. The general request. This is the one the transport head's deletions and repair
    #    costs arrive as, and the only kind where approving can CARRY OUT the action.
    "general": {
        "label": "Approval request",
        "collection": "approval_requests",
        "pending_statuses": ("pending",),
        "raised_by_field": "submitted_by",
        "raised_at_field": "submitted_at",
        "who_decides": "The school's owner, or the principal when it is sent to both",
        "steps": 1,
        "may_decide": _may_decide_general,
        "decide": _decide_general,
        "title": lambda doc: doc.get("title") or "Approval request",
        "detail": lambda doc: doc.get("description") or "",
        "default_roles": (OWNER, PRINCIPAL),
        "extra_roles": _general_extra_roles,
        # Decision 27: the raiser may change a pending request and the change is
        # recorded in the conversation. Only the general kind has fields whose
        # meaning is "what I am asking for". Editing a certificate or an announcement
        # is a different feature with its own screen, so those kinds honestly refuse.
        "editable_fields": ("title", "description", "estimated_impact", "note"),
        # Raising one from the approvals screen, 2026-08-15 (Abhimanyu).
        #
        # `createApprovalRequest` sat in the frontend uncalled, which is the exact state
        # the two DECIDE functions were in before this work: the platform could receive
        # permission and, for a general request, nobody could ask for it except through
        # Flo. Abhimanyu's own example, Sonu raising a salary approval, had no button.
        #
        # Only the general kind is raisable here, and that is deliberate rather than an
        # omission. A certificate is asked for on the certificates screen, where the
        # child and the type of certificate are chosen; a leave request is asked for on
        # the leave screen. Putting those on this screen would be a second way to create
        # the same record, and two ways to create one thing is how they drift apart.
        "raisable_here": True,
        # Mirrors `require_role("admin")` on POST /api/operations/approval-requests,
        # which is the route the screen calls. It is why the school's owner does not see
        # the control: decision 25 says Aman and Adesh approve, they do not raise.
        "may_raise": lambda user: user.get("role") == "admin",
    },
    # 2. Certificates. Created by the accountant or management head, issued by the owner
    #    or the principal.
    "certificate": {
        "label": "Certificate",
        "collection": "certificates",
        "pending_statuses": ("pending_approval",),
        "raised_by_field": "requested_by",
        "raised_at_field": "created_at",
        "who_decides": "The school's owner or the principal",
        "steps": 1,
        "may_decide": lambda user, doc: is_owner_or_principal(user),
        "decide": _decide_certificate,
        "title": lambda doc: (
            f"{str(doc.get('cert_type') or 'certificate').replace('_', ' ').title()}"
            + (f" for {doc['student_name']}" if doc.get("student_name") else "")
        ),
        "detail": lambda doc: f"Serial number {doc.get('serial_number') or 'not yet given'}",
        "default_roles": (OWNER, PRINCIPAL),
    },
    # 3. A colleague's leave.
    "staff_leave": {
        "label": "Staff leave",
        "collection": "leave_requests",
        "pending_statuses": ("pending",),
        "raised_by_field": "user_id",
        "raised_at_field": "applied_at",
        "who_decides": "The school's owner or the principal",
        "steps": 1,
        "may_decide": lambda user, doc: is_owner_or_principal(user),
        "decide": _decide_staff_leave,
        "default_roles": (OWNER, PRINCIPAL),
        "title": lambda doc: (
            f"{str(doc.get('leave_type') or 'Leave').replace('_', ' ').title()} leave"
            + (f", {_dates(doc)}" if _dates(doc) else "")
        ),
        "detail": lambda doc: doc.get("reason") or "",
    },
    # 4. Announcements.
    #
    # The plan's table said this one is the principal's alone. The code has always let
    # the owner or the principal decide it, and decision 22 says every kind keeps the
    # approvers it has today, so it keeps both. Confirmed by Abhimanyu on 2026-08-15
    # after the difference was pointed out; the plan's table is the thing that was wrong.
    "announcement": {
        "label": "Announcement",
        "collection": "announcements",
        "pending_statuses": ("pending_approval",),
        "raised_by_field": "created_by",
        "raised_at_field": "created_at",
        "who_decides": "The school's owner or the principal",
        "steps": 1,
        "may_decide": lambda user, doc: is_owner_or_principal(user),
        "decide": _decide_announcement,
        "default_roles": (OWNER, PRINCIPAL),
        "title": lambda doc: doc.get("title") or "Announcement",
        "detail": lambda doc: doc.get("content") or doc.get("message") or "",
    },
    # 5. A colleague correcting their own details. Approving APPLIES the change.
    "staff_profile_change": {
        "label": "Correction to staff details",
        "collection": "profile_change_requests",
        "pending_statuses": ("pending",),
        "raised_by_field": "user_id",
        "raised_at_field": "created_at",
        "who_decides": "The school's owner or the principal, and never their own",
        "steps": 1,
        "may_decide": _may_decide_profile_change,
        "decide": _decide_profile_change,
        "default_roles": (OWNER, PRINCIPAL),
        "title": lambda doc: (
            f"Correction to {doc.get('staff_name') or 'a colleague'}'s details"
        ),
        "detail": lambda doc: ", ".join(
            f"{field.replace('_', ' ')} to {value}"
            for field, value in (doc.get("requested") or {}).items()
        ),
        "applies_the_change_on_approval": True,
    },
    # 6. A child's leave. The ONLY two-step kind, and the only one a teacher decides.
    "student_leave": {
        "label": "Student leave",
        "collection": "student_leave_requests",
        "pending_statuses": ("pending_teacher", "pending_principal"),
        "raised_by_field": "submitted_by",
        "raised_at_field": "created_at",
        "who_decides": "The class teacher first, then the principal for a longer absence",
        "steps": 2,
        "may_decide": _may_decide_student_leave,
        "decide": _decide_student_leave,
        "default_roles": (PRINCIPAL,),
        "extra_people": _student_leave_extra_people,
        "title": lambda doc: (
            f"Leave for {doc.get('student_name') or 'a child'}"
            + (f", {_dates(doc)}" if _dates(doc) else "")
        ),
        "detail": lambda doc: doc.get("reason") or "",
        "step_label": lambda doc: (
            "Waiting for the class teacher" if doc.get("status") == "pending_teacher"
            else "Waiting for the principal"
        ),
    },
}


def kind_or_raise(kind: str) -> Dict[str, Any]:
    entry = APPROVAL_KINDS.get(kind)
    if not entry:
        raise ApprovalKindUnknown(
            f"'{kind}' is not a kind of approval this platform knows about."
        )
    return entry


async def may_decide(db, kind: str, user: dict, doc: dict) -> bool:
    """May this person decide this record? Never widens anything; see the module note."""
    entry = kind_or_raise(kind)
    check = entry["may_decide"]
    if kind == "student_leave":
        return await check(db, user, doc)
    return bool(check(user, doc))


def to_card(kind: str, doc: dict, *, now: Optional[datetime] = None) -> dict:
    """The one shape all six become on the screen, in the counts and in Flo's answers.

    Everything a person reads comes from here, so a new kind is drawn correctly the day
    it is added rather than needing the screen changed too.
    """
    entry = kind_or_raise(kind)
    raised_at = doc.get(entry["raised_at_field"])
    waiting = _hours_waiting(raised_at, now)
    is_pending = doc.get("status") in entry["pending_statuses"]
    step_label = entry.get("step_label")
    card = {
        "kind": kind,
        "kind_label": entry["label"],
        "id": doc.get("id"),
        "title": entry["title"](doc),
        "detail": entry["detail"](doc),
        "status": doc.get("status"),
        "is_pending": is_pending,
        "raised_by": doc.get(entry["raised_by_field"]),
        "raised_at": raised_at,
        "who_decides": entry["who_decides"],
        "steps": entry["steps"],
        "step_label": (
            step_label(doc) if step_label
            else (entry["who_decides"] if is_pending else None)
        ),
        "hours_waiting": None if waiting is None else round(waiting, 1),
        # Decision 28: overdue is SHOWN and nothing is ever decided automatically.
        "overdue": bool(is_pending and waiting is not None and waiting > DEFAULT_OVERDUE_HOURS),
        "decided_by": doc.get("decided_by") or doc.get("approved_by") or doc.get("issued_by"),
        "decided_at": doc.get("decided_at") or doc.get("approved_at") or doc.get("issued_date"),
        "decision_reason": (
            doc.get("decision_reason") or doc.get("rejection_reason") or doc.get("reason_rejected")
        ),
    }
    # R3-2, 2026-08-15: say out loud when agreeing to something CARRIES IT OUT, so a
    # person can tell "I agree with this" from "do this now".
    if doc.get("approval_carries_out_the_action"):
        card["carries_out_the_action"] = True
        card["what_approving_does"] = doc.get("what_approving_does")
    elif entry.get("applies_the_change_on_approval"):
        card["carries_out_the_action"] = True
        card["what_approving_does"] = (
            "Agreeing to this CHANGES the colleague's details straight away."
        )
    return card


def _collection(db, entry: dict):
    # `getattr` rather than `db[...]`, because the stand-in database used by the tests
    # exposes its collections as attributes only. Reaching for a subscript would have
    # worked in production and failed the whole suite, which is the least useful order
    # to find that out in.
    return getattr(db, entry["collection"])


async def _fetch(db, entry: dict, query: dict, branch_id: Optional[str], limit: int) -> List[dict]:
    return await _collection(db, entry).find(
        scoped_query(query, branch_id=branch_id), {"_id": 0}
    ).to_list(limit)


async def waiting_on(db, user: dict, *, kind: Optional[str] = None, limit: int = 200) -> List[dict]:
    """Everything across every kind that this person can decide right now.

    One question, every kind, both for the screen and for Flo when somebody asks "are
    there any approvals pending for me?" (decision 30).
    """
    kinds = [kind] if kind else list(APPROVAL_KINDS)
    out: List[dict] = []
    for name in kinds:
        entry = kind_or_raise(name)
        docs = await _fetch(
            db, entry, {"status": {"$in": list(entry["pending_statuses"])}},
            user.get("branch_id"), limit,
        )
        for doc in docs:
            if await may_decide(db, name, user, doc):
                out.append(to_card(name, doc))
    out.sort(key=lambda card: card.get("raised_at") or "", reverse=True)
    return out


async def raised_by(db, user: dict, *, kind: Optional[str] = None, limit: int = 200) -> List[dict]:
    """Everything this person has asked for, decided or not.

    The other direction of decision 30: what am I waiting on somebody else for. Also
    what makes the screen honest for a department head, who raises far more than he
    decides.
    """
    kinds = [kind] if kind else list(APPROVAL_KINDS)
    out: List[dict] = []
    for name in kinds:
        entry = kind_or_raise(name)
        docs = await _fetch(
            db, entry, {entry["raised_by_field"]: user.get("id")}, user.get("branch_id"), limit,
        )
        out.extend(to_card(name, doc) for doc in docs)
    out.sort(key=lambda card: card.get("raised_at") or "", reverse=True)
    return out


async def load(db, kind: str, record_id: str, school_id: str) -> dict:
    entry = kind_or_raise(kind)
    # branch-scope: intentional - pinned by a unique id, so a branch filter could only
    # turn a real row into a false 404.
    doc = await _collection(db, entry).find_one(
        scoped_filter({"id": record_id}, school_id), {"_id": 0}
    )
    if not doc:
        raise ApprovalKindUnknown("That request no longer exists.")
    return doc


async def decide(db, actor_ctx, user: dict, kind: str, record_id: str,
                 decision: str, reason: str) -> dict:
    """Approve or reject, whatever the kind, through that kind's own service.

    The gate is applied here AND again inside the service. That is deliberate
    belt-and-braces: this one gives a person an honest refusal instead of a confusing
    error, and the service's one is the one that actually holds the line.
    """
    entry = kind_or_raise(kind)
    if decision not in ("approve", "reject"):
        raise ApprovalNotVisible("A decision must be approve or reject.")
    doc = await load(db, kind, record_id, actor_ctx.school_id)
    if not await may_decide(db, kind, user, doc):
        raise ApprovalNotVisible(
            "You are not one of the people who decides this kind of request."
        )
    if doc.get("status") not in entry["pending_statuses"]:
        raise ApprovalNotVisible("That request has already been decided.")
    return await entry["decide"](db, actor_ctx, doc, decision, reason)
