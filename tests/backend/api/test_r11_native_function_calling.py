"""R11.2 + R11.3 — native Azure function calling and true token streaming.

R11.2: the model returns structured `tool_calls` (never JSON-in-text); the chat
tool-loop dispatches them; only authorized tools are advertised so invented tool
names are impossible.

R11.3: the final answer streams token-by-token; a mid-stream provider error is
surfaced via the R1 turn contract (partial text kept + interrupted marker).
"""
from __future__ import annotations

import json

import pytest

from middleware.auth import create_jwt
from ai.llm_client import LLMResult, ToolCall
import routes.chat as chat


CONV_ID = "conv-r11"


@pytest.fixture(autouse=True)
def _wire(fake_db, monkeypatch):
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


def _seed(fake_db):
    fake_db.conversations.docs[:] = [
        {"_id": CONV_ID, "id": CONV_ID, "user_id": "owner-1", "schoolId": "aaryans-joya", "title": "R11"}
    ]
    fake_db.messages.docs[:] = []


def _post(client, text="tell me about Rahul"):
    return client.post(
        f"/api/chat/conversations/{CONV_ID}/messages",
        json={"text": text, "session_id": "sess-r11"},
        headers=_headers(),
    )


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


class _SeqChat:
    """A fake llm_client.chat that returns a queued sequence of LLMResults and
    records whether `tools` were advertised on each call (proves native FC)."""

    def __init__(self, results):
        self.results = list(results)
        self.tools_seen = []

    async def __call__(self, system, messages, session_id=None, role=None, tools=None, tool_choice="auto"):
        self.tools_seen.append(tools)
        return self.results.pop(0) if self.results else LLMResult(text="ok", ok=True)


def test_native_tool_call_dispatches_read_tool(client, fake_db, monkeypatch):
    """R11.2: a structured tool_call runs the tool, then the model answers."""
    _seed(fake_db)

    seq = _SeqChat([
        LLMResult(text="", ok=True, reason="tool_calls",
                  tool_calls=[ToolCall(id="c1", name="search_students", arguments={"query": "Rahul"})]),
        LLMResult(text="Rahul is in class 4B.", tokens=8, ok=True, reason="stop"),
    ])
    monkeypatch.setattr(chat.llm_client, "chat", seq)

    ran = {}

    async def _fake_search(params, user, scope=None):
        ran["params"] = params
        return {"success": True, "data": [{"id": "s1", "name": "Rahul", "class_name": "4B"}], "denied": False}
    monkeypatch.setitem(chat.TOOL_REGISTRY["search_students"], "fn", _fake_search)

    resp = _post(client)
    assert resp.status_code == 200
    events = _events(resp.text)

    # tools were advertised to the model on the first call (native FC wired)
    assert seq.tools_seen and seq.tools_seen[0], "no tools advertised to the model"
    assert any(t["function"]["name"] == "search_students" for t in seq.tools_seen[0])
    # the read tool actually ran with the structured args
    assert ran.get("params", {}).get("query") == "Rahul"
    # a tool_call event was emitted and the final answer persisted
    assert any(e.get("type") == "tool_call" and e.get("tool") == "search_students" for e in events)
    persisted = [m for m in fake_db.messages.docs if m.get("role") == "assistant"]
    assert any("4B" in m.get("content", "") for m in persisted)


def test_native_write_tool_call_emits_confirm_card(client, fake_db, monkeypatch):
    """R11.2/AC4: a write tool_call is gated behind the confirm card, unchanged."""
    _seed(fake_db)
    seq = _SeqChat([
        LLMResult(text="", ok=True, reason="tool_calls",
                  tool_calls=[ToolCall(id="w1", name="award_house_points",
                                       arguments={"student_name": "Rahul", "points": 5, "reason": "helpful"})]),
    ])
    monkeypatch.setattr(chat.llm_client, "chat", seq)

    async def _resolve(params, db, scope=None):
        return params
    monkeypatch.setattr(chat, "_resolve_params", _resolve)

    resp = _post(client, text="give Rahul 5 house points")
    events = _events(resp.text)
    assert any(e.get("type") == "confirm_action" for e in events), \
        f"no confirm card; got {[e.get('type') for e in events]}"


def test_invented_tool_name_is_narrated_not_silent(client, fake_db, monkeypatch):
    """R11.2/AC3: if a tool name is not in the registry, the turn narrates it
    (the provider constrains real calls, but the loop is still fail-safe)."""
    _seed(fake_db)
    seq = _SeqChat([
        LLMResult(text="", ok=True, reason="tool_calls",
                  tool_calls=[ToolCall(id="x", name="teleport_students", arguments={})]),
    ])
    monkeypatch.setattr(chat.llm_client, "chat", seq)

    resp = _post(client)
    persisted = [m for m in fake_db.messages.docs if m.get("role") == "assistant"]
    assert any("don't have a capability" in m.get("content", "") for m in persisted)


