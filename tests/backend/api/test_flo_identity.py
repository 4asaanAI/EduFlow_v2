"""The assistant is called Flo. Everywhere. Always.

Abhimanyu, 2026-07-22: 'Name the AI assistant "Flo" officially everywhere over the
platform ... to make it consistent everywhere and not anything else.'

A name drifts one string at a time — someone writes "the assistant" in a new error
message and nobody notices until the product is calling itself three things. These
tests fail when that happens.
"""
from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = pytest.mark.asyncio

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
    assert "I'm Flo — I can only help with school-related queries" in prompt
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
    """Adapted from the `stop-slop` skill, adopted 2026-07-22."""
    prompt = _prompt()
    assert "HOW YOU WRITE:" in prompt
    assert "Answer first" in prompt
    assert "Name the actor" in prompt


def test_flo_is_told_not_to_use_long_dashes():
    """Abhimanyu, 2026-07-22, pointing at a live reply reading "Hey Aman - how can
    I help...": the long dash is an AI tell. The first version of these rules left
    that out as marginal; that judgement was wrong."""
    prompt = _prompt()
    assert "NEVER use the em-dash" in prompt
    assert "—" in prompt, "the rule must show the actual em-dash character"
    assert "–" in prompt, "the rule must show the actual en-dash character"


def test_the_hyphen_is_explicitly_still_allowed():
    """A sloppy 'no dashes' rule would break '5-A', 'class-teacher' and '3+ days'
    across every reply. The rule names the characters it bans."""
    prompt = _prompt()
    assert 'The ordinary hyphen "-" is FINE' in prompt
    assert "5-A" in prompt


def test_flo_is_told_not_to_open_with_a_greeting():
    prompt = _prompt()
    assert "Do not open with a greeting" in prompt


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
