"""Asset/inventory domain service — single shared write path (AD7).

Both the REST routes (`POST/PATCH/DELETE /api/ops/assets*`) and the AI tools
(`create_asset`, `update_asset`, `delete_asset`) call these functions.

**Parity decision (canonical = REST field set):** the legacy PATCH `$set` the
raw body; the service pins a mutable whitelist and adds an audit row on every
mutation (the routes wrote none).

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import uuid

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_query


class AssetValidationError(Exception):
    """Invalid input → HTTP 400."""


class AssetNotFoundError(Exception):
    """Unknown asset id within the caller's scope → HTTP 404."""


_MUTABLE_FIELDS = {"name", "category", "quantity", "location", "status",
                   "purchase_date", "maintenance_due"}


async def _audit(db, actor_ctx: ActorContext, *, action: str, asset_id: str, changes: dict) -> None:
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "asset",
            "entity_id": asset_id,
            "action": action,
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": changes,
            "reason": None,
            "created_at": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )


async def create_asset(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Create an asset. params: {name, category?, quantity?, location?, status?, purchase_date?, maintenance_due?}"""
    if not params.get("name"):
        raise AssetValidationError("name is required")
    try:
        quantity = int(params.get("quantity", 1))
    except (TypeError, ValueError):
        raise AssetValidationError("quantity must be a whole number")
    asset = {
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "name": params.get("name"),
        "category": params.get("category", ""),
        "quantity": quantity,
        "location": params.get("location", ""),
        "status": params.get("status", "good"),
        "purchase_date": params.get("purchase_date", ""),
        "maintenance_due": params.get("maintenance_due", ""),
        "created_by": actor_ctx.user_id,
        "created_by_role": actor_ctx.role,
        "created_by_sub_category": actor_ctx.sub_category or "",
    }
    await db.assets.insert_one({**asset, "_id": asset["id"]})
    await _audit(db, actor_ctx, action="create", asset_id=asset["id"], changes={"created": asset})
    return {"asset": asset}


async def update_asset(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Update an asset. params: {asset_id, <any of the mutable fields>}"""
    asset_id = params.get("asset_id")
    if not asset_id:
        raise AssetValidationError("asset_id is required")
    existing = await db.assets.find_one(
        scoped_query({"id": asset_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not existing:
        raise AssetNotFoundError(asset_id)
    changes = {k: v for k, v in params.items() if k in _MUTABLE_FIELDS and v is not None}
    if "quantity" in changes:
        try:
            changes["quantity"] = int(changes["quantity"])
        except (TypeError, ValueError):
            raise AssetValidationError("quantity must be a whole number")
    if not changes:
        return {"asset": existing, "noop": True}
    await db.assets.update_one(
        scoped_query({"id": asset_id}, branch_id=actor_ctx.branch_id), {"$set": changes}
    )
    await _audit(db, actor_ctx, action="update", asset_id=asset_id,
                 changes={"before": existing, "after": changes})
    updated = await db.assets.find_one(
        scoped_query({"id": asset_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    return {"asset": updated}


async def delete_asset(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Delete an asset (hard delete, matching the panel). params: {asset_id}"""
    asset_id = params.get("asset_id")
    if not asset_id:
        raise AssetValidationError("asset_id is required")
    existing = await db.assets.find_one(
        scoped_query({"id": asset_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not existing:
        raise AssetNotFoundError(asset_id)
    await db.assets.delete_one(scoped_query({"id": asset_id}, branch_id=actor_ctx.branch_id))
    # F.10: actor-tagged deletion audit — who deleted what, when.
    await _audit(db, actor_ctx, action="delete", asset_id=asset_id, changes={"deleted": existing})
    return {"deleted": True, "asset": existing}
