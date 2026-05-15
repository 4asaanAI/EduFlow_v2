"""Part 2 Patch P3: error opacity / defensive input handling tests.

Tests that _parse_tool_calls and _json_candidates correctly handle:
  1. Non-string inputs to _parse_tool_calls (returns []).
  2. None input to _parse_tool_calls (returns []).
  3. Non-string inputs to _json_candidates (returns []).
  4. Oversized input to _json_candidates is truncated before scanning.
  5. Valid JSON tool call string is parsed correctly.
"""

from __future__ import annotations

import json
import pytest

from routes.chat import _parse_tool_calls, _json_candidates


# ─── test 1: non-string dict input to _parse_tool_calls returns [] ───────────

def test_parse_tool_calls_non_string_returns_empty():
    """_parse_tool_calls({'dict': 'input'}) must return [] without raising."""
    result = _parse_tool_calls({"dict": "input"})
    assert result == []


# ─── test 2: None input to _parse_tool_calls returns [] ─────────────────────

def test_parse_tool_calls_none_returns_empty():
    """_parse_tool_calls(None) must return [] without raising."""
    result = _parse_tool_calls(None)
    assert result == []


# ─── test 3: non-string input to _json_candidates returns [] ─────────────────

def test_json_candidates_non_string_returns_empty():
    """_json_candidates(42) must return [] without raising."""
    result = _json_candidates(42)
    assert result == []


# ─── test 4: oversized input to _json_candidates is truncated ────────────────

def test_json_candidates_oversized_input_truncated():
    """Input of 40,000 chars is truncated to ≤32,000 before scanning.

    Verifies the cap guard prevents quadratic-ish scans on adversarial input.
    We inject a valid JSON object AFTER the 32,000-char boundary; it must
    NOT appear in the candidates (since it gets chopped off).
    """
    padding = "x" * 32001  # just beyond the 32,000 cap
    tail = '{"action": "should_not_appear", "params": {}}'
    oversized = padding + tail
    assert len(oversized) > 32000
    candidates = _json_candidates(oversized)
    # The tail JSON was past the cap; it should not be found
    for c in candidates:
        assert "should_not_appear" not in c


# ─── test 5: valid JSON tool call string is parsed correctly ─────────────────

def test_parse_tool_calls_valid_json():
    """A proper JSON tool call string returns the parsed dict with action + params."""
    payload = json.dumps({
        "action": "get_fee_summary",
        "params": {"class_id": "class-1"},
        "reason": "user asked about fees",
    })
    result = _parse_tool_calls(payload)
    assert len(result) == 1
    call = result[0]
    assert call["action"] == "get_fee_summary"
    assert call["params"] == {"class_id": "class-1"}
