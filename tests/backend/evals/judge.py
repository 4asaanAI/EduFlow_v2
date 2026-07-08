"""R11.1 — LLM-judge harness for the golden eval corpus.

Two concerns, deliberately separated so the *logic* is testable without credentials:

- Pure functions (no network): `parse_judge_scores`, `aggregate`, `regression_check`.
  These are unit-tested in CI with a fake judge — the scoring/threshold maths can
  never silently break.
- Async orchestration (`run_conversation`, `judge_conversation`, `run_eval`): take
  the assistant + judge chat callables as parameters so the real run wires them to
  Azure (`LLMClient().chat`) while tests inject deterministic fakes.

The credentialed run lives in `test_eval_llm_judge.py` behind the `llm_eval`
marker (deselected by default, like `mongo_real`), so it never runs — or skips —
in the standard credential-less suite.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from ai.prompts import build_system_prompt

DIMENSIONS = ("correctness", "completeness", "tone")
# A per-dimension aggregate that falls more than this below the recorded baseline
# blocks release (AC2). Absolute floor also enforced (see regression_check).
DEFAULT_THRESHOLD = 0.05

_JUDGE_SYSTEM = (
    "You are a strict QA judge for a school-management AI assistant. You are given "
    "the user's role, their message(s), the assistant's reply, and a rubric. Score "
    "the reply on three dimensions from 0.0 to 1.0:\n"
    "- correctness: did it do/answer the right thing for the rubric, with no wrong "
    "or fabricated facts, and respect role limits (a denial that correctly refuses "
    "scores HIGH on correctness)?\n"
    "- completeness: did it fully address the request (or fully explain why it can't)?\n"
    "- tone: professional, clear, appropriate for a school context.\n"
    'Respond with ONLY a JSON object: {"correctness": <float>, "completeness": '
    '<float>, "tone": <float>, "notes": "<one line>"}.'
)


@dataclass
class EvalResult:
    id: str
    scores: dict
    assistant_text: str = ""
    error: Optional[str] = None


@dataclass
class EvalReport:
    results: list = field(default_factory=list)
    aggregate: dict = field(default_factory=dict)


def build_judge_prompt(convo, assistant_text: str) -> str:
    turns = "\n".join(f"  user: {t}" for t in convo.turns)
    return (
        f"ROLE: {convo.role}"
        + (f" / {convo.sub_category}" if convo.sub_category else "")
        + f"\nLANGUAGE: {convo.language}\n"
        f"CONVERSATION:\n{turns}\n"
        f"EXPECTED OUTCOME: {convo.expected_outcome}\n"
        f"RUBRIC: {convo.rubric}\n\n"
        f"ASSISTANT REPLY:\n{assistant_text}\n"
    )


def parse_judge_scores(text: str) -> dict:
    """Extract the three dimension scores from a judge reply, robustly.

    Accepts a bare JSON object or JSON embedded in prose/code fences. Missing or
    non-numeric dimensions default to 0.0 (a judge that fails to score a dimension
    is treated as the worst case, never silently passed). Values are clamped [0,1].
    """
    obj = None
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
        except (ValueError, TypeError):
            obj = None
    obj = obj if isinstance(obj, dict) else {}
    scores = {}
    for dim in DIMENSIONS:
        val = obj.get(dim)
        try:
            f = float(val)
        except (TypeError, ValueError):
            f = 0.0
        scores[dim] = max(0.0, min(1.0, f))
    return scores


def aggregate(results: list) -> dict:
    """Mean per dimension + an `overall` mean across all dimensions.

    Results carrying an `error` (the assistant/judge turn failed) contribute 0.0 —
    a broken turn is a quality failure, not an excused skip."""
    if not results:
        return {dim: 0.0 for dim in DIMENSIONS} | {"overall": 0.0, "n": 0}
    agg = {}
    for dim in DIMENSIONS:
        vals = [(r.scores.get(dim, 0.0) if not r.error else 0.0) for r in results]
        agg[dim] = round(sum(vals) / len(vals), 4)
    agg["overall"] = round(sum(agg[dim] for dim in DIMENSIONS) / len(DIMENSIONS), 4)
    agg["n"] = len(results)
    return agg


def regression_check(current: dict, baseline: Optional[dict], threshold: float = DEFAULT_THRESHOLD):
    """Compare a fresh aggregate against the recorded baseline.

    Returns (ok: bool, problems: list[str]). A per-dimension (or overall) score
    that dropped by more than `threshold` versus the baseline fails. With no
    baseline yet, any run is accepted (it BECOMES the baseline) but reported."""
    problems = []
    if not baseline:
        return True, ["no baseline recorded yet — this run establishes it"]
    for key in (*DIMENSIONS, "overall"):
        base = baseline.get(key)
        cur = current.get(key)
        if base is None or cur is None:
            continue
        if cur < base - threshold:
            problems.append(f"{key}: {cur:.4f} dropped > {threshold} below baseline {base:.4f}")
    return (not problems), problems


async def run_conversation(convo, assistant_chat: Callable[..., Awaitable]) -> str:
    """Drive the real prompt through the assistant model and return its reply text.

    `assistant_chat(system_prompt, messages)` returns an object with `.text`/`.ok`
    (an `LLMResult`). We build the genuine role-scoped system prompt so the eval
    exercises the real prompt wiring, not a stand-in."""
    user = {"role": convo.role, "sub_category": convo.sub_category, "name": "Eval User"}
    system_prompt = build_system_prompt(user, school_context={}, lang="en")
    messages = [{"role": "user", "content": t} for t in convo.turns]
    result = await assistant_chat(system_prompt=system_prompt, messages=messages)
    if not getattr(result, "ok", True):
        return ""
    return getattr(result, "text", "") or ""


async def judge_conversation(convo, assistant_text: str, judge_chat: Callable[..., Awaitable]) -> dict:
    prompt = build_judge_prompt(convo, assistant_text)
    result = await judge_chat(
        system_prompt=_JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_judge_scores(getattr(result, "text", "") or "")


async def run_eval(convos, assistant_chat, judge_chat) -> EvalReport:
    results = []
    for c in convos:
        try:
            reply = await run_conversation(c, assistant_chat)
            if not reply:
                results.append(EvalResult(id=c.id, scores={d: 0.0 for d in DIMENSIONS},
                                          error="assistant produced no reply"))
                continue
            scores = await judge_conversation(c, reply, judge_chat)
            results.append(EvalResult(id=c.id, scores=scores, assistant_text=reply))
        except Exception as exc:  # pragma: no cover - defensive; recorded as failure
            results.append(EvalResult(id=c.id, scores={d: 0.0 for d in DIMENSIONS}, error=str(exc)))
    return EvalReport(results=results, aggregate=aggregate(results))
