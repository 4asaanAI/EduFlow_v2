from __future__ import annotations
"""Payroll routes — salary structures and disbursements.

Migration 009 created salary_structures and salary_disbursements collections
but no routes existed. This file provides the foundational payroll API.
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from pymongo.errors import DuplicateKeyError

from database import get_db
from middleware.auth import get_current_user, require_owner
from tenant import scoped_query, get_school_id

router = APIRouter(prefix="/api/payroll", tags=["payroll"])


def _is_owner_or_accountant(user: dict) -> bool:
    if user.get("role") == "owner":
        return True
    if user.get("role") == "admin" and user.get("sub_category") in ("accounts", "accountant"):
        return True
    return False


def _require_owner_or_accountant(request: Request) -> dict:
    user = get_current_user(request)
    if not _is_owner_or_accountant(user):
        raise HTTPException(403, "Forbidden")
    return user


@router.get("/structures")
async def list_salary_structures(request: Request):
    """List all salary structures. Owner and accountant only."""
    user = _require_owner_or_accountant(request)
    db = get_db()
    bid = user.get("branch_id")
    structures = await db.salary_structures.find(
        scoped_query({}, branch_id=bid), {"_id": 0}
    ).to_list(200)
    return {"success": True, "data": structures, "meta": {"count": len(structures)}}


@router.post("/structures")
async def create_salary_structure(request: Request, user: dict = Depends(require_owner)):
    """Create a salary structure. Owner only."""
    db = get_db()
    body = await request.json()
    bid = user.get("branch_id")

    structure = {
        "id": str(uuid.uuid4()),
        "staff_id": body.get("staff_id", ""),
        "designation": body.get("designation", ""),
        "base_salary": body.get("base_salary", 0),
        "allowances": body.get("allowances", {}),
        "deductions": body.get("deductions", {}),
        "effective_from": body.get("effective_from", datetime.now(timezone.utc).strftime("%Y-%m")),
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    doc = {**structure}
    if bid:
        doc["branch_id"] = bid
    doc["schoolId"] = get_school_id()

    await db.salary_structures.insert_one(doc)
    return {"success": True, "data": structure}


@router.get("/disbursements")
async def list_disbursements(request: Request, month: str = None):
    """List salary disbursements for a month. Owner and accountant only."""
    user = _require_owner_or_accountant(request)
    db = get_db()
    bid = user.get("branch_id")

    query: dict = {}
    if month:
        query["month"] = month

    disbursements = await db.salary_disbursements.find(
        scoped_query(query, branch_id=bid), {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    # Enrich with staff names
    results = []
    for d in disbursements:
        staff = await db.staff.find_one(scoped_query({"id": d.get("staff_id")}, branch_id=bid))
        results.append({
            **d,
            "staff_name": staff.get("name") if staff else d.get("staff_id"),
        })

    return {"success": True, "data": results, "meta": {"count": len(results), "month": month}}


@router.post("/disburse")
async def create_disbursement(request: Request, user: dict = Depends(require_owner)):
    """Record a salary disbursement. Owner only. EC-10.4: unique per (staff_id, month)."""
    db = get_db()
    body = await request.json()
    bid = user.get("branch_id")

    staff_id = body.get("staff_id", "")
    month = body.get("month", datetime.now(timezone.utc).strftime("%Y-%m"))

    disbursement = {
        "id": str(uuid.uuid4()),
        "staff_id": staff_id,
        "month": month,
        "gross": body.get("gross", 0),
        "deductions": body.get("deductions", {}),
        "net": body.get("net", body.get("gross", 0)),
        "status": body.get("status", "pending"),
        "disbursed_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    doc = {**disbursement}
    if bid:
        doc["branch_id"] = bid
    doc["schoolId"] = get_school_id()

    try:
        await db.salary_disbursements.insert_one(doc)
    except DuplicateKeyError:
        # EC-10.4: unique index prevents concurrent double-disbursement
        raise HTTPException(409, "Salary already disbursed for this staff member this month")

    return {"success": True, "data": disbursement}


@router.patch("/disbursements/{disbursement_id}/process")
async def mark_disbursement_processed(
    disbursement_id: str, request: Request, user: dict = Depends(require_owner)
):
    """Mark a disbursement as processed. Owner only."""
    db = get_db()
    bid = user.get("branch_id")
    result = await db.salary_disbursements.update_one(
        scoped_query({"id": disbursement_id}, branch_id=bid),
        {"$set": {"status": "processed", "processed_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Disbursement not found")
    return {"success": True}
