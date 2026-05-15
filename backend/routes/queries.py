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

router = APIRouter(prefix="/api/queries", tags=["queries"])

ALLOWED_EXTS = {".png", ".jpg", ".jpeg"}
ALLOWED_PRIORITIES = {"low", "medium", "high", "critical"}
MAX_FILE_MB = 15  # MongoDB document limit is 16MB


def get_user(req: Request):
    return get_current_user(req)


def _is_it_tech(user: dict) -> bool:
    """Only admin/it_tech may resolve, reopen, or delete tickets."""
    return user["role"] == "admin" and user.get("sub_category") == "it_tech"


# ─── GET /api/queries ────────────────────────────────────────────────────────

@router.get("")
async def list_queries(request: Request, status: str = None, priority: str = None):
    get_user(request)
    db = get_db()
    query = {}
    if status in ("open", "resolved"):
        query["status"] = status
    if priority in ALLOWED_PRIORITIES:
        query["priority"] = priority
    tickets = await db.queries.find(query, {"_id": 0, "attachment_data": 0}).sort("created_at", -1).to_list(200)
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

    # Validate inputs
    title = title.strip()
    description = description.strip()
    if not title or len(title) > 200:
        raise HTTPException(400, "Title must be 1–200 characters")
    if not description or len(description) > 2000:
        raise HTTPException(400, "Description must be 1–2000 characters")
    if priority not in ALLOWED_PRIORITIES:
        raise HTTPException(400, f"Priority must be one of: {', '.join(ALLOWED_PRIORITIES)}")

    ticket_id = str(uuid.uuid4())
    attachment_url = None
    attachment_type = None
    attachment_data = None

    if attachment and attachment.filename:
        ext = Path(attachment.filename).suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(400, "Attachment must be png, jpg, or jpeg")
        contents = await attachment.read()
        if len(contents) > MAX_FILE_MB * 1024 * 1024:
            raise HTTPException(400, f"File too large. Max {MAX_FILE_MB}MB")
        attachment_type = ext.lstrip(".")
        attachment_data = contents
        attachment_url = f"/api/queries/{ticket_id}/attachment"

    ticket = {
        "id": ticket_id,
        "title": title,
        "description": description,
        "priority": priority,
        "status": "open",
        "created_by": user["id"],
        "created_by_name": user.get("name", ""),
        "created_by_role": user.get("role", ""),
        "attachment_url": attachment_url,
        "attachment_type": attachment_type,
        "created_at": datetime.now().isoformat(),
        "resolved_at": None,
        "resolved_by": None,
        "resolved_by_name": None,
    }

    db = get_db()
    db_record = {**ticket, "_id": ticket["id"]}
    if attachment_data:
        db_record["attachment_data"] = attachment_data
    await db.queries.insert_one(db_record)
    return {"success": True, "data": ticket}


# ─── PATCH /api/queries/{id}/resolve ────────────────────────────────────────

@router.patch("/{ticket_id}/resolve")
async def resolve_query(ticket_id: str, request: Request):
    user = get_user(request)
    if not _is_it_tech(user):
        raise HTTPException(403, "Forbidden")
    db = get_db()
    ticket = await db.queries.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    now = datetime.now().isoformat()
    await db.queries.update_one(
        {"id": ticket_id},
        {"$set": {
            "status": "resolved",
            "resolved_at": now,
            "resolved_by": user["id"],
            "resolved_by_name": user.get("name", ""),
        }}
    )
    return {"success": True, "status": "resolved", "resolved_at": now}


# ─── PATCH /api/queries/{id}/unresolve ──────────────────────────────────────

@router.patch("/{ticket_id}/unresolve")
async def unresolve_query(ticket_id: str, request: Request):
    user = get_user(request)
    if not _is_it_tech(user):
        raise HTTPException(403, "Forbidden")
    db = get_db()
    ticket = await db.queries.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    await db.queries.update_one(
        {"id": ticket_id},
        {"$set": {"status": "open", "resolved_at": None, "resolved_by": None, "resolved_by_name": None}}
    )
    return {"success": True, "status": "open"}


# ─── DELETE /api/queries/{id} ────────────────────────────────────────────────

@router.delete("/{ticket_id}")
async def delete_query(ticket_id: str, request: Request):
    user = get_user(request)
    db = get_db()
    ticket = await db.queries.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if not _is_it_tech(user):
        raise HTTPException(403, "Forbidden")
    await db.queries.delete_one({"id": ticket_id})
    return {"success": True}


# ─── GET /api/queries/{id}/attachment ───────────────────────────────────────

@router.get("/{ticket_id}/attachment")
async def get_attachment(ticket_id: str, request: Request):
    get_user(request)
    db = get_db()
    ticket = await db.queries.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if not ticket.get("attachment_data"):
        raise HTTPException(404, "No attachment")
    ext = ticket.get("attachment_type", "jpg")
    content_type = f"image/{ext}" if ext != "pdf" else "application/pdf"
    return Response(content=bytes(ticket["attachment_data"]), media_type=content_type)
