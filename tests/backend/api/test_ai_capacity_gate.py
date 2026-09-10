"""AI concurrency gate - the "heavy usage" cap on simultaneous chat turns.

Verifies the (limit + 1)-th concurrent chat request is rejected immediately
with a heavy_usage event instead of being allowed to queue silently, and that
a slot freed by one request lets the next one through.
"""
from __future__ import annotations

import json

import pytest

from middleware.auth import create_jwt
from ai.llm_client import LLMResult
import routes.chat as chat
import services.ai_capacity as ai_capacity

CONV_ID = "conv-capacity"


@pytest.fixture(autouse=True)
def _wire_chat_deps(fake_db, monkeypatch):
    import services.token_service as _ts
    monkeypatch.setattr(_ts, "get_db", lambda: fake_db, raising=False)

    async def _fake_context(role, uid, branch_id=None):
        return {"school_name": "Test School"}
    monkeypatch.setattr(chat, "build_school_context", _fake_context, raising=False)
    monkeypatch.setattr(chat, "build_system_prompt", lambda user, ctx, lang, **kwargs: "system", raising=False)
    monkeypatch.setattr(chat, "detect_language", lambda text: "en", raising=False)

    async def fake_chat(*a, **k):
        return LLMResult(text="hello", tokens=5, ok=True, reason="stop")
    monkeypatch.setattr(chat.llm_client, "chat", fake_chat)
    yield
    # Never leak a stuck counter into the next test.
    ai_capacity._in_flight = 0


def _headers():
    return {"Authorization": f"Bearer {create_jwt({'user_id': 'owner-1', 'role': 'owner', 'name': 'Owner'})}"}


def _seed_conversation(fake_db):
    fake_db.conversations.docs[:] = [
        {"_id": CONV_ID, "id": CONV_ID, "user_id": "owner-1", "schoolId": "aaryans-joya", "title": "Capacity"}
    ]
    fake_db.messages.docs[:] = []


def _events(resp_text: str):
    out = []
    for part in resp_text.split("\n\n"):
        part = part.strip()
        if part.startswith("data: "):
            try:
                out.append(json.loads(part[len("data: "):]))
            except Exception:
                pass
    return out


def _post(client):
    return client.post(
        f"/api/chat/conversations/{CONV_ID}/messages",
        json={"text": "hi", "session_id": "sess-capacity"},
        headers=_headers(),
    )


def test_request_over_capacity_gets_heavy_usage_message_not_silence(client, fake_db, monkeypatch):
    _seed_conversation(fake_db)
    monkeypatch.setattr(ai_capacity, "MAX_CONCURRENT_AI_REQUESTS", 1)
    ai_capacity._in_flight = 1  # simulate one turn already in flight

    resp = _post(client)
    assert resp.status_code == 200
    events = _events(resp.text)
    heavy = [e for e in events if e.get("type") == "heavy_usage"]
    assert heavy, f"expected a heavy_usage event when at capacity; got {[e.get('type') for e in events]}"
    done = [e for e in events if e.get("type") == "done"]
    assert done, "even a rejected turn must end with a terminal done event"
    # Rejected before Phase 1 - no assistant message should have been persisted.
    assert not [m for m in fake_db.messages.docs if m.get("role") == "assistant"]


def test_slot_is_released_after_turn_completes(client, fake_db, monkeypatch):
    _seed_conversation(fake_db)
    monkeypatch.setattr(ai_capacity, "MAX_CONCURRENT_AI_REQUESTS", 1)

    resp = _post(client)
    assert resp.status_code == 200
    events = _events(resp.text)
    assert not [e for e in events if e.get("type") == "heavy_usage"]
    assert ai_capacity.current_in_flight() == 0, "slot must be freed once the turn finishes"


def test_resolve_max_concurrent_scales_with_cpu_count(monkeypatch):
    monkeypatch.delenv("AI_MAX_CONCURRENT_REQUESTS", raising=False)
    monkeypatch.delenv("AI_CONCURRENCY_PER_CPU", raising=False)
    monkeypatch.setattr(ai_capacity.os, "cpu_count", lambda: 2)
    assert ai_capacity._resolve_max_concurrent() == 6  # 2 vCPU x default 3/CPU

    monkeypatch.setattr(ai_capacity.os, "cpu_count", lambda: 4)
    assert ai_capacity._resolve_max_concurrent() == 12  # 4 vCPU x default 3/CPU


def test_explicit_override_env_wins_over_cpu_sizing(monkeypatch):
    monkeypatch.setenv("AI_MAX_CONCURRENT_REQUESTS", "9")
    assert ai_capacity._resolve_max_concurrent() == 9
