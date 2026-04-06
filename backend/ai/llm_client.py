import os
import uuid
import asyncio
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model_name = os.environ.get("LLM_MODEL", "gemini-2.5-flash-preview-04-17")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        else:
            logger.warning("GEMINI_API_KEY not set")

    async def chat(self, system_prompt: str, messages: list, session_id: str = None) -> str:
        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"

        if not self.api_key:
            return "LLM not configured. Please set GEMINI_API_KEY environment variable."

        history = []
        for msg in messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [msg["content"]]})

        last_msg = messages[-1]["content"] if messages else ""

        def _call():
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
            )
            chat = model.start_chat(history=history)
            response = chat.send_message(last_msg)
            tokens = 0
            try:
                usage = response.usage_metadata
                tokens = (usage.prompt_token_count or 0) + (usage.candidates_token_count or 0)
            except Exception:
                tokens = max(1, len(response.text) // 4)
            return response.text, tokens

        try:
            return await asyncio.to_thread(_call)
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return f"Error: {str(e)}", 0


llm_client = LLMClient()
