from __future__ import annotations

import os
import json
import uuid
import asyncio
import logging
import queue
import threading
import time
from dataclasses import dataclass, field

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)

# R1.6 AC2: reasoning-family deployments spend budget on hidden reasoning before
# emitting visible content, so a low ceiling yields empty replies. 4000 is the
# floor for a normal call; the empty+length retry (R1.6 AC1) goes higher still.
DEFAULT_MAX_COMPLETION_TOKENS = 4000
RETRY_MAX_COMPLETION_TOKENS = 8000

# Human-facing text for a degraded/unavailable turn (used by the SSE adapters).
AI_UNAVAILABLE_MESSAGE = "AI is temporarily unavailable. Core school tools remain available."


@dataclass
class ToolCall:
    """A single structured tool call returned by native function calling (R11.2).

    `id` is the provider tool-call id (echoed back on the tool-result message);
    `name` is the registry tool name; `arguments` is the parsed argument dict.
    Replaces the old JSON-in-text tool emission that chat.py used to regex-parse.
    """
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class LLMResult:
    """Single return type for LLMClient.chat() (R1.7 + R11.2).

    Kills the old tuple|dict dual return that caused audit X1 (a tuple/dict was
    persisted as question-paper content). Callers read `.text`/`.tokens` and
    branch on `.ok` — never isinstance/tuple/dict gymnastics.

    R11.2: `tool_calls` carries structured native function calls. When present,
    the turn is a tool-request turn (text is usually empty) and is still `ok`.
    """
    text: str
    tokens: int = 0
    ok: bool = True
    reason: str | None = None
    tool_calls: list | None = None


def ai_unavailable_result(reason: str) -> LLMResult:
    """A typed, not-ok result for a degraded/failed LLM turn."""
    return LLMResult(text="", tokens=0, ok=False, reason=reason)


def get_azure_key() -> str:
    """Read the Azure OpenAI key, accepting BOTH documented names (R9.1/C2).

    The incident-class config bug: code read only ``AZURE_OPENAI_API_KEY`` while
    CLAUDE.md/.env.example documented ``AZURE_OPENAI_KEY`` — a mismatch that left
    the client silently unconfigured (every turn degraded, no error). Accept
    either, preferring the SDK-native ``AZURE_OPENAI_API_KEY``.
    """
    return os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_KEY", "")


def validate_ai_config() -> None:
    """Fail LOUD at startup when the AI config is missing outside development.

    Same posture as ``tenant.validate_school_id`` (R9.1/C2 AC2): a
    non-development environment with no LLM key or endpoint is a
    misconfiguration that would otherwise surface only as silent AI degradation,
    so we raise here and refuse to boot.

    NOTE (confidentiality): env-var names retain the historical AZURE_* prefix
    for ops continuity, but no user-facing surface ever names the provider — the
    assistant is "Layaa AI" to every client.
    """
    env = os.environ.get("ENVIRONMENT", "development").strip().lower()
    if env in ("development", "test", "testing"):
        return
    missing = []
    if not get_azure_key():
        missing.append("AZURE_OPENAI_API_KEY (or AZURE_OPENAI_KEY)")
    if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
        missing.append("AZURE_OPENAI_ENDPOINT")
    if missing:
        raise ValueError(
            "LLM configuration is required outside development. Missing: "
            + ", ".join(missing)
            + ". The AI assistant cannot function without it; refusing to start "
            "rather than degrade silently."
        )


