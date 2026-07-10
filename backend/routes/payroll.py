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
from services.payroll_service import (
    is_owner_or_accountant as _is_owner_or_accountant,
    disburse_salary,
    upsert_salary_structure,
)
from tenant import scoped_query, get_school_id

router = APIRouter(prefix="/api/payroll", tags=["payroll"])


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
    """Create/update a salary structure. Owner only. R12.5: delegates to payroll_service."""
    db = get_db()
    body = await request.json()
    doc = await upsert_salary_structure(
        db,
        staff_id=body.get("staff_id", ""),
        base_salary=float(body.get("base_salary", 0)),
        allowances=body.get("allowances"),
        deductions=body.get("deductions"),
        effective_from=body.get("effective_from"),
        is_active=body.get("is_active", True),
        updated_by=user["id"],
        school_id=get_school_id(),
        branch_id=user.get("branch_id"),
    )
    return {"success": True, "data": doc}


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
async def create_disbursement(request: Request):
    """Record a salary disbursement. Owner or accountant. R12.5: delegates to payroll_service."""
    user = _require_owner_or_accountant(request)
    db = get_db()
    body = await request.json()
    bid = user.get("branch_id")

    staff_id = body.get("staff_id", "")
    month = body.get("month", datetime.now(timezone.utc).strftime("%Y-%m"))
    # Accept both canonical (base_salary/net_amount) and legacy (gross/net) field names.
    base_salary = float(body.get("base_salary") or body.get("gross") or 0)
    raw_deductions = body.get("deductions", {})
    deductions_amt = (
        sum(float(v or 0) for v in raw_deductions.values())
        if isinstance(raw_deductions, dict)
        else float(raw_deductions or 0)
    )
    net_override = body.get("net_amount") or body.get("net")
    # If caller provides explicit net, derive deductions to match.
    if net_override is not None and base_salary > 0:
        deductions_amt = max(base_salary - float(net_override), 0.0)

    doc, idempotent = await disburse_salary(
        db,
        staff_id=staff_id,
        month=month,
        base_salary=base_salary,
        allowances=0.0,
        deductions=deductions_amt,
        payment_mode=body.get("payment_mode", "bank_transfer"),
        reference=body.get("reference"),
        status=body.get("status", "paid"),
        paid_by=user["id"],
        school_id=get_school_id(),
        branch_id=bid,
    )
    if idempotent:
        return {"success": True, "data": doc, "idempotent": True}
    return {"success": True, "data": doc}


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
