"""R11.1 — deterministic structural eval (runs in the standard CI suite).

This tier needs NO LLM and NO credentials: it proves the golden corpus is
*coherent with the current system* and that the real prompt builder produces a
usable prompt for every entry. It catches drift between the corpus's expected
behavior and the live prompt↔registry wiring (complementing the LLM-judge tier,
which scores answer quality and requires Azure credentials).
"""

from __future__ import annotations

from ai.prompts import TOOLS_BY_ROLE, build_system_prompt
from ai.tool_functions_v2 import TOOL_REGISTRY
from tests.backend.evals.corpus import (
    load_corpus, advertised_tools, VALID_OUTCOMES, TOOL_USING_OUTCOMES,
)

# All assertions here are pure/synchronous — no asyncio marker needed.

CORPUS = load_corpus()


def test_corpus_has_at_least_40_conversations():
    assert len(CORPUS) >= 40, f"corpus has only {len(CORPUS)} conversations (need >= 40)"


def test_corpus_ids_are_unique():
    ids = [c.id for c in CORPUS]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate corpus ids: {dupes}"


def test_corpus_covers_every_role_and_sub_category():
    """Every (role, sub_category) prompt variant is exercised (owner/student are
    covered by their None-sub entries; the role==sub alias keys are equivalent)."""
    covered = {(c.role, c.sub_category) for c in CORPUS}
    covered_roles = {c.role for c in CORPUS}
    missing = []
    for (role, sub) in TOOLS_BY_ROLE.keys():
        if sub is None or sub == role:
            if role not in covered_roles:
                missing.append((role, sub))
        elif (role, sub) not in covered:
            missing.append((role, sub))
    assert not missing, f"corpus does not cover these variants: {missing}"


def test_corpus_covers_required_scenario_tags():
    tags = [t for c in CORPUS for t in c.tags]
    for required in ("incident", "followup", "ambiguous", "denial", "hinglish"):
        assert required in tags, f"corpus missing a '{required}' scenario"
    assert tags.count("hinglish") >= 4, "need >= 4 Hinglish conversations"
    assert tags.count("denial") >= 3, "need >= 3 denial conversations"


def test_every_outcome_is_valid():
    bad = [(c.id, c.expected_outcome) for c in CORPUS if c.expected_outcome not in VALID_OUTCOMES]
    assert not bad, f"invalid expected_outcome values: {bad}"


def test_expected_tools_are_coherent_with_the_advertised_toolset():
    """The crux structural invariant, per outcome:
      - answer/confirm  → expected_tool exists AND is advertised to the role
      - denial          → expected_tool exists AND is NOT advertised (that's what
                          makes the refusal correct)
      - disambiguation/chat → no expected_tool.
    """
    problems = []
    for c in CORPUS:
        adv = advertised_tools(c.role, c.sub_category)
        if c.expected_outcome in TOOL_USING_OUTCOMES:
            if not c.expected_tool:
                problems.append((c.id, "tool-using outcome but no expected_tool"))
            elif c.expected_tool not in TOOL_REGISTRY:
                problems.append((c.id, f"expected_tool {c.expected_tool!r} not in registry"))
            elif c.expected_tool not in adv:
                problems.append((c.id, f"expected_tool {c.expected_tool!r} not advertised to {c.role}/{c.sub_category}"))
        elif c.expected_outcome == "denial":
            if not c.expected_tool:
                problems.append((c.id, "denial should name the tool the user is (wrongly) asking for"))
            elif c.expected_tool in adv:
                problems.append((c.id, f"denial expected_tool {c.expected_tool!r} IS advertised — not a real denial"))
        else:  # disambiguation | chat
            if c.expected_tool is not None:
                problems.append((c.id, f"{c.expected_outcome} should not name an expected_tool"))
    assert not problems, "corpus/toolset incoherence:\n  " + "\n  ".join(f"{i}: {m}" for i, m in problems)


def test_system_prompt_builds_for_every_conversation():
    """The real prompt builder must produce a non-trivial prompt that advertises
    the expected tool (when one is expected) for every corpus entry."""
    failures = []
    for c in CORPUS:
        user = {"role": c.role, "sub_category": c.sub_category, "name": "Eval User"}
        try:
            prompt = build_system_prompt(user, school_context={}, lang="en")
        except Exception as exc:  # pragma: no cover - a build failure is the finding
            failures.append((c.id, f"prompt build raised {exc!r}"))
            continue
        if not prompt or len(prompt) < 100:
            failures.append((c.id, "prompt suspiciously short"))
        if c.expected_outcome in TOOL_USING_OUTCOMES and c.expected_tool:
            if c.expected_tool not in prompt:
                failures.append((c.id, f"expected_tool {c.expected_tool!r} absent from the built prompt"))
    assert not failures, "prompt-build failures:\n  " + "\n  ".join(f"{i}: {m}" for i, m in failures)
