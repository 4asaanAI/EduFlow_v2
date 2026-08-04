"""Inspection Remediation BLOCK 2 — T8 (NEW-12), the advertised tool list.

Before this block an owner's every chat message carried 107 tool definitions. The
trim removes structural configuration tools from what the model is OFFERED. The
non-negotiable property is that it changes cost and NOTHING about authorization:
an excluded tool must still be authorized, still dispatchable, and still advertised
when it is named explicitly.
"""

from __future__ import annotations

import pytest

from ai.tool_access import is_tool_authorized
from ai.tool_chat_exclusions import EXCLUDE_FOR_ROLE, is_chat_advertised
from ai.tool_functions_v2 import TOOL_REGISTRY

OWNER = {"id": "o1", "role": "owner"}
PRINCIPAL = {"id": "p1", "role": "admin", "sub_category": "principal"}
ACCOUNTANT = {"id": "a1", "role": "admin", "sub_category": "accountant"}
TEACHER = {"id": "t1", "role": "teacher"}


def _advertised(user):
    from routes.chat import _build_llm_tools
    return {t["function"]["name"] for t in _build_llm_tools(user)}


def test_owner_tool_list_is_smaller_than_the_authorized_set():
    authorized = {n for n, d in TOOL_REGISTRY.items() if is_tool_authorized(OWNER, d)}
    advertised = _advertised(OWNER)
    assert advertised < authorized, "the trim did nothing"
    assert len(authorized) - len(advertised) == len(EXCLUDE_FOR_ROLE["owner"])


def test_excluded_tools_are_still_authorized():
    """The whole safety argument for T8: this is a cost change, not a permission change."""
    for name in EXCLUDE_FOR_ROLE["owner"]:
        tool_def = TOOL_REGISTRY.get(name)
        assert tool_def is not None, f"{name} is not a real tool — the exclusion list has rotted"
        assert is_tool_authorized(OWNER, tool_def) is True, f"{name} lost the owner's permission"


def test_an_excluded_tool_is_still_advertised_when_named_explicitly():
    """Suggested actions and the tool panel pass `only={...}` — never trimmed."""
    from routes.chat import _build_llm_tools
    name = sorted(EXCLUDE_FOR_ROLE["owner"])[0]
    tools = _build_llm_tools(OWNER, only={name})
    assert [t["function"]["name"] for t in tools] == [name]


@pytest.mark.parametrize("user", [ACCOUNTANT, TEACHER], ids=["accountant", "teacher"])
def test_smaller_roles_are_untouched(user):
    authorized = {n for n, d in TOOL_REGISTRY.items() if is_tool_authorized(user, d)}
    assert _advertised(user) == authorized


def test_everyday_work_is_never_trimmed():
    """Recording a payment or marking attendance is conversation, not configuration."""
    for name in ("record_fee_payment", "mark_attendance", "apply_discount",
                 "create_student", "draft_document", "get_student_database"):
        assert is_chat_advertised(OWNER, name), f"{name} must stay available in chat"


def test_exclusion_list_contains_no_read_tools():
    """Trimming a read tool would make Flo unable to answer a question. Only the
    deliberate, form-driven writes belong here."""
    from services.ai_action_policy import is_action_tool
    for name in EXCLUDE_FOR_ROLE["owner"]:
        assert is_action_tool(TOOL_REGISTRY[name]), f"{name} is a read tool and must not be trimmed"
