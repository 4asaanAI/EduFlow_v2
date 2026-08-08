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
from tenant import scoped_query


class PayrollValidationError(Exception):
    pass


class PayrollNotFoundError(Exception):
    pass


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
        scoped_query(
            {"staff_id": staff_id, "month": month},
            branch_id=branch_id, school_id=school_id,
        ), {"_id": 0}
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
            scoped_query(
                {"staff_id": staff_id, "month": month},
                branch_id=branch_id, school_id=school_id,
            ), {"_id": 0}
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
    existing = await db.salary_structures.find_one(
        scoped_query(
            {"staff_id": staff_id}, branch_id=branch_id, school_id=school_id
        ), {"_id": 0}
    )
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
        scoped_query(
            {"staff_id": staff_id}, branch_id=branch_id, school_id=school_id
        ),
        {"$set": doc, "$setOnInsert": {"_id": doc["id"]}},
        upsert=True,
    )
    return {k: v for k, v in doc.items() if k != "_id"}


async def build_payslip(db, disbursement: dict, *, branch_id: str | None) -> dict:
    staff = await db.staff.find_one(
        scoped_query({"id": disbursement.get("staff_id")}, branch_id=branch_id), {"_id": 0}
    )
    structure = await db.salary_structures.find_one(
        scoped_query({"staff_id": disbursement.get("staff_id")}, branch_id=branch_id), {"_id": 0}
    )
    return {
        "payslip_number": disbursement.get("payslip_number") or f"PAY-{disbursement.get('month')}-{disbursement.get('id', '')[:8].upper()}",
        "disbursement_id": disbursement.get("id"),
        "month": disbursement.get("month"),
        "staff": {
            "id": disbursement.get("staff_id"), "name": (staff or {}).get("name"),
            "employee_id": (staff or {}).get("employee_id"),
            "department": (staff or {}).get("department"),
        },
        "earnings": {
            "base_salary": float(disbursement.get("base_salary") or 0),
            "allowances": disbursement.get("allowance_breakdown") or (structure or {}).get("allowances") or {},
            "allowances_total": float(disbursement.get("allowances") or 0),
        },
        "deductions": {
            "breakdown": disbursement.get("deduction_breakdown") or (structure or {}).get("deductions") or {},
            "total": float(disbursement.get("deductions") or 0),
        },
        "net_amount": float(disbursement.get("net_amount") or 0),
        "payment_mode": disbursement.get("payment_mode"),
        "reference": disbursement.get("reference"),
        "status": disbursement.get("status"),
        "paid_at": disbursement.get("paid_at"),
        "revision": int(disbursement.get("revision") or 0),
        "issued_at": _now_iso(),
    }


async def correct_disbursement(db, *, disbursement_id: str, changes: dict,
                               reason: str, corrected_by: str,
                               branch_id: str | None) -> dict:
    if not str(reason or "").strip():
        raise PayrollValidationError("reason is required")
    original = await db.salary_disbursements.find_one(
        scoped_query({"id": disbursement_id}, branch_id=branch_id), {"_id": 0}
    )
    if not original:
        raise PayrollNotFoundError("Disbursement not found")
    allowed = {"base_salary", "allowances", "deductions", "payment_mode", "reference", "status"}
    update = {key: value for key, value in changes.items() if key in allowed}
    if not update:
        raise PayrollValidationError("At least one correctable field is required")
    for key in ("base_salary", "allowances", "deductions"):
        if key in update:
            try:
                update[key] = float(update[key])
            except (TypeError, ValueError):
                raise PayrollValidationError(f"{key} must be a number")
            if update[key] < 0:
                raise PayrollValidationError(f"{key} cannot be negative")
    if "status" in update and update["status"] not in {"pending", "paid", "processed", "reversed"}:
        raise PayrollValidationError("Invalid payroll status")
    base = float(update.get("base_salary", original.get("base_salary") or 0))
    allowances = float(update.get("allowances", original.get("allowances") or 0))
    deductions = float(update.get("deductions", original.get("deductions") or 0))
    update["net_amount"] = max(base + allowances - deductions, 0)
    update["revision"] = int(original.get("revision") or 0) + 1
    update["corrected_at"] = _now_iso()
    update["corrected_by"] = corrected_by
    correction_id = str(uuid.uuid4())
    correction = {
        "_id": correction_id, "id": correction_id,
        "schoolId": original.get("schoolId"), "branch_id": branch_id,
        "disbursement_id": disbursement_id, "revision": update["revision"],
        "before": {key: original.get(key) for key in [*allowed, "net_amount", "revision"]},
        "changes": {key: value for key, value in update.items() if key not in {"corrected_at", "corrected_by"}},
        "reason": reason.strip(), "corrected_by": corrected_by,
        "created_at": _now_iso(),
    }
    await db.salary_disbursement_corrections.insert_one(correction)
    result = await db.salary_disbursements.update_one(
        scoped_query({"id": disbursement_id, "revision": original.get("revision", {"$exists": False})}, branch_id=branch_id),
        {"$set": update},
    )
    if result.matched_count == 0:
        await db.salary_disbursement_corrections.delete_one({"id": correction_id})
        raise PayrollValidationError("Disbursement changed; refresh and retry")
    return {**original, **update, "correction_id": correction_id}
