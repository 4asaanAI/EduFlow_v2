"""R11.1 — golden eval corpus loader + coherence helpers.

The corpus itself lives as data under `_bmad-output/test-artifacts/eval-corpus/`
(so it is reviewable/diffable independently of test code). This module loads it and
exposes helpers shared by the deterministic structural eval and the LLM-judge runner.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from ai.prompts import TOOLS_BY_ROLE

# repo_root/tests/backend/evals/corpus.py → repo_root
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CORPUS_PATH = os.path.join(
    _REPO_ROOT, "_bmad-output", "test-artifacts", "eval-corpus", "corpus.json"
)
SCORES_BASELINE_PATH = os.path.join(
    _REPO_ROOT, "_bmad-output", "test-artifacts", "eval-corpus", "scores-baseline.json"
)

VALID_OUTCOMES = {"answer", "confirm", "denial", "disambiguation", "chat"}
# Outcomes for which the assistant is expected to USE the tool (so it must be
# advertised to the role). For "denial" the tool must NOT be advertised (that is
# what makes the refusal correct). For "disambiguation"/"chat" no tool is expected.
TOOL_USING_OUTCOMES = {"answer", "confirm"}


@dataclass
class Conversation:
    id: str
    role: str
    sub_category: Optional[str]
    language: str
    tags: list
    turns: list
    expected_tool: Optional[str]
    expected_outcome: str
    rubric: str = ""


def load_corpus() -> list:
    with open(CORPUS_PATH, encoding="utf-8") as fh:
        raw = json.load(fh)
    convos = []
    for c in raw["conversations"]:
        convos.append(Conversation(
            id=c["id"],
            role=c["role"],
            sub_category=c.get("sub_category"),
            language=c.get("language", "en"),
            tags=c.get("tags", []),
            turns=c["turns"],
            expected_tool=c.get("expected_tool"),
            expected_outcome=c["expected_outcome"],
            rubric=c.get("rubric", ""),
        ))
    return convos


def advertised_tools(role: str, sub_category: Optional[str]) -> set:
    """The tool names advertised to (role, sub_category), honouring the same
    fallback lookup the prompt builder uses."""
    from ai.prompts import _resolve_tools
    return {t["name"] for t in _resolve_tools(role, sub_category)}
