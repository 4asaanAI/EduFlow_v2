"""Epic R3 — Prompt ↔ Registry Parity (behavior tier).

Covers the runtime behavior behind the parity fixes: the newly-implemented
get_announcements tool (H2), the canonical accountant sub_category routing for
both tools and context (C4), and the award_house_points schema alignment (H1).
The static drift gate lives in tests/backend/parity/prompt_registry_parity_test.py.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


# ── R3.3 (H2): get_announcements is real, student-safe, published-only ─────────

def _ann(**kw):
    base = {
        "id": kw.get("id", "a1"),
        "schoolId": "aaryans-joya",
        "title": "T",
        "content": "C",
        "audience_type": "all",
        "target_roles": ["student", "teacher", "admin", "parent"],
        "is_draft": False,
        "sent_at": datetime.now().isoformat(),
        "created_at": datetime.now().isoformat(),
    }
    base.update(kw)
    return base


async def test_get_announcements_returns_published_visible(monkeypatch):
    from ai.tool_functions_v2 import tool_get_announcements
    import ai.tool_functions_v2 as _mod

    docs = [
        _ann(id="pub", title="Sports Day"),
        _ann(id="draft", title="Draft", is_draft=True),           # not visible
        _ann(id="pending", title="Pending", sent_at=None),        # not visible
        _ann(id="staff", title="Staff only", audience_type="staff",
             target_roles=["admin", "teacher"]),                  # wrong audience
    ]
    db = type("FakeDb", (), {"announcements": FakeCollection(docs)})()
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_announcements(
        params={"days": 30}, user={"id": "s1", "role": "student"}, scope=None,
    )
    assert result["success"] is True
    titles = {d["title"] for d in result["data"]}
    assert titles == {"Sports Day"}  # only the published, student-audience one


async def test_get_announcements_empty_is_not_a_crash(monkeypatch):
    from ai.tool_functions_v2 import tool_get_announcements
    import ai.tool_functions_v2 as _mod

    db = type("FakeDb", (), {"announcements": FakeCollection([])})()
    monkeypatch.setattr(_mod, "get_db", lambda: db)
    result = await tool_get_announcements(
        params={}, user={"id": "s1", "role": "student"}, scope=None,
    )
    # _empty_result convention — no exception, clear message.
    assert "announcement" in result.get("message", "").lower()


async def test_get_announcements_registered_for_student():
    from ai.tool_functions_v2 import TOOL_REGISTRY
    assert "get_announcements" in TOOL_REGISTRY
    assert TOOL_REGISTRY["get_announcements"]["roles"] == ["student"]


# ── R3.1 (C4): accountant routing (tools + context), no principal leak ─────────

def test_accountant_resolves_to_accounts_tools():
    from ai.prompts import _resolve_tools, TOOL_RECORD_FEE_PAYMENT, TOOL_APPROVE_LEAVE
    tools = _resolve_tools("admin", "accountant")
    assert TOOL_RECORD_FEE_PAYMENT in tools
    assert TOOL_APPROVE_LEAVE not in tools  # principal-only must not leak to accountant


async def test_accountant_context_is_accounts_not_principal(monkeypatch):
    """C4: an accountant must get the accounts-scoped context, never the
    principal context (which carries leave/attendance over-exposure)."""
    import ai.context_builder as cb

    calls = []

    async def _fake_accounts(db, today):
        calls.append("accounts")
        return {"scope": "accounts"}

    async def _fake_principal(db, today):
        calls.append("principal")
        return {"scope": "principal"}

    staff_doc = {"user_id": "u1", "sub_category": "accountant", "schoolId": "aaryans-joya"}
    db = type("FakeDb", (), {
        "school_settings": FakeCollection([]),
        "academic_years": FakeCollection([]),
        "staff": FakeCollection([staff_doc]),
    })()

    monkeypatch.setattr(cb, "get_db", lambda: db)
    monkeypatch.setattr(cb, "_build_accounts_context", _fake_accounts)
    monkeypatch.setattr(cb, "_build_principal_context", _fake_principal)

    ctx = await cb.build_school_context("admin", "u1")
    assert ctx["scope"] == "accounts"
    assert calls == ["accounts"]  # principal builder never called


# ── R3.2 (H1): award_house_points advertises what the impl actually needs ──────

def test_award_house_points_schema_matches_impl():
    from ai.prompts import TOOL_AWARD_HOUSE_POINTS
    from ai.tool_functions_v2 import TOOL_REGISTRY

    prompt_params = set(TOOL_AWARD_HOUSE_POINTS["params_schema"].keys())
    reg_params = set(TOOL_REGISTRY["award_house_points"]["params_schema"].keys())
    # Prompt now teaches student_name (impl requirement), not the old house_name ghost.
    assert "student_name" in prompt_params
    assert "house_name" not in prompt_params
    # category was never persisted → dropped from both surfaces.
    assert "category" not in prompt_params
    assert "category" not in reg_params
