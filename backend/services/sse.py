from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from contextlib import suppress
from typing import Any

KEEPALIVE_SECONDS = 30
_connections: dict[str, dict[str, asyncio.Queue]] = defaultdict(dict)


def encode_sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


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
    if _connections[channel].get(session_id) is queue:
        _connections[channel].pop(session_id, None)


async def publish(channel: str, event: dict[str, Any]) -> None:
    for queue in list(_connections[channel].values()):
        if queue.full():
            with suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        with suppress(asyncio.QueueFull):
            queue.put_nowait(event)
