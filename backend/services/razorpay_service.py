from __future__ import annotations

"""Razorpay billing integration for EduFlow token recharge + subscriptions.

Replaces the former Stripe integration (vendor change, 2026-06-08). The hosted-redirect
UX is preserved: one-time top-ups use **Razorpay Payment Links** (which return a hosted
`short_url`), and subscriptions use **Razorpay Subscriptions** (also a `short_url`), so the
route response shape (`{checkout_url, session_id}`) and the webhook-driven crediting model
are unchanged from the caller's point of view.

Webhook events handled: ``payment_link.paid`` (top-up), ``subscription.activated``,
``subscription.charged`` (renewal), ``subscription.cancelled``.

DB fields (renamed from the Stripe schema): ``razorpay_reference_id`` is the idempotency
key on ``token_purchases`` (unique-indexed); ``razorpay_customer_id`` on ``token_balances``.
``payment_provider`` is ``"razorpay"``.
"""

import json
import logging
import os
from datetime import datetime, timezone

import razorpay

from pymongo.errors import DuplicateKeyError

from database import get_db
from services.token_service import DEFAULT_ROLE_LIMITS, PACKS

logger = logging.getLogger(__name__)

SUBSCRIPTION_PLANS: dict[str, dict] = {
    "monthly_starter": {
        "tokens_per_month": 1_000_000,
        "price_inr": 999,
        "label": "Starter",
        "subtitle": "Up to 200 students",
        "razorpay_plan_env": "RAZORPAY_PLAN_MONTHLY_STARTER",
        "popular": False,
    },
    "monthly_growth": {
        "tokens_per_month": 3_000_000,
        "price_inr": 2499,
        "label": "Growth",
        "subtitle": "200–500 students",
        "razorpay_plan_env": "RAZORPAY_PLAN_MONTHLY_GROWTH",
        "popular": True,
    },
    "monthly_enterprise": {
        "tokens_per_month": 8_000_000,
        "price_inr": 4999,
        "label": "Enterprise",
        "subtitle": "500+ students",
        "razorpay_plan_env": "RAZORPAY_PLAN_MONTHLY_ENTERPRISE",
        "popular": False,
    },
}

# Number of billing cycles a monthly subscription runs before Razorpay stops it.
SUBSCRIPTION_TOTAL_COUNT = 12


def _razorpay_client() -> razorpay.Client:
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret:
        raise ValueError("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not configured.")
    return razorpay.Client(auth=(key_id, key_secret))


async def create_checkout_session(
    pack_id: str,
    branch_id: str,
    user_id: str,
    success_url: str,
    cancel_url: str,
) -> dict:
    """Create a Razorpay Payment Link for a one-time token top-up."""
    pack = PACKS.get(pack_id)
    if not pack:
        raise ValueError(f"Unknown pack: {pack_id}")

    client = _razorpay_client()
    link = client.payment_link.create(
        {
            "amount": pack["price_inr"] * 100,
            "currency": "INR",
            "description": f"EduFlow Token Pack — {pack_id}",
            "notes": {"branch_id": branch_id, "user_id": user_id, "pack_id": pack_id, "kind": "topup"},
            "callback_url": success_url,
            "callback_method": "get",
        }
    )
    return {"checkout_url": link["short_url"], "session_id": link["id"]}


async def create_subscription_session(
    plan_id: str,
    branch_id: str,
    owner_id: str,
    success_url: str,
    cancel_url: str,
) -> dict:
    """Create a Razorpay Subscription for a recurring school plan."""
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    if not plan:
        raise ValueError(f"Unknown subscription plan: {plan_id}")

    razorpay_plan_id = os.getenv(plan["razorpay_plan_env"], "")
    if not razorpay_plan_id:
        raise ValueError(
            f"Razorpay Plan ID not configured for plan '{plan_id}'. "
            f"Set env var {plan['razorpay_plan_env']}."
        )

    client = _razorpay_client()
    subscription = client.subscription.create(
        {
            "plan_id": razorpay_plan_id,
            "total_count": SUBSCRIPTION_TOTAL_COUNT,
            "customer_notify": 1,
            "notes": {"branch_id": branch_id, "owner_id": owner_id, "plan_id": plan_id, "kind": "subscription"},
        }
    )
    return {"checkout_url": subscription["short_url"], "session_id": subscription["id"]}


