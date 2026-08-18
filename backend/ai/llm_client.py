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
    branch on `.ok` - never isinstance/tuple/dict gymnastics.

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


GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"

# Amazon Bedrock — Nova 2 Lite via global cross-region inference profile.
# The global profile routes to the nearest available region automatically.
# Model ID stays here so switching to Nova Pro or a future model needs one edit.
BEDROCK_DEFAULT_MODEL = "global.amazon.nova-2-lite-v1:0"
BEDROCK_DEFAULT_REGION = "ap-south-1"


def get_azure_key() -> str:
    """Read the Azure OpenAI key, accepting BOTH documented names (R9.1/C2)."""
    return os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_KEY", "")


def validate_ai_config() -> None:
    """Fail loud at startup when no AI provider is configured outside development.

    Priority: Bedrock (AWS_BEARER_TOKEN_BEDROCK) → Groq (GROQ_API_KEY) → Azure.
    """
    env = os.environ.get("ENVIRONMENT", "development").strip().lower()
    if env in ("development", "test", "testing"):
        return
    if os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        return
    if os.environ.get("GROQ_API_KEY"):
        return
    missing = []
    if not get_azure_key():
        missing.append("AZURE_OPENAI_API_KEY (or AZURE_OPENAI_KEY)")
    if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
        missing.append("AZURE_OPENAI_ENDPOINT")
    if missing:
        raise ValueError(
            "LLM configuration required outside development. Set AWS_BEARER_TOKEN_BEDROCK, "
            "GROQ_API_KEY, or both: " + ", ".join(missing)
        )


from ai.writing_style import plain_dashes


