"""Glue between the chat turn (`routes/chat.py`) and the memory/skills services.

Keeps `routes/chat.py` thin: it calls three hooks, all gated to Owner/Principal
(Phase-1 self-learning scope, FR43) and all best-effort (never raise into a turn):

- `recall_context_block`  (G.3) — pre-LLM: a text block of relevant memories/skills
  to append to the system prompt.
- `handle_pre_turn`       (G.4/G.8) — inline `remember:`/`forget`, affirmative
  confirmation of a pending uncertain memory, and corrections.
- `finalize_turn`         (G.4/G.6) — auto-save durable info, distill a skill, and
  return an in-chat yes/no question for genuinely-uncertain items (no UI, FR32).

Pending uncertain memories ride on the conversation doc (`pending_memory`) so the
next turn's affirmative reply can confirm them — no new UI surface.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.actor_context import actor_ctx_from_user
from services.memory import is_memory_subject, skills_store
from services.memory import store as memory_store
from services.memory import extractor

logger = logging.getLogger(__name__)


def _ctx(user: dict):
    return actor_ctx_from_user(user, branch_id=user.get("branch_id"))


async def recall_context_block(db, user: dict, user_text: str) -> str:
    """Return a system-prompt block of recalled memories + skills (G.3). Empty str
    when nothing relevant, the user isn't a memory subject, or anything fails."""
    if not is_memory_subject(user) or not user_text:
        return ""
    try:
        ctx = _ctx(user)
        mems = await memory_store.recall(db, ctx, user_text)
        skills = await skills_store.recall_skills(db, ctx, user_text)
    except Exception as e:
        logger.warning("recall_context_block failed: %s", e)
        return ""
    if not mems and not skills:
        return ""

    lines: List[str] = ["\n\n## What you remember about this user"]
    for m in mems:
        lines.append(f"- ({m.get('category', 'fact')}) {m.get('text')}")
    if skills:
        lines.append("\n### Learned ways of working")
        for s in skills:
            steps = "; ".join(s.get("steps", [])[:5])
            lines.append(f"- {s.get('title')}: {steps}" if steps else f"- {s.get('title')}")
    lines.append(
        "\nUse this background naturally. If the user corrects something here, "
        "acknowledge it — it will be unlearned."
    )
    return "\n".join(lines)


async def handle_pre_turn(db, user: dict, user_text: str, conv: Optional[dict]) -> Optional[str]:
    """Handle explicit memory commands / confirmations BEFORE the LLM runs (G.4/G.8).

    Returns a short response string to short-circuit the turn (and skip the LLM), or
    None to let the turn proceed normally.
    """
    if not is_memory_subject(user) or not user_text:
        return None
    ctx = _ctx(user)
    try:
        # 1) Inline "remember: X"
        remember = extractor.parse_inline_remember(user_text)
        if remember:
            saved = await memory_store.add_memory(db, ctx, text=remember, source="user", confidence=0.95)
            return "Got it — I'll remember that." if saved else "I couldn't save that, please try rephrasing."

        # 2) Inline "forget X"
        forget = extractor.parse_inline_forget(user_text)
        if forget:
            res = await memory_store.correct_memory(db, ctx, match_text=forget)
            if res["removed"]:
                return "Done — I've forgotten that."
            return "I don't have anything matching that to forget."

        # 3) Affirmative reply confirming a pending uncertain memory
        pending = (conv or {}).get("pending_memory")
        if pending and extractor.is_affirmative(user_text):
            await memory_store.add_memory(
                db, ctx, text=pending.get("text", ""),
                category=pending.get("category", "fact"), source="user", confidence=0.9,
            )
            await _clear_pending(db, user, conv)
            return "Saved — I'll keep that in mind."

        # 4) Correction of an existing memory ("that's not right …")
        if extractor.looks_like_correction(user_text):
            # Remove the most lexically-related memory; the LLM turn then proceeds to
            # answer afresh. Conservative: only act if we actually match something.
            related = await memory_store.recall(db, ctx, user_text, k=1)
            if related:
                await memory_store.correct_memory(db, ctx, memory_id=related[0]["id"])
                # fall through (return None) so the assistant still answers the turn
    except Exception as e:
        logger.warning("handle_pre_turn failed: %s", e)

    # Any pending memory not confirmed by an affirmative is now stale — clear it so
    # it doesn't linger across unrelated turns.
    if conv and conv.get("pending_memory") and not extractor.is_affirmative(user_text):
        await _clear_pending(db, user, conv)
    return None


async def _clear_pending(db, user: dict, conv: Optional[dict]) -> None:
    if not conv:
        return
    try:
        from tenant import get_school_id, scoped_filter

        await db.conversations.update_one(
            scoped_filter({"id": conv.get("id"), "user_id": user["id"]}, get_school_id()),
            {"$set": {"pending_memory": None}},
        )
    except Exception:
        pass


async def _set_pending(db, user: dict, conv_id: str, item: Dict[str, Any]) -> None:
    try:
        from tenant import get_school_id, scoped_filter

        await db.conversations.update_one(
            scoped_filter({"id": conv_id, "user_id": user["id"]}, get_school_id()),
            {"$set": {"pending_memory": {
                "text": item.get("text"),
                "category": item.get("category", "fact"),
                "confidence": item.get("confidence"),
            }}},
        )
    except Exception as e:
        logger.warning("_set_pending failed: %s", e)


async def finalize_turn(
    db, user: dict, *, user_text: str, assistant_text: str, conv_id: str,
    history: List[Dict], round_count: int, tool_count: int,
) -> Optional[str]:
    """Post-LLM: auto-save durable info, distill a skill, ask about uncertain items.

    Returns an in-chat yes/no question string to append to the assistant's reply
    (None if nothing to ask). Best-effort; never raises.
    """
    if not is_memory_subject(user):
        return None
    ctx = _ctx(user)
    question: Optional[str] = None
    try:
        items = await extractor.extract_memory_items(user_text, assistant_text, session_id=conv_id)
        for it in items.get("autosave", []):
            await memory_store.add_memory(
                db, ctx, text=it["text"], category=it.get("category", "fact"),
                source="auto", confidence=it.get("confidence", 0.8),
            )
        uncertain = items.get("uncertain", [])
        if uncertain:
            top = uncertain[0]
            await _set_pending(db, user, conv_id, top)
            question = f"\n\nWould you like me to remember that {top['text']}? (yes/no)"
    except Exception as e:
        logger.warning("finalize_turn memory extraction failed: %s", e)

    # Skill distillation (G.6) — only for genuinely complex runs.
    try:
        skill = await extractor.extract_skill(
            history, round_count=round_count, tool_count=tool_count, session_id=conv_id
        )
        if skill:
            await skills_store.add_skill(
                db, ctx, title=skill["title"], problem=skill.get("problem", ""),
                solution=skill.get("solution", ""), steps=skill.get("steps", []),
                tags=skill.get("tags", []), source="learned",
                confidence=skill.get("confidence", 0.7),
            )
    except Exception as e:
        logger.warning("finalize_turn skill extraction failed: %s", e)

    return question
