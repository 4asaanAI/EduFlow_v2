from __future__ import annotations
"""Payroll routes - salary structures and disbursements.

Migration 009 created salary_structures and salary_disbursements collections
but no routes existed. This file provides the foundational payroll API.
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from pymongo.errors import DuplicateKeyError

from database import get_db
from middleware.auth import get_current_user
from services.payroll_service import (
    PayrollNotFoundError,
    PayrollValidationError,
    build_payslip,
    correct_disbursement,
    is_owner_or_accountant as _is_owner_or_accountant,
    disburse_salary,
    upsert_salary_structure,
)
from services.accounting_period_service import AccountingPeriodClosedError, assert_posting_allowed
from services.actor_context import actor_ctx_from_user
from services.audit_service import write_audit_doc
from tenant import scoped_query, get_school_id

router = APIRouter(prefix="/api/payroll", tags=["payroll"])


async def _audit_payroll_write(db, user: dict, action: str, entity_id: str, changes: dict) -> None:
    actor = actor_ctx_from_user(
        user, school_id=get_school_id(), branch_id=user.get("branch_id")
    )
    await write_audit_doc(db, {
        "id": str(uuid.uuid4()), "entity_type": "payroll", "entity_id": entity_id,
        "action": action, "changed_by": actor.user_id, "changed_by_role": actor.role,
        "changes": changes, "created_at": actor.now_iso(),
    }, school_id=actor.school_id, branch_id=actor.branch_id or "")


def _may_read_payroll(user: dict) -> bool:
    """The school's owner, the principal, and the accountant head.

    Decision 9, 2026-08-10: Aman and Adesh both see everyone's salary. The principal
    was added to the screen gate below but NOT to the payslip check further down, so
    Adesh could open the payroll screen and then be refused the moment he clicked a
    payslip - the dead-button shape this sub-part exists to remove (R2-6, plan §1.8).
    One helper now, so the screen and the record cannot disagree again.
    """
    is_principal = (user or {}).get("role") == "admin" and (user or {}).get("sub_category") == "principal"
    return bool(_is_owner_or_accountant(user) or is_principal)


def _require_owner_or_accountant(request: Request) -> dict:
    user = get_current_user(request)
    if not _may_read_payroll(user):
        raise HTTPException(403, "Forbidden")
    return user


@router.get("/structures")
async def list_salary_structures(request: Request):
    """List salary structures for the owner, principal, or accountant."""
    user = _require_owner_or_accountant(request)
    db = get_db()
    bid = user.get("branch_id")
    structures = await db.salary_structures.find(
        scoped_query({}, branch_id=bid), {"_id": 0}
    ).to_list(200)
    return {"success": True, "data": structures, "meta": {"count": len(structures)}}


@router.post("/structures")
async def create_salary_structure(request: Request, user: dict = Depends(_require_owner_or_accountant)):
    """Create/update a salary structure through the canonical payroll service."""
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
    await _audit_payroll_write(db, user, "salary_structure_upsert", doc["id"], doc)
    return {"success": True, "data": doc}


@router.get("/disbursements")
async def list_disbursements(request: Request, month: str = None):
    """List salary disbursements for a month for authorized finance profiles."""
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
    # NEW-04/T7: batched (was one staff find_one per disbursement).
    disb_staff_ids = sorted({d.get("staff_id") for d in disbursements if d.get("staff_id")})
    disb_staff_map = {}
    if disb_staff_ids:
        disb_staff_docs = await db.staff.find(
            scoped_query({"id": {"$in": disb_staff_ids}}, branch_id=bid)
        ).to_list(len(disb_staff_ids))
        disb_staff_map = {s["id"]: s for s in disb_staff_docs if s.get("id")}
    for d in disbursements:
        staff = disb_staff_map.get(d.get("staff_id"))
        results.append({
            **d,
            "staff_name": staff.get("name") if staff else d.get("staff_id"),
        })

    return {"success": True, "data": results, "meta": {"count": len(results), "month": month}}


@router.get("/my-disbursements")
async def list_my_disbursements(request: Request):
    user = get_current_user(request)
    db = get_db()
    bid = user.get("branch_id")
    staff = await db.staff.find_one(
        scoped_query({"user_id": user.get("id")}, branch_id=bid), {"_id": 0, "id": 1}
    )
    if not staff:
        raise HTTPException(403, "Staff profile not found")
    rows = await db.salary_disbursements.find(
        scoped_query({"staff_id": staff["id"]}, branch_id=bid), {"_id": 0}
    ).sort("month", -1).to_list(200)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/disburse")
async def create_disbursement(request: Request):
    """Record a salary disbursement. Owner or accountant. R12.5: delegates to payroll_service."""
    user = _require_owner_or_accountant(request)
    db = get_db()
    body = await request.json()
    bid = user.get("branch_id")

    staff_id = body.get("staff_id", "")
    month = body.get("month", datetime.now(timezone.utc).strftime("%Y-%m"))
    try:
        await assert_posting_allowed(db, bid, f"{month}-01")
    except AccountingPeriodClosedError as exc:
        raise HTTPException(409, str(exc))
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
    await _audit_payroll_write(db, user, "salary_disbursement_create", doc["id"], doc)
    return {"success": True, "data": doc}


@router.patch("/disbursements/{disbursement_id}/process")
async def mark_disbursement_processed(
    disbursement_id: str, request: Request, user: dict = Depends(_require_owner_or_accountant)
):
    """Mark a disbursement as processed. Owner, principal, or accountant."""
    db = get_db()
    bid = user.get("branch_id")
    result = await db.salary_disbursements.update_one(
        scoped_query({"id": disbursement_id}, branch_id=bid),
        {"$set": {"status": "processed", "processed_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Disbursement not found")
    return {"success": True}


@router.get("/disbursements/{disbursement_id}/payslip")
async def get_payslip(disbursement_id: str, request: Request):
    """Return a structured payslip to finance roles or the matching staff account."""
    user = get_current_user(request)
    db = get_db()
    bid = user.get("branch_id")
    disbursement = await db.salary_disbursements.find_one(
        scoped_query({"id": disbursement_id}, branch_id=bid), {"_id": 0}
    )
    if not disbursement:
        raise HTTPException(404, "Disbursement not found")
    if not _may_read_payroll(user):
        staff = await db.staff.find_one(
            scoped_query({"id": disbursement.get("staff_id"), "user_id": user.get("id")}, branch_id=bid),
            {"_id": 0, "id": 1},
        )
        if not staff:
            raise HTTPException(403, "Forbidden")
    return {"success": True, "data": await build_payslip(db, disbursement, branch_id=bid)}


@router.get("/disbursements/{disbursement_id}/corrections")
async def list_disbursement_corrections(disbursement_id: str, request: Request,
                                        user: dict = Depends(_require_owner_or_accountant)):
    rows = await get_db().salary_disbursement_corrections.find(
        scoped_query({"disbursement_id": disbursement_id}, branch_id=user.get("branch_id")),
        {"_id": 0},
    ).sort("revision", 1).to_list(100)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.patch("/disbursements/{disbursement_id}/correct")
async def patch_disbursement_correction(disbursement_id: str, request: Request,
                                        user: dict = Depends(_require_owner_or_accountant)):
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    current = await db.salary_disbursements.find_one(
        scoped_query({"id": disbursement_id}, branch_id=bid), {"_id": 0, "month": 1}
    )
    if not current:
        raise HTTPException(404, "Disbursement not found")
    try:
        await assert_posting_allowed(db, bid, f"{current['month']}-01")
        row = await correct_disbursement(
            db, disbursement_id=disbursement_id,
            changes=body.get("changes") or {}, reason=body.get("reason") or "",
            corrected_by=user["id"], branch_id=bid,
        )
    except AccountingPeriodClosedError as exc:
        raise HTTPException(409, str(exc))
    except PayrollNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except PayrollValidationError as exc:
        raise HTTPException(400, str(exc))
    await _audit_payroll_write(
        db, user, "salary_disbursement_correct", disbursement_id,
        {"reason": body.get("reason"), "changes": body.get("changes") or {}},
    )
    return {"success": True, "data": row}
