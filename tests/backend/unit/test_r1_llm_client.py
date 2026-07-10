"""R1.6 / R1.7 — LLM client contract: single LLMResult return, empty→ok=False,
retry with headroom on empty+length, and the academics/assistant migrations."""
from __future__ import annotations

import pytest

from ai import llm_client as llm_mod
from ai.llm_client import LLMResult, LLMClient, ai_unavailable_result

pytestmark = pytest.mark.asyncio


class _Choice:
    def __init__(self, content, finish_reason):
        self.message = type("M", (), {"content": content})()
        self.finish_reason = finish_reason


class _Resp:
    def __init__(self, content, finish_reason="stop"):
        self.choices = [_Choice(content, finish_reason)]
        self.usage = type("U", (), {"prompt_tokens": 10, "completion_tokens": 5})()


def _client_with(responses):
    """Build an LLMClient whose underlying SDK returns `responses` in order."""
    client = LLMClient.__new__(LLMClient)
    client.deployment = "test-deploy"
    calls = {"n": 0, "max_tokens": []}

    class _Completions:
        def create(self, model, messages, timeout, max_completion_tokens):
            calls["max_tokens"].append(max_completion_tokens)
            r = responses[min(calls["n"], len(responses) - 1)]
            calls["n"] += 1
            return r

    client._client = type("C", (), {"chat": type("Ch", (), {"completions": _Completions()})()})()
    return client, calls


async def test_ai_unavailable_result_is_typed_failure():
    r = ai_unavailable_result("not_configured")
    assert isinstance(r, LLMResult)
    assert r.ok is False and r.text == "" and r.reason == "not_configured"


async def test_not_configured_returns_ok_false():
    client = LLMClient.__new__(LLMClient)
    client._client = None
    client.deployment = "x"
    r = await client.chat("sys", [{"role": "user", "content": "hi"}])
    assert isinstance(r, LLMResult) and r.ok is False


async def test_successful_call_returns_text_and_ok(monkeypatch):
    client, calls = _client_with([_Resp("Here is your answer.")])
    monkeypatch.setattr("services.layaastat.emit_llm_span", _noop_span())
    r = await client.chat("sys", [{"role": "user", "content": "hi"}], "sess")
    assert r.ok is True and r.text == "Here is your answer."
    assert calls["max_tokens"][0] == llm_mod.DEFAULT_MAX_COMPLETION_TOKENS


async def test_empty_content_is_ok_false(monkeypatch):
    client, _ = _client_with([_Resp("", finish_reason="stop")])
    monkeypatch.setattr("services.layaastat.emit_llm_span", _noop_span())
    r = await client.chat("sys", [{"role": "user", "content": "hi"}], "sess")
    assert r.ok is False and r.text == ""


async def test_empty_length_retries_with_more_headroom(monkeypatch):
    # First call: empty + finish_reason=length → retry; second call returns text.
    client, calls = _client_with([
        _Resp("", finish_reason="length"),
        _Resp("Recovered answer after retry.", finish_reason="stop"),
    ])
    monkeypatch.setattr("services.layaastat.emit_llm_span", _noop_span())
    r = await client.chat("sys", [{"role": "user", "content": "hi"}], "sess")
    assert r.ok is True and "Recovered answer" in r.text
    assert calls["n"] == 2, "did not retry on empty+length"
    assert calls["max_tokens"][1] == llm_mod.RETRY_MAX_COMPLETION_TOKENS
    assert calls["max_tokens"][1] > calls["max_tokens"][0]


async def test_exception_returns_ok_false(monkeypatch):
    client = LLMClient.__new__(LLMClient)
    client.deployment = "x"

    class _Boom:
        def create(self, **k):
            raise RuntimeError("boom")

    client._client = type("C", (), {"chat": type("Ch", (), {"completions": _Boom()})()})()
    monkeypatch.setattr("services.layaastat.emit_llm_span", _noop_span())
    r = await client.chat("sys", [{"role": "user", "content": "hi"}], "sess")
    assert isinstance(r, LLMResult) and r.ok is False


def _noop_span():
    async def _span(**kwargs):
        return None
    return _span
