"""R11.1 — the credentialed LLM-judge quality gate (AC2).

Runs the WHOLE golden corpus through the real prompt pipeline and a real LLM judge,
then blocks if any dimension dropped more than the threshold below the recorded
baseline. Requires Azure OpenAI credentials, so it is marked `llm_eval` and
DESELECTED by default (the standard suite runs the deterministic structural eval and
the judge-logic unit tests instead). Run in credentialed nightly/pre-release CI:

    pytest -m llm_eval tests/backend/evals/test_eval_llm_judge.py

On the first credentialed run (no baseline yet) the aggregate is written to
scores-baseline.json and the run passes; subsequent runs gate against it.
"""

from __future__ import annotations

import json
import os

import pytest

from ai.llm_client import LLMClient
from tests.backend.evals.corpus import load_corpus, SCORES_BASELINE_PATH
from tests.backend.evals import judge

pytestmark = [pytest.mark.llm_eval, pytest.mark.asyncio]


def _credentials_present() -> bool:
    return bool(os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"))


async def test_golden_corpus_quality_no_regression():
    if not _credentials_present():
        pytest.skip("Azure OpenAI credentials absent — run this tier in credentialed CI only.")

    client = LLMClient()

    async def assistant_chat(system_prompt, messages):
        return await client.chat(system_prompt=system_prompt, messages=messages)

    async def judge_chat(system_prompt, messages):
        return await client.chat(system_prompt=system_prompt, messages=messages)

    convos = load_corpus()
    report = await judge.run_eval(convos, assistant_chat, judge_chat)

    baseline = None
    if os.path.exists(SCORES_BASELINE_PATH):
        with open(SCORES_BASELINE_PATH, encoding="utf-8") as fh:
            baseline = json.load(fh).get("aggregate")

    ok, problems = judge.regression_check(report.aggregate, baseline)

    # Persist the fresh scores so the run is auditable and (first-run) establishes
    # the baseline. Per-conversation detail is kept for the trace viewer (R11.5).
    payload = {
        "aggregate": report.aggregate,
        "results": [{"id": r.id, "scores": r.scores, "error": r.error} for r in report.results],
    }
    if baseline is None:
        with open(SCORES_BASELINE_PATH, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)

    assert ok, "Eval quality regression vs baseline:\n  " + "\n  ".join(problems)
