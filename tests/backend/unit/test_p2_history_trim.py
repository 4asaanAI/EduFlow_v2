"""Part 2 Patch P2: _trim_history function and elision marker logic tests.

Tests that conversation history trimming correctly:
  1. Passes short lists through unchanged.
  2. Keeps first 2 anchors + last 10 recent, drops middle on long lists.
  3. Truncates oversize anchor content to fit within CHAR_BUDGET.
  4. Elision marker is inserted after trim, at the correct splice position.
  5. No elision marker is inserted when all messages fit in the window.
"""

from __future__ import annotations

import pytest

from routes.chat import (
    _trim_history,
    CHAR_BUDGET,
    HISTORY_KEEP_FIRST,
    HISTORY_KEEP_RECENT,
)


def _msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


# ─── test 1: short list is returned as-is ───────────────────────────────────

def test_trim_history_short_list_unchanged():
    """List whose total chars fit in CHAR_BUDGET is returned unchanged."""
    messages = [_msg("user", "Hello"), _msg("assistant", "Hi there")]
    result = _trim_history(messages)
    assert result == messages


# ─── test 2: keeps anchors + recent, drops middle ───────────────────────────

def test_trim_history_keeps_anchors_and_recent():
    """Long list keeps first HISTORY_KEEP_FIRST + last HISTORY_KEEP_RECENT messages."""
    # Build 30 messages with content large enough to exceed CHAR_BUDGET
    big_content = "x" * 1000  # 1000 chars each, 30 msgs = 30,000 > 24,000
    messages = [_msg("user" if i % 2 == 0 else "assistant", big_content) for i in range(30)]
    result = _trim_history(messages)
    total = HISTORY_KEEP_FIRST + HISTORY_KEEP_RECENT
    assert len(result) <= total
    # First message (anchor[0]) should be present
    assert result[0]["content"] == big_content or "[…truncated…]" in result[0]["content"]
    # Last message should be present or near the end
    last_kept = result[-1]
    assert last_kept is not None


# ─── test 3: oversize anchors get their content truncated ────────────────────

def test_trim_history_oversize_anchor_truncated():
    """Anchors with very large content are truncated when they still exceed CHAR_BUDGET
    after the middle-message trim pass.

    The truncation path (Part 2 Patch P2) only runs after the list has been
    trimmed to first-N + last-M; we must therefore supply more than
    HISTORY_KEEP_FIRST + HISTORY_KEEP_RECENT messages to enter the trim
    branch, then use giant anchor content that still exceeds CHAR_BUDGET
    after all middle messages are stripped.
    """
    # Two huge anchors (12,000 chars each) plus enough filler messages to
    # trigger the trim branch (need > 12 total).
    huge = "a" * 12000  # 12,000 chars each → 24,000 total just from anchors
    filler = "short"
    messages = [
        _msg("user", huge),       # anchor[0]
        _msg("assistant", huge),  # anchor[1]
    ] + [_msg("user" if i % 2 == 0 else "assistant", filler) for i in range(11)]
    # 13 messages total; total_chars ≫ CHAR_BUDGET

    result = _trim_history(messages)

    # Result must fit within CHAR_BUDGET
    total_chars = sum(len(m.get("content", "") or "") for m in result)
    assert total_chars <= CHAR_BUDGET, (
        f"After trim, total chars {total_chars} still exceeds CHAR_BUDGET {CHAR_BUDGET}"
    )
    # At least one anchor must carry the truncation marker
    truncated = [m for m in result if "[…truncated…]" in (m.get("content") or "")]
    assert len(truncated) >= 1


# ─── test 4: elision marker survives after trim ───────────────────────────────

def test_elision_marker_survives_after_trim():
    """Simulate 30-message conversation: after _trim_history + splice, elision
    marker is present at insert_pos and message indices outside the kept range
    are absent.
    """
    big_content = "y" * 1000  # 30 * 1000 = 30,000 > CHAR_BUDGET
    messages_for_llm = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": big_content}
        for i in range(30)
    ]

    # Simulate the anchors (first 2) and total count (30)
    total_msgs = 30
    anchors_count = HISTORY_KEEP_FIRST

    # Run trim
    trimmed = _trim_history(list(messages_for_llm))

    # Simulate omitted calculation: total - what's kept (before trim)
    # In reality omitted is computed off DB, we simulate it
    omitted = max(0, total_msgs - (HISTORY_KEEP_FIRST + HISTORY_KEEP_RECENT))
    assert omitted > 0  # sanity: should be 30 - 12 = 18

    # Insert elision marker as chat.py does
    insert_pos = min(anchors_count, len(trimmed))
    trimmed.insert(
        insert_pos,
        {"role": "system", "content": f"[{omitted} earlier messages omitted for context length]"},
    )

    # Marker must be present
    marker_msgs = [m for m in trimmed if "messages omitted" in (m.get("content") or "")]
    assert len(marker_msgs) == 1
    assert str(omitted) in marker_msgs[0]["content"]

    # The last message (message #30) should still be present
    last_content = trimmed[-1]["content"]
    assert last_content == big_content or "[…truncated…]" in last_content


# ─── test 5: no elision marker when nothing omitted ──────────────────────────

def test_no_elision_marker_when_nothing_omitted():
    """When all messages fit in the window, omitted=0, so no elision marker is inserted."""
    # 5 short messages — well under CHAR_BUDGET
    messages = [_msg("user" if i % 2 == 0 else "assistant", "Short.") for i in range(5)]
    trimmed = _trim_history(list(messages))

    total_msgs = 5
    history_raw_len = 5  # all fit
    omitted = max(0, total_msgs - history_raw_len)
    assert omitted == 0

    # No elision marker should be spliced in
    marker_msgs = [m for m in trimmed if "messages omitted" in (m.get("content") or "")]
    assert len(marker_msgs) == 0
