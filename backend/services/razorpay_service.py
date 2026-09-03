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
import uuid
from datetime import datetime, timedelta, timezone

import razorpay

from pymongo.errors import DuplicateKeyError

from database import get_db, get_raw_db, get_txn_session
from services import audit_changes
from services.audit_service import write_audit
from services.token_service import DEFAULT_ROLE_LIMITS, PACKS
from tenant import _school_id_var

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


async def begin_webhook_event(event_id: str, event_type: str, event: dict) -> bool:
    """Journal a verified event before handling; return False if already processed."""
    db = get_raw_db()  # provider-wide infrastructure record, before tenant resolution
    existing = await db.razorpay_webhook_inbox.find_one({"id": event_id})
    if existing and existing.get("status") in {"processed", "ignored"}:
        return False
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        retryable = {"id": event_id, "status": "failed"}
        if existing.get("status") == "processing":
            stale_before = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            retryable = {"id": event_id, "status": "processing", "updated_at": {"$lt": stale_before}}
        result = await db.razorpay_webhook_inbox.update_one(
            retryable,
            {"$set": {"status": "processing", "updated_at": now, "last_error": None}, "$inc": {"attempts": 1}},
        )
        return result.matched_count == 1
    doc = {
        "_id": event_id,
        "id": event_id,
        "event_type": event_type,
        "event": event,
        "status": "processing",
        "attempts": 1,
        "received_at": now,
        "updated_at": now,
        "last_error": None,
    }
    try:
        await db.razorpay_webhook_inbox.insert_one(doc)
    except DuplicateKeyError:
        # Another worker owns the inserted processing lease.
        return False
    return True


async def finish_webhook_event(event_id: str, *, error: str | None = None,
                               outcome: str = "processed") -> None:
    db = get_raw_db()  # provider-wide infrastructure record, before tenant resolution
    now = datetime.now(timezone.utc).isoformat()
    update = {
        "status": "failed" if error else outcome,
        "updated_at": now,
        "last_error": error,
    }
    if not error and outcome == "processed":
        update["processed_at"] = now
    if not error and outcome == "ignored":
        update["ignored_at"] = now
    await db.razorpay_webhook_inbox.update_one({"id": event_id}, {"$set": update})


async def create_school_fee_checkout(
    db,
    *,
    school_id: str,
    branch_id: str,
    user_id: str,
    transaction_ids: list[str],
    success_url: str | None = None,
) -> dict:
    """Create an optional hosted payment link for already-authorized fee charges."""
    if not transaction_ids:
        raise ValueError("transaction_ids is required")
    unique_ids = list(dict.fromkeys(transaction_ids))
    rows = await db.fee_transactions.find(
        {"id": {"$in": unique_ids}, "deleted": {"$ne": True}}, {"_id": 0}
    ).to_list(len(unique_ids))
    if len(rows) != len(unique_ids):
        raise ValueError("One or more fee transactions were not found")
    total = 0.0
    for row in rows:
        status = row.get("status")
        amount = float(row.get("amount") or 0)
        if status == "partial":
            amount = max(amount - float(row.get("paid_amount") or 0), 0)
        elif status not in {"pending", "overdue", "unpaid"}:
            amount = 0
        total += amount
    if total <= 0:
        raise ValueError("Selected transactions have no outstanding balance")

    checkout_id = str(uuid.uuid4())
    request_data = {
        "amount": int(round(total * 100)),
        "currency": "INR",
        "description": f"EduFlow school fees ({len(rows)} charge{'s' if len(rows) != 1 else ''})",
        "notes": {
            "purpose": "school_fee",
            "school_id": school_id,
            "branch_id": branch_id,
            "user_id": user_id,
            "checkout_id": checkout_id,
        },
    }
    if success_url:
        request_data["callback_url"] = success_url
        request_data["callback_method"] = "get"
    link = _razorpay_client().payment_link.create(request_data)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": checkout_id,
        "schoolId": school_id,
        "branch_id": branch_id,
        "user_id": user_id,
        "transaction_ids": unique_ids,
        "amount": total,
        "currency": "INR",
        "status": "created",
        "razorpay_reference_id": link.get("id"),
        "checkout_url": link.get("short_url"),
        "created_at": now,
        "updated_at": now,
    }
    await db.school_fee_checkouts.insert_one({**doc, "_id": checkout_id})
    # R4-2: a family being asked to pay online is a school money record and recorded
    # nothing. The webhook plumbing in this module stays unaudited on purpose (see
    # audit_coverage): a dedupe inbox row and a token-balance counter are machinery
    # nobody asks "who did that?" about. A fee demand sent to a family is not.
    await write_audit(
        db,
        action="school_fee_checkout_create",
        entity_id=checkout_id,
        collection="school_fee_checkouts",
        changed_by=doc.get("created_by") or "system",
        changed_by_role="",
        school_id=doc.get("schoolId") or "",
        branch_id=doc.get("branch_id") or "",
        changes=audit_changes.created(doc),
        reason=f"Online payment link for {total} raised",
    )
    return doc


