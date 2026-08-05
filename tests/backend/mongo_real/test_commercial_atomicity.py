from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.actor_context import ActorContext
from services.commercial_service import CommercialConflictError, create_sale
from services.txn_context import reset_current_session, set_current_session

pytestmark = [pytest.mark.asyncio, pytest.mark.mongo_real]


def _actor():
    return ActorContext(
        user_id="owner-1", role="owner", sub_category=None,
        school_id="school-commercial", branch_id="branch-joya",
        now_fn=lambda: datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc),
    )


async def _seed(db):
    scope = {"schoolId": "school-commercial", "branch_id": "branch-joya"}
    await db.legal_entities.insert_one({
        "_id": "entity-1", "id": "entity-1", **scope, "name": "School",
        "code": "SCH", "entity_type": "school", "is_group": False,
        "is_active": True, "is_default": True,
    })
    await db.pos_shifts.insert_one({
        "_id": "shift-1", "id": "shift-1", **scope, "entity_id": "entity-1",
        "cashier_id": "owner-1", "status": "open", "opening_cash_paise": 0,
    })
    for suffix, stock in (("a", 5), ("b", 0)):
        await db.inventory_items.insert_one({
            "_id": f"item-{suffix}", "id": f"item-{suffix}", **scope,
            "sku": suffix.upper(), "name": f"Item {suffix.upper()}",
            "is_active": True, "on_hand": stock, "quantity": stock,
        })
        await db.commercial_products.insert_one({
            "_id": f"product-{suffix}", "id": f"product-{suffix}", **scope,
            "entity_id": "entity-1", "inventory_item_id": f"item-{suffix}",
            "sku": suffix.upper(), "name": f"Item {suffix.upper()}",
            "unit_price_paise": 10000, "tax_rate_bps": 0, "is_active": True,
        })


async def test_mid_sale_stock_failure_rolls_back_every_collection(mongo_real_db, mongo_real_client):
    await _seed(mongo_real_db)
    session = await mongo_real_client.start_session()
    token = set_current_session(session)
    try:
        with pytest.raises(CommercialConflictError):
            async with session:
                async with session.start_transaction():
                    await create_sale(mongo_real_db, _actor(), {
                        "entity_id": "entity-1", "shift_id": "shift-1",
                        "lines": [
                            {"product_id": "product-a", "quantity": 1},
                            {"product_id": "product-b", "quantity": 1},
                        ],
                        "payments": [{"mode": "cash", "amount": 200}],
                    }, idempotency_key="rollback-sale", session=session)
    finally:
        reset_current_session(token)

    first = await mongo_real_db.inventory_items.find_one({"id": "item-a"})
    assert first["on_hand"] == 5
    assert await mongo_real_db.stock_movements.count_documents({}) == 0
    assert await mongo_real_db.retail_sales.count_documents({}) == 0
    assert await mongo_real_db.retail_idempotency.count_documents({}) == 0
