"""Transport domain service - single shared write path (AD7).

Both the REST routes (`POST/PATCH/DELETE /api/transport*`) and the AI tools
(`create_transport_route`, `update_transport_route`, `delete_transport_route`,
`add_transport_vehicle`) call these functions.

**Parity decisions:** the legacy PATCH `$set` the raw body - the service pins a
mutable whitelist; the legacy DELETE removed a route blindly - the service now
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


class TransportApprovalRequired(Exception):
    """The transport head asked to delete something. Aman or Adesh has to agree → 202.

    NOT an error, and it must never be presented as one. The request has been recorded
    and is waiting for a decision; the caller is told what happens next and who it went
    to. Carries the approval id so the screen and Flo can both point at it.
    """

    def __init__(self, approval_id: str, message: str):
        super().__init__(message)
        self.approval_id = approval_id
        self.message = message


def _needs_approval_to_delete(actor_ctx: ActorContext) -> bool:
    """R3-2, 2026-08-15. Abhimanyu: the transport head deletes with Aman OR Adesh's
    agreement, either one of them.

    He is the only profile in this position, and deliberately so. Everyone else who can
    reach these functions - the owner, the principal, the accountant head - either grants
    the approval or has held the ability outright since before this release, so putting
    them behind a gate would be taking something away that nobody asked to take.
    """
    return actor_ctx.role == "admin" and actor_ctx.sub_category == "transport_head"


async def _ask_for_agreement(db, actor_ctx: ActorContext, *, title: str, description: str,
                             impact: str, pending_action: dict) -> "TransportApprovalRequired":
    """Record the request and hand back the exception the caller raises.

    Routed `owner_and_principal` so EITHER Aman or Adesh can decide it. Both are
    notified. This is the same queue and the same screen the school already uses, not a
    second approval system, which is what answer 9 of 2026-08-11 asked for about repairs
    and applies just as well here.
    """
    from services.approvals_service import create_approval_request_doc

    approval_id = await create_approval_request_doc(
        db, actor_ctx,
        title=title,
        description=description,
        estimated_impact=impact,
        note="Requested by the transport head. Nothing has been deleted yet.",
        routing="owner_and_principal",
        pending_action=pending_action,
    )
    return TransportApprovalRequired(
        approval_id,
        f"{title}. This needs the school's owner or the principal to agree, so it has "
        f"been sent to both of them and nothing has been deleted yet.",
    )


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


async def delete_route(db, actor_ctx: ActorContext, params: dict, *, session=None,
                       _approved: bool = False) -> dict:
    """Delete a transport route. Blocked while active students are assigned. params: {route_id}

    R3-2, 2026-08-15: for the transport head this RECORDS A REQUEST instead of deleting,
    and Aman or Adesh carries it out by approving. `_approved` is set only by the approval
    service when one of them has said yes; nothing outside this file passes it.
    """
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
            f"{assigned} active student(s) are assigned to this route - reassign them first"
        )
    # Checked AFTER the "children are still on it" rule on purpose. Sending Aman a
    # request that would have been refused anyway wastes his time and teaches the
    # transport head nothing about why it cannot happen.
    if _needs_approval_to_delete(actor_ctx) and not _approved:
        raise await _ask_for_agreement(
            db, actor_ctx,
            title=f"Delete the bus route '{existing.get('route_name', route_id)}'",
            description=(
                f"The transport head has asked to delete the route "
                f"'{existing.get('route_name', route_id)}'. No child is assigned to it."
            ),
            impact="The route disappears from the transport screens. No child is affected.",
            pending_action={"kind": "delete_transport_route", "route_id": route_id},
        )
    await db.transport_routes.delete_one(scoped_query({"id": route_id}, branch_id=bid))
    # F.10: actor-tagged deletion audit - who deleted what, when.
    await _audit(db, actor_ctx, action="delete", entity_type="transport_route",
                 entity_id=route_id, changes={"deleted": existing})
    return {"deleted": True, "route": existing}


async def delete_vehicle(db, actor_ctx: ActorContext, params: dict, *, session=None,
                         _approved: bool = False) -> dict:
    """Take a vehicle off the register. params: {vehicle_id}

    R3-2, 2026-08-15. There was no way to remove a vehicle at all before this: a bus sold
    or scrapped stayed on the register for ever, and the transport head was being given
    the job of keeping that register right.

    Refused while the vehicle is still on a route, the same rule that protects a route
    with children on it, and for the same reason: a record that vanishes while something
    still points at it leaves the thing pointing at nothing, which reads as data loss.

    For the transport head this records a request rather than deleting. `_approved` is set
    only by the approval service once Aman or Adesh has agreed.
    """
    vehicle_id = params.get("vehicle_id")
    if not vehicle_id:
        raise TransportValidationError("vehicle_id is required")
    bid = actor_ctx.branch_id
    existing = await db.vehicles.find_one(
        scoped_query({"id": vehicle_id}, branch_id=bid), {"_id": 0}
    )
    if not existing:
        raise TransportNotFoundError(vehicle_id)
    number = existing.get("vehicle_number", "")
    if number:
        in_use = await db.transport_routes.count_documents(
            scoped_query({"vehicle_no": number, "is_active": {"$ne": False}}, branch_id=bid)
        )
        if in_use:
            raise TransportConflictError(
                f"Vehicle {number} is still running on {in_use} route(s) - take it off "
                "those routes first"
            )
    if _needs_approval_to_delete(actor_ctx) and not _approved:
        raise await _ask_for_agreement(
            db, actor_ctx,
            title=f"Take vehicle {number or vehicle_id} off the register",
            description=(
                f"The transport head has asked to remove vehicle {number or vehicle_id}. "
                "It is not running on any route."
            ),
            impact="The vehicle disappears from the transport screens. No route is affected.",
            pending_action={"kind": "delete_transport_vehicle", "vehicle_id": vehicle_id},
        )
    await db.vehicles.delete_one(scoped_query({"id": vehicle_id}, branch_id=bid))
    await _audit(db, actor_ctx, action="delete", entity_type="vehicle",
                 entity_id=vehicle_id, changes={"deleted": existing})
    return {"deleted": True, "vehicle": existing}


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