def verify_webhook(raw_body: bytes, signature: str) -> dict:
    """Verify a Razorpay webhook signature and return the parsed event dict.

    Raises ``razorpay.errors.SignatureVerificationError`` on a bad signature and
    ``ValueError`` if the webhook secret is not configured.
    """
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise ValueError("RAZORPAY_WEBHOOK_SECRET is not configured.")
    body_str = raw_body.decode("utf-8") if isinstance(raw_body, (bytes, bytearray)) else str(raw_body)
    _razorpay_client().utility.verify_webhook_signature(body_str, signature, webhook_secret)
    return json.loads(body_str)


async def handle_payment_link_paid(link: dict) -> None:
    """Credit a one-time top-up from a paid Razorpay Payment Link entity."""
    if link.get("status") != "paid":
        return

    notes = link.get("notes") or {}
    branch_id = notes.get("branch_id")
    user_id = notes.get("user_id")
    pack_id = notes.get("pack_id")
    reference_id = link.get("id")

    if not all([branch_id, user_id, pack_id, reference_id]):
        logger.warning("payment_link_paid_missing_notes", extra={"reference_id": reference_id})
        return

    pack = PACKS.get(pack_id)
    if not pack:
        logger.error("payment_link_paid_unknown_pack", extra={"pack_id": pack_id, "reference_id": reference_id})
        return

    db = get_db()
    existing = await db.token_purchases.find_one({"razorpay_reference_id": reference_id})
    if existing:
        logger.info("payment_link_paid_already_processed", extra={"reference_id": reference_id})
        return

    await purchase_topup_razorpay(db, branch_id, user_id, pack_id, reference_id, pack["tokens"])


async def handle_subscription_activated(subscription: dict) -> None:
    """Store subscription fields on token_balances when a subscription activates."""
    notes = subscription.get("notes") or {}
    branch_id = notes.get("branch_id")
    plan_id = notes.get("plan_id")
    subscription_id = subscription.get("id")
    customer_id = subscription.get("customer_id")
    status = subscription.get("status", "active")
    current_end = subscription.get("current_end")

    if not branch_id:
        logger.warning("subscription_activated_missing_branch_id", extra={"subscription_id": subscription_id})
        return

    period_end_iso = (
        datetime.fromtimestamp(current_end, tz=timezone.utc).isoformat() if current_end else None
    )

    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.token_balances.update_one(
        {"branch_id": branch_id},
        {
            "$set": {
                "subscription_id": subscription_id,
                "subscription_status": status,
                "subscription_plan": plan_id,
                "subscription_current_period_end": period_end_iso,
                "razorpay_customer_id": customer_id,
                "updated_at": now_iso,
            },
            "$setOnInsert": {
                "branch_id": branch_id,
                "role_limits": DEFAULT_ROLE_LIMITS,
                "school_topup_pool": 0,
                "self_recharge_enabled": True,
                "personal_topups": {},
                "created_at": now_iso,
            },
        },
        upsert=True,
    )
    logger.info(
        "subscription_activated",
        extra={"branch_id": branch_id, "subscription_id": subscription_id, "plan_id": plan_id},
    )


