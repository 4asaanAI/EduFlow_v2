"""Canonical state normalizer for the dual-entrypoint parity harness (Story F.6).

The parity harness drives the SAME seed through both write entrypoints — the REST
handler (via TestClient) and the AI tool (via real dispatch) — and asserts the DB
blast radius is identical. Volatile fields (ids, timestamps, request-correlation)
legitimately differ between two independent runs, so they are masked before diffing.

This module centralizes the masking RULESET so every per-tool parity test (and the
F.5 dry-run-vs-real comparison) uses ONE definition of "equivalent state" — the
ruleset itself is unit-tested in `test_normalizer.py`. The CI drift gate
(`test_parity_corpus.py`) fails if a write tool ships without a corpus entry.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Optional

# Fields that legitimately differ between two independent runs of the same seed.
VOLATILE_FIELDS = {
    "id",
    "_id",
    "created_at",
    "updated_at",
    "timestamp",
    "confirmed_at",
    "started_at",
    "executed_at",
    "correlation_id",
    "request_id",
    "idempotency_key",
    "plan_token",
    "token",
    "dispatch_id",
}


def mask_doc(doc: dict, volatile: Optional[Iterable[str]] = None) -> dict:
    """Recursively drop volatile keys from a single document."""
    vol = set(volatile) if volatile is not None else VOLATILE_FIELDS
    out: dict = {}
    for key, value in doc.items():
        if key in vol:
            continue
        if isinstance(value, dict):
            out[key] = mask_doc(value, vol)
        elif isinstance(value, list):
            out[key] = [mask_doc(v, vol) if isinstance(v, dict) else v for v in value]
        else:
            out[key] = value
    return out


def _sort_key(doc: dict) -> tuple:
    # Order-independent: sort by the most stable identifying fields available.
    return (
        str(doc.get("entity_id", "")),
        str(doc.get("student_id", "")),
        str(doc.get("staff_id", "")),
        str(doc.get("action", "")),
        str(doc.get("status", "")),
        str(sorted(doc.items(), key=lambda kv: kv[0])),
    )


def normalize_docs(docs: Iterable[dict], volatile: Optional[Iterable[str]] = None) -> list:
    """Mask volatile fields and sort so two runs are order-independently comparable."""
    masked = [mask_doc(copy.deepcopy(d), volatile) for d in docs]
    masked.sort(key=_sort_key)
    return masked


def diff_snapshots(left: dict, right: dict, volatile: Optional[Iterable[str]] = None) -> dict:
    """Return per-collection differences between two snapshots (empty = identical).

    Each snapshot is `{collection_name: [docs]}`. The result maps a collection to
    `{"only_left": [...], "only_right": [...]}` for any collection that differs.
    """
    out: dict = {}
    for coll in set(left) | set(right):
        ln = normalize_docs(left.get(coll, []), volatile)
        rn = normalize_docs(right.get(coll, []), volatile)
        if ln != rn:
            only_left = [d for d in ln if d not in rn]
            only_right = [d for d in rn if d not in ln]
            out[coll] = {"only_left": only_left, "only_right": only_right}
    return out
