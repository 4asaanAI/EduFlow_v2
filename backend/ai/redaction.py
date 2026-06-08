"""PII minimization for the LLM + trace/audit layer (Stories F.1 / F.2, FR19-23).

DPDP posture: send the model (and persist to traces) the MINIMUM personal data
necessary. Children's special-category fields — date of birth, contact numbers,
health/medical records, full home address, government IDs (Aadhaar), and secrets
— are never shipped to Azure OpenAI nor written to chat traces. Identifiers and
references (ids, admission numbers, names used for addressing) are sent instead.

`redact_for_llm()` is THE canonical redactor; `routes/chat.py:_safe_tool_result_for_chat`
delegates to it so the SAME masking applies at (a) the outbound LLM payload and
(b) trace persistence. `contains_unredacted_pii()` is the scanner the F.2 test
uses to assert persisted traces/audit hold zero unredacted special-category PII.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[restricted in chat]"

# Exact key names that carry special-category / secret data — fully masked.
_RESTRICTED_EXACT = {
    "address",
    "home_address",
    "permanent_address",
    "correspondence_address",
    "date_of_birth",
    "dob",
    "aadhaar",
    "aadhaar_number",
    "aadhar",
    "aadhar_number",
    "father_aadhaar",
    "mother_aadhaar",
    "guardian_aadhaar",
    "blood_group",
    "religion",
    "caste",
    "social_category",
    "disability",
    "disability_status",
    "medical_record",
    "medical_records",
    "medical_history",
    "medical_conditions",
    "health_record",
    "health_records",
    "health_status",
    "health_info",
    "health_notes",
    "allergies",
    "password",
    "password_hash",
    "salt",
    "secret",
    "api_key",
    "private_key",
    "refresh_token",
    "access_token",
    "session_token",
    "webhook_secret",
}

# Substring markers — any key containing one of these is masked (covers nested/
# prefixed variants like `student_medical_notes`). Deliberately NARROW so we don't
# over-block non-PII keys (e.g. bare "health" would catch `system_health` — the
# IT-tech dashboard read; health PII is covered by the exact keys above instead).
_RESTRICTED_SUBSTRINGS = ("medical", "aadhaar", "aadhar", "disabilit")


def _is_phone_field(key_lower: str) -> bool:
    return (
        key_lower in ("phone", "mobile", "phone_number", "mobile_number")
        or key_lower.endswith(("_phone", "_mobile"))
        or key_lower.startswith(("phone_", "mobile_"))
    )


def _mask_phone(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "XX"
    return f"{digits[:2]}XX-XXX-{digits[-3:]}"


def redact_for_llm(value: Any) -> Any:
    """Recursively redact special-category / secret fields from a tool result.

    - Restricted keys → `[restricted in chat]`.
    - Phone/contact keys → masked (last 3 digits kept for human reference).
    - Everything else (ids, names, counts, statuses, amounts strictly needed for
      the task) passes through so the model can still do its job.
    """
    if isinstance(value, list):
        return [redact_for_llm(item) for item in value]
    if not isinstance(value, dict):
        return value

    safe: dict[str, Any] = {}
    for key, raw in value.items():
        key_lower = str(key).lower()
        if key_lower in _RESTRICTED_EXACT or any(s in key_lower for s in _RESTRICTED_SUBSTRINGS):
            safe[key] = REDACTED
        elif _is_phone_field(key_lower) or "contact" in key_lower:
            if isinstance(raw, str):
                safe[key] = _mask_phone(raw)
            elif isinstance(raw, (dict, list)):
                safe[key] = redact_for_llm(raw)
            else:
                safe[key] = REDACTED
        else:
            safe[key] = redact_for_llm(raw)
    return safe


# A loose 12-digit Aadhaar matcher + a 10-digit Indian phone matcher, used by the
# trace scanner to catch raw PII that slipped past key-based redaction.
_AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
_RAW_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\-\s]?)?[6-9]\d{9}(?!\d)")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def redact_text_for_memory(text: str) -> str:
    """Scrub raw special-category / contact PII from a FREE-TEXT memory before it
    is persisted (Story G.2, FR34/DPDP).

    `redact_for_llm()` masks STRUCTURED tool results by key name; a learned memory
    is a single free-text string, so key-based masking can't apply. This scrubs the
    two raw-PII shapes the trace scanner flags (Aadhaar-shaped 12-digit groups and
    10-digit Indian phone numbers) plus emails — surgically, so the memory keeps its
    useful, non-special-category content (names, amounts, intents). Calibration note
    (DPDP guardrails): deliberately NARROW — never blanket-redact the text into
    uselessness, only the raw identifiers.
    """
    if not isinstance(text, str) or not text:
        return text
    out = _AADHAAR_RE.sub(REDACTED, text)
    out = _RAW_PHONE_RE.sub(REDACTED, out)
    out = _EMAIL_RE.sub(REDACTED, out)
    return out


def contains_unredacted_pii(text: str) -> list[str]:
    """Return a list of unredacted-PII matches found in `text` (empty = clean).

    Used by the F.2 regression scan over persisted chat traces + audit logs. It
    flags raw Aadhaar-shaped and raw 10-digit-phone-shaped substrings; a masked
    phone (`98XX-XXX-210`) does not match because it contains `X`.
    """
    found: list[str] = []
    if not isinstance(text, str):
        return found
    found.extend(_AADHAAR_RE.findall(text))
    found.extend(_RAW_PHONE_RE.findall(text))
    return found
