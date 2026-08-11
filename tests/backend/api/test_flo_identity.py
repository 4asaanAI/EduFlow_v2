"""The assistant is called Flo. Everywhere. Always.

Abhimanyu, 2026-07-22: 'Name the AI assistant "Flo" officially everywhere over the
platform ... to make it consistent everywhere and not anything else.'

A name drifts one string at a time - someone writes "the assistant" in a new error
message and nobody notices until the product is calling itself three things. These
tests fail when that happens.
"""
from __future__ import annotations

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]


def _prompt(**kwargs):
    from ai.prompts import build_system_prompt

    base = {"user": {"role": "owner", "name": "Owner"}, "school_context": {}}
    base.update(kwargs)
    return build_system_prompt(**base)


def test_flo_is_told_its_own_name():
    prompt = _prompt()
    assert "You are Flo" in prompt
    assert "YOUR NAME IS FLO" in prompt


def test_flo_is_told_not_to_call_itself_eduflow():
    """EduFlow is the platform Flo works inside, not Flo."""
    prompt = _prompt()
    assert "EduFlow is the platform you work" in prompt
    assert "Never introduce yourself as EduFlow" in prompt


def test_the_refusal_line_uses_the_name():
    prompt = _prompt()
    assert "I'm Flo - I can only help with school-related queries" in prompt
    assert "I'm EduFlow AI" not in prompt


def test_the_injection_block_response_uses_the_name():
    from ai.content_filter import INJECTION_BLOCKED_RESPONSE

    assert INJECTION_BLOCKED_RESPONSE.startswith("I'm Flo,")
    assert "EduFlow AI" not in INJECTION_BLOCKED_RESPONSE


def test_no_backend_string_still_calls_it_eduflow_ai():
    """Guards the class of drift, not one instance."""
    offenders = []
    for path in (REPO / "backend").rglob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            # The system prompt names the wrong names in order to FORBID them.
            # That line is the fix, not a violation of it.
            if "Never introduce yourself as" in line:
                continue
            if re.search(r"EduFlow\s+AI\b", line):
                offenders.append(f"{path.relative_to(REPO)}:{i}: {line.strip()[:80]}")
    assert not offenders, "the assistant is called Flo:\n" + "\n".join(offenders)


def test_no_user_facing_screen_still_calls_it_eduflow_ai():
    offenders = []
    src = REPO / "frontend" / "src"
    for path in src.rglob("*.js"):
        if "__tests__" in path.parts:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith(("//", "*", "/*")):
                continue
            # The mascot's accessible label names both the assistant and the
            # product it belongs to, which is correct: "Flo, the EduFlow AI
            # assistant". Anything else is the drift this test exists to catch.
            if "aria-label=\"Flo," in line:
                continue
            if re.search(r"EduFlow\s+AI\b", line):
                offenders.append(f"{path.relative_to(REPO)}:{i}: {stripped[:80]}")
    assert not offenders, "the assistant is called Flo:\n" + "\n".join(offenders)


def test_flo_is_told_how_to_write():
    """The stop-slop adaptation is an immutable built-in habit on every turn."""
    prompt = _prompt()
    assert "BUILT-IN HABIT /stop-slop" in prompt
    assert "Answer first" in prompt
    assert "Name the actor and concrete result" in prompt


def test_flo_is_told_not_to_use_long_dashes():
    """Abhimanyu, 2026-07-22, pointing at a live reply reading "Hey Aman - how can
    I help...": the long dash is an AI tell. The first version of these rules left
    that out as marginal; that judgement was wrong."""
    prompt = _prompt()
    # The wording Flo actually receives comes from the always-on habit in
    # ai/builtin_skills.py, not from the legacy copy in ai/prompts.py.
    assert "long dash of any kind" in prompt

    # 2026-08-11: these two lines used to require the rule to PRINT the em dash and the
    # en dash as examples. That was a fair safeguard when the worry was an ambiguous
    # rule, and it became a trap for two reasons. First, Abhimanyu asked that no long
    # dash appear anywhere on the platform, and showing the model the character it must
    # never use is the worst place to keep one. Second, a sweep removing long dashes
    # from the codebase silently rewrote the rule into "never use a hyphen" - the
    # instruction deleted itself and only this test's failure said so.
    #
    # The rule now names the characters by their unicode numbers, which cannot be
    # rewritten by a text sweep, and `ai/writing_style.py` enforces it after the fact so
    # the wording is no longer the only thing standing between Flo and a long dash.
    assert "2014" in prompt and "2013" in prompt, (
        "the rule must still name exactly which characters are banned"
    )
    from ai.writing_style import contains_long_dash
    assert not contains_long_dash(prompt), (
        "Flo's own instructions contain the character they forbid"
    )


