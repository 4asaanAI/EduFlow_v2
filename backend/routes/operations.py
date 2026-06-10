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
    update_incident_status as svc_update_incident_status,
    IncidentValidationError,
    IncidentNotFoundError,
)
from services.approvals_service import (
    decide_approval_request as decide_approval_request_service,
    ApprovalValidationError,
    ApprovalNotFoundError,
    ApprovalAuthorizationError,
)
from services.announcement_service import (
    decide_announcement_status,
    AnnouncementValidationError,
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
    total = await db.leave_requests.count_documents(scoped_filter(query, get_school_id()))
    items = await db.leave_requests.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort("applied_at", -1).skip(skip).limit(limit).to_list(limit)
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
    items = await db.approval_requests.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort("submitted_at", -1).to_list(100)
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
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    cert_type = body.get("cert_type") or body.get("type", "bonafide")
    # Fix 4: character and merit cert types also require approval
    requires_approval = cert_type in {"bonafide", "tc", "transfer_certificate", "character", "merit"}
    approved_actor = _is_owner_or_principal_user(user)
    cert = add_school_id({
        "id": str(uuid.uuid4()),
        "student_id": body.get("student_id"),
        "cert_type": cert_type,
        "serial_number": f"CERT{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}",
        "content_data": body.get("content_data", {}),
        "status": "generated" if (approved_actor or not requires_approval) else "pending_approval",
        "issued_date": datetime.now().strftime("%Y-%m-%d") if (approved_actor or not requires_approval) else None,
        "issued_by": user["id"] if (approved_actor or not requires_approval) else None,
        "requested_by": user["id"],
        "created_at": datetime.now().isoformat(),
    })
    await db.certificates.insert_one({**cert, "_id": cert["id"]})
    if cert["status"] == "pending_approval":
        principals = await db.users.find(
            scoped_query({"role": "admin", "sub_category": "principal", "is_active": {"$ne": False}}, branch_id=bid),
            {"_id": 0, "id": 1},
        ).to_list(20)
        await fan_out_notifications(
            db,
            [p["id"] for p in principals if p.get("id")],
            notification_type="certificate_approval_requested",
            title="Certificate approval required",
            message=f"{cert_type.replace('_', ' ').title()} certificate is waiting for approval.",
            source_id=cert["id"],
            source_type="certificate",
        )
    return {"success": True, "data": cert}


@router.patch("/certificates/{cert_id}/approve")
async def approve_cert(cert_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    bid = user.get("branch_id")
    cert = await db.certificates.find_one(scoped_query({"id": cert_id}, branch_id=bid), {"_id": 0})
    if not cert:
        raise HTTPException(404, "Certificate not found")
    # Fix 5: state guard
    if cert.get("status") != "pending_approval":
        raise HTTPException(422, "Certificate is not in pending_approval state")
    now = datetime.now().isoformat()
    update = {
        "status": "generated",
        "issued_date": datetime.now().strftime("%Y-%m-%d"),
        "issued_by": user["id"],
        "approved_by": user["id"],
        "approved_at": now,
    }
    await db.certificates.update_one(scoped_query({"id": cert_id}, branch_id=bid), {"$set": update})
    if cert.get("requested_by"):
        await create_notification(
            db,
            user_id=cert["requested_by"],
            notification_type="certificate_approved",
            title="Certificate approved",
            message=f"{cert.get('cert_type', 'Certificate')} approved.",
            source_id=cert_id,
            source_type="certificate",
        )
    updated = await db.certificates.find_one(scoped_query({"id": cert_id}, branch_id=bid), {"_id": 0})
    return {"success": True, "data": updated}


@router.patch("/certificates/{cert_id}/reject")
async def reject_cert(cert_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(400, "reason is required")
    cert = await db.certificates.find_one(scoped_query({"id": cert_id}, branch_id=bid), {"_id": 0})
    if not cert:
        raise HTTPException(404, "Certificate not found")
    # Fix 5: state guard
    if cert.get("status") != "pending_approval":
        raise HTTPException(422, "Certificate is not in pending_approval state")
    update = {
        "status": "rejected",
        "rejected_by": user["id"],
        "rejected_at": datetime.now().isoformat(),
        "rejection_reason": reason,
    }
    await db.certificates.update_one(scoped_query({"id": cert_id}, branch_id=bid), {"$set": update})
    if cert.get("requested_by"):
        await create_notification(
            db,
            user_id=cert["requested_by"],
            notification_type="certificate_rejected",
            title="Certificate rejected",
            message=reason,
            source_id=cert_id,
            source_type="certificate",
        )
    updated = await db.certificates.find_one(scoped_query({"id": cert_id}, branch_id=bid), {"_id": 0})
    return {"success": True, "data": updated}


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
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    amount = float(body.get("amount", 0))
    category = body.get("category")
    if category:
        budget = await db.expense_budgets.find_one(scoped_query({"category": category}, branch_id=bid), {"_id": 0})
        if budget and amount > float(budget.get("remaining_amount", budget.get("monthly_limit", 0)) or 0):
            raise HTTPException(400, "Expense exceeds remaining category budget")
    expense = add_school_id({
        "id": str(uuid.uuid4()),
        "category": category,
        "description": body.get("description", ""),
        "amount": amount,
        "date": body.get("date", datetime.now().strftime("%Y-%m-%d")),
        "vendor": body.get("vendor", ""),
        "approved_by": user["id"],
        "recorded_by": user["id"],
        "created_at": datetime.now().isoformat(),
    })
    await db.expenses.insert_one({**expense, "_id": expense["id"]})
    return {"success": True, "data": expense}


# ─── Story 13: Incident Management (enhanced) ─────────────────────────────────

@router.get("/incidents")
async def list_incidents(request: Request, status: str = None, q: str = None, page: int = 1, limit: int = 20, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    bid = user.get("branch_id")
    query = {}
    if status:
        query["status"] = status
    if q:
        query["$or"] = [
            {"description": {"$regex": q, "$options": "i"}},
            {"involved_parties": {"$regex": q, "$options": "i"}},
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
    db = get_db()
    # P9.8: Any authenticated user (teacher, admin, owner) may log incidents.
    body = await request.json()
    if not body.get("description"):
        raise HTTPException(400, "description is required")
    severity = body.get("severity", "low")
    if severity not in ("low", "medium", "high"):
        raise HTTPException(400, "severity must be low, medium, or high")
    # P9.8: Auto-assign high-severity incidents to principal
    assigned_to = "principal" if severity == "high" else body.get("assigned_to", None)
    incident = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "title": body.get("title", ""),
        "description": body["description"],
        "severity": severity,
        "involved_parties": body.get("involved_parties", ""),
        "category": body.get("category", "general"),
        "status": "open",
        "thread": [],
        "logged_by": user["id"],
        "logged_by_name": user.get("name", ""),
        "assigned_to": assigned_to,
        "due_date": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })
    await db.incidents.insert_one(incident)
    # High-severity: notify Owner and Principal
    if severity == "high":
        owners_principals = await db.users.find(
            {"role": {"$in": ["owner", "admin"]}, "is_active": {"$ne": False}}, {"_id": 0, "id": 1, "sub_category": 1, "role": 1}
        ).to_list(20)
        await fan_out_notifications(
            db,
            [
                up["id"] for up in owners_principals
                if up.get("role") == "owner" or up.get("sub_category") == "principal"
            ],
            notification_type="high_severity_incident",
            title="High-severity incident",
            message=f"High-severity incident reported: {body['description'][:80]}",
            source_id=incident["id"],
            source_type="incident",
        )
    await _write_audit(db, "incident_create", "incidents", incident["id"], user, {"severity": severity, "description": body["description"][:100]})
    return {"success": True, "data": {k: v for k, v in incident.items() if k != "_id"}}


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
    _require_frontdesk(user)
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    today = datetime.now().strftime("%Y-%m-%d")
    today_prefix = today
    force = body.get("force", False)
    visitor_name = (body.get("visitor_name") or "").strip()
    norm_name = re.escape(visitor_name) if visitor_name else ""
    if visitor_name:
        duplicate = await db.visitor_log.find_one(
            scoped_query({
                "visitor_name": {"$regex": norm_name, "$options": "i"},
                "time_in": {"$regex": f"^{today_prefix}"},
                "time_out": None,
            }, branch_id=bid),
            {"_id": 0},
        )
        if duplicate:
            if not force:
                # Fix 2: return structured 409 with duplicate:true
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=409, content={
                    "success": False, "duplicate": True,
                    "existing_id": duplicate.get("id"),
                    "detail": "Visitor already checked in today. Pass force:true to override.",
                })
            # EC-11.1: Rate limit on force overrides
            MAX_FORCE_OVERRIDES = 3
            force_count = await db.visitor_log.count_documents(
                scoped_query({
                    "visitor_name": {"$regex": norm_name, "$options": "i"},
                    "time_in": {"$regex": f"^{today_prefix}"},
                    "force_override": True,
                }, branch_id=bid)
            )
            if force_count >= MAX_FORCE_OVERRIDES:
                raise HTTPException(429, f"Maximum {MAX_FORCE_OVERRIDES} forced check-ins per visitor per day exceeded")
    visitor = add_school_id({
        "id": str(uuid.uuid4()),
        "visitor_name": visitor_name,
        "phone": body.get("phone", ""),
        "purpose": body.get("purpose"),
        "whom_to_meet": body.get("whom_to_meet", ""),
        "id_type": body.get("id_type", ""),
        "time_in": datetime.now().isoformat(),
        "time_out": None,
        "force_override": force,
    })
    await db.visitor_log.insert_one({**visitor, "_id": visitor["id"]})
    return {"success": True, "data": visitor}


@router.patch("/visitors/{visitor_id}/checkout")
async def checkout_visitor(visitor_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    _require_frontdesk(user)
    db = get_db()
    bid = user.get("branch_id")
    # branch-scope: receptionist sees only own branch
    await db.visitor_log.update_one(scoped_query({"id": visitor_id}, branch_id=bid), {"$set": {"time_out": datetime.now().isoformat()}})
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
    db = get_db()
    body = await request.json()
    asset = add_school_id({
        "id": str(uuid.uuid4()),
        "name": body.get("name"),
        "category": body.get("category", ""),
        "quantity": int(body.get("quantity", 1)),
        "location": body.get("location", ""),
        "status": body.get("status", "good"),
        "purchase_date": body.get("purchase_date", ""),
        "maintenance_due": body.get("maintenance_due", ""),
        "created_by": user.get("id"),
        "created_by_role": user.get("role"),
        "created_by_sub_category": user.get("sub_category", ""),
    })
    await db.assets.insert_one({**asset, "_id": asset["id"]})
    return {"success": True, "data": asset}


@router.patch("/assets/{asset_id}")
async def update_asset(asset_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    await db.assets.update_one(scoped_query({"id": asset_id}, branch_id=bid), {"$set": body})
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
    db = get_db()
    body = await request.json()
    route = add_school_id({
        "id": str(uuid.uuid4()),
        "route_name": body.get("route_name") or body.get("name"),
        "start_point": body.get("start_point", ""),
        "end_point": body.get("end_point", ""),
        "stops": body.get("stops", []),
        "driver_name": body.get("driver_name", ""),
        "driver_phone": body.get("driver_phone", ""),
        "vehicle_no": body.get("vehicle_no") or body.get("vehicle_id", ""),
        "capacity": body.get("capacity", ""),
        "fare": body.get("fare", 0),
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    })
    await db.transport_routes.insert_one({**route, "_id": route["id"]})
    return {"success": True, "data": route}


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
    db = get_db()
    body = await request.json()
    vehicle = add_school_id({
        "id": str(uuid.uuid4()),
        "vehicle_number": body.get("vehicle_number", ""),
        "vehicle_type": body.get("vehicle_type", "bus"),
        "capacity": int(body.get("capacity", 0)),
        "driver_name": body.get("driver_name", ""),
        "driver_phone": body.get("driver_phone", ""),
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    })
    await db.vehicles.insert_one({**vehicle, "_id": vehicle["id"]})
    return {"success": True, "data": vehicle}


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
    """Alias: zones map to transport routes with zone semantics."""
    db = get_db()
    body = await request.json()
    zone = add_school_id({
        "id": str(uuid.uuid4()),
        "route_name": body.get("name") or body.get("route_name", ""),
        "description": body.get("description", ""),
        "fare": body.get("fare", 0),
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    })
    await db.transport_routes.insert_one({**zone, "_id": zone["id"]})
    return {"success": True, "data": zone}


@router.patch("/transport/{route_id}")
@transport_router.patch("/{route_id}")
async def update_route(route_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    await db.transport_routes.update_one(scoped_query({"id": route_id}, branch_id=bid), {"$set": body})
    route = await db.transport_routes.find_one(scoped_query({"id": route_id}, branch_id=bid), {"_id": 0})
    return {"success": True, "data": route}


@router.delete("/transport/{route_id}")
@transport_router.delete("/{route_id}")
async def delete_route(route_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    bid = user.get("branch_id")
    await db.transport_routes.delete_one(scoped_query({"id": route_id}, branch_id=bid))
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
        {"_id": 0, "id": 1, "name": 1, "coordinates": 1, "route_zone_id": 1},
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
    _require_accounting(user)
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json(); body.pop("id", None)
    await db.expenses.update_one(scoped_query({"id": expense_id}, branch_id=bid), {"$set": body})
    return {"success": True}


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    _require_accounting(user)
    db = get_db()
    bid = user.get("branch_id")
    await db.expenses.delete_one(scoped_query({"id": expense_id}, branch_id=bid))
    return {"success": True}


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    bid = user.get("branch_id")
    await db.assets.delete_one(scoped_query({"id": asset_id}, branch_id=bid))
    return {"success": True}


@router.delete("/announcements/{ann_id}")
async def delete_announcement(ann_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    await db.announcements.delete_one(scoped_filter({"id": ann_id}, get_school_id()))
    return {"success": True}


@router.delete("/visitors/{visitor_id}")
async def delete_visitor(visitor_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    _require_frontdesk(user)
    db = get_db()
    bid = user.get("branch_id")
    # branch-scope: receptionist sees only own branch
    await db.visitor_log.delete_one(scoped_query({"id": visitor_id}, branch_id=bid))
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
    """Story 7-47: principal approval moves announcement to active."""
    db = get_db()
    ann = await db.announcements.find_one(scoped_filter({"id": ann_id}, get_school_id()))
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    if ann.get("status") != "pending_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve announcement in status '{ann.get('status', 'unknown')}'",
        )

    now = datetime.now().isoformat()
    await db.announcements.update_one(
        scoped_filter({"id": ann_id}, get_school_id()),
        {"$set": {
            "status": "active",
            "approved_by": user.get("id"),
            "approved_by_name": user.get("name", ""),
            "approved_at": now,
        }},
    )
    await _write_audit(
        db,
        action="announcement_approved",
        entity_type="announcement",
        entity_id=ann_id,
        user=user,
        changes={
            "status": {"from": "pending_approval", "to": "active"},
            "target_roles": ann.get("target_roles") or ann.get("audience_roles"),
        },
    )
    return {"success": True, "data": {"id": ann_id, "status": "active", "approved_at": now}}


@router.patch("/announcements/{ann_id}/reject")
async def reject_announcement(ann_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    """Story 7-47: principal rejection with mandatory reason; notifies author."""
    db = get_db()
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="rejection reason is required")

    ann = await db.announcements.find_one(scoped_filter({"id": ann_id}, get_school_id()))
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    if ann.get("status") != "pending_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject announcement in status '{ann.get('status', 'unknown')}'",
        )

    now = datetime.now().isoformat()
    await db.announcements.update_one(
        scoped_filter({"id": ann_id}, get_school_id()),
        {"$set": {
            "status": "rejected",
            "rejected_by": user.get("id"),
            "rejected_by_name": user.get("name", ""),
            "rejected_at": now,
            "rejection_reason": reason,
        }},
    )
    await _write_audit(
        db,
        action="announcement_rejected",
        entity_type="announcement",
        entity_id=ann_id,
        user=user,
        changes={
            "status": {"from": "pending_approval", "to": "rejected"},
            "target_roles": ann.get("target_roles") or ann.get("audience_roles"),
        },
        reason=reason,
    )

    author_id = ann.get("created_by")
    if author_id:
        await create_notification(
            db,
            user_id=author_id,
            notification_type="announcement_rejected",
            title="Announcement rejected",
            message=f"Your announcement '{ann.get('title', '')}' was rejected: {reason}",
            source_id=ann_id,
            source_type="announcement",
        )

    return {"success": True, "data": {"id": ann_id, "status": "rejected", "rejected_at": now, "reason": reason}}


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
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    enquiry = add_school_id({
        "id": str(uuid.uuid4()),
        "student_name": body.get("student_name"),
        "parent_name": body.get("parent_name"),
        "phone": body.get("phone"),
        "class_applying": body.get("class_applying", ""),
        "status": "new",
        "source": body.get("source", "walk_in"),
        "assigned_to": user["id"],
        "created_at": datetime.now().isoformat(),
    })
    await db.enquiries.insert_one({**enquiry, "_id": enquiry["id"]})
    return {"success": True, "data": enquiry}


@router.patch("/enquiries/{enquiry_id}")
async def update_enquiry(enquiry_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    existing = await db.enquiries.find_one(scoped_query({"id": enquiry_id}, branch_id=bid), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Enquiry not found")
    # Aligned with frontend pipeline stages
    allowed_transitions = {
        "new": {"contacted", "lost"},
        "contacted": {"visit_scheduled", "lost"},
        "visit_scheduled": {"visited", "lost"},
        "visited": {"documents_submitted", "lost"},
        "documents_submitted": {"fee_paid", "lost"},
        "fee_paid": {"enrolled", "lost"},
        "enrolled": {"lost"},
        "lost": set(),
        # legacy / backward-compat
        "applied": {"admitted", "enrolled", "lost"},
        "admitted": {"enrolled", "lost"},
        "closed": set(),
    }
    update = {k: v for k, v in body.items() if k in {"status", "assigned_to", "source", "class_applying", "phone", "parent_name"}}
    new_status = update.get("status")
    if new_status and new_status != existing.get("status"):
        current = existing.get("status", "new")
        # Fix 7: EC-11.2 owner backward transition guard — owner can freely move stages
        if user.get("role") == "owner":
            if existing.get("status") == "enrolled":
                linked_student = await db.students.find_one(
                    scoped_query({"enquiry_id": enquiry_id}, branch_id=bid)
                )
                if linked_student:
                    raise HTTPException(409, "Cannot revert enrolled enquiry — student record exists. Delete the student record first.")
            # Allow any transition for owner
        elif new_status not in allowed_transitions.get(current, set()):
            raise HTTPException(400, f"Invalid enquiry transition from {current} to {new_status}")
    if body.get("note") or new_status:
        await db.enquiries.update_one(
            scoped_query({"id": enquiry_id}, branch_id=bid),
            {"$push": {"timeline": {
                "id": str(uuid.uuid4()),
                "author_id": user["id"],
                "from_status": existing.get("status"),
                "to_status": new_status or existing.get("status"),
                "note": body.get("note", ""),
                "created_at": datetime.now().isoformat(),
            }}},
        )
    update["updated_at"] = datetime.now().isoformat()
    await db.enquiries.update_one(scoped_query({"id": enquiry_id}, branch_id=bid), {"$set": update})
    updated = await db.enquiries.find_one(scoped_query({"id": enquiry_id}, branch_id=bid), {"_id": 0})
    return {"success": True, "data": updated}


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
