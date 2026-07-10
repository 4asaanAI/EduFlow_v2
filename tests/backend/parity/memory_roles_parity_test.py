"""R10.5 AC3 — MEMORY_ROLES ↔ advertised-behavior parity guard.

Sibling to the prompt↔registry parity gate: it keeps the self-learning ROLE policy
honest so advertised behavior matches actual gating. Two merge-blocking invariants:

 1. Capture ⊆ Recall — the assistant can never auto-LEARN from a role it can't even
    RECALL for (R10.5 AC2). A capture-widened role that isn't recall-widened is a
    policy bug.
 2. Default is Owner/Principal-only — both extra-role sets ship EMPTY, so widening is
    a deliberate, reviewed config change (and, per AC3, must land together with the
    matching per-role prompt disclosure). If this fails, someone widened the surface;
    the accompanying prompt/disclosure update must be reviewed in the same change.
"""

from __future__ import annotations

from services.memory import policy


def test_capture_is_subset_of_recall():
    assert policy.MEMORY_CAPTURE_EXTRA_ROLES <= policy.MEMORY_RECALL_EXTRA_ROLES, (
        "MEMORY_CAPTURE_EXTRA_ROLES must be a subset of MEMORY_RECALL_EXTRA_ROLES — "
        "a role cannot be auto-learned-from without also being recall-enabled (R10.5 AC2)."
    )


def test_widening_is_off_by_default():
    # Ships Owner/Principal-only. If you intentionally widen, update this guard AND
    # the per-role prompt disclosure in the SAME change (AC3), then adjust this test.
    assert policy.MEMORY_RECALL_EXTRA_ROLES == set()
    assert policy.MEMORY_CAPTURE_EXTRA_ROLES == set()
