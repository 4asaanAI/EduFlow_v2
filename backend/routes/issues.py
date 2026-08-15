from __future__ import annotations

"""Issue tracker - facility requests (Maintenance Admin) and tech requests (IT/Tech Admin)"""
import calendar
import logging
import uuid
from datetime import date as _date, datetime, timedelta, timezone

from fastapi import APIRouter, Request, HTTPException, Depends

from pagination import clamp_page, clamp_page_size
from database import get_db
from middleware.auth import get_current_user, require_owner, require_role, require_access, require_owner_or_principal
from services.audit_service import write_audit_doc
from services.notification_service import create_notification, fan_out_notifications
from services.actor_context import actor_ctx_from_user
from services import platform_ticket_service
from services.incident_service import (
    confirm_resolution as svc_confirm_resolution,
    IncidentValidationError,
    IncidentNotFoundError,
)
from tenant import get_school_id, scoped_filter, scoped_query, add_school_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/issues", tags=["issues"])


def get_user(req: Request):
    return get_current_user(req)


FACILITY_CATEGORIES = {
    "plumbing", "electrical", "civil", "cleaning", "security", "carpentry",
    "painting", "pest_control", "hvac", "fire_safety", "landscaping", "other",
    # R3-2, 2026-08-15. Servicing and repairs to the school's buses, vans and autos.
    #
    # This category is what makes Abhimanyu's decision of 2026-08-15 expressible at all:
    # the transport head sees what a VEHICLE repair costs, and not what repairs to
    # buildings and other school property cost. Without a category naming the difference,
    # "vehicle repairs only" would have been a promise with nothing behind it.
    "vehicle",
}

