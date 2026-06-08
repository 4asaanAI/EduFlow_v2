"""Story F.11 — Phase-1 action-authorization lockdown (Owner + Principal only)."""

from __future__ import annotations

import pytest

from services import ai_action_policy
from services.ai_action_policy import is_action_authorized_phase1, is_action_tool
from routes.chat import _is_tool_authorized

pytestmark = pytest.mark.asyncio

OWNER = {"id": "o1", "role": "owner"}
PRINCIPAL = {"id": "p1", "role": "admin", "sub_category": "principal"}
ACCOUNTANT = {"id": "a1", "role": "admin", "sub_category": "accountant"}
TEACHER = {"id": "t1", "role": "teacher"}
STUDENT = {"id": "s1", "role": "student"}

WRITE_TOOL = {"roles": ["owner", "admin", "teacher"], "dispatch_type": "write", "requires_confirmation": True}
READ_TOOL = {"roles": ["owner", "admin", "teacher", "student"]}


def test_is_action_tool_detects_writes():
    assert is_action_tool(WRITE_TOOL) is True
    assert is_action_tool(READ_TOOL) is False


def test_owner_and_principal_may_act():
    assert is_action_authorized_phase1(OWNER, WRITE_TOOL) is True
    assert is_action_authorized_phase1(PRINCIPAL, WRITE_TOOL) is True


def test_other_staff_refused_for_writes_in_phase1():
    assert is_action_authorized_phase1(TEACHER, WRITE_TOOL) is False
    assert is_action_authorized_phase1(ACCOUNTANT, WRITE_TOOL) is False


def test_reads_unaffected_for_everyone():
    for u in (TEACHER, ACCOUNTANT, STUDENT):
        assert is_action_authorized_phase1(u, READ_TOOL) is True


def test_is_tool_authorized_enforces_lockdown_on_writes():
    # teacher is in roles[] for the write tool but the lockdown refuses the action
    assert _is_tool_authorized(TEACHER, WRITE_TOOL) is False
    assert _is_tool_authorized(OWNER, WRITE_TOOL) is True
    assert _is_tool_authorized(PRINCIPAL, WRITE_TOOL) is True
    # reads still pass for teacher/student
    assert _is_tool_authorized(TEACHER, READ_TOOL) is True
    assert _is_tool_authorized(STUDENT, READ_TOOL) is True


def test_is_tool_authorized_preserves_subcategory_gate():
    sub_gated = {"roles": ["owner", "admin"], "sub_categories": ["principal"]}
    # read tool gated to principal sub_category: accountant blocked, principal allowed
    assert _is_tool_authorized(ACCOUNTANT, sub_gated) is False
    assert _is_tool_authorized(PRINCIPAL, sub_gated) is True
    assert _is_tool_authorized(OWNER, sub_gated) is True


def test_lockdown_single_switch_widens_in_phase2(monkeypatch):
    # Phase 2 (Epic H) flips one flag — no engine change. Verify the switch lifts.
    monkeypatch.setattr(ai_action_policy, "LOCKDOWN_ENABLED", False)
    assert is_action_authorized_phase1(TEACHER, WRITE_TOOL) is True
