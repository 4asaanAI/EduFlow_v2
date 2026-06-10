"""Incident / complaint / facility-request / tech-request service — the single
shared write path for the runtime-collection ("dynamic-collection") tools
(AI Layer Hardening, AD7 / Epic C).

The AI tools `assign_followup`, `update_incident_status`, `add_thread_entry`, and
`confirm_resolution` historically picked their target collection *at write time* by
scanning ``incidents`` → ``complaints`` → ``facility_requests`` → ``tech_requests``
(``_find_mutable_record``). Epic C makes the target **explicit**: the record type is
resolved up front (``resolve_record_type``) and passed to the service, so scoping,
audit, and later transactions know the mutation surface before any write happens.

Both the REST routes (operations.py incidents endpoints, issues.py facility confirm)
and the AI-tool adapters call these functions, so an AI write produces the exact same
database change as the UI.

Services raise domain exceptions, never ``HTTPException``.
"""

from __future__ import annotations

from services.txn_context import session_kwargs as _txn_session_kwargs

import uuid
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.notification_service import create_notification
from tenant import scoped_query

# Resolution order is significant: it pins the legacy ``_find_mutable_record``
# precedence so the characterization test stays green.
RECORD_TYPES = ("incidents", "complaints", "facility_requests", "tech_requests")
_THREAD_TYPES = ("incidents", "complaints")


class IncidentValidationError(Exception):
    """Missing/invalid fields or an illegal state transition → HTTP 400."""


class IncidentNotFoundError(Exception):
    """No record with this id in the resolved collection → HTTP 404."""


class IncidentAmbiguousError(Exception):
    """The same id exists in more than one collection → refuse (HTTP 409)."""


def _session_kwargs(session) -> dict:
    # AI Layer Hardening D.2: resolve the AMBIENT transaction session when the
    # caller passes none, so a service invoked inside the plan executor's txn
    # auto-enlists. Outside a txn this is {} (identical to pre-D.2 behavior).
    return _txn_session_kwargs(session)


def _note_field(record_type: str) -> str:
    return "thread" if record_type in _THREAD_TYPES else "notes"


def _handle(db, record_type: str):
    if record_type not in RECORD_TYPES:
        raise IncidentValidationError(f"Unknown record type: {record_type}")
    return getattr(db, record_type)


def _is_maintenance(actor_ctx: ActorContext) -> bool:
    return actor_ctx.role == "admin" and actor_ctx.sub_category == "maintenance"


async def resolve_record_type(
    db,
    record_id: str,
    *,
    branch_id: Optional[str] = None,
    include_tech: bool = True,
) -> tuple[str, dict]:
    """Resolve which collection owns ``record_id`` BEFORE any write.

    Returns ``(record_type, doc)``. Raises ``IncidentNotFoundError`` if no
    collection holds the id, or ``IncidentAmbiguousError`` if more than one does
    (record ids are UUID4, so a collision is a hard refusal — never a blind scan
    at write time).
    """
    candidates = [t for t in RECORD_TYPES if include_tech or t != "tech_requests"]
    matches: list[tuple[str, dict]] = []
    for record_type in candidates:
        doc = await _handle(db, record_type).find_one(
            scoped_query({"id": record_id}, branch_id=branch_id), {"_id": 0}
        )
        if doc:
            matches.append((record_type, doc))
    if not matches:
        raise IncidentNotFoundError(f"No incident/complaint/request found for id {record_id}.")
    if len(matches) > 1:
        collisions = ", ".join(rt for rt, _ in matches)
        raise IncidentAmbiguousError(
            f"Record id {record_id} is ambiguous — it exists in: {collisions}. "
            "Specify which record type to act on."
        )
    return matches[0]


def _build_note(actor_ctx: ActorContext, content: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "author_id": actor_ctx.user_id,
        "author_name": actor_ctx.actor_name,
        "author_role": actor_ctx.role,
        "content": content,
        "timestamp": actor_ctx.now_iso(),
    }


async def _append_note(db, record_type, record_id, actor_ctx, content, *, branch_id, session=None):
    entry = _build_note(actor_ctx, content)
    field = _note_field(record_type)
    await _handle(db, record_type).update_one(
        scoped_query({"id": record_id}, branch_id=branch_id),
        {"$push": {field: entry}, "$set": {"updated_at": actor_ctx.now_iso()}},
        **_session_kwargs(session),
    )
    return entry


