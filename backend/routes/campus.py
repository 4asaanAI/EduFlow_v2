"""Enterprise campus resources, custody, inventory, procurement, and library APIs."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from middleware.auth import require_role
from services.actor_context import actor_ctx_from_user
from services.campus_ops_service import (
    CampusConflictError,
    CampusNotFoundError,
    CampusValidationError,
    adjust_stock,
    cancel_booking,
    checkout_asset,
    create_booking,
    create_inventory_item,
    create_library_title,
    create_purchase_order,
    create_requisition,
    create_resource,
    decide_requisition,
    issue_library_title,
    receive_purchase_order,
    renew_library_loan,
    return_asset,
    return_library_loan,
)
from tenant import get_school_id, scoped_query


router = APIRouter(prefix="/api/campus", tags=["campus-operations"])


def _actor(user):
    return actor_ctx_from_user(user, school_id=get_school_id())


def _error(exc: Exception):
    if isinstance(exc, CampusNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, CampusConflictError):
        return HTTPException(409, str(exc))
    return HTTPException(400, str(exc))


def _require_manager(user: dict, allowed: set[str]) -> None:
    if user.get("role") == "owner":
        return
    if user.get("role") != "admin" or user.get("sub_category") not in allowed:
        raise HTTPException(403, "This operation requires the appropriate school operations role")


async def _body(request: Request) -> dict:
    return await request.json()


@router.get("/resources")
async def list_resources(request: Request,
                         user: dict = Depends(require_role("owner", "admin", "teacher"))):
    rows = await get_db().resources.find(
        scoped_query({"is_active": True}, branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("name", 1).to_list(500)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/resources")
async def post_resource(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "maintenance", "it_tech"})
    try:
        row = await create_resource(get_db(), _actor(user), await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/resource-bookings")
async def list_resource_bookings(request: Request, from_at: str | None = None,
                                 to_at: str | None = None,
                                 user: dict = Depends(require_role("owner", "admin", "teacher"))):
    query = {}
    if from_at:
        query["end_at"] = {"$gte": from_at}
    if to_at:
        query.setdefault("start_at", {})["$lte"] = to_at
    rows = await get_db().resource_bookings.find(
        scoped_query(query, branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("start_at", 1).to_list(1000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/resource-bookings")
async def post_resource_booking(request: Request,
                                user: dict = Depends(require_role("owner", "admin", "teacher"))):
    try:
        row = await create_booking(get_db(), _actor(user), await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.patch("/resource-bookings/{booking_id}/cancel")
async def patch_resource_booking_cancel(booking_id: str, request: Request,
                                        user: dict = Depends(require_role("owner", "admin", "teacher"))):
    try:
        row = await cancel_booking(get_db(), _actor(user), booking_id)
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/asset-custody")
async def list_asset_custody(request: Request, status: str | None = None,
                             user: dict = Depends(require_role("owner", "admin"))):
    query = {"status": status} if status else {}
    rows = await get_db().asset_custody.find(
        scoped_query(query, branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("checked_out_at", -1).to_list(1000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/assets/{asset_id}/checkout")
async def post_asset_checkout(asset_id: str, request: Request,
                              user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "maintenance", "it_tech", "receptionist"})
    try:
        row = await checkout_asset(get_db(), _actor(user), asset_id, await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.patch("/asset-custody/{custody_id}/return")
async def patch_asset_return(custody_id: str, request: Request,
                             user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "maintenance", "it_tech", "receptionist"})
    try:
        row = await return_asset(get_db(), _actor(user), custody_id, await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/inventory/items")
async def list_inventory_items(request: Request,
                               user: dict = Depends(require_role("owner", "admin"))):
    rows = await get_db().inventory_items.find(
        scoped_query({"is_active": True}, branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("name", 1).to_list(1000)
    for row in rows:
        row["sku"] = row.get("sku") or row.get("id")
        row["on_hand"] = row.get("on_hand", row.get("quantity", 0))
        row["reorder_level"] = row.get("reorder_level", row.get("min_stock", 0))
        row["needs_reorder"] = float(row.get("on_hand") or 0) <= float(row.get("reorder_level") or 0)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/inventory/items")
async def post_inventory_item(request: Request,
                              user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "maintenance", "accountant"})
    try:
        row = await create_inventory_item(get_db(), _actor(user), await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.post("/inventory/items/{item_id}/movements")
async def post_stock_movement(item_id: str, request: Request,
                              user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "maintenance", "accountant"})
    try:
        row = await adjust_stock(get_db(), _actor(user), item_id, await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/procurement/requisitions")
async def list_requisitions(request: Request,
                            user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "maintenance", "accountant"})
    rows = await get_db().purchase_requisitions.find(
        scoped_query({}, branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/procurement/requisitions")
async def post_requisition(request: Request,
                           user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "maintenance", "accountant"})
    try:
        row = await create_requisition(get_db(), _actor(user), await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.patch("/procurement/requisitions/{requisition_id}/decision")
async def patch_requisition_decision(requisition_id: str, request: Request,
                                     user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal"})
    try:
        row = await decide_requisition(get_db(), _actor(user), requisition_id, await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/procurement/orders")
async def list_purchase_orders(request: Request,
                               user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "maintenance", "accountant"})
    rows = await get_db().purchase_orders.find(
        scoped_query({}, branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/procurement/requisitions/{requisition_id}/order")
async def post_purchase_order(requisition_id: str, request: Request,
                              user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "accountant"})
    try:
        row = await create_purchase_order(get_db(), _actor(user), requisition_id, await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.patch("/procurement/orders/{order_id}/receive")
async def patch_purchase_order_receive(order_id: str, request: Request,
                                       user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "maintenance", "accountant"})
    try:
        row = await receive_purchase_order(get_db(), _actor(user), order_id)
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/library/titles")
async def list_library_titles(request: Request, search: str | None = None,
                              user: dict = Depends(require_role("owner", "admin", "teacher", "student", "parent"))):
    query = {"is_active": True}
    if search:
        safe_search = re.escape(search.strip())
        query["$or"] = [
            {"title": {"$regex": safe_search, "$options": "i"}},
            {"author": {"$regex": safe_search, "$options": "i"}},
            {"accession_number": {"$regex": safe_search, "$options": "i"}},
        ]
    rows = await get_db().library_titles.find(
        scoped_query(query, branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("title", 1).to_list(1000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/library/titles")
async def post_library_title(request: Request,
                             user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "librarian"})
    try:
        row = await create_library_title(get_db(), _actor(user), await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/library/loans")
async def list_library_loans(request: Request, status: str | None = None,
                             user: dict = Depends(require_role("owner", "admin", "teacher", "student", "parent"))):
    db = get_db()
    query = {"status": status} if status else {}
    branch_id = user.get("branch_id")
    if user.get("role") == "student":
        student = await db.students.find_one(
            scoped_query({"user_id": user["id"]}, branch_id=branch_id), {"_id": 0, "id": 1}
        )
        query.update({"borrower_type": "student", "borrower_id": student.get("id") if student else "__none__"})
    elif user.get("role") == "parent":
        guardians = await db.guardians.find(
            scoped_query({"user_id": user["id"]}, branch_id=branch_id), {"_id": 0, "student_id": 1}
        ).to_list(100)
        query.update({"borrower_type": "student", "borrower_id": {"$in": [g["student_id"] for g in guardians if g.get("student_id")]}})
    elif user.get("role") == "teacher":
        staff = await db.staff.find_one(
            scoped_query({"user_id": user["id"]}, branch_id=branch_id), {"_id": 0, "id": 1}
        )
        query.update({"borrower_type": "staff", "borrower_id": staff.get("id") if staff else "__none__"})
    elif user.get("role") == "admin":
        _require_manager(user, {"principal", "librarian"})
    rows = await db.library_loans.find(
        scoped_query(query, branch_id=branch_id), {"_id": 0}
    ).sort("issued_at", -1).to_list(1000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/library/titles/{title_id}/issue")
async def post_library_issue(title_id: str, request: Request,
                             user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "librarian"})
    try:
        row = await issue_library_title(get_db(), _actor(user), title_id, await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.patch("/library/loans/{loan_id}/return")
async def patch_library_return(loan_id: str, request: Request,
                               user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "librarian"})
    try:
        row = await return_library_loan(get_db(), _actor(user), loan_id, await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.patch("/library/loans/{loan_id}/renew")
async def patch_library_renew(loan_id: str, request: Request,
                              user: dict = Depends(require_role("owner", "admin"))):
    _require_manager(user, {"principal", "librarian"})
    try:
        row = await renew_library_loan(get_db(), _actor(user), loan_id, await _body(request))
    except (CampusValidationError, CampusNotFoundError, CampusConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}
