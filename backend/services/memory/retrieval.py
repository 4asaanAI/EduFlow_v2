"""Keyword relevance scoring for memory recall — cloned from Odysseus `src/memory.py`.

This is the ALWAYS-AVAILABLE retrieval path (FR33: hybrid recall must degrade
gracefully to keyword-only when the vector store is unavailable). The optional
vector path lives in `vector.py`; `store.recall()` blends the two.

Kept deliberately dependency-free (pure-Python token math) so it works on the
Python-3.9 / Elastic Beanstalk stack with zero extra packages — exactly the
fallback the G.1 infra spike mandates.
"""

from __future__ import annotations

import math
import re
import time
from typing import Dict, List


def tokenize(text: str) -> List[str]:
    """Split on whitespace and strip trailing punctuation (Odysseus parity)."""
    return [word.strip('.,!?";:()[]') for word in text.split()]


def jaccard_similarity(text1: str, text2: str) -> float:
    """Jaccard token-set similarity, 0.0–1.0 (Odysseus `get_text_similarity`)."""
    if not text1 or not text2:
        return 0.0
    tokens1 = set(t for t in tokenize(text1.lower()) if t)
    tokens2 = set(t for t in tokenize(text2.lower()) if t)
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0
    inter = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(inter) / len(union)


# Recency half-life: a memory loses half its recency weight every 90 days. Combined
# with the stored `confidence`, this implements G.8's "stale/low-confidence ones
# decay in retrieval ranking" without ever fully hiding a memory.
_RECENCY_HALF_LIFE_S = 90 * 24 * 3600


def _recency_weight(entry: Dict, *, now: float) -> float:
    ts = entry.get("updated_at_ts") or entry.get("created_at_ts") or now
    try:
        age = max(0.0, now - float(ts))
    except (TypeError, ValueError):
        age = 0.0
    return 0.5 ** (age / _RECENCY_HALF_LIFE_S)


def score_memories(
    query: str,
    memories: List[Dict],
    *,
    threshold: float = 0.05,
    now: float = None,
) -> List[Dict]:
    """Score memories against a query by keyword similarity × confidence × recency.

    Returns the input dicts (sorted best-first) for those scoring >= threshold,
    each annotated with a `_score` key. Confidence and recency act as multipliers
    so a stale, low-confidence memory ranks below a fresh, high-confidence one with
    the same lexical overlap (G.8 decay) — but neither can zero the score out, so a
    strong lexical match still surfaces.
    """
    if not memories or not query or not query.strip():
        return []
    now = now if now is not None else time.time()
    q = query.lower()
    q_tokens = set(t for t in tokenize(q) if t)
    if not q_tokens:
        return []

    scored: List[Dict] = []
    for mem in memories:
        text = (mem.get("text") or "").lower()
        m_tokens = set(t for t in tokenize(text) if t)
        if not m_tokens:
            continue
        base = len(q_tokens & m_tokens) / len(q_tokens | m_tokens)
        # Exact phrase containment is a strong relevance signal (Odysseus parity).
        if q in text:
            base = max(base, 0.8)
        if base <= 0:
            continue
        try:
            confidence = float(mem.get("confidence", 0.7))
        except (TypeError, ValueError):
            confidence = 0.7
        confidence = min(1.0, max(0.1, confidence))
        recency = _recency_weight(mem, now=now)
        # Blend: lexical score is primary; confidence/recency scale it within [0.3,1].
        final = base * (0.4 + 0.6 * confidence) * (0.5 + 0.5 * recency)
        if final >= threshold:
            scored.append({**mem, "_score": round(final, 5)})

    scored.sort(key=lambda m: m["_score"], reverse=True)
    return scored