def test_the_hyphen_is_explicitly_still_allowed():
    """A sloppy 'no dashes' rule would break '5-A', 'class-teacher' and '3+ days'
    across every reply. The rule names the characters it bans."""
    prompt = _prompt()
    assert "ordinary keyboard hyphen" in prompt
    # The examples are what stop a model over-applying the rule.
    assert "5-A" in prompt and "class-teacher" in prompt


def test_flo_is_told_not_to_open_with_a_greeting():
    prompt = _prompt()
    assert "Do not open with a greeting" in prompt


@pytest.mark.parametrize("user", [
    {"role": "owner", "name": "Owner"},
    {"role": "admin", "sub_category": "principal", "name": "Principal"},
    {"role": "admin", "sub_category": "accountant", "name": "Accountant"},
    {"role": "teacher", "name": "Teacher"},
    {"role": "student", "name": "Student"},
    {"role": "parent", "name": "Parent"},
])
def test_stop_slop_habit_applies_to_every_role(user):
    prompt = _prompt(user=user)
    assert prompt.count("BUILT-IN HABIT /stop-slop") == 1
    assert "Follow this habit automatically" in prompt


def test_stop_slop_is_code_backed_not_a_deletable_school_memory():
    from ai.builtin_skills import ALWAYS_ON_SKILLS, STOP_SLOP

    assert STOP_SLOP in ALWAYS_ON_SKILLS
    assert STOP_SLOP.slug == "stop-slop"
    assert STOP_SLOP.__dataclass_params__.frozen is True


def test_the_style_rules_do_not_cancel_the_product_rules():
    """`stop-slop` bans emphasis and em-dashes. This product deliberately bolds
    key figures and marks status with emoji so an owner can scan a reply on a
    phone. Adopting the skill must not quietly delete that."""
    prompt = _prompt()
    assert "Use bold for key metrics" in prompt
    assert "Use emoji indicators for status" in prompt
    assert "Use markdown tables for tabular data" in prompt


def test_flo_knows_the_schools_fee_structure_when_recorded():
    """Abhimanyu, 2026-07-22: 'record the fee structure ... to make the assistant
    (Mascot Flo) aware of the fees of various classes in The Aaryans'."""
    prompt = _prompt(school_settings={
        "ai_context": {"fee_structure": "Class IX-X: 4,000 per month, 48,000 per year."}
    })
    assert "FEE STRUCTURE" in prompt
    assert "48,000 per year" in prompt


# ─── The habit reaches generated DOCUMENTS too ───────────────────────────────
#
# Owner request 17, 2026-08-06: "add the /stop-slop skill as Flo's habit so that it
# never prints AI slop in her replies or generated documents". The chat prompt had
# carried it since 2026-08-05; the one-off prompts that generate documents did not,
# because they are assembled in their own route files and never touched ai/prompts.py.
# A question paper is printed and handed to children, so it is exactly the case the
# habit exists for.


def test_with_builtin_habits_appends_the_habit_to_any_prompt():
    from ai.builtin_skills import with_builtin_habits

    result = with_builtin_habits("You are an expert question paper setter.")

    assert "You are an expert question paper setter." in result
    assert "BUILT-IN HABIT /stop-slop" in result
    assert result.count("BUILT-IN HABIT /stop-slop") == 1


def test_the_question_paper_generator_carries_the_habit():
    """Read from the source rather than the model: the assertion has to fail if the
    call is ever rewritten without the wrapper, and mocking the model would still
    pass on a prompt that had lost it."""
    import inspect

    import routes.academics as academics

    source = inspect.getsource(academics)
    assert "with_builtin_habits(" in source, (
        "the generated question paper no longer goes through the plain-language habit"
    )
