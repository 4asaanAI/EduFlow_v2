from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from contextlib import suppress
from typing import Any

# In-process SSE fan-out for a single API process. Multi-process deployments
# should move this channel registry to Redis pub/sub or another shared broker.
KEEPALIVE_SECONDS = 30
KEEPALIVE_COMMENT = ": keepalive\n\n"
_connections: dict[str, dict[str, asyncio.Queue]] = defaultdict(dict)
logger = logging.getLogger(__name__)


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
