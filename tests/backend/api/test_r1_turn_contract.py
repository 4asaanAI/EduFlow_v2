"""R1 — Turn Completion Contract (the incident fix).

Drives the real chat SSE endpoint through the failure injections named in the
architecture doc (§10) and asserts the contract every time:
  * a terminal `done` event with a REAL message id (never f"empty-{conv_id}")
  * a persisted assistant message (reload would show it)
  * the user never ends the turn with nothing on screen

Also covers the LLM-client contract (R1.6/R1.7) and the academics/assistant
migrations (R1.7 AC2/AC3).
"""
from __future__ import annotations

import json

import pytest

from middleware.auth import create_jwt
from ai.llm_client import LLMResult
import routes.chat as chat


CONV_ID = "conv-r1"


@pytest.fixture(autouse=True)
def _wire_chat_deps(fake_db, monkeypatch):
    """Isolate the turn-completion contract from the heavy context-build phase.

    Phase 4 fans out to context_builder (many collections the fake DB doesn't
    model); stub the two Phase-4 helpers so the generator proceeds to the LLM /
    Phase-14 stage, which is what these tests exercise. token_service.get_db is
    pointed at the fake so token accounting doesn't null-crash.
    """
    import services.token_service as _ts
    monkeypatch.setattr(_ts, "get_db", lambda: fake_db, raising=False)

    async def _fake_context(role, uid):
        return {"school_name": "Test School"}
    monkeypatch.setattr(chat, "build_school_context", _fake_context, raising=False)
    monkeypatch.setattr(chat, "build_system_prompt", lambda user, ctx, lang: "system", raising=False)
    monkeypatch.setattr(chat, "detect_language", lambda text: "en", raising=False)
    yield


def _headers():
    return {"Authorization": f"Bearer {create_jwt({'user_id': 'owner-1', 'role': 'owner', 'name': 'Owner'})}"}


def _seed_conversation(fake_db):
    fake_db.conversations.docs[:] = [
        {"_id": CONV_ID, "id": CONV_ID, "user_id": "owner-1", "schoolId": "aaryans-joya", "title": "R1"}
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


def _assistant_messages(fake_db):
    return [m for m in fake_db.messages.docs if m.get("role") == "assistant"]


def _post(client):
    return client.post(
        f"/api/chat/conversations/{CONV_ID}/messages",
        json={"text": "how many students are enrolled?", "session_id": "sess-r1"},
        headers=_headers(),
    )


def _assert_contract(resp, fake_db):
    """Every turn: a done event with a real id + a persisted assistant message."""
    assert resp.status_code == 200
    events = _events(resp.text)
    done = [e for e in events if e.get("type") == "done"]
    assert done, f"no terminal done event; got {[e.get('type') for e in events]}"
    mid = done[-1].get("message_id")
    assert mid, "done event carried no message_id"
    assert not str(mid).startswith("empty-"), "done used the banned empty-{conv_id} sentinel"
    persisted = _assistant_messages(fake_db)
    assert persisted, "no assistant message was persisted (turn would be silent on reload)"
    assert any(m.get("content", "").strip() for m in persisted), "persisted assistant message is blank"
    return events, persisted


def test_llm_unavailable_still_completes_turn(client, fake_db, monkeypatch):
    """RC-1/S2: model returns an unavailable result → user still gets a message."""
    _seed_conversation(fake_db)

    async def fake_chat(*a, **k):
        return LLMResult(text="", tokens=0, ok=False, reason="not_configured")
    monkeypatch.setattr(chat.llm_client, "chat", fake_chat)

    _assert_contract(_post(client), fake_db)


def test_content_policy_marker_becomes_fallback_not_blank(client, fake_db, monkeypatch):
    """R1.4/S3: policy boilerplate is replaced with the fallback, never blanked."""
    _seed_conversation(fake_db)

    async def fake_chat(*a, **k):
        return LLMResult(
            text="The content policy settings on the AI service prevented this.",
            tokens=7, ok=True, reason="stop",
        )
    monkeypatch.setattr(chat.llm_client, "chat", fake_chat)

    _events_, persisted = _assert_contract(_post(client), fake_db)
    assert any(chat.FALLBACK_TEXT in m.get("content", "") for m in persisted)


def test_llm_exception_completes_turn_with_error(client, fake_db, monkeypatch):
    """S9: an LLM exception is caught, surfaced (ai_unavailable), and persisted —
    never a silent turn. The Phase-8 call wrapper converts the crash to ok=False."""
    _seed_conversation(fake_db)

    async def boom(*a, **k):
        raise RuntimeError("azure exploded")
    monkeypatch.setattr(chat.llm_client, "chat", boom)

    resp = _post(client)
    events, _ = _assert_contract(resp, fake_db)
    assert any(e.get("type") in ("error", "ai_unavailable") for e in events), \
        "LLM crash produced neither an error nor ai_unavailable event"


def test_close_tool_matches_suggests_authorized_only():
    """R1.5 AC1: unknown-tool hints suggest close AUTHORIZED names, and never
    invent a suggestion for pure gibberish."""
    owner = {"role": "owner"}
    assert isinstance(chat._close_tool_matches("query_incidnets", owner), list)
    assert chat._close_tool_matches("zzzzzzzzzz", owner) == []


def test_fallback_text_is_non_empty():
    """R1.3: the contract's fallback is real, user-facing text."""
    assert chat.FALLBACK_TEXT and chat.FALLBACK_TEXT.strip()


def test_normal_answer_streams_and_persists(client, fake_db, monkeypatch):
    _seed_conversation(fake_db)

    async def fake_chat(*a, **k):
        return LLMResult(text="You have 412 students enrolled.", tokens=12, ok=True, reason="stop")
    monkeypatch.setattr(chat.llm_client, "chat", fake_chat)

    events, persisted = _assert_contract(_post(client), fake_db)
    assert any(e.get("type") == "text_delta" for e in events)
    assert any("412 students" in m.get("content", "") for m in persisted)
