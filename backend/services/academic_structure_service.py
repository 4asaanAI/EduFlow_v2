"""Academic-structure domain service — the single shared write path for classes
(incl. their section field) and houses (AI Layer Hardening, AD7 / Epic K, Story K.2).

Classes and houses had **no** write REST routes before this story (classes came
only from `seed.py`/import; houses had a GET-with-auto-seed + a points route).
Per the approved K.2 scope, this service is the single write path and BOTH a new
minimal service-backed REST route (the parity reference) and the matching
Owner/Principal AI tool call it — adding backend capability with **no new UI**.

"Sections" are not a separate collection — a section is the `section` field on a
class record, managed via `create_class`/`update_class`.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
Role/authority gating stays in the route `Depends(...)` and chat `_is_tool_authorized`
(P2). Classes are branch-scoped (owner = cross-branch, principal = own branch);
houses are school-scoped (mirrors the existing GET /activities/houses).
"""

from __future__ import annotations

import uuid
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import add_school_id, scoped_filter, scoped_query


class AcademicStructureValidationError(Exception):
    """Invalid input (missing/invalid field) → HTTP 400."""


class AcademicStructureNotFoundError(Exception):
    """Target class/house does not exist (in scope) → HTTP 404."""


class AcademicStructureConflictError(Exception):
    """Deletion blocked by referential integrity (e.g. class still has students) → HTTP 409."""


CLASS_UPDATABLE_FIELDS = {
    "name", "section", "academic_year_id", "class_teacher_id", "room_number",
}
HOUSE_UPDATABLE_FIELDS = {"name", "colour"}
_IMMUTABLE_KEYS = {"_id", "id", "schoolId", "branch_id"}


def _session_kwargs(session) -> dict:
    return _txn_session_kwargs(session)


async def _audit(
    db,
    actor_ctx: ActorContext,
    *,
    entity_type: str,
    action: str,
    entity_id: str,
    changes: dict,
    session=None,
) -> None:
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
            "reason": "",
            "created_at": actor_ctx.now().isoformat(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )


# ───────────────────────────── Classes ─────────────────────────────────────


