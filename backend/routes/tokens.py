from __future__ import annotations
"""
Token management routes for EduFlow.

Endpoints:
  GET  /api/tokens/balance                  — branch token balance (owner/admin)
  GET  /api/tokens/usage                    — branch usage stats (owner) or user stats
  GET  /api/tokens/usage/me                 — current user's usage this month
  GET  /api/tokens/packs                    — available top-up packs + subscription plans
  PUT  /api/tokens/limits                   — update per-role limits (owner only)
  POST /api/tokens/create-checkout-session  — Razorpay one-time payment link (owner only)
  POST /api/tokens/create-subscription-session — Razorpay subscription (owner only)
  POST /api/tokens/webhook                  — Razorpay webhook receiver (no JWT auth)
"""

import logging
import os

import razorpay
from fastapi import APIRouter, Depends, HTTPException, Request

from middleware.auth import get_current_user, require_owner
from services.razorpay_service import (
    SUBSCRIPTION_PLANS,
    create_checkout_session,
    create_subscription_session,
    handle_payment_link_paid,
    handle_subscription_activated,
    handle_subscription_cancelled,
    handle_subscription_charged,
    verify_webhook,
)
from services.token_service import (
    PACKS,
    get_balance,
    get_usage_stats,
    update_role_limits,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tokens", tags=["tokens"])


def _resolve_branch(user: dict) -> str:
    return user.get("branch_id") or "branch-aaryans-joya"


def _validate_redirect_url(url: str | None, field: str) -> None:
    if url and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail=f"{field} must be a valid HTTPS URL.")


# ─── GET /api/tokens/balance ─────────────────────────────────────────────────

@router.get("/balance")
async def balance_endpoint(request: Request):
    user = get_current_user(request)
    branch_id = _resolve_branch(user)
    try:
        data = await get_balance(branch_id)
        return {"success": True, "data": data}
    except Exception:
        logger.error("token_balance_fetch_failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch token balance.")


# ─── GET /api/tokens/usage ───────────────────────────────────────────────────

@router.get("/usage")
async def usage_endpoint(request: Request, user_id: str = None):
    user = get_current_user(request)
    branch_id = _resolve_branch(user)
    # auth: dynamic gate — only branch-wide stats require owner/admin
    if not user_id and user["role"] not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        data = await get_usage_stats(branch_id, user_id=user_id)
        return {"success": True, "data": data}
    except Exception:
        logger.error("token_usage_stats_fetch_failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch usage stats.")


# ─── GET /api/tokens/usage/me ────────────────────────────────────────────────

@router.get("/usage/me")
async def my_usage_endpoint(request: Request):
    user = get_current_user(request)
    branch_id = _resolve_branch(user)
    try:
        data = await get_usage_stats(branch_id, user_id=user["id"])
        return {"success": True, "data": data}
    except Exception:
        logger.error("my_token_usage_fetch_failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch your usage stats.")


# ─── GET /api/tokens/packs ──────────────────────────────────────────────────

@router.get("/packs")
async def packs_endpoint(request: Request):
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

    subscriptions_list = [
        {
            "id": plan_id,
            "tokens_per_month": info["tokens_per_month"],
            "price_inr": info["price_inr"],
            "label": info["label"],
        }
        for plan_id, info in SUBSCRIPTION_PLANS.items()
    ]

    return {"success": True, "data": {"packs": packs_list, "subscriptions": subscriptions_list}}


# ─── PUT /api/tokens/limits ──────────────────────────────────────────────────

@router.put("/limits")
async def limits_endpoint(request: Request, user: dict = Depends(require_owner)):
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
    except Exception:
        logger.error("token_limits_update_failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update limits.")


# ─── POST /api/tokens/create-checkout-session ────────────────────────────────

@router.post("/create-checkout-session")
async def create_checkout_session_endpoint(
    request: Request, user: dict = Depends(require_owner)
):
    branch_id = _resolve_branch(user)
    body = await request.json()
    pack_id = (body.get("pack_id") or "").strip()
    success_url = (body.get("success_url") or "").strip()
    cancel_url = (body.get("cancel_url") or "").strip()

    if not pack_id:
        raise HTTPException(status_code=400, detail="pack_id is required.")
    if pack_id not in PACKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown pack: {pack_id}. Available: {', '.join(PACKS.keys())}",
        )
    _validate_redirect_url(success_url, "success_url")
    _validate_redirect_url(cancel_url, "cancel_url")
    if not os.getenv("RAZORPAY_KEY_ID"):
        raise HTTPException(status_code=400, detail="Razorpay is not configured on this server.")

    try:
        result = await create_checkout_session(
            pack_id=pack_id,
            branch_id=branch_id,
            user_id=user["id"],
            success_url=success_url or "https://app.eduflow.in?recharge=success",
            cancel_url=cancel_url or "https://app.eduflow.in?recharge=cancel",
        )
        return {"success": True, "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.error("create_checkout_session_failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create checkout session.")


# ─── POST /api/tokens/create-subscription-session ────────────────────────────

@router.post("/create-subscription-session")
async def create_subscription_session_endpoint(
    request: Request, user: dict = Depends(require_owner)
):
    branch_id = _resolve_branch(user)
    body = await request.json()
    plan_id = (body.get("plan_id") or "").strip()
    success_url = (body.get("success_url") or "").strip()
    cancel_url = (body.get("cancel_url") or "").strip()

    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required.")
    if plan_id not in SUBSCRIPTION_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown plan: {plan_id}. Available: {', '.join(SUBSCRIPTION_PLANS.keys())}",
        )
    _validate_redirect_url(success_url, "success_url")
    _validate_redirect_url(cancel_url, "cancel_url")
    if not os.getenv("RAZORPAY_KEY_ID"):
        raise HTTPException(status_code=400, detail="Razorpay is not configured on this server.")

    try:
        result = await create_subscription_session(
            plan_id=plan_id,
            branch_id=branch_id,
            owner_id=user["id"],
            success_url=success_url or "https://app.eduflow.in?recharge=success",
            cancel_url=cancel_url or "https://app.eduflow.in?recharge=cancel",
        )
        return {"success": True, "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.error("create_subscription_session_failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create subscription session.")


# ─── POST /api/tokens/webhook ────────────────────────────────────────────────
# No JWT auth — Razorpay signature verification replaces it.

@router.post("/webhook")
async def razorpay_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")

    if not os.getenv("RAZORPAY_WEBHOOK_SECRET"):
        raise HTTPException(status_code=400, detail="Webhook endpoint not configured.")

    try:
        event = verify_webhook(raw_body, signature)
    except (razorpay.errors.SignatureVerificationError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    event_type = event.get("event")
    payload = event.get("payload") or {}

    def _entity(key: str) -> dict:
        return (payload.get(key) or {}).get("entity") or {}

    try:
        if event_type == "payment_link.paid":
            await handle_payment_link_paid(_entity("payment_link"))
        elif event_type == "subscription.activated":
            await handle_subscription_activated(_entity("subscription"))
        elif event_type == "subscription.charged":
            await handle_subscription_charged(_entity("subscription"), _entity("payment").get("id"))
        elif event_type == "subscription.cancelled":
            await handle_subscription_cancelled(_entity("subscription"))
        else:
            logger.info("razorpay_webhook_unhandled_event", extra={"event_type": event_type})
    except Exception:
        logger.error(
            "razorpay_webhook_handler_error",
            extra={"event_type": event_type},
            exc_info=True,
        )
        # Return 200 to prevent a Razorpay retry storm — log the error for investigation.
        return {"received": True, "error": "handler_failed"}

    return {"received": True}
