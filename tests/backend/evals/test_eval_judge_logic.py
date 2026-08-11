"""R11.1 - unit tests for the LLM-judge harness LOGIC (no credentials needed).

Locks the scoring/threshold maths and the full orchestration with a FAKE judge, so
the credentialed nightly run can trust the plumbing. The real-model run lives in
test_eval_llm_judge.py behind the `llm_eval` marker.
"""

from __future__ import annotations

import pytest

from ai.llm_client import ToolCall
from tests.backend.evals import judge
from tests.backend.evals.judge import (
    DIMENSIONS, parse_judge_scores, aggregate, regression_check, EvalResult, run_eval,
)
from tests.backend.evals.corpus import load_corpus

# ── parse_judge_scores ─────────────────────────────────────────────────────────

def test_parse_bare_json():
    s = parse_judge_scores('{"correctness": 0.9, "completeness": 0.8, "tone": 1.0}')
    assert s == {"correctness": 0.9, "completeness": 0.8, "tone": 1.0}


def test_parse_json_in_prose_and_fences():
    s = parse_judge_scores('Sure!\n```json\n{"correctness":0.5,"completeness":0.5,"tone":0.5}\n```')
    assert s["correctness"] == 0.5


def test_parse_clamps_and_defaults_missing_to_zero():
    s = parse_judge_scores('{"correctness": 1.7, "tone": "bad"}')
    assert s["correctness"] == 1.0     # clamped
    assert s["completeness"] == 0.0    # missing → worst case
    assert s["tone"] == 0.0            # non-numeric → worst case


def test_parse_garbage_is_all_zero():
    s = parse_judge_scores("the model said nothing useful")
    assert all(s[d] == 0.0 for d in DIMENSIONS)


# ── aggregate ──────────────────────────────────────────────────────────────────

def test_aggregate_means():
    results = [
        EvalResult(id="a", scores={"correctness": 1.0, "completeness": 1.0, "tone": 1.0}),
        EvalResult(id="b", scores={"correctness": 0.0, "completeness": 0.0, "tone": 0.0}),
    ]
    agg = aggregate(results)
    assert agg["correctness"] == 0.5
    assert agg["overall"] == 0.5
    assert agg["n"] == 2


def test_aggregate_counts_errored_turn_as_zero():
    results = [
        EvalResult(id="a", scores={"correctness": 1.0, "completeness": 1.0, "tone": 1.0}),
        EvalResult(id="b", scores={"correctness": 1.0, "completeness": 1.0, "tone": 1.0}, error="no reply"),
    ]
    agg = aggregate(results)
    assert agg["overall"] == 0.5  # the errored turn drags the mean down (not excused)


# ── regression_check ─────────────────────────────────────────────────────────────

def test_regression_no_baseline_accepts_and_reports():
    ok, notes = regression_check({"overall": 0.9}, baseline=None)
    assert ok is True and notes


def test_regression_rejects_first_baseline_below_absolute_floor():
    current = {"correctness": 0.9, "completeness": 0.65, "tone": 0.9, "overall": 0.82}
    ok, problems = regression_check(current, baseline=None)
    assert ok is False
    assert any("completeness" in problem for problem in problems)


def test_regression_blocks_on_drop_beyond_threshold():
    baseline = {"correctness": 0.9, "completeness": 0.9, "tone": 0.9, "overall": 0.9}
    current = {"correctness": 0.9, "completeness": 0.9, "tone": 0.70, "overall": 0.83}
    ok, problems = regression_check(current, baseline, threshold=0.05)
    assert ok is False
    assert any("tone" in p for p in problems)


def test_regression_allows_within_threshold_and_improvements():
    baseline = {"correctness": 0.9, "completeness": 0.9, "tone": 0.9, "overall": 0.9}
    current = {"correctness": 0.92, "completeness": 0.88, "tone": 0.90, "overall": 0.90}
    ok, problems = regression_check(current, baseline, threshold=0.05)
    assert ok is True and not problems


# ── run_eval orchestration with FAKE assistant + judge (no network) ──────────────

class _FakeResult:
    def __init__(self, text, ok=True, tool_calls=None):
        self.text = text
        self.ok = ok
        self.tokens = 1
        self.tool_calls = tool_calls


async def test_run_eval_end_to_end_with_fakes():
    convos = load_corpus()[:5]

    async def fake_assistant(system_prompt, messages, tools=None):
        # A plausible non-empty reply so the judge stage runs.
        assert "user" in messages[0]["role"]
        assert tools
        return _FakeResult("Here is the information you asked for.")

    async def fake_judge(system_prompt, messages):
        return _FakeResult('{"correctness": 0.9, "completeness": 0.85, "tone": 0.95}')

    report = await run_eval(convos, fake_assistant, fake_judge)
    assert len(report.results) == 5
    assert report.aggregate["n"] == 5
    assert report.aggregate["correctness"] == 0.9
    assert 0.0 <= report.aggregate["overall"] <= 1.0


async def test_run_eval_records_empty_assistant_reply_as_error():
    convos = load_corpus()[:2]

    async def empty_assistant(system_prompt, messages, tools=None):
        return _FakeResult("", ok=False)  # the incident class: no reply

    async def fake_judge(system_prompt, messages):
        return _FakeResult('{"correctness": 1, "completeness": 1, "tone": 1}')

    report = await run_eval(convos, empty_assistant, fake_judge)
    assert all(r.error for r in report.results)
    assert report.aggregate["overall"] == 0.0  # silent turns score zero


async def test_run_eval_scores_native_tool_call_instead_of_empty_reply():
    convos = load_corpus()[:1]

    async def tool_assistant(system_prompt, messages, tools=None):
        return _FakeResult("", tool_calls=[ToolCall(id="call-1", name="get_fee_summary")])

    async def fake_judge(system_prompt, messages):
        assert "TOOL_CALL: get_fee_summary({})" in messages[0]["content"]
        return _FakeResult('{"correctness": 1, "completeness": 1, "tone": 1}')

    report = await run_eval(convos, tool_assistant, fake_judge)
    assert report.results[0].error is None
    assert report.aggregate["overall"] == 1.0
