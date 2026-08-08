"""Parent messaging REST routes — the panel entrance to `services/messaging_service`.

⚠️  NOT to be confused with `routes/messaging.py`, which is the STAFF-to-staff internal
chat (threads, groups, read receipts, SSE). Different feature, different audience,
different prefix: that one owns `/api/messaging`, this one owns `/api/parent-messaging`.
Named apart deliberately — the two were briefly conflated during this build.

Flo's `send_parent_message` tool calls the SAME service functions, so a message sent
from a screen and a message sent through Flo are produced by identical code. The
parity gate in `tests/backend/parity/messaging_parity_test.py` pins that.

Services raise domain exceptions; this adapter is the only layer that turns them into
HTTP status codes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from database import get_db
from middleware.auth import (
    require_owner_accountant_or_principal,
    require_owner_or_admin_subcategories,
    require_owner_or_principal,
)
from services.actor_context import actor_ctx_from_user
from services.messaging_service import (
    MessagingLimitError,
    MessagingNotConfiguredError,
    MessagingValidationError,
    channel_status,
    create_template,
    delete_template,
    list_templates,
    preview,
    refresh_whatsapp_template_status,
    send_messages,
    submit_whatsapp_template_for_approval,
    update_template,
)
from tenant import get_school_id

router = APIRouter(prefix="/api/parent-messaging", tags=["parent-messaging"])

# Spreadsheet import is open to the four reviewed authority profiles. Which COLUMNS
# each of them may actually write is decided inside the import service, not here, so
# the REST route and Flo's tool cannot disagree about it.
require_import_profile = require_owner_or_admin_subcategories(
    "principal", "accountant", "management",
)


def _raise(exc: Exception):
    if isinstance(exc, MessagingValidationError):
        raise HTTPException(400, str(exc))
    if isinstance(exc, MessagingNotConfiguredError):
        raise HTTPException(503, str(exc))
    if isinstance(exc, MessagingLimitError):
        raise HTTPException(429, str(exc))
    raise exc


@router.get("/status")
async def get_status(request: Request, user: dict = Depends(require_owner_accountant_or_principal)):
    """Whether each channel can actually send — asked BEFORE a send, not after."""
    return {"success": True, "data": {
        "whatsapp": channel_status("whatsapp"),
        "sms": channel_status("sms"),
    }}


@router.get("/templates")
async def get_templates(request: Request, channel: str = "",
                        user: dict = Depends(require_owner_accountant_or_principal)):
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    rows = await list_templates(db, ctx, channel=channel)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/templates")
async def post_template(request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await create_template(db, ctx, await request.json())
    except Exception as exc:
        _raise(exc)
    return {"success": True, "data": result["template"]}


@router.patch("/templates/{template_id}")
async def patch_template(template_id: str, request: Request,
                         user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await update_template(db, ctx, {**(await request.json()), "template_id": template_id})
    except Exception as exc:
        _raise(exc)
    return {"success": True, "data": result["template"], "note": result.get("note", "")}


@router.delete("/templates/{template_id}")
async def remove_template(template_id: str, request: Request,
                          user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await delete_template(db, ctx, {"template_id": template_id})
    except Exception as exc:
        _raise(exc)
    return {"success": True, "data": result}


@router.post("/templates/submit-whatsapp")
async def submit_whatsapp_template(request: Request,
                                   user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await submit_whatsapp_template_for_approval(db, ctx, await request.json())
    except Exception as exc:
        _raise(exc)
    return {"success": True, "data": result["template"], "message": result["message"]}


@router.get("/templates/{template_id}/approval")
async def template_approval(template_id: str, request: Request,
                            user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await refresh_whatsapp_template_status(db, ctx, {"template_id": template_id})
    except Exception as exc:
        _raise(exc)
    return {"success": True, "data": result}


@router.post("/preview")
async def post_preview(request: Request,
                       user: dict = Depends(require_owner_accountant_or_principal)):
    """Who would receive this, and what it would say. Writes nothing."""
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await preview(db, ctx, await request.json())
    except Exception as exc:
        _raise(exc)
    # The full recipient list carries guardian phone numbers; the panel only needs the
    # count and one sample, so it is not returned here.
    result.pop("recipients", None)
    return {"success": True, "data": result}


@router.post("/send")
async def post_send(request: Request,
                    user: dict = Depends(require_owner_accountant_or_principal)):
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await send_messages(db, ctx, await request.json())
    except Exception as exc:
        _raise(exc)
    return {"success": True, "data": result}


@router.get("/logs")
async def get_logs(request: Request, limit: int = 100, batch_id: str = "",
                   user: dict = Depends(require_owner_accountant_or_principal)):
    """What was actually sent, so 'what did that family get?' is answerable."""
    db = get_db()
    q = {"schoolId": get_school_id()}
    if batch_id:
        q["batch_id"] = batch_id
    rows = await db.message_logs.find(q, {"_id": 0}).sort("sent_at", -1).to_list(min(limit, 500))
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


# ─── Spreadsheet import ───────────────────────────────────────────────────────
# Lives here rather than in `import_data.py` because it shares this file's adapter
# style and is the REST twin of Flo's `import_data_file` tool. Pinned by
# tests/backend/parity/data_import_parity_test.py.

from services.data_import_service import (  # noqa: E402
    ImportFileUnavailableError,
    ImportValidationError,
    apply_import,
    apply_upload,
    preview_import,
    preview_upload,
)

import_router = APIRouter(prefix="/api/data-import", tags=["data-import"])


def _raise_import(exc: Exception):
    if isinstance(exc, ImportValidationError):
        raise HTTPException(400, str(exc))
    if isinstance(exc, ImportFileUnavailableError):
        raise HTTPException(404, str(exc))
    raise exc


@import_router.post("/preview")
async def post_import_preview(request: Request,
                              user: dict = Depends(require_import_profile)):
    """What the import WOULD change, across every row. Writes nothing."""
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await preview_import(db, ctx, await request.json())
    except Exception as exc:
        _raise_import(exc)
    return {"success": True, "data": result}


@import_router.post("/apply")
async def post_import_apply(request: Request,
                            user: dict = Depends(require_import_profile)):
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await apply_import(db, ctx, await request.json())
    except Exception as exc:
        _raise_import(exc)
    return {"success": True, "data": result}


# ─── The same import, from a screen ──────────────────────────────────────────
# The Data Import panel uploads a file directly rather than going through a chat
# attachment. These two endpoints exist so that path reaches the SAME service, and
# therefore the same segment scoping and the same fill-blanks-only rule, instead of
# growing a second set of import rules on the screen side.

MAX_UPLOAD_IMPORT_BYTES = 20 * 1024 * 1024


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD_IMPORT_BYTES:
        raise HTTPException(413, "That file is larger than 20 MB.")
    if not data:
        raise HTTPException(400, "That file is empty.")
    return data


@import_router.post("/upload-preview")
async def post_upload_preview(file: UploadFile = File(...),
                              overwrite: bool = Form(False),
                              user: dict = Depends(require_import_profile)):
    """What an uploaded file WOULD change. Writes nothing."""
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    data = await _read_upload(file)
    try:
        result = await preview_upload(db, ctx, data, file.filename or "", overwrite=overwrite)
    except Exception as exc:
        _raise_import(exc)
    return {"success": True, "data": result}


@import_router.post("/upload-apply")
async def post_upload_apply(file: UploadFile = File(...),
                            overwrite: bool = Form(False),
                            user: dict = Depends(require_import_profile)):
    db = get_db()
    ctx = actor_ctx_from_user(user, school_id=get_school_id())
    data = await _read_upload(file)
    try:
        result = await apply_upload(db, ctx, data, file.filename or "", overwrite=overwrite)
    except Exception as exc:
        _raise_import(exc)
    return {"success": True, "data": result}
