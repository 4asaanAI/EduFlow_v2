from __future__ import annotations

import os
import uuid
import asyncio
import logging
import time
from dataclasses import dataclass

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
class LLMResult:
    """Single return type for LLMClient.chat() (R1.7).

    Kills the old tuple|dict dual return that caused audit X1 (a tuple/dict was
    persisted as question-paper content). Callers read `.text`/`.tokens` and
    branch on `.ok` — never isinstance/tuple/dict gymnastics.
    """
    text: str
    tokens: int = 0
    ok: bool = True
    reason: str | None = None


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
    non-development environment with no Azure key or endpoint is a
    misconfiguration that would otherwise surface only as silent AI degradation,
    so we raise here and refuse to boot.
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
            "Azure OpenAI configuration is required outside development. Missing: "
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
            # Endpoint already includes /openai/v1 path (Azure AI Foundry style)
            # Use standard OpenAI client with base_url to avoid doubled path
            base_url = self.endpoint.rstrip("/")
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=base_url,
            )
        else:
            self._client = None
            logger.warning("Azure OpenAI client not configured")

    async def chat(
        self,
        system_prompt: str,
        messages: list,
        session_id: str = None,
        role: str = None,
    ) -> LLMResult:
        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"

        if not self._client:
            return ai_unavailable_result("not_configured")

        az_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            msg_role = msg.get("role", "user")
            if msg_role == "model":
                msg_role = "assistant"
            content = msg.get("content", "")
            # content may be a str (text-only) or a list (multimodal with image)
            az_messages.append({"role": msg_role, "content": content})

        def _call(max_tokens: int):
            logger.debug(
                "Azure LLM call | session=%s | deployment=%s | messages=%d | max_tokens=%d",
                session_id, self.deployment, len(az_messages), max_tokens,
            )
            # Part 2 Patch P5: hard per-call timeout. The OpenAI SDK's
            # synchronous client default is ~600s which is far too long for
            # an SSE handler; long stalls leak workers and Azure tokens.
            response = self._client.chat.completions.create(
                model=self.deployment,
                messages=az_messages,
                timeout=45,
                max_completion_tokens=max_tokens,
            )
            choice = response.choices[0]
            text = choice.message.content or ""
            finish_reason = getattr(choice, "finish_reason", None)
            input_tok = output_tok = 0
            try:
                input_tok = response.usage.prompt_tokens or 0
                output_tok = response.usage.completion_tokens or 0
            except Exception:
                output_tok = max(1, len(text) // 4)
            logger.debug(
                "Azure LLM done | session=%s | tokens=%d | finish=%s",
                session_id, input_tok + output_tok, finish_reason,
            )
            return text, input_tok + output_tok, input_tok, output_tok, finish_reason

        t0 = time.perf_counter()
        try:
            text, tokens, input_tok, output_tok, finish_reason = await asyncio.to_thread(
                _call, DEFAULT_MAX_COMPLETION_TOKENS
            )
            # R1.6 AC1: an empty reply truncated by the token ceiling ("length")
            # is almost always the reasoning family exhausting budget before any
            # visible content. Retry ONCE with more headroom.
            if not text.strip() and finish_reason == "length":
                logger.warning(
                    "Azure LLM empty content, finish_reason=length; retrying with headroom | session=%s",
                    session_id,
                )
                r_text, r_tokens, r_in, r_out, finish_reason = await asyncio.to_thread(
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
            # R1.6 AC3: empty content (even after retry) is a typed FAILURE, never
            # a "successful" empty string — the turn contract (R1.3) surfaces a
            # fallback instead of a silent blank.
            if not text.strip():
                return LLMResult(text="", tokens=tokens, ok=False, reason=f"empty_{finish_reason or 'unknown'}")
            return LLMResult(text=text, tokens=tokens, ok=True, reason=finish_reason)
        except Exception as e:
            duration = round((time.perf_counter() - t0) * 1000, 1)
            error_str = str(e).lower()
            error_name = e.__class__.__name__.lower()
            error_code = str(getattr(e, 'code', '') or '').lower()
            logger.error(
                "Azure OpenAI error | class=%s | code=%s | msg=%.300s",
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


llm_client = LLMClient()
