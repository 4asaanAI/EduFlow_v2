"""
Token management routes for EduFlow.

Endpoints:
  GET  /api/tokens/balance     — branch token balance (owner/admin)
  GET  /api/tokens/usage       — branch usage stats (owner) or user stats (with ?user_id=)
  GET  /api/tokens/usage/me    — current user's usage this month
  POST /api/tokens/purchase    — record a top-up purchase (after Razorpay payment)
  PUT  /api/tokens/limits      — update per-role limits (owner only)
  GET  /api/tokens/packs       — available top-up packs with prices
"""

import logging
from fastapi import APIRouter, Request, HTTPException, Depends

from middleware.auth import get_current_user, require_owner
from services.token_service import (
    get_balance,
    get_usage_stats,
    purchase_topup,
    update_role_limits,
    PACKS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tokens", tags=["tokens"])


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _resolve_branch(user: dict) -> str:
    """Extract branch_id from the authenticated user, with dev fallback."""
    return user.get("branch_id") or "branch-aaryans-joya"


# ─── GET /api/tokens/balance ─────────────────────────────────────────────────

@router.get("/balance")
async def balance_endpoint(request: Request):
    """Get the current token balance and configuration for the branch."""
    user = get_current_user(request)
    branch_id = _resolve_branch(user)

    try:
        data = await get_balance(branch_id)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Token balance error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch token balance.")


# ─── GET /api/tokens/usage ───────────────────────────────────────────────────

@router.get("/usage")
async def usage_endpoint(request: Request, user_id: str = None):
    """
    Get usage statistics.
    - Without user_id: branch-level stats (owner/admin only)
    - With ?user_id=...: that user's stats
    """
    user = get_current_user(request)
    branch_id = _resolve_branch(user)

    # auth: dynamic gate — only branch-wide stats require owner/admin;
    # per-user stats are accessible to the caller themself.
    if not user_id and user["role"] not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        data = await get_usage_stats(branch_id, user_id=user_id)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Token usage stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch usage stats.")


# ─── GET /api/tokens/usage/me ────────────────────────────────────────────────

@router.get("/usage/me")
async def my_usage_endpoint(request: Request):
    """Get the current user's token usage for this month."""
    user = get_current_user(request)
    branch_id = _resolve_branch(user)

    try:
        data = await get_usage_stats(branch_id, user_id=user["id"])
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"My token usage error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch your usage stats.")


# ─── POST /api/tokens/purchase ───────────────────────────────────────────────

@router.post("/purchase")
async def purchase_endpoint(request: Request):
    """
    Record a token top-up purchase after Razorpay payment.
    Body: {"pack_id": "basic", "payment_id": "pay_abc123"}
    """
    user = get_current_user(request)
    branch_id = _resolve_branch(user)
    body = await request.json()

    pack_id = body.get("pack_id", "").strip()
    payment_id = body.get("payment_id", "").strip()

    if not pack_id:
        raise HTTPException(status_code=400, detail="pack_id is required.")
    if not payment_id:
        raise HTTPException(status_code=400, detail="payment_id is required.")
    if pack_id not in PACKS:
        raise HTTPException(status_code=400, detail=f"Unknown pack: {pack_id}. Available: {', '.join(PACKS.keys())}")

    try:
        result = await purchase_topup(branch_id, user["id"], pack_id, payment_id)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Purchase failed."))
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token purchase error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process purchase.")


# ─── PUT /api/tokens/limits ──────────────────────────────────────────────────

@router.put("/limits")
async def limits_endpoint(request: Request, user: dict = Depends(require_owner)):
    """
    Update per-role token limits. Owner only.
    Body: {"limits": {"owner": -1, "admin": 100000, "teacher": 50000, "student": 20000}}
    """
    branch_id = _resolve_branch(user)
    body = await request.json()
    limits = body.get("limits")

    if not limits or not isinstance(limits, dict):
        raise HTTPException(status_code=400, detail="'limits' object is required in the request body.")

    try:
        result = await update_role_limits(branch_id, limits)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Update failed."))
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token limits update error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update limits.")


# ─── GET /api/tokens/packs ──────────────────────────────────────────────────

@router.get("/packs")
async def packs_endpoint(request: Request):
    """Return available token packs with prices."""
    # Auth check — any authenticated user can view packs
    get_current_user(request)

    packs_list = [
        {
            "id": pack_id,
            "tokens": info["tokens"],
            "price_inr": info["price_inr"],
            "label": f"{info['tokens'] // 1000}K tokens",
        }
        for pack_id, info in PACKS.items()
    ]

    return {"success": True, "data": packs_list}
