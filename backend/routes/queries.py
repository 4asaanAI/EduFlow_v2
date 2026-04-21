"""
Support Ticket / Query routes — accessible by all roles.
Tickets are visible across all users.
"""
import uuid
import re
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pathlib import Path

from database import get_db
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/queries", tags=["queries"])

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTS = {".mp4", ".png", ".jpg", ".jpeg"}
ALLOWED_PRIORITIES = {"low", "medium", "high", "critical"}
MAX_FILE_MB = 20


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
    tickets = await db.queries.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
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

    attachment_url = None
    attachment_type = None

    if attachment and attachment.filename:
        safe_name = Path(attachment.filename).name
        ext = Path(safe_name).suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(400, "Attachment must be mp4, png, jpg, or jpeg")
        # Check file size
        contents = await attachment.read()
        if len(contents) > MAX_FILE_MB * 1024 * 1024:
            raise HTTPException(400, f"File too large. Max {MAX_FILE_MB}MB")
        # Save file with unique name
        unique_name = f"query_{uuid.uuid4().hex[:8]}{ext}"
        file_path = UPLOAD_DIR / unique_name
        file_path.write_bytes(contents)
        attachment_url = f"/api/uploads/serve/{unique_name}"
        attachment_type = ext.lstrip(".")

    ticket = {
        "id": str(uuid.uuid4()),
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
    await db.queries.insert_one({**ticket, "_id": ticket["id"]})
    return {"success": True, "data": ticket}


# ─── PATCH /api/queries/{id}/resolve ────────────────────────────────────────

@router.patch("/{ticket_id}/resolve")
async def resolve_query(ticket_id: str, request: Request):
    user = get_user(request)
    if not _is_it_tech(user):
        raise HTTPException(403, "Only IT & Tech staff can resolve tickets")
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
        raise HTTPException(403, "Only IT & Tech staff can reopen tickets")
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
        raise HTTPException(403, "Only IT & Tech staff can delete tickets")
    await db.queries.delete_one({"id": ticket_id})
    return {"success": True}
