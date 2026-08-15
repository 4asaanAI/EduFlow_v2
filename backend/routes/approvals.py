"""One approvals screen for the whole platform.

Approvals workflow, 2026-08-15. Every profile gets the same screen (decision 25); what
differs is what is on it, and that is decided by the registry rather than by this file.
Nothing here names a kind of approval, so a seventh kind appears on the screen, in the
counts and in Flo's answers the day it is added to `approval_registry.APPROVAL_KINDS`.

**Every route is signed-in-only and nothing else.** That is not a missing gate. Who may
see and decide a particular request is a question about that RECORD, not about a role, and
it is answered by the same code that answers it for the screens the six kinds already
have. A static role gate here would either lock out a class teacher who decides a child's
leave, or let somebody through to a queue that then has to refuse them row by row.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from middleware.auth import get_current_user
from services.actor_context import actor_ctx_from_user
from services import approval_registry as registry
from services import approval_thread_service as threads
from tenant import get_school_id, scoped_filter

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def _ctx(user: dict):
    return actor_ctx_from_user(user, school_id=get_school_id())


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, registry.ApprovalKindUnknown):
        return HTTPException(404, str(exc))
    if isinstance(exc, (registry.ApprovalNotVisible, threads.ThreadForbidden)):
        return HTTPException(403, str(exc))
    if isinstance(exc, threads.ThreadClosed):
        return HTTPException(409, str(exc))
    return HTTPException(400, str(exc))


@router.get("/kinds")
async def list_kinds(request: Request, user: dict = Depends(get_current_user)):
    """What kinds of approval exist, in ordinary words, for the screen's filter.

    Read from the registry so the filter can never offer a kind that does not exist, nor
    miss one that does.
    """
    return {"success": True, "data": [
        {
            "kind": name,
            "label": entry["label"],
            "who_decides": entry["who_decides"],
            "steps": entry["steps"],
            # Whether this person can ASK for one of these from this screen. Answered by
            # the server so the screen never has to hold its own idea of who may raise
            # what, which is how a control ends up offered to somebody the route refuses.
            "may_raise": bool(
                entry.get("raisable_here")
                and (entry.get("may_raise") or (lambda _u: False))(user)
            ),
        }
        for name, entry in registry.APPROVAL_KINDS.items()
    ]}


@router.get("/waiting-on-me")
async def waiting_on_me(request: Request, kind: str = None,
                        user: dict = Depends(get_current_user)):
    """Everything, of every kind, that this person can decide right now."""
    try:
        cards = await registry.waiting_on(get_db(), user, kind=kind)
    except registry.ApprovalKindUnknown as exc:
        raise _http(exc)
    return {"success": True, "data": cards, "meta": {
        "count": len(cards),
        "overdue": sum(1 for card in cards if card.get("overdue")),
    }}


@router.get("/raised-by-me")
async def raised_by_me(request: Request, kind: str = None,
                       user: dict = Depends(get_current_user)):
    """Everything this person has asked for, decided or not."""
    try:
        cards = await registry.raised_by(get_db(), user, kind=kind)
    except registry.ApprovalKindUnknown as exc:
        raise _http(exc)
    return {"success": True, "data": cards, "meta": {
        "count": len(cards),
        "still_waiting": sum(1 for card in cards if card.get("is_pending")),
    }}


@router.get("/{kind}/{record_id}")
async def read_one(kind: str, record_id: str, request: Request,
                   user: dict = Depends(get_current_user)):
    """One approval: the card, its conversation, and whether this person may decide it."""
    db = get_db()
    school_id = get_school_id()
    try:
        doc = await registry.load(db, kind, record_id, school_id)
        conversation = await threads.list_messages(
            db, user, kind, record_id, doc, school_id, user.get("branch_id")
        )
        can_decide = await registry.may_decide(db, kind, user, doc)
    except (registry.ApprovalKindUnknown, threads.ThreadForbidden) as exc:
        raise _http(exc)
    card = registry.to_card(kind, doc)
    thread = conversation["thread"]
    messages = await _name_the_attachments(db, conversation["messages"], school_id)
    return {"success": True, "data": {
        **card,
        "may_decide": can_decide,
        "may_reply": thread.get("status") == "open",
        "may_reopen": can_decide and thread.get("status") == "closed"
                      and thread.get("closed_decision") != "reject",
        "may_edit": bool(
            card.get("is_pending")
            and card.get("raised_by") == user.get("id")
            and registry.APPROVAL_KINDS[kind].get("editable_fields")
        ),
        "participants": thread.get("participants") or [],
        "conversation_status": thread.get("status"),
        "messages": messages,
    }}


async def _name_the_attachments(db, messages: list, school_id: str) -> list:
    """Give every attached file its NAME, so the screen can offer it as something to open.

    An attachment used to reach the screen as an id and nothing else, so the only honest
    thing the screen could draw was "2 attached". A count is not a document: the person
    deciding a repair cost could see that a quote existed and had no way to read it, which
    is the same shape as every other fault this release closed.

    **This grants nothing.** The file itself is still fetched one at a time through
    `/api/uploads/link/{file_id}`, which applies the ordinary file rules plus the narrow
    approvals rule, and a name is already visible to anybody who can see the message it
    hangs on. A file whose record has gone is named as missing rather than dropped, so a
    lost attachment cannot be mistaken for one that was never sent.
    """
    ids = sorted({
        file_id
        for message in messages
        for file_id in (message.get("attachments") or [])
    })
    if not ids:
        return messages
    rows = await db.file_uploads.find(
        # branch-scope: intentional - a file belongs to its uploader and the school, not
        # to a branch, and these ids came from messages this person may already read.
        scoped_filter({"id": {"$in": ids}}, school_id),
        {"_id": 0, "id": 1, "file_name": 1, "file_size_kb": 1},
    ).to_list(len(ids))
    by_id = {row["id"]: row for row in rows}
    return [
        {
            **message,
            "attachment_files": [
                {
                    "id": file_id,
                    "file_name": (by_id.get(file_id) or {}).get("file_name")
                    or "A file that is no longer stored",
                    "file_size_kb": (by_id.get(file_id) or {}).get("file_size_kb"),
                    "missing": file_id not in by_id,
                }
                for file_id in (message.get("attachments") or [])
            ],
        }
        for message in messages
    ]


@router.get("/{kind}/{record_id}/people")
async def people_to_bring_in(kind: str, record_id: str, request: Request,
                             user: dict = Depends(get_current_user)):
    """The colleagues who could be brought into THIS conversation, by name.

    Until this, "bring somebody in" asked for an account id, which is a string nobody at
    the school knows or could look up. A control that needs a value a person cannot
    obtain is the same as no control at all.

    **It is scoped to the record on purpose, not offered as a general staff directory.**
    Every approvals route is signed-in-only, deliberately, because who may see a request
    is a question about the RECORD. A flat list of colleagues on that gate would hand the
    school's staff list to any student or guardian with a login. So this refuses anybody
    who may not read this conversation, and it hands back nothing but a name and a job.

    **The list is the SAME question the staff room asks**, `_staff_contacts`: the login
    is active, the person is staff, and their release has landed. Nobody is offered who
    could not answer, which is the rule Abhimanyu set on 2026-08-14, and a profile
    switched on for its release appears here the same day with no change to this file.
    """
    from routes.messaging import _staff_contacts

    db = get_db()
    school_id = get_school_id()
    try:
        doc = await registry.load(db, kind, record_id, school_id)
        thread = await threads.ensure_thread(
            db, kind, record_id, doc, school_id, user.get("branch_id")
        )
        if not await threads.may_read(db, user, kind, record_id, doc, thread):
            raise threads.ThreadForbidden("You are not part of this conversation.")
    except (registry.ApprovalKindUnknown, threads.ThreadForbidden) as exc:
        raise _http(exc)
    already = {p.get("user_id") for p in (thread.get("participants") or [])}
    contacts = await _staff_contacts(db, user)
    data = [
        {
            "id": contact["id"],
            "name": contact["name"],
            # What they do, so two people with similar names are told apart by their job
            # rather than by an id.
            "job": (contact.get("sub_category") or contact.get("role") or "")
            .replace("_", " ").title(),
            # Shown as already in rather than hidden, so nobody adds somebody twice and
            # wonders why nothing happened.
            "already_in": contact["id"] in already,
        }
        for contact in contacts
        if contact["id"] != user.get("id")
    ]
    return {"success": True, "data": data, "meta": {"count": len(data)}}


@router.post("/{kind}/{record_id}/decide")
async def decide(kind: str, record_id: str, request: Request,
                 user: dict = Depends(get_current_user)):
    """Approve or reject, whatever the kind.

    The decision itself is carried out by that kind's own service, so this route cannot
    let anybody decide anything they could not decide before this screen existed.
    """
    db = get_db()
    body = await request.json()
    decision = (body.get("decision") or "").strip().lower()
    reason = (body.get("reason") or "").strip()
    if decision not in ("approve", "reject"):
        raise HTTPException(400, "A decision must be approve or reject.")
    # Every kind on this platform already insists on a reason for a refusal, so this is
    # not a new rule; it is the same rule asked once instead of six times.
    if decision == "reject" and not reason:
        raise HTTPException(400, "Say why it was refused, so the person knows what to fix.")
    ctx = _ctx(user)
    try:
        doc = await registry.load(db, kind, record_id, get_school_id())
        result = await registry.decide(db, ctx, user, kind, record_id, decision, reason)
        # The conversation ends when the request is decided (decision 24). Done AFTER the
        # decision, so a refused decision never closes a thread over something that is
        # still open.
        await threads.close_thread(db, ctx, kind, record_id, doc, decision, reason)
    except Exception as exc:  # domain errors only; anything else re-raises below
        mapped = _map_domain_error(exc)
        if mapped is None:
            raise
        raise mapped
    return {"success": True, "data": result}


@router.patch("/{kind}/{record_id}")
async def edit_pending(kind: str, record_id: str, request: Request,
                       user: dict = Depends(get_current_user)):
    """The raiser changes a request while it is still pending, and the change is recorded.

    Decision 27. If the owner says "make it 9,000, not 12,000", the person who asked
    changes it rather than the person deciding, because an approver editing a request as
    they approve it makes the requester and the approver the same person in one click.

    The change is written into the conversation, so nobody can quietly alter a request
    after somebody has read it.
    """
    db = get_db()
    body = await request.json()
    entry = registry.kind_or_raise(kind)
    editable = entry.get("editable_fields")
    if not editable:
        raise HTTPException(
            400,
            "This kind of request cannot be edited once it has been raised. Ask for it "
            "to be refused and put up a new one.",
        )
    school_id = get_school_id()
    doc = await registry.load(db, kind, record_id, school_id)
    if doc.get(entry["raised_by_field"]) != user.get("id"):
        raise HTTPException(403, "Only the person who raised this can change it.")
    if doc.get("status") not in entry["pending_statuses"]:
        raise HTTPException(409, "This has already been decided, so it cannot be changed.")
    changes = {field: body[field] for field in editable if field in body}
    if not changes:
        raise HTTPException(400, "Nothing was changed.")

    ctx = _ctx(user)
    import uuid

    from services.audit_service import write_audit_doc
    from tenant import scoped_filter

    await registry._collection(db, entry).update_one(
        scoped_filter({"id": record_id}, school_id), {"$set": changes}
    )
    # Recorded in the action log as well as in the conversation. The two are for
    # different people: the conversation is what the approver reads before deciding,
    # and the action log is what somebody asks months later.
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": school_id,
            "entity_type": entry["collection"],
            "entity_id": record_id,
            "action": "approval_request_edited",
            "changed_by": ctx.user_id,
            "changed_by_role": ctx.role,
            "changes": {
                field: {"from": doc.get(field), "to": value}
                for field, value in changes.items()
            },
            "created_at": ctx.now_iso(),
        },
        school_id=school_id,
        branch_id=ctx.branch_id,
    )
    was = ", ".join(
        f"{field.replace('_', ' ')} from '{doc.get(field)}' to '{value}'"
        for field, value in changes.items()
    )
    await threads.system_note(
        db, ctx, kind, record_id, doc,
        f"{user.get('name') or 'The person who raised this'} changed {was}.",
    )
    return {"success": True, "data": registry.to_card(kind, {**doc, **changes})}


@router.post("/{kind}/{record_id}/reply")
async def reply(kind: str, record_id: str, request: Request,
                user: dict = Depends(get_current_user)):
    """Say something about this request. Flo is never in here; see the thread service."""
    db = get_db()
    body = await request.json()
    try:
        doc = await registry.load(db, kind, record_id, get_school_id())
        message = await threads.post_message(
            db, _ctx(user), user, kind, record_id, doc,
            body.get("body"), body.get("attachments"),
        )
    except Exception as exc:
        mapped = _map_domain_error(exc)
        if mapped is None:
            raise
        raise mapped
    return {"success": True, "data": message}


@router.post("/{kind}/{record_id}/participants")
async def add_participant(kind: str, record_id: str, request: Request,
                          user: dict = Depends(get_current_user)):
    """Bring somebody in, choosing whether the conversation so far comes with them."""
    db = get_db()
    body = await request.json()
    try:
        doc = await registry.load(db, kind, record_id, get_school_id())
        entry = await threads.add_participant(
            db, _ctx(user), user, kind, record_id, doc,
            body.get("user_id"), bool(body.get("share_history")),
        )
    except Exception as exc:
        mapped = _map_domain_error(exc)
        if mapped is None:
            raise
        raise mapped
    return {"success": True, "data": entry}


@router.post("/{kind}/{record_id}/reopen")
async def reopen(kind: str, record_id: str, request: Request,
                 user: dict = Depends(get_current_user)):
    """Re-open a closed conversation. Only somebody who decides this kind may."""
    db = get_db()
    body = await request.json()
    try:
        doc = await registry.load(db, kind, record_id, get_school_id())
        result = await threads.reopen_thread(
            db, _ctx(user), user, kind, record_id, doc, (body.get("reason") or "").strip()
        )
    except Exception as exc:
        mapped = _map_domain_error(exc)
        if mapped is None:
            raise
        raise mapped
    return {"success": True, "data": result}


def _map_domain_error(exc: Exception):
    """Turn a domain error from any of the six services into an honest HTTP answer.

    Returns None for anything unrecognised, so a genuine fault is never swallowed and
    dressed up as a 400. A bug reported as a bad request is a bug nobody looks for.
    """
    from services.approvals_service import (
        ApprovalAuthorizationError, ApprovalNotFoundError, ApprovalValidationError,
        PendingActionError,
    )
    from services.certificate_service import (
        CertificateNotFoundError, CertificateStateError, CertificateValidationError,
    )
    from services.announcement_service import (
        AnnouncementNotFoundError, AnnouncementStateError, AnnouncementValidationError,
    )
    from services.leave_service import LeaveNotFoundError, LeaveValidationError
    from services.profile_change_service import (
        ProfileChangeAuthorizationError, ProfileChangeConflictError,
        ProfileChangeNotFoundError, ProfileChangeValidationError,
    )
    from services.student_leave_service import (
        StudentLeaveAuthorizationError, StudentLeaveConflictError,
        StudentLeaveNotFoundError, StudentLeaveValidationError,
    )

    if isinstance(exc, (registry.ApprovalKindUnknown, ApprovalNotFoundError,
                        CertificateNotFoundError, AnnouncementNotFoundError,
                        LeaveNotFoundError, ProfileChangeNotFoundError,
                        StudentLeaveNotFoundError)):
        return HTTPException(404, str(exc) or "That request no longer exists.")
    if isinstance(exc, (registry.ApprovalNotVisible, threads.ThreadForbidden,
                        ApprovalAuthorizationError, ProfileChangeAuthorizationError,
                        StudentLeaveAuthorizationError)):
        return HTTPException(403, str(exc) or "Forbidden")
    if isinstance(exc, (threads.ThreadClosed, ProfileChangeConflictError,
                        StudentLeaveConflictError, CertificateStateError,
                        PendingActionError)):
        return HTTPException(409, str(exc))
    if isinstance(exc, (threads.ThreadValidationError, ApprovalValidationError,
                        CertificateValidationError, AnnouncementValidationError,
                        AnnouncementStateError, LeaveValidationError,
                        ProfileChangeValidationError, StudentLeaveValidationError)):
        return HTTPException(400, str(exc))
    return None
