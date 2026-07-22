"""File upload routes backed by private S3 objects."""
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import RedirectResponse
from database import get_db
from middleware.auth import get_current_user
from tenant import add_school_id, get_school_id, scoped_filter
from services.s3_storage import (
    PRESIGNED_URL_EXPIRY_SECONDS,
    build_upload_key,
    create_presigned_get_url,
    delete_object,
    infer_content_type,
    upload_bytes,
)
from datetime import datetime
import logging
import uuid

router = APIRouter(prefix="/api/uploads", tags=["uploads"])
logger = logging.getLogger(__name__)

# File type rules by role
ALLOWED_TYPES = {
    "owner": ["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg", "heic", "mp4"],
    "admin": ["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg", "heic"],
    "teacher": ["pdf", "docx", "xlsx", "png", "jpg", "jpeg"],
    "student": ["pdf", "png", "jpg", "jpeg", "heic"],
}
MAX_SIZE_BY_ROLE = {
    "owner": 50 * 1024 * 1024,
    "admin": 50 * 1024 * 1024,
    "teacher": 20 * 1024 * 1024,
    "student": 10 * 1024 * 1024,
}
LARGE_UPLOAD_WARNING_BYTES = 20 * 1024 * 1024

EXPECTED_MIME_BY_EXTENSION = {
    "pdf": {"application/pdf"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "docx": {"application/zip"},
    "xlsx": {"application/zip"},
    "xls": {"application/vnd.ms-office"},
    "mp4": {"video/mp4"},
    # HEIC brands can occur at variable offsets; accept by extension only.
    "heic": None,
}


def _format_size_limit(limit_bytes: int) -> str:
    return f"{limit_bytes // (1024 * 1024)}MB"


def detect_mime_from_bytes(content: bytes) -> str:
    """Return a conservative MIME family from magic bytes."""
    head = content[:512].lstrip(b"\xef\xbb\xbf")
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "application/zip"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/vnd.ms-office"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "video/mp4"
    return "application/octet-stream"


def validate_file_content_type(filename: str, content: bytes, ext: str) -> None:
    expected = EXPECTED_MIME_BY_EXTENSION.get(ext)
    if expected is None:
        return

    detected = detect_mime_from_bytes(content)
    # DOCX/XLSX are ZIP-based; we accept valid ZIP for these extensions.
    # Known limitation: double-extension names like .exe.pdf are checked by
    # final extension only. Uploaded files are stored and served, not executed.
    if detected not in expected:
        raise HTTPException(415, "File content does not match declared extension")


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
    max_size = MAX_SIZE_BY_ROLE.get(role, 10 * 1024 * 1024)
    if len(content) > max_size:
        size_mb = len(content) / (1024 * 1024)
        raise HTTPException(
            400,
            f"File size {size_mb:.1f}MB exceeds {role} upload limit of {_format_size_limit(max_size)}",
        )
    if len(content) > LARGE_UPLOAD_WARNING_BYTES:
        logger.warning(
            "large_upload_in_memory",
            extra={"role": role, "size_bytes": len(content), "filename": file.filename},
        )

    validate_file_content_type(file.filename, content, ext)

    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}.{ext}"
    content_type = infer_content_type(file.filename, file.content_type)
    school_id = get_school_id()
    s3_key = build_upload_key(file_id, file.filename, school_id=school_id)
    stored = upload_bytes(
        content=content,
        key=s3_key,
        content_type=content_type,
        original_filename=file.filename,
    )

    record = add_school_id({
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
    }, school_id)
    try:
        await db.file_uploads.insert_one(record)
    except Exception:
        logger.error(
            "file_upload_record_insert_failed",
            extra={"s3_key": stored.key, "school_id": school_id, "file_id": file_id},
            exc_info=True,
        )
        try:
            delete_object(stored.key)
        except Exception:
            logger.error(
                "s3_rollback_failed",
                extra={"s3_key": stored.key, "school_id": school_id, "file_id": file_id},
                exc_info=True,
            )
            await db.orphaned_s3_keys.insert_one({
                "s3_key": stored.key,
                "school_id": school_id,
                "file_id": file_id,
                "failed_at": datetime.now().isoformat(),
                "reason": "insert_failed_delete_failed",
            })
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


# File access model:
# - Users can serve their own uploads.
# - Owner/admin+principal users can serve any upload in their current school.
# - Students and other non-admin roles cannot serve another user's upload.
def _can_access_upload(record: dict, user: dict) -> bool:
    """Is this caller entitled to this specific stored file?

    This is the existing file-access permission — a person's own uploads, plus
    owner and admin+principal reaching any file in their school. It introduces no
    NEW permission: a generated document's `uploaded_by` is whoever asked Flo for
    it, and that person could have exported the same data directly.
    """
    can_cross_user = (
        user.get("role") == "owner"
        or (user.get("role") == "admin" and user.get("sub_category") == "principal")
    )
    return record.get("uploaded_by") == user.get("id") or can_cross_user


