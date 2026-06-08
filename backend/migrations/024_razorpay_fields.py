from __future__ import annotations


async def migrate(db) -> None:
    """Vendor change Stripe→Razorpay (2026-06-08): rename vendor-specific fields.

    - token_balances.stripe_customer_id  → razorpay_customer_id
    - token_purchases.stripe_session_id  → razorpay_reference_id
    - drop the old token_purchases_stripe_session_id unique index (replaced by
      token_purchases_razorpay_reference_id in database._create_indexes()).

    The subscription_* fields are vendor-neutral and unchanged; each token_purchases
    row keeps the payment_provider value recorded when it was written.
    """
    await db.token_balances.update_many(
        {"stripe_customer_id": {"$exists": True}},
        {"$rename": {"stripe_customer_id": "razorpay_customer_id"}},
    )
    await db.token_balances.update_many(
        {"razorpay_customer_id": {"$exists": False}},
        {"$set": {"razorpay_customer_id": None}},
    )
    await db.token_purchases.update_many(
        {"stripe_session_id": {"$exists": True}},
        {"$rename": {"stripe_session_id": "razorpay_reference_id"}},
    )
    try:
        await db.token_purchases.drop_index("token_purchases_stripe_session_id")
    except Exception:
        pass  # index may not exist (fresh DB or already dropped) — best-effort cleanup
