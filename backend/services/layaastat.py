"""Fire-and-forget client that ships spans and events to LayaaStat."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_URL = (os.environ.get("LAYAASTAT_URL") or "").rstrip("/")
_KEY = os.environ.get("LAYAASTAT_INGEST_KEY") or ""
_ENABLED = bool(_URL and _KEY)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=5.0)
    return _client


async def _post(path: str, payload: dict) -> None:
    if not _ENABLED:
        return
    try:
        await _get_client().post(
            f"{_URL}{path}",
            json=payload,
            headers={"x-ingest-key": _KEY, "content-type": "application/json"},
        )
    except Exception:
        logger.debug("layaastat post failed", exc_info=True)


async def emit_llm_span(
    *,
    model: str,
    provider_name: str,
    operation_name: str = "chat",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    duration_ms: float | None = None,
    error_type: str | None = None,
    trace_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    asyncio.ensure_future(
        _post("/api/otel", {
            "trace_id": trace_id or str(uuid.uuid4()),
            "span_id": str(uuid.uuid4()),
            "operation_name": operation_name,
            "provider_name": provider_name,
            "model": model,
            "occurred_at": now,
            "duration_ms": duration_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "error_type": error_type,
        })
    )


async def emit_event(
    event_name: str,
    *,
    distinct_id: str | None = None,
    source: str = "eduflow-backend",
    payload: dict[str, Any] | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    asyncio.ensure_future(
        _post("/api/ingest", {
            "event_name": event_name,
            "distinct_id": distinct_id,
            "occurred_at": now,
            "source": source,
            "payload": payload or {},
        })
    )
