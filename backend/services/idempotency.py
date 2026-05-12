from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import Response

try:
    from middleware.auth import decode_jwt
except Exception:  # pragma: no cover - import safety during partial app startup
    decode_jwt = None

from tenant import get_school_id

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL_HOURS = 24
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXCLUDED_PATHS = {
    "/api/chat/confirm",
    "/api/fees/transactions",
}


def should_handle_idempotency(request: Request) -> bool:
    if request.method.upper() not in MUTATING_METHODS:
        return False
    if request.url.path in EXCLUDED_PATHS or request.url.path.endswith("/confirm"):
        return False
    return bool(request.headers.get("Idempotency-Key"))


def _user_id_from_request(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if decode_jwt and auth.startswith("Bearer "):
        try:
            return decode_jwt(auth[7:]).get("id") or "anonymous"
        except Exception:
            return "anonymous"
    return "anonymous"


def record_key(request: Request) -> str:
    raw_key = request.headers.get("Idempotency-Key", "")
    identity = "|".join([
        get_school_id(),
        _user_id_from_request(request),
        request.method.upper(),
        request.url.path,
        raw_key,
    ])
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


async def get_replay_response(db, key: str) -> Response | None:
    now = datetime.now(timezone.utc)
    doc = await db.idempotency_keys.find_one({"key": key, "expires_at": {"$gt": now}})
    if not doc:
        return None
    return Response(
        content=doc.get("body", "").encode("utf-8"),
        status_code=int(doc.get("status_code", 200)),
        media_type=doc.get("content_type") or "application/json",
        headers={"X-Idempotent-Replay": "true"},
    )


async def store_response(
    db,
    *,
    key: str,
    request: Request,
    response: Response,
    body: bytes,
) -> None:
    content_type = response.headers.get("content-type", "")
    if response.status_code < 200 or response.status_code >= 300:
        return
    if "text/event-stream" in content_type:
        return

    try:
        body_text = body.decode("utf-8")
        if "application/json" in content_type:
            json.loads(body_text)
    except Exception:
        return

    now = datetime.now(timezone.utc)
    document: dict[str, Any] = {
        "key": key,
        "raw_key": request.headers.get("Idempotency-Key"),
        "method": request.method.upper(),
        "path": request.url.path,
        "user_id": _user_id_from_request(request),
        "schoolId": get_school_id(),
        "status_code": response.status_code,
        "content_type": content_type.split(";")[0] or "application/json",
        "body": body_text,
        "created_at": now,
        "expires_at": now + timedelta(hours=IDEMPOTENCY_TTL_HOURS),
    }
    try:
        await db.idempotency_keys.update_one(
            {"key": key},
            {"$setOnInsert": {**document, "_id": key}},
            upsert=True,
        )
    except Exception:
        logger.warning("failed to store idempotency response", exc_info=True)
