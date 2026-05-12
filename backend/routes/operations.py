"""Routes: certificates, expenses, complaints, visitors, assets, transport, announcements"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from middleware.auth import get_current_user
from datetime import datetime
from tenant import get_school_id, scoped_filter
import uuid

router = APIRouter(prefix="/api/ops", tags=["operations"])
workflow_router = APIRouter(prefix="/api/operations", tags=["operations-workflow"])


def get_user(req: Request):
    return get_current_user(req)


def _can_decide(user: dict) -> bool:
    return user.get("role") == "owner" or (user.get("role") == "admin" and user.get("sub_category", "principal") == "principal")


def _audit_doc(action: str, entity_type: str, entity_id: str, user: dict, changes: dict, reason: str = None):
    return {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "changed_by": user.get("id"),
        "changed_by_role": user.get("role"),
        "changes": changes,
        "reason": reason,
        "created_at": datetime.now().isoformat(),
    }


async def _notify(db, *, user_id: str, notification_type: str, message: str, source_id: str, source_type: str):
    await db.notifications.insert_one({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "user_id": user_id,
        "type": notification_type,
        "message": message,
        "source_record_id": source_id,
        "source_record_type": source_type,
        "read": False,
        "created_at": datetime.now().isoformat(),
    })


@workflow_router.post("/leave-requests")
async def create_leave_request(request: Request):
    db = get_db()
    user = get_user(request)
    body = await request.json()
    if body.get("user_id") and body.get("user_id") != user["id"]:
        raise HTTPException(403, "Cannot submit leave on behalf of another user")
    if not body.get("date_range") or not body.get("leave_type") or not body.get("reason"):
        raise HTTPException(400, "date_range, leave_type, and reason are required")
    staff = await db.staff.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()), {"_id": 0})
    if not staff:
        raise HTTPException(404, "Staff profile not found")
    leave = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "staff_id": staff["id"],
        "user_id": user["id"],
        "date_range": body["date_range"],
        "start_date": body["date_range"].get("start"),
        "end_date": body["date_range"].get("end"),
        "leave_type": body["leave_type"],
        "reason": body["reason"],
        "status": "pending",
        "applied_at": datetime.now().isoformat(),
    }
    await db.leave_requests.insert_one(leave)
    await db.audit_logs.insert_one(_audit_doc("leave_submit", "leave_request", leave["id"], user, {"created": {k: v for k, v in leave.items() if k != "_id"}}))
    return {"success": True, "data": {k: v for k, v in leave.items() if k != "_id"}}


@workflow_router.get("/leave-requests")
async def list_leave_requests(request: Request, status: str = None, page: int = 1, limit: int = 20):
    db = get_db()
    user = get_user(request)
    query = {"status": status} if status else {}
    if not _can_decide(user):
        query["user_id"] = user["id"]
    limit = min(max(limit, 1), 20)
    skip = max(page - 1, 0) * limit
    total = await db.leave_requests.count_documents(scoped_filter(query, get_school_id()))
    items = await db.leave_requests.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort("applied_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@workflow_router.patch("/leave-requests/{leave_id}/decide")
async def decide_leave_request(leave_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if not _can_decide(user):
        raise HTTPException(403, "Only Owner or Principal can decide leave requests")
    body = await request.json()
    if body.get("status") not in ("approved", "rejected") or not body.get("reason"):
        raise HTTPException(400, "status approved/rejected and reason are required")
    leave = await db.leave_requests.find_one(scoped_filter({"id": leave_id}, get_school_id()), {"_id": 0})
    if not leave:
        raise HTTPException(404, "Leave request not found")
    update = {
        "status": body["status"],
        "decision_reason": body["reason"],
        "decided_by": user["id"],
        "decided_at": datetime.now().isoformat(),
    }
    await db.leave_requests.update_one(scoped_filter({"id": leave_id}, get_school_id()), {"$set": update})
    if body["status"] == "approved":
        await db.staff_availability.update_one(
            scoped_filter({"staff_id": leave["staff_id"], "leave_request_id": leave_id}, get_school_id()),
            {"$set": {
                "staff_id": leave["staff_id"],
                "leave_request_id": leave_id,
                "status": "on_leave",
                "date_range": leave.get("date_range"),
                "schoolId": get_school_id(),
                "updated_at": datetime.now().isoformat(),
            }},
            upsert=True,
        )
    await db.audit_logs.insert_one(_audit_doc("leave_decide", "leave_request", leave_id, user, update, body["reason"]))
    await _notify(db, user_id=leave["user_id"], notification_type="leave_decision", message=f"Leave request {body['status']}", source_id=leave_id, source_type="leave_request")
    updated = await db.leave_requests.find_one(scoped_filter({"id": leave_id}, get_school_id()), {"_id": 0})
    return {"success": True, "data": updated}


@workflow_router.post("/approval-requests")
async def create_approval_request(request: Request):
    db = get_db()
    user = get_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Only Admin users can submit approval requests")
    body = await request.json()
    required = {"title", "description", "estimated_impact", "note", "routing"}
    if any(not body.get(field) for field in required):
        raise HTTPException(400, "title, description, estimated_impact, note, and routing are required")
    if body["routing"] not in ("owner_only", "owner_and_principal"):
        raise HTTPException(400, "routing must be owner_only or owner_and_principal")
    record = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "title": body["title"],
        "description": body["description"],
        "estimated_impact": body["estimated_impact"],
        "note": body["note"],
        "routing": body["routing"],
        "status": "pending",
        "submitted_by": user["id"],
        "submitted_at": datetime.now().isoformat(),
        "unread_for": ["owner"] + (["principal"] if body["routing"] == "owner_and_principal" else []),
    }
    await db.approval_requests.insert_one(record)
    await db.audit_logs.insert_one(_audit_doc("approval_submit", "approval_request", record["id"], user, {"created": {k: v for k, v in record.items() if k != "_id"}}))
    await _notify(db, user_id="owner", notification_type="approval_submitted", message=record["title"], source_id=record["id"], source_type="approval_request")
    if body["routing"] == "owner_and_principal":
        await _notify(db, user_id="principal", notification_type="approval_submitted", message=record["title"], source_id=record["id"], source_type="approval_request")
    return {"success": True, "data": {k: v for k, v in record.items() if k != "_id"}}


@workflow_router.get("/approval-requests")
async def list_approval_requests(request: Request, status: str = None):
    db = get_db()
    user = get_user(request)
    query = {"status": status} if status else {}
    if user.get("role") == "owner":
        pass
    elif user.get("role") == "admin" and user.get("sub_category", "principal") == "principal":
        query["routing"] = "owner_and_principal"
    else:
        query["submitted_by"] = user["id"]
    items = await db.approval_requests.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort("submitted_at", -1).to_list(100)
    role_key = "owner" if user.get("role") == "owner" else "principal"
    unread = sum(1 for item in items if role_key in item.get("unread_for", []))
    return {"success": True, "data": items, "meta": {"unread_count": unread}}


@workflow_router.patch("/approval-requests/{approval_id}/decide")
async def decide_approval_request(approval_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    body = await request.json()
    if body.get("status") not in ("approved", "rejected") or not body.get("reason"):
        raise HTTPException(400, "status approved/rejected and reason are required")
    approval = await db.approval_requests.find_one(scoped_filter({"id": approval_id}, get_school_id()), {"_id": 0})
    if not approval:
        raise HTTPException(404, "Approval request not found")
    principal = user.get("role") == "admin" and user.get("sub_category", "principal") == "principal"
    if user.get("role") != "owner" and not (principal and approval.get("routing") == "owner_and_principal"):
        raise HTTPException(403, "Not authorized to decide this approval request")
    update = {
        "status": body["status"],
        "decision_reason": body["reason"],
        "decided_by": user["id"],
        "decided_at": datetime.now().isoformat(),
        "unread_for": [],
    }
    await db.approval_requests.update_one(scoped_filter({"id": approval_id}, get_school_id()), {"$set": update})
    await db.audit_logs.insert_one(_audit_doc("approval_decide", "approval_request", approval_id, user, update, body["reason"]))
    await _notify(db, user_id=approval["submitted_by"], notification_type="approval_decision", message=f"{approval['title']} {body['status']}", source_id=approval_id, source_type="approval_request")
    updated = await db.approval_requests.find_one(scoped_filter({"id": approval_id}, get_school_id()), {"_id": 0})
    return {"success": True, "data": updated}


# --- Certificates ---
@router.get("/certificates")
async def list_certs(request: Request, student_id: str = None):
    db = get_db()
    user = get_user(request)
    query = {}
    if student_id:
        if user["role"] == "student":
            own = await db.students.find_one({"user_id": user["id"]})
            if not own or own["id"] != student_id:
                raise HTTPException(403, "Forbidden")
        query["student_id"] = student_id
    elif user["role"] == "student":
        own = await db.students.find_one({"user_id": user["id"]})
        if own:
            query["student_id"] = own["id"]
    certs = await db.certificates.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    for c in certs:
        s = await db.students.find_one({"id": c.get("student_id")}, {"_id": 0})
        c["student_name"] = s["name"] if s else "N/A"
    return {"success": True, "data": certs}


@router.post("/certificates")
async def create_cert(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    cert = {
        "id": str(uuid.uuid4()),
        "student_id": body.get("student_id"),
        "cert_type": body.get("cert_type", "bonafide"),
        "serial_number": f"CERT{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}",
        "content_data": body.get("content_data", {}),
        "status": "generated",
        "issued_date": datetime.now().strftime("%Y-%m-%d"),
        "issued_by": user["id"],
        "created_at": datetime.now().isoformat(),
    }
    await db.certificates.insert_one({**cert, "_id": cert["id"]})
    return {"success": True, "data": cert}


# --- Expenses ---
@router.get("/expenses")
async def list_expenses(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    expenses = await db.expenses.find({}, {"_id": 0}).sort("date", -1).to_list(100)
    return {"success": True, "data": expenses}


@router.post("/expenses")
async def create_expense(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    expense = {
        "id": str(uuid.uuid4()),
        "category": body.get("category"),
        "description": body.get("description", ""),
        "amount": float(body.get("amount", 0)),
        "date": body.get("date", datetime.now().strftime("%Y-%m-%d")),
        "vendor": body.get("vendor", ""),
        "approved_by": user["id"],
        "recorded_by": user["id"],
        "created_at": datetime.now().isoformat(),
    }
    await db.expenses.insert_one({**expense, "_id": expense["id"]})
    return {"success": True, "data": expense}


# --- Complaints ---
@router.get("/complaints")
async def list_complaints(request: Request):
    db = get_db()
    user = get_user(request)
    query = {}
    if user["role"] not in ["owner", "admin"]:
        query["submitted_by"] = user["id"]
    complaints = await db.complaints.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"success": True, "data": complaints}


@router.post("/complaints")
async def create_complaint(request: Request):
    db = get_db()
    user = get_user(request)
    body = await request.json()
    complaint = {
        "id": str(uuid.uuid4()),
        "submitted_by": user["id"],
        "subject": body.get("subject"),
        "description": body.get("description"),
        "category": body.get("category", "other"),
        "priority": body.get("priority", "normal"),
        "status": "open",
        "created_at": datetime.now().isoformat(),
    }
    await db.complaints.insert_one({**complaint, "_id": complaint["id"]})
    return {"success": True, "data": complaint}


@router.patch("/complaints/{complaint_id}")
async def update_complaint(complaint_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    await db.complaints.update_one({"id": complaint_id}, {"$set": body})
    return {"success": True}


# --- Visitors ---
@router.get("/visitors")
async def list_visitors(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    visitors = await db.visitor_log.find({}, {"_id": 0}).sort("time_in", -1).to_list(50)
    return {"success": True, "data": visitors}


@router.post("/visitors")
async def log_visitor(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    visitor = {
        "id": str(uuid.uuid4()),
        "visitor_name": body.get("visitor_name"),
        "phone": body.get("phone", ""),
        "purpose": body.get("purpose"),
        "whom_to_meet": body.get("whom_to_meet", ""),
        "id_type": body.get("id_type", ""),
        "time_in": datetime.now().isoformat(),
        "time_out": None,
    }
    await db.visitor_log.insert_one({**visitor, "_id": visitor["id"]})
    return {"success": True, "data": visitor}


@router.patch("/visitors/{visitor_id}/checkout")
async def checkout_visitor(visitor_id: str, request: Request):
    db = get_db()
    await db.visitor_log.update_one({"id": visitor_id}, {"$set": {"time_out": datetime.now().isoformat()}})
    return {"success": True}


# --- Assets ---
@router.get("/assets")
async def list_assets(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    assets = await db.assets.find({}, {"_id": 0}).to_list(100)
    return {"success": True, "data": assets}


@router.post("/assets")
async def create_asset(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    asset = {
        "id": str(uuid.uuid4()),
        "name": body.get("name"),
        "category": body.get("category", ""),
        "quantity": int(body.get("quantity", 1)),
        "location": body.get("location", ""),
        "status": body.get("status", "good"),
        "purchase_date": body.get("purchase_date", ""),
        "maintenance_due": body.get("maintenance_due", ""),
    }
    await db.assets.insert_one({**asset, "_id": asset["id"]})
    return {"success": True, "data": asset}


@router.patch("/assets/{asset_id}")
async def update_asset(asset_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    await db.assets.update_one({"id": asset_id}, {"$set": body})
    return {"success": True}


# --- Transport ---
@router.get("/transport")
async def list_transport(request: Request):
    db = get_db()
    routes = await db.transport_routes.find({}, {"_id": 0}).to_list(50)
    return {"success": True, "data": routes}


@router.post("/transport")
async def create_route(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    route = {
        "id": str(uuid.uuid4()),
        "route_name": body.get("route_name"),
        "start_point": body.get("start_point", ""),
        "end_point": body.get("end_point", ""),
        "stops": body.get("stops", []),
        "driver_name": body.get("driver_name", ""),
        "driver_phone": body.get("driver_phone", ""),
        "vehicle_no": body.get("vehicle_no", ""),
        "capacity": body.get("capacity", ""),
        "fare": body.get("fare", ""),
        "is_active": True,
    }
    await db.transport_routes.insert_one({**route, "_id": route["id"]})
    return {"success": True, "data": route}


@router.patch("/transport/{route_id}")
async def update_route(route_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    await db.transport_routes.update_one({"id": route_id}, {"$set": body})
    route = await db.transport_routes.find_one({"id": route_id}, {"_id": 0})
    return {"success": True, "data": route}


@router.delete("/transport/{route_id}")
async def delete_route(route_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    await db.transport_routes.delete_one({"id": route_id})
    return {"success": True}


@router.post("/study-plan")
async def save_study_plan(request: Request):
    db = get_db()
    user = get_user(request)
    body = await request.json()
    from datetime import datetime as dt
    await db.study_plans.update_one(
        {"user_id": user["id"]},
        {"$set": {**body, "user_id": user["id"], "updated_at": dt.now().isoformat()}},
        upsert=True
    )
    return {"success": True}


@router.patch("/expenses/{expense_id}")
async def update_expense(expense_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json(); body.pop("id", None)
    await db.expenses.update_one({"id": expense_id}, {"$set": body})
    return {"success": True}


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    await db.expenses.delete_one({"id": expense_id})
    return {"success": True}


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    await db.assets.delete_one({"id": asset_id})
    return {"success": True}


@router.delete("/announcements/{ann_id}")
async def delete_announcement(ann_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    await db.announcements.delete_one({"id": ann_id})
    return {"success": True}


@router.delete("/visitors/{visitor_id}")
async def delete_visitor(visitor_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    await db.visitor_log.delete_one({"id": visitor_id})
    return {"success": True}


# --- Announcements ---
@router.get("/announcements")
async def list_announcements(request: Request):
    db = get_db()
    announcements = await db.announcements.find({"is_draft": False}, {"_id": 0}).sort("created_at", -1).to_list(30)
    return {"success": True, "data": announcements}


@router.post("/announcements")
async def create_announcement(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    announcement = {
        "id": str(uuid.uuid4()),
        "title": body.get("title"),
        "content": body.get("content"),
        "audience_type": body.get("audience_type", "all"),
        "audience_classes": body.get("audience_classes", []),
        "audience_roles": body.get("audience_roles", []),
        "channels": body.get("channels", ["push"]),
        "is_draft": body.get("is_draft", False),
        "sent_at": datetime.now().isoformat() if not body.get("is_draft", False) else None,
        "created_by": user["id"],
        "created_at": datetime.now().isoformat(),
    }
    await db.announcements.insert_one({**announcement, "_id": announcement["id"]})
    return {"success": True, "data": announcement}


# --- Enquiries ---
@router.get("/enquiries")
async def list_enquiries(request: Request, status: str = None):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    query = {}
    if status:
        query["status"] = status
    enquiries = await db.enquiries.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"success": True, "data": enquiries}


@router.post("/enquiries")
async def create_enquiry(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    enquiry = {
        "id": str(uuid.uuid4()),
        "student_name": body.get("student_name"),
        "parent_name": body.get("parent_name"),
        "phone": body.get("phone"),
        "class_applying": body.get("class_applying", ""),
        "status": "new",
        "source": body.get("source", "walk_in"),
        "assigned_to": user["id"],
        "created_at": datetime.now().isoformat(),
    }
    await db.enquiries.insert_one({**enquiry, "_id": enquiry["id"]})
    return {"success": True, "data": enquiry}


@router.patch("/enquiries/{enquiry_id}")
async def update_enquiry(enquiry_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    await db.enquiries.update_one({"id": enquiry_id}, {"$set": body})
    return {"success": True}


# --- Leave (teacher self-apply) ---
@router.post("/leaves")
async def apply_leave(request: Request):
    db = get_db()
    user = get_user(request)
    body = await request.json()
    staff = await db.staff.find_one({"user_id": user["id"]})
    if not staff:
        # Create a minimal staff record for this teacher if not found
        from datetime import datetime as dt
        import uuid
        staff_id = str(uuid.uuid4())
        await db.staff.insert_one({
            "_id": staff_id, "id": staff_id, "user_id": user["id"],
            "name": user.get("name", "Staff"), "staff_type": "teacher",
            "is_active": True, "created_at": dt.now().isoformat(),
        })
        staff = {"id": staff_id}
    from datetime import datetime as dt
    import uuid
    leave = {
        "id": str(uuid.uuid4()),
        "staff_id": staff["id"],
        "user_id": user["id"],
        "leave_type": body.get("leave_type", "casual"),
        "start_date": body.get("start_date"),
        "end_date": body.get("end_date"),
        "reason": body.get("reason"),
        "status": "pending",
        "applied_at": dt.now().isoformat(),
    }
    await db.leave_requests.insert_one({**leave, "_id": leave["id"]})
    return {"success": True, "data": leave}


# --- Study Planner ---
@router.get("/study-plan")
async def get_study_plan(request: Request):
    db = get_db()
    user = get_user(request)
    plan = await db.study_plans.find_one({"user_id": user["id"]}, {"_id": 0})
    if not plan:
        return {"success": True, "data": {"monday": "", "tuesday": "", "wednesday": "", "thursday": "", "friday": "", "saturday": ""}}
    return {"success": True, "data": plan}
