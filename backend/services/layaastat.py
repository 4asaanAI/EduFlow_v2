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

# R9.3 (M9): hold strong refs to fire-and-forget tasks. `asyncio.ensure_future`
# without a reference lets the event loop GC a still-pending task, silently
# dropping the span/event. Tasks self-remove from the set when done.
_pending_tasks: set = set()


def _spawn(coro) -> None:
    try:
        task = asyncio.ensure_future(coro)
    except RuntimeError:
        # No running loop (e.g. called from sync context/tests) — drop quietly.
        coro.close()
        return
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


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
        # R9.3 (M9): a dropped span/event is observability loss — surface it at
        # warning, not debug (debug is suppressed under the INFO root logger).
        logger.warning("layaastat post failed for %s", path, exc_info=True)


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
    _spawn(
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
    _spawn(
        _post("/api/ingest", {
            "event_name": event_name,
            "distinct_id": distinct_id,
            "occurred_at": now,
            "source": source,
            "payload": payload or {},
        })
    )