class LLMClient:
    def __init__(self):
        bedrock_token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
        groq_key = os.environ.get("GROQ_API_KEY", "")

        if bedrock_token:
            # Bedrock is the primary provider when AWS_BEARER_TOKEN_BEDROCK is set.
            self._provider = "bedrock"
            self.deployment = os.environ.get("BEDROCK_MODEL_ID", BEDROCK_DEFAULT_MODEL)
            self._bedrock_token = bedrock_token
            self._bedrock_region = os.environ.get("AWS_REGION", BEDROCK_DEFAULT_REGION)
            self._client = None  # OpenAI-compat client unused for Bedrock
            self._bedrock_client = self._make_bedrock_client()
            # Groq kept as fallback if Bedrock is set but fails at runtime.
            self._groq_key = groq_key
            logger.info("LLM client using Bedrock | model=%s | region=%s",
                        self.deployment, self._bedrock_region)
        elif groq_key and OpenAI:
            self.deployment = os.environ.get("GROQ_MODEL", GROQ_DEFAULT_MODEL)
            self._provider = "groq"
            self._client = OpenAI(api_key=groq_key, base_url=GROQ_BASE_URL)
            self._bedrock_client = None
            self._bedrock_token = ""
            logger.info("LLM client using Groq | model=%s", self.deployment)
        else:
            self.api_key = get_azure_key()
            self.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
            self.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.6-luna")
            self.api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2026-03-03")
            self._provider = "azure_openai"
            self._bedrock_client = None
            self._bedrock_token = ""

            if self.api_key and self.endpoint and OpenAI:
                base_url = self.endpoint.rstrip("/")
                self._client = OpenAI(api_key=self.api_key, base_url=base_url)
                logger.info("LLM client using Azure OpenAI | model=%s", self.deployment)
            else:
                self._client = None
                logger.warning("LLM client not configured")

    def _make_bedrock_client(self):
        """Create a boto3 bedrock-runtime client with bearer token auth."""
        try:
            import boto3
            token = self._bedrock_token

            client = boto3.client(
                "bedrock-runtime",
                region_name=self._bedrock_region,
                aws_access_key_id="bedrock-bearer-auth",
                aws_secret_access_key="bedrock-bearer-auth",
            )

            def _inject_bearer(request, **kwargs):
                request.headers["Authorization"] = f"Bearer {token}"

            client.meta.events.register("before-send.bedrock-runtime.*", _inject_bearer)
            return client
        except Exception as e:
            logger.error("Failed to create Bedrock client: %s", e)
            return None

    # ── Bedrock message/tool translation ─────────────────────────────────

    def _build_bedrock_messages(self, messages: list, system_prompt: str = "") -> list:
        """Convert internal message list to Bedrock Converse format.

        Nova 2 Lite does not support the `system` parameter in Converse; when
        system_prompt is supplied it is injected as a user+assistant prelude so
        all Nova models work the same way. Tool results become user-role messages
        per the Converse API contract.
        """
        out = []
        if system_prompt:
            out.append({"role": "user", "content": [{"text": system_prompt}]})
            out.append({"role": "assistant", "content": [{"text": "Understood."}]})
        for msg in messages:
            role = msg.get("role", "user")
            if role == "model":
                role = "assistant"

            if role == "tool":
                # Tool results are sent as user messages in Bedrock Converse.
                content_text = msg.get("content", "") or ""
                out.append({
                    "role": "user",
                    "content": [{"toolResult": {
                        "toolUseId": msg.get("tool_call_id", ""),
                        "content": [{"text": content_text}],
                    }}],
                })
                continue

            if role == "assistant" and msg.get("tool_calls"):
                # Re-emit tool call blocks from a prior assistant turn.
                content = []
                if msg.get("content"):
                    content.append({"text": msg["content"]})
                for tc in msg["tool_calls"]:
                    fn = getattr(tc, "function", None)
                    tc_id = getattr(tc, "id", "") or ""
                    tc_name = getattr(fn, "name", "") if fn else (tc.get("id", "") if isinstance(tc, dict) else "")
                    tc_args = {}
                    if isinstance(tc, dict):
                        tc_id = tc.get("id", "")
                        fn_data = tc.get("function", {})
                        tc_name = fn_data.get("name", "")
                        args_raw = fn_data.get("arguments", "{}")
                        try:
                            tc_args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                        except (ValueError, TypeError):
                            tc_args = {}
                    content.append({"toolUse": {
                        "toolUseId": tc_id,
                        "name": tc_name,
                        "input": tc_args,
                    }})
                out.append({"role": "assistant", "content": content})
                continue

            text = msg.get("content") or ""
            if not isinstance(text, str):
                text = str(text)
            out.append({"role": role, "content": [{"text": text}]})
        return out

    @staticmethod
    def _openai_tools_to_bedrock(tools: list) -> list:
        """Convert OpenAI function-calling schema list to Bedrock toolSpec list."""
        result = []
        for t in (tools or []):
            fn = t.get("function", {})
            params = fn.get("parameters", {}) or {}
            result.append({"toolSpec": {
                "name": fn.get("name", ""),
                "description": fn.get("description", fn.get("name", "")),
                "inputSchema": {"json": params},
            }})
        return result

    @staticmethod
    def _extract_bedrock_tool_calls(content_blocks: list) -> list:
        """Extract ToolCall objects from a Bedrock assistant content block list."""
        calls = []
        for block in (content_blocks or []):
            tu = block.get("toolUse")
            if not tu:
                continue
            calls.append(ToolCall(
                id=tu.get("toolUseId", ""),
                name=tu.get("name", ""),
                arguments=tu.get("input", {}) or {},
            ))
        return calls

    @staticmethod
    def _bedrock_text(content_blocks: list) -> str:
        """Extract concatenated text from Bedrock assistant content blocks."""
        parts = []
        for block in (content_blocks or []):
            if "text" in block:
                parts.append(block["text"])
        return "".join(parts)

    # ── message assembly ──────────────────────────────────────────────────
    # Groq free tier: 8,000 tokens per request. A tool result from get_staff_list
    # (90+ staff) or get_student_database can be 4,000-6,000 tokens on its own,
    # leaving no room for the system prompt + history. Cap each tool result at
    # ~1,200 chars (~300 tokens) when in Groq mode so the follow-up call fits.
    _GROQ_TOOL_RESULT_CHAR_LIMIT = 4800  # ~1,200 tokens; generous for small results

    def _build_messages(self, system_prompt: str, messages: list) -> list:
        """Translate our internal message list to the chat-completions shape.

        Supports plain text/multimodal content AND the native-function-calling
        turn shapes (R11.2): an assistant message carrying `tool_calls`, and a
        `role: "tool"` result message carrying `tool_call_id`.
        """
        az_messages = [{"role": "system", "content": system_prompt}]
        groq_mode = self._provider == "groq"
        for msg in messages:
            msg_role = msg.get("role", "user")
            if msg_role == "model":
                msg_role = "assistant"

            if msg_role == "tool":
                content = msg.get("content", "") or ""
                if groq_mode and len(content) > self._GROQ_TOOL_RESULT_CHAR_LIMIT:
                    content = content[:self._GROQ_TOOL_RESULT_CHAR_LIMIT] + "\n...[truncated for token limit]"
                az_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "content": content,
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

        if getattr(self, "_provider", None) == "bedrock":
            return await self._chat_bedrock(system_prompt, messages, session_id, tools, tool_choice)

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
            # Same rule as the streaming path: Flo never prints a long dash, and
            # this is the non-streaming half. Generated documents come through
            # here, and a question paper the school prints is exactly what the
            # owner meant by "not in her replies OR GENERATED DOCUMENTS".
            text = plain_dashes(choice.message.content or "")
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
            # visible content. Retry ONCE with more headroom - but not when the
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
                provider_name=self._provider,
                input_tokens=input_tok,
                output_tokens=output_tok,
                duration_ms=duration,
                trace_id=session_id,
            )
            # R11.2: a tool-request turn is a valid, ok result even with no prose.
            if tool_calls:
                return LLMResult(text=text, tokens=tokens, ok=True, reason=finish_reason, tool_calls=tool_calls)
            # R1.6 AC3: empty content (even after retry) is a typed FAILURE, never
            # a "successful" empty string - the turn contract (R1.3) surfaces a
            # fallback instead of a silent blank.
            if not text.strip():
                return LLMResult(text="", tokens=tokens, ok=False, reason=f"empty_{finish_reason or 'unknown'}")
            return LLMResult(text=text, tokens=tokens, ok=True, reason=finish_reason)
        except Exception as e:
            duration = round((time.perf_counter() - t0) * 1000, 1)
            error_name = e.__class__.__name__.lower()
            error_code = str(getattr(e, 'code', '') or '').lower()
            error_msg = str(e)
            logger.error(
                "LLM error | class=%s | code=%s | msg=%.300s",
                error_name, error_code, error_msg,
            )

            from services.layaastat import emit_llm_span
            await emit_llm_span(
                model=self.deployment,
                provider_name=self._provider,
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
          {"type": "delta", "text": "..."}         - a visible text chunk
          {"type": "done", "tokens": N, "reason": "stop", "ok": True}
          {"type": "error", "reason": "...", "ok": False, "text": "<partial>"}

        The sync SDK stream is drained on a worker thread and bridged to the
        event loop through a queue, so the SSE generator never blocks. A partial
        text buffer is preserved on mid-stream failure so the R1 turn contract
        can keep what was produced and mark the turn interrupted (AC3).
        """
        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"

        if getattr(self, "_provider", None) == "bedrock":
            async for chunk in self._chat_stream_bedrock(system_prompt, messages, session_id):
                yield chunk
            return

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
            except Exception as e:  # noqa: BLE001 - surfaced to caller as an error event
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
                    # Flo never prints a long dash. The /stop-slop habit asks her not to
                    # write one; this is what makes it true. Every reply, every generated
                    # document and every drafted parent message passes through here, which
                    # is why it is done once here rather than at each place that emits a
                    # frame. See ai/writing_style.py.
                    payload = plain_dashes(payload)
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
                        provider_name=self._provider,
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
                        provider_name=self._provider,
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

    # ── Bedrock implementation ────────────────────────────────────────────

    async def _chat_bedrock(
        self, system_prompt: str, messages: list, session_id: str,
        tools: list = None, tool_choice: str = "auto",
    ) -> LLMResult:
        """Non-streaming Bedrock Converse call with tool support."""
        if not self._bedrock_client:
            return ai_unavailable_result("bedrock_not_configured")

        bedrock_messages = self._build_bedrock_messages(messages, system_prompt)
        kwargs: dict = {
            "modelId": self.deployment,
            "messages": bedrock_messages,
            "inferenceConfig": {
                "maxTokens": DEFAULT_MAX_COMPLETION_TOKENS,
                "temperature": 0.7,
            },
        }
        if tools:
            bedrock_tools = self._openai_tools_to_bedrock(tools)
            kwargs["toolConfig"] = {
                "tools": bedrock_tools,
                "toolChoice": {"auto": {}} if tool_choice == "auto" else {"any": {}},
            }

        t0 = time.perf_counter()
        try:
            resp = await asyncio.to_thread(self._bedrock_client.converse, **kwargs)
            duration = round((time.perf_counter() - t0) * 1000, 1)

            msg = resp.get("output", {}).get("message", {})
            content_blocks = msg.get("content", [])
            stop_reason = resp.get("stopReason", "")
            usage = resp.get("usage", {})
            input_tok = usage.get("inputTokens", 0)
            output_tok = usage.get("outputTokens", 0)
            tokens = input_tok + output_tok

            tool_calls = self._extract_bedrock_tool_calls(content_blocks)
            text = plain_dashes(self._bedrock_text(content_blocks))

            from services.layaastat import emit_llm_span
            await emit_llm_span(
                model=self.deployment, provider_name=self._provider,
                input_tokens=input_tok, output_tokens=output_tok,
                duration_ms=duration, trace_id=session_id,
            )
            logger.debug(
                "Bedrock done | session=%s | tokens=%d | stop=%s | tool_calls=%d",
                session_id, tokens, stop_reason, len(tool_calls),
            )

            if tool_calls:
                return LLMResult(text=text, tokens=tokens, ok=True, reason=stop_reason, tool_calls=tool_calls)
            if not text.strip():
                return LLMResult(text="", tokens=tokens, ok=False, reason=f"empty_{stop_reason or 'unknown'}")
            return LLMResult(text=text, tokens=tokens, ok=True, reason=stop_reason)

        except Exception as e:
            duration = round((time.perf_counter() - t0) * 1000, 1)
            error_name = e.__class__.__name__.lower()
            error_code = str(getattr(e, "response", {}).get("Error", {}).get("Code", "") or "").lower()
            logger.error("Bedrock error | class=%s | code=%s | msg=%.300s", error_name, error_code, str(e))
            from services.layaastat import emit_llm_span
            await emit_llm_span(
                model=self.deployment, provider_name=self._provider, duration_ms=duration,
                error_type=error_code or error_name or "bedrock_failed", trace_id=session_id,
            )
            # Fallback to Groq if available; trim history to last 6 messages so
            # the total stays under Groq's 8,000-token limit.
            if self._groq_key and OpenAI:
                logger.warning("Bedrock failed; falling back to Groq | session=%s", session_id)
                groq = LLMClient.__new__(LLMClient)
                groq.deployment = os.environ.get("GROQ_MODEL", GROQ_DEFAULT_MODEL)
                groq._provider = "groq"
                groq._client = OpenAI(api_key=self._groq_key, base_url=GROQ_BASE_URL)
                groq._bedrock_client = None
                groq._bedrock_token = ""
                trimmed = messages[-6:] if len(messages) > 6 else messages
                return await groq.chat(system_prompt, trimmed, session_id, role=None,
                                       tools=tools, tool_choice=tool_choice)
            return ai_unavailable_result(error_code or error_name or "bedrock_failed")

    async def _chat_stream_bedrock(
        self, system_prompt: str, messages: list, session_id: str,
    ):
        """Streaming Bedrock ConverseStream — yields same dicts as chat_stream()."""
        if not self._bedrock_client:
            yield {"type": "error", "reason": "bedrock_not_configured", "ok": False, "text": ""}
            return

        bedrock_messages = self._build_bedrock_messages(messages, system_prompt)
        kwargs = {
            "modelId": self.deployment,
            "messages": bedrock_messages,
            "inferenceConfig": {"maxTokens": DEFAULT_MAX_COMPLETION_TOKENS, "temperature": 0.7},
        }

        q: "queue.Queue" = queue.Queue(maxsize=256)
        t0 = time.perf_counter()

        def _drain_bedrock():
            try:
                resp = self._bedrock_client.converse_stream(**kwargs)
                stream = resp.get("stream")
                input_tok = output_tok = 0
                finish_reason = None
                for event in stream:
                    if "contentBlockDelta" in event:
                        delta = event["contentBlockDelta"].get("delta", {})
                        if "text" in delta:
                            q.put(("delta", delta["text"]))
                    elif "messageStop" in event:
                        finish_reason = event["messageStop"].get("stopReason")
                    elif "metadata" in event:
                        usage = event["metadata"].get("usage", {})
                        input_tok = usage.get("inputTokens", 0)
                        output_tok = usage.get("outputTokens", 0)
                q.put(("done", (input_tok + output_tok, finish_reason)))
            except Exception as exc:
                q.put(("error", exc))
            finally:
                q.put((None, None))

        worker = threading.Thread(target=_drain_bedrock, daemon=True)
        worker.start()

        buffered = []
        try:
            while True:
                kind, payload = await asyncio.to_thread(q.get)
                if kind is None:
                    break
                if kind == "delta":
                    payload = plain_dashes(payload)
                    buffered.append(payload)
                    yield {"type": "delta", "text": payload}
                elif kind == "done":
                    tokens, finish_reason = payload
                    duration = round((time.perf_counter() - t0) * 1000, 1)
                    text = "".join(buffered)
                    tokens = tokens or max(1, len(text) // 4)
                    from services.layaastat import emit_llm_span
                    await emit_llm_span(
                        model=self.deployment, provider_name=self._provider,
                        output_tokens=tokens, duration_ms=duration, trace_id=session_id,
                    )
                    yield {"type": "done", "tokens": tokens, "reason": finish_reason, "ok": True}
                elif kind == "error":
                    duration = round((time.perf_counter() - t0) * 1000, 1)
                    e = payload
                    error_name = e.__class__.__name__.lower()
                    logger.error("Bedrock stream error | class=%s | msg=%.200s", error_name, str(e))
                    from services.layaastat import emit_llm_span
                    await emit_llm_span(
                        model=self.deployment, provider_name=self._provider,
                        duration_ms=duration, error_type=error_name, trace_id=session_id,
                    )
                    yield {"type": "error", "reason": error_name, "ok": False, "text": "".join(buffered)}
        finally:
            pass


llm_client = LLMClient()
