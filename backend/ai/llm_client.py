from __future__ import annotations

import os
import uuid
import asyncio
import logging
import time
from typing import Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


def ai_unavailable_result(reason: str) -> dict[str, Any]:
    return {
        "type": "ai_unavailable",
        "degraded": True,
        "message": "AI is temporarily unavailable. Core school tools remain available.",
        "reason": reason,
        "tokens": 0,
    }


class LLMClient:
    def __init__(self):
        self.api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
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
    ) -> tuple:
        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"

        if not self._client:
            return ai_unavailable_result("not_configured")

        az_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            msg_role = msg.get("role", "user")
            if msg_role == "model":
                msg_role = "assistant"
            az_messages.append({"role": msg_role, "content": msg.get("content", "")})

        def _call():
            logger.debug(
                "Azure LLM call | session=%s | deployment=%s | messages=%d",
                session_id, self.deployment, len(az_messages),
            )
            # Part 2 Patch P5: hard per-call timeout. The OpenAI SDK's
            # synchronous client default is ~600s which is far too long for
            # an SSE handler; long stalls leak workers and Azure tokens.
            response = self._client.chat.completions.create(
                model=self.deployment,
                messages=az_messages,
                timeout=45,
                max_completion_tokens=1200,
            )
            text = response.choices[0].message.content or ""
            input_tok = output_tok = 0
            try:
                input_tok = response.usage.prompt_tokens or 0
                output_tok = response.usage.completion_tokens or 0
            except Exception:
                output_tok = max(1, len(text) // 4)
            logger.debug("Azure LLM done | session=%s | tokens=%d", session_id, input_tok + output_tok)
            return text, input_tok + output_tok, input_tok, output_tok

        t0 = time.perf_counter()
        try:
            text, tokens, input_tok, output_tok = await asyncio.to_thread(_call)
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
            return text, tokens
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