async def _audit(db, action, record_type, record_id, actor_ctx, changes, reason=None):
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "entity_type": record_type,
            "collection": record_type,
            "entity_id": record_id,
            "action": action,
            "changed_by": actor_ctx.user_id,
            "changed_by_name": actor_ctx.actor_name,
            "changed_by_role": actor_ctx.role,
            "changes": changes,
            "reason": reason,
            "created_at": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )


async def assign_followup(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
) -> dict:
    """Assign a follow-up owner/due-date to a resolved record, optionally adding a
    note, then audit + notify the assignee.

    params: ``{record_type, record_id, assignee_staff_id, due_date, note?, status?}``
    """
    record_type = params.get("record_type")
    record_id = params.get("record_id")
    if not record_type or not record_id or not params.get("assignee_staff_id") or not params.get("due_date"):
        raise IncidentValidationError("record_type, record_id, assignee_staff_id, and due_date are required.")
    handle = _handle(db, record_type)
    bid = actor_ctx.branch_id
    existing = await handle.find_one(scoped_query({"id": record_id}, branch_id=bid), {"_id": 0})
    if not existing:
        raise IncidentNotFoundError("Record not found for follow-up assignment.")

    updates = {
        "assigned_to": params["assignee_staff_id"],
        "due_date": params["due_date"],
        "updated_at": actor_ctx.now_iso(),
    }
    if params.get("status"):
        updates["status"] = params["status"]
    await handle.update_one(
        scoped_query({"id": record_id}, branch_id=bid), {"$set": updates}, **_session_kwargs(session)
    )

    note_entry = None
    if params.get("note"):
        note_entry = await _append_note(db, record_type, record_id, actor_ctx, params["note"], branch_id=bid, session=session)

    await _audit(db, "assign_followup", record_type, record_id, actor_ctx, updates, params.get("note"))

    staff = await db.staff.find_one(scoped_query({"id": params["assignee_staff_id"]}, branch_id=bid), {"_id": 0})
    await create_notification(
        db,
        user_id=(staff or {}).get("user_id"),
        notification_type="followup_assigned",
        title="Follow-up assigned",
        message=params.get("note") or "A follow-up has been assigned to you.",
        source_id=record_id,
        source_type=record_type,
    )
    return {"record_id": record_id, "updates": updates, "note": note_entry}


async def add_thread_entry(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
) -> dict:
    """Append a thread/notes entry to a resolved record + audit.

    params: ``{record_type, record_id, content}``
    """
    record_type = params.get("record_type")
    record_id = params.get("record_id")
    if not record_type or not record_id or not params.get("content"):
        raise IncidentValidationError("record_type, record_id, and content are required.")
    handle = _handle(db, record_type)
    bid = actor_ctx.branch_id
    existing = await handle.find_one(scoped_query({"id": record_id}, branch_id=bid), {"_id": 0})
    if not existing:
        raise IncidentNotFoundError("Record not found for thread entry.")
    entry = await _append_note(db, record_type, record_id, actor_ctx, params["content"], branch_id=bid, session=session)
    await _audit(db, "add_thread_entry", record_type, record_id, actor_ctx, {"entry": entry})
    return {"entry": entry}


async def update_incident_status(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
) -> dict:
    """Transition a resolved record's status (and/or add a resolution note),
    append an optional thread note, then audit with the previous status.

    params: ``{record_type, record_id, new_status?, note?, resolution_note?}``
    """
    record_type = params.get("record_type")
    record_id = params.get("record_id")
    new_status = params.get("new_status")
    resolution_note = params.get("resolution_note")
    if not record_type or not record_id:
        raise IncidentValidationError("record_type and record_id are required.")
    if not new_status and not resolution_note and not params.get("note"):
        raise IncidentValidationError("new_status, resolution_note, or note is required.")
    # Transition guard (centralised so both entrypoints enforce it).
    if _is_maintenance(actor_ctx) and new_status == "closed":
        raise IncidentValidationError("Maintenance Admin cannot close a facility request directly.")

    handle = _handle(db, record_type)
    bid = actor_ctx.branch_id
    existing = await handle.find_one(scoped_query({"id": record_id}, branch_id=bid), {"_id": 0})
    if not existing:
        raise IncidentNotFoundError("Incident, complaint, or request not found.")

    updates = {"updated_at": actor_ctx.now_iso()}
    if new_status:
        updates["status"] = new_status
    if resolution_note:
        updates["resolution_note"] = resolution_note
        updates["resolved_by"] = actor_ctx.user_id
        updates["resolved_at"] = actor_ctx.now_iso()
    await handle.update_one(
        scoped_query({"id": record_id}, branch_id=bid), {"$set": updates}, **_session_kwargs(session)
    )

    if params.get("note"):
        await _append_note(db, record_type, record_id, actor_ctx, params["note"], branch_id=bid, session=session)

    await _audit(
        db,
        "update_incident_status",
        record_type,
        record_id,
        actor_ctx,
        {"previous_status": existing.get("status"), **updates},
        params.get("note"),
    )
    return {"record_id": record_id, "updates": updates}


