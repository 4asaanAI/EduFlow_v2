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

# Groq primary provider config
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-120b"

# Groq free/on-demand tier counts prompt tokens + reserved max_completion_tokens
# against a single per-minute ceiling (TPM). A request 413s ("Request too large")
# when prompt + reserved output exceeds this, EVEN IF the model would never emit
# that many output tokens. So the completion budget must be FITTED to the space
# left under the ceiling after the prompt — otherwise a trivial "hi" reserves the
# full DEFAULT_MAX and tips a ~4k-token prompt over the 8k limit.
GROQ_TPM_LIMIT = 8000
# Buffer for the difference between our chars/4 estimate and Groq's real tokenizer
# (tool schemas tokenize denser than prose). Keep generous — a too-small margin
# reintroduces the 413.
GROQ_TPM_SAFETY_MARGIN = 1000
# Never fit below this — a reasoning model spends output budget on hidden thinking
# before any visible content, so too small a floor yields empty replies.
GROQ_MIN_COMPLETION_TOKENS = 1024

# gpt-oss is a REASONING model: by default it burns thousands of hidden reasoning
# tokens even on a trivial "hi" (observed: 2900+ tokens for a 25-char reply). On
# Groq's free 8000 TPM tier that single behaviour both slows every turn AND blows
# the per-minute budget → 429 throttling → 10–23s SDK backoff waits. "low" effort
# cuts the reasoning spend dramatically for a school-assistant workload that rarely
# needs deep chain-of-thought, keeping turns fast and under the TPM ceiling.
GROQ_REASONING_EFFORT = os.environ.get("GROQ_REASONING_EFFORT", "low").strip().lower()


