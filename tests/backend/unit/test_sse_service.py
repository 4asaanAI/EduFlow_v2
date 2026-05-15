from __future__ import annotations

import asyncio
from contextlib import suppress

import pytest

from services import sse


@pytest.fixture(autouse=True)
def clear_connections():
    sse._connections.clear()
    yield
    sse._connections.clear()


def test_normalize_session_id_strips_whitespace():
    assert sse.normalize_session_id("  session-1  ") == "session-1"


def test_normalize_session_id_generates_for_whitespace():
    session_id = sse.normalize_session_id("   ", fallback="generated-1")

    assert session_id == "generated-1"


@pytest.mark.asyncio
async def test_keepalive_loop_enqueues_comment_events(monkeypatch):
    monkeypatch.setattr(sse, "KEEPALIVE_SECONDS", 0.05)
    queue = await sse.connect("attendance", "session-1")
    task = asyncio.create_task(sse.keepalive_loop())

    try:
        await asyncio.sleep(0.16)
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    assert len(events) >= 2
    assert all(event == sse.KEEPALIVE_COMMENT for event in events)


@pytest.mark.asyncio
async def test_keepalive_loop_handles_no_channels(monkeypatch):
    monkeypatch.setattr(sse, "KEEPALIVE_SECONDS", 0.05)
    task = asyncio.create_task(sse.keepalive_loop())

    try:
        await asyncio.sleep(0.06)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    assert dict(sse._connections) == {}


@pytest.mark.asyncio
async def test_keepalive_loop_cancels_cleanly(monkeypatch):
    monkeypatch.setattr(sse, "KEEPALIVE_SECONDS", 0.05)
    task = asyncio.create_task(sse.keepalive_loop())
    await asyncio.sleep(0)

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert task.cancelled()


@pytest.mark.asyncio
async def test_publish_does_not_create_empty_channel_bucket():
    await sse.publish("missing-channel", {"type": "noop"})

    assert "missing-channel" not in sse._connections


@pytest.mark.asyncio
async def test_disconnect_removes_empty_channel_bucket():
    queue = await sse.connect("fees", "session-1")

    await sse.disconnect("fees", "session-1", queue)

    assert "fees" not in sse._connections
