"""Story F.6 — unit tests for the parity normalizer ruleset."""

from __future__ import annotations

import pytest

from tests.backend.parity.normalizer import (
    mask_doc,
    normalize_docs,
    diff_snapshots,
    VOLATILE_FIELDS,
)



def test_mask_drops_volatile_fields():
    doc = {"id": "x", "_id": "y", "student_id": "s1", "status": "present", "created_at": "t"}
    masked = mask_doc(doc)
    assert "id" not in masked and "_id" not in masked and "created_at" not in masked
    assert masked == {"student_id": "s1", "status": "present"}


def test_mask_is_recursive():
    doc = {"a": {"id": "drop", "keep": 1}, "rows": [{"timestamp": "t", "v": 2}]}
    masked = mask_doc(doc)
    assert masked == {"a": {"keep": 1}, "rows": [{"v": 2}]}


def test_normalize_is_order_independent():
    a = [{"student_id": "s2", "status": "absent"}, {"student_id": "s1", "status": "present"}]
    b = [{"student_id": "s1", "status": "present"}, {"student_id": "s2", "status": "absent"}]
    assert normalize_docs(a) == normalize_docs(b)


def test_diff_identical_snapshots_empty():
    left = {"student_attendance": [{"id": "1", "student_id": "s1", "status": "present"}]}
    right = {"student_attendance": [{"id": "2", "student_id": "s1", "status": "present"}]}
    assert diff_snapshots(left, right) == {}


def test_diff_detects_real_difference():
    left = {"c": [{"student_id": "s1", "status": "present"}]}
    right = {"c": [{"student_id": "s1", "status": "absent"}]}
    d = diff_snapshots(left, right)
    assert "c" in d