# The only category whose money the transport head may see. A set rather than a bare
# comparison so that adding a second one is a visible edit somebody has to justify.
TRANSPORT_COST_CATEGORIES = frozenset({"vehicle"})
VALID_STATUSES = {"open", "accepted", "in_progress", "pending_parts", "pending_owner_confirmation", "done", "closed"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
# Fix 12.1: Correct SLA hours per NFR12.2, renamed constant
FACILITY_SLA_HOURS = {"low": 168, "medium": 72, "high": 24, "urgent": 4}

# Fix 12.2: Rate-limit cooldown
ESCALATION_COOLDOWN_SECONDS = 3600

# Fix 12.3: Photo limit
PHOTO_LIMIT = 5


def _can_view_all(user: dict) -> bool:
    """Owner and principal see every request. Nobody else does.

    R3-2, 2026-08-15. This used to read `sub_category in ("principal", None)`, so an
    admin carrying NO sub_category at all was treated as the principal. Nobody decided
    that; it is a default that leaked, and it governs the maintenance calendar, the
    contractor list, the whole issue register and the request history - which is exactly
    where Chaman's access lands, so it had to be settled before granting him anything
    behind it.

    Dropping `None` is consistent with the rest of the platform rather than a new rule:
    `scope_resolver` already denies by default when `sub_category` is missing, and
    migration 016 exists precisely to backfill legacy rows so none is left in that state.
    An admin row with no sub_category is a data fault, and the safe reading of a data
    fault is "no", not "principal".
    """
    role = user.get("role")
    return role == "owner" or (role == "admin" and user.get("sub_category") == "principal")


def _is_maint(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "maintenance"


def _is_it_tech(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "it_tech"


def _facility_self_only(user: dict) -> bool:
    """Profiles that may see the repair requests they raised, and no others."""
    return user.get("role") == "teacher" or (
        user.get("role") == "admin" and user.get("sub_category") == "receptionist"
    )


_COST_FIELDS = ("estimated_cost", "actual_cost", "cost_awaiting_approval")


def _strip_costs_for(user: dict, rec: dict) -> dict:
    """Take the money off a repair request for anyone not entitled to see it.

    R3-2, 2026-08-15. Abhimanyu's decision: the transport head sees what a VEHICLE repair
    costs, because transport money is his, and does NOT see what repairs to buildings and
    other school property cost.

    Removed rather than zeroed. A repair showing 0 and a repair nobody has priced look
    identical, and this platform has been bitten before by a partial answer that reads as
    a complete one.
    """
    if not rec:
        return rec
    role, sub = user.get("role"), user.get("sub_category")
    if role == "owner" or (role == "admin" and sub in ("principal", "accountant")):
        return rec
    if role == "admin" and sub == "transport_head":
        if rec.get("category") in TRANSPORT_COST_CATEGORIES:
            return rec
    return {k: v for k, v in rec.items() if k not in _COST_FIELDS}


def _may_read_facility_request(user: dict, rec: dict) -> bool:
    """One statement of who may read a repair request, list or single record.

    R3-2, 2026-08-15. The list route already made this decision in-line. The single-record
    route made no decision at all. Rather than copy the list's rules into a second place -
    which is the exact habit the R3-1 survey named, about a dozen hand-written lists of
    desk names that never move together - both now ask this.

    IT is refused outright: facility work is not theirs and the list route says so
    explicitly. Everyone else either sees all of them or only the ones they raised.
    """
    if _is_it_tech(user):
        return False
    if _can_view_all(user) or _is_maint(user):
        return True
    if _facility_self_only(user):
        return rec.get("logged_by") == user.get("id")
    # Anybody else reaches their own requests and nothing more. A person who raised a
    # repair may follow it up whatever their profile; that is not a permission grant.
    return rec.get("logged_by") == user.get("id")


def _is_it(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "it_tech"


def _audit(action, entity_type, entity_id, user, changes):
    return add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "changed_by": user.get("id"),
        "changed_by_name": user.get("name", ""),
        "changed_by_role": user.get("role"),
        "collection": entity_type,
        "changes": changes,
        "created_at": datetime.now().isoformat(),
    })


def _sla_due(priority: str) -> str:
    # Fix 12.1: uses renamed FACILITY_SLA_HOURS with corrected values
    return (datetime.now() + timedelta(hours=FACILITY_SLA_HOURS.get(priority, 72))).isoformat()


def _is_overdue(doc: dict) -> bool:
    # Fix 12.8: check "due_at" first (new field name), fall back to "sla_due_at" and "scheduled_date"
    due_at = doc.get("due_at") or doc.get("sla_due_at") or doc.get("scheduled_date")
    if not due_at or doc.get("status") in {"done", "closed"}:
        return False
    try:
        return datetime.fromisoformat(str(due_at)[:19]) < datetime.now()
    except ValueError:
        return False


def _add_months(dt: _date, months: int) -> _date:
    """Calendar-correct month addition (Fix 12.9)."""
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _next_scheduled_date(scheduled_date: str, recurrence: str) -> str | None:
    """Fix 12.9: calendar-correct recurrence arithmetic (no 30/90/365 shortcuts)."""
    try:
        base = _date.fromisoformat(scheduled_date[:10])
    except ValueError:
        return None
    if recurrence == "weekly":
        return (base + timedelta(weeks=1)).isoformat()
    if recurrence == "monthly":
        return _add_months(base, 1).isoformat()
    if recurrence == "quarterly":
        return _add_months(base, 3).isoformat()
    if recurrence == "annual":
        return _add_months(base, 12).isoformat()
    return None


async def _write_audit(db, action, entity_type, entity_id, user, changes):
    await write_audit_doc(
        db,
        _audit(action, entity_type, entity_id, user, changes),
        school_id=get_school_id(),
        branch_id=user.get("branch_id"),
    )


async def _notification_targets(db, query: dict, projection: dict, limit: int = 30) -> list[dict]:
    users = getattr(db, "users", None)
    if users is None:
        return []
    # branch-scope: intentional - user records are school-wide; notifications fan out to all admins/owners regardless of branch
    scoped_q = scoped_filter(query, get_school_id())  # branch-scope: intentional - see the note directly above this line
    return await users.find(scoped_q, projection).to_list(limit)


# ─── Facility Requests (Maintenance Admin) ────────────────────────────────────

@router.post("/facility")
async def create_facility_request(request: Request):
    db = get_db()
    user = get_user(request)
    # Allow: maintenance admin, owner, teacher, or any staff raising a request
    role = user.get("role")
    sub = user.get("sub_category")
    # R3-2, 2026-08-15: `transport_head` added - he holds the "report a problem" screen
    # and arranges the servicing, so he must be able to raise a request; and `None`
    # removed, for the same reason it came out of `_can_view_all`. An admin with no job
    # title is a data fault, not a profile, and reading it as permission is a default
    # nobody chose.
    allowed = role in ("owner", "teacher") or (role == "admin" and sub in (
        "maintenance", "principal", "receptionist", "management", "transport_head"))
    if not allowed:
        raise HTTPException(403, "You are not permitted to raise facility requests")
    body = await request.json()
    if not body.get("description"):
        raise HTTPException(400, "description is required")
    cat = body.get("category", "other")
    if cat not in FACILITY_CATEGORIES:
        raise HTTPException(400, f"category must be one of {sorted(FACILITY_CATEGORIES)}")
    priority = body.get("priority", "medium")
    if priority not in VALID_PRIORITIES:
        raise HTTPException(400, f"priority must be one of {sorted(VALID_PRIORITIES)}")
    req_doc = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "type": "facility",
        "description": body["description"],
        "location": body.get("location", ""),
        "category": cat,
        "priority": priority,
        "due_at": _sla_due(priority),  # Fix 12.8: renamed sla_due_at → due_at
        "photos": [u for u in body.get("photos", []) if isinstance(u, str)][:PHOTO_LIMIT],
        "estimated_cost": body.get("estimated_cost"),
        "actual_cost": body.get("actual_cost"),
        "vendor_id": body.get("vendor_id"),
        "status": "open",
        "logged_by": user["id"],
        "logged_by_name": user.get("name", ""),
        "logged_by_role": role,
        "notes": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })
    await db.facility_requests.insert_one(req_doc)
    await _write_audit(db, "facility_request_create", "facility_requests", req_doc["id"], user, {"created": req_doc["description"]})

    msg = f"New maintenance request [{priority.upper()}]: {req_doc['description'][:80]} @ {req_doc['location']} - raised by {user.get('name', 'Staff')}."
    # Notify maintenance admins, owners, and principals (flat users collection schema)
    notify_targets = await _notification_targets(db,
        {"role": {"$in": ["owner", "admin"]}, "is_active": {"$ne": False}},
        {"_id": 0, "id": 1, "role": 1, "sub_category": 1},
    )
    await fan_out_notifications(
        db,
        [
            target["id"] for target in notify_targets
            if target.get("id")
            and target.get("id") != user["id"]
            and (target.get("role") == "owner" or target.get("sub_category") in ("principal", "maintenance"))
        ],
        notification_type="facility_request_new",
        title="New facility request",
        message=msg,
        source_id=req_doc["id"],
        source_type="facility_request",
    )

    return {"success": True, "data": {k: v for k, v in req_doc.items() if k != "_id"}}


