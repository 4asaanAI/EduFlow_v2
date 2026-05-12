"""Issue tracker — facility requests (Maintenance Admin) and tech requests (IT/Tech Admin)"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from middleware.auth import get_current_user
from tenant import get_school_id, scoped_filter, add_school_id
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/issues", tags=["issues"])


def get_user(req: Request):
    return get_current_user(req)


FACILITY_CATEGORIES = {"plumbing", "electrical", "civil", "cleaning", "security", "other"}
VALID_STATUSES = {"open", "in_progress", "pending_owner_confirmation", "closed"}


def _can_view_all(user: dict) -> bool:
    return user.get("role") in ("owner",) or (
        user.get("role") == "admin" and user.get("sub_category") in ("principal", None)
    )


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


async def _notify(db, *, user_id: str, notification_type: str, message: str, source_id: str, source_type: str):
    await db.notifications.insert_one(add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notification_type,
        "message": message,
        "source_record_id": source_id,
        "source_record_type": source_type,
        "read": False,
        "created_at": datetime.now().isoformat(),
    }))


# ─── Facility Requests (Maintenance Admin) ────────────────────────────────────

@router.post("/facility")
async def create_facility_request(request: Request):
    db = get_db()
    user = get_user(request)
    if not (user.get("role") == "admin" and user.get("sub_category") == "maintenance") and user.get("role") != "owner":
        raise HTTPException(403, "Only Maintenance Admin or Owner can create facility requests")
    body = await request.json()
    if not body.get("description"):
        raise HTTPException(400, "description is required")
    cat = body.get("category", "other")
    if cat not in FACILITY_CATEGORIES:
        raise HTTPException(400, f"category must be one of {sorted(FACILITY_CATEGORIES)}")
    req_doc = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "type": "facility",
        "description": body["description"],
        "location": body.get("location", ""),
        "category": cat,
        "status": "open",
        "logged_by": user["id"],
        "logged_by_name": user.get("name", ""),
        "notes": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })
    await db.facility_requests.insert_one(req_doc)
    await db.audit_logs.insert_one(_audit("facility_request_create", "facility_requests", req_doc["id"], user, {"created": req_doc["description"]}))
    return {"success": True, "data": {k: v for k, v in req_doc.items() if k != "_id"}}


@router.get("/facility")
async def list_facility_requests(request: Request, status: str = None, page: int = 1, limit: int = 20):
    db = get_db()
    user = get_user(request)
    is_maint = user.get("role") == "admin" and user.get("sub_category") == "maintenance"
    if user.get("role") == "admin" and user.get("sub_category") == "it_tech":
        raise HTTPException(403, "IT/Tech Admin cannot access facility requests")
    if not _can_view_all(user) and not is_maint:
        raise HTTPException(403, "Forbidden")
    query = {}
    if status:
        query["status"] = status
    if is_maint:
        query["logged_by"] = user["id"]
    limit = min(max(limit, 1), 50)
    skip = max(page - 1, 0) * limit
    total = await db.facility_requests.count_documents(scoped_filter(query, get_school_id()))
    items = await db.facility_requests.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@router.patch("/facility/{request_id}")
async def update_facility_request(request_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    is_maint = user.get("role") == "admin" and user.get("sub_category") == "maintenance"
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
            raise HTTPException(403, "Maintenance Admin cannot close a request — Owner must confirm resolution")
        updates["status"] = new_status
    if body.get("note"):
        note_entry = {
            "id": str(uuid.uuid4()),
            "author_id": user["id"],
            "author_name": user.get("name", ""),
            "content": body["note"],
            "timestamp": datetime.now().isoformat(),
        }
        await db.facility_requests.update_one({"id": request_id}, {"$push": {"notes": note_entry}})
    if updates:
        await db.facility_requests.update_one({"id": request_id}, {"$set": updates})
    await db.audit_logs.insert_one(_audit("facility_request_update", "facility_requests", request_id, user, {"changes": updates}))
    updated = await db.facility_requests.find_one({"id": request_id}, {"_id": 0})
    return {"success": True, "data": updated}


@router.post("/facility/{request_id}/confirm-resolution")
async def confirm_facility_resolution(request_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user.get("role") != "owner":
        raise HTTPException(403, "Only Owner can confirm resolution")
    existing = await db.facility_requests.find_one(scoped_filter({"id": request_id}, get_school_id()))
    if not existing:
        raise HTTPException(404, "Facility request not found")
    if existing.get("status") != "pending_owner_confirmation":
        raise HTTPException(400, "Request must be in pending_owner_confirmation status")
    await db.facility_requests.update_one(
        {"id": request_id},
        {"$set": {"status": "closed", "resolved_by": user["id"], "resolved_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()}}
    )
    # Notify the maintenance admin who logged it
    await _notify(db, user_id=existing["logged_by"], notification_type="facility_resolved",
                  message=f"Your facility request has been resolved and closed by the Owner.",
                  source_id=request_id, source_type="facility_request")
    await db.audit_logs.insert_one(_audit("facility_request_close", "facility_requests", request_id, user, {"status": "closed"}))
    return {"success": True, "message": "Facility request closed and maintenance admin notified"}


# ─── Tech Requests (IT/Tech Admin) ────────────────────────────────────────────

@router.post("/tech")
async def create_tech_request(request: Request):
    db = get_db()
    user = get_user(request)
    if not (user.get("role") == "admin" and user.get("sub_category") == "it_tech") and user.get("role") != "owner":
        raise HTTPException(403, "Only IT/Tech Admin or Owner can create tech requests")
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
    await db.audit_logs.insert_one(_audit("tech_request_create", "tech_requests", req_doc["id"], user, {"created": req_doc["description"]}))
    return {"success": True, "data": {k: v for k, v in req_doc.items() if k != "_id"}}


@router.get("/tech")
async def list_tech_requests(request: Request, status: str = None, page: int = 1, limit: int = 20):
    db = get_db()
    user = get_user(request)
    is_it = user.get("role") == "admin" and user.get("sub_category") == "it_tech"
    if user.get("role") == "admin" and user.get("sub_category") == "maintenance":
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
    is_it = user.get("role") == "admin" and user.get("sub_category") == "it_tech"
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
        await db.tech_requests.update_one({"id": request_id}, {"$push": {"notes": note_entry}})
    if updates:
        await db.tech_requests.update_one({"id": request_id}, {"$set": updates})
    await db.audit_logs.insert_one(_audit("tech_request_update", "tech_requests", request_id, user, {"changes": updates}))
    updated = await db.tech_requests.find_one({"id": request_id}, {"_id": 0})
    return {"success": True, "data": updated}


# ─── Merged view (Owner / Principal) ─────────────────────────────────────────

@router.get("")
async def list_all_issues(request: Request, type: str = "all", status: str = None, page: int = 1, limit: int = 50):
    db = get_db()
    user = get_user(request)
    if not _can_view_all(user):
        raise HTTPException(403, "Only Owner or Principal can view all issues")
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