def _is_gpt_oss(model: str) -> bool:
    """gpt-oss models accept the `reasoning_effort` knob; others reject it."""
    return "gpt-oss" in (model or "").lower()


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
    # Which provider/model actually produced this result (Groq vs Azure fallback).
    # Used for correct token/model attribution in usage logs and turn traces —
    # never assume the configured Azure deployment answered.
    provider: str | None = None
    model: str | None = None


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
            logger.warning("LLM client (Azure) not configured")

        # Groq primary provider — optional; falls back to Azure if absent or failing.
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key and OpenAI:
            self._groq_client = OpenAI(api_key=groq_key, base_url=GROQ_BASE_URL)
            self._groq_model = GROQ_MODEL
            print(f"[LLM INIT] Groq configured ✓ | model={GROQ_MODEL} | key={groq_key[:12]}...")
            logger.info("Groq primary provider configured | model=%s", GROQ_MODEL)
        else:
            self._groq_client = None
            self._groq_model = GROQ_MODEL
            print(f"[LLM INIT] Groq NOT configured | GROQ_API_KEY={'SET but OpenAI missing' if groq_key else 'MISSING'}")
            logger.info("Groq primary provider not configured (GROQ_API_KEY missing); using Azure only")

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

    def _make_completion_call(self, client, model: str, az_messages: list, tools: list, tool_choice: str, max_tokens: int):
        """Execute a single synchronous chat-completions call.

        Extracted so both Groq and Azure paths reuse identical call logic with
        different client/model values. Called via asyncio.to_thread.
        """
        kwargs = dict(
            model=model,
            messages=az_messages,
            timeout=45,
            max_completion_tokens=max_tokens,
        )
        # Cut hidden reasoning spend on gpt-oss (Groq) — see GROQ_REASONING_EFFORT.
        if _is_gpt_oss(model) and GROQ_REASONING_EFFORT:
            kwargs["reasoning_effort"] = GROQ_REASONING_EFFORT
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        response = client.chat.completions.create(**kwargs)
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
        return text, input_tok + output_tok, input_tok, output_tok, finish_reason, tool_calls

    async def _attempt_chat(
        self,
        client,
        model: str,
        provider_name: str,
        az_messages: list,
        tools: list,
        tool_choice: str,
        session_id: str,
        t0: float,
    ) -> LLMResult | None:
        """Try one provider. Returns LLMResult on success, None on any failure.

        Includes the R1.6 AC1 empty+length retry. Emits a layaastat span.
        Logs at DEBUG on success, WARNING on failure so fallback events are
        always visible in logs regardless of log level.
        """
        logger.debug(
            "LLM call | provider=%s | session=%s | model=%s | messages=%d | tools=%d",
            provider_name, session_id, model, len(az_messages), len(tools or []),
        )
        try:
            # Token count safeguard: warn before sending if payload looks oversized.
            # (chars of messages JSON + tool schemas) / 4 ≈ tokens — fast, approximate.
            _TOKEN_WARN = 7000
            _msg_chars = sum(len(json.dumps(m)) for m in az_messages)
            _tool_chars = sum(len(json.dumps(t)) for t in (tools or []))
            _est_tokens = (_msg_chars + _tool_chars) // 4
            print(f"[LLM CALL] provider={provider_name} | session={session_id} | messages={len(az_messages)} | tools={len(tools or [])} | ~{_est_tokens} tokens")
            if _est_tokens > _TOKEN_WARN:
                print(f"[LLM WARN] payload {_est_tokens} tokens > {_TOKEN_WARN} threshold")
                logger.warning(
                    "LLM payload token estimate %d > %d | provider=%s | session=%s | "
                    "messages=%d | tools=%d — check EXCLUDE_FOR_ROLE or trim history",
                    _est_tokens, _TOKEN_WARN, provider_name, session_id,
                    len(az_messages), len(tools or []),
                )

            # Groq's TPM ceiling counts prompt + reserved completion. Fit the
            # completion budget into the space left after the prompt so a request
            # can't 413 on output it may never use. Azure has no such coupling —
            # it keeps the full DEFAULT/RETRY budget.
            _default_max = DEFAULT_MAX_COMPLETION_TOKENS
            _retry_max = RETRY_MAX_COMPLETION_TOKENS
            if provider_name == "groq":
                _fitted = GROQ_TPM_LIMIT - _est_tokens - GROQ_TPM_SAFETY_MARGIN
                _default_max = max(GROQ_MIN_COMPLETION_TOKENS, min(_default_max, _fitted))
                _retry_max = max(GROQ_MIN_COMPLETION_TOKENS, min(_retry_max, _fitted))
                print(f"[LLM FIT] groq completion budget fitted to {_default_max} (prompt~{_est_tokens} + budget must stay under {GROQ_TPM_LIMIT} TPM)")
                logger.info(
                    "Groq completion budget fitted | session=%s | prompt_est=%d | budget=%d | tpm_limit=%d",
                    session_id, _est_tokens, _default_max, GROQ_TPM_LIMIT,
                )

            print(f"[LLM CALL] sending request to {provider_name}...")
            text, tokens, input_tok, output_tok, finish_reason, tool_calls = await asyncio.to_thread(
                self._make_completion_call, client, model, az_messages, tools, tool_choice,
                _default_max,
            )
            # R1.6 AC1: empty reply truncated by the token ceiling — retry ONCE
            # with more headroom (not when tool_calls, since empty text is normal then).
            if not text.strip() and not tool_calls and finish_reason == "length":
                logger.warning(
                    "LLM empty content finish_reason=length; retrying with headroom | provider=%s | session=%s",
                    provider_name, session_id,
                )
                r_text, r_tokens, r_in, r_out, finish_reason, tool_calls = await asyncio.to_thread(
                    self._make_completion_call, client, model, az_messages, tools, tool_choice,
                    _retry_max,
                )
                text = r_text
                tokens += r_tokens
                input_tok += r_in
                output_tok += r_out

            duration = round((time.perf_counter() - t0) * 1000, 1)
            logger.debug(
                "LLM done | provider=%s | session=%s | tokens=%d | finish=%s | tool_calls=%d",
                provider_name, session_id, tokens, finish_reason, len(tool_calls),
            )
            from services.layaastat import emit_llm_span
            await emit_llm_span(
                model=model,
                provider_name=provider_name,
                input_tokens=input_tok,
                output_tokens=output_tok,
                duration_ms=duration,
                trace_id=session_id,
            )
            print(f"[LLM OK] provider={provider_name} | finish={finish_reason} | tokens={tokens} | tool_calls={len(tool_calls)} | text_len={len(text)}")
            if tool_calls:
                return LLMResult(text=text, tokens=tokens, ok=True, reason=finish_reason, tool_calls=tool_calls, provider=provider_name, model=model)
            # R1.6 AC3: empty content (even after retry) is a typed FAILURE.
            if not text.strip():
                print(f"[LLM EMPTY] provider={provider_name} returned empty text | finish={finish_reason}")
                return LLMResult(text="", tokens=tokens, ok=False, reason=f"empty_{finish_reason or 'unknown'}", provider=provider_name, model=model)
            return LLMResult(text=text, tokens=tokens, ok=True, reason=finish_reason, provider=provider_name, model=model)

        except Exception as e:
            duration = round((time.perf_counter() - t0) * 1000, 1)
            error_name = e.__class__.__name__.lower()
            error_code = str(getattr(e, "code", "") or "").lower()
            print(f"[LLM ERROR] provider={provider_name} | {type(e).__name__} | code={error_code} | {str(e)[:400]}")
            logger.warning(
                "LLM provider failed | provider=%s | session=%s | class=%s | code=%s | msg=%.300s",
                provider_name, session_id, error_name, error_code, str(e),
            )
            from services.layaastat import emit_llm_span
            await emit_llm_span(
                model=model,
                provider_name=provider_name,
                duration_ms=duration,
                error_type=error_code or error_name or "request_failed",
                trace_id=session_id,
            )
            return None  # signal: caller should try next provider

    async def chat(
        self,
        system_prompt: str,
        messages: list,
        session_id: str = None,
        role: str = None,
        tools: list = None,
        tool_choice: str = "auto",
    ) -> LLMResult:
        """Single non-streaming completion with Groq primary → Azure fallback.

        R11.2: pass `tools` (OpenAI function schemas generated from TOOL_REGISTRY)
        to enable native function calling; the model can only name a tool that
        exists in `tools`, so invented tool names are impossible.

        Provider selection:
          1. Groq (openai/gpt-oss-120b) — primary, if GROQ_API_KEY is configured.
             Prints "groq" to stdout for debug visibility.
          2. Azure OpenAI — fallback, always tried if Groq is absent or fails.
             Prints "existing" to stdout for debug visibility.

        A failure at step 1 is always logged as a WARNING (never silent) before
        step 2 is attempted, fulfilling the zero-silent-failures contract.
        """
        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"

        az_messages = self._build_messages(system_prompt, messages)
        t0 = time.perf_counter()

        # Use getattr so tests that create LLMClient via __new__ (no __init__)
        # and don't set these attributes still work correctly.
        _groq_client = getattr(self, "_groq_client", None)
        _groq_model = getattr(self, "_groq_model", GROQ_MODEL)

        print(f"[CHAT] session={session_id} | messages={len(messages)} | tools={len(tools or [])} | groq_ready={bool(_groq_client)} | azure_ready={bool(self._client)}")

        # ── Primary: Groq ──────────────────────────────────────────────────
        if _groq_client:
            print("[CHAT] → trying Groq primary")
            print("groq")  # debug: confirms Groq is the active provider
            logger.info("LLM primary: Groq | session=%s | model=%s", session_id, _groq_model)
            result = await self._attempt_chat(
                _groq_client, _groq_model, "groq",
                az_messages, tools, tool_choice, session_id, t0,
            )
            if result is not None:
                print(f"[CHAT] Groq succeeded | ok={result.ok} | reason={result.reason}")
                return result
            # result is None → Groq failed; log the fallback and continue
            print("[CHAT] Groq returned None → falling back to Azure")
            logger.warning(
                "Groq primary failed — falling back to Azure | session=%s", session_id
            )
        else:
            print("[CHAT] Groq client not available, skipping to Azure")

        # ── Fallback: Azure OpenAI ─────────────────────────────────────────
        if not self._client:
            print("[CHAT] Azure client also not configured → ai_unavailable")
            logger.error(
                "No LLM provider available | session=%s | groq_configured=%s | azure_configured=%s",
                session_id, bool(_groq_client), bool(self._client),
            )
            return ai_unavailable_result("not_configured")

        print("[CHAT] → trying Azure fallback")
        print("existing")  # debug: confirms Azure is the active provider
        logger.info("LLM fallback: Azure | session=%s | model=%s", session_id, self.deployment)
        result = await self._attempt_chat(
            self._client, self.deployment, "azure_openai",
            az_messages, tools, tool_choice, session_id, t0,
        )
        if result is not None:
            print(f"[CHAT] Azure succeeded | ok={result.ok} | reason={result.reason}")
            return result

        # Both providers failed — never return silently.
        print("[CHAT] BOTH providers failed → ai_unavailable(all_providers_failed)")
        logger.error(
            "All LLM providers failed | session=%s | groq_tried=%s",
            session_id, bool(_groq_client),
        )
        return ai_unavailable_result("all_providers_failed")

    def _run_stream_drain(self, client, model: str, az_messages: list, q: "queue.Queue", max_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS) -> None:
        """Worker thread: drain a streaming completion into queue `q`.

        Events pushed to `q`:
          ("delta", text_chunk)
          ("done",  (total_tokens, finish_reason))
          ("error", exception)
          (None, None)  — always last, signals end of stream

        `max_tokens` is fitted by the caller for TPM-limited providers (Groq).
        """
        try:
            _stream_kwargs = dict(
                model=model,
                messages=az_messages,
                timeout=45,
                max_completion_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
            # Cut hidden reasoning spend on gpt-oss (Groq) — see GROQ_REASONING_EFFORT.
            if _is_gpt_oss(model) and GROQ_REASONING_EFFORT:
                _stream_kwargs["reasoning_effort"] = GROQ_REASONING_EFFORT
            stream = client.chat.completions.create(**_stream_kwargs)
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
        except Exception as e:  # noqa: BLE001
            q.put(("error", e))
        finally:
            q.put((None, None))

    async def chat_stream(
        self,
        system_prompt: str,
        messages: list,
        session_id: str = None,
        role: str = None,
    ):
        """Stream a final-answer completion token-by-token with Groq primary → Azure fallback.

        Yields dicts:
          {"type": "delta", "text": "..."}         — a visible text chunk
          {"type": "done", "tokens": N, "reason": "stop", "ok": True}
          {"type": "error", "reason": "...", "ok": False, "text": "<partial>"}

        Provider selection mirrors chat():
          1. Groq — primary, prints "groq" to stdout.
          2. Azure — fallback if Groq is absent OR fails before any text is emitted.
             Prints "existing" to stdout.

        Mid-stream fallback: if Groq has already emitted at least one text delta,
        we cannot switch providers (the SSE stream is committed). In that case the
        error is forwarded as-is. Fallback only happens when Groq errors before
        any text reaches the client.
        """
        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"

        az_messages = self._build_messages(system_prompt, messages)
        t0 = time.perf_counter()

        # Build the ordered list of (provider_name, client, model) to try.
        _groq_client = getattr(self, "_groq_client", None)
        _groq_model = getattr(self, "_groq_model", GROQ_MODEL)
        providers: list[tuple[str, object, str]] = []
        if _groq_client:
            providers.append(("groq", _groq_client, _groq_model))
        if self._client:
            providers.append(("azure_openai", self._client, self.deployment))

        print(f"[STREAM] session={session_id} | providers_available={[p[0] for p in providers]}")

        if not providers:
            print("[STREAM] no providers configured → error")
            yield {"type": "error", "reason": "not_configured", "ok": False, "text": ""}
            return

        for attempt_idx, (provider_name, client, model) in enumerate(providers):
            is_last_provider = (attempt_idx == len(providers) - 1)

            if provider_name == "groq":
                print(f"[STREAM] → trying Groq stream | model={model}")
                print("groq")  # debug: confirms Groq stream is active
                logger.info("LLM stream primary: Groq | session=%s | model=%s", session_id, model)
            else:
                print(f"[STREAM] → trying Azure stream | model={model}")
                print("existing")  # debug: confirms Azure stream is active
                logger.info("LLM stream fallback: Azure | session=%s | model=%s", session_id, model)

            # Fit the completion budget under Groq's TPM ceiling (see chat()).
            # Streaming carries no tool schemas, but a post-tool final answer
            # injects the tool result into the prompt, which can still be large.
            _stream_max = DEFAULT_MAX_COMPLETION_TOKENS
            if provider_name == "groq":
                _est_tokens = sum(len(json.dumps(m)) for m in az_messages) // 4
                _fitted = GROQ_TPM_LIMIT - _est_tokens - GROQ_TPM_SAFETY_MARGIN
                _stream_max = max(GROQ_MIN_COMPLETION_TOKENS, min(_stream_max, _fitted))
                print(f"[STREAM FIT] groq completion budget fitted to {_stream_max} (prompt~{_est_tokens}, TPM {GROQ_TPM_LIMIT})")
                logger.info(
                    "Groq stream completion budget fitted | session=%s | prompt_est=%d | budget=%d",
                    session_id, _est_tokens, _stream_max,
                )

            q: "queue.Queue" = queue.Queue(maxsize=256)
            worker = threading.Thread(
                target=self._run_stream_drain,
                args=(client, model, az_messages, q, _stream_max),
                daemon=True,
            )
            worker.start()

            buffered: list[str] = []
            emitted_delta = False
            provider_failed_clean = False

            try:
                while True:
                    kind, payload = await asyncio.to_thread(q.get)
                    if kind is None:
                        break
                    if kind == "delta":
                        buffered.append(payload)
                        emitted_delta = True
                        yield {"type": "delta", "text": payload}
                    elif kind == "done":
                        total_tok, finish_reason = payload
                        duration = round((time.perf_counter() - t0) * 1000, 1)
                        text = "".join(buffered)
                        if not total_tok:
                            total_tok = max(1, len(text) // 4)
                        print(f"[STREAM DONE] provider={provider_name} | finish={finish_reason} | tokens={total_tok} | chars={len(text)}")
                        from services.layaastat import emit_llm_span
                        await emit_llm_span(
                            model=model,
                            provider_name=provider_name,
                            output_tokens=total_tok,
                            duration_ms=duration,
                            trace_id=session_id,
                        )
                        yield {"type": "done", "tokens": total_tok, "reason": finish_reason, "ok": True, "provider": provider_name, "model": model}
                        return  # success — stop here
                    elif kind == "error":
                        duration = round((time.perf_counter() - t0) * 1000, 1)
                        e = payload
                        error_code = str(getattr(e, "code", "") or "").lower()
                        error_name = e.__class__.__name__.lower()
                        print(f"[STREAM ERROR] provider={provider_name} | emitted_delta={emitted_delta} | is_last={is_last_provider} | {type(e).__name__} | code={error_code} | {str(e)[:400]}")

                        if emitted_delta or is_last_provider:
                            # Either we already committed output (can't switch) or
                            # this is the last provider — surface the error.
                            if not is_last_provider:
                                logger.error(
                                    "LLM stream error mid-stream (cannot fall back) | provider=%s | session=%s | class=%s | code=%s | msg=%.200s",
                                    provider_name, session_id, error_name, error_code, str(e),
                                )
                            else:
                                logger.error(
                                    "LLM stream error | provider=%s | session=%s | class=%s | code=%s | msg=%.200s",
                                    provider_name, session_id, error_name, error_code, str(e),
                                )
                            from services.layaastat import emit_llm_span
                            await emit_llm_span(
                                model=model,
                                provider_name=provider_name,
                                duration_ms=duration,
                                error_type=error_code or error_name or "stream_failed",
                                trace_id=session_id,
                            )
                            yield {
                                "type": "error",
                                "reason": error_code or error_name or "stream_failed",
                                "ok": False,
                                "text": "".join(buffered),
                                "provider": provider_name,
                                "model": model,
                            }
                            return
                        else:
                            # No output emitted yet → fall back to next provider.
                            logger.warning(
                                "LLM stream provider failed before any output, falling back | provider=%s | session=%s | error=%s: %.200s",
                                provider_name, session_id, error_name, str(e),
                            )
                            from services.layaastat import emit_llm_span
                            await emit_llm_span(
                                model=model,
                                provider_name=provider_name,
                                duration_ms=duration,
                                error_type=error_code or error_name or "stream_failed",
                                trace_id=session_id,
                            )
                            provider_failed_clean = True
                            break
            finally:
                pass  # daemon thread exits when stream closes/GCs

            if not provider_failed_clean:
                return  # completed (done or error already yielded)
            # provider_failed_clean=True → loop continues to next provider


llm_client = LLMClient()
