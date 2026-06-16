"""Org-configuration domain service — the single shared write path for branches,
school settings, and the year-end transition (AI Layer Hardening, AD7 / Epic K,
Story K.3).

Both the REST routes (`POST/PUT /api/settings/branches`, `DELETE
/api/settings/branches/{id}`, `PATCH /api/settings/school`,
`POST /api/settings/year-end-transition`) and the matching **owner-authority** AI
tools call these functions, so an AI org-config change is byte-identical to the
panel. These are owner-only (org-level config stays owner-only even in Phase 2,
AD15) — gated in the route `Depends(require_owner)` and the registry `roles=["owner"]`.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import uuid
from datetime import timezone

from pymongo.errors import DuplicateKeyError

from services.actor_context import ActorContext
from services.audit_service import write_audit
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import get_school_id, scoped_filter


class OrgConfigValidationError(Exception):
    """Invalid input (missing required field) → HTTP 400."""


class OrgConfigNotFoundError(Exception):
    """Target branch does not exist (in scope) → HTTP 404."""


class OrgConfigConflictError(Exception):
    """Duplicate branch code, or deletion blocked by referential integrity → 409."""


SCHOOL_SETTINGS_FIELDS = {
    "attendance_threshold", "school_name", "board", "city", "ai_context",
    # Part 1-A school identity & profile (owner-managed, all roles read)
    "state", "address", "established", "principal", "phone", "email", "website", "logo_url",
}


def _session_kwargs(session) -> dict:
    return _txn_session_kwargs(session)


# ───────────────────────────── Branches ────────────────────────────────────


async def create_branch(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Create a school branch. params: ``{name, branch_code?, location?}``"""
    if not params.get("name"):
        raise OrgConfigValidationError("name is required")
    branch = {
        "id": str(uuid.uuid4()),
        "name": params.get("name", ""),
        "branch_code": params.get("branch_code", ""),
        "location": params.get("location", ""),
        "created_by": actor_ctx.user_id,
        "created_at": actor_ctx.now_utc().isoformat(),
        "schoolId": actor_ctx.school_id,
    }
    try:
        await db.branches.insert_one({**branch, "_id": branch["id"]}, **_session_kwargs(session))
    except DuplicateKeyError:
        raise OrgConfigConflictError("Branch code already exists for this school")
    await write_audit(
        db,
        action="branch_create",
        entity_id=branch["id"],
        collection="branches",
        changed_by=actor_ctx.user_id,
        changed_by_role=actor_ctx.role or "",
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id or "",
        changes={"name": branch["name"], "branch_code": branch["branch_code"]},
    )
    return {"branch": branch}


async def upsert_branch(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Create-or-update a branch by id. params: ``{branch_id, name, address?, phone?, is_active?}``"""
    branch_id = params.get("branch_id")
    if not branch_id:
        raise OrgConfigValidationError("branch_id is required")
    if not params.get("name"):
        raise OrgConfigValidationError("name is required")
    doc = {
        "id": branch_id,
        "schoolId": actor_ctx.school_id,
        "name": params["name"],
        "address": params.get("address", ""),
        "phone": params.get("phone", ""),
        "is_active": params.get("is_active", True),
        "updated_by": actor_ctx.user_id,
        "updated_at": actor_ctx.now().isoformat(),
    }
    await db.branches.update_one(
        scoped_filter({"id": branch_id}, actor_ctx.school_id),
        {"$set": doc, "$setOnInsert": {"_id": branch_id}},
        upsert=True, **_session_kwargs(session),
    )
    await write_audit(
        db,
        action="branch_upsert",
        entity_id=branch_id,
        collection="branches",
        changed_by=actor_ctx.user_id,
        changed_by_role=actor_ctx.role or "",
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id or "",
        changes=doc,
    )
    return {"branch": doc}


async def delete_branch(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Delete a branch. Destructive (F.10). Blocked if any active student is still
    assigned to it. params: ``{branch_id}``"""
    branch_id = params.get("branch_id")
    if not branch_id:
        raise OrgConfigValidationError("branch_id is required")
    existing = await db.branches.find_one(
        scoped_filter({"id": branch_id}, actor_ctx.school_id), {"_id": 0},
        **_session_kwargs(session),
    )
    if not existing:
        raise OrgConfigNotFoundError("Branch not found")
    student_count = await db.students.count_documents(
        scoped_filter({"branch_id": branch_id, "is_active": True}, actor_ctx.school_id),
        **_session_kwargs(session),
    )
    if student_count:
        raise OrgConfigConflictError(
            f"Cannot delete a branch with {student_count} active student(s) assigned"
        )
    await db.branches.delete_one(
        scoped_filter({"id": branch_id}, actor_ctx.school_id), **_session_kwargs(session),
    )
    await write_audit(
        db,
        action="branch_delete",
        entity_id=branch_id,
        collection="branches",
        changed_by=actor_ctx.user_id,
        changed_by_role=actor_ctx.role or "",
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id or "",
        changes={"deleted": existing},
    )
    return {"deleted": True, "branch_id": branch_id}


# ─────────────────────────── School settings ───────────────────────────────


async def update_school_settings(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Update school-level settings (whitelisted fields only)."""
    update = {k: v for k, v in params.items() if k in SCHOOL_SETTINGS_FIELDS}
    await db.school_settings.update_one(
        scoped_filter({"id": "main"}, actor_ctx.school_id),
        {"$set": {**update, "schoolId": actor_ctx.school_id, "updated_at": actor_ctx.now().isoformat()}},
        upsert=True, **_session_kwargs(session),
    )
    await write_audit(
        db,
        action="school_settings_update",
        entity_id="main",
        collection="school_settings",
        changed_by=actor_ctx.user_id,
        changed_by_role=actor_ctx.role or "",
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id or "",
        changes=update,
    )
    return {"updated": update}


# ──────────────────────── Year-end transition ──────────────────────────────


async def year_end_transition(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Transition to a new academic year: create the new year (current), mark all
    prior years not-current, and report students carried forward. High-impact —
    routed through F.10's two-step confirm at the dispatch layer."""
    new_year_name = params.get("new_year_name")
    if not new_year_name:
        raise OrgConfigValidationError("new_year_name required")
    new_ay = {
        "id": str(uuid.uuid4()),
        "name": new_year_name,
        "start_date": params.get("start_date", f"{new_year_name[:4]}-04-01"),
        "end_date": params.get("end_date", f"{new_year_name[5:]}-03-31"),
        "is_current": True,
    }
    await db.academic_years.update_many(
        {"is_current": True}, {"$set": {"is_current": False}}, **_session_kwargs(session),
    )
    await db.academic_years.insert_one({**new_ay, "_id": new_ay["id"]}, **_session_kwargs(session))
    await write_audit(
        db,
        action="academic_year_transition",
        entity_id=new_ay["id"],
        collection="academic_years",
        changed_by=actor_ctx.user_id,
        changed_by_role=actor_ctx.role or "",
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id or "",
        changes={"new_year": new_ay},
    )
    student_count = await db.students.count_documents({"is_active": True}, **_session_kwargs(session))
    return {
        "new_year": new_ay,
        "students_carried_forward": student_count,
        "message": (
            f"Transitioned to {new_year_name}. {student_count} students carried forward. "
            "Previous year archived."
        ),
    }
