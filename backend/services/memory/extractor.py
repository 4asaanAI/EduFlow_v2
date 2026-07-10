"""LLM-driven extraction: memory auto-save (G.4) + skill distillation (G.6).

Cloned/adapted from Odysseus `memory_extractor.py` + `skill_extractor.py`, re-homed
onto EduFlow's `ai.llm_client`. Both are best-effort and must NEVER raise into the
chat turn — on any failure they return an empty result and the turn proceeds.

Importance policy (G.4): clearly-durable info is saved automatically (no prompt);
genuinely-uncertain items are returned as a yes/no question for the assistant to ask
*in chat* (FR32: never a UI control). Anything trivial/transient is dropped.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from ai.llm_client import llm_client

logger = logging.getLogger(__name__)

# ── Memory extraction (G.4) ──────────────────────────────────────────────────

_MEMORY_PROMPT = (
    "You analyze ONE turn of a school administrator's chat with an AI assistant and "
    "decide what — if anything — is worth durably remembering ABOUT THE ADMINISTRATOR "
    "(their preferences, recurring instructions, standing decisions, ongoing concerns, "
    "or how they like work done).\n\n"
    "Return STRICT JSON: an object with a single key \"items\", an array (possibly empty) "
    "of objects, each: {\"text\": short third-person fact, \"category\": one of "
    "fact|preference|contact|task|concern, \"confidence\": 0.0-1.0}.\n\n"
    "Rules:\n"
    "- Save durable, reusable facts about the administrator or their standing wishes.\n"
    "- DO NOT save transient operational data (a single attendance count, today's "
    "number), one-off question/answers, or anything about a specific child's health/"
    "religion/caste/medical/biometric data.\n"
    "- DO NOT include phone numbers, Aadhaar, emails, or addresses in the text.\n"
    "- confidence >= 0.75 means clearly worth saving; 0.4-0.75 means uncertain; "
    "below 0.4 means skip (don't include it).\n"
    "- If nothing is worth remembering, return {\"items\": []}.\n"
    "Return ONLY the JSON object, no markdown fences, no commentary."
)

AUTOSAVE_CONFIDENCE = 0.75   # >= → save silently
UNCERTAIN_FLOOR = 0.4        # [floor, autosave) → ask in chat; below → drop


def _parse_json_blob(response: str) -> Optional[Any]:
    if not response:
        return None
    text = response.strip()
    if text.lower() == "null":
        return None
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    # Slice to the outermost JSON object/array if surrounded by prose.
    if text and text[0] not in "{[":
        starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
        if starts:
            start = min(starts)
            end = max(text.rfind("}"), text.rfind("]"))
            if 0 <= start < end:
                text = text[start:end + 1]
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


async def _llm_json(system_prompt: str, user_content: str, session_id: str) -> Optional[Any]:
    try:
        result = await llm_client.chat(system_prompt, [{"role": "user", "content": user_content}], session_id)
        if not result.ok:  # R1.7: LLMResult, not tuple|dict
            return None
        return _parse_json_blob(result.text)
    except Exception as e:
        logger.warning("[memory-extract] LLM JSON call failed: %s", e)
        return None


async def extract_memory_items(user_text: str, assistant_text: str, *, session_id: str = "mem") -> Dict[str, List[Dict]]:
    """Return {'autosave': [...], 'uncertain': [...]} for one chat turn (G.4).

    Items are {text, category, confidence}; autosave >= AUTOSAVE_CONFIDENCE,
    uncertain in [UNCERTAIN_FLOOR, AUTOSAVE_CONFIDENCE). Never raises.
    """
    empty = {"autosave": [], "uncertain": []}
    if not user_text or not user_text.strip():
        return empty
    convo = f"[administrator] {user_text}\n[assistant] {assistant_text or ''}"
    data = await _llm_json(_MEMORY_PROMPT, f"Turn:\n{convo}", session_id)
    if not isinstance(data, dict):
        return empty
    items = data.get("items")
    if not isinstance(items, list):
        return empty

    autosave, uncertain = [], []
    for it in items:
        if not isinstance(it, dict):
            continue
        text = (it.get("text") or "").strip()
        if not text:
            continue
        try:
            conf = float(it.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        category = (it.get("category") or "fact").strip().lower()
        entry = {"text": text, "category": category, "confidence": conf}
        if conf >= AUTOSAVE_CONFIDENCE:
            autosave.append(entry)
        elif conf >= UNCERTAIN_FLOOR:
            uncertain.append(entry)
    return {"autosave": autosave, "uncertain": uncertain}


# ── Inline command (Odysseus parity): "remember: X" ──────────────────────────

# R6.1 (X3): inline memory SAVE requires an EXPLICIT memory cue. Bare imperatives
# — "save …", "note …", "store …" — are NOT memory commands; they belong to the
# normal tool/LLM pipeline (e.g. "note attendance for class 5", "save the draft").
# Only an explicit remember/memorize verb, or an explicit "note/make a note … to
# self / a note" phrasing, saves a memory.
_INLINE_RE = re.compile(r"^(?:remember|memorize|memorise)\b[:\-]?\s+(?:that\s+)?(.+)$", re.IGNORECASE)
_INLINE_NOTE_RE = re.compile(
    r"^(?:"
    # Explicit note-noun / to-self phrasings — self-evidently a memory save.
    r"(?:note to self|make a note|take a note|save a note)(?:\s+(?:that|to|about|of))?"
    # Bare "jot down"/"note down" are ambiguous with operational commands
    # ("note down attendance for class 5", "jot down the marks"): only treat
    # them as a memory save when a memory connector (that/about) follows, so
    # domain imperatives fall through to the tool/LLM pipeline (X3).
    r"|(?:jot down|note down)\s+(?:that|about)"
    r")[:\-]?\s+(.+)$",
    re.IGNORECASE,
)
# R6.1 (X3): inline FORGET requires an explicit memory-note cue. Bare "delete …"
# / "remove …" are NOT memory commands ("delete student Rahul", "remove fee record
# for …") and must fall through to the tool/LLM pipeline. "forget <domain thing>"
# without a note cue also falls through.
_FORGET_RE = re.compile(
    r"^forget\s+(?:"
    r"(?:the|that|my)\s+(?:note|memory|memories)(?:\s+(?:about|that|regarding))?"
    r"|what\s+i\s+(?:told|said)(?:\s+you)?(?:\s+about)?"
    r"|that\s+i\b"
    r")\s*(.*)$",
    re.IGNORECASE,
)
# Affirmative replies that confirm a pending uncertain memory. Anchored as a
# FULL-MESSAGE match (only trailing courtesy words/punctuation allowed) so a real
# request that merely starts with "ok" — e.g. "ok show me the fees" — is NOT
# mistaken for a bare confirmation and does not swallow the user's actual ask.
_AFFIRM_RE = re.compile(
    r"^\s*(yes|yeah|yep|sure|ok|okay|please do|go ahead|save it|remember it|do it)"
    r"[\s,.!]*(please)?[\s,.!]*$",
    re.IGNORECASE,
)
# Correction openers (G.8). Deliberately CONSERVATIVE and anchored to the START of
# the message: only explicit "that's wrong / not right / no that's not" phrasings.
# A bare mid-sentence "actually" is intentionally excluded — it is far too common
# in normal requests and would otherwise silently delete a relevant memory.
_CORRECT_RE = re.compile(
    r"^\s*(no[,\s]+)?(that'?s|that is|that was|thats)\s+(not right|wrong|not correct|incorrect|not true)\b",
    re.IGNORECASE,
)


def parse_inline_remember(message: str) -> Optional[str]:
    if not message:
        return None
    stripped = message.strip()
    m = _INLINE_RE.match(stripped) or _INLINE_NOTE_RE.match(stripped)
    return m.group(1).strip() if m else None


def parse_inline_forget(message: str) -> Optional[str]:
    if not message:
        return None
    m = _FORGET_RE.match(message.strip())
    if not m:
        return None
    # The cue itself ("forget the note about …") is enough to enter the forget
    # flow; the captured tail narrows WHICH note (may be empty → list all).
    return m.group(1).strip()


def is_affirmative(message: str) -> bool:
    return bool(message and _AFFIRM_RE.match(message.strip()))


def looks_like_correction(message: str) -> bool:
    return bool(message and _CORRECT_RE.search(message))


# ── Skill extraction (G.6) ────────────────────────────────────────────────────

_SKILL_PROMPT = (
    "You are analyzing an AI school-assistant work session. The assistant took {rounds} "
    "rounds and {tool_count} tool calls to complete the task.\n\n"
    "Extract a reusable 'skill' ONLY IF the session contains a concrete, repeatable "
    "procedure for completing a similar school-administration task next time (a sequence "
    "of tool calls / steps).\n\n"
    "Return the bare word null when the session is NOT a reusable procedure (one-off, "
    "pure Q&A, the assistant failed, or it's about one specific child/date).\n\n"
    "When a genuine reusable procedure exists, return STRICT JSON with: \"title\" (under "
    "10 words), \"problem\" (1-2 sentences), \"solution\" (1-2 sentences), \"steps\" "
    "(3-7 short steps), \"tags\" (3-5 keywords), \"confidence\" (0.0-1.0).\n"
    "Be conservative: if in doubt, return null. Return ONLY JSON or the bare word null."
)

_SKILL_CONTEXT_WINDOW = 12


async def extract_skill(
    history: List[Dict], *, round_count: int, tool_count: int, session_id: str = "skill",
) -> Optional[Dict]:
    """Distill a reusable skill from a complex run (>=2 rounds OR >=2 tools). Never raises."""
    if round_count < 2 and tool_count < 2:
        return None
    recent = (history or [])[-_SKILL_CONTEXT_WINDOW:]
    if not recent:
        return None
    lines = []
    for msg in recent:
        role = msg.get("role", "?")
        content = msg.get("content", "") or ""
        if not isinstance(content, str):
            continue
        if len(content) > 500:
            content = content[:500] + "..."
        lines.append(f"[{role}] {content}")
    if not lines:
        return None
    prompt = _SKILL_PROMPT.format(rounds=round_count, tool_count=tool_count)
    data = await _llm_json(prompt, "Conversation:\n" + "\n".join(lines), session_id)
    if not isinstance(data, dict):
        return None
    title = (data.get("title") or "").strip()
    if not title:
        return None
    try:
        conf = float(data.get("confidence", 0.7))
    except (TypeError, ValueError):
        conf = 0.7
    return {
        "title": title,
        "problem": data.get("problem", ""),
        "solution": data.get("solution", ""),
        "steps": data.get("steps", []) if isinstance(data.get("steps"), list) else [],
        "tags": data.get("tags", []) if isinstance(data.get("tags"), list) else [],
        "confidence": conf,
    }
