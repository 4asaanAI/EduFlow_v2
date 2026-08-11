from __future__ import annotations
"""Audit Log UI - Story 33"""
import re
from fastapi import APIRouter, Request, HTTPException, Depends
from database import TimedQuery, get_db
from middleware.auth import get_current_user, require_role
from tenant import get_school_id, scoped_filter

router = APIRouter(prefix="/api/audit-log", tags=["audit"])

#: Admin sub-categories allowed to read the audit log.
#:
#: Owner request 10, 2026-08-06: the log is a record of who changed what in the
#: school's data, and Aman asked that only the owner and the principal be able to
#: read it. `it_tech` and `management` used to be here and were removed then; the
#: menu side of the same rule lives in `frontend/src/lib/helpMenu.js`.
#:
AUDIT_READER_SUB_CATEGORIES = ("principal",)


def get_user(req: Request):
    return get_current_user(req)


@router.get("")
async def list_audit_log(
    request: Request,
    collection: str = None,
    changed_by: str = None,
    date_from: str = None,
    date_to: str = None,
    q: str = None,
    branch_id: str = None,
    page: int = 1,
    limit: int = 50,
):
    db = get_db()
    user = get_user(request)
    # Owner or the explicitly identified principal profile only.
    if user.get("role") == "admin":
        if user.get("sub_category", "") not in AUDIT_READER_SUB_CATEGORIES:
            raise HTTPException(403, "Forbidden")
    elif user.get("role") != "owner":
        raise HTTPException(403, "Forbidden")

    query = {}
    if page < 1:
        raise HTTPException(400, "page must be >= 1")
    if not 1 <= limit <= 100:
        raise HTTPException(400, "limit must be between 1 and 100")

    if collection:
        query["collection"] = collection

    if changed_by:
        query["changed_by"] = changed_by
    is_principal = user.get("role") == "admin" and user.get("sub_category") == "principal"
    if is_principal and branch_id and branch_id != user.get("branch_id"):
        raise HTTPException(403, "Forbidden")
    if branch_id:
        query["branch_id"] = branch_id
    elif is_principal and user.get("branch_id"):
        query["branch_id"] = user.get("branch_id")
    if date_from or date_to:
        date_query = {}
        if date_from:
            date_query["$gte"] = date_from
        if date_to:
            date_query["$lte"] = date_to + "T23:59:59"
        query["created_at"] = date_query
    if q:
        safe_q = re.escape(q)
        query["$or"] = [
            {"changed_by": {"$regex": safe_q, "$options": "i"}},
            {"entity_id": {"$regex": safe_q, "$options": "i"}},
            {"action": {"$regex": safe_q, "$options": "i"}},
        ]

    skip = (page - 1) * limit
    scoped = scoped_filter(query, get_school_id())  # branch-scope: intentional - the audit trail is a school-wide record; role-based narrowing is applied to `query` above, not here
    async with TimedQuery(collection_name="audit_logs", operation="count_documents", query_shape="audit_log_list"):
        total = await db.audit_logs.count_documents(scoped)
    async with TimedQuery(collection_name="audit_logs", operation="find", query_shape="audit_log_list"):
        items = await db.audit_logs.find(scoped, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}


@router.get("/daily-digest")
async def daily_digest(
    request: Request,
    hours: int = 24,
    user: dict = Depends(require_role("owner", "admin")),
):
    """R2-15 - the day in one page, for the two people who run the school.

    Gated the same way the action log is: the school's owner and the principal only
    (Aman's request 10 of 2026-08-06, reconfirmed 2026-08-10). This summarises exactly
    the rows they can already read one at a time, so anybody else reaching it would be
    reading the action log through a different door.
    """
    from services.actor_context import actor_ctx_from_user
    from services.daily_digest_service import build_daily_digest, render_digest_text

    if user.get("role") != "owner" and user.get("sub_category") not in AUDIT_READER_SUB_CATEGORIES:
        raise HTTPException(403, "Forbidden")
    hours = max(1, min(int(hours or 24), 168))

    db = get_db()
    digest = await build_daily_digest(db, actor_ctx_from_user(user), hours=hours)
    return {"success": True, "data": {**digest, "text": render_digest_text(digest)}}


