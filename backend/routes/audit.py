"""Audit Log UI — Story 33"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from middleware.auth import get_current_user
from tenant import get_school_id, scoped_filter

router = APIRouter(prefix="/api/audit-log", tags=["audit"])

FINANCIAL_COLLECTIONS = {"fee_transactions", "fee_structures", "payroll", "expenses"}
USER_MGMT_COLLECTIONS = {"users", "refresh_tokens"}
PRINCIPAL_BLOCKED = FINANCIAL_COLLECTIONS | USER_MGMT_COLLECTIONS


def get_user(req: Request):
    return get_current_user(req)


@router.get("")
async def list_audit_log(
    request: Request,
    collection: str = None,
    changed_by: str = None,
    date_from: str = None,
    date_to: str = None,
    q: str = None,
    page: int = 1,
    limit: int = 50,
):
    db = get_db()
    user = get_user(request)
    if user.get("role") == "admin":
        sub = user.get("sub_category", "")
        if sub not in ("principal", None, ""):
            raise HTTPException(403, "Only Owner or Principal can view audit log")
    elif user.get("role") != "owner":
        raise HTTPException(403, "Only Owner or Principal can view audit log")

    is_principal = user.get("role") == "admin" and user.get("sub_category") == "principal"
    query = {}

    if collection:
        if is_principal and collection in PRINCIPAL_BLOCKED:
            raise HTTPException(403, "Principal cannot view financial or user-management audit entries")
        query["collection"] = collection
    elif is_principal:
        query["collection"] = {"$nin": list(PRINCIPAL_BLOCKED)}

    if changed_by:
        query["changed_by"] = changed_by
    if date_from or date_to:
        date_query = {}
        if date_from:
            date_query["$gte"] = date_from
        if date_to:
            date_query["$lte"] = date_to + "T23:59:59"
        query["created_at"] = date_query
    if q:
        query["$or"] = [
            {"changed_by": {"$regex": q, "$options": "i"}},
            {"entity_id": {"$regex": q, "$options": "i"}},
            {"action": {"$regex": q, "$options": "i"}},
        ]

    limit = min(max(limit, 1), 50)
    skip = max(page - 1, 0) * limit
    scoped = scoped_filter(query, get_school_id())
    total = await db.audit_logs.count_documents(scoped)
    items = await db.audit_logs.find(scoped, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@router.get("/record/{record_id}")
async def get_record_history(record_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user.get("role") not in ("owner", "admin"):
        raise HTTPException(403, "Forbidden")
    is_principal = user.get("role") == "admin" and user.get("sub_category") == "principal"
    query = {
        "$or": [
            {"entity_id": record_id},
            {"record_id": record_id},
        ]
    }
    if is_principal:
        query["collection"] = {"$nin": list(PRINCIPAL_BLOCKED)}
    items = await db.audit_logs.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"success": True, "data": items}