async def handle_school_fee_payment_link_paid(link: dict) -> None:
    """Settle only the charges recorded on the matching checkout."""
    if link.get("status") != "paid":
        return
    notes = link.get("notes") or {}
    branch_id = notes.get("branch_id")
    checkout_id = notes.get("checkout_id")
    reference_id = link.get("id")
    if not branch_id or not checkout_id or not reference_id:
        raise ValueError("School-fee payment link is missing required notes")
    raw_db = get_raw_db()
    school_id = await _resolve_school_for_branch(raw_db, branch_id)
    if not school_id:
        raise ValueError("School-fee payment link branch cannot be resolved")
    ctx_token = _school_id_var.set(school_id)
    try:
        db = get_db()
        from services.txn_context import reset_current_session, set_current_session
        session = await get_txn_session()
        session_token = set_current_session(session)
        try:
            async with session:
                async with session.start_transaction():
                    checkout = await db.school_fee_checkouts.find_one(
                        {"id": checkout_id}, session=session
                    )
                    if not checkout:
                        raise ValueError("School-fee checkout was not found")
                    if checkout.get("status") == "paid":
                        return
                    expected_paise = int(round(float(checkout.get("amount") or 0) * 100))
                    paid_paise = link.get("amount_paid") or link.get("amount")
                    if paid_paise is not None and int(paid_paise) != expected_paise:
                        raise ValueError("School-fee payment amount does not match checkout")
                    if link.get("currency") and link.get("currency") != checkout.get("currency", "INR"):
                        raise ValueError("School-fee payment currency does not match checkout")
                    if checkout.get("status") == "created":
                        claimed = await db.school_fee_checkouts.update_one(
                            {"id": checkout_id, "status": "created"},
                            {"$set": {"status": "processing", "updated_at": datetime.now(timezone.utc).isoformat()}},
                            session=session,
                        )
                        if claimed.matched_count == 0:
                            raise ValueError("School-fee checkout is being processed")
                    elif checkout.get("status") != "processing":
                        raise ValueError("School-fee checkout is not payable")
                    now = datetime.now(timezone.utc).isoformat()
                    for transaction_id in checkout.get("transaction_ids", []):
                        transaction = await db.fee_transactions.find_one(
                            {"id": transaction_id}, {"_id": 0}, session=session
                        )
                        if not transaction or transaction.get("deleted") is True:
                            raise ValueError("A checkout fee transaction no longer exists")
                        await db.fee_transactions.update_one({"id": transaction_id}, {"$set": {
                            "status": "paid",
                            "paid_amount": float(transaction.get("amount") or 0),
                            "paid_date": now[:10],
                            "payment_mode": "online",
                            "transaction_ref": reference_id,
                            "updated_at": now,
                        }}, session=session)
                    await db.school_fee_checkouts.update_one(
                        {"id": checkout_id, "status": "processing"}, {"$set": {
                            "status": "paid", "paid_at": now, "updated_at": now,
                            "razorpay_reference_id": reference_id,
                        }}, session=session,
                    )
                    # R4-2. Money arriving from a family is the single most disputed
                    # kind of record a school holds. Written INSIDE the transaction, so
                    # a settlement that rolls back cannot leave an audit row claiming a
                    # family paid when they did not.
                    await write_audit(
                        db,
                        action="school_fee_checkout_paid",
                        entity_id=checkout_id,
                        collection="school_fee_checkouts",
                        changed_by="razorpay",
                        changed_by_role="system",
                        school_id=checkout.get("schoolId") or "",
                        branch_id=checkout.get("branch_id") or "",
                        changes=audit_changes.bulk(
                            {"reference_id": reference_id, "paid_at": now},
                            affected=len(checkout.get("transaction_ids", [])),
                        ),
                        reason="Online fee payment settled",
                    )
        finally:
            reset_current_session(session_token)
    finally:
        _school_id_var.reset(ctx_token)

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
            "description": f"EduFlow Token Pack - {pack_id}",
            "notes": {"branch_id": branch_id, "user_id": user_id, "pack_id": pack_id, "kind": "topup"},
            "callback_url": success_url,
            "callback_method": "get",
        }
    )
    return {"checkout_url": link["short_url"], "session_id": link["id"]}


