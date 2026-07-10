"""R11.5 — conversation trace viewer for support.

A per-turn diagnostic timeline that makes the "the AI didn't reply" incident
class diagnosable from the panel alone (AC3), gated owner-only + school-scoped
(AC2), and — critically — never revealing the underlying LLM provider/model to a
client (Layaa AI confidentiality).
"""
from __future__ import annotations

import json

import pytest

from middleware.auth import create_jwt
from ai.llm_client import LLMResult
import routes.chat as chat

CONV_ID = "conv-trace"
SCHOOL = "aaryans-joya"


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    fake_db.ai_turn_traces.docs[:] = []
    fake_db.conversations.docs[:] = []
    fake_db.messages.docs[:] = []
    yield
    fake_db.ai_turn_traces.docs[:] = []


def _seed_trace(fake_db, *, outcome="answered", school=SCHOOL, error_type=None):
    fake_db.ai_turn_traces.docs.append({
        "id": f"tr-{outcome}-{school}", "schoolId": school, "branch_id": None,
        "conversation_id": CONV_ID, "message_id": "m1", "user_id": "u1", "role": "owner",
        "outcome": outcome, "language": "en",
        "tools": [{"tool": "get_fee_summary", "status": "done"}],
        # internal-only provider/model — the endpoint must NOT surface these
        "llm": {"provider": "azure_openai", "model": "gpt-4.1", "finish_reason": "stop",
                "ok": error_type is None, "error_type": error_type, "tokens": 42},
        "created_at": "2026-07-10T10:00:00+00:00",
    })


def test_trace_unauthenticated_returns_401(client):
    resp = client.get(f"/api/chat/conversations/{CONV_ID}/trace")
    assert resp.status_code == 401


def test_trace_wrong_role_returns_403(client, fake_db):
    _seed_trace(fake_db)
    headers = _bearer({"user_id": "t1", "role": "teacher", "name": "T"})
    resp = client.get(f"/api/chat/conversations/{CONV_ID}/trace", headers=headers)
    assert resp.status_code == 403


def test_trace_returns_turns_and_never_reveals_provider(client, fake_db):
    _seed_trace(fake_db, outcome="answered")
    headers = _bearer({"user_id": "own-1", "role": "owner", "name": "Owner"})
    resp = client.get(f"/api/chat/conversations/{CONV_ID}/trace", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] and body["meta"]["count"] == 1
    turn = body["data"][0]
    assert turn["outcome"] == "answered"
    assert turn["assistant"] == "Layaa AI"
    # Confidentiality: the raw provider/model must NOT appear anywhere in the payload.
    blob = json.dumps(body).lower()
    for leak in ("azure", "openai", "gpt-4", "gpt-5", "gpt_"):
        assert leak not in blob, f"provider/model leaked to client: {leak!r}"


def test_trace_is_school_scoped(client, fake_db):
    _seed_trace(fake_db, outcome="answered", school=SCHOOL)
    _seed_trace(fake_db, outcome="answered", school="other-school")
    headers = _bearer({"user_id": "own-1", "role": "owner", "name": "Owner"})
    resp = client.get(f"/api/chat/conversations/{CONV_ID}/trace", headers=headers)
    assert resp.json()["meta"]["count"] == 1  # other-school row excluded


def test_incident_class_is_diagnosable(client, fake_db):
    """AC3: a turn where the assistant produced nothing shows a fallback/unavailable
    outcome + error_type, so an owner can see WHY there was no reply."""
    _seed_trace(fake_db, outcome="unavailable", error_type="ai_unavailable")
    headers = _bearer({"user_id": "own-1", "role": "owner", "name": "Owner"})
    resp = client.get(f"/api/chat/conversations/{CONV_ID}/trace", headers=headers)
    turn = resp.json()["data"][0]
    assert turn["outcome"] == "unavailable"
    assert turn["error_type"] == "ai_unavailable"
    assert turn["ok"] is False


def test_turn_writes_a_trace_row_end_to_end(client, fake_db, monkeypatch):
    """A real owner turn persists a diagnostic trace row (capture is wired)."""
    fake_db.conversations.docs[:] = [
        {"_id": CONV_ID, "id": CONV_ID, "user_id": "own-1", "schoolId": SCHOOL, "title": "t"}
    ]
    import services.token_service as _ts
    monkeypatch.setattr(_ts, "get_db", lambda: fake_db, raising=False)

    async def _ctx(role, uid):
        return {"school_name": "S"}
    monkeypatch.setattr(chat, "build_school_context", _ctx, raising=False)
    monkeypatch.setattr(chat, "build_system_prompt", lambda u, c, l: "sys", raising=False)
    monkeypatch.setattr(chat, "detect_language", lambda t: "en", raising=False)

    async def fake_chat(*a, **k):
        return LLMResult(text="You have 412 students.", tokens=10, ok=True, reason="stop")
    monkeypatch.setattr(chat.llm_client, "chat", fake_chat)

    resp = client.post(
        f"/api/chat/conversations/{CONV_ID}/messages",
        json={"text": "how many students?", "session_id": "s"},
        headers=_bearer({"user_id": "own-1", "role": "owner", "name": "Owner"}),
    )
    assert resp.status_code == 200
    rows = [t for t in fake_db.ai_turn_traces.docs if t.get("conversation_id") == CONV_ID]
    assert rows, "no turn-trace row was written"
    assert rows[-1]["outcome"] == "answered"
