"""Accounting-period lifecycle and posting lock guard."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.txn_context import get_current_session, session_kwargs
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
    if len(raw) != 10:
        raise AccountingPeriodValidationError(f"{key} must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        raise AccountingPeriodValidationError(f"{key} must be YYYY-MM-DD")
    if parsed.isoformat() != raw:
        raise AccountingPeriodValidationError(f"{key} must be YYYY-MM-DD")
    return parsed


async def assert_posting_allowed(db, branch_id: str | None, posting_date,
                                 entity_id: str | None = None, *, session=None) -> dict | None:
    """Allow legacy behavior until a relevant period exists, then fail closed.

    Entity-specific periods take precedence. Legacy periods without ``entity_id``
    continue to govern existing postings and become the fallback for the default
    entity, without rewriting any stored record.
    """
    value = _date(posting_date, "posting_date").isoformat()
    date_filter = {"start_date": {"$lte": value}, "end_date": {"$gte": value}}
    effective_session = session if session is not None else get_current_session()
    kwargs = session_kwargs(effective_session)
    if entity_id:
        period = await db.accounting_periods.find_one(scoped_query({
            **date_filter, "entity_id": entity_id,
        }, branch_id=branch_id), {"_id": 0}, **kwargs)
        entity = await db.legal_entities.find_one(
            scoped_query({"id": entity_id, "is_active": True}, branch_id=branch_id),
            {"_id": 0, "is_default": 1, "owns_legacy_records": 1}, **kwargs,
        )
        if not entity:
            raise AccountingPeriodClosedError("Legal entity is not active")
        owns_legacy = entity.get("owns_legacy_records", entity.get("is_default"))
        if not period and owns_legacy:
            period = await db.accounting_periods.find_one(scoped_query({
                **date_filter, "entity_id": {"$exists": False},
            }, branch_id=branch_id), {"_id": 0}, **kwargs)
    else:
        period = await db.accounting_periods.find_one(
            scoped_query(date_filter, branch_id=branch_id), {"_id": 0}, **kwargs
        )
    if period:
        if period.get("status") != "open":
            raise AccountingPeriodClosedError(
                f"Accounting period {period.get('name') or period.get('id')} is closed"
            )
        if effective_session is not None:
            touched = await db.accounting_periods.update_one(
                scoped_query({"id": period["id"], "status": "open"}, branch_id=branch_id),
                {"$inc": {"activity_version": 1}}, **kwargs,
            )
            if touched.matched_count == 0:
                raise AccountingPeriodClosedError("Accounting period changed while posting")
        return period
    if entity_id:
        config_filter = ({"$or": [{"entity_id": entity_id}, {"entity_id": {"$exists": False}}]}
                         if owns_legacy else {"entity_id": entity_id})
    else:
        config_filter = {}
    configured = await db.accounting_periods.find_one(
        scoped_query(config_filter, branch_id=branch_id), {"_id": 0, "id": 1}, **kwargs
    )
    if configured:
        raise AccountingPeriodClosedError("No open accounting period covers this posting date")
    return None


async def create_period(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    kwargs = session_kwargs(session)
    name = str(params.get("name") or "").strip()
    if not name:
        raise AccountingPeriodValidationError("name is required")
    start = _date(params.get("start_date"), "start_date")
    end = _date(params.get("end_date"), "end_date")
    if end < start:
        raise AccountingPeriodValidationError("end_date cannot be before start_date")
    entity_id = str(params.get("entity_id") or "").strip() or None
    if entity_id:
        entity = await db.legal_entities.find_one(
            scoped_query({"id": entity_id, "is_active": True}, branch_id=actor_ctx.branch_id),
            {"_id": 0, "is_group": 1}, **kwargs,
        )
        if not entity:
            raise AccountingPeriodValidationError("Legal entity not found")
        if entity.get("is_group"):
            raise AccountingPeriodValidationError("Group entities cannot own accounting periods")
    overlap_filter = {
        "start_date": {"$lte": end.isoformat()}, "end_date": {"$gte": start.isoformat()},
        **({"entity_id": entity_id} if entity_id else {"entity_id": {"$exists": False}}),
    }
    lock_id = f"{actor_ctx.school_id}:{actor_ctx.branch_id or 'school'}:{entity_id or 'legacy'}"
    await db.accounting_period_locks.find_one_and_update(
        {"_id": lock_id},
        {"$inc": {"revision": 1}, "$setOnInsert": {
            "schoolId": actor_ctx.school_id, "branch_id": actor_ctx.branch_id,
            "entity_id": entity_id,
        }},
        upsert=True, **kwargs,
    )
    overlap = await db.accounting_periods.find_one(
        scoped_query(overlap_filter, branch_id=actor_ctx.branch_id), {"_id": 0, "id": 1}, **kwargs
    )
    if overlap:
        raise AccountingPeriodValidationError("Accounting periods cannot overlap")
    period_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "_id": period_id, "id": period_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "name": name,
        **({"entity_id": entity_id} if entity_id else {}),
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "status": "open", "created_by": actor_ctx.user_id,
        "created_at": now, "updated_at": now,
    }
    await db.accounting_periods.insert_one(doc, **kwargs)
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
    result = await db.accounting_periods.update_one(
        scoped_query({"id": period_id, "status": period.get("status")}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": status, "updated_at": now,
                  f"{status}_by": actor_ctx.user_id, f"{status}_at": now},
         "$push": {"status_history": event}},
    )
    if result.matched_count == 0:
        raise AccountingPeriodValidationError("Accounting period changed concurrently")
    await write_audit_doc(db, {
        "id": str(uuid.uuid4()), "entity_type": "accounting_period", "entity_id": period_id,
        "action": f"accounting_period_{status}", "changed_by": actor_ctx.user_id,
        "changed_by_role": actor_ctx.role, "changes": event, "reason": reason,
        "created_at": now,
    }, school_id=actor_ctx.school_id, branch_id=actor_ctx.branch_id or "")
    return {**period, "status": status, "status_history": [*(period.get("status_history") or []), event]}
