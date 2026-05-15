from __future__ import annotations

"""Issue tracker — facility requests (Maintenance Admin) and tech requests (IT/Tech Admin)"""
from fastapi import APIRouter, Request, HTTPException, Depends
from database import get_db
from middleware.auth import get_current_user, require_owner, require_access
from services.audit_service import write_audit_doc
from services.notification_service import create_notification, fan_out_notifications
from tenant import get_school_id, scoped_filter, add_school_id
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/issues", tags=["issues"])


def get_user(req: Request):
    return get_current_user(req)


FACILITY_CATEGORIES = {
    "plumbing", "electrical", "civil", "cleaning", "security", "carpentry",
    "painting", "pest_control", "hvac", "fire_safety", "landscaping", "other",
}
VALID_STATUSES = {"open", "accepted", "in_progress", "pending_parts", "pending_owner_confirmation", "done", "closed"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}


def _can_view_all(user: dict) -> bool:
    """Owner and principal can see all requests; generic admins (no sub_category) can too."""
    return user.get("role") in ("owner",) or (
        user.get("role") == "admin" and user.get("sub_category") in ("principal", None)
    )


def _is_maint(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "maintenance"


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
    scoped_q = scoped_filter(query, get_school_id())
    return await users.find(scoped_q, projection).to_list(limit)


# ─── Facility Requests (Maintenance Admin) ────────────────────────────────────

@router.post("/facility")
async def create_facility_request(request: Request):
    db = get_db()
    user = get_user(request)
    # Allow: maintenance admin, owner, teacher, or any staff raising a request
    role = user.get("role")
    sub = user.get("sub_category")
    allowed = role in ("owner", "teacher") or (role == "admin" and sub in ("maintenance", "principal", "receptionist", None))
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
        "photos": [u for u in body.get("photos", []) if isinstance(u, str)][:3],
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

    msg = f"New maintenance request [{priority.upper()}]: {req_doc['description'][:80]} @ {req_doc['location']} — raised by {user.get('name', 'Staff')}."
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
async def list_facility_requests(request: Request, status: str = None, priority: str = None, category: str = None, page: int = 1, limit: int = 20):
    db = get_db()
    user = get_user(request)
    is_maintenance = _is_maint(user)
    if user.get("role") == "admin" and user.get("sub_category") == "it_tech":
        raise HTTPException(403, "IT/Tech Admin cannot access facility requests")
    # Teachers/staff who raised requests can see their own
    is_self_only = user.get("role") in ("teacher",) or (
        user.get("role") == "admin" and user.get("sub_category") in ("receptionist",)
    )
    if not _can_view_all(user) and not is_maintenance and not is_self_only:
        raise HTTPException(403, "Forbidden")
    query = {}
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    if category:
        query["category"] = category
    # Self-view: teachers/receptionist see only their own requests
    if is_self_only:
        query["logged_by"] = user["id"]
    # Maintenance admin sees ALL school facility requests (not filtered to self)
    limit = min(max(limit, 1), 100)
    skip = max(page - 1, 0) * limit
    total = await db.facility_requests.count_documents(scoped_filter(query, get_school_id()))
    items = await db.facility_requests.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort([("priority", 1), ("created_at", -1)]).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@router.patch("/facility/{request_id}")
async def update_facility_request(request_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    is_maint = _is_maint(user)
    if not is_maint and not _can_view_all(user):
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    existing = await db.facility_requests.find_one(scoped_filter({"id": request_id}, get_school_id()))
    if not existing:
        raise HTTPException(404, "Facility request not found")
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
        await db.facility_requests.update_one(scoped_filter({"id": request_id}, get_school_id()), {"$push": {"notes": note_entry}})
    if updates:
        await db.facility_requests.update_one(scoped_filter({"id": request_id}, get_school_id()), {"$set": updates})
    await _write_audit(db, "facility_request_update", "facility_requests", request_id, user, {"changes": updates})
    updated = await db.facility_requests.find_one(scoped_filter({"id": request_id}, get_school_id()), {"_id": 0})
    return {"success": True, "data": updated}


@router.post("/facility/{request_id}/confirm-resolution")
async def confirm_facility_resolution(request_id: str, request: Request, user: dict = Depends(require_owner)):
    db = get_db()
    existing = await db.facility_requests.find_one(scoped_filter({"id": request_id}, get_school_id()))
    if not existing:
        raise HTTPException(404, "Facility request not found")
    if existing.get("status") != "pending_owner_confirmation":
        raise HTTPException(400, "Request must be in pending_owner_confirmation status")
    await db.facility_requests.update_one(
        scoped_filter({"id": request_id}, get_school_id()),
        {"$set": {"status": "closed", "resolved_by": user["id"], "resolved_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()}}
    )
    # Notify the maintenance admin who logged it
    await create_notification(
        db,
        user_id=existing["logged_by"],
        notification_type="facility_resolved",
        title="Facility request resolved",
        message=f"Your facility request has been resolved and closed by the Owner.",
        source_id=request_id,
        source_type="facility_request",
    )
    await _write_audit(db, "facility_request_close", "facility_requests", request_id, user, {"status": "closed"})
    return {"success": True, "message": "Facility request closed and maintenance admin notified"}


# ─── Tech Requests (IT/Tech Admin) ────────────────────────────────────────────

@router.post("/tech")
async def create_tech_request(
    request: Request,
    user: dict = Depends(require_access("owner", "admin", sub_category="it_tech")),
):
    db = get_db()
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


@router.get("/tech")
async def list_tech_requests(request: Request, status: str = None, page: int = 1, limit: int = 20):
    db = get_db()
    user = get_user(request)
    is_it = _is_it(user)
    if _is_maint(user):
        raise HTTPException(403, "Maintenance Admin cannot access tech requests")
    if not _can_view_all(user) and not is_it:
        raise HTTPException(403, "Forbidden")
    query = {}
    if status:
        query["status"] = status
    limit = min(max(limit, 1), 50)
    skip = max(page - 1, 0) * limit
    total = await db.tech_requests.count_documents(scoped_filter(query, get_school_id()))
    items = await db.tech_requests.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@router.patch("/tech/{request_id}")
async def update_tech_request(request_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    is_it = _is_it(user)
    if not is_it and not _can_view_all(user):
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    existing = await db.tech_requests.find_one(scoped_filter({"id": request_id}, get_school_id()))
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
        await db.tech_requests.update_one(scoped_filter({"id": request_id}, get_school_id()), {"$push": {"notes": note_entry}})
    if updates:
        await db.tech_requests.update_one(scoped_filter({"id": request_id}, get_school_id()), {"$set": updates})
    await _write_audit(db, "tech_request_update", "tech_requests", request_id, user, {"changes": updates})
    updated = await db.tech_requests.find_one(scoped_filter({"id": request_id}, get_school_id()), {"_id": 0})
    return {"success": True, "data": updated}


# ─── Merged view (Owner / Principal) ─────────────────────────────────────────

@router.get("")
async def list_all_issues(request: Request, type: str = "all", status: str = None, page: int = 1, limit: int = 50):
    db = get_db()
    user = get_user(request)
    if not _can_view_all(user):
        raise HTTPException(403, "Forbidden")
    query = {}
    if status:
        query["status"] = status
    limit = min(max(limit, 1), 50)
    skip = max(page - 1, 0) * limit
    results = []
    scoped = scoped_filter(query, get_school_id())
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


# ─── Maintenance Schedule ─────────────────────────────────────────────────────

@router.get("/maintenance/schedule")
async def list_maintenance_schedule(request: Request, page: int = 1, limit: int = 20):
    db = get_db()
    user = get_user(request)
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    limit = min(max(limit, 1), 100)
    skip = max(page - 1, 0) * limit
    total = await db.maintenance_schedule.count_documents(scoped_filter({}, get_school_id()))
    items = await db.maintenance_schedule.find(scoped_filter({}, get_school_id()), {"_id": 0}).sort("scheduled_date", 1).skip(skip).limit(limit).to_list(limit)
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
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    existing = await db.maintenance_schedule.find_one(scoped_filter({"id": entry_id}, get_school_id()))
    if not existing:
        raise HTTPException(404, "Schedule entry not found")
    updates = {"updated_at": datetime.now().isoformat()}
    for field in ("title", "description", "scheduled_date", "recurrence", "category", "assigned_to", "vendor_id", "status"):
        if field in body:
            updates[field] = body[field]
    await db.maintenance_schedule.update_one(scoped_filter({"id": entry_id}, get_school_id()), {"$set": updates})
    await _write_audit(db, "maintenance_schedule_update", "maintenance_schedule", entry_id, user, {"changes": updates})
    updated = await db.maintenance_schedule.find_one(scoped_filter({"id": entry_id}, get_school_id()), {"_id": 0})
    return {"success": True, "data": updated}


# ─── Vendor Log ───────────────────────────────────────────────────────────────

@router.get("/maintenance/vendors")
async def list_vendors(request: Request, page: int = 1, limit: int = 20):
    db = get_db()
    user = get_user(request)
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    limit = min(max(limit, 1), 100)
    skip = max(page - 1, 0) * limit
    total = await db.maintenance_vendors.count_documents(scoped_filter({}, get_school_id()))
    items = await db.maintenance_vendors.find(scoped_filter({}, get_school_id()), {"_id": 0}).sort("name", 1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


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
    if not _can_view_all(user) and not _is_maint(user):
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    existing = await db.maintenance_vendors.find_one(scoped_filter({"id": vendor_id}, get_school_id()))
    if not existing:
        raise HTTPException(404, "Vendor not found")
    updates = {"updated_at": datetime.now().isoformat()}
    for field in ("name", "category", "contact_person", "phone", "email", "address", "gst_number", "rating", "tags", "is_active"):
        if field in body:
            updates[field] = body[field]
    await db.maintenance_vendors.update_one(scoped_filter({"id": vendor_id}, get_school_id()), {"$set": updates})
    await _write_audit(db, "vendor_update", "maintenance_vendors", vendor_id, user, {"changes": updates})
    updated = await db.maintenance_vendors.find_one(scoped_filter({"id": vendor_id}, get_school_id()), {"_id": 0})
    return {"success": True, "data": updated}
