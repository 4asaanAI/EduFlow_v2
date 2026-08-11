"""Understand a photograph - the paid fallback, used only when reading it was not enough.

UI Sweep Epic 10, Story 10.6. Abhimanyu, 2026-07-22: "fall back to the service you
already pay for only when someone needs a photo genuinely understood."

READ THIS BEFORE CHANGING ANY OF IT.

**OCR runs first and this does not.** `services/ocr_service.py` reads printed pages on
this server for nothing, and the image never leaves the machine. That covers most of
what a school photographs: fee slips, admission forms, circulars, mark sheets. This
module exists for the remainder - a handwritten note, or "what is happening in this
picture" - and it is a FALLBACK, never a parallel attempt. A page whose text was read
successfully must never reach here.

**It adds no new service.** The platform already runs entirely on Azure OpenAI; this
uses the SAME deployment Flo talks through (`AZURE_OPENAI_DEPLOYMENT`). There is no new
subscription, no new resource and no standing charge - an image simply costs tokens
like text does. That correction is recorded in D-26, because "don't link us to Azure"
was said when the platform was already, entirely, on Azure.

**It may not work, and must say so.** The chat deployment may not accept images. When
it refuses one, that is reported as "this server cannot look at pictures yet" - never
as an empty description, and never as an invented one.

**Proven working 2026-08-06, and the defect that hid until then.** The live deployment
(`gpt-5.6-luna`) reads images correctly, verified against the real endpoint on both a
trivial image and a dense, text-heavy screenshot it transcribed accurately. Until that
date NO photograph could ever be read, because this module sent `max_tokens` while the
model family requires `max_completion_tokens` - an HTTP 400 on every single call. It
stayed hidden because the error landed in the generic `except` below and was reported to
staff as "the picture could not be examined", which reads like a problem with the photo.
The screen then advised re-saving the image, so people re-exported files that were never
at fault. Two lessons are now pinned in `tests/backend/unit/test_vision_service.py`:
assert the OUTGOING REQUEST SHAPE, because every other image test mocks this function
out entirely; and never let a fault of ours be worded as a fault of the user's input.
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# An image costs tokens. This is a description, not an essay - but length is bounded
# by the PROMPT ("factually and briefly"), not by a tight ceiling. The ceiling only has
# to be high enough that hidden reasoning can never consume the whole budget and leave
# no visible answer; llm_client.py learned that the hard way (R1.6 AC2) and sits at
# 4000 for the same reason. Billing is on tokens actually emitted - a real description
# measured 14 - so headroom here is close to free, whereas too little of it produces an
# empty reply that reads as "this page is blank".
MAX_DESCRIPTION_TOKENS = 2000
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
    chat - the shape every current vision-capable model accepts.
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
            # MUST be max_completion_tokens, NOT max_tokens. The current model family
            # rejects `max_tokens` outright with HTTP 400 `unsupported_parameter`, and
            # because that lands in the exception handler below it surfaced to the
            # school as "the picture could not be examined" - so every photo anyone
            # sent Flo failed, while the screen advised re-saving the image, which
            # could never have helped. `llm_client.py` has always sent
            # `max_completion_tokens`; this module was written against the older name
            # and no test ever exercised the real request shape. See
            # tests/backend/unit/test_vision_service.py, which now pins it.
            max_completion_tokens=MAX_DESCRIPTION_TOKENS,
            timeout=VISION_TIMEOUT_SECONDS,
        )
        choice = response.choices[0]
        text = (choice.message.content or "").strip()
        if not text:
            # An empty reply has two very different causes and they must not be
            # reported the same way. Hidden reasoning eating the whole budget is our
            # ceiling being too low; saying "nothing could be made out" there would
            # blame the photograph for our own setting (the Epic 4 defect class: a
            # failure that reads as a finding).
            if getattr(choice, "finish_reason", None) == "length":
                logger.error(
                    "vision: budget exhausted before any description was written "
                    "(finish_reason=length, ceiling=%d) - raise MAX_DESCRIPTION_TOKENS",
                    MAX_DESCRIPTION_TOKENS,
                )
                return VisionResult(
                    available=True,
                    reason="The picture could not be described within the allowed length.",
                )
            return VisionResult(available=True, reason="Nothing could be made out in that picture.")
        return VisionResult(description=text, available=True)

    except Exception as exc:
        detail = str(exc).lower()

        # OUR fault, not the picture's, and permanent until someone changes the code.
        # This branch exists because the `max_tokens` bug hid here for weeks: a 400
        # `unsupported_parameter` fell through to the generic message below, which says
        # "just now" and prompted the screen to advise re-saving the image. Staff
        # re-saved photographs that were never the problem. A malformed request must
        # therefore be LOUD in the log and must never send anyone on that errand.
        if "unsupported_parameter" in detail or "unsupported parameter" in detail or (
            "invalid_request_error" in detail and "max_tokens" in detail
        ):
            logger.error(
                "vision: the request shape is wrong and NO image can succeed until it "
                "is fixed - this is a code defect, not a bad photograph | %s", exc,
            )
            return VisionResult(
                available=False,
                reason="Picture reading is misconfigured on this server. Re-uploading will not help; this needs a fix.",
            )

        # A deployment that genuinely cannot take images lands here. Report the
        # limitation plainly - an invented description would be far worse than an
        # admission. Note "content" was deliberately REMOVED from this list: it also
        # matches content-filter and content-policy errors, which are not
        # "this model is text-only" and were being mislabelled as such.
        if "image" in detail or "multimodal" in detail or "vision" in detail:
            logger.warning("vision: deployment rejected an image | %s", exc)
            return VisionResult(
                available=False,
                reason="This server cannot look at pictures yet - its AI model only accepts text.",
            )
        # Error opacity (P3): the caller never sees the exception text.
        logger.exception("vision: request failed")
        return VisionResult(available=True, reason="The picture could not be examined just now.")
