from __future__ import annotations
"""Canonical payroll service — single source of truth for disbursements and structures.

R12.5: Consolidates the two divergent disbursement implementations in payroll.py and
fees.py into one service with a canonical schema, correct idempotency, and a single
auth policy. Both REST routes delegate here.

Canonical disbursement schema:
  id, schoolId, staff_id, month, base_salary, allowances, deductions, net_amount,
  payment_mode, reference, status, paid_by, paid_at, branch_id (if set)
"""

import uuid
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_owner_or_accountant(user: dict) -> bool:
    """R12.5 AC3: canonical accountant check — drops legacy 'accounts' sub_category."""
    if user.get("role") == "owner":
        return True
    return (
        user.get("role") == "admin"
        and user.get("sub_category") == "accountant"
    )


async def disburse_salary(
    db,
    *,
    staff_id: str,
    month: str,
    base_salary: float,
    allowances: float = 0.0,
    deductions: float = 0.0,
    payment_mode: str = "bank_transfer",
    reference: str | None = None,
    status: str = "paid",
    paid_by: str,
    school_id: str,
    branch_id: str | None = None,
) -> tuple[dict, bool]:
    """Record a salary disbursement.

    Returns (doc, is_idempotent). Idempotent on (schoolId, staff_id, month):
    if a record already exists, returns the existing doc with is_idempotent=True.
    Raises DuplicateKeyError only on concurrent double-submit (race condition),
    which the caller should catch and return the existing row.
    """
    net_amount = max(base_salary + allowances - deductions, 0.0)

    # Idempotency: check before insert to return the existing doc cleanly.
    existing = await db.salary_disbursements.find_one(
        {"staff_id": staff_id, "month": month}, {"_id": 0}
    )
    if existing:
        return existing, True

    doc: dict = {
        "id": str(uuid.uuid4()),
        "schoolId": school_id,
        "staff_id": staff_id,
        "month": month,
        "base_salary": base_salary,
        "allowances": allowances,
        "deductions": deductions,
        "net_amount": net_amount,
        "payment_mode": payment_mode,
        "reference": reference,
        "status": status,
        "paid_by": paid_by,
        "paid_at": _now_iso(),
    }
    if branch_id:
        doc["branch_id"] = branch_id

    try:
        await db.salary_disbursements.insert_one(doc)
    except DuplicateKeyError:
        # Concurrent double-submit — return the winner's row.
        existing = await db.salary_disbursements.find_one(
            {"staff_id": staff_id, "month": month}, {"_id": 0}
        )
        return existing or doc, True

    return {k: v for k, v in doc.items() if k != "_id"}, False


async def upsert_salary_structure(
    db,
    *,
    staff_id: str,
    base_salary: float,
    allowances: dict | None = None,
    deductions: dict | None = None,
    effective_from: str | None = None,
    is_active: bool = True,
    updated_by: str,
    school_id: str,
    branch_id: str | None = None,
) -> dict:
    """Upsert a salary structure for a staff member (one canonical record per staff_id)."""
    now = _now_iso()
    existing = await db.salary_structures.find_one({"staff_id": staff_id}, {"_id": 0})
    doc = {
        "id": (existing or {}).get("id") or str(uuid.uuid4()),
        "schoolId": school_id,
        "staff_id": staff_id,
        "base_salary": float(base_salary),
        "allowances": allowances or {},
        "deductions": deductions or {},
        "effective_from": effective_from or now[:10],
        "is_active": is_active,
        "updated_by": updated_by,
        "updated_at": now,
        "created_at": (existing or {}).get("created_at") or now,
    }
    if branch_id:
        doc["branch_id"] = branch_id

    await db.salary_structures.update_one(
        {"staff_id": staff_id},
        {"$set": doc, "$setOnInsert": {"_id": doc["id"]}},
        upsert=True,
    )
    return {k: v for k, v in doc.items() if k != "_id"}