async def create_class(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Create a class (a class carries its section as a field).

    params: ``{name, section?, academic_year_id?, class_teacher_id?, room_number?, branch_id?}``
    returns: ``{"class": <doc>}``
    """
    if not params.get("name"):
        raise AcademicStructureValidationError("name is required")
    # A class belongs to a branch. Only an owner (cross-branch authority) may target
    # an arbitrary branch via params; a branch-scoped actor (e.g. principal) is pinned
    # to their own branch so they cannot create a class outside their scope (NFR5).
    if actor_ctx.role == "owner":
        branch_id = params.get("branch_id") or actor_ctx.branch_id or ""
    else:
        branch_id = actor_ctx.branch_id or ""
    doc = {
        "id": str(uuid.uuid4()),
        "name": params["name"],
        "section": params.get("section", ""),
        "academic_year_id": params.get("academic_year_id", ""),
        "branch_id": branch_id,
        "class_teacher_id": params.get("class_teacher_id"),
        "room_number": params.get("room_number", ""),
        "created_by": actor_ctx.user_id,
        "created_at": actor_ctx.now().isoformat(),
    }
    doc = add_school_id(doc, actor_ctx.school_id)
    await db.classes.insert_one({**doc, "_id": doc["id"]}, **_session_kwargs(session))
    await _audit(
        db, actor_ctx, entity_type="class", action="class_create",
        entity_id=doc["id"], changes={"created": doc}, session=session,
    )
    return {"class": doc}


async def update_class(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Update a class's editable fields (incl. its section).

    params: ``{class_id, **fields}``  returns: ``{"class": <updated>, "noop": bool}``
    """
    class_id = params.get("class_id")
    if not class_id:
        raise AcademicStructureValidationError("class_id is required")
    changes = {k: v for k, v in params.items() if k in CLASS_UPDATABLE_FIELDS}
    existing = await db.classes.find_one(
        scoped_query({"id": class_id}, branch_id=actor_ctx.branch_id), {"_id": 0},
        **_session_kwargs(session),
    )
    if not existing:
        raise AcademicStructureNotFoundError("Class not found")
    effective = {k: v for k, v in changes.items() if existing.get(k) != v}
    if not effective:
        return {"class": existing, "noop": True}
    effective["updated_at"] = actor_ctx.now().isoformat()
    await db.classes.update_one(
        scoped_query({"id": class_id}, branch_id=actor_ctx.branch_id),
        {"$set": effective}, **_session_kwargs(session),
    )
    await _audit(
        db, actor_ctx, entity_type="class", action="class_update",
        entity_id=class_id, changes={k: v for k, v in effective.items() if k != "updated_at"},
        session=session,
    )
    updated = await db.classes.find_one(
        scoped_query({"id": class_id}, branch_id=actor_ctx.branch_id), {"_id": 0},
        **_session_kwargs(session),
    )
    return {"class": updated, "noop": False}


async def delete_class(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Delete a class. Destructive (F.10 two-step at the dispatch layer). Blocked
    if any active student is still assigned to it (referential integrity).

    params: ``{class_id}``  returns: ``{"deleted": True, "class_id": <id>}``
    """
    class_id = params.get("class_id")
    if not class_id:
        raise AcademicStructureValidationError("class_id is required")
    existing = await db.classes.find_one(
        scoped_query({"id": class_id}, branch_id=actor_ctx.branch_id), {"_id": 0},
        **_session_kwargs(session),
    )
    if not existing:
        raise AcademicStructureNotFoundError("Class not found")
    student_count = await db.students.count_documents(
        scoped_filter({"class_id": class_id, "is_active": True}, actor_ctx.school_id),
        **_session_kwargs(session),
    )
    if student_count:
        raise AcademicStructureConflictError(
            f"Cannot delete a class with {student_count} active student(s) assigned"
        )
    await db.classes.delete_one(
        scoped_query({"id": class_id}, branch_id=actor_ctx.branch_id),
        **_session_kwargs(session),
    )
    await _audit(
        db, actor_ctx, entity_type="class", action="class_delete",
        entity_id=class_id, changes={"deleted": existing}, session=session,
    )
    return {"deleted": True, "class_id": class_id}


# ────────────────────────────── Houses ─────────────────────────────────────


async def create_house(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Create a house. params: ``{name, colour?}``  returns: ``{"house": <doc>}``"""
    if not params.get("name"):
        raise AcademicStructureValidationError("name is required")
    doc = {
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "name": params["name"],
        "colour": params.get("colour", params["name"]),
        "points": 0,
        "created_at": actor_ctx.now().isoformat(),
    }
    await db.houses.insert_one({**doc, "_id": doc["id"]}, **_session_kwargs(session))
    await _audit(
        db, actor_ctx, entity_type="house", action="house_create",
        entity_id=doc["id"], changes={"created": doc}, session=session,
    )
    return {"house": doc}


async def update_house(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Update a house's name/colour. NOT a points change (that stays the
    audited `award_house_points` path). returns ``{"house": <updated>, "noop": bool}``"""
    house_id = params.get("house_id")
    if not house_id:
        raise AcademicStructureValidationError("house_id is required")
    changes = {k: v for k, v in params.items() if k in HOUSE_UPDATABLE_FIELDS}
    existing = await db.houses.find_one(
        scoped_filter({"id": house_id}, actor_ctx.school_id), {"_id": 0},
        **_session_kwargs(session),
    )
    if not existing:
        raise AcademicStructureNotFoundError("House not found")
    effective = {k: v for k, v in changes.items() if existing.get(k) != v}
    if not effective:
        return {"house": existing, "noop": True}
    effective["updated_at"] = actor_ctx.now().isoformat()
    await db.houses.update_one(
        scoped_filter({"id": house_id}, actor_ctx.school_id),
        {"$set": effective}, **_session_kwargs(session),
    )
    await _audit(
        db, actor_ctx, entity_type="house", action="house_update",
        entity_id=house_id, changes={k: v for k, v in effective.items() if k != "updated_at"},
        session=session,
    )
    updated = await db.houses.find_one(
        scoped_filter({"id": house_id}, actor_ctx.school_id), {"_id": 0},
        **_session_kwargs(session),
    )
    return {"house": updated, "noop": False}


async def delete_house(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Delete a house. Destructive (F.10). Blocked if any active student is still
    assigned to it by name. params: ``{house_id}``  returns ``{"deleted": True, ...}``"""
    house_id = params.get("house_id")
    if not house_id:
        raise AcademicStructureValidationError("house_id is required")
    existing = await db.houses.find_one(
        scoped_filter({"id": house_id}, actor_ctx.school_id), {"_id": 0},
        **_session_kwargs(session),
    )
    if not existing:
        raise AcademicStructureNotFoundError("House not found")
    student_count = await db.students.count_documents(
        scoped_filter({"house": existing.get("name"), "is_active": True}, actor_ctx.school_id),
        **_session_kwargs(session),
    )
    if student_count:
        raise AcademicStructureConflictError(
            f"Cannot delete a house with {student_count} active student(s) assigned"
        )
    await db.houses.delete_one(
        scoped_filter({"id": house_id}, actor_ctx.school_id),
        **_session_kwargs(session),
    )
    await _audit(
        db, actor_ctx, entity_type="house", action="house_delete",
        entity_id=house_id, changes={"deleted": existing}, session=session,
    )
    return {"deleted": True, "house_id": house_id}