class LLMClient:
    def __init__(self):
        self.api_key = get_azure_key()
        self.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        self.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.3-chat")
        self.api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2026-03-03")

        if self.api_key and self.endpoint and OpenAI:
            # Endpoint already includes /openai/v1 path (AI Foundry v1 style).
            # Use the standard OpenAI client with base_url to avoid a doubled path.
            base_url = self.endpoint.rstrip("/")
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=base_url,
            )
        else:
            self._client = None
            logger.warning("LLM client not configured")

    # ── message assembly ──────────────────────────────────────────────────
    def _build_messages(self, system_prompt: str, messages: list) -> list:
        """Translate our internal message list to the chat-completions shape.

        Supports plain text/multimodal content AND the native-function-calling
        turn shapes (R11.2): an assistant message carrying `tool_calls`, and a
        `role: "tool"` result message carrying `tool_call_id`.
        """
        az_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            msg_role = msg.get("role", "user")
            if msg_role == "model":
                msg_role = "assistant"

            if msg_role == "tool":
                az_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "content": msg.get("content", "") or "",
                })
                continue

            entry = {"role": msg_role, "content": msg.get("content", "")}
            if msg_role == "assistant" and msg.get("tool_calls"):
                # Re-emit prior tool calls so the provider accepts the following
                # tool-result messages.
                entry["tool_calls"] = msg["tool_calls"]
                if entry.get("content") in (None, ""):
                    entry["content"] = None
            az_messages.append(entry)
        return az_messages

    @staticmethod
    def _extract_tool_calls(message) -> list:
        raw = getattr(message, "tool_calls", None)
        if not raw:
            return []
        out = []
        for t in raw:
            fn = getattr(t, "function", None)
            name = getattr(fn, "name", None) if fn else None
            if not name:
                continue
            args_raw = getattr(fn, "arguments", None) if fn else None
            try:
                args = json.loads(args_raw) if args_raw else {}
            except (json.JSONDecodeError, ValueError, TypeError):
                args = {}
            if not isinstance(args, dict):
                args = {}
            out.append(ToolCall(id=getattr(t, "id", "") or "", name=name, arguments=args))
        return out

    async def chat(
        self,
        system_prompt: str,
        messages: list,
        session_id: str = None,
        role: str = None,
        tools: list = None,
        tool_choice: str = "auto",
    ) -> LLMResult:
        """Single non-streaming completion.

        R11.2: pass `tools` (OpenAI function schemas generated from TOOL_REGISTRY)
        to enable native function calling; the model can only name a tool that
        exists in `tools`, so invented tool names are impossible.
        """
        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"

        if not self._client:
            return ai_unavailable_result("not_configured")

        az_messages = self._build_messages(system_prompt, messages)

        def _call(max_tokens: int):
            logger.debug(
                "LLM call | session=%s | deployment=%s | messages=%d | max_tokens=%d | tools=%d",
                session_id, self.deployment, len(az_messages), max_tokens, len(tools or []),
            )
            # Part 2 Patch P5: hard per-call timeout. The SDK's synchronous
            # client default (~600s) is far too long for an SSE handler; long
            # stalls leak workers and tokens.
            kwargs = dict(
                model=self.deployment,
                messages=az_messages,
                timeout=45,
                max_completion_tokens=max_tokens,
            )
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = tool_choice
            response = self._client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            text = choice.message.content or ""
            tool_calls = self._extract_tool_calls(choice.message)
            finish_reason = getattr(choice, "finish_reason", None)
            input_tok = output_tok = 0
            try:
                input_tok = response.usage.prompt_tokens or 0
                output_tok = response.usage.completion_tokens or 0
            except Exception:
                output_tok = max(1, len(text) // 4)
            logger.debug(
                "LLM done | session=%s | tokens=%d | finish=%s | tool_calls=%d",
                session_id, input_tok + output_tok, finish_reason, len(tool_calls),
            )
            return text, input_tok + output_tok, input_tok, output_tok, finish_reason, tool_calls

        t0 = time.perf_counter()
        try:
            text, tokens, input_tok, output_tok, finish_reason, tool_calls = await asyncio.to_thread(
                _call, DEFAULT_MAX_COMPLETION_TOKENS
            )
            # R1.6 AC1: an empty reply truncated by the token ceiling ("length")
            # is almost always the reasoning family exhausting budget before any
            # visible content. Retry ONCE with more headroom — but not when the
            # model legitimately returned tool_calls (empty text is expected then).
            if not text.strip() and not tool_calls and finish_reason == "length":
                logger.warning(
                    "LLM empty content, finish_reason=length; retrying with headroom | session=%s",
                    session_id,
                )
                r_text, r_tokens, r_in, r_out, finish_reason, tool_calls = await asyncio.to_thread(
                    _call, RETRY_MAX_COMPLETION_TOKENS
                )
                text = r_text
                tokens += r_tokens
                input_tok += r_in
                output_tok += r_out
            duration = round((time.perf_counter() - t0) * 1000, 1)
            from services.layaastat import emit_llm_span
            await emit_llm_span(
                model=self.deployment,
                provider_name="azure_openai",
                input_tokens=input_tok,
                output_tokens=output_tok,
                duration_ms=duration,
                trace_id=session_id,
            )
            # R11.2: a tool-request turn is a valid, ok result even with no prose.
            if tool_calls:
                return LLMResult(text=text, tokens=tokens, ok=True, reason=finish_reason, tool_calls=tool_calls)
            # R1.6 AC3: empty content (even after retry) is a typed FAILURE, never
            # a "successful" empty string — the turn contract (R1.3) surfaces a
            # fallback instead of a silent blank.
            if not text.strip():
                return LLMResult(text="", tokens=tokens, ok=False, reason=f"empty_{finish_reason or 'unknown'}")
            return LLMResult(text=text, tokens=tokens, ok=True, reason=finish_reason)
        except Exception as e:
            duration = round((time.perf_counter() - t0) * 1000, 1)
            error_name = e.__class__.__name__.lower()
            error_code = str(getattr(e, 'code', '') or '').lower()
            logger.error(
                "LLM error | class=%s | code=%s | msg=%.300s",
                error_name, error_code, str(e),
            )
            from services.layaastat import emit_llm_span
            await emit_llm_span(
                model=self.deployment,
                provider_name="azure_openai",
                duration_ms=duration,
                error_type=error_code or error_name or "request_failed",
                trace_id=session_id,
            )
            if "timeout" in error_name or "connection" in error_name:
                return ai_unavailable_result(error_name)
            return ai_unavailable_result(error_code or error_name or "request_failed")

    async def chat_stream(
        self,
        system_prompt: str,
        messages: list,
        session_id: str = None,
        role: str = None,
    ):
        """Stream a final-answer completion token-by-token (R11.3).

        Yields dicts:
          {"type": "delta", "text": "..."}         — a visible text chunk
          {"type": "done", "tokens": N, "reason": "stop", "ok": True}
          {"type": "error", "reason": "...", "ok": False, "text": "<partial>"}

        The sync SDK stream is drained on a worker thread and bridged to the
        event loop through a queue, so the SSE generator never blocks. A partial
        text buffer is preserved on mid-stream failure so the R1 turn contract
        can keep what was produced and mark the turn interrupted (AC3).
        """
        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"
        if not self._client:
            yield {"type": "error", "reason": "not_configured", "ok": False, "text": ""}
            return

        az_messages = self._build_messages(system_prompt, messages)
        q: "queue.Queue" = queue.Queue(maxsize=256)
        t0 = time.perf_counter()

        def _drain():
            try:
                stream = self._client.chat.completions.create(
                    model=self.deployment,
                    messages=az_messages,
                    timeout=45,
                    max_completion_tokens=DEFAULT_MAX_COMPLETION_TOKENS,
                    stream=True,
                    stream_options={"include_usage": True},
                )
                finish_reason = None
                input_tok = output_tok = 0
                for ev in stream:
                    if getattr(ev, "usage", None):
                        try:
                            input_tok = ev.usage.prompt_tokens or 0
                            output_tok = ev.usage.completion_tokens or 0
                        except Exception:
                            pass
                    if not getattr(ev, "choices", None):
                        continue
                    ch = ev.choices[0]
                    delta = getattr(ch, "delta", None)
                    if delta is not None and getattr(delta, "content", None):
                        q.put(("delta", delta.content))
                    if getattr(ch, "finish_reason", None):
                        finish_reason = ch.finish_reason
                q.put(("done", (input_tok + output_tok, finish_reason)))
            except Exception as e:  # noqa: BLE001 — surfaced to caller as an error event
                q.put(("error", e))
            finally:
                q.put((None, None))

        worker = threading.Thread(target=_drain, daemon=True)
        worker.start()

        buffered = []
        tokens = 0
        try:
            while True:
                kind, payload = await asyncio.to_thread(q.get)
                if kind is None:
                    break
                if kind == "delta":
                    buffered.append(payload)
                    yield {"type": "delta", "text": payload}
                elif kind == "done":
                    tokens, finish_reason = payload
                    duration = round((time.perf_counter() - t0) * 1000, 1)
                    text = "".join(buffered)
                    if not tokens:
                        tokens = max(1, len(text) // 4)
                    from services.layaastat import emit_llm_span
                    await emit_llm_span(
                        model=self.deployment,
                        provider_name="azure_openai",
                        output_tokens=tokens,
                        duration_ms=duration,
                        trace_id=session_id,
                    )
                    yield {"type": "done", "tokens": tokens, "reason": finish_reason, "ok": True}
                elif kind == "error":
                    duration = round((time.perf_counter() - t0) * 1000, 1)
                    e = payload
                    error_code = str(getattr(e, "code", "") or "").lower()
                    error_name = e.__class__.__name__.lower()
                    logger.error("LLM stream error | class=%s | code=%s | msg=%.200s", error_name, error_code, str(e))
                    from services.layaastat import emit_llm_span
                    await emit_llm_span(
                        model=self.deployment,
                        provider_name="azure_openai",
                        duration_ms=duration,
                        error_type=error_code or error_name or "stream_failed",
                        trace_id=session_id,
                    )
                    yield {
                        "type": "error",
                        "reason": error_code or error_name or "stream_failed",
                        "ok": False,
                        "text": "".join(buffered),
                    }
        finally:
            # Best-effort: the daemon thread exits when the stream closes/GCs.
            pass


llm_client = LLMClient()
