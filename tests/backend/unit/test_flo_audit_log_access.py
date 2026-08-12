from __future__ import annotations

"""Flo must obey the same action-log rule as the screens and the web address.

Owner request 10 (2026-08-06) cut the action log down to the owner and the principal.
That was applied to `routes/audit.py`, to the menu in `Sidebar.js` and to the per-tool
allow-list in `toolPermissions.js` - but NOT to Flo, and the drift ran in BOTH
directions, which is why it survived a review:

  - An `it_tech` admin who had lost the screen could still ask Flo for the log, and
    Flo's own role rules told them they could.
  - The principal, who IS allowed the log and has it on screen, was never offered it
    by Flo at all.

A rule enforced on three of four doors is not enforced. These tests pin the fourth.
"""

import pytest

from ai.prompts import _resolve_tools
from ai.tool_functions_v2 import TOOL_REGISTRY, tool_query_audit_log
from routes.audit import AUDIT_READER_SUB_CATEGORIES

OWNER = {"id": "own-1", "role": "owner", "name": "Aman Litt"}
PRINCIPAL = {"id": "pri-1", "role": "admin", "sub_category": "principal", "name": "Adesh Singh"}
IT_TECH = {"id": "it-1", "role": "admin", "sub_category": "it_tech", "name": "IT"}
MANAGEMENT = {"id": "mgt-1", "role": "admin", "sub_category": "management", "name": "Mgmt"}
ACCOUNTANT = {"id": "acc-1", "role": "admin", "sub_category": "accountant", "name": "Accounts"}
TEACHER = {"id": "tch-1", "role": "teacher", "name": "Teacher"}
STUDENT = {"id": "stu-1", "role": "student", "name": "Student"}


def _tool_names(role: str, sub_category=None):
    return {t["name"] for t in _resolve_tools(role, sub_category)}


# ── The offer side: Flo must not advertise what it will then refuse ──────────────

def test_the_owner_and_the_principal_are_offered_the_action_log():
    assert "query_audit_log" in _tool_names("owner", None)
    assert "query_audit_log" in _tool_names("admin", "principal"), (
        "the principal is allowed the log and has it on screen, so Flo must offer it"
    )


@pytest.mark.parametrize("sub_category", ["it_tech", "management", "accountant"])
def test_other_admins_are_not_offered_the_action_log(sub_category):
    """Offering a tool that will only refuse is worse than not offering it: the person
    is invited to ask, and then told no."""
    assert "query_audit_log" not in _tool_names("admin", sub_category)


@pytest.mark.parametrize("role", ["teacher", "student", "parent"])
def test_teachers_students_and_parents_are_not_offered_the_action_log(role):
    assert "query_audit_log" not in _tool_names(role, None)


def test_the_registry_no_longer_authorises_teachers_and_students():
    """The registry is the real gate; the prompt list is only the shop window. Both
    had to change, and this is the one that actually enforces."""
    roles = TOOL_REGISTRY["query_audit_log"]["roles"]
    assert set(roles) == {"owner", "admin"}, roles


# ── The enforcement side: the tool itself refuses ────────────────────────────────

@pytest.mark.parametrize("user", [IT_TECH, MANAGEMENT, ACCOUNTANT, TEACHER, STUDENT])
async def test_the_tool_refuses_anyone_outside_the_rule(user, fake_db, monkeypatch):
    """And it must refuse as a DENIAL, not as an empty result. "There is nothing there"
    would be a confident wrong answer about the school's own records (R4.3/M2)."""
    monkeypatch.setattr("ai.tool_functions_v2.get_db", lambda: fake_db)
    result = await tool_query_audit_log({}, user)
    assert result["success"] is False
    assert result["denied"] is True
    assert "owner and principal" in result["message"].lower()


@pytest.mark.parametrize("user", [OWNER, PRINCIPAL])
async def test_the_owner_and_principal_are_let_through(user, fake_db, monkeypatch):
    monkeypatch.setattr("ai.tool_functions_v2.get_db", lambda: fake_db)
    fake_db.audit_logs.docs[:] = []
    result = await tool_query_audit_log({}, user)
    assert result.get("denied") is not True, result


async def test_a_legacy_admin_with_no_sub_category_is_not_audit_reader(fake_db, monkeypatch):
    monkeypatch.setattr("ai.tool_functions_v2.get_db", lambda: fake_db)
    fake_db.audit_logs.docs[:] = []
    legacy = {"id": "old-1", "role": "admin", "name": "Legacy Admin"}
    result = await tool_query_audit_log({}, legacy)
    assert result.get("denied") is True
    assert AUDIT_READER_SUB_CATEGORIES == ("principal",)


def test_flo_and_the_route_share_one_list_rather_than_two_copies():
    """The whole reason this defect existed is that the rule was written down more than
    once. If someone re-states the sub-categories inside the tool instead of importing
    them, this is the test that should have caught it."""
    import inspect

    source = inspect.getsource(tool_query_audit_log)
    assert "AUDIT_READER_SUB_CATEGORIES" in source, (
        "the tool must import the route's list, not restate it"
    )