@router.get("/facility")
async def list_facility_requests(
    request: Request,
    status: str = None,
    priority: str = None,
    category: str = None,
    overdue: bool = None,  # Fix 12.7: filter by overdue flag
    page: int = 1,
    limit: int = 20,
):
    db = get_db()
    user = get_user(request)
    bid = user.get("branch_id")
    is_maintenance = _is_maint(user)
    if user.get("role") == "admin" and user.get("sub_category") == "it_tech":
        raise HTTPException(403, "IT/Tech Admin cannot access facility requests")
    # Teachers/staff who raised requests can see their own
    is_self_only = _facility_self_only(user)
    # R3-2, 2026-08-15: the transport head sees VEHICLE repairs, all of them, because he
    # arranges the servicing. Not the whole campus queue: a leaking tap in a classroom is
    # the maintenance team's and always was.
    is_transport_head = user.get("role") == "admin" and user.get("sub_category") == "transport_head"
    if not _can_view_all(user) and not is_maintenance and not is_self_only and not is_transport_head:
        raise HTTPException(403, "Forbidden")
    query = {}
    if is_transport_head:
        # Applied to the QUERY, so the count and the rows agree and no filter he can send
        # widens it. He may still narrow further with the `category` parameter below.
        query["category"] = {"$in": sorted(TRANSPORT_COST_CATEGORIES)}
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    if category:
        # R3-2: the transport head's restriction above is set on this same key, so a
        # plain assignment here would let him ask for `category=plumbing` and read the
        # whole campus queue. Anything outside his categories is refused rather than
        # quietly returning nothing, because an empty list reads as "no repairs" and
        # that is a different fact from "not yours".
        if is_transport_head and category not in TRANSPORT_COST_CATEGORIES:
            raise HTTPException(
                403,
                "Repairs to buildings and other school property are the maintenance "
                "team's. You see vehicle repairs.",
            )
        query["category"] = category
    # Self-view: teachers/receptionist see only their own requests
    if is_self_only:
        query["logged_by"] = user["id"]
    # Maintenance admin sees ALL school facility requests (not filtered to self)
    page = clamp_page(page)
    limit = clamp_page_size(limit)
    skip = (page - 1) * limit
    total = await db.facility_requests.count_documents(scoped_query(query, branch_id=bid))
    items = await db.facility_requests.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort([("priority", 1), ("created_at", -1)]).skip(skip).limit(limit).to_list(limit)
    # Fix 12.8: rename overdue → is_overdue
    for item in items:
        item["is_overdue"] = _is_overdue(item)
    # Fix 12.7: apply overdue filter if requested
    if overdue is True:
        items = [i for i in items if i["is_overdue"]]
    elif overdue is False:
        items = [i for i in items if not i["is_overdue"]]
    # R3-2, 2026-08-15: the list has always printed `estimated_cost` on screen, and the
    # transport head reaches this list now. Same rule as the single record.
    items = [_strip_costs_for(user, i) for i in items]
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@router.get("/facility/cost-summary")
async def get_facility_cost_summary(request: Request, user: dict = Depends(require_owner_or_principal)):
    """Cost summary by category using MongoDB $sum (null-safe). EC-12.4."""
    db = get_db()
    bid = user.get("branch_id")
    today = _date.today()
    pipeline = [
        {"$match": scoped_query({}, branch_id=bid)},
        {"$group": {
            "_id": "$category",
            "total_estimated": {"$sum": "$estimated_cost"},
            "total_actual": {"$sum": "$actual_cost"},
            "count": {"$sum": 1},
        }},
    ]
    results = await db.facility_requests.aggregate(pipeline).to_list(None)
    return {"success": True, "data": results, "meta": {"month": today.strftime("%Y-%m")}}


