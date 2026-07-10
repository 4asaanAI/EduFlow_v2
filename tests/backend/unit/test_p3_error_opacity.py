"""Part 2 Patch P3 + R11.2: defensive input handling tests.

`_json_candidates` (still used for the <<<RICH_CONTENT>>> block) must tolerate
non-string and oversized input. The old JSON-in-text tool parsers were deleted
in R11.2 (native function calling); `_tool_calls_to_candidates` is their
structured replacement and must degrade gracefully on empty/bad input.
"""

from __future__ import annotations

import pytest

from routes.chat import _tool_calls_to_candidates, _json_candidates
from ai.llm_client import ToolCall


# ─── _tool_calls_to_candidates defensive handling (R11.2) ────────────────────

def test_tool_calls_to_candidates_none_returns_empty():
    assert _tool_calls_to_candidates(None) == []


def test_tool_calls_to_candidates_skips_nameless_calls():
    """A tool_call with no name is skipped, not turned into a bad candidate."""
    result = _tool_calls_to_candidates([ToolCall(id="x", name="", arguments={})])
    assert result == []


def test_tool_calls_to_candidates_coerces_non_dict_args():
    """Malformed (non-dict) arguments coerce to {} without raising."""
    tc = ToolCall(id="x", name="get_fee_summary", arguments={"class_id": "class-1"})
    result = _tool_calls_to_candidates([tc])
    assert len(result) == 1
    assert result[0]["action"] == "get_fee_summary"
    assert result[0]["params"] == {"class_id": "class-1"}


# ─── _json_candidates defensive handling (rich-content block) ────────────────

def test_json_candidates_non_string_returns_empty():
    """_json_candidates(42) must return [] without raising."""
    assert _json_candidates(42) == []


def test_json_candidates_oversized_input_truncated():
    """Input of 40,000 chars is truncated to ≤32,000 before scanning.

    Verifies the cap guard prevents quadratic-ish scans on adversarial input.
    We inject a valid JSON object AFTER the 32,000-char boundary; it must NOT
    appear in the candidates (since it gets chopped off).
    """
    padding = "x" * 32001  # just beyond the 32,000 cap
    tail = '{"marker": "should_not_appear"}'
    oversized = padding + tail
    assert len(oversized) > 32000
    candidates = _json_candidates(oversized)
    for c in candidates:
        assert "should_not_appear" not in c
