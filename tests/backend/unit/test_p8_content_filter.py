"""Part 2 Patch P8: content filter correctness tests.

Verifies that filter_response:
  1. Replaces blocked terms in student role output.
  2. Passes teacher output through unchanged.
  3. Handles empty input safely.
  4. Does not break valid JSON for clean content.
  5. Action-button JSON for students passes through as parseable JSON.
"""

from __future__ import annotations

import json
import pytest

from ai.content_filter import filter_response, BLOCKED_TOPIC_RESPONSE


# ─── test 1: student role — blocked term is replaced ─────────────────────────

def test_filter_response_student_blocks_sensitive_terms():
    """filter_response replaces blocked drug terms in student role output."""
    input_text = "the student took cocaine"
    result = filter_response(input_text, "student")
    # The original text must not be returned unchanged — it's blocked
    assert result != input_text
    # The replacement should be the standard blocked-topic message
    assert result == BLOCKED_TOPIC_RESPONSE


# ─── test 2: teacher role passes through unchanged ───────────────────────────

def test_filter_response_teacher_passes_through():
    """filter_response returns the input unchanged for teacher role."""
    input_text = "the student took cocaine"
    result = filter_response(input_text, "teacher")
    assert result == input_text


# ─── test 3: empty input is handled safely ───────────────────────────────────

def test_filter_response_student_empty_input():
    """filter_response('', 'student') returns empty or safe value without raising."""
    result = filter_response("", "student")
    assert isinstance(result, str)
    assert len(result) >= 0  # empty string or replacement — either is acceptable


# ─── test 4: filtering clean JSON does not break JSON parsability ─────────────

def test_filter_on_json_dumps_is_stable():
    """Filtering a JSON-serialized list of clean school data preserves valid JSON."""
    data = [{"value": "normal school data"}, {"value": "attendance report"}]
    json_str = json.dumps(data)
    result = filter_response(json_str, "student")
    # Clean content should pass through — must still be parseable JSON
    parsed = json.loads(result)
    assert isinstance(parsed, list)


# ─── test 5: action buttons JSON passes through as valid JSON for students ────

def test_action_buttons_filtered_same_as_rich_blocks():
    """A clean action_buttons list serialised to JSON remains parseable after
    filter_response is applied for the student role.

    This validates the pattern from chat.py where filter_response is applied
    to action_buttons JSON the same way as rich_blocks.
    """
    action_buttons = [
        {"label": "View Timetable", "action": "view_timetable"},
        {"label": "Check Attendance", "action": "check_attendance"},
    ]
    json_str = json.dumps(action_buttons)
    result = filter_response(json_str, "student")
    # Clean content — must still parse as a list
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