@router.get("/facility/{request_id}")
async def get_facility_request(request_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Single facility request by ID. Fix 12.5.

    R3-2, 2026-08-15: this route used to be signed-in-only. Any account on the platform
    could read any repair request by its id, INCLUDING `estimated_cost` and `actual_cost`,
    while the list route beside it refused the same people. A single record is not less
    sensitive than the list it came from, and a facility request is where every repair
    amount on this platform lives.

    It now answers the same question the list answers, through the same helper, so the
    two cannot drift apart. Nothing on screen calls this route, so nobody loses a working
    control by it being narrowed.
    """
    db = get_db()
    bid = user.get("branch_id")
    # NEW-07/T13: this document IS the response body - exclude the internal id.
    rec = await db.facility_requests.find_one(
        scoped_query({"id": request_id}, branch_id=bid), {"_id": 0}
    )
    if not rec:
        raise HTTPException(404, "Facility request not found")
    if not _may_read_facility_request(user, rec):
        raise HTTPException(403, "Forbidden")
    rec["is_overdue"] = _is_overdue(rec)
    return {"success": True, "data": _strip_costs_for(user, rec)}


@router.post("/facility/{request_id}/propose-cost")
async def propose_repair_cost(request_id: str, request: Request):
    """The transport head says what a vehicle repair will cost. Aman or Adesh agrees it.

    R3-2, 2026-08-15. Abhimanyu's decision: he arranges the servicing and sees the cost,
    and the figure is agreed BEFORE the money is committed.

    So the amount does not land on the request. It sits beside it as
    `cost_awaiting_approval` until the school's owner or the principal says yes, at which
    point the approval service moves it onto `estimated_cost`. Writing it straight onto
    the request and calling it "pending" would leave a figure that every screen reads as
    the real one.
    """
    db = get_db()
    user = get_user(request)
    body = await request.json()
    try:
        amount = float(body.get("estimated_cost"))
    except (TypeError, ValueError):
        raise HTTPException(400, "estimated_cost must be a number")
    if amount < 0:
        raise HTTPException(400, "estimated_cost cannot be negative")

    rec = await db.facility_requests.find_one(
        scoped_query({"id": request_id}, branch_id=user.get("branch_id")), {"_id": 0}
    )
    if not rec:
        raise HTTPException(404, "Facility request not found")

    is_transport_head = user.get("role") == "admin" and user.get("sub_category") == "transport_head"
    if is_transport_head:
        if rec.get("category") not in TRANSPORT_COST_CATEGORIES:
            raise HTTPException(
                403,
                "That is not a vehicle repair. Repairs to buildings and other school "
                "property are the maintenance team's.",
            )
    elif not _can_view_all(user):
        raise HTTPException(403, "Forbidden")

    from services.approvals_service import create_approval_request_doc

    actor_ctx = actor_ctx_from_user(user)
    approval_id = await create_approval_request_doc(
        db, actor_ctx,
        title=f"Agree Rs. {amount:,.0f} for the repair: {rec.get('description', '')[:60]}",
        description=(
            f"The transport head has quoted Rs. {amount:,.0f} for a vehicle repair: "
            f"{rec.get('description', '')}. Nothing is committed until this is agreed."
        ),
        estimated_impact=f"Rs. {amount:,.0f} of school money, paid by the accountant head.",
        note="Proposed cost. The money is not committed yet.",
        routing="owner_and_principal",
        pending_action={"kind": "agree_a_repair_cost", "request_id": request_id,
                        "estimated_cost": amount},
    )
    await db.facility_requests.update_one(
        scoped_query({"id": request_id}, branch_id=user.get("branch_id")),
        {"$set": {"cost_awaiting_approval": amount, "cost_approval_id": approval_id}},
    )
    await _write_audit(db, "repair_cost_proposed", "facility_requests", request_id, user,
                       {"proposed": amount, "approval_id": approval_id})
    return {
        "success": True,
        "awaiting_approval": True,
        "data": {"approval_id": approval_id, "proposed_cost": amount},
        "message": (
            f"Rs. {amount:,.0f} has been sent to the school's owner and the principal to "
            "agree. Nothing is committed until one of them says yes."
        ),
    }


@router.patch("/facility/{request_id}")
async def update_facility_request(request_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    bid = user.get("branch_id")
    is_maint = _is_maint(user)
    if not is_maint and not _can_view_all(user):
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    existing = await db.facility_requests.find_one(scoped_query({"id": request_id}, branch_id=bid))
    if not existing:
        raise HTTPException(404, "Facility request not found")

    # Fix 12.3: atomic photo append with limit guard
    if "photos_append" in body:
        new_photos = body["photos_append"]
        if not isinstance(new_photos, list):
            new_photos = [new_photos]
        current_photos = existing.get("photos", [])
        if len(current_photos) >= PHOTO_LIMIT:
            raise HTTPException(409, f"Maximum {PHOTO_LIMIT} photos allowed - limit reached")
        for photo in new_photos:
            await db.facility_requests.update_one(
                scoped_query({"id": request_id}, branch_id=bid),
                {"$push": {"photos": photo}},
            )
        body = {k: v for k, v in body.items() if k != "photos_append"}

    updates = {"updated_at": datetime.now().isoformat()}
    new_status = body.get("status")
    if new_status:
        if new_status not in VALID_STATUSES:
            raise HTTPException(400, f"Invalid status. Valid: {sorted(VALID_STATUSES)}")
        if is_maint and new_status == "closed":
            raise HTTPException(403, "Forbidden")
        updates["status"] = new_status
    if body.get("note"):
        note_entry = {
            "id": str(uuid.uuid4()),
            "author_id": user["id"],
            "author_name": user.get("name", ""),
            "content": body["note"],
            "timestamp": datetime.now().isoformat(),
        }
        await db.facility_requests.update_one(scoped_query({"id": request_id}, branch_id=bid), {"$push": {"notes": note_entry}})
    for field in ("priority", "estimated_cost", "actual_cost", "vendor_id"):
        if field in body:
            updates[field] = body[field]
    if "priority" in updates and updates["priority"] != existing.get("priority"):
        if updates["priority"] not in VALID_PRIORITIES:
            raise HTTPException(400, f"priority must be one of {sorted(VALID_PRIORITIES)}")
        updates["due_at"] = _sla_due(updates["priority"])  # Fix 12.8: due_at
    if updates:
        await db.facility_requests.update_one(scoped_query({"id": request_id}, branch_id=bid), {"$set": updates})
    await _write_audit(db, "facility_request_update", "facility_requests", request_id, user, {"changes": updates})
    updated = await db.facility_requests.find_one(scoped_query({"id": request_id}, branch_id=bid), {"_id": 0})
    return {"success": True, "data": updated}


@router.post("/facility/{request_id}/escalate")
async def escalate_facility_request(request_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    bid = user.get("branch_id")
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    existing = await db.facility_requests.find_one(scoped_query({"id": request_id}, branch_id=bid), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Facility request not found")

    # Fix 12.2a: status guard - cannot escalate closed/done requests
    if existing.get("status") in {"closed", "done"}:
        raise HTTPException(400, "Cannot escalate a closed or done request")

    # Fix 12.2b: rate-limit - 1 hour between escalations
    escalated_at_str = existing.get("escalated_at")
    if escalated_at_str:
        try:
            escalated_at = datetime.fromisoformat(escalated_at_str.replace("Z", "+00:00"))
            now_utc = datetime.now(timezone.utc)
            if escalated_at > now_utc:
                logger.warning(
                    "escalated_at in future for request %s - treating as never-escalated", request_id
                )
            elif (now_utc - escalated_at).total_seconds() < ESCALATION_COOLDOWN_SECONDS:
                raise HTTPException(429, "Request was escalated recently - wait 1 hour before re-escalating")
        except ValueError:
            pass  # malformed date - allow escalation

    body = await request.json()
    update = {
        "priority": body.get("priority", "urgent"),
        "escalated": True,
        "escalated_by": user["id"],
        "escalated_at": datetime.now(timezone.utc).isoformat(),
        "escalation_reason": body.get("reason", ""),
        "due_at": _sla_due(body.get("priority", "urgent")),  # Fix 12.8: due_at
        "updated_at": datetime.now().isoformat(),
    }
    if update["priority"] not in VALID_PRIORITIES:
        raise HTTPException(400, f"priority must be one of {sorted(VALID_PRIORITIES)}")
    await db.facility_requests.update_one(scoped_query({"id": request_id}, branch_id=bid), {"$set": update})
    await _write_audit(db, "facility_request_escalate", "facility_requests", request_id, user, update)

    # Fix 12.2c: notify owner users after escalation
    try:
        owner_users = await db.auth_users.find({"user_info.role": "owner"}).to_list(10)
        for owner in owner_users:
            owner_id = owner.get("user_info", {}).get("id") or owner.get("id")
            if owner_id:
                await create_notification(
                    db=db,
                    user_id=owner_id,
                    notification_type="facility_escalated",
                    title="Facility Request Escalated",
                    message=f"Facility request '{existing.get('title', 'Request')}' has been escalated.",
                    source_id=request_id,
                    source_type="facility_request",
                )
    except Exception:
        logger.warning("Failed to notify owners after escalation of %s", request_id)

    updated = await db.facility_requests.find_one(scoped_query({"id": request_id}, branch_id=bid), {"_id": 0})
    return {"success": True, "data": updated}


@router.post("/facility/{request_id}/confirm-resolution")
async def confirm_facility_resolution(request_id: str, request: Request, user: dict = Depends(require_owner)):
    # Story C.3: delegate to services.incident_service.confirm_resolution - the SAME
    # write path as the AI `confirm_resolution` tool (close + audit + submitter notify).
    db = get_db()
    try:
        body = await request.json()
    except Exception:
        body = {}
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_confirm_resolution(db, actor_ctx, {
            "request_id": request_id,
            "confirmation_note": body.get("confirmation_note"),
        })
    except IncidentNotFoundError:
        raise HTTPException(404, "Facility request not found")
    except IncidentValidationError:
        raise HTTPException(400, "Request must be in pending_owner_confirmation status")
    return {"success": True, "message": "Facility request closed and maintenance admin notified"}


# ─── Tech Requests (IT/Tech Admin) ────────────────────────────────────────────

@router.post("/tech")
async def create_tech_request(
    request: Request,
    user: dict = Depends(require_role("owner", "admin")),
):
    db = get_db()
    if not (_is_it(user) or user.get("role") == "owner"):
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    if not body.get("description"):
        raise HTTPException(400, "description is required")
    req_doc = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "type": "tech",
        "description": body["description"],
        "location": body.get("location", ""),
        "category": body.get("category", "hardware"),
        "status": "open",
        "logged_by": user["id"],
        "logged_by_name": user.get("name", ""),
        "notes": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })
    await db.tech_requests.insert_one(req_doc)
    await _write_audit(db, "tech_request_create", "tech_requests", req_doc["id"], user, {"created": req_doc["description"]})
    return {"success": True, "data": {k: v for k, v in req_doc.items() if k != "_id"}}


def _require_it_tech_access(request: Request) -> dict:
    """Part 13: owner role OR admin with sub_category=it_tech. Raises 403 otherwise."""
    user = get_current_user(request)
    if user.get("role") == "owner":
        return user
    if user.get("role") == "admin" and user.get("sub_category") == "it_tech":
        return user
    raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/tech")
async def list_tech_requests(
    request: Request,
    status: str = None,
    page: int = 1,
    limit: int = 20,
    user: dict = Depends(_require_it_tech_access),
):
    # rbac: intentional - only it_tech admin and owner can view tech tickets
    db = get_db()
    bid = user.get("branch_id")
    query = {}
    if status:
        query["status"] = status
    page = clamp_page(page)
    limit = clamp_page_size(limit)
    skip = (page - 1) * limit
    total = await db.tech_requests.count_documents(scoped_query(query, branch_id=bid))
    items = await db.tech_requests.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@router.patch("/tech/{request_id}")
async def update_tech_request(request_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    bid = user.get("branch_id")
    is_it = _is_it(user)
    if not is_it and not _can_view_all(user):
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    existing = await db.tech_requests.find_one(scoped_query({"id": request_id}, branch_id=bid))
    if not existing:
        raise HTTPException(404, "Tech request not found")
    # Reassignment lock: once status advanced or note added, category is locked
    if body.get("category") and body["category"] != existing.get("category"):
        has_notes = len(existing.get("notes", [])) > 0
        is_advanced = existing.get("status", "open") != "open"
        if has_notes or is_advanced:
            raise HTTPException(400, "Category cannot be changed after notes have been added or status advanced beyond open")
    updates = {"updated_at": datetime.now().isoformat()}
    if body.get("status") and body["status"] in VALID_STATUSES:
        updates["status"] = body["status"]
    if body.get("category"):
        updates["category"] = body["category"]
    if body.get("note"):
        note_entry = {
            "id": str(uuid.uuid4()),
            "author_id": user["id"],
            "author_name": user.get("name", ""),
            "content": body["note"],
            "timestamp": datetime.now().isoformat(),
        }
        await db.tech_requests.update_one(scoped_query({"id": request_id}, branch_id=bid), {"$push": {"notes": note_entry}})
    if updates:
        await db.tech_requests.update_one(scoped_query({"id": request_id}, branch_id=bid), {"$set": updates})
    await _write_audit(db, "tech_request_update", "tech_requests", request_id, user, {"changes": updates})
    updated = await db.tech_requests.find_one(scoped_query({"id": request_id}, branch_id=bid), {"_id": 0})
    return {"success": True, "data": updated}


# ─── Platform tickets: telling Layaa AI (R4-5) ────────────────────────────────
#
# The two above stay inside the school. This one leaves it. Every profile may raise
# one, owner down to student, because the person most likely to see a screen that will
# not load is whoever was using it, and a report we refuse to accept is a fault we hear
# about a week later instead.
#
# There is therefore NO role gate on raising a ticket, and that is a decision rather
# than an omission. Reading OTHER people's tickets is gated: you see your own, and the
# owner and principal see all of them, which is the same rule the merged view below
# already uses.
#
# Every one of these is a thin shell over `platform_ticket_service`. The screen and Flo
# reach the same function, so a change to how a ticket is recorded cannot land in one
# entrance and miss the other.

@router.post("/platform")
async def raise_platform_ticket(request: Request, user: dict = Depends(get_current_user)):
    """Report a platform problem to Layaa AI. Open to every signed-in profile."""
    db = get_db()
    body = await request.json()
    try:
        ticket = await platform_ticket_service.raise_ticket(
            db,
            user,
            title=body.get("title", ""),
            detail=body.get("detail"),
            kind=body.get("kind", "support"),
            priority=body.get("priority", "normal"),
            context=body.get("context") or {},
            app_url=body.get("app_url"),
            screenshot_base64=body.get("screenshot_base64"),
            screenshot_mime=body.get("screenshot_mime"),
        )
    except platform_ticket_service.PlatformTicketError as exc:
        raise HTTPException(400, str(exc))
    return {"success": True, "data": ticket}


@router.get("/platform")
async def list_platform_tickets(
    request: Request,
    status: str = None,
    page: int = 1,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    page = clamp_page(page)
    limit = clamp_page_size(limit)
    result = await platform_ticket_service.list_tickets(
        db,
        user,
        # The one place that decides who sees everybody's. The service never guesses.
        mine_only=not _can_view_all(user),
        status=status,
        skip=(page - 1) * limit,
        limit=limit,
    )
    return {
        "success": True,
        "data": result["items"],
        "meta": {"page": page, "limit": limit, "total": result["total"]},
    }


@router.post("/platform/{ticket_id}/resend")
async def resend_platform_ticket(ticket_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Try again to deliver a ticket that is saved here but never reached Layaa AI."""
    db = get_db()
    existing = await db.platform_tickets.find_one(
        scoped_query({"id": ticket_id}, branch_id=user.get("branch_id")), {"_id": 0}
    )
    if not existing:
        raise HTTPException(404, "Ticket not found")
    # You may push your own along; the owner and principal may push anybody's. Without
    # this a student could re-send a colleague's ticket, which is a small thing, but it
    # is somebody else's report and not theirs to act on.
    if existing.get("raised_by") != user.get("id") and not _can_view_all(user):
        raise HTTPException(403, "Forbidden")
    try:
        ticket = await platform_ticket_service.resend_ticket(db, user, ticket_id)
    except platform_ticket_service.PlatformTicketError as exc:
        raise HTTPException(404, str(exc))
    return {"success": True, "data": ticket}


# ─── Merged view (Owner / Principal) ─────────────────────────────────────────

@router.get("")
async def list_all_issues(request: Request, type: str = "all", status: str = None, page: int = 1, limit: int = 50):
    db = get_db()
    user = get_user(request)
    if not _can_view_all(user):
        raise HTTPException(403, "Forbidden")
    bid = user.get("branch_id")
    query = {}
    if status:
        query["status"] = status
    limit = min(max(limit, 1), 50)
    skip = max(page - 1, 0) * limit
    results = []
    # branch-scope: intentional - owner has cross-branch visibility (bid=None falls back to school-only); principal is branch-scoped via bid
    scoped = scoped_query(query, branch_id=bid)
    if type in ("all", "facility"):
        fac = await db.facility_requests.find(scoped, {"_id": 0}).sort("created_at", -1).to_list(200)
        for f in fac:
            f["issue_type"] = "facility"
        results.extend(fac)
    if type in ("all", "tech"):
        tech = await db.tech_requests.find(scoped, {"_id": 0}).sort("created_at", -1).to_list(200)
        for t in tech:
            t["issue_type"] = "tech"
        results.extend(tech)
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    total = len(results)
    paginated = results[skip: skip + limit]
    return {"success": True, "data": paginated, "meta": {"page": page, "limit": limit, "total": total}}


# ─── Request History (audit trail) ───────────────────────────────────────────

_HISTORY_ACTION_LABELS = {
    "facility_request_update":   "Request updated",
    "facility_request_escalate": "Escalated to owner",
    "tech_request_update":       "Tech issue updated",
}

# Actions to skip in history (creation already synthesised from record)
_HISTORY_SKIP_ACTIONS = {"facility_request_create", "tech_request_create"}


def _extract_status_from_audit(changes: dict) -> str | None:
    """Handle both flat (escalate) and nested (update) change structures."""
    nested = (changes.get("changes") or {})
    return nested.get("status") or changes.get("status")


def _extract_detail_from_audit(action: str, changes: dict) -> str | None:
    inner = changes.get("changes") or changes
    parts = []
    status = _extract_status_from_audit(changes)
    if status:
        parts.append(f"Status → {status.replace('_', ' ')}")
    if action == "facility_request_escalate":
        reason = changes.get("escalation_reason")
        priority = changes.get("priority")
        if priority:
            parts.append(f"Priority set to {priority}")
        if reason:
            parts.append(f"Reason: {reason}")
    if not parts:
        for key in ("rejection_reason", "resolution", "note"):
            val = inner.get(key) or changes.get(key)
            if val:
                parts.append(str(val))
                break
    return " · ".join(parts) if parts else None


@router.get("/{issue_type}/{request_id}/history")
async def get_request_history(issue_type: str, request_id: str, request: Request):
    """Full audit trail for a facility or tech request. Owner/admin only."""
    # Enforce authentication before any request validation so unauthenticated
    # callers always get 401 (not a 400 that leaks the endpoint's shape).
    # Mirrors the get_user()-first ordering used by every other handler here.
    user = get_user(request)
    if issue_type not in ("facility", "tech"):
        raise HTTPException(400, "issue_type must be 'facility' or 'tech'")
    db = get_db()
    bid = user.get("branch_id")
    school_id = get_school_id()

    can_see = _can_view_all(user) or (_is_maint(user) and issue_type == "facility") or (_is_it(user) and issue_type == "tech")
    if not can_see:
        raise HTTPException(403, "Forbidden")

    coll = db.facility_requests if issue_type == "facility" else db.tech_requests
    record = await coll.find_one(scoped_query({"id": request_id}, branch_id=bid), {"_id": 0})
    if not record:
        raise HTTPException(404, f"{issue_type.title()} request not found")

    timeline = []

    # 1. Creation event from the record itself
    timeline.append({
        "event_type": "created",
        "label": "Request raised",
        "detail": record.get("description", ""),
        "actor": record.get("logged_by_name", ""),
        "actor_role": record.get("logged_by_role", ""),
        "timestamp": record.get("created_at", ""),
        "is_current": False,
    })

    # 2. Audit log events (sorted ascending - history order)
    audit_entries = await db.audit_logs.find(
        scoped_filter({"entity_id": request_id}, school_id), {"_id": 0}  # branch-scope: intentional - pinned by a unique id, so a branch filter could only turn a real row into a false 404
    ).sort("created_at", 1).to_list(200)

    for entry in audit_entries:
        action = entry.get("action", "")
        if action in _HISTORY_SKIP_ACTIONS:
            continue
        label = _HISTORY_ACTION_LABELS.get(action) or action.replace("_", " ").title()
        changes = entry.get("changes") or {}
        detail = _extract_detail_from_audit(action, changes)
        timeline.append({
            "event_type": action,
            "label": label,
            "detail": detail,
            "actor": entry.get("changed_by_name", ""),
            "actor_role": entry.get("changed_by_role", ""),
            "timestamp": entry.get("created_at") or entry.get("timestamp") or "",
            "is_current": False,
        })

    # 3. Notes as timeline events (stored inline on the record)
    for note in (record.get("notes") or []):
        timeline.append({
            "event_type": "note",
            "label": "Note added",
            "detail": note.get("content", ""),
            "actor": note.get("author_name", ""),
            "actor_role": "",
            "timestamp": note.get("timestamp", ""),
            "is_current": False,
        })

    # Sort all events chronologically; mark the last one as current
    timeline.sort(key=lambda e: e.get("timestamp", ""))
    if timeline:
        timeline[-1]["is_current"] = True

    return {
        "success": True,
        "data": {
            "record": record,
            "timeline": timeline,
        },
    }


# ─── Maintenance Schedule ─────────────────────────────────────────────────────

@router.get("/maintenance/schedule/upcoming")
async def get_upcoming_schedule(
    request: Request,
    days: int = 14,
    user: dict = Depends(require_owner_or_principal),
):
    """Upcoming maintenance tasks for the next N days. Fix 12.6."""
    db = get_db()
    bid = user.get("branch_id")
    today = _date.today().isoformat()
    until = (_date.today() + timedelta(days=days)).isoformat()
    items = await db.maintenance_schedule.find(
        scoped_query({"scheduled_date": {"$gte": today, "$lte": until}}, branch_id=bid),
        {"_id": 0},
    ).sort("scheduled_date", 1).to_list(100)
    return {"success": True, "data": items}


@router.get("/maintenance/schedule")
async def list_maintenance_schedule(request: Request, page: int = 1, limit: int = 20):
    db = get_db()
    user = get_user(request)
    bid = user.get("branch_id")
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    page = clamp_page(page)
    limit = clamp_page_size(limit)
    skip = (page - 1) * limit
    total = await db.maintenance_schedule.count_documents(scoped_query({}, branch_id=bid))
    items = await db.maintenance_schedule.find(scoped_query({}, branch_id=bid), {"_id": 0}).sort("scheduled_date", 1).skip(skip).limit(limit).to_list(limit)
    for item in items:
        item["is_overdue"] = _is_overdue(item)  # Fix 12.8: renamed overdue → is_overdue
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@router.post("/maintenance/schedule")
async def create_maintenance_schedule(request: Request):
    db = get_db()
    user = get_user(request)
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    if not body.get("title") or not body.get("scheduled_date"):
        raise HTTPException(400, "title and scheduled_date are required")
    entry = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "title": body["title"],
        "description": body.get("description", ""),
        "scheduled_date": body["scheduled_date"],
        "recurrence": body.get("recurrence", "one_time"),  # one_time, weekly, monthly, quarterly, annual
        "category": body.get("category", "other"),
        "assigned_to": body.get("assigned_to", ""),
        "vendor_id": body.get("vendor_id", ""),
        "status": "scheduled",  # scheduled, in_progress, done, skipped
        "created_by": user["id"],
        "created_by_name": user.get("name", ""),
        "notes": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })
    await db.maintenance_schedule.insert_one(entry)
    await _write_audit(db, "maintenance_schedule_create", "maintenance_schedule", entry["id"], user, {"title": entry["title"]})
    return {"success": True, "data": {k: v for k, v in entry.items() if k != "_id"}}