async def confirm_resolution(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
) -> dict:
    """Owner confirmation that closes a facility request pending confirmation.

    params: ``{request_id, confirmation_note?}``
    """
    request_id = params.get("request_id")
    if not request_id:
        raise IncidentValidationError("request_id is required.")
    bid = actor_ctx.branch_id
    existing = await db.facility_requests.find_one(scoped_query({"id": request_id}, branch_id=bid), {"_id": 0})
    if not existing:
        raise IncidentNotFoundError("Facility request not found.")
    if existing.get("status") != "pending_owner_confirmation":
        raise IncidentValidationError("Request must be pending Owner confirmation before it can be closed.")

    update = {
        "status": "closed",
        "resolved_by": actor_ctx.user_id,
        "resolved_at": actor_ctx.now_iso(),
        "updated_at": actor_ctx.now_iso(),
    }
    await db.facility_requests.update_one(
        scoped_query({"id": request_id}, branch_id=bid), {"$set": update}, **_session_kwargs(session)
    )
    if params.get("confirmation_note"):
        await _append_note(db, "facility_requests", request_id, actor_ctx, params["confirmation_note"], branch_id=bid, session=session)
    # Canonical audit action = "confirm_resolution" (the AI tool's name; the legacy REST
    # route wrote "facility_request_close" but no consumer depends on it — parity test pins this).
    await _audit(db, "confirm_resolution", "facility_requests", request_id, actor_ctx, {"status": "closed"}, params.get("confirmation_note"))
    await create_notification(
        db,
        user_id=existing.get("logged_by"),
        notification_type="facility_resolved",
        title="Facility request resolved",
        message="Facility request resolved and closed by Owner.",
        source_id=request_id,
        source_type="facility_request",
    )
    return {"request_id": request_id, "update": update}


async def create_incident(db, actor_ctx: ActorContext, params: dict, *, session=None, fan_out_fn=None) -> dict:
    """Create an incident (shared write path — REST POST /api/ops/incidents + AI
    `create_incident`). P9.8 semantics preserved: any authenticated role may log;
    high severity auto-assigns to principal and fans out a notification.

    params: {description, title?, severity?, category?, involved_parties?, assigned_to?}
    """
    if not params.get("description"):
        raise IncidentValidationError("description is required")
    severity = params.get("severity", "low")
    if severity not in ("low", "medium", "high"):
        raise IncidentValidationError("severity must be low, medium, or high")
    assigned_to = "principal" if severity == "high" else params.get("assigned_to") or None
    incident = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "title": params.get("title", ""),
        "description": params["description"],
        "severity": severity,
        "involved_parties": params.get("involved_parties", ""),
        "category": params.get("category", "general"),
        "status": "open",
        "thread": [],
        "logged_by": actor_ctx.user_id,
        "logged_by_name": actor_ctx.actor_name,
        "assigned_to": assigned_to,
        "due_date": None,
        "created_at": actor_ctx.now_iso(),
        "updated_at": actor_ctx.now_iso(),
    }
    incident["id"] = incident["_id"]  # one id for both keys, matching panel reads by `id`
    await db.incidents.insert_one(incident, **_session_kwargs(session))

    if severity == "high" and fan_out_fn is not None:
        owners_principals = await db.users.find(
            {"role": {"$in": ["owner", "admin"]}, "is_active": {"$ne": False}},
            {"_id": 0, "id": 1, "sub_category": 1, "role": 1},
        ).to_list(20)
        await fan_out_fn(
            db,
            [
                up["id"] for up in owners_principals
                if up.get("role") == "owner" or up.get("sub_category") == "principal"
            ],
            notification_type="high_severity_incident",
            title="High-severity incident",
            message=f"High-severity incident reported: {params['description'][:80]}",
            source_id=incident["id"],
            source_type="incident",
        )
    await _audit(
        db, "incident_create", "incidents", incident["id"], actor_ctx,
        {"severity": severity, "description": params["description"][:100]},
    )
    return {"incident": {k: v for k, v in incident.items() if k != "_id"}}
