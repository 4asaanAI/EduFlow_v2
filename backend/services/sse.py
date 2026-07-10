from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections import defaultdict
from contextlib import suppress
from typing import Any

# R14.1 (P-M3): In-process SSE fan-out.
#
# HARD CONSTRAINT: this registry lives in a single process. Events published on
# worker A are invisible to clients connected to worker B. Running with
# WEB_CONCURRENCY > 1 and no shared broker (REDIS_URL) will silently drop
# notifications for users whose SSE connection landed on a different worker.
#
# Chosen posture: OPTION B — enforce single-worker at startup.
# Startup refuses to start when WEB_CONCURRENCY > 1 unless REDIS_URL is set.
# See `validate_multi_worker_config()` below; called from server.py startup.
# To move to a broker in future, set REDIS_URL and swap `publish` for
# a redis pub/sub fan-out; `connect/disconnect` remain per-worker.
KEEPALIVE_SECONDS = 30
KEEPALIVE_COMMENT = ": keepalive\n\n"
_connections: dict[str, dict[str, asyncio.Queue]] = defaultdict(dict)
logger = logging.getLogger(__name__)


def validate_multi_worker_config() -> None:
    """Refuse to start if WEB_CONCURRENCY > 1 and no shared broker is configured.

    The in-process SSE channel registry is per-worker, so a multi-worker deployment
    will silently drop notifications for users whose connection landed on a different
    worker. Set REDIS_URL to enable a shared broker path, or keep WEB_CONCURRENCY=1.
    """
    try:
        workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
    except ValueError:
        workers = 1

    if workers > 1 and not os.environ.get("REDIS_URL"):
        raise ValueError(
            "WEB_CONCURRENCY=%d but REDIS_URL is not set. The SSE channel registry "
            "is in-process: notifications sent on worker A will not reach clients "
            "connected to worker B. Either set WEB_CONCURRENCY=1 (recommended for "
            "this deployment) or set REDIS_URL to a shared broker. "
            "See docs/deployment-runbook.md §9." % workers
        )


def encode_sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


def normalize_session_id(session_id: str | None, *, fallback: str | None = None) -> str:
    cleaned = (session_id or "").strip()
    if cleaned:
        return cleaned
    generated = fallback or str(uuid.uuid4())
    logger.warning("sse_session_id_missing", extra={"generated_session_id": generated})
    return generated


async def connect(channel: str, session_id: str) -> asyncio.Queue:
    channel_connections = _connections[channel]
    previous = channel_connections.get(session_id)
    if previous:
        with suppress(asyncio.QueueFull):
            previous.put_nowait({"type": "close", "reason": "duplicate_session"})
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    channel_connections[session_id] = queue
    return queue


async def disconnect(channel: str, session_id: str, queue: asyncio.Queue) -> None:
    channel_connections = _connections.get(channel)
    if not channel_connections:
        return
    if channel_connections.get(session_id) is queue:
        channel_connections.pop(session_id, None)
    if not channel_connections:
        _connections.pop(channel, None)


async def publish(channel: str, event: dict[str, Any]) -> None:
    channel_connections = _connections.get(channel)
    if not channel_connections:
        return
    for queue in list(channel_connections.values()):
        if queue.full():
            with suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        with suppress(asyncio.QueueFull):
            queue.put_nowait(event)
    if not channel_connections:
        _connections.pop(channel, None)


async def keepalive_loop() -> None:
    while True:
        await asyncio.sleep(KEEPALIVE_SECONDS)
        for channel, channel_connections in list(_connections.items()):
            for queue in list(channel_connections.values()):
                if queue.full():
                    with suppress(asyncio.QueueEmpty):
                        queue.get_nowait()
                with suppress(asyncio.QueueFull):
                    queue.put_nowait(KEEPALIVE_COMMENT)
            if not channel_connections:
                _connections.pop(channel, None)