async def handle_subscription_charged(subscription: dict, payment_id: str | None) -> None:
    """Credit the monthly token grant when a subscription renewal is charged."""
    subscription_id = subscription.get("id")
    # Idempotency reference: prefer the payment id, else the subscription cycle end.
    reference_id = f"subcharge_{payment_id}" if payment_id else f"subcharge_{subscription_id}_{subscription.get('current_end')}"

    if not subscription_id:
        logger.warning("subscription_charged_missing_id", extra={"reference_id": reference_id})
        return

    db = get_db()
    existing = await db.token_purchases.find_one({"razorpay_reference_id": reference_id})
    if existing:
        logger.info("subscription_charged_already_processed", extra={"reference_id": reference_id})
        return

    balance_doc = await db.token_balances.find_one({"subscription_id": subscription_id})
    if not balance_doc:
        logger.warning("subscription_charged_no_balance_doc", extra={"subscription_id": subscription_id})
        return

    branch_id = balance_doc["branch_id"]
    plan_id = balance_doc.get("subscription_plan")
    plan = SUBSCRIPTION_PLANS.get(plan_id) if plan_id else None
    tokens = plan["tokens_per_month"] if plan else 0

    if tokens <= 0:
        logger.warning("subscription_charged_zero_tokens", extra={"plan_id": plan_id, "subscription_id": subscription_id})
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    current_end = subscription.get("current_end")
    period_end_iso = (
        datetime.fromtimestamp(current_end, tz=timezone.utc).isoformat() if current_end else None
    )

    try:
        await db.token_purchases.insert_one(
            {
                "branch_id": branch_id,
                "user_id": "subscription_renewal",
                "pack_id": plan_id,
                "tokens": tokens,
                "price_inr": plan["price_inr"] if plan else 0,
                "razorpay_reference_id": reference_id,
                "payment_provider": "razorpay",
                "created_at": now_iso,
            }
        )
    except DuplicateKeyError:
        logger.info("subscription_charged_already_processed_concurrent", extra={"reference_id": reference_id})
        return

    await db.token_balances.update_one(
        {"branch_id": branch_id},
        {
            "$inc": {"school_topup_pool": tokens},
            "$set": {
                "updated_at": now_iso,
                **({"subscription_current_period_end": period_end_iso} if period_end_iso else {}),
            },
        },
    )
    logger.info(
        "subscription_renewal_credited",
        extra={"branch_id": branch_id, "tokens": tokens, "reference_id": reference_id},
    )


async def handle_subscription_cancelled(subscription: dict) -> None:
    """Mark a subscription canceled on token_balances."""
    notes = subscription.get("notes") or {}
    branch_id = notes.get("branch_id")
    subscription_id = subscription.get("id")
    db = get_db()

    if not branch_id and subscription_id:
        balance_doc = await db.token_balances.find_one({"subscription_id": subscription_id})
        if balance_doc:
            branch_id = balance_doc.get("branch_id")

    if not branch_id:
        logger.warning("subscription_cancelled_no_branch", extra={"subscription_id": subscription_id})
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.token_balances.update_one(
        {"branch_id": branch_id},
        {"$set": {"subscription_status": "canceled", "updated_at": now_iso}},
    )
    logger.info(
        "subscription_canceled",
        extra={"branch_id": branch_id, "subscription_id": subscription_id},
    )


async def purchase_topup_razorpay(
    db,
    branch_id: str,
    user_id: str,
    pack_id: str,
    razorpay_reference_id: str,
    tokens: int,
) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    pack = PACKS.get(pack_id, {})

    try:
        await db.token_purchases.insert_one(
            {
                "branch_id": branch_id,
                "user_id": user_id,
                "pack_id": pack_id,
                "tokens": tokens,
                "price_inr": pack.get("price_inr", 0),
                "razorpay_reference_id": razorpay_reference_id,
                "payment_provider": "razorpay",
                "created_at": now_iso,
            }
        )
    except DuplicateKeyError:
        logger.info("razorpay_topup_already_processed", extra={"reference_id": razorpay_reference_id})
        return

    await db.token_balances.update_one(
        {"branch_id": branch_id},
        {
            "$inc": {"school_topup_pool": tokens},
            "$set": {"updated_at": now_iso},
            "$setOnInsert": {
                "branch_id": branch_id,
                "role_limits": DEFAULT_ROLE_LIMITS,
                "school_topup_pool": 0,
                "self_recharge_enabled": True,
                "personal_topups": {},
                "created_at": now_iso,
            },
        },
        upsert=True,
    )
    logger.info(
        "razorpay_topup_credited",
        extra={
            "branch_id": branch_id,
            "user_id": user_id,
            "pack_id": pack_id,
            "tokens": tokens,
            "reference_id": razorpay_reference_id,
        },
    )
