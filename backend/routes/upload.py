"""File upload routes backed by private S3 objects."""
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import RedirectResponse
from database import get_db
from middleware.auth import get_current_user
from services.s3_storage import (
    build_upload_key,
    create_presigned_get_url,
    delete_object,
    infer_content_type,
    upload_bytes,
)
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

# File type rules by role
ALLOWED_TYPES = {
    "owner": ["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg", "heic", "mp4"],
    "admin": ["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg", "heic"],
    "teacher": ["pdf", "docx", "xlsx", "png", "jpg", "jpeg"],
    "student": ["pdf", "png", "jpg", "jpeg", "heic"],
}
MAX_SIZE_MB = 10
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024


def get_user(req: Request):
    return get_current_user(req)


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

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    allowed = ALLOWED_TYPES.get(role, [])
    if ext not in allowed:
        raise HTTPException(400, f"File type .{ext} not allowed for role {role}. Allowed: {', '.join(allowed)}")

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        size_mb = len(content) / (1024 * 1024)
        raise HTTPException(400, f"File size {size_mb:.1f}MB exceeds {MAX_SIZE_MB}MB limit")

    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}.{ext}"
    content_type = infer_content_type(file.filename, file.content_type)
    s3_key = build_upload_key(file_id, file.filename)
    stored = upload_bytes(
        content=content,
        key=s3_key,
        content_type=content_type,
        original_filename=file.filename,
    )

    record = {
        "_id": file_id,
        "id": file_id,
        "uploaded_by": user["id"],
        "file_url": f"/api/uploads/serve/{safe_filename}",
        "file_name": file.filename,
        "safe_filename": safe_filename,
        "file_type": content_type,
        "file_size_kb": int(len(content) / 1024),
        "file_size_bytes": len(content),
        "linked_table": entity_type,
        "linked_id": entity_id or None,
        "created_at": datetime.now().isoformat(),
        "storage": "s3",
        "s3_bucket": stored.bucket,
        "s3_key": stored.key,
        "s3_etag": stored.etag,
        "sha256": stored.sha256,
    }
    try:
        await db.file_uploads.insert_one(record)
    except Exception:
        delete_object(stored.key)
        raise

    return {"success": True, "data": {
        "id": file_id,
        "uploaded_by": user["id"],
        "file_url": f"/api/uploads/serve/{safe_filename}",
        "file_name": file.filename,
        "file_type": content_type,
        "file_size_kb": int(len(content) / 1024),
        "file_size_bytes": len(content),
        "linked_table": entity_type,
        "linked_id": entity_id or None,
        "created_at": record["created_at"],
        "storage": "s3",
        "sha256": stored.sha256,
    }}


@router.get("/serve/{filename}")
async def serve_file(filename: str):
    db = get_db()
    # Prevent path traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(400, "Invalid filename")
    record = await db.file_uploads.find_one({"safe_filename": filename})
    if not record:
        raise HTTPException(404, "File not found")
    if not record.get("s3_key"):
        raise HTTPException(409, "File has not been migrated to S3")
    return RedirectResponse(
        create_presigned_get_url(record["s3_key"]),
        status_code=307,
    )


@router.get("")
async def list_uploads(request: Request, entity_type: str = None, entity_id: str = None):
    db = get_db()
    user = get_user(request)
    query = {"uploaded_by": user["id"]}
    if entity_type:
        query["linked_table"] = entity_type
    if entity_id:
        query["linked_id"] = entity_id
    if user["role"] in ["owner", "admin"]:
        query = {}
        if entity_type:
            query["linked_table"] = entity_type
        if entity_id:
            query["linked_id"] = entity_id
    files = await db.file_uploads.find(
        query,
        {"_id": 0, "data": 0, "s3_bucket": 0, "s3_key": 0},
    ).sort("created_at", -1).to_list(100)
    return {"success": True, "data": files}


@router.delete("/{file_id}")
async def delete_file(file_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    record = await db.file_uploads.find_one({"id": file_id}, {"data": 0})
    if not record:
        raise HTTPException(404, "File not found")
    if record["uploaded_by"] != user["id"] and user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    if record.get("s3_key"):
        delete_object(record["s3_key"])
    await db.file_uploads.delete_one({"id": file_id})
    return {"success": True}
