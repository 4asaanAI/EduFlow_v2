from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException, Depends
from database import get_db
from middleware.auth import get_current_user, require_role, require_owner, require_owner_or_principal
from tenant import get_school_id, scoped_filter
from services.audit_service import write_audit
from services.actor_context import actor_ctx_from_user
from services.academic_structure_service import (
    create_class as svc_create_class,
    update_class as svc_update_class,
    delete_class as svc_delete_class,
    AcademicStructureValidationError,
    AcademicStructureNotFoundError,
    AcademicStructureConflictError,
)
from services.org_config_service import (
    create_branch as svc_create_branch,
    upsert_branch as svc_upsert_branch,
    delete_branch as svc_delete_branch,
    update_school_settings as svc_update_school_settings,
    year_end_transition as svc_year_end_transition,
    OrgConfigValidationError,
    OrgConfigNotFoundError,
    OrgConfigConflictError,
)
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/settings", tags=["settings"])


def get_user(req: Request):
    return get_current_user(req)


def _is_it_tech(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "it_tech"


def _can_manage_platform(user: dict) -> bool:
    return user.get("role") == "owner" or _is_it_tech(user)


def _settings_query(extra: dict | None = None) -> dict:
    return scoped_filter(extra or {}, get_school_id())


# --- Token Usage Tracking ---
@router.post("/token-usage")
async def track_token_usage(request: Request):
    """Track LLM token usage per user per month."""
    db = get_db()
    user = get_user(request)
    body = await request.json()
    tokens = int(body.get("tokens", 0))
    month = datetime.now().strftime("%Y-%m")
    await db.token_usage.update_one(
        _settings_query({"user_id": user["id"], "month": month}),
        {"$inc": {"tokens": tokens, "sessions": 1}, "$set": {"schoolId": get_school_id(), "user_id": user["id"], "month": month}},
        upsert=True
    )
    await write_audit(
        db,
        action="token_usage_track",
        entity_id=user["id"],
        collection="token_usage",
        changed_by=user["id"],
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes={"tokens": tokens, "month": month},
    )
    return {"success": True}


@router.get("/token-usage")
async def get_token_usage(request: Request):
    """Get current user's token usage for current month."""
    db = get_db()
    user = get_user(request)
    month = datetime.now().strftime("%Y-%m")
    usage = await db.token_usage.find_one(_settings_query({"user_id": user["id"], "month": month}), {"_id": 0})
    if not usage:
        return {"success": True, "data": {"tokens": 0, "sessions": 0, "month": month, "limit": 50000}}
    usage["limit"] = 50000
    return {"success": True, "data": usage}


@router.get("/token-usage/admin")
async def get_token_usage_admin(request: Request, user: dict = Depends(require_owner)):
    """Admin view of token usage with per-user custom limits and 80% threshold detection."""
    db = get_db()
    DEFAULT_LIMIT = 50000

    usage_records = await db.token_usage.find(_settings_query()).to_list(None)
    custom_limits = await db.token_limits.find(_settings_query()).to_list(None)
    limit_map = {rec.get("user_id"): rec.get("limit", DEFAULT_LIMIT) for rec in custom_limits}

    users_over_80: list[dict] = []
    for rec in usage_records:
        uid = rec.get("user_id")
        tokens_used = int(rec.get("tokens", rec.get("tokens_used", 0)) or 0)
        effective_limit = int(limit_map.get(uid, DEFAULT_LIMIT))
        pct = (tokens_used / effective_limit * 100) if effective_limit > 0 else 0
        if pct >= 80:
            users_over_80.append({
                "user_id": uid,
                "tokens_used": tokens_used,
                "effective_limit": effective_limit,
                "percent_used": round(pct, 1),
            })

    return {
        "success": True,
        "data": usage_records,
        "meta": {
            "count": len(usage_records),
            "users_over_80_pct": users_over_80,
            "default_limit": DEFAULT_LIMIT,
        },
    }


@router.get("/token-usage/aggregate")
async def get_token_usage_aggregate(request: Request, month: str = None, user: dict = Depends(require_role("owner", "admin"))):
    if not _can_manage_platform(user):
        raise HTTPException(403, "Forbidden")
    db = get_db()
    target_month = month or datetime.now().strftime("%Y-%m")
    rows = await db.token_usage.find(_settings_query({"month": target_month}), {"_id": 0}).to_list(5000)
    total_tokens = sum(int(row.get("tokens", 0) or 0) for row in rows)
    total_sessions = sum(int(row.get("sessions", 0) or 0) for row in rows)
    return {"success": True, "data": {"month": target_month, "users": len(rows), "tokens": total_tokens, "sessions": total_sessions, "rows": rows}}


@router.put("/token-limits/{user_id}")
async def set_token_limit(user_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    if not _can_manage_platform(user):
        raise HTTPException(403, "Forbidden")
    db = get_db()
    body = await request.json()
    limit = int(body.get("limit", 0))
    if limit <= 0:
        raise HTTPException(400, "limit must be positive")
    doc = {"user_id": user_id, "limit": limit, "updated_by": user["id"], "updated_at": datetime.now().isoformat()}
    await db.token_limits.update_one(_settings_query({"user_id": user_id}), {"$set": doc, "$setOnInsert": {"_id": str(uuid.uuid4()), "schoolId": get_school_id()}}, upsert=True)
    return {"success": True, "data": doc}


# --- Year-end Session Transition ---
@router.post("/year-end-transition")
async def year_end_transition(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    """Transition to new academic year: create new year, promote students, archive old data.

    Thin adapter over services.org_config_service.year_end_transition (Story K.3 / AD7)."""
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        data = await svc_year_end_transition(db, actor_ctx, body)
    except OrgConfigValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": data}


@router.patch("/school")
async def update_school_settings(request: Request, user: dict = Depends(require_owner)):
    """Thin adapter over services.org_config_service.update_school_settings (Story K.3 / AD7)."""
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    await svc_update_school_settings(db, actor_ctx, body)
    return {"success": True}


@router.get("/branches")
async def list_branches(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    branches = await db.branches.find(_settings_query(), {"_id": 0}).sort("name", 1).to_list(100)
    return {"success": True, "data": branches, "meta": {"count": len(branches)}}


@router.post("/branches")
async def create_branch(request: Request, user: dict = Depends(require_owner)):
    """Owner-only: create a new school branch. Unique branch_code enforced by DB index.

    Thin adapter over services.org_config_service.create_branch (Story K.3 / AD7)."""
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_create_branch(db, actor_ctx, body)
    except OrgConfigValidationError as e:
        raise HTTPException(400, str(e))
    except OrgConfigConflictError as e:
        raise HTTPException(409, str(e))
    return {"success": True, "data": result["branch"]}


@router.put("/branches/{branch_id}")
async def upsert_branch(branch_id: str, request: Request, user: dict = Depends(require_owner)):
    """Thin adapter over services.org_config_service.upsert_branch (Story K.3 / AD7)."""
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_upsert_branch(db, actor_ctx, {**body, "branch_id": branch_id})
    except OrgConfigValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["branch"]}


@router.delete("/branches/{branch_id}")
async def delete_branch(branch_id: str, request: Request, user: dict = Depends(require_owner)):
    """Owner-only: delete a branch. Parity reference for the AI `delete_branch`
    tool (destructive — F.10 two-step at the chat layer)."""
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_delete_branch(db, actor_ctx, {"branch_id": branch_id})
    except OrgConfigNotFoundError as e:
        raise HTTPException(404, str(e))
    except OrgConfigConflictError as e:
        raise HTTPException(409, str(e))
    return {"success": True, "data": result}


@router.get("/me")
async def get_settings(request: Request):
    db = get_db()
    user = get_user(request)
    user_rec = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not user_rec:
        return {"success": True, "data": {"preferred_language": "en", "theme": "dark"}}
    return {"success": True, "data": {"preferred_language": user_rec.get("preferred_language", "en"), "theme": "dark"}}


@router.patch("/me")
async def update_settings(request: Request):
    db = get_db()
    user = get_user(request)
    body = await request.json()
    allowed = {"preferred_language", "theme", "notifications", "attendance_threshold"}
    update = {k: v for k, v in body.items() if k in allowed}
    await db.users.update_one({"id": user["id"]}, {"$set": update}, upsert=True)
    # Also persist notification settings to user_settings collection
    if "notifications" in update:
        from datetime import datetime as dt
        await db.user_settings.update_one(
            {"user_id": user["id"]},
            {"$set": {"notifications": update["notifications"], "updated_at": dt.now().isoformat()}},
            upsert=True
        )
    await write_audit(
        db,
        action="user_settings_update",
        entity_id=user["id"],
        collection="users",
        changed_by=user["id"],
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes=update,
    )
    return {"success": True}


@router.get("/school")
async def get_school_settings(request: Request, user: dict = Depends(require_role("admin", "owner", "teacher", "staff"))):
    db = get_db()
    settings = await db.school_settings.find_one(_settings_query({"id": "main"}), {"_id": 0})
    if not settings:
        import os
        settings = {
            "school_name": os.environ.get("SCHOOL_NAME", "The Aaryans"),
            "board": os.environ.get("SCHOOL_BOARD", "CBSE"),
            "city": os.environ.get("SCHOOL_CITY", "Lucknow"),
            "state": os.environ.get("SCHOOL_STATE", "Uttar Pradesh"),
        }
    return {"success": True, "data": settings}


@router.get("/classes")
async def get_classes(request: Request, user: dict = Depends(require_role("admin", "owner", "teacher", "staff"))):
    db = get_db()
    classes = await db.classes.find(_settings_query(), {"_id": 0}).to_list(50)
    return {"success": True, "data": classes}


# ── Class CRUD (Story K.2) — service-backed parity reference for the AI tools ──
# No new UI: these wrap the academic_structure_service single write path.
@router.post("/classes")
async def create_class(request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_create_class(db, actor_ctx, body)
    except AcademicStructureValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["class"]}


@router.patch("/classes/{class_id}")
async def update_class(class_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_update_class(db, actor_ctx, {**body, "class_id": class_id})
    except AcademicStructureNotFoundError as e:
        raise HTTPException(404, str(e))
    except AcademicStructureValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["class"]}


@router.delete("/classes/{class_id}")
async def delete_class(class_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_delete_class(db, actor_ctx, {"class_id": class_id})
    except AcademicStructureNotFoundError as e:
        raise HTTPException(404, str(e))
    except AcademicStructureConflictError as e:
        raise HTTPException(409, str(e))
    return {"success": True, "data": result}


@router.get("/forms")
async def list_forms(request: Request, user: dict = Depends(require_role("admin", "owner", "teacher", "staff"))):
    db = get_db()
    forms = await db.custom_forms.find(_settings_query(), {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"success": True, "data": forms}


@router.post("/forms")
async def create_form(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    try:
        db = get_db()
        body = await request.json()
        if not body.get("title"):
            raise HTTPException(400, "Title is required")
        if not body.get("fields") or len(body.get("fields", [])) == 0:
            raise HTTPException(400, "At least one field is required")

        form = {
            "id": str(uuid.uuid4()),
            "schoolId": get_school_id(),
            "title": body.get("title"),
            "fields": body.get("fields", []),
            "audience": body.get("audience", "all"),
            "public_slug": body.get("public_slug") or str(uuid.uuid4())[:8],
            "expires_at": body.get("expires_at"),
            "created_by": user["id"],
            "is_active": True,
            "created_at": datetime.now().isoformat(),
        }
        result = await db.custom_forms.insert_one({**form, "_id": form["id"]})
        await write_audit(
            db,
            action="custom_form_create",
            entity_id=form["id"],
            collection="custom_forms",
            changed_by=user["id"],
            changed_by_role=user.get("role", ""),
            school_id=get_school_id(),
            branch_id=user.get("branch_id", ""),
            changes={"title": form["title"], "audience": form["audience"]},
        )
        return {"success": True, "data": form}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error creating form: {str(e)}")


@router.get("/forms/{form_id}")
async def get_form(form_id: str, request: Request, user: dict = Depends(require_role("admin", "owner", "teacher", "staff"))):
    db = get_db()
    form = await db.custom_forms.find_one(_settings_query({"id": form_id}), {"_id": 0})
    if not form:
        raise HTTPException(404, "Form not found")
    return {"success": True, "data": form}


@router.post("/forms/{form_id}/responses")
async def submit_form_response(form_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    body = await request.json()
    response = {
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "form_id": form_id,
        "submitted_by": user["id"],
        "submitted_by_name": user.get("name", "Anonymous"),
        "submitted_by_role": user["role"],
        "answers": body.get("answers", {}),
        "submitted_at": datetime.now().isoformat(),
    }
    await db.form_responses.insert_one({**response, "_id": response["id"]})
    await write_audit(
        db,
        action="form_response_submit",
        entity_id=response["id"],
        collection="form_responses",
        changed_by=user["id"],
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes={"form_id": form_id},
    )
    return {"success": True, "data": response}


@router.get("/forms/{form_id}/responses")
async def get_form_responses(form_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    responses = await db.form_responses.find(_settings_query({"form_id": form_id}), {"_id": 0}).sort("submitted_at", -1).to_list(500)
    return {"success": True, "data": responses}


@router.delete("/forms/{form_id}")
async def delete_form(form_id: str, request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    await db.custom_forms.delete_one(_settings_query({"id": form_id}))
    await db.form_responses.delete_many(_settings_query({"form_id": form_id}))
    await write_audit(
        db,
        action="custom_form_delete",
        entity_id=form_id,
        collection="custom_forms",
        changed_by=user["id"],
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes={"deleted": True},
    )
    return {"success": True}


async def get_academic_year(request: Request):
    db = get_db()
    ay = await db.academic_years.find_one(_settings_query({"is_current": True}), {"_id": 0})
    return {"success": True, "data": ay}