@router.patch("/maintenance/schedule/{entry_id}")
async def update_maintenance_schedule(entry_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    bid = user.get("branch_id")
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    # branch-scope: intentional - schedule records are school-wide (branch_id may be None on seeded data)
    existing = await db.maintenance_schedule.find_one(scoped_query({"id": entry_id}, branch_id=None))
    if not existing:
        raise HTTPException(404, "Schedule entry not found")
    updates = {"updated_at": datetime.now().isoformat()}
    for field in ("title", "description", "scheduled_date", "recurrence", "category", "assigned_to", "vendor_id", "status"):
        if field in body:
            updates[field] = body[field]
    await db.maintenance_schedule.update_one(scoped_query({"id": entry_id}, branch_id=None), {"$set": updates})
    if updates.get("status") in {"done", "skipped"} and existing.get("recurrence") not in (None, "", "one_time"):
        next_date = _next_scheduled_date(existing.get("scheduled_date", ""), existing.get("recurrence", ""))
        if next_date:
            next_entry = {
                **{k: v for k, v in existing.items() if k != "_id"},
                "_id": str(uuid.uuid4()),
                "id": str(uuid.uuid4()),
                "scheduled_date": next_date,
                "status": "scheduled",
                "previous_entry_id": entry_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            await db.maintenance_schedule.insert_one(add_school_id(next_entry))
    await _write_audit(db, "maintenance_schedule_update", "maintenance_schedule", entry_id, user, {"changes": updates})
    updated = await db.maintenance_schedule.find_one(scoped_query({"id": entry_id}, branch_id=None), {"_id": 0})
    return {"success": True, "data": updated}


# ─── Vendor Log ───────────────────────────────────────────────────────────────

@router.get("/maintenance/vendors")
async def list_vendors(request: Request, page: int = 1, limit: int = 20):
    db = get_db()
    user = get_user(request)
    bid = user.get("branch_id")
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    page = clamp_page(page)
    limit = clamp_page_size(limit)
    skip = (page - 1) * limit
    total = await db.maintenance_vendors.count_documents(scoped_query({}, branch_id=bid))
    items = await db.maintenance_vendors.find(scoped_query({}, branch_id=bid), {"_id": 0}).sort("name", 1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@router.get("/maintenance/vendors/preferred")
async def preferred_vendors(request: Request, category: str = None, limit: int = 5):
    db = get_db()
    user = get_user(request)
    bid = user.get("branch_id")
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    query = {"is_active": True}
    if category:
        query["category"] = category
    vendors = await db.maintenance_vendors.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("rating", -1).limit(clamp_page_size(limit, 20)).to_list(20)
    return {"success": True, "data": vendors}


@router.post("/maintenance/vendors")
async def create_vendor(request: Request):
    db = get_db()
    user = get_user(request)
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    if not body.get("name"):
        raise HTTPException(400, "name is required")
    vendor = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "name": body["name"],
        "category": body.get("category", "general"),  # plumbing, electrical, civil, general, etc.
        "contact_person": body.get("contact_person", ""),
        "phone": body.get("phone", ""),
        "email": body.get("email", ""),
        "address": body.get("address", ""),
        "gst_number": body.get("gst_number", ""),
        "rating": body.get("rating", 0),  # 0–5
        "tags": body.get("tags", []),
        "is_active": True,
        "added_by": user["id"],
        "added_by_name": user.get("name", ""),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })
    await db.maintenance_vendors.insert_one(vendor)
    await _write_audit(db, "vendor_create", "maintenance_vendors", vendor["id"], user, {"name": vendor["name"]})
    return {"success": True, "data": {k: v for k, v in vendor.items() if k != "_id"}}


@router.patch("/maintenance/vendors/{vendor_id}")
async def update_vendor(vendor_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    bid = user.get("branch_id")
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    # branch-scope: intentional - vendor records are school-wide (branch_id may be None on seeded data)
    existing = await db.maintenance_vendors.find_one(scoped_query({"id": vendor_id}, branch_id=None))
    if not existing:
        raise HTTPException(404, "Vendor not found")
    updates = {"updated_at": datetime.now().isoformat()}
    for field in ("name", "category", "contact_person", "phone", "email", "address", "gst_number", "rating", "tags", "is_active"):
        if field in body:
            updates[field] = body[field]
    await db.maintenance_vendors.update_one(scoped_query({"id": vendor_id}, branch_id=None), {"$set": updates})
    await _write_audit(db, "vendor_update", "maintenance_vendors", vendor_id, user, {"changes": updates})
    updated = await db.maintenance_vendors.find_one(scoped_query({"id": vendor_id}, branch_id=None), {"_id": 0})
    return {"success": True, "data": updated}
