"""Transport domain service — single shared write path (AD7).

Both the REST routes (`POST/PATCH/DELETE /api/transport*`) and the AI tools
(`create_transport_route`, `update_transport_route`, `delete_transport_route`,
`add_transport_vehicle`) call these functions.

**Parity decisions:** the legacy PATCH `$set` the raw body — the service pins a
mutable whitelist; the legacy DELETE removed a route blindly — the service now
blocks deletion while active students are assigned to the zone (same safety rule
the K-epic review mandated for classes/houses/branches) and writes the F.10
deletion audit.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import uuid

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_query


class TransportValidationError(Exception):
    """Invalid input → HTTP 400."""


class TransportNotFoundError(Exception):
    """Unknown route/vehicle id within the caller's scope → HTTP 404."""


class TransportConflictError(Exception):
    """Active students still assigned to the zone → HTTP 409."""


_ROUTE_MUTABLE = {"route_name", "start_point", "end_point", "stops", "driver_name",
                  "driver_phone", "vehicle_no", "capacity", "fare", "is_active",
                  "description", "centroid"}


async def _audit(db, actor_ctx: ActorContext, *, action: str, entity_type: str, entity_id: str, changes: dict) -> None:
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
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


async def create_route(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Create a transport route/zone. params: {route_name|name, start_point?, end_point?,
    stops?, driver_name?, driver_phone?, vehicle_no?, capacity?, fare?, description?}"""
    route_name = params.get("route_name") or params.get("name")
    if not route_name:
        raise TransportValidationError("route_name is required")
    route = {
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "route_name": route_name,
        "start_point": params.get("start_point", ""),
        "end_point": params.get("end_point", ""),
        "stops": params.get("stops", []),
        "driver_name": params.get("driver_name", ""),
        "driver_phone": params.get("driver_phone", ""),
        "vehicle_no": params.get("vehicle_no") or params.get("vehicle_id", ""),
        "capacity": params.get("capacity", ""),
        "fare": params.get("fare", 0),
        "is_active": True,
        "created_at": actor_ctx.now_iso(),
    }
    if params.get("description"):
        route["description"] = params["description"]
    await db.transport_routes.insert_one({**route, "_id": route["id"]})
    await _audit(db, actor_ctx, action="create", entity_type="transport_route",
                 entity_id=route["id"], changes={"created": route})
    return {"route": route}


async def update_route(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Update a transport route. params: {route_id, <any of the mutable fields>}"""
    route_id = params.get("route_id")
    if not route_id:
        raise TransportValidationError("route_id is required")
    bid = actor_ctx.branch_id
    existing = await db.transport_routes.find_one(
        scoped_query({"id": route_id}, branch_id=bid), {"_id": 0}
    )
    if not existing:
        raise TransportNotFoundError(route_id)
    changes = {k: v for k, v in params.items() if k in _ROUTE_MUTABLE and v is not None}
    if not changes:
        return {"route": existing, "noop": True}
    await db.transport_routes.update_one(
        scoped_query({"id": route_id}, branch_id=bid), {"$set": changes}
    )
    await _audit(db, actor_ctx, action="update", entity_type="transport_route",
                 entity_id=route_id, changes={"before": existing, "after": changes})
    updated = await db.transport_routes.find_one(
        scoped_query({"id": route_id}, branch_id=bid), {"_id": 0}
    )
    return {"route": updated}


async def delete_route(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Delete a transport route. Blocked while active students are assigned. params: {route_id}"""
    route_id = params.get("route_id")
    if not route_id:
        raise TransportValidationError("route_id is required")
    bid = actor_ctx.branch_id
    existing = await db.transport_routes.find_one(
        scoped_query({"id": route_id}, branch_id=bid), {"_id": 0}
    )
    if not existing:
        raise TransportNotFoundError(route_id)
    assigned = await db.students.count_documents(
        scoped_query({"route_zone_id": route_id, "is_active": {"$ne": False}}, branch_id=bid)
    )
    if assigned:
        raise TransportConflictError(
            f"{assigned} active student(s) are assigned to this route — reassign them first"
        )
    await db.transport_routes.delete_one(scoped_query({"id": route_id}, branch_id=bid))
    # F.10: actor-tagged deletion audit — who deleted what, when.
    await _audit(db, actor_ctx, action="delete", entity_type="transport_route",
                 entity_id=route_id, changes={"deleted": existing})
    return {"deleted": True, "route": existing}


async def create_vehicle(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Register a vehicle. params: {vehicle_number, vehicle_type?, capacity?, driver_name?, driver_phone?}"""
    if not params.get("vehicle_number"):
        raise TransportValidationError("vehicle_number is required")
    try:
        capacity = int(params.get("capacity", 0))
    except (TypeError, ValueError):
        raise TransportValidationError("capacity must be a whole number")
    vehicle = {
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "vehicle_number": params.get("vehicle_number", ""),
        "vehicle_type": params.get("vehicle_type", "bus"),
        "capacity": capacity,
        "driver_name": params.get("driver_name", ""),
        "driver_phone": params.get("driver_phone", ""),
        "is_active": True,
        "created_at": actor_ctx.now_iso(),
    }
    await db.vehicles.insert_one({**vehicle, "_id": vehicle["id"]})
    await _audit(db, actor_ctx, action="create", entity_type="vehicle",
                 entity_id=vehicle["id"], changes={"created": vehicle})
    return {"vehicle": vehicle}
