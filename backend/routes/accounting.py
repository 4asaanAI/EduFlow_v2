"""Accounting-period controls for financial posting locks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from middleware.auth import require_owner, require_role
from services.accounting_period_service import (
    AccountingPeriodNotFoundError,
    AccountingPeriodValidationError,
    change_period_status,
    create_period,
)
from services.actor_context import actor_ctx_from_user
from tenant import get_school_id, scoped_query


router = APIRouter(prefix="/api/accounting", tags=["accounting"])


@router.get("/periods")
async def list_periods(request: Request,
                       user: dict = Depends(require_role("owner", "admin"))):
    if user.get("role") != "owner" and user.get("sub_category") != "accountant":
        raise HTTPException(403, "Only the school owner or accountant can view accounting periods")
    rows = await get_db().accounting_periods.find(
        scoped_query({}, branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("start_date", -1).to_list(500)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/periods")
async def post_period(request: Request, user: dict = Depends(require_owner)):
    try:
        row = await create_period(
            get_db(), actor_ctx_from_user(user, school_id=get_school_id()), await request.json()
        )
    except AccountingPeriodValidationError as exc:
        raise HTTPException(400, str(exc))
    return {"success": True, "data": row}


@router.patch("/periods/{period_id}/status")
async def patch_period_status(period_id: str, request: Request,
                              user: dict = Depends(require_owner)):
    try:
        row = await change_period_status(
            get_db(), actor_ctx_from_user(user, school_id=get_school_id()),
            period_id, await request.json(),
        )
    except AccountingPeriodNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except AccountingPeriodValidationError as exc:
        raise HTTPException(400, str(exc))
    return {"success": True, "data": row}
