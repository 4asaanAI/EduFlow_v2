"""Deferred tool loading - the token saving, and the guarantees that make it safe.

The one thing this must never do is turn a cost optimisation into a permission change,
or into Flo claiming it cannot do something it can. Both have happened here before: the
role-based trim this replaces once told the school's owner an operation was "not
available to me" about something they were fully authorised to do.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")

from tests.backend.conftest import APP_AVAILABLE

if not APP_AVAILABLE:
    pytest.skip("App not importable", allow_module_level=True)

from ai import tool_search
from ai.tool_access import is_tool_authorized
from ai.tool_functions_v2 import TOOL_REGISTRY
from routes.chat import _authorized_tool_names, _build_llm_tools

OWNER = {"id": "o1", "role": "owner", "name": "Aman", "branch_id": "branch-joya"}
PRINCIPAL = {"id": "p1", "role": "admin", "sub_category": "principal",
             "name": "Meena", "branch_id": "branch-joya"}
TEACHER = {"id": "t1", "role": "teacher", "name": "Ravi", "branch_id": "branch-joya"}
STUDENT = {"id": "s1", "role": "student", "name": "Kid", "branch_id": "branch-joya"}


@pytest.fixture(autouse=True)
def _enabled(monkeypatch):
    monkeypatch.setenv("EDUFLOW_TOOL_SEARCH", "1")


def _tokens(user, unlocked=None):
    return len(json.dumps(_build_llm_tools(user, unlocked=unlocked))) // 4


# ─── It must not change who can do what ──────────────────────────────────────

def test_deferring_does_not_change_authorization():
    """The authorized set is identical whether or not deferral is on."""
    for user in (OWNER, PRINCIPAL, TEACHER, STUDENT):
        allowed = {n for n, d in TOOL_REGISTRY.items() if is_tool_authorized(user, d)}
        os.environ["EDUFLOW_TOOL_SEARCH"] = "0"
        off = {n for n, d in TOOL_REGISTRY.items() if is_tool_authorized(user, d)}
        os.environ["EDUFLOW_TOOL_SEARCH"] = "1"
        assert allowed == off


def test_search_never_returns_a_tool_the_caller_cannot_use():
    """A student searching for fee writes must find nothing - deferral is not a door."""
    available = {n: d for n, d in TOOL_REGISTRY.items()
                 if is_tool_authorized(STUDENT, d) and not tool_search.is_core(n)}
    for name in tool_search.rank("record fee payment delete student", available, limit=10):
        assert is_tool_authorized(STUDENT, TOOL_REGISTRY[name])


def test_every_deferred_tool_is_reachable_by_search():
    """Nothing may become invisible: each deferred tool must be findable by its name.

    This is the guarantee the old hide-by-role trim could not make.
    """
    available = {n: d for n, d in TOOL_REGISTRY.items()
                 if is_tool_authorized(OWNER, d) and not tool_search.is_core(n)}
    unreachable = [
        name for name in available
        if name not in tool_search.rank(f"select:{name}", available, limit=1)
    ]
    assert unreachable == []


def test_catalogue_lists_every_deferred_tool():
    names = _authorized_tool_names(OWNER)
    block = tool_search.catalogue_block(names)
    for name in tool_search.deferred_names(names):
        assert name in block


# ─── The saving ──────────────────────────────────────────────────────────────

def test_owner_turn_is_much_cheaper(monkeypatch):
    monkeypatch.setenv("EDUFLOW_TOOL_SEARCH", "0")
    before = _tokens(OWNER)
    monkeypatch.setenv("EDUFLOW_TOOL_SEARCH", "1")
    after = _tokens(OWNER) + len(tool_search.catalogue_block(_authorized_tool_names(OWNER))) // 4
    assert after < before / 3, f"expected a large saving, got {before} -> {after}"


def test_core_tools_are_always_advertised():
    advertised = {t["function"]["name"] for t in _build_llm_tools(OWNER)}
    for name in tool_search.core_names():
        if name in TOOL_REGISTRY and is_tool_authorized(OWNER, TOOL_REGISTRY[name]):
            assert name in advertised


def test_search_tools_itself_is_always_advertised():
    """If the model cannot see the search tool, every deferred tool is unreachable."""
    for user in (OWNER, PRINCIPAL, TEACHER):
        advertised = {t["function"]["name"] for t in _build_llm_tools(user)}
        assert "search_tools" in advertised


def test_unlocked_tools_become_advertised():
    advertised = {t["function"]["name"] for t in _build_llm_tools(OWNER)}
    assert "get_expenses" not in advertised
    unlocked = {t["function"]["name"] for t in _build_llm_tools(OWNER, unlocked={"get_expenses"})}
    assert "get_expenses" in unlocked


def test_kill_switch_restores_the_old_behaviour(monkeypatch):
    monkeypatch.setenv("EDUFLOW_TOOL_SEARCH", "0")
    advertised = {t["function"]["name"] for t in _build_llm_tools(OWNER)}
    assert "get_expenses" in advertised
    assert len(advertised) > 100


# ─── Ranking ─────────────────────────────────────────────────────────────────

def _owner_available():
    return {n: d for n, d in TOOL_REGISTRY.items()
            if is_tool_authorized(OWNER, d) and not tool_search.is_core(n)}


@pytest.mark.parametrize("query,expected", [
    ("expenses", "get_expenses"),
    ("bus route transport", "get_transport_status"),
    ("salary payroll", "disburse_salary"),
    ("whatsapp template", "get_message_templates"),
    ("house points", "award_house_points"),
])
def test_plain_keyword_search_finds_the_obvious_tool(query, expected):
    assert expected in tool_search.rank(query, _owner_available(), limit=8)


def test_select_form_returns_exact_names():
    got = tool_search.rank("select:get_expenses,update_expense", _owner_available())
    assert got == ["get_expenses", "update_expense"]


def test_select_form_ignores_unknown_names():
    got = tool_search.rank("select:get_expenses,not_a_real_tool", _owner_available())
    assert got == ["get_expenses"]


def test_required_word_form_restricts_by_name():
    got = tool_search.rank("+transport bus route", _owner_available(), limit=10)
    assert got
    assert all("transport" in n for n in got)


def test_empty_query_returns_nothing():
    assert tool_search.rank("", _owner_available()) == []


def test_nonsense_query_returns_nothing():
    assert tool_search.rank("zzzqqqxyz", _owner_available()) == []


# ─── The tool itself ─────────────────────────────────────────────────────────

async def test_search_tools_returns_usable_schemas():
    result = await TOOL_REGISTRY["search_tools"]["fn"]({"query": "expenses"}, OWNER, None)
    assert result["success"] is True
    row = result["data"][0]
    assert row["schema"]["type"] == "function"
    assert row["schema"]["function"]["name"] == row["name"]


async def test_search_tools_says_so_when_nothing_matches():
    """It must tell the model to be honest rather than invent a tool."""
    result = await TOOL_REGISTRY["search_tools"]["fn"]({"query": "zzzqqqxyz"}, OWNER, None)
    assert result["data"] == []
    assert "not something you can do" in result["message"]


async def test_search_tools_never_returns_core_tools():
    """Core tools are already loaded; returning them again would waste the saving."""
    result = await TOOL_REGISTRY["search_tools"]["fn"](
        {"query": "select:get_daily_brief,get_expenses"}, OWNER, None
    )
    names = [r["name"] for r in result["data"]]
    assert "get_daily_brief" not in names
    assert "get_expenses" in names


async def test_student_search_cannot_reach_owner_tools():
    result = await TOOL_REGISTRY["search_tools"]["fn"](
        {"query": "select:delete_student,record_fee_payment"}, STUDENT, None
    )
    assert result["data"] == []


# ─── "Nothing gets lost" - the guarantee, across EVERY role ──────────────────

ALL_PROFILES = [
    ({"id": "u", "role": "owner", "branch_id": "branch-joya"}, "owner"),
    ({"id": "u", "role": "admin", "sub_category": "principal", "branch_id": "branch-joya"}, "principal"),
    ({"id": "u", "role": "admin", "sub_category": "accountant", "branch_id": "branch-joya"}, "accountant"),
    ({"id": "u", "role": "admin", "sub_category": "management", "branch_id": "branch-joya"}, "management"),
    ({"id": "u", "role": "admin", "sub_category": "receptionist", "branch_id": "branch-joya"}, "receptionist"),
    ({"id": "u", "role": "admin", "sub_category": "transport_head", "branch_id": "branch-joya"}, "transport_head"),
    ({"id": "u", "role": "teacher", "sub_category": "class_teacher", "branch_id": "branch-joya"}, "class_teacher"),
    ({"id": "u", "role": "teacher", "sub_category": "subject_teacher", "branch_id": "branch-joya"}, "subject_teacher"),
    ({"id": "u", "role": "student", "branch_id": "branch-joya"}, "student"),
    ({"id": "u", "role": "parent", "branch_id": "branch-joya"}, "parent"),
]


@pytest.mark.parametrize("user,label", ALL_PROFILES, ids=[p[1] for p in ALL_PROFILES])
def test_nothing_is_lost_every_authorized_tool_stays_reachable(user, label):
    """THE guarantee: for every role, each tool the person may use is either loaded
    up front or named in the catalogue AND retrievable by search. A tool that is
    neither would be invisible - Flo would deny a capability it actually has, which
    is precisely the failure the old hide-by-role trim caused."""
    names = _authorized_tool_names(user)
    advertised = {t["function"]["name"] for t in _build_llm_tools(user)}
    catalogue = tool_search.catalogue_block(names)
    available = {n: d for n, d in TOOL_REGISTRY.items()
                 if is_tool_authorized(user, d) and not tool_search.is_core(n)}

    lost = []
    for name in names:
        if name in advertised:
            continue
        if name not in catalogue:
            lost.append((name, "not in catalogue"))
        elif tool_search.rank(f"select:{name}", available, limit=1) != [name]:
            lost.append((name, "not retrievable by search"))
    assert lost == [], f"{label}: these tools became unreachable: {lost}"


@pytest.mark.parametrize("user,label", ALL_PROFILES, ids=[p[1] for p in ALL_PROFILES])
def test_authorized_set_is_byte_identical_with_and_without_deferral(user, label):
    """Deferral must not add or remove a single permission for anyone."""
    import os as _os
    before = {n for n, d in TOOL_REGISTRY.items() if is_tool_authorized(user, d)}
    _os.environ["EDUFLOW_TOOL_SEARCH"] = "0"
    try:
        after = {n for n, d in TOOL_REGISTRY.items() if is_tool_authorized(user, d)}
        full = {t["function"]["name"] for t in _build_llm_tools(user)}
    finally:
        _os.environ["EDUFLOW_TOOL_SEARCH"] = "1"
    assert before == after
    # With deferral off, the advertised list is the full authorized-and-advertisable
    # set - proving the catalogue path is the ONLY thing deferral changes.
    assert full <= before
