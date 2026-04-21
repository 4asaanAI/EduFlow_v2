import os
import uuid
import asyncio
import logging
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        self.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        self.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.3-chat")
        self.api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

        if self.api_key and self.endpoint:
            self._client = AzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.endpoint,
                api_version=self.api_version,
            )
        else:
            self._client = None
            logger.warning("AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT not set")

    async def chat(self, system_prompt: str, messages: list, session_id: str = None) -> tuple:
        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"

        if not self._client:
            return "Azure OpenAI not configured. Please set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT.", 0

        az_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            role = msg.get("role", "user")
            # Azure OpenAI uses "assistant" not "model"
            if role == "model":
                role = "assistant"
            az_messages.append({"role": role, "content": msg.get("content", "")})

        def _call():
            response = self._client.chat.completions.create(
                model=self.deployment,
                messages=az_messages,
            )
            text = response.choices[0].message.content or ""
            tokens = 0
            try:
                tokens = (response.usage.prompt_tokens or 0) + (response.usage.completion_tokens or 0)
            except Exception:
                tokens = max(1, len(text) // 4)
            return text, tokens

        try:
            return await asyncio.to_thread(_call)
        except Exception as e:
            logger.error(f"Azure OpenAI error: {e}")
            return f"Error: {str(e)}", 0


llm_client = LLMClient()
