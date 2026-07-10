"""Post-merge epic-close review fixes for Epics R5, R6, R7.

Each test is a fails-before / passes-after regression guard for a defect found
during the adversarial re-review of the merged R5–R7 diff. Grouped by the epic
whose code the fix touches.

Findings covered:
  R5-1 (Med)  reversed/degenerate coordinator range no longer widens to ALL classes
  R5-2 (Low)  mis-cased / aliased admin sub_category gets its real chat context
  R5-3 (Low)  KG in-charge class regex is \\b-anchored ("KGeography" excluded)
  R6-1 (Low)  bare "note down <domain object>" falls through (not a memory save)
  R6-2 (Low)  degraded keyword-only recall WARNs only when vectors are enabled
  R7-1 (Low)  future-dated pending defaulter never reports negative days_overdue
  R7-2 (Low)  event_date is normalized to ISO (lexicographic window compare is safe)
  R7-3 (Low)  exam pass-rate is "N/A" when not every graded student is scorable
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

from tests.backend.conftest import FakeCollection, FakeDb

pytestmark = pytest.mark.asyncio


def _make_db(**overrides):
    db = FakeDb()
    for attr, docs in overrides.items():
        setattr(db, attr, FakeCollection(list(docs)))
    return db


# ── R5-1: reversed/degenerate coordinator range must fail closed ────────────

async def test_reversed_coordinator_range_resolves_to_no_classes():
    """A range like "5-1" produced an empty alternation regex ("^()\\b") that
    matched EVERY class name — widening the coordinator to the whole branch.
    It must now resolve to zero classes (deny by default)."""
    from ai import scope_resolver as rl
    db = _make_db(
        staff=[{"id": "s-co", "user_id": "u-co", "is_active": True, "role": "teacher",
                "sub_category": "coordinator", "coordinator_range": "5-1"}],
        classes=[
            {"id": "c1", "name": "Class 1", "section": "A"},
            {"id": "c10", "name": "Class 10", "section": "A"},
            {"id": "n", "name": "Nursery", "section": "A"},
        ],
    )
    scope = await rl.resolve_scope({"id": "u-co", "role": "teacher"}, db)
    assert scope.class_ids == []  # NOT every class in the branch


async def test_valid_single_coordinator_range_still_resolves():
    """Guard the fix didn't break a valid single-class range ("5-5")."""
    from ai import scope_resolver as rl
    db = _make_db(
        staff=[{"id": "s-co", "user_id": "u-co", "is_active": True, "role": "teacher",
                "sub_category": "coordinator", "coordinator_range": "5-5"}],
        classes=[
            {"id": "c5", "name": "Class 5", "section": "A"},
            {"id": "c50", "name": "Class 50", "section": "A"},
        ],
    )
    scope = await rl.resolve_scope({"id": "u-co", "role": "teacher"}, db)
    assert scope.class_ids == ["c5"]


# ── R5-3: KG in-charge class regex is \b-anchored ───────────────────────────

async def test_kg_incharge_regex_excludes_non_kg_class_names():
    """"KG"/"Nursery" must match "KG-A"/"Nursery" but never "KGeography"."""
    from ai import scope_resolver as rl
    db = _make_db(
        staff=[{"id": "s-kg", "user_id": "u-kg", "is_active": True, "role": "teacher",
                "sub_category": "kg_incharge", "is_incharge": True}],
        classes=[
            {"id": "kga", "name": "KG-A", "section": "A", "class_teacher_id": "u-kg"},
            {"id": "bad", "name": "KGeography", "section": "A", "class_teacher_id": "u-kg"},
        ],
    )
    scope = await rl.resolve_scope({"id": "u-kg", "role": "teacher"}, db)
    assert scope.class_ids == ["kga"]


# ── R5-2: mis-cased / aliased admin sub_category → its real context ─────────

async def test_miscased_accountant_gets_accounts_context_not_minimal():
    """Before the fix, sub_category="Accountant"/"accounts" fell through to the
    minimal context even though scope_resolver grants financial tool access."""
    import ai.context_builder as cb
    db = _make_db(staff=[{
        "id": "acc-1", "user_id": "u-acc", "schoolId": "aaryans-joya",
        "role": "admin", "sub_category": "Accountant", "is_active": True,
    }])
    marker = {"role": "accounts", "_marker": "accounts_ctx"}
    with patch.object(cb, "get_db", lambda: db), \
         patch.object(cb, "_build_accounts_context", AsyncMock(return_value=dict(marker))):
        ctx = await cb.build_school_context("admin", "u-acc")
    assert ctx.get("_marker") == "accounts_ctx"
    assert "no school-wide operational data" not in ctx.get("note", "")


async def test_unknown_admin_subcategory_still_minimal():
    """The alias normalization must NOT promote a genuinely unknown sub_category
    (it_tech/maintenance/…) into an operational context."""
    import ai.context_builder as cb
    db = _make_db(staff=[{
        "id": "it-1", "user_id": "u-it", "schoolId": "aaryans-joya",
        "role": "admin", "sub_category": "it_tech", "is_active": True,
    }])
    with patch.object(cb, "get_db", lambda: db):
        ctx = await cb.build_school_context("admin", "u-it")
    assert "no school-wide operational data" in ctx.get("note", "")


