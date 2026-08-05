"""Accounting-period lifecycle and posting lock guard."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_query


class AccountingPeriodValidationError(Exception):
    pass


class AccountingPeriodNotFoundError(Exception):
    pass


class AccountingPeriodClosedError(Exception):
    pass


def _date(value, key: str) -> date:
    raw = str(value or "").strip()
    if len(raw) == 7:
        raw = f"{raw}-01"
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        raise AccountingPeriodValidationError(f"{key} must be YYYY-MM-DD")


async def assert_posting_allowed(db, branch_id: str | None, posting_date) -> dict | None:
    """Allow legacy behavior until the first period exists, then fail closed."""
    value = _date(posting_date, "posting_date").isoformat()
    period = await db.accounting_periods.find_one(scoped_query({
        "start_date": {"$lte": value}, "end_date": {"$gte": value},
    }, branch_id=branch_id), {"_id": 0})
    if period:
        if period.get("status") != "open":
            raise AccountingPeriodClosedError(
                f"Accounting period {period.get('name') or period.get('id')} is closed"
            )
        return period
    configured = await db.accounting_periods.find_one(
        scoped_query({}, branch_id=branch_id), {"_id": 0, "id": 1}
    )
    if configured:
        raise AccountingPeriodClosedError("No open accounting period covers this posting date")
    return None


async def create_period(db, actor_ctx: ActorContext, params: dict) -> dict:
    name = str(params.get("name") or "").strip()
    if not name:
        raise AccountingPeriodValidationError("name is required")
    start = _date(params.get("start_date"), "start_date")
    end = _date(params.get("end_date"), "end_date")
    if end < start:
        raise AccountingPeriodValidationError("end_date cannot be before start_date")
    overlap = await db.accounting_periods.find_one(scoped_query({
        "start_date": {"$lte": end.isoformat()}, "end_date": {"$gte": start.isoformat()},
    }, branch_id=actor_ctx.branch_id), {"_id": 0, "id": 1})
    if overlap:
        raise AccountingPeriodValidationError("Accounting periods cannot overlap")
    period_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "_id": period_id, "id": period_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "name": name,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "status": "open", "created_by": actor_ctx.user_id,
        "created_at": now, "updated_at": now,
    }
    await db.accounting_periods.insert_one(doc)
    return {key: value for key, value in doc.items() if key != "_id"}


async def change_period_status(db, actor_ctx: ActorContext, period_id: str, params: dict) -> dict:
    status = str(params.get("status") or "").lower()
    if status not in {"open", "closed"}:
        raise AccountingPeriodValidationError("status must be open or closed")
    reason = str(params.get("reason") or "").strip()
    if status == "open" and not reason:
        raise AccountingPeriodValidationError("reason is required when reopening a period")
    period = await db.accounting_periods.find_one(
        scoped_query({"id": period_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not period:
        raise AccountingPeriodNotFoundError("Accounting period not found")
    if period.get("status") == status:
        return period
    now = datetime.now(timezone.utc).isoformat()
    event = {"from": period.get("status"), "to": status, "reason": reason or None,
             "by": actor_ctx.user_id, "at": now}
    await db.accounting_periods.update_one(
        scoped_query({"id": period_id, "status": period.get("status")}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": status, "updated_at": now,
                  f"{status}_by": actor_ctx.user_id, f"{status}_at": now},
         "$push": {"status_history": event}},
    )
    await write_audit_doc(db, {
        "id": str(uuid.uuid4()), "entity_type": "accounting_period", "entity_id": period_id,
        "action": f"accounting_period_{status}", "changed_by": actor_ctx.user_id,
        "changed_by_role": actor_ctx.role, "changes": event, "reason": reason,
        "created_at": now,
    }, school_id=actor_ctx.school_id, branch_id=actor_ctx.branch_id or "")
    return {**period, "status": status, "status_history": [*(period.get("status_history") or []), event]}
