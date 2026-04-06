"""File upload routes — store files on disk, record metadata in MongoDB"""
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from database import get_db
from datetime import datetime
import uuid
import os
import shutil
from pathlib import Path

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# File type rules by role
ALLOWED_TYPES = {
    "owner": ["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg", "heic", "mp4"],
    "admin": ["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg", "heic"],
    "teacher": ["pdf", "docx", "xlsx", "png", "jpg", "jpeg"],
    "student": ["pdf", "png", "jpg", "jpeg", "heic"],
}
MAX_SIZE_MB = 50


def get_user(req: Request):
    return {"id": req.headers.get("X-User-Id", "user-owner-001"), "role": req.headers.get("X-User-Role", "owner")}


@router.post("")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    entity_type: str = Form(default="general"),
    entity_id: str = Form(default=""),
):
    db = get_db()
    user = get_user(request)
    role = user["role"]

    # Check file extension
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    allowed = ALLOWED_TYPES.get(role, [])
    if ext not in allowed:
        raise HTTPException(400, f"File type .{ext} not allowed for role {role}. Allowed: {', '.join(allowed)}")

    # Read file and check size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(400, f"File size {size_mb:.1f}MB exceeds {MAX_SIZE_MB}MB limit")

    # Save to disk
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}.{ext}"
    file_path = UPLOAD_DIR / safe_filename
    with open(file_path, "wb") as f:
        f.write(content)

    # Record in DB
    record = {
        "id": file_id,
        "uploaded_by": user["id"],
        "file_url": f"/api/uploads/serve/{safe_filename}",
        "file_name": file.filename,
        "file_type": file.content_type or f"application/{ext}",
        "file_size_kb": int(len(content) / 1024),
        "linked_table": entity_type,
        "linked_id": entity_id or None,
        "created_at": datetime.now().isoformat(),
        "path": str(file_path),
    }
    await db.file_uploads.insert_one({**record, "_id": record["id"]})

    return {"success": True, "data": {k: v for k, v in record.items() if k != "path"}}


@router.get("/serve/{filename}")
async def serve_file(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(file_path))


@router.get("")
async def list_uploads(request: Request, entity_type: str = None, entity_id: str = None):
    db = get_db()
    user = get_user(request)
    query = {"uploaded_by": user["id"]}
    if entity_type:
        query["linked_table"] = entity_type
    if entity_id:
        query["linked_id"] = entity_id
    # Admin/owner can see all
    if user["role"] in ["owner", "admin"]:
        query = {}
        if entity_type:
            query["linked_table"] = entity_type
        if entity_id:
            query["linked_id"] = entity_id
    files = await db.file_uploads.find(query, {"_id": 0, "path": 0}).sort("created_at", -1).to_list(100)
    return {"success": True, "data": files}


@router.delete("/{file_id}")
async def delete_file(file_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    record = await db.file_uploads.find_one({"id": file_id})
    if not record:
        raise HTTPException(404, "File not found")
    # Only uploader or admin/owner can delete
    if record["uploaded_by"] != user["id"] and user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    # Remove from disk
    if record.get("path") and os.path.exists(record["path"]):
        os.remove(record["path"])
    await db.file_uploads.delete_one({"id": file_id})
    return {"success": True}