@router.get("/school-summary")
async def school_summary(
    request: Request,
    day: str = None,
    user: dict = Depends(require_role("owner", "admin")),
):
    """The whole school on one page (Abhimanyu, 2026-08-12).

    Gated exactly like the action log and the daily digest, and for the same reason: it
    carries money, the roll and what everyone changed. The accountant head and the admin
    office each already have the half that is theirs; this is the whole, and it belongs
    to the two people who run the school.
    """
    from services.actor_context import actor_ctx_from_user
    from services.school_summary_service import summary_for_day

    if user.get("role") != "owner" and user.get("sub_category") not in AUDIT_READER_SUB_CATEGORIES:
        raise HTTPException(403, "Forbidden")

    db = get_db()
    return {"success": True,
            "data": await summary_for_day(db, actor_ctx_from_user(user), day=day)}


@router.get("/school-summary/history")
async def school_summary_history(
    request: Request,
    limit: int = 30,
    user: dict = Depends(require_role("owner", "admin")),
):
    """Every day's summary that has been kept, newest first."""
    from services.actor_context import actor_ctx_from_user
    from services.school_summary_service import list_summaries

    if user.get("role") != "owner" and user.get("sub_category") not in AUDIT_READER_SUB_CATEGORIES:
        raise HTTPException(403, "Forbidden")

    db = get_db()
    rows = await list_summaries(db, actor_ctx_from_user(user), limit=limit)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


# ── R2-18 - same-day undo of your own change ─────────────────────────────────
#
# Deliberately in this file and NOT behind `AUDIT_READER_SUB_CATEGORIES`. The action log
# itself stays with the owner and the principal (Aman's request 10 of 2026-08-06,
# reconfirmed 2026-08-10), and these two routes do not open it: they show a person only
# their OWN changes from today and let them put one back. Seeing what you did yourself is
# not the same as reading the school's action log, and conflating the two would either
# hand Lalit the log or leave him with no way to correct a typo he is not allowed to
# delete his way out of.

@router.get("/my-changes-today")
async def my_changes_today(request: Request, user: dict = Depends(get_current_user)):
    """Today's changes made by the person asking, each marked reversible or not."""
    from services.actor_context import actor_ctx_from_user
    from services.undo_service import list_my_undoable_changes

    db = get_db()
    result = await list_my_undoable_changes(db, actor_ctx_from_user(user))
    return {"success": True, "data": result["changes"], "meta": {"count": result["count"]}}


@router.post("/my-changes-today/{audit_id}/undo")
async def undo_my_change(audit_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Put back one of your own changes from today. Refuses with a reason, never silently."""
    from services.actor_context import actor_ctx_from_user
    from services.undo_service import (
        UndoNotFoundError,
        UndoRefusedError,
        undo_change,
    )

    db = get_db()
    try:
        result = await undo_change(db, actor_ctx_from_user(user), {"audit_id": audit_id})
    except UndoNotFoundError:
        raise HTTPException(404, "That change could not be found")
    except UndoRefusedError as e:
        # 422, not 403: the person is allowed to ask, and this particular change cannot
        # be put back. The message says which, and is written to be read by a person.
        raise HTTPException(422, str(e))
    return {"success": True, "data": result}


# NOTE: the two R2-18 routes above are declared BEFORE this one deliberately.
# `/{record_id}` matches any single path segment, so a route registered after it
# is never reached - `/my-changes-today` was answered by this handler and refused
# with the action log's own 403. FastAPI matches in declaration order.
@router.get("/{record_id}")
@router.get("/record/{record_id}")
async def get_record_history(
    record_id: str,
    request: Request,
    page: int = 1,
    limit: int = 50,
    user: dict = Depends(require_role("owner", "admin")),
):
    db = get_db()
    if user.get("role") == "admin" and user.get("sub_category", "") not in AUDIT_READER_SUB_CATEGORIES:
        raise HTTPException(403, "Forbidden")
    if page < 1:
        raise HTTPException(400, "page must be >= 1")
    if not 1 <= limit <= 100:
        raise HTTPException(400, "limit must be between 1 and 100")
    query = {
        "$or": [
            {"entity_id": record_id},
            {"record_id": record_id},
        ]
    }
    is_principal = user.get("role") == "admin" and user.get("sub_category") == "principal"
    if is_principal and user.get("branch_id"):
        query["branch_id"] = user.get("branch_id")
    scoped = scoped_filter(query, get_school_id())  # branch-scope: intentional - a principal is already pinned to their own branch_id a few lines above; the owner reads the school
    skip = (page - 1) * limit
    async with TimedQuery(collection_name="audit_logs", operation="count_documents", query_shape="record_history"):
        total = await db.audit_logs.count_documents(scoped)
    async with TimedQuery(collection_name="audit_logs", operation="find", query_shape="record_history"):
        items = await db.audit_logs.find(scoped, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"success": True, "data": items, "meta": {"page": page, "limit": limit, "total": total}}

