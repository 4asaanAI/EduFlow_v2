"""Build a document, store it, audit it, and hand back a link that expires.

UI Sweep Epic 10, the storing half of Story 10.1.

`services/document_builder.py` turns a description into bytes and knows nothing about
the school, the database or S3. This module is the other half: it puts those bytes
somewhere the right person can fetch them and nobody else can.

IT REUSES THE PATH CERTIFICATES ALREADY USE (`routes/image_gen.py`) rather than
inventing a second one: S3 under the `{school_id}/uploads/...` key convention set in
Part 6, a `file_uploads` record, an audit row, and a presigned URL with an expiry.
A generated document must never be reachable on an unauthenticated public URL —
that was the defect `hotfix-1` was raised for.

THE RULE THAT MATTERS MOST: **generating a document IS a data export.** "Give me a
spreadsheet of every student" and `GET /api/export/students` return the same 1,802
children by different routes. Callers must therefore apply the SAME role gate the
equivalent export already has. This module does not decide that — it cannot know which
data was drawn on — so the caller must, and `ai/tool_functions_v2.py` is where that
happens for Flo.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from database import get_db
from services.audit_service import write_audit
from services.document_builder import BuiltDocument, build_document
from services.s3_storage import (
    PRESIGNED_URL_EXPIRY_SECONDS,
    build_upload_key,
    create_presigned_get_url,
    upload_bytes,
)
from tenant import add_school_id, get_school_id

logger = logging.getLogger(__name__)

# Same abuse brake as certificate generation, and deliberately the same collection so
# a school cannot get a fresh allowance by switching from certificates to documents.
DAILY_DOCUMENT_CAP = 200


class DocumentQuotaExceeded(Exception):
    """The school's daily generation allowance is used up."""


async def _enforce_daily_cap(db, school_id: str, kind: str = "document") -> bool:
    """Per-school, per-kind daily cap. Returns False when over.

    Deliberately identical in shape to `routes/image_gen.py:_enforce_daily_cap` and
    sharing its collection — a second counter would mean a second allowance.
    """
    day = date.today().isoformat()
    q = {"schoolId": school_id, "kind": kind, "day": day}
    existing = await db.image_gen_quota.find_one(q)
    if existing:
        if existing.get("count", 0) >= DAILY_DOCUMENT_CAP:
            return False
        await db.image_gen_quota.update_one({"_id": existing["_id"]}, {"$inc": {"count": 1}})
    else:
        await db.image_gen_quota.insert_one({"_id": str(uuid.uuid4()), **q, "count": 1})
    return True


async def store_document(
    built: BuiltDocument,
    *,
    user: dict,
    audit_action: str = "document_generated",
    linked_table: str = "documents",
    linked_id: str = "",
    source: str = "",
) -> Dict[str, Any]:
    """Persist an already-built document and return a link to it.

    Storage happens only AFTER the bytes exist, so a build that fails leaves no
    orphan object in S3 with no `file_uploads` record pointing at it.
    """
    db = get_db()
    school_id = get_school_id()
    file_id = str(uuid.uuid4())
    suffix = f".{built.doc_type}"
    safe_filename = f"{file_id}{suffix}"

    stored = upload_bytes(
        content=built.content,
        key=build_upload_key(file_id, built.filename, school_id=school_id),
        content_type=built.content_type,
        original_filename=built.filename,
    )

    record = add_school_id({
        "_id": file_id,
        "id": file_id,
        "uploaded_by": user["id"],
        "file_url": f"/api/uploads/serve/{safe_filename}",
        "file_name": built.filename,
        "safe_filename": safe_filename,
        "file_type": built.content_type,
        "file_size_kb": int(built.size_bytes / 1024),
        "file_size_bytes": built.size_bytes,
        "linked_table": linked_table,
        "linked_id": linked_id or None,
        "created_at": datetime.now().isoformat(),
        "generated": True,
        "generated_source": source,
        "storage": "s3",
        "s3_bucket": stored.bucket,
        "s3_key": stored.key,
        "s3_etag": stored.etag,
        "sha256": stored.sha256,
    }, school_id)
    await db.file_uploads.insert_one(record)

    # Every generated document is a copy of school data leaving the platform, so it
    # is audited like one. Ids and counts only — NFR-S2 forbids PII in log fields,
    # and the document body may be a child's medical note.
    await write_audit(
        db,
        action=audit_action,
        entity_id=file_id,
        collection=linked_table,
        changed_by=user["id"],
        changed_by_role=user.get("role", ""),
        school_id=school_id,
        branch_id=user.get("branch_id", ""),
        changes={
            "file_id": file_id,
            "doc_type": built.doc_type,
            "size_bytes": built.size_bytes,
            "truncated": built.truncated,
            "source": source,
        },
    )

    logger.info(
        "document generated | file_id=%s | type=%s | bytes=%d | truncated=%s | source=%s",
        file_id, built.doc_type, built.size_bytes, built.truncated, source,
    )

    return {
        "file_id": file_id,
        "file_name": built.filename,
        "doc_type": built.doc_type,
        "content_type": built.content_type,
        "size_bytes": built.size_bytes,
        "size_kb": int(built.size_bytes / 1024),
        "truncated": built.truncated,
        "notes": built.notes,
        "download_url": create_presigned_get_url(stored.key),
        "expires_in_seconds": PRESIGNED_URL_EXPIRY_SECONDS,
    }


async def create_document(
    *,
    user: dict,
    doc_type: str,
    filename: str = "",
    title: str = "",
    paragraphs: Optional[List[Any]] = None,
    headers: Optional[List[Any]] = None,
    rows: Optional[List[List[Any]]] = None,
    slides: Optional[List[Dict[str, Any]]] = None,
    source: str = "",
    audit_action: str = "document_generated",
) -> Dict[str, Any]:
    """Build + store in one call. Raises DocumentBuildError or DocumentQuotaExceeded.

    The cap is checked BEFORE building: refusing after spending the work is the same
    money and the same memory, with a worse answer.
    """
    db = get_db()
    school_id = get_school_id()
    if not await _enforce_daily_cap(db, school_id):
        raise DocumentQuotaExceeded(
            f"This school has already generated {DAILY_DOCUMENT_CAP} documents today. "
            "The allowance resets tomorrow."
        )

    built = build_document(
        doc_type=doc_type,
        filename=filename,
        title=title,
        paragraphs=paragraphs,
        headers=headers,
        rows=rows,
        slides=slides,
    )
    return await store_document(
        built, user=user, source=source, audit_action=audit_action
    )