@router.get("/serve/{filename}")
async def serve_file(filename: str, user: dict = Depends(get_current_user)):
    db = get_db()
    # Prevent path traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(400, "Invalid filename")
    record = await db.file_uploads.find_one(
        # branch-scope: intentional — file_uploads is school-scoped; a file belongs to
        # its uploader and the school, not to a branch.
        scoped_filter({"safe_filename": filename}, get_school_id())
    )
    if not record:
        raise HTTPException(404, "File not found")
    if not _can_access_upload(record, user):
        raise HTTPException(403, "Forbidden")
    if not record.get("s3_key"):
        raise HTTPException(409, "File has not been migrated to S3")
    return RedirectResponse(
        create_presigned_get_url(record["s3_key"]),
        status_code=307,
    )


@router.get("/link/{file_id}")
async def generated_file_link(file_id: str, user: dict = Depends(get_current_user)):
    """Mint a FRESH presigned download URL for a stored file, at request time.

    Why this endpoint exists (D-37). A presigned URL is about 1,200 characters, roughly
    1,000 of them an opaque security token. `draft_document` used to put that URL in its
    tool result, and the prompt asked the model to transcribe it into a `file` block.
    A language model cannot reproduce 1,000 random characters byte-for-byte, so the link
    arrived with a character altered and S3 answered `SignatureDoesNotMatch`. Now the
    model only carries the short `file_id`; the signed URL is minted here when the person
    taps download, so it is always fresh — and Story 10.3's expiry problem disappears.

    It returns JSON rather than redirecting to S3 so that a missing or forbidden file is
    answered in our own words. A 307 straight to S3 would render any S3 error as raw XML
    with the school's bucket name and account number on screen — the very defect Story
    10.3 forbids.
    """
    db = get_db()
    record = await db.file_uploads.find_one(
        # branch-scope: intentional — file_uploads is school-scoped; a file belongs to
        # its uploader and the school, not to a branch.
        scoped_filter({"id": file_id}, get_school_id())
    )
    if not record:
        raise HTTPException(404, "That file could not be found. Please ask for it again.")
    if not _can_access_upload(record, user):
        raise HTTPException(403, "Forbidden")
    if not record.get("s3_key"):
        raise HTTPException(409, "File has not been migrated to S3")
    return {"success": True, "data": {
        "download_url": create_presigned_get_url(record["s3_key"]),
        "file_name": record.get("file_name"),
        "file_type": record.get("file_type"),
        "file_size_kb": record.get("file_size_kb"),
        "expires_in_seconds": PRESIGNED_URL_EXPIRY_SECONDS,
    }}


@router.get("")
async def list_uploads(
    request: Request,
    entity_type: str = None,
    entity_id: str = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
):
    db = get_db()
    user = get_user(request)
    can_cross_user = (
        user.get("role") == "owner"
        or (user.get("role") == "admin" and user.get("sub_category") == "principal")
    )
    query = {"uploaded_by": user["id"]}
    if entity_type:
        query["linked_table"] = entity_type
    if entity_id:
        query["linked_id"] = entity_id
    if can_cross_user:
        query = {}
        if entity_type:
            query["linked_table"] = entity_type
        if entity_id:
            query["linked_id"] = entity_id
    # branch-scope: intentional — file_uploads is school-scoped, not branch-scoped.
    query = scoped_filter(query, get_school_id())
    skip = (page - 1) * limit
    total = await db.file_uploads.count_documents(query)
    files = await db.file_uploads.find(
        query,
        {"_id": 0, "data": 0, "s3_bucket": 0, "s3_key": 0},
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {
        "success": True,
        "data": files,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": skip + len(files) < total,
        },
    }


@router.delete("/{file_id}")
async def delete_file(file_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    # branch-scope: intentional — file_uploads is school-scoped, not branch-scoped.
    record = await db.file_uploads.find_one(scoped_filter({"id": file_id}, get_school_id()), {"data": 0})
    if not record:
        raise HTTPException(404, "File not found")
    if record["uploaded_by"] != user["id"] and user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    if record.get("s3_key"):
        delete_object(record["s3_key"])
    # branch-scope: intentional — file_uploads is school-scoped, not branch-scoped.
    await db.file_uploads.delete_one(scoped_filter({"id": file_id}, get_school_id()))
    return {"success": True}