def test_build_llm_tools_only_advertises_authorized(monkeypatch):
    """R11.2: a student is never advertised a management/write tool — the model
    cannot invoke what it is not given (invented/unauthorized names impossible)."""
    owner_tools = {t["function"]["name"] for t in chat._build_llm_tools({"role": "owner"})}
    student_tools = {t["function"]["name"] for t in chat._build_llm_tools({"role": "student"})}
    assert "award_house_points" in owner_tools
    assert "award_house_points" not in student_tools
    # every advertised schema is well-formed
    for t in chat._build_llm_tools({"role": "owner"}):
        assert t["type"] == "function"
        assert t["function"]["parameters"]["type"] == "object"


def test_openai_tool_schema_marks_required_and_arrays():
    from ai.tool_functions_v2 import openai_tool_schema, TOOL_REGISTRY
    schema = openai_tool_schema("mark_attendance", TOOL_REGISTRY["mark_attendance"],
                                required=("class_id", "attendance"))
    params = schema["function"]["parameters"]
    assert set(params.get("required", [])) == {"class_id", "attendance"}
    # array params get an items schema (valid JSON Schema)
    assert params["properties"]["attendance"]["type"] == "array"
    assert "items" in params["properties"]["attendance"]


# ── R11.3 streaming ──────────────────────────────────────────────────────────

async def _drain(system, messages, session_id, sink):
    out = []
    async for ev in chat._stream_final_answer(system, messages, session_id, sink):
        out.append(ev)
    return out


@pytest.mark.asyncio
async def test_stream_final_answer_forwards_deltas_and_withholds_rich(monkeypatch):
    """R11.3/AC1: visible prose streams; the <<<RICH_CONTENT>>> block is buffered
    (never shown as raw text) and the full text is captured for parsing."""
    async def fake_stream(system, messages, session_id=None, role=None):
        for t in ["Atten", "dance is ", "91%.", "<<<RICH_", "CONTENT>>>", '{"rich_blocks":[]}']:
            yield {"type": "delta", "text": t}
        yield {"type": "done", "tokens": 12, "reason": "stop", "ok": True}
    monkeypatch.setattr(chat.llm_client, "chat_stream", fake_stream)

    sink = {}
    events = await _drain("sys", [{"role": "user", "content": "hi"}], "s", sink)
    visible = "".join(json.loads(e[len("data: "):])["delta"] for e in events)
    assert visible == "Attendance is 91%."          # marker + json withheld
    assert "<<<RICH_CONTENT>>>" in sink["text"]      # full text captured for parsing
    assert sink["ok"] is True and sink["tokens"] == 12


@pytest.mark.asyncio
async def test_stream_final_answer_midstream_error_keeps_partial(monkeypatch):
    """R11.3/AC3: a mid-stream provider error keeps the partial text and reports
    not-ok, so the R1 turn contract can persist + mark the turn interrupted."""
    async def fake_stream(system, messages, session_id=None, role=None):
        yield {"type": "delta", "text": "Here is the "}
        yield {"type": "error", "reason": "connection_error", "ok": False, "text": "Here is the "}
    monkeypatch.setattr(chat.llm_client, "chat_stream", fake_stream)

    sink = {}
    await _drain("sys", [{"role": "user", "content": "hi"}], "s", sink)
    assert sink["ok"] is False
    assert sink["error"] == "connection_error"
    assert sink["text"] == "Here is the "


@pytest.mark.asyncio
async def test_owner_turn_streams_final_answer(client, fake_db, monkeypatch):
    """R11.3: an owner conversational turn streams the final answer via chat_stream
    (not the simulated buffered chunking)."""
    _seed(fake_db)

    async def only_text(system, messages, session_id=None, role=None, tools=None, tool_choice="auto"):
        return LLMResult(text="unused-buffered", ok=True, reason="stop")
    monkeypatch.setattr(chat.llm_client, "chat", only_text)

    streamed = {"used": False}

    async def fake_stream(system, messages, session_id=None, role=None):
        streamed["used"] = True
        for t in ["You ", "have ", "412 ", "students."]:
            yield {"type": "delta", "text": t}
        yield {"type": "done", "tokens": 9, "reason": "stop", "ok": True}
    monkeypatch.setattr(chat.llm_client, "chat_stream", fake_stream)

    resp = _post(client, text="how many students?")
    events = _events(resp.text)
    assert streamed["used"], "final answer did not use the streaming path"
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "text_delta")
    assert "412 students" in text
    persisted = [m for m in fake_db.messages.docs if m.get("role") == "assistant"]
    assert any("412 students" in m.get("content", "") for m in persisted)