# ── R6-1: bare "note down <domain object>" is NOT a memory save ─────────────

def test_note_down_domain_object_falls_through():
    from services.memory import extractor
    assert extractor.parse_inline_remember("note down attendance for class 5") is None
    assert extractor.parse_inline_remember("jot down the marks for the exam") is None


def test_note_down_with_memory_connector_still_saves():
    from services.memory import extractor
    assert extractor.parse_inline_remember(
        "note down that the owner prefers reports at 5pm"
    ) == "the owner prefers reports at 5pm"
    assert extractor.parse_inline_remember(
        "jot down about the annual day venue"
    ) == "the annual day venue"


# ── R6-2: degraded recall log is gated on vectors being enabled ─────────────

async def test_degraded_recall_warns_only_when_vectors_enabled(caplog):
    """With vectors intentionally OFF (default), keyword-only recall must NOT
    spam a WARNING every turn; when the flag is ON but the index is down it
    MUST warn so operators notice the degradation (XM10)."""
    from services.memory import store as memory_store
    from services.actor_context import actor_ctx_from_user

    db = FakeDb()
    db.ai_memories = FakeCollection()
    ctx = actor_ctx_from_user(
        {"id": "owner-1", "role": "owner", "name": "T", "branch_id": "branch-a"},
        school_id="aaryans-joya", branch_id="branch-a",
    )
    await memory_store.add_memory(db, ctx, text="reports at 5pm")

    # Vectors disabled (the shipped default): no WARNING.
    with patch.object(memory_store, "vector_enabled", lambda: False):
        with caplog.at_level(logging.WARNING, logger="services.memory.store"):
            caplog.clear()
            await memory_store.recall(db, ctx, "reports")
            assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    # Vectors enabled but the index is unavailable: a real degradation → WARNING.
    with patch.object(memory_store, "vector_enabled", lambda: True):
        with caplog.at_level(logging.WARNING, logger="services.memory.store"):
            caplog.clear()
            await memory_store.recall(db, ctx, "reports")
            assert any("keyword-only" in r.getMessage() for r in caplog.records)


# ── R7-1: future-dated pending defaulter never reports negative overdue ─────

async def test_future_dated_pending_defaulter_days_overdue_clamped(monkeypatch):
    from ai.tool_functions_v2 import tool_get_fee_defaulters
    import ai.tool_functions_v2 as _mod

    db = type("FakeDb", (), {
        "fee_transactions": FakeCollection([
            {"student_id": "s1", "status": "pending", "amount": 400, "due_date": "2027-01-01",
             "schoolId": "aaryans-joya"},
        ]),
        "students": FakeCollection([
            {"id": "s1", "name": "Future Payer", "class_id": "c1", "schoolId": "aaryans-joya"},
        ]),
        "classes": FakeCollection([
            {"id": "c1", "name": "5", "section": "A", "schoolId": "aaryans-joya"},
        ]),
    })()
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_fee_defaulters({}, {"id": "u1", "role": "owner"}, scope=None)
    rows = result.get("data", [])
    assert rows and rows[0]["days_overdue"] == 0  # never negative


# ── R7-2: event_date normalized to ISO ──────────────────────────────────────

def test_normalize_iso_date_coerces_and_rejects():
    from ai.tool_functions_v2 import _normalize_iso_date
    assert _normalize_iso_date("2026-07-15") == "2026-07-15"
    assert _normalize_iso_date("15/07/2026") == "2026-07-15"   # dd/mm/yyyy (India)
    assert _normalize_iso_date("2026-07-15T09:30:00") == "2026-07-15"
    assert _normalize_iso_date("next tuesday") is None
    assert _normalize_iso_date("") is None
    assert _normalize_iso_date(None) is None


# ── R7-3: exam pass-rate honest when not all graded rows are scorable ───────

async def test_exam_pass_rate_na_when_partial_scorable(monkeypatch):
    from ai.tool_functions_v2 import tool_get_exam_results_summary
    import ai.tool_functions_v2 as _mod

    db = type("FakeDb", (), {
        "exams": FakeCollection([
            {"id": "e1", "name": "Unit Test", "subject": "Math", "exam_date": "2026-05-01",
             "schoolId": "aaryans-joya"},  # exam max_marks unknown
        ]),
        "exam_results": FakeCollection([
            {"exam_id": "e1", "student_id": "s1", "marks_obtained": 40, "max_marks": 50,
             "schoolId": "aaryans-joya"},
            {"exam_id": "e1", "student_id": "s2", "marks_obtained": 30,
             "schoolId": "aaryans-joya"},  # no max → not scorable
        ]),
    })()
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_exam_results_summary({}, {"id": "u1", "role": "owner"}, scope=None)
    row = result["data"][0]
    assert row["students"] == 2
    assert row["pass_rate"] == "N/A"  # subset rate would mislead against students=2
