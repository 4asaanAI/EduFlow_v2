"""Accounting-period controls for financial posting locks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from database import TransactionUnavailableError, get_db, get_txn_session
from middleware.auth import require_role
from services.accounting_period_service import (
    AccountingPeriodNotFoundError,
    AccountingPeriodValidationError,
    change_period_status,
    create_period,
)
from services.actor_context import actor_ctx_from_user
from services.txn_context import reset_current_session, set_current_session
from school_identity import default_branch_id
from tenant import get_school_id, scoped_query


router = APIRouter(prefix="/api/accounting", tags=["accounting"])


def _require_finance_profile(user: dict) -> dict:
    if user.get("role") == "owner":
        return user
    if user.get("role") == "admin" and user.get("sub_category") in {"principal", "accountant"}:
        return user
    raise HTTPException(403, "Only the school owner, principal, or accountant can manage accounting periods")


def _actor(user: dict):
    return actor_ctx_from_user(
        user, school_id=get_school_id(), branch_id=user.get("branch_id") or default_branch_id()
    )


async def _create_period_transactionally(user: dict, body: dict):
    session = await get_txn_session()
    token = set_current_session(session)
    try:
        async with session:
            async with session.start_transaction():
                return await create_period(get_db(), _actor(user), body, session=session)
    finally:
        reset_current_session(token)


@router.get("/periods")
async def list_periods(request: Request,
                       entity_id: str | None = None,
                       user: dict = Depends(require_role("owner", "admin"))):
    _require_finance_profile(user)
    db = get_db()
    branch_id = user.get("branch_id") or default_branch_id()
    query = {}
    if entity_id:
        entity = await db.legal_entities.find_one(
            scoped_query({"id": entity_id, "is_active": True}, branch_id=branch_id),
            {"_id": 0, "is_default": 1, "owns_legacy_records": 1},
        )
        if not entity:
            raise HTTPException(404, "Legal entity not found")
        owns_legacy = entity.get("owns_legacy_records", entity.get("is_default"))
        query = ({"$or": [{"entity_id": entity_id}, {"entity_id": {"$exists": False}}]}
                 if owns_legacy else {"entity_id": entity_id})
    rows = await db.accounting_periods.find(
        scoped_query(query, branch_id=branch_id), {"_id": 0}
    ).sort("start_date", -1).to_list(500)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/periods")
async def post_period(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    _require_finance_profile(user)
    try:
        row = await _create_period_transactionally(user, await request.json())
    except AccountingPeriodValidationError as exc:
        raise HTTPException(400, str(exc))
    except TransactionUnavailableError as exc:
        raise HTTPException(503, str(exc))
    return {"success": True, "data": row}


@router.patch("/periods/{period_id}/status")
async def patch_period_status(period_id: str, request: Request,
                              user: dict = Depends(require_role("owner", "admin"))):
    _require_finance_profile(user)
    try:
        row = await change_period_status(
            get_db(), _actor(user),
            period_id, await request.json(),
        )
    except AccountingPeriodNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except AccountingPeriodValidationError as exc:
        raise HTTPException(400, str(exc))
    return {"success": True, "data": row}