async def create_subscription_session(
    plan_id: str,
    branch_id: str,
    user_id: str,
    success_url: str,
    cancel_url: str,
) -> dict:
    """Create a Razorpay Subscription for an individual monthly token plan."""
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
            "notes": {"branch_id": branch_id, "user_id": user_id, "plan_id": plan_id, "kind": "subscription"},
        }
    )
    return {"checkout_url": subscription["short_url"], "session_id": subscription["id"]}


async def _resolve_school_for_branch(raw_db, branch_id: str) -> str | None:
    """Resolve the schoolId that owns branch_id. Returns None if not found."""
    branch = await raw_db.branches.find_one({"id": branch_id})
    if branch:
        return branch.get("schoolId")
    return None


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

    # R12.2: resolve school_id from branch, not from ambient env-default.
    raw_db = get_raw_db()
    school_id = await _resolve_school_for_branch(raw_db, branch_id)
    if not school_id:
        logger.error(
            "payment_link_paid_unresolvable_school",
            extra={"branch_id": branch_id, "reference_id": reference_id},
        )
        return

    ctx_token = _school_id_var.set(school_id)
    try:
        db = get_db()
        existing = await db.token_purchases.find_one({"razorpay_reference_id": reference_id})
        if existing:
            logger.info("payment_link_paid_already_processed", extra={"reference_id": reference_id})
            return
        await purchase_topup_razorpay(db, branch_id, user_id, pack_id, reference_id, pack["tokens"])
    finally:
        _school_id_var.reset(ctx_token)


