"""Audit Log UI — Story 33"""
from fastapi import APIRouter, Request, HTTPException, Depends
from database import TimedQuery, get_db
from middleware.auth import get_current_user, require_role
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
    branch_id: str = None,
    page: int = 1,
    limit: int = 50,
):
    db = get_db()
    user = get_user(request)
    # auth: owner OR admin (with sub_category principal/None/"") — narrower
    # than require_owner_or_principal because legacy admins without a
    # sub_category were grandfathered in; canonical helper would lock them out.
    if user.get("role") == "admin":
        sub = user.get("sub_category", "")
        if sub not in ("principal", None, ""):
            raise HTTPException(403, "Forbidden")
    elif user.get("role") != "owner":
        raise HTTPException(403, "Forbidden")

    is_principal = user.get("role") == "admin" and user.get("sub_category") == "principal"
    query = {}
    if page < 1:
        raise HTTPException(400, "page must be >= 1")
    if not 1 <= limit <= 100:
        raise HTTPException(400, "limit must be between 1 and 100")

    if collection:
        if is_principal and collection in PRINCIPAL_BLOCKED:
            raise HTTPException(403, "Forbidden")
        query["collection"] = collection
    elif is_principal:
        query["collection"] = {"$nin": list(PRINCIPAL_BLOCKED)}

    if changed_by:
        query["changed_by"] = changed_by
    if is_principal and branch_id and branch_id != user.get("branch_id"):
        raise HTTPException(403, "Forbidden")
    if branch_id:
        query["branch_id"] = branch_id
    elif is_principal and user.get("branch_id"):
        query["branch_id"] = user.get("branch_id")
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

    skip = (page - 1) * limit
    scoped = scoped_filter(query, get_school_id())
    async with TimedQuery(collection_name="audit_logs", operation="count_documents", query_shape="audit_log_list"):
        total = await db.audit_logs.count_documents(scoped)
    async with TimedQuery(collection_name="audit_logs", operation="find", query_shape="audit_log_list"):
        items = await db.audit_logs.find(scoped, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@router.get("/{record_id}")
@router.get("/record/{record_id}")
async def get_record_history(
    record_id: str,
    request: Request,
    page: int = 1,
    limit: int = 50,
    user: dict = Depends(require_role("owner", "admin")),
):
    db = get_db()
    if page < 1:
        raise HTTPException(400, "page must be >= 1")
    if not 1 <= limit <= 100:
        raise HTTPException(400, "limit must be between 1 and 100")
    is_principal = user.get("role") == "admin" and user.get("sub_category") == "principal"
    query = {
        "$or": [
            {"entity_id": record_id},
            {"record_id": record_id},
        ]
    }
    if is_principal:
        query["collection"] = {"$nin": list(PRINCIPAL_BLOCKED)}
        if user.get("branch_id"):
            query["branch_id"] = user.get("branch_id")
    scoped = scoped_filter(query, get_school_id())
    skip = (page - 1) * limit
    async with TimedQuery(collection_name="audit_logs", operation="count_documents", query_shape="record_history"):
        total = await db.audit_logs.count_documents(scoped)
    async with TimedQuery(collection_name="audit_logs", operation="find", query_shape="record_history"):
        items = await db.audit_logs.find(scoped, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}
