from __future__ import annotations

import os
import uuid
import asyncio
import logging
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

    async def chat(self, system_prompt: str, messages: list, session_id: str = None) -> tuple:
        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"

        if not self._client:
            return ai_unavailable_result("not_configured")

        az_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            role = msg.get("role", "user")
            if role == "model":
                role = "assistant"
            az_messages.append({"role": role, "content": msg.get("content", "")})

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
            )
            text = response.choices[0].message.content or ""
            tokens = 0
            try:
                tokens = (response.usage.prompt_tokens or 0) + (response.usage.completion_tokens or 0)
            except Exception:
                tokens = max(1, len(text) // 4)
            logger.debug("Azure LLM done | session=%s | tokens=%d", session_id, tokens)
            return text, tokens

        try:
            return await asyncio.to_thread(_call)
        except Exception as e:
            error_str = str(e).lower()
            error_name = e.__class__.__name__.lower()

            # Azure content policy block (HTTP 400) — return a helpful canned message
            # instead of "AI unavailable" so the user knows what happened
            if "400" in str(e) or "content_filter" in error_str or "content management policy" in error_str or "badrequesterror" in error_name:
                logger.warning(f"Azure content filter triggered: {e}")
                return (
                    "I wasn't able to process that specific phrasing due to content policy settings on the AI service. "
                    "Could you try rephrasing your question? For example, instead of mentioning specific complaint categories, "
                    "try asking about 'open issues', 'pending cases', or 'unresolved grievances'. "
                    "All your school management tools in the sidebar are fully available.",
                    0,
                )

            if "timeout" in error_name or "connection" in error_name:
                logger.warning(f"Azure OpenAI unavailable: {e}")
                return ai_unavailable_result(error_name)

            logger.error(f"Azure OpenAI error: {e}")
            return ai_unavailable_result(error_name or "request_failed")


llm_client = LLMClient()
