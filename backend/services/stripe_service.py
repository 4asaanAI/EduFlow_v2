from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import stripe

from pymongo.errors import DuplicateKeyError

from database import get_db
from services.token_service import DEFAULT_ROLE_LIMITS, PACKS

logger = logging.getLogger(__name__)

SUBSCRIPTION_PLANS: dict[str, dict] = {
    "monthly_school_starter": {
        "tokens_per_month": 2_000_000,
        "price_inr": 2499,
        "label": "Starter School — 2M tokens/month",
        "stripe_price_env": "STRIPE_PRICE_MONTHLY_SCHOOL_STARTER",
    },
    "monthly_school_pro": {
        "tokens_per_month": 5_000_000,
        "price_inr": 4999,
        "label": "Pro School — 5M tokens/month",
        "stripe_price_env": "STRIPE_PRICE_MONTHLY_SCHOOL_PRO",
    },
}


def _stripe_api_key() -> str:
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        raise ValueError("STRIPE_SECRET_KEY is not configured.")
    return key


async def create_checkout_session(
    pack_id: str,
    branch_id: str,
    user_id: str,
    success_url: str,
    cancel_url: str,
) -> dict:
    pack = PACKS.get(pack_id)
    if not pack:
        raise ValueError(f"Unknown pack: {pack_id}")

    stripe.api_key = _stripe_api_key()

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "inr",
                    "product_data": {"name": f"EduFlow Token Pack — {pack_id}"},
                    "unit_amount": pack["price_inr"] * 100,
                },
                "quantity": 1,
            }
        ],
        metadata={"branch_id": branch_id, "user_id": user_id, "pack_id": pack_id},
        success_url=success_url,
        cancel_url=cancel_url,
    )

    return {"checkout_url": session.url, "session_id": session.id}


async def create_subscription_session(
    plan_id: str,
    branch_id: str,
    owner_id: str,
    success_url: str,
    cancel_url: str,
) -> dict:
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    if not plan:
        raise ValueError(f"Unknown subscription plan: {plan_id}")

    price_id = os.getenv(plan["stripe_price_env"], "")
    if not price_id:
        raise ValueError(
            f"Stripe Price ID not configured for plan '{plan_id}'. "
            f"Set env var {plan['stripe_price_env']}."
        )

    stripe.api_key = _stripe_api_key()

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        metadata={"branch_id": branch_id, "owner_id": owner_id, "plan_id": plan_id},
        success_url=success_url,
        cancel_url=cancel_url,
    )

    return {"checkout_url": session.url, "session_id": session.id}


def verify_webhook(raw_body: bytes, sig_header: str) -> object:
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise ValueError("STRIPE_WEBHOOK_SECRET is not configured.")
    stripe.api_key = _stripe_api_key()
    return stripe.Webhook.construct_event(raw_body, sig_header, webhook_secret)


async def handle_checkout_completed(session: dict) -> None:
    if session.get("payment_status") != "paid" or session.get("mode") != "payment":
        return

    meta = session.get("metadata") or {}
    branch_id = meta.get("branch_id")
    user_id = meta.get("user_id")
    pack_id = meta.get("pack_id")
    session_id = session.get("id")

    if not all([branch_id, user_id, pack_id, session_id]):
        logger.warning(
            "checkout_completed_missing_metadata",
            extra={"session_id": session_id},
        )
        return

    pack = PACKS.get(pack_id)
    if not pack:
        logger.error(
            "checkout_completed_unknown_pack",
            extra={"pack_id": pack_id, "session_id": session_id},
        )
        return

    db = get_db()
    existing = await db.token_purchases.find_one({"stripe_session_id": session_id})
    if existing:
        logger.info(
            "checkout_completed_already_processed",
            extra={"session_id": session_id},
        )
        return

    await purchase_topup_stripe(
        db, branch_id, user_id, pack_id, session_id, pack["tokens"]
    )


