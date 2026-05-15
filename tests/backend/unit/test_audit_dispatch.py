"""Part 2 Patch P4: audit log integrity tests.

Three invariants enforced:
  1. Write-ahead row exists before tool execution (state="pending").
  2. ``success`` is False when the tool result is missing the success key
     (previous behavior defaulted to True — silent successful writes).
  3. Audit row gets written on both success AND failure paths (no silent gaps).
"""

from __future__ import annotations

import pytest

from backend.services import confirm_tokens
from backend.services.confirm_tokens import (
    _infer_success,
    audit_ai_dispatch,
    audit_ai_dispatch_finalize,
    audit_ai_dispatch_pending,
)


class _FakeAuditCollection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)
        return type("R", (), {"inserted_id": doc.get("_id")})()

    async def update_one(self, q, update):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()):
                d.update(update.get("$set", {}))
                return type("R", (), {"matched_count": 1, "modified_count": 1})()
        return type("R", (), {"matched_count": 0, "modified_count": 0})()


class _FakeDb:
    def __init__(self):
        self.ai_dispatch_audit_log = _FakeAuditCollection()


# ─── _infer_success ─────────────────────────────────────────────────────────

def test_infer_success_explicit_true():
    assert _infer_success({"success": True}) is True


def test_infer_success_missing_key_is_false():
    """Regression for the original bug: defaulted True on missing key."""
    assert _infer_success({}) is False
    assert _infer_success({"data": []}) is False


def test_infer_success_status_ok():
    assert _infer_success({"status": "ok"}) is True
    assert _infer_success({"status": "success"}) is True


def test_infer_success_status_failed():
    assert _infer_success({"status": "failed"}) is False
    assert _infer_success({"status": "error"}) is False


def test_infer_success_error_dict():
    assert _infer_success({"error": "data_unavailable"}) is False


def test_infer_success_none():
    assert _infer_success(None) is False


def test_infer_success_non_dict():
    assert _infer_success("ok") is False
    assert _infer_success([]) is False


# ─── pending + finalize round trip ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_pending_audit_inserts_with_status_pending():
    db = _FakeDb()
    audit_id = await audit_ai_dispatch_pending(
        tool_name="record_fee_payment",
        params={"student_id": "stu-1"},
        user_id="u-1", session_id="s-1",
        confirmed_at=None, school_id="school-x", branch_id="b1",
        db=db,
    )
    row = db.ai_dispatch_audit_log.docs[0]
    assert row["status"] == "pending"
    assert row["success"] is False
    assert row["school_id"] == "school-x"
    assert row["branch_id"] == "b1"
    assert row["id"] == audit_id


@pytest.mark.asyncio
async def test_finalize_marks_success_when_result_success_true():
    db = _FakeDb()
    audit_id = await audit_ai_dispatch_pending(
        tool_name="x", params={}, user_id="u", session_id="s",
        confirmed_at=None, db=db,
    )
    await audit_ai_dispatch_finalize(audit_id=audit_id, result={"success": True}, db=db)
    assert db.ai_dispatch_audit_log.docs[0]["status"] == "success"
    assert db.ai_dispatch_audit_log.docs[0]["success"] is True


@pytest.mark.asyncio
async def test_finalize_marks_failure_when_result_missing_success_key():
    db = _FakeDb()
    audit_id = await audit_ai_dispatch_pending(
        tool_name="x", params={}, user_id="u", session_id="s",
        confirmed_at=None, db=db,
    )
    # Tool returns {"data": [...]} with no success key — must record failure.
    await audit_ai_dispatch_finalize(audit_id=audit_id, result={"data": []}, db=db)
    assert db.ai_dispatch_audit_log.docs[0]["status"] == "failure"
    assert db.ai_dispatch_audit_log.docs[0]["success"] is False


@pytest.mark.asyncio
async def test_finalize_records_error_on_exception_path():
    db = _FakeDb()
    audit_id = await audit_ai_dispatch_pending(
        tool_name="x", params={}, user_id="u", session_id="s",
        confirmed_at=None, db=db,
    )
    await audit_ai_dispatch_finalize(audit_id=audit_id, error="internal:abc-123", db=db)
    row = db.ai_dispatch_audit_log.docs[0]
    assert row["status"] == "failure"
    assert row["success"] is False
    assert row["error"] == "internal:abc-123"


@pytest.mark.asyncio
async def test_legacy_audit_dispatch_uses_new_success_semantics():
    db = _FakeDb()
    await audit_ai_dispatch(
        tool_name="x", params={}, user_id="u", session_id="s",
        confirmed_at=None, result={}, db=db,
    )
    # Pre-Patch-P4 this would have recorded success=True. Now False.
    assert db.ai_dispatch_audit_log.docs[0]["success"] is False
