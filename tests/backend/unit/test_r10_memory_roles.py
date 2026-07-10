"""Epic R10.5 — MEMORY_ROLES policy switch (mirrors LOCKDOWN_ENABLED).

- AC1: a single config switch controls which roles get memory/skills; widening is a
       config change, not an engine change.
- AC2: a recall-widened role gets READ-RECALL ONLY (no auto-capture) until a separate
       explicit decision adds it to capture. Capture ⊆ Recall is a hard invariant.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from services.actor_context import actor_ctx_from_user
from services.memory import policy
from services.memory import can_capture_memories, can_recall_memories, is_memory_subject
from services.memory import chat_integration
from tests.backend.conftest import FakeDb

OWNER = {"id": "o1", "role": "owner"}
PRINCIPAL = {"id": "p1", "role": "admin", "sub_category": "principal"}
TEACHER = {"id": "t1", "role": "teacher"}
ACCOUNTANT = {"id": "a1", "role": "admin", "sub_category": "accountant"}


def test_default_only_owner_and_principal():
    for u in (OWNER, PRINCIPAL):
        assert can_recall_memories(u) and can_capture_memories(u)
    for u in (TEACHER, ACCOUNTANT):
        assert not can_recall_memories(u)
        assert not can_capture_memories(u)


def test_is_memory_subject_is_capture_predicate():
    assert is_memory_subject(OWNER) is True
    assert is_memory_subject(TEACHER) is False


def test_widening_recall_is_read_only_not_capture(monkeypatch):
    # AC1/AC2: add teacher to recall ONLY.
    monkeypatch.setattr(policy, "MEMORY_RECALL_EXTRA_ROLES", {"teacher"})
    monkeypatch.setattr(policy, "MEMORY_CAPTURE_EXTRA_ROLES", set())
    assert can_recall_memories(TEACHER) is True
    assert can_capture_memories(TEACHER) is False  # recall widening alone ≠ capture


def test_capture_requires_both_sets(monkeypatch):
    # AC2 invariant: capture needs BOTH recall + capture widening.
    monkeypatch.setattr(policy, "MEMORY_RECALL_EXTRA_ROLES", set())
    monkeypatch.setattr(policy, "MEMORY_CAPTURE_EXTRA_ROLES", {"teacher"})
    assert can_capture_memories(TEACHER) is False  # capture-only, no recall → denied
    monkeypatch.setattr(policy, "MEMORY_RECALL_EXTRA_ROLES", {"teacher"})
    assert can_capture_memories(TEACHER) is True  # now both → allowed


def test_admin_subrole_token(monkeypatch):
    monkeypatch.setattr(policy, "MEMORY_RECALL_EXTRA_ROLES", {"admin:accountant"})
    assert can_recall_memories(ACCOUNTANT) is True
    # a different admin sub-role is NOT covered
    assert can_recall_memories({"id": "x", "role": "admin", "sub_category": "receptionist"}) is False


async def test_recall_context_block_gated_on_recall_predicate(monkeypatch):
    db = FakeDb()
    # seed a memory owned by the teacher
    db.ai_memories.docs.append({
        "id": "m1", "user_id": "t1", "schoolId": "aaryans-joya", "text": "teacher prefers morning classes",
        "category": "preference", "superseded": False, "confidence": 0.9, "updated_at_ts": 100.0,
    })
    # not widened → no recall block
    assert await chat_integration.recall_context_block(db, TEACHER, "morning classes") == ""
    # widen recall → block appears
    monkeypatch.setattr(policy, "MEMORY_RECALL_EXTRA_ROLES", {"teacher"})
    block = await chat_integration.recall_context_block(db, TEACHER, "morning classes")
    assert "morning classes" in block
