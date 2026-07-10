"""Routes: certificates, expenses, visitors, assets, transport, announcements, incidents"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Request, HTTPException
from database import get_db
from middleware.auth import get_current_user, require_owner_or_principal, require_role
from services.audit_service import write_audit_doc
from services.notification_service import create_notification, fan_out_notifications
from services.actor_context import actor_ctx_from_user
from services.incident_service import (
    add_thread_entry as svc_add_thread_entry,
    assign_followup as svc_assign_followup,
    create_incident as svc_create_incident,
    update_incident_status as svc_update_incident_status,
    IncidentValidationError,
    IncidentNotFoundError,
)
from services.expense_service import (
    create_expense as svc_create_expense,
    update_expense as svc_update_expense,
    delete_expense as svc_delete_expense,
    ExpenseValidationError,
    ExpenseNotFoundError,
)
from services.enquiry_service import (
    create_enquiry as svc_create_enquiry,
    update_enquiry as svc_update_enquiry,
    EnquiryValidationError,
    EnquiryNotFoundError,
    EnquiryConflictError,
)
from services.approvals_service import (
    decide_approval_request as decide_approval_request_service,
    ApprovalValidationError,
    ApprovalNotFoundError,
    ApprovalAuthorizationError,
)
from services.announcement_service import (
    decide_announcement_status,
    decide_announcement as svc_decide_announcement,
    delete_announcement as svc_delete_announcement,
    AnnouncementValidationError,
    AnnouncementNotFoundError,
    AnnouncementStateError,
)
from services.asset_service import (
    create_asset as svc_create_asset,
    update_asset as svc_update_asset,
    delete_asset as svc_delete_asset,
    AssetValidationError,
    AssetNotFoundError,
)
from services.visitor_service import (
    log_visitor as svc_log_visitor,
    checkout_visitor as svc_checkout_visitor,
    delete_visitor as svc_delete_visitor,
    VisitorValidationError,
    VisitorNotFoundError,
    VisitorDuplicateError,
    VisitorRateLimitError,
)
from services.certificate_service import (
    create_certificate as svc_create_certificate,
    approve_certificate as svc_approve_certificate,
    reject_certificate as svc_reject_certificate,
    CertificateValidationError,
    CertificateNotFoundError,
    CertificateStateError,
)
from services.transport_service import (
    create_route as svc_create_transport_route,
    update_route as svc_update_transport_route,
    delete_route as svc_delete_transport_route,
    create_vehicle as svc_create_vehicle,
    TransportValidationError,
    TransportNotFoundError,
    TransportConflictError,
)
from datetime import datetime, date as _date, timedelta
from tenant import get_school_id, scoped_filter, scoped_query, add_school_id
import uuid
import os
import re
from services.maps_service import geocode as _geocode_address, haversine_km as _haversine_km

router = APIRouter(prefix="/api/ops", tags=["operations"])
workflow_router = APIRouter(prefix="/api/operations", tags=["operations-workflow"])
transport_router = APIRouter(prefix="/api/transport", tags=["transport"])

def _can_decide(user: dict) -> bool:
    """Legacy predicate kept for in-file callers. New code uses
    `Depends(require_owner_or_principal)` from middleware.auth.

    NOTE: previously defaulted sub_category to 'principal' which silently
    promoted any admin row missing sub_category. Now strict.
    """
    return user.get("role") == "owner" or (
        user.get("role") == "admin" and user.get("sub_category") == "principal"
    )


def _require_owner_or_accountant(request: Request) -> dict:
    """P10.6: Allow owner regardless of sub_category, OR admin with sub_category in accounts/accountant."""
    user = get_current_user(request)
    if user.get("role") == "owner":
        return user
    if user.get("role") == "admin" and user.get("sub_category") in ("accounts", "accountant"):
        return user
    raise HTTPException(status_code=403, detail="Forbidden")


_ALL_ANNOUNCEMENT_ROLES = ["teacher", "student", "admin", "parent"]


def _announcement_target_roles(body: dict, audience_type: str | None = None) -> list[str]:
    audience_type = audience_type or body.get("audience_type", "all")
    explicit_roles = body.get("target_roles")
    if explicit_roles is None:
        explicit_roles = body.get("audience_roles")
    if audience_type == "all":
        return list(_ALL_ANNOUNCEMENT_ROLES)
    if audience_type == "class":
        return ["student"]
    return list(explicit_roles or [])


# Announcement moderation gate moved to services.announcement_service.decide_announcement_status
# (Story A.4) — the single source of truth shared by this route and the AI create_announcement tool.


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


async def _write_audit(db, action: str, entity_type: str, entity_id: str, user: dict, changes: dict, reason: str = None):
    await write_audit_doc(
        db,
        _audit_doc(action, entity_type, entity_id, user, changes, reason),
        school_id=get_school_id(),
        branch_id=user.get("branch_id"),
    )


def _is_principal(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "principal"


def _is_owner_or_principal_user(user: dict) -> bool:
    return user.get("role") == "owner" or _is_principal(user)


def _is_accounts(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") in ("accounts", "accountant")


def _is_receptionist(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "receptionist"


def _require_accounting(user: dict) -> None:
    if user.get("role") != "owner" and not _is_accounts(user):
        raise HTTPException(403, "Forbidden")


def _require_frontdesk(user: dict) -> None:
    if user.get("role") != "owner" and not _is_principal(user) and not _is_receptionist(user):
        raise HTTPException(403, "Forbidden")


@workflow_router.post("/leave-requests")
async def create_leave_request(request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
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
    await _write_audit(db, "leave_submit", "leave_request", leave["id"], user, {"created": {k: v for k, v in leave.items() if k != "_id"}})
    return {"success": True, "data": {k: v for k, v in leave.items() if k != "_id"}}


@workflow_router.get("/leave-requests")
async def list_leave_requests(request: Request, status: str = None, page: int = 1, limit: int = 20, user: dict = Depends(get_current_user)):
    db = get_db()
    query = {"status": status} if status else {}
    if not _can_decide(user):
        query["user_id"] = user["id"]
    limit = min(max(limit, 1), 20)
    skip = max(page - 1, 0) * limit
    # Branch-scoped for deciders (principal sees own branch; owner has no branch_id so sees all).
    # Non-deciders already have query["user_id"] set, so branch further scopes them correctly.
    bid = user.get("branch_id")
    total = await db.leave_requests.count_documents(scoped_query(query, branch_id=bid))
    items = await db.leave_requests.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("applied_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@workflow_router.patch("/leave-requests/{leave_id}/decide")
async def decide_leave_request(leave_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
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
    await _write_audit(db, "leave_decide", "leave_request", leave_id, user, update, body["reason"])
    await create_notification(
        db,
        user_id=leave["user_id"],
        notification_type="leave_decision",
        title="Leave request updated",
        message=f"Leave request {body['status']}",
        source_id=leave_id,
        source_type="leave_request",
    )
    updated = await db.leave_requests.find_one(scoped_filter({"id": leave_id}, get_school_id()), {"_id": 0})
    return {"success": True, "data": updated}


@workflow_router.post("/approval-requests")
async def create_approval_request(request: Request, user: dict = Depends(require_role("admin"))):
    db = get_db()
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
    await _write_audit(db, "approval_submit", "approval_request", record["id"], user, {"created": {k: v for k, v in record.items() if k != "_id"}})
    # Notify by role: find actual user IDs rather than sending to literal role strings
    owner_users = await db.users.find(scoped_filter({"role": "owner"}, get_school_id()), {"_id": 0, "id": 1}).to_list(5)
    await fan_out_notifications(
        db,
        [ou["id"] for ou in owner_users],
        notification_type="approval_submitted",
        title="Approval submitted",
        message=record["title"],
        source_id=record["id"],
        source_type="approval_request",
    )
    if body["routing"] == "owner_and_principal":
        principal_users = await db.users.find(scoped_filter({"role": "admin", "sub_category": "principal"}, get_school_id()), {"_id": 0, "id": 1}).to_list(5)
        await fan_out_notifications(
            db,
            [pu["id"] for pu in principal_users],
            notification_type="approval_submitted",
            title="Approval submitted",
            message=record["title"],
            source_id=record["id"],
            source_type="approval_request",
        )
    return {"success": True, "data": {k: v for k, v in record.items() if k != "_id"}}


@workflow_router.get("/approval-requests")
async def list_approval_requests(request: Request, status: str = None, user: dict = Depends(get_current_user)):
    db = get_db()
    query = {"status": status} if status else {}
    if user.get("role") == "owner":
        pass
    elif user.get("role") == "admin" and user.get("sub_category") == "principal":
        query["routing"] = "owner_and_principal"
    else:
        query["submitted_by"] = user["id"]
    # Branch-scoped: principal sees only their branch; owner (no branch_id) sees all.
    items = await db.approval_requests.find(scoped_query(query, branch_id=user.get("branch_id")), {"_id": 0}).sort("submitted_at", -1).to_list(100)
    role_key = "owner" if user.get("role") == "owner" else "principal"
    unread = sum(1 for item in items if role_key in item.get("unread_for", []))
    return {"success": True, "data": items, "meta": {"unread_count": unread}}


@workflow_router.patch("/approval-requests/{approval_id}/decide")
async def decide_approval_request(approval_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    body = await request.json()
    # auth: routing-dependent authorization is enforced inside the service
    # (owner decides any; principal only owner_and_principal) — record-level gate.
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    params = {"approval_id": approval_id, "status": body.get("status"), "reason": body.get("reason")}
    try:
        result = await decide_approval_request_service(db, actor_ctx, params)
    except ApprovalValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ApprovalAuthorizationError:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"success": True, "data": result["approval"]}


# --- Certificates ---
@router.get("/certificates")
async def list_certs(request: Request, student_id: str = None, user: dict = Depends(get_current_user)):
    db = get_db()
    bid = user.get("branch_id")
    query = {}
    if student_id:
        if user["role"] == "student":
            own = await db.students.find_one(scoped_query({"user_id": user["id"]}, branch_id=bid))
            if not own or own["id"] != student_id:
                raise HTTPException(403, "Forbidden")
        query["student_id"] = student_id
    elif user["role"] == "student":
        own = await db.students.find_one(scoped_query({"user_id": user["id"]}, branch_id=bid))
        if own:
            query["student_id"] = own["id"]
    certs = await db.certificates.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("created_at", -1).to_list(50)
    now = datetime.now()
    CERT_APPROVAL_SLA_HOURS = int(os.environ.get("CERT_APPROVAL_SLA_HOURS", "48"))
    for c in certs:
        s = await db.students.find_one(scoped_query({"id": c.get("student_id")}, branch_id=bid), {"_id": 0})
        c["student_name"] = s["name"] if s else "N/A"
        # Fix 5: mark overdue pending certs
        if c.get("status") == "pending_approval" and c.get("created_at"):
            try:
                created = datetime.fromisoformat(c["created_at"].replace("Z", ""))
                c["is_overdue"] = (now - created).total_seconds() / 3600 > CERT_APPROVAL_SLA_HOURS
            except (ValueError, AttributeError):
                c["is_overdue"] = False
        else:
            c["is_overdue"] = False
    return {"success": True, "data": certs}


@router.post("/certificates")
async def create_cert(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    # AD7 shared write path — same service as the AI `create_certificate` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_create_certificate(db, actor_ctx, body)
    except CertificateValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["certificate"]}


@router.patch("/certificates/{cert_id}/approve")
async def approve_cert(cert_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    # AD7 shared write path — same service as the AI `approve_certificate` tool.
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_approve_certificate(db, actor_ctx, {"cert_id": cert_id})
    except CertificateNotFoundError:
        raise HTTPException(404, "Certificate not found")
    except CertificateStateError as e:
        raise HTTPException(422, str(e))
    except CertificateValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["certificate"]}


@router.patch("/certificates/{cert_id}/reject")
async def reject_cert(cert_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    # AD7 shared write path — same service as the AI `reject_certificate` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_reject_certificate(db, actor_ctx, {"cert_id": cert_id, "reason": body.get("reason")})
    except CertificateNotFoundError:
        raise HTTPException(404, "Certificate not found")
    except CertificateStateError as e:
        raise HTTPException(422, str(e))
    except CertificateValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["certificate"]}


# --- Expenses ---
@router.get("/expenses/summary")
async def expense_summary(request: Request):
    """P10.6: Monthly and YTD expense breakdown by category (owner or accountant only)."""
    user = _require_owner_or_accountant(request)
    db = get_db()
    bid = user.get("branch_id")

    today = _date.today()
    month_start = today.strftime("%Y-%m-01")
    year_start = f"{today.year}-01-01"

    expenses = await db.expenses.find(
        scoped_query({}, branch_id=bid)
    ).to_list(1000)

    monthly: dict = {}
    ytd: dict = {}
    for e in expenses:
        cat = e.get("category", "Other")
        amt = e.get("amount", 0)
        if e.get("date", "") >= month_start:
            monthly[cat] = monthly.get(cat, 0) + amt
        if e.get("date", "") >= year_start:
            ytd[cat] = ytd.get(cat, 0) + amt

    return {"success": True, "data": {"monthly": monthly, "ytd": ytd}}


@router.get("/expenses")
async def list_expenses(request: Request, user: dict = Depends(_require_owner_or_accountant)):
    db = get_db()
    bid = user.get("branch_id")
    expenses = await db.expenses.find(scoped_query({}, branch_id=bid), {"_id": 0}).sort("date", -1).to_list(100)
    return {"success": True, "data": expenses}


@router.post("/expenses")
async def create_expense(request: Request, user: dict = Depends(_require_owner_or_accountant)):
    # AD7 shared write path — same service as the AI `create_expense` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_create_expense(db, actor_ctx, body)
    except ExpenseValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["expense"]}


# ─── Story 13: Incident Management (enhanced) ─────────────────────────────────

@router.get("/incidents")
async def list_incidents(request: Request, status: str = None, q: str = None, page: int = 1, limit: int = 20, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    bid = user.get("branch_id")
    query = {}
    if status:
        query["status"] = status
    if q:
        safe_q = re.escape(q)
        query["$or"] = [
            {"description": {"$regex": safe_q, "$options": "i"}},
            {"involved_parties": {"$regex": safe_q, "$options": "i"}},
        ]
    is_principal = user.get("role") == "admin" and user.get("sub_category") == "principal"
    if is_principal:
        query["category"] = {"$ne": "financial"}
    limit = min(max(limit, 1), 50)
    skip = max(page - 1, 0) * limit
    total = await db.incidents.count_documents(scoped_query(query, branch_id=bid))
    items = await db.incidents.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@router.post("/incidents")
async def create_incident(request: Request, user: dict = Depends(get_current_user)):
    # P9.8: Any authenticated user (teacher, admin, owner) may log incidents.
    # AD7 shared write path — same service as the AI `create_incident` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_create_incident(db, actor_ctx, body, fan_out_fn=fan_out_notifications)
    except IncidentValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["incident"]}


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    bid = user.get("branch_id")
    incident = await db.incidents.find_one(scoped_query({"id": incident_id}, branch_id=bid), {"_id": 0})
    if not incident:
        raise HTTPException(404, "Incident not found")
    thread = sorted(incident.get("thread", []), key=lambda x: x.get("timestamp", ""), reverse=True)
    incident["thread"] = thread
    return {"success": True, "data": incident}


@router.post("/incidents/{incident_id}/thread")
async def add_incident_thread(incident_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    # Story C.2: delegate to services.incident_service — the SAME write path as the AI
    # `add_thread_entry` tool (push entry + canonical 'add_thread_entry' audit).
    db = get_db()
    body = await request.json()
    if not body.get("content"):
        raise HTTPException(400, "content is required")
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_add_thread_entry(db, actor_ctx, {
            "record_type": "incidents", "record_id": incident_id, "content": body["content"],
        })
    except IncidentNotFoundError:
        raise HTTPException(404, "Incident not found")
    except IncidentValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["entry"]}


@router.patch("/incidents/{incident_id}/assign")
async def assign_incident(incident_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    # Story C.2: delegate to services.incident_service — the SAME write path as the AI
    # `assign_followup` tool (assignment fields + optional note + audit + assignee notify).
    db = get_db()
    body = await request.json()
    if not body.get("assigned_to") or not body.get("due_date"):
        raise HTTPException(400, "assigned_to and due_date are required")
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_assign_followup(db, actor_ctx, {
            "record_type": "incidents",
            "record_id": incident_id,
            "assignee_staff_id": body["assigned_to"],
            "due_date": body["due_date"],
            "note": body.get("note"),
            "status": body.get("status"),
        })
    except IncidentNotFoundError:
        raise HTTPException(404, "Incident not found")
    except IncidentValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


@router.patch("/incidents/{incident_id}")
async def update_incident(incident_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    """P9.8: Principal/owner can update status and add resolution note.

    Story C.3: delegate to services.incident_service.update_incident_status — the SAME
    write path as the AI `update_incident_status` tool (status transition + audit)."""
    db = get_db()
    body = await request.json()
    if not body.get("status") and not body.get("resolution_note"):
        raise HTTPException(400, "No update fields provided")
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_update_incident_status(db, actor_ctx, {
            "record_type": "incidents",
            "record_id": incident_id,
            "new_status": body.get("status"),
            "resolution_note": body.get("resolution_note"),
        })
    except IncidentNotFoundError:
        raise HTTPException(404, "Incident not found")
    except IncidentValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


# --- Visitors ---
@router.get("/visitors")
async def list_visitors(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    _require_frontdesk(user)
    db = get_db()
    bid = user.get("branch_id")
    # branch-scope: receptionist sees only own branch
    visitors = await db.visitor_log.find(scoped_query({}, branch_id=bid), {"_id": 0}).sort("time_in", -1).to_list(50)
    return {"success": True, "data": visitors}


@router.post("/visitors")
async def log_visitor(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    # AD7 shared write path — same service as the AI `log_visitor` tool.
    _require_frontdesk(user)
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_log_visitor(db, actor_ctx, body)
    except VisitorDuplicateError as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content={
            "success": False, "duplicate": True,
            "existing_id": e.existing_id,
            "detail": str(e),
        })
    except VisitorRateLimitError as e:
        raise HTTPException(429, str(e))
    except VisitorValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["visitor"]}


@router.patch("/visitors/{visitor_id}/checkout")
async def checkout_visitor(visitor_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    # AD7 shared write path — same service as the AI `checkout_visitor` tool.
    _require_frontdesk(user)
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_checkout_visitor(db, actor_ctx, {"visitor_id": visitor_id})
    except VisitorNotFoundError:
        raise HTTPException(404, "Visitor not found")
    except VisitorValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


# --- Assets ---
def _is_owner_or_principal(user: dict) -> bool:
    """Returns True if user is owner, or admin with principal sub_category."""
    return user.get("role") == "owner" or (
        user.get("role") == "admin" and user.get("sub_category") == "principal"
    )


@router.get("/assets")
async def list_assets(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    bid = user.get("branch_id")
    base_query: dict = {}
    # Non-principal admin sub-roles only see assets they created
    if not _is_owner_or_principal(user):
        base_query["created_by"] = user.get("id")
    assets = await db.assets.find(scoped_query(base_query, branch_id=bid), {"_id": 0}).to_list(100)
    return {"success": True, "data": assets}


@router.post("/assets")
async def create_asset(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    # AD7 shared write path — same service as the AI `create_asset` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_create_asset(db, actor_ctx, body)
    except AssetValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["asset"]}


@router.patch("/assets/{asset_id}")
async def update_asset(asset_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    # AD7 shared write path — same service as the AI `update_asset` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_update_asset(db, actor_ctx, {**body, "asset_id": asset_id})
    except AssetNotFoundError:
        raise HTTPException(404, "Asset not found")
    except AssetValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


# --- Transport ---
@router.get("/transport")
@transport_router.get("")
async def list_transport(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    bid = user.get("branch_id")
    routes = await db.transport_routes.find(scoped_query({}, branch_id=bid), {"_id": 0}).to_list(50)
    # Enrich with student count per zone
    for route in routes:
        count = await db.students.count_documents(scoped_query({"route_zone_id": route.get("id"), "is_active": {"$ne": False}}, branch_id=bid))
        route["student_count"] = count
    return {"success": True, "data": routes}


@router.post("/transport")
@transport_router.post("")
async def create_route(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    # AD7 shared write path — same service as the AI `create_transport_route` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_create_transport_route(db, actor_ctx, body)
    except TransportValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["route"]}


@router.get("/transport/roster")
@transport_router.get("/roster")
async def get_transport_roster(request: Request, zone_id: str = None, user: dict = Depends(require_role("owner", "admin"))):
    """Owner/Principal: full roster. Transport Head: zone-specific."""
    db = get_db()
    bid = user.get("branch_id")
    query = {"is_active": {"$ne": False}}
    if zone_id:
        query["route_zone_id"] = zone_id
    students = await db.students.find(scoped_query(query, branch_id=bid), {"_id": 0, "name": 1, "class_name": 1, "guardian_phone": 1, "route_zone_id": 1}).to_list(500)
    zones = await db.transport_routes.find(scoped_query({}, branch_id=bid), {"_id": 0, "id": 1, "route_name": 1}).to_list(50)
    zone_map = {z["id"]: z["route_name"] for z in zones}
    for s in students:
        s["zone_name"] = zone_map.get(s.get("route_zone_id", ""), "Not Assigned")
    return {"success": True, "data": students, "meta": {"total": len(students)}}


@router.post("/transport/vehicles")
@transport_router.post("/vehicles")
async def create_vehicle(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    # AD7 shared write path — same service as the AI `add_transport_vehicle` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_create_vehicle(db, actor_ctx, body)
    except TransportValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["vehicle"]}


@router.get("/transport/vehicles")
@transport_router.get("/vehicles")
async def list_vehicles(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    bid = user.get("branch_id")
    vehicles = await db.vehicles.find(scoped_query({}, branch_id=bid), {"_id": 0}).to_list(50)
    return {"success": True, "data": vehicles}


@router.post("/transport/zones")
@transport_router.post("/zones")
async def create_zone(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    """Alias: zones map to transport routes with zone semantics (AD7 shared service)."""
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    params = {"route_name": body.get("name") or body.get("route_name", ""),
              "description": body.get("description", ""), "fare": body.get("fare", 0)}
    try:
        result = await svc_create_transport_route(db, actor_ctx, params)
    except TransportValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["route"]}


@router.patch("/transport/{route_id}")
@transport_router.patch("/{route_id}")
async def update_route(route_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    # AD7 shared write path — same service as the AI `update_transport_route` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_update_transport_route(db, actor_ctx, {**body, "route_id": route_id})
    except TransportNotFoundError:
        raise HTTPException(404, "Route not found")
    except TransportValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["route"]}


@router.delete("/transport/{route_id}")
@transport_router.delete("/{route_id}")
async def delete_route(route_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    # AD7 shared write path — same service as the AI `delete_transport_route` tool.
    # Now blocked while active students are assigned (K-review safety rule).
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_delete_transport_route(db, actor_ctx, {"route_id": route_id})
    except TransportNotFoundError:
        raise HTTPException(404, "Route not found")
    except TransportConflictError as e:
        raise HTTPException(409, str(e))
    except TransportValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


# --- Transport Optimisation (Story 7-46) ---

def _parse_latlon(lat, lng):
    """Parse and validate lat/lng from request body. Returns (float, float) or raises 422."""
    if lat is None or lng is None:
        raise HTTPException(status_code=422, detail="lat and lng are required")
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="lat and lng must be numeric")
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        raise HTTPException(status_code=422, detail="lat must be -90..90 and lng must be -180..180")
    return lat, lng


@router.patch("/transport/students/{student_id}/coordinates")
@transport_router.patch("/students/{student_id}/coordinates")
async def set_student_coordinates(
    student_id: str,
    request: Request,
    user: dict = Depends(require_role("owner", "admin")),
):
    """Store backend-only lat/lng on a student — never returned in list responses."""
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    lat, lng = _parse_latlon(body.get("lat"), body.get("lng"))
    result = await db.students.update_one(
        scoped_query({"id": student_id}, branch_id=bid),
        {"$set": {"coordinates": {"lat": lat, "lng": lng}}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True, "data": {"student_id": student_id, "coordinates": {"lat": lat, "lng": lng}}}


@router.patch("/transport/zones/{zone_id}/centroid")
@transport_router.patch("/zones/{zone_id}/centroid")
async def set_zone_centroid(
    zone_id: str,
    request: Request,
    user: dict = Depends(require_role("owner", "admin")),
):
    """Set the geographic centroid of a route zone."""
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    lat, lng = _parse_latlon(body.get("lat"), body.get("lng"))
    result = await db.transport_routes.update_one(
        scoped_query({"id": zone_id}, branch_id=bid),
        {"$set": {"centroid": {"lat": lat, "lng": lng}}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Zone not found")
    return {"success": True, "data": {"zone_id": zone_id, "centroid": {"lat": lat, "lng": lng}}}


@router.post("/transport/geocode")
@transport_router.post("/geocode")
async def geocode_address(
    request: Request,
    user: dict = Depends(require_role("owner", "admin")),
):
    """Geocode an address string to lat/lng using Google Maps Geocoding API."""
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Maps API not configured")
    body = await request.json()
    address = (body.get("address") or "").strip()
    if not address:
        raise HTTPException(status_code=422, detail="address is required")
    try:
        result = await _geocode_address(address, api_key)
    except RuntimeError:
        raise HTTPException(status_code=502, detail="Geocoding request failed")
    return {"success": True, "data": result}


@router.get("/transport/suggest-route")
@transport_router.get("/suggest-route")
async def suggest_route(
    student_id: str,
    request: Request,
    user: dict = Depends(require_role("owner", "admin")),
):
    """Rank active route zones by proximity to a student's stored coordinates."""
    db = get_db()
    bid = user.get("branch_id")
    student = await db.students.find_one(
        scoped_query({"id": student_id}, branch_id=bid),
        {"_id": 0, "id": 1, "name": 1, "coordinates": 1, "route_zone_id": 1},
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    coords = student.get("coordinates")
    if not coords or coords.get("lat") is None or coords.get("lng") is None:
        raise HTTPException(status_code=422, detail="Student has no coordinates set")
    slat, slng = float(coords["lat"]), float(coords["lng"])

    zones = await db.transport_routes.find(
        scoped_query({"is_active": {"$ne": False}}, branch_id=bid),
        {"_id": 0, "id": 1, "route_name": 1, "centroid": 1},
    ).to_list(500)

    ranked = []
    for z in zones:
        if "id" not in z:
            continue
        centroid = z.get("centroid")
        if not centroid or centroid.get("lat") is None or centroid.get("lng") is None:
            continue
        dist = _haversine_km(slat, slng, float(centroid["lat"]), float(centroid["lng"]))
        ranked.append({
            "zone_id": z["id"],
            "zone_name": z.get("route_name", ""),
            "distance_km": round(dist, 2),
            "is_current": z["id"] == student.get("route_zone_id"),
        })
    ranked.sort(key=lambda x: x["distance_km"])
    return {
        "success": True,
        "data": ranked,
        "meta": {
            "student_id": student_id,
            "student_name": student.get("name", ""),
            "zones_loaded": len(zones),
        },
    }


@router.get("/transport/cluster-analysis")
@transport_router.get("/cluster-analysis")
async def cluster_analysis(
    request: Request,
    user: dict = Depends(require_role("owner", "admin")),
):
    """Return students whose current zone is not the nearest zone."""
    db = get_db()
    bid = user.get("branch_id")

    zones = await db.transport_routes.find(
        scoped_query({"is_active": {"$ne": False}}, branch_id=bid),
        {"_id": 0, "id": 1, "route_name": 1, "centroid": 1},
    ).to_list(500)
    zones_with_centroid = [
        z for z in zones
        if "id" in z
        and z.get("centroid") and z["centroid"].get("lat") is not None and z["centroid"].get("lng") is not None
    ]
    zone_map = {z["id"]: z for z in zones if "id" in z}

    students = await db.students.find(
        scoped_query({"is_active": {"$ne": False}, "coordinates": {"$exists": True}}, branch_id=bid),
        {"_id": 0, "id": 1, "name": 1, "admission_number": 1, "coordinates": 1, "route_zone_id": 1},
    ).to_list(5000)

    suboptimal = []
    total_with_coords = 0
    for s in students:
        coords = s.get("coordinates")
        if not coords or coords.get("lat") is None or coords.get("lng") is None:
            continue
        total_with_coords += 1
        slat, slng = float(coords["lat"]), float(coords["lng"])
        if not zones_with_centroid:
            continue
        distances = []
        for z in zones_with_centroid:
            c = z["centroid"]
            dist = _haversine_km(slat, slng, float(c["lat"]), float(c["lng"]))
            distances.append((dist, z))
        distances.sort(key=lambda x: x[0])
        nearest_dist, nearest_zone = distances[0]
        current_zone_id = s.get("route_zone_id")
        if current_zone_id and current_zone_id != nearest_zone["id"]:
            current_dist = next((d for d, z in distances if z["id"] == current_zone_id), None)
            if current_dist is not None:
                suboptimal.append({
                    "student_id": s["id"],
                    "student_name": s.get("name", ""),
                    "admission_number": s.get("admission_number", ""),
                    "current_zone_id": current_zone_id,
                    "current_zone_name": zone_map.get(current_zone_id, {}).get("route_name", ""),
                    "nearest_zone_id": nearest_zone["id"],
                    "nearest_zone_name": nearest_zone.get("route_name", ""),
                    "current_distance_km": round(current_dist, 2),
                    "nearest_distance_km": round(nearest_dist, 2),
                    "savings_km": round(current_dist - nearest_dist, 2),
                })
    suboptimal.sort(key=lambda x: x["savings_km"], reverse=True)
    return {
        "success": True,
        "data": suboptimal,
        "meta": {
            "total_suboptimal": len(suboptimal),
            "total_with_coords": total_with_coords,
            "zones_loaded": len(zones),
            "students_loaded": len(students),
        },
    }


@router.post("/study-plan")
async def save_study_plan(request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    body = await request.json()
    from datetime import datetime as dt
    await db.study_plans.update_one(
        scoped_filter({"user_id": user["id"]}, get_school_id()),
        {"$set": {**body, "user_id": user["id"], "updated_at": dt.now().isoformat()}},
        upsert=True
    )
    return {"success": True}


@router.patch("/expenses/{expense_id}")
async def update_expense(expense_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    # AD7 shared write path — same service as the AI `update_expense` tool.
    _require_accounting(user)
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_update_expense(db, actor_ctx, {**body, "expense_id": expense_id})
    except ExpenseNotFoundError:
        raise HTTPException(404, "Expense not found")
    except ExpenseValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    # AD7 shared write path — same service as the AI `delete_expense` tool.
    _require_accounting(user)
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_delete_expense(db, actor_ctx, {"expense_id": expense_id})
    except ExpenseNotFoundError:
        raise HTTPException(404, "Expense not found")
    except ExpenseValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    # AD7 shared write path — same service as the AI `delete_asset` tool.
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_delete_asset(db, actor_ctx, {"asset_id": asset_id})
    except AssetNotFoundError:
        raise HTTPException(404, "Asset not found")
    except AssetValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


@router.delete("/announcements/{ann_id}")
async def delete_announcement(ann_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    # AD7 shared write path — same service as the AI `delete_announcement` tool.
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_delete_announcement(db, actor_ctx, {"announcement_id": ann_id})
    except AnnouncementNotFoundError:
        raise HTTPException(404, "Announcement not found")
    except AnnouncementValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


@router.delete("/visitors/{visitor_id}")
async def delete_visitor(visitor_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    # AD7 shared write path — same service as the AI `delete_visitor` tool.
    _require_frontdesk(user)
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_delete_visitor(db, actor_ctx, {"visitor_id": visitor_id})
    except VisitorNotFoundError:
        raise HTTPException(404, "Visitor not found")
    except VisitorValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


# --- Announcements ---
@router.get("/announcements")
async def list_announcements(request: Request, page: int = 1, limit: int = 20, user: dict = Depends(get_current_user)):
    """Story 14: returns announcements targeted at the calling user's role."""
    db = get_db()
    role = user.get("role", "")
    limit = min(max(limit, 1), 50)
    skip = max(page - 1, 0) * limit
    # Story 7-47: only `active` rows (or legacy rows missing `status`) are visible
    # to recipients. Pending and rejected announcements are hidden.
    # Owners/admins also see announcements they created so they can review sent items.
    audience_clause = {"$or": [
        {"audience_roles": {"$in": [role, "all"]}},
        {"audience_roles": {"$exists": False}},
        {"audience_roles": []},
        {"audience_type": "all"},
    ]}
    status_clause = {"$or": [
        {"status": "active"},
        {"status": {"$exists": False}},
    ]}
    if role in ("owner", "admin"):
        query = {
            "is_draft": {"$ne": True},
            "$or": [
                {"$and": [audience_clause, status_clause]},
                {"created_by": user.get("id")},
            ],
        }
    else:
        query = {
            "is_draft": {"$ne": True},
            "$and": [audience_clause, status_clause],
        }
    query = scoped_filter(query, get_school_id())
    total = await db.announcements.count_documents(query)
    announcements = await db.announcements.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": announcements, "meta": {"page": page, "limit": limit, "total": total}}


@router.post("/announcements")
async def create_announcement(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    body = await request.json()
    has_explicit_roles = body.get("target_roles") is not None or body.get("audience_roles") is not None
    audience_type = body.get("audience_type") or ("role" if has_explicit_roles else "all")
    target_roles = _announcement_target_roles(body, audience_type)

    # Moderation gate centralized in services.announcement_service (Story A.4) — the
    # same decision the AI create_announcement tool uses. EC-9.1 (owner/principal
    # broadcast directly) + Story 7-47 (teacher/student/all/class held for approval).
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        initial_status = decide_announcement_status(
            actor_ctx, audience_type, target_roles, raw_audience_roles=body.get("audience_roles")
        )
    except AnnouncementValidationError as e:
        raise HTTPException(422, detail=str(e))

    announcement = add_school_id({
        "id": str(uuid.uuid4()),
        "title": body.get("title"),
        "content": body.get("content"),
        "audience_type": audience_type,
        "audience_classes": body.get("audience_classes", []),
        "audience_roles": target_roles,
        "target_roles": target_roles,
        "channels": body.get("channels", []),
        "is_draft": body.get("is_draft", False),
        "status": initial_status,
        "sent_at": datetime.now().isoformat() if not body.get("is_draft", False) else None,
        "created_by": user["id"],
        "created_by_name": user.get("name", ""),
        "created_at": datetime.now().isoformat(),
    })
    await db.announcements.insert_one({**announcement, "_id": announcement["id"]})
    return {"success": True, "data": announcement}


# ─── Complaints (P11: front-desk intake with routing + on-behalf-of capture) ──

# Category → owning department. Receptionists file complaints on a caller's
# behalf; routing puts each one in front of the right team. Note "fees" →
# "accountant" (the role), not "accounts" (there is no such role).
_COMPLAINT_DEPARTMENT = {
    "fees": "accountant",
    "academics": "principal",
    "maintenance": "maintenance",
    "facility": "maintenance",
    "it": "ittech",
    "tech": "ittech",
    "transport": "transport",
}
_DEFAULT_COMPLAINT_DEPARTMENT = "principal"


def _mask_phone(phone: str | None) -> str | None:
    """Mask all but the last 4 digits (DPDP — only the owner sees full numbers)."""
    if not phone:
        return phone
    if len(phone) <= 4:
        return "*" * len(phone)
    return "*" * (len(phone) - 4) + phone[-4:]


@router.post("/complaints")
async def create_complaint(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    """Front-desk complaint intake — routes by category, captures on-behalf-of caller."""
    db = get_db()
    body = await request.json()
    category = (body.get("category") or "general").strip().lower()
    department = _COMPLAINT_DEPARTMENT.get(category, _DEFAULT_COMPLAINT_DEPARTMENT)

    complaint = add_school_id({
        "id": str(uuid.uuid4()),
        "category": category,
        "description": body.get("description"),
        "on_behalf_of_name": body.get("on_behalf_of_name"),
        "on_behalf_of_phone": body.get("on_behalf_of_phone"),
        "department": department,
        "status": "open",
        "created_by": user["id"],
        "created_by_name": user.get("name", ""),
        "created_at": datetime.now().isoformat(),
    })
    await db.complaints.insert_one({**complaint, "_id": complaint["id"]})
    return {"success": True, "data": complaint}


@router.get("/complaints")
async def list_complaints(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    """List complaints; masks caller phone numbers for everyone except the owner (DPDP)."""
    db = get_db()
    # branch-scope: intentional — complaints are triaged school-wide by the front desk
    rows = await db.complaints.find(scoped_filter({}, get_school_id()), {"_id": 0}).to_list(500)
    if user.get("role") != "owner":
        for row in rows:
            if row.get("on_behalf_of_phone"):
                row["on_behalf_of_phone"] = _mask_phone(row["on_behalf_of_phone"])
    return {"success": True, "data": rows}


@router.get("/announcements/pending")
async def list_pending_announcements(request: Request, user: dict = Depends(require_owner_or_principal)):
    """Story 7-47: principal-only list of announcements awaiting approval."""
    db = get_db()
    rows = (
        await db.announcements.find(scoped_filter({"status": "pending_approval"}, get_school_id()), {"_id": 0})
        .sort("created_at", -1)
        .to_list(200)
    )
    return {"success": True, "data": rows}


@router.patch("/announcements/{ann_id}/approve")
async def approve_announcement(ann_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    """Story 7-47 — AD7 shared write path, same service as the AI `decide_announcement` tool."""
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_decide_announcement(db, actor_ctx, {"announcement_id": ann_id, "decision": "approve"})
    except AnnouncementNotFoundError:
        raise HTTPException(status_code=404, detail="Announcement not found")
    except AnnouncementStateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AnnouncementValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "data": result}


@router.patch("/announcements/{ann_id}/reject")
async def reject_announcement(ann_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    """Story 7-47 — AD7 shared write path, same service as the AI `decide_announcement` tool."""
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_decide_announcement(
            db, actor_ctx, {"announcement_id": ann_id, "decision": "reject", "reason": body.get("reason")})
    except AnnouncementNotFoundError:
        raise HTTPException(status_code=404, detail="Announcement not found")
    except AnnouncementStateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AnnouncementValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "data": result}


# --- Enquiries ---
@router.get("/enquiries")
async def list_enquiries(request: Request, status: str = None, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    bid = user.get("branch_id")
    query = {}
    if status:
        query["status"] = status
    # branch-scope: receptionist sees only own branch
    enquiries = await db.enquiries.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"success": True, "data": enquiries}


@router.post("/enquiries")
async def create_enquiry(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    # AD7 shared write path — same service as the AI `create_enquiry` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_create_enquiry(db, actor_ctx, body)
    except EnquiryValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["enquiry"]}


@router.patch("/enquiries/{enquiry_id}")
async def update_enquiry(enquiry_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    # AD7 shared write path — same service as the AI `update_enquiry_status` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_update_enquiry(db, actor_ctx, {**body, "enquiry_id": enquiry_id})
    except EnquiryNotFoundError:
        raise HTTPException(404, "Enquiry not found")
    except EnquiryConflictError as e:
        raise HTTPException(409, str(e))
    except EnquiryValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["enquiry"]}


@router.get("/visitors/pending-checkout")
@router.get("/visitors/overdue")  # backward-compat alias
async def list_overdue_visitors(request: Request, stale_hours: int = None, hours: int = 4, user: dict = Depends(require_role("owner", "admin"))):
    """Fix 2: renamed from /overdue to /pending-checkout; stale_hours is canonical, hours is backward-compat alias."""
    _require_frontdesk(user)
    db = get_db()
    bid = user.get("branch_id")
    effective_hours = stale_hours if stale_hours is not None else hours
    cutoff = (datetime.now() - timedelta(hours=max(1, min(effective_hours, 12)))).isoformat()
    # branch-scope: receptionist sees only own branch
    rows = await db.visitor_log.find(
        scoped_query({"time_out": None, "time_in": {"$lte": cutoff}}, branch_id=bid),
        {"_id": 0},
    ).sort("time_in", 1).to_list(100)
    return {"success": True, "data": rows, "meta": {"stale_hours": effective_hours, "hours": effective_hours, "count": len(rows)}}


# --- Leave (teacher self-apply) ---
@router.post("/leaves")
async def apply_leave(request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    body = await request.json()
    staff = await db.staff.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()))
    if not staff:
        # Create a minimal staff record for this teacher if not found
        from datetime import datetime as dt
        import uuid
        staff_id = str(uuid.uuid4())
        await db.staff.insert_one({
            "_id": staff_id, "id": staff_id, "schoolId": get_school_id(), "user_id": user["id"],
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
        "schoolId": get_school_id(),
    }
    await db.leave_requests.insert_one({**leave, "_id": leave["id"]})
    return {"success": True, "data": leave}


# --- Study Planner ---
@router.get("/study-plan")
async def get_study_plan(request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    plan = await db.study_plans.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()), {"_id": 0})
    if not plan:
        return {"success": True, "data": {"monday": "", "tuesday": "", "wednesday": "", "thursday": "", "friday": "", "saturday": ""}}
    return {"success": True, "data": plan}
