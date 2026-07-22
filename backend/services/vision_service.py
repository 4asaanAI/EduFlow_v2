"""Understand a photograph — the paid fallback, used only when reading it was not enough.

UI Sweep Epic 10, Story 10.6. Abhimanyu, 2026-07-22: "fall back to the service you
already pay for only when someone needs a photo genuinely understood."

READ THIS BEFORE CHANGING ANY OF IT.

**OCR runs first and this does not.** `services/ocr_service.py` reads printed pages on
this server for nothing, and the image never leaves the machine. That covers most of
what a school photographs: fee slips, admission forms, circulars, mark sheets. This
module exists for the remainder — a handwritten note, or "what is happening in this
picture" — and it is a FALLBACK, never a parallel attempt. A page whose text was read
successfully must never reach here.

**It adds no new service.** The platform already runs entirely on Azure OpenAI; this
uses the SAME deployment Flo talks through (`AZURE_OPENAI_DEPLOYMENT`). There is no new
subscription, no new resource and no standing charge — an image simply costs tokens
like text does. That correction is recorded in D-26, because "don't link us to Azure"
was said when the platform was already, entirely, on Azure.

**It may not work, and must say so.** The chat deployment may not accept images. When
it refuses one, that is reported as "this server cannot look at pictures yet" — never
as an empty description, and never as an invented one.
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# An image costs tokens. This is a description, not an essay.
MAX_DESCRIPTION_TOKENS = 400
VISION_TIMEOUT_SECONDS = 45

_DEFAULT_QUESTION = (
    "Describe what this image shows, factually and briefly. If it contains readable "
    "text, quote it. If you cannot tell what something is, say so rather than guessing."
)


@dataclass
class VisionResult:
    description: str = ""
    available: bool = True
    reason: str = ""

    @property
    def understood(self) -> bool:
        return bool(self.description.strip())


def vision_available() -> tuple:
    """Is the paid fallback usable at all? (available, reason)"""
    from ai.llm_client import get_azure_key

    if not get_azure_key() or not os.environ.get("AZURE_OPENAI_ENDPOINT"):
        return False, "This server is not connected to the AI service, so it cannot look at pictures."
    return True, ""


def describe_image(
    data: bytes,
    mime_type: str,
    *,
    question: Optional[str] = None,
) -> VisionResult:
    """Ask the model what a picture shows. Never raises.

    The image is sent inline as a base64 data URI on the same deployment used for
    chat — the shape every current vision-capable model accepts.
    """
    available, why = vision_available()
    if not available:
        return VisionResult(available=False, reason=why)

    try:
        from ai.llm_client import LLMClient

        client = LLMClient()
        if not client._client:
            return VisionResult(
                available=False,
                reason="This server is not connected to the AI service, so it cannot look at pictures.",
            )

        b64 = base64.b64encode(data).decode()
        response = client._client.chat.completions.create(
            model=client.deployment,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": question or _DEFAULT_QUESTION},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                ],
            }],
            max_tokens=MAX_DESCRIPTION_TOKENS,
            timeout=VISION_TIMEOUT_SECONDS,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            return VisionResult(available=True, reason="Nothing could be made out in that picture.")
        return VisionResult(description=text, available=True)

    except Exception as exc:
        # A deployment that cannot take images lands here. Report the limitation
        # plainly — an invented description would be far worse than an admission.
        detail = str(exc).lower()
        if "image" in detail or "content" in detail or "multimodal" in detail or "vision" in detail:
            logger.warning("vision: deployment rejected an image | %s", exc)
            return VisionResult(
                available=False,
                reason="This server cannot look at pictures yet — its AI model only accepts text.",
            )
        # Error opacity (P3): the caller never sees the exception text.
        logger.exception("vision: request failed")
        return VisionResult(available=True, reason="The picture could not be examined just now.")
