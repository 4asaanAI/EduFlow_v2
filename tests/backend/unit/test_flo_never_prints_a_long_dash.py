"""Flo never prints a long dash, and this is what makes that true.

Abhimanyu, 2026-08-11: "make sure that Flo doesn't print them either in her replies and
should have the /stop-slop as a habit".

The habit has told Flo not to use them since 2026-07-22, when Abhimanyu pointed at a live
reply reading "Hey Aman - how can I help..." and named the dash as the giveaway. **A
prompt rule is a request.** A model follows it most of the time, which is the failure
mode that is hard to catch: they stop appearing often enough that nobody checks, and then
one turns up in a circular that has already reached 1,842 families.

So it is enforced twice, and these tests pin both halves.
"""

from __future__ import annotations

import pytest

from ai.builtin_skills import ALWAYS_ON_SKILLS, render_builtin_habits, with_builtin_habits
from ai.writing_style import contains_long_dash, plain_dashes

EM = "—"
EN = "–"


# ── The guarantee ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dash", [
    "—",  # em dash
    "–",  # en dash
    "‒",  # figure dash
    "―",  # horizontal bar
    "−",  # minus sign
    "－",  # fullwidth hyphen-minus
])
def test_every_long_dash_becomes_a_plain_hyphen(dash):
    # A model reaching for "a long dash" does not always reach for the same character,
    # and a rule naming only the em dash is quietly satisfied by an en dash.
    assert plain_dashes(f"Fees are due{dash}please pay") == "Fees are due-please pay"
    assert not contains_long_dash(plain_dashes(f"a{dash}b"))


def test_the_ordinary_hyphen_is_left_alone():
    # It is needed, and stripping it would break the school's own vocabulary.
    for kept in ("Class 5-A", "class-teacher", "3+ days", "2026-08-11", "e-mail"):
        assert plain_dashes(kept) == kept


def test_nothing_else_about_the_sentence_changes():
    original = "Sonu recorded 4,500 for admission number 1234 at 9:15am."
    assert plain_dashes(original) == original


def test_a_missing_or_non_string_value_is_handled_rather_than_crashing():
    # Callers hold None and numbers, and should not have to check first.
    assert plain_dashes(None) is None
    assert plain_dashes("") == ""
    assert plain_dashes(42) == 42
    assert contains_long_dash(None) is False


# ── The two places it is applied ─────────────────────────────────────────────

def test_the_streaming_reply_is_cleaned(monkeypatch):
    # Every word Flo streams goes through this one point, which is why it is done here
    # and not at the dozen places that emit an SSE frame.
    import ai.llm_client as llm

    source = llm.__file__
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "payload = plain_dashes(payload)" in text, (
        "the streaming path no longer cleans the model's text"
    )


def test_the_non_streaming_reply_is_cleaned():
    # Generated documents come through the non-streaming call. A question paper the
    # school prints is exactly what the owner meant by "or generated documents".
    import ai.llm_client as llm

    with open(llm.__file__, encoding="utf-8") as handle:
        text = handle.read()
    assert "plain_dashes(choice.message.content" in text, (
        "the non-streaming path no longer cleans the model's text"
    )


# ── The habit itself ─────────────────────────────────────────────────────────

def test_stop_slop_is_always_on_for_every_role():
    slugs = {skill.slug for skill in ALWAYS_ON_SKILLS}
    assert "stop-slop" in slugs, "the plain-language habit is no longer always on"


def test_the_habit_still_forbids_long_dashes():
    habits = render_builtin_habits()
    assert "long dash" in habits
    assert "2014" in habits and "2013" in habits, (
        "the rule must name the characters. It used to PRINT them as examples, which "
        "meant a sweep that removed long dashes from the codebase silently rewrote the "
        "rule into 'never use a hyphen' - the instruction deleted itself."
    )


def test_the_habit_does_not_print_the_thing_it_forbids():
    # The rule naming em dashes must not itself contain one, or the model is shown the
    # character it is being told never to use.
    assert not contains_long_dash(render_builtin_habits())


def test_the_habit_is_appended_to_prompts_built_elsewhere():
    # Document-generating routes assemble their own prompts and must still get it.
    combined = with_builtin_habits("You write a question paper.")
    assert "You write a question paper." in combined
    assert "stop-slop" in combined


def test_no_role_brief_prints_a_long_dash():
    # Whatever the habit says, an example in a brief teaches by showing.
    from ai.prompts import ROLE_RULES

    offenders = [key for key, text in ROLE_RULES.items() if contains_long_dash(text)]
    assert offenders == [], f"these briefs still contain a long dash: {offenders}"