async def handle_subscription_created(subscription: dict) -> None:
    meta = subscription.get("metadata") or {}
    branch_id = meta.get("branch_id")
    plan_id = meta.get("plan_id")
    subscription_id = subscription.get("id")
    customer_id = subscription.get("customer")
    status = subscription.get("status", "active")
    current_period_end = subscription.get("current_period_end")

    if not branch_id:
        logger.warning(
            "subscription_created_missing_branch_id",
            extra={"subscription_id": subscription_id},
        )
        return

    period_end_iso = (
        datetime.fromtimestamp(current_period_end, tz=timezone.utc).isoformat()
        if current_period_end
        else None
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
                "stripe_customer_id": customer_id,
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
        "subscription_created",
        extra={"branch_id": branch_id, "subscription_id": subscription_id, "plan_id": plan_id},
    )


async def handle_invoice_payment_succeeded(invoice: dict) -> None:
    if invoice.get("billing_reason") != "subscription_cycle":
        return

    subscription_id = invoice.get("subscription")
    invoice_id = invoice.get("id")

    if not subscription_id or not invoice_id:
        logger.warning("invoice_payment_missing_ids", extra={"invoice_id": invoice_id})
        return

    db = get_db()

    idempotency_key = f"invoice_{invoice_id}"
    existing = await db.token_purchases.find_one({"stripe_session_id": idempotency_key})
    if existing:
        logger.info("invoice_already_processed", extra={"invoice_id": invoice_id})
        return

    balance_doc = await db.token_balances.find_one({"subscription_id": subscription_id})
    if not balance_doc:
        logger.warning(
            "invoice_payment_no_balance_doc",
            extra={"subscription_id": subscription_id},
        )
        return

    branch_id = balance_doc["branch_id"]
    plan_id = balance_doc.get("subscription_plan")
    plan = SUBSCRIPTION_PLANS.get(plan_id) if plan_id else None
    tokens = plan["tokens_per_month"] if plan else 0

    if tokens <= 0:
        logger.warning(
            "invoice_payment_zero_tokens",
            extra={"plan_id": plan_id, "subscription_id": subscription_id},
        )
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    lines_data = invoice.get("lines", {}).get("data", [])
    current_period_end = (lines_data[0].get("period") or {}).get("end") if lines_data else None
    period_end_iso = (
        datetime.fromtimestamp(current_period_end, tz=timezone.utc).isoformat()
        if current_period_end
        else None
    )

    try:
        await db.token_purchases.insert_one(
            {
                "branch_id": branch_id,
                "user_id": "subscription_renewal",
                "pack_id": plan_id,
                "tokens": tokens,
                "price_inr": plan["price_inr"] if plan else 0,
                "stripe_session_id": idempotency_key,
                "payment_provider": "stripe",
                "created_at": now_iso,
            }
        )
    except DuplicateKeyError:
        logger.info("invoice_already_processed_concurrent", extra={"invoice_id": invoice_id})
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
        extra={"branch_id": branch_id, "tokens": tokens, "invoice_id": invoice_id},
    )


async def handle_subscription_deleted(subscription: dict) -> None:
    meta = subscription.get("metadata") or {}
    branch_id = meta.get("branch_id")
    subscription_id = subscription.get("id")
    db = get_db()

    if not branch_id and subscription_id:
        balance_doc = await db.token_balances.find_one({"subscription_id": subscription_id})
        if balance_doc:
            branch_id = balance_doc.get("branch_id")

    if not branch_id:
        logger.warning(
            "subscription_deleted_no_branch",
            extra={"subscription_id": subscription_id},
        )
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


async def purchase_topup_stripe(
    db,
    branch_id: str,
    user_id: str,
    pack_id: str,
    stripe_session_id: str,
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
                "stripe_session_id": stripe_session_id,
                "payment_provider": "stripe",
                "created_at": now_iso,
            }
        )
    except DuplicateKeyError:
        logger.info(
            "stripe_topup_already_processed",
            extra={"session_id": stripe_session_id},
        )
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
        "stripe_topup_credited",
        extra={
            "branch_id": branch_id,
            "user_id": user_id,
            "pack_id": pack_id,
            "tokens": tokens,
            "session_id": stripe_session_id,
        },
    )
