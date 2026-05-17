from __future__ import annotations


async def migrate(db) -> None:
    """Add Stripe subscription fields to token_balances documents (Story 7-42)."""
    await db.token_balances.update_many(
        {"stripe_customer_id": {"$exists": False}},
        {
            "$set": {
                "stripe_customer_id": None,
                "subscription_id": None,
                "subscription_status": None,
                "subscription_plan": None,
                "subscription_current_period_end": None,
            }
        },
    )
