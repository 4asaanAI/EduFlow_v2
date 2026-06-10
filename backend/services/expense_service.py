"""Expense domain service — the single shared write path for expense records
(AI Layer Hardening, AD7 — drift-gate remediation for `create_expense` plus the
new `update_expense` / `delete_expense` AI tools).

Both the REST routes (`POST/PATCH/DELETE /api/ops/expenses*`) and the AI tools
(`create_expense`, `update_expense`, `delete_expense`) call these functions, so
an AI expense write is byte-identical to a panel write: the same budget guard,
the same field set, the same audit row.

**Parity decision (case-by-case):** the legacy AI tool stamped `branch_id` and
read `schoolId` from the JWT; the REST route stamped neither branch nor audit.
Canonical = REST field set + env `schoolId`, PLUS the AI path's `branch_id`
stamp (required for branch isolation) and an audit row on every mutation.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import uuid
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import scoped_query


class ExpenseValidationError(Exception):
    """Invalid input (missing/non-numeric field, budget exceeded) → HTTP 400."""


class ExpenseNotFoundError(Exception):
    """Unknown expense id within the caller's scope → HTTP 404."""


# PATCH whitelist — the legacy REST route $set the raw body; the service pins the
# mutable surface so neither entrypoint can flip schoolId/branch_id/audit fields.
_MUTABLE_FIELDS = {"category", "description", "amount", "date", "vendor"}


def _session_kwargs(session) -> dict:
    return _txn_session_kwargs(session)


async def _audit(db, actor_ctx: ActorContext, *, action: str, expense_id: str, changes: dict, session=None) -> None:
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "expense",
            "entity_id": expense_id,
            "action": action,
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": changes,
            "reason": None,
            "created_at": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )


async def _check_budget(db, actor_ctx: ActorContext, category: Optional[str], amount: float, session=None) -> None:
    if not category:
        return
    budget = await db.expense_budgets.find_one(
        scoped_query({"category": category}, branch_id=actor_ctx.branch_id), {"_id": 0}, **_session_kwargs(session)
    )
    if budget:
        remaining = float(budget.get("remaining_amount", budget.get("monthly_limit", 0)) or 0)
        if amount > remaining:
            raise ExpenseValidationError(
                f"Expense of ₹{amount:,.2f} exceeds remaining budget of ₹{remaining:,.2f} for '{category}'"
            )


async def create_expense(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Create an expense. params: {category, amount, description?, date?, vendor?}"""
    category = params.get("category")
    if not category:
        raise ExpenseValidationError("category is required")
    if params.get("amount") in (None, ""):
        raise ExpenseValidationError("amount is required")
    try:
        amount = float(params["amount"])
    except (TypeError, ValueError):
        raise ExpenseValidationError("amount must be a number")

    await _check_budget(db, actor_ctx, category, amount, session=session)

    expense = {
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "category": category,
        "description": params.get("description", ""),
        "amount": amount,
        "date": params.get("date") or actor_ctx.now().strftime("%Y-%m-%d"),
        "vendor": params.get("vendor", ""),
        "approved_by": actor_ctx.user_id,
        "recorded_by": actor_ctx.user_id,
        "created_at": actor_ctx.now_iso(),
    }
    if actor_ctx.branch_id:
        expense["branch_id"] = actor_ctx.branch_id
    await db.expenses.insert_one({**expense, "_id": expense["id"]}, **_session_kwargs(session))
    await _audit(db, actor_ctx, action="create", expense_id=expense["id"], changes={"created": expense}, session=session)
    return {"expense": expense}


async def update_expense(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Update an expense. params: {expense_id, category?, description?, amount?, date?, vendor?}"""
    expense_id = params.get("expense_id")
    if not expense_id:
        raise ExpenseValidationError("expense_id is required")
    existing = await db.expenses.find_one(
        scoped_query({"id": expense_id}, branch_id=actor_ctx.branch_id), {"_id": 0}, **_session_kwargs(session)
    )
    if not existing:
        raise ExpenseNotFoundError(expense_id)

    changes = {k: v for k, v in params.items() if k in _MUTABLE_FIELDS and v is not None}
    if "amount" in changes:
        try:
            changes["amount"] = float(changes["amount"])
        except (TypeError, ValueError):
            raise ExpenseValidationError("amount must be a number")
        await _check_budget(
            db, actor_ctx, changes.get("category") or existing.get("category"), changes["amount"], session=session
        )
    if not changes:
        return {"expense": existing, "noop": True}

    changes["updated_at"] = actor_ctx.now_iso()
    await db.expenses.update_one(
        scoped_query({"id": expense_id}, branch_id=actor_ctx.branch_id),
        {"$set": changes},
        **_session_kwargs(session),
    )
    await _audit(db, actor_ctx, action="update", expense_id=expense_id,
                 changes={"before": existing, "after": changes}, session=session)
    updated = await db.expenses.find_one(
        scoped_query({"id": expense_id}, branch_id=actor_ctx.branch_id), {"_id": 0}, **_session_kwargs(session)
    )
    return {"expense": updated}


async def delete_expense(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Delete an expense (hard delete, matching the panel). params: {expense_id}"""
    expense_id = params.get("expense_id")
    if not expense_id:
        raise ExpenseValidationError("expense_id is required")
    existing = await db.expenses.find_one(
        scoped_query({"id": expense_id}, branch_id=actor_ctx.branch_id), {"_id": 0}, **_session_kwargs(session)
    )
    if not existing:
        raise ExpenseNotFoundError(expense_id)
    await db.expenses.delete_one(
        scoped_query({"id": expense_id}, branch_id=actor_ctx.branch_id), **_session_kwargs(session)
    )
    # F.10: actor-tagged deletion audit — who deleted what, when.
    await _audit(db, actor_ctx, action="delete", expense_id=expense_id, changes={"deleted": existing}, session=session)
    return {"deleted": True, "expense": existing}
