"""Epic E.5/E.6 — the chat planner SSE path: one confirm card for a valid plan,
graceful deep-link fallback when the assistant can't complete the job."""

from __future__ import annotations

import json

import pytest

from routes import chat
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


class _FakeDb:
    def __init__(self):
        self.confirm_tokens = FakeCollection()
        self.messages = FakeCollection()


_OWNER = {"id": "admin-1", "role": "owner", "branch_id": None}


async def _collect(gen):
    events = []
    async for ev in gen:
        events.append(ev)
    return events


def _parsed(events):
    out = []
    for e in events:
        for line in e.splitlines():
            if line.startswith("data: "):
                out.append(json.loads(line[6:]))
    return out


async def test_valid_plan_emits_single_confirm_card_and_one_token():
    db = _FakeDb()
    calls = [
        {"action": "approve_leave", "params": {"leave_id": "lv-1", "action": "approve"}},
        {"action": "create_announcement", "params": {"title": "T", "content": "C"}},
    ]
    events = _parsed(await _collect(
        chat._stream_plan(calls, _OWNER, db, None, "sess-1", None, "en", 0)
    ))
    confirms = [e for e in events if e.get("type") == "confirm_action"]
    assert len(confirms) == 1
    assert confirms[0]["is_plan"] is True
    assert len(confirms[0]["steps"]) == 2
    # Exactly one plan-confirm token issued for the whole plan.
    assert len(db.confirm_tokens.docs) == 1
    assert db.confirm_tokens.docs[0]["plan"][0]["tool"] == "approve_leave"


async def test_cannot_plan_emits_deeplink_navigate_no_token():
    db = _FakeDb()
    calls = [
        {"action": "make_coffee", "params": {}},
        {"action": "create_announcement", "params": {"title": "T", "content": "C"}},
    ]
    events = _parsed(await _collect(
        chat._stream_plan(calls, _OWNER, db, None, "sess-2", None, "en", 0)
    ))
    assert not any(e.get("type") == "confirm_action" for e in events)
    navs = [e for e in events if e.get("type") == "navigate"]
    assert navs and navs[0]["url"] == "/app?tool=dashboard"
    # No partial write, no token issued.
    assert db.confirm_tokens.docs == []
