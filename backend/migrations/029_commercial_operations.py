"""Migration 029: indexes for CRM, campus retail, and legal entities.

Index-only and idempotent. It never seeds, rewrites, backfills, or deletes school data.
"""

from __future__ import annotations


async def migrate(db=None):
    if db is None:
        raise RuntimeError("Run migration 029 through migrations/run_all.py")

    await db.legal_entities.create_index(
        [("schoolId", 1), ("branch_id", 1), ("code", 1)], unique=True
    )
    await db.legal_entities.create_index(
        [("schoolId", 1), ("branch_id", 1), ("is_default", 1)],
        unique=True, partialFilterExpression={"is_default": True, "is_active": True},
    )
    await db.commercial_sequences.create_index(
        [("schoolId", 1), ("branch_id", 1), ("entity_id", 1), ("kind", 1), ("year", 1)], unique=True
    )
    await db.crm_activities.create_index([("enquiry_id", 1), ("occurred_at", -1)])
    # tenant-scope: intentional — the hash embeds schoolId and branch_id, so this
    # global unique index cannot collide across tenants (audit A-1, 2026-08-05).
    await db.crm_contact_keys.create_index("contact_hash", unique=True)
    await db.crm_opportunities.create_index([("entity_id", 1), ("stage", 1), ("updated_at", -1)])
    await db.commercial_products.create_index(
        [("schoolId", 1), ("branch_id", 1), ("entity_id", 1), ("sku", 1)], unique=True
    )
    await db.pos_shifts.create_index([("entity_id", 1), ("cashier_id", 1), ("status", 1)])
    await db.pos_shifts.create_index(
        [("schoolId", 1), ("branch_id", 1), ("entity_id", 1), ("cashier_id", 1)],
        name="uniq_open_pos_shift", unique=True,
        partialFilterExpression={"status": "open"},
    )
    await db.retail_sales.create_index(
        [("schoolId", 1), ("branch_id", 1), ("entity_id", 1), ("receipt_number", 1)], unique=True
    )
    await db.retail_returns.create_index(
        [("schoolId", 1), ("branch_id", 1), ("entity_id", 1), ("return_number", 1)], unique=True
    )
    await db.retail_returns.create_index([("sale_id", 1), ("status", 1)])
    await db.retail_idempotency.create_index(
        [("schoolId", 1), ("branch_id", 1), ("key", 1)], unique=True
    )
    await db.retail_return_idempotency.create_index(
        [("schoolId", 1), ("branch_id", 1), ("key", 1)], unique=True
    )


if __name__ == "__main__":
    raise SystemExit("Run through: python backend/migrations/run_all.py")
