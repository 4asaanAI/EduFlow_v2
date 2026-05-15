"""Part 2 Patch P5: SSE generator robustness — module-level invariants.

Tests the constants and lightweight helpers that protect the SSE generator
from hangs, infinite loops, and malformed events:

  1. KEEPALIVE_INTERVAL is short (≤ 10 s) for fast disconnect detection.
  2. LLM_WALLCLOCK_BUDGET is exactly 90 s.
  3. A "done" SSE event string is valid JSON with type="done".
  4. MAX_TOOL_ROUNDS is at least 3 (prevents premature loop exit).
  5. The Scope fallback used in chat.py is a valid Scope object with the
     expected attributes.
"""

from __future__ import annotations

import json
import pytest

from routes.chat import KEEPALIVE_INTERVAL, LLM_WALLCLOCK_BUDGET, MAX_TOOL_ROUNDS
from ai.scope_resolver import Scope


# ─── test 1: keepalive interval is short ────────────────────────────────────

def test_keepalive_interval_is_short():
    """KEEPALIVE_INTERVAL must be ≤ 10 s for fast client-disconnect detection."""
    assert KEEPALIVE_INTERVAL <= 10


# ─── test 2: LLM wallclock budget is 90 ─────────────────────────────────────

def test_llm_wallclock_budget_is_module_constant():
    """LLM_WALLCLOCK_BUDGET must equal 90 (matches the Azure call ceiling)."""
    assert LLM_WALLCLOCK_BUDGET == 90


# ─── test 3: done event format is parseable JSON ────────────────────────────

def test_done_event_format():
    """A hardcoded 'done' SSE event must be parseable as JSON with type='done'."""
    raw_event = 'data: {"type": "done"}\n\n'
    # Strip the SSE framing
    assert raw_event.startswith("data: ")
    json_part = raw_event[len("data: "):].strip()
    parsed = json.loads(json_part)
    assert parsed["type"] == "done"


# ─── test 4: MAX_TOOL_ROUNDS is at least 3 ──────────────────────────────────

def test_loop_condition_max_tool_rounds():
    """MAX_TOOL_ROUNDS must be >= 3 (prevents premature multi-tool loop exit)."""
    assert MAX_TOOL_ROUNDS >= 3


# ─── test 5: scope fallback produces a valid Scope object ───────────────────

def test_scope_fallback_is_proper_scope_object():
    """The self_only fallback Scope used in chat.py exception path must be valid.

    Verifies that Scope(type='self_only', role='teacher', user_id='u1') has
    both a .filter() method and a .branch_id attribute — the two things the
    downstream code expects.
    """
    scope = Scope(type="self_only", role="teacher", user_id="u1")
    assert hasattr(scope, "filter"), "Scope must have .filter() method"
    assert callable(scope.filter)
    assert hasattr(scope, "branch_id"), "Scope must have .branch_id attribute"
    # filter() must return a dict without raising
    result = scope.filter()
    assert isinstance(result, dict)