async def handle_subscription_activated(subscription: dict) -> None:
    """Store subscription fields on token_balances when a subscription activates."""
    notes = subscription.get("notes") or {}
    branch_id = notes.get("branch_id")
    plan_id = notes.get("plan_id")
    user_id = notes.get("user_id")
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

    # R12.2: resolve school_id from branch, not from ambient env-default.
    raw_db = get_raw_db()
    school_id = await _resolve_school_for_branch(raw_db, branch_id)
    if not school_id:
        logger.error(
            "subscription_activated_unresolvable_school",
            extra={"branch_id": branch_id, "subscription_id": subscription_id},
        )
        return

    ctx_token = _school_id_var.set(school_id)
    try:
        db = get_db()
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.token_balances.update_one(
            {"branch_id": branch_id},
            {
                "$set": {
                    "subscription_id": subscription_id,
                    "subscription_user_id": user_id,
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
    finally:
        _school_id_var.reset(ctx_token)
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

    # R12.2: use raw_db to find the balance doc cross-tenant, then scope to resolved school.
    raw_db = get_raw_db()
    notes = subscription.get("notes") or {}

    # balance_doc lookup needs to span all schools (subscription_id is globally unique).
    balance_doc = await raw_db.token_balances.find_one({"subscription_id": subscription_id})
    if not balance_doc:
        # Race condition: subscription.charged and subscription.activated arrive simultaneously.
        # activated creates the balance doc; if charged ran first the doc doesn't exist yet.
        # Fall back to the notes on the subscription object which carry branch_id and plan_id.
        branch_id_from_notes = notes.get("branch_id")
        if not branch_id_from_notes:
            logger.warning("subscription_charged_no_balance_doc", extra={"subscription_id": subscription_id})
            return
        balance_doc = await raw_db.token_balances.find_one({"branch_id": branch_id_from_notes})
        if not balance_doc:
            logger.warning("subscription_charged_no_balance_doc", extra={"subscription_id": subscription_id})
            return

    branch_id = balance_doc["branch_id"]
    school_id = balance_doc.get("schoolId") or await _resolve_school_for_branch(raw_db, branch_id)
    if not school_id:
        logger.error(
            "subscription_charged_unresolvable_school",
            extra={"branch_id": branch_id, "subscription_id": subscription_id},
        )
        return

    user_id = notes.get("user_id") or balance_doc.get("subscription_user_id", "unknown")
    plan_id = balance_doc.get("subscription_plan") or notes.get("plan_id")
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

    # R12.2: scope DB to the resolved school.
    ctx_token = _school_id_var.set(school_id)
    try:
        db = get_db()
        existing = await db.token_purchases.find_one({"razorpay_reference_id": reference_id})
        if existing:
            logger.info("subscription_charged_already_processed", extra={"reference_id": reference_id})
            return

        # R12.3: atomic - both operations in a single transaction.
        session = await get_txn_session()
        async with session:
            async with session.start_transaction():
                try:
                    await db.token_purchases.insert_one(
                        {
                            "branch_id": branch_id,
                            "user_id": user_id,
                            "pack_id": plan_id,
                            "tokens": tokens,
                            "price_inr": plan["price_inr"] if plan else 0,
                            "razorpay_reference_id": reference_id,
                            "payment_provider": "razorpay",
                            "created_at": now_iso,
                        },
                        session=session,
                    )
                except DuplicateKeyError:
                    logger.info("subscription_charged_already_processed_concurrent", extra={"reference_id": reference_id})
                    return

                await db.token_balances.update_one(
                    {"branch_id": branch_id},
                    {
                        "$inc": {f"personal_topups.{user_id}": tokens},
                        "$set": {
                            "updated_at": now_iso,
                            **({"subscription_current_period_end": period_end_iso} if period_end_iso else {}),
                        },
                    },
                    session=session,
                )
    finally:
        _school_id_var.reset(ctx_token)

    logger.info(
        "subscription_renewal_credited",
        extra={"branch_id": branch_id, "tokens": tokens, "reference_id": reference_id},
    )


async def handle_subscription_cancelled(subscription: dict) -> None:
    """Mark a subscription canceled on token_balances."""
    notes = subscription.get("notes") or {}
    branch_id = notes.get("branch_id")
    subscription_id = subscription.get("id")

    # R12.2: use raw_db to look up balance doc cross-tenant first.
    raw_db = get_raw_db()
    school_id = None

    if not branch_id and subscription_id:
        balance_doc = await raw_db.token_balances.find_one({"subscription_id": subscription_id})
        if balance_doc:
            branch_id = balance_doc.get("branch_id")
            school_id = balance_doc.get("schoolId")

    if not branch_id:
        logger.warning("subscription_cancelled_no_branch", extra={"subscription_id": subscription_id})
        return

    if not school_id:
        school_id = await _resolve_school_for_branch(raw_db, branch_id)
    if not school_id:
        logger.error(
            "subscription_cancelled_unresolvable_school",
            extra={"branch_id": branch_id, "subscription_id": subscription_id},
        )
        return

    ctx_token = _school_id_var.set(school_id)
    try:
        db = get_db()
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.token_balances.update_one(
            {"branch_id": branch_id},
            {"$set": {"subscription_status": "canceled", "updated_at": now_iso}},
        )
    finally:
        _school_id_var.reset(ctx_token)
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

    # R12.3: atomic - claim insert and balance increment in a single transaction.
    session = await get_txn_session()
    async with session:
        async with session.start_transaction():
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
                    },
                    session=session,
                )
            except DuplicateKeyError:
                logger.info("razorpay_topup_already_processed", extra={"reference_id": razorpay_reference_id})
                return

            # R12.3 AC1: removed "personal_topups": {} from $setOnInsert - it conflicted
            # with $inc on personal_topups.{user_id} when the balance doc didn't yet exist.
            # MongoDB's $inc on a sub-path auto-creates the parent object on upsert.
            await db.token_balances.update_one(
                {"branch_id": branch_id},
                {
                    "$inc": {f"personal_topups.{user_id}": tokens},
                    "$set": {"updated_at": now_iso},
                    "$setOnInsert": {
                        "branch_id": branch_id,
                        "role_limits": DEFAULT_ROLE_LIMITS,
                        "school_topup_pool": 0,
                        "self_recharge_enabled": True,
                        "created_at": now_iso,
                    },
                },
                upsert=True,
                session=session,
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
