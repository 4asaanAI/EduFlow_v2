from __future__ import annotations
"""
Support Ticket / Query routes — accessible by all roles.
Tickets are visible across all users.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import Response
from pathlib import Path

from database import get_db
from middleware.auth import get_current_user
from services.actor_context import actor_ctx_from_user
from services.query_ticket_service import (
    create_ticket as svc_create_ticket,
    resolve_ticket as svc_resolve_ticket,
    reopen_ticket as svc_reopen_ticket,
    assign_ticket as svc_assign_ticket,
    delete_ticket as svc_delete_ticket,
    TicketValidationError,
    TicketNotFoundError,
)
from tenant import add_school_id, get_school_id, scoped_filter

router = APIRouter(prefix="/api/queries", tags=["queries"])

ALLOWED_EXTS = {".png", ".jpg", ".jpeg"}
ALLOWED_PRIORITIES = {"low", "medium", "high", "critical"}
MAX_FILE_MB = 15  # MongoDB document limit is 16MB


def get_user(req: Request):
    return get_current_user(req)


def _is_it_tech(user: dict) -> bool:
    """Only admin/it_tech may resolve, reopen, or delete tickets."""
    return user["role"] == "admin" and user.get("sub_category") == "it_tech"


def _is_support_admin(user: dict) -> bool:
    if user.get("role") == "owner":
        return True
    if user.get("role") == "admin" and user.get("sub_category") in ("principal", "it_tech", "receptionist"):
        # rbac: intentional — receptionist is front-desk triage, sees all school tickets
        return True
    return False


def _ticket_scope(user: dict, query: dict | None = None) -> dict:
    query = query or {}
    if _is_support_admin(user):
        return scoped_filter(query, get_school_id())
    return scoped_filter(
        {"$and": [query, {"$or": [{"created_by": user.get("id")}, {"assigned_to": user.get("id")}]}]},
        get_school_id(),
    )


# ─── GET /api/queries ────────────────────────────────────────────────────────

@router.get("")
async def list_queries(request: Request, status: str = None, priority: str = None):
    user = get_user(request)
    db = get_db()
    query = {}
    if status in ("open", "in_progress", "resolved"):
        query["status"] = status
    if priority in ALLOWED_PRIORITIES:
        query["priority"] = priority
    tickets = await db.queries.find(_ticket_scope(user, query), {"_id": 0, "attachment_data": 0}).sort("created_at", -1).to_list(200)
    return {"success": True, "data": tickets}


# ─── POST /api/queries ───────────────────────────────────────────────────────

@router.post("")
async def create_query(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    priority: str = Form(...),
    attachment: UploadFile = File(None),
):
    user = get_user(request)
    upload = None
    if attachment and attachment.filename:
        ext = Path(attachment.filename).suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(400, "Attachment must be png, jpg, or jpeg")
        contents = await attachment.read()
        if len(contents) > MAX_FILE_MB * 1024 * 1024:
            raise HTTPException(400, f"File too large. Max {MAX_FILE_MB}MB")
        upload = {"data": contents, "type": ext.lstrip(".")}

    # AD7 shared write path — same service as the AI `create_query_ticket` tool;
    # only the multipart attachment handling above is route-specific.
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    params = {
        "title": title,
        "description": description,
        "priority": priority,
        "category": request.query_params.get("category"),
        "assigned_to": request.query_params.get("assigned_to"),
    }
    try:
        result = await svc_create_ticket(db, actor_ctx, params, attachment=upload)
    except TicketValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["ticket"]}


# ─── PATCH /api/queries/{id}/resolve ────────────────────────────────────────

@router.patch("/{ticket_id}/resolve")
async def resolve_query(ticket_id: str, request: Request):
    user = get_user(request)
    if not (_is_it_tech(user) or user.get("role") == "owner"):
        raise HTTPException(403, "Forbidden")
    # AD7 shared write path — same service as the AI `resolve_query_ticket` tool.
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_resolve_ticket(db, actor_ctx, {"ticket_id": ticket_id})
    except TicketNotFoundError:
        raise HTTPException(404, "Ticket not found")
    except TicketValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "status": "resolved", "resolved_at": result["resolved_at"]}


# ─── PATCH /api/queries/{id}/unresolve ──────────────────────────────────────

@router.patch("/{ticket_id}/unresolve")
async def unresolve_query(ticket_id: str, request: Request):
    user = get_user(request)
    if not (_is_it_tech(user) or user.get("role") == "owner"):
        raise HTTPException(403, "Forbidden")
    # AD7 shared write path — same service as the AI `reopen_query_ticket` tool.
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_reopen_ticket(db, actor_ctx, {"ticket_id": ticket_id})
    except TicketNotFoundError:
        raise HTTPException(404, "Ticket not found")
    except TicketValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "status": "open"}


# ─── DELETE /api/queries/{id} ────────────────────────────────────────────────

@router.patch("/{ticket_id}/assign")
async def assign_query(ticket_id: str, request: Request):
    user = get_user(request)
    if not _is_support_admin(user):
        raise HTTPException(403, "Forbidden")
    # AD7 shared write path — same service as the AI `assign_query_ticket` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        result = await svc_assign_ticket(
            db, actor_ctx,
            {"ticket_id": ticket_id, "assigned_to": body.get("assigned_to"), "status": body.get("status", "in_progress")})
    except TicketNotFoundError:
        raise HTTPException(404, "Ticket not found")
    except TicketValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["ticket"]}


@router.delete("/{ticket_id}")
async def delete_query(ticket_id: str, request: Request):
    user = get_user(request)
    if not (_is_it_tech(user) or user.get("role") == "owner"):
        raise HTTPException(403, "Forbidden")
    # AD7 shared write path — same service as the AI `delete_query_ticket` tool.
    db = get_db()
    actor_ctx = actor_ctx_from_user(user)
    try:
        await svc_delete_ticket(db, actor_ctx, {"ticket_id": ticket_id})
    except TicketNotFoundError:
        raise HTTPException(404, "Ticket not found")
    except TicketValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


# ─── GET /api/queries/{id}/attachment ───────────────────────────────────────

@router.get("/{ticket_id}/attachment")
async def get_attachment(ticket_id: str, request: Request):
    user = get_user(request)
    db = get_db()
    ticket = await db.queries.find_one(_ticket_scope(user, {"id": ticket_id}))
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if not ticket.get("attachment_data"):
        raise HTTPException(404, "No attachment")
    ext = ticket.get("attachment_type", "jpg")
    content_type = f"image/{ext}" if ext != "pdf" else "application/pdf"
    return Response(content=bytes(ticket["attachment_data"]), media_type=content_type)
