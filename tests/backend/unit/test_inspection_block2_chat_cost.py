"""Inspection Remediation BLOCK 2 — T8 (NEW-12), the advertised tool list.

**Mechanism replaced 2026-08-08; the intent is unchanged and still pinned here.**

T8 originally solved the cost problem by HIDING structural tools from owner/principal
(`EXCLUDE_FOR_ROLE`). That worked on tokens and failed on trust: a hidden tool is, to
the model, indistinguishable from one that does not exist, which is how the school's
owner came to be told an operation was "not available to me" about something they were
fully authorised to do. The delete tools were pulled back out of the list for exactly
that reason (owner instruction, 2026-08-07).

`ai/tool_search.py` now achieves the saving differently: a small CORE of everyday tools
is described in full, everything else is listed BY NAME and its instructions fetched on
demand. Nothing is invisible, so the failure above cannot recur.

The properties this file has always defended are re-asserted below against the new
mechanism: the list must be cheaper than the authorized set, it must change cost and
NOTHING about authorization, everyday work must stay immediate, and no tool — least of
all a delete — may become unreachable.
"""

from __future__ import annotations

import pytest

from ai import tool_search
from ai.tool_access import is_tool_authorized
from ai.tool_functions_v2 import TOOL_REGISTRY

OWNER = {"id": "o1", "role": "owner"}
PRINCIPAL = {"id": "p1", "role": "admin", "sub_category": "principal"}
ACCOUNTANT = {"id": "a1", "role": "admin", "sub_category": "accountant"}
TEACHER = {"id": "t1", "role": "teacher"}


@pytest.fixture(autouse=True)
def _enabled(monkeypatch):
    monkeypatch.setenv("EDUFLOW_TOOL_SEARCH", "1")


def _advertised(user, unlocked=None):
    from routes.chat import _build_llm_tools
    return {t["function"]["name"] for t in _build_llm_tools(user, unlocked=unlocked)}


def _authorized(user):
    return {n for n, d in TOOL_REGISTRY.items() if is_tool_authorized(user, d)}


def test_owner_tool_list_is_smaller_than_the_authorized_set():
    advertised = _advertised(OWNER)
    assert advertised < _authorized(OWNER), "deferral did nothing"


def test_deferred_tools_are_still_authorized():
    """The whole safety argument: this is a cost change, not a permission change."""
    from routes.chat import _authorized_tool_names

    for name in tool_search.deferred_names(_authorized_tool_names(OWNER)):
        tool_def = TOOL_REGISTRY.get(name)
        assert tool_def is not None, f"{name} is not a real tool — the catalogue has rotted"
        assert is_tool_authorized(OWNER, tool_def)


def test_a_deferred_tool_is_still_advertised_when_named_explicitly():
    """The tool panel and suggested actions name a tool directly; that path never defers."""
    from routes.chat import _build_llm_tools

    named = {t["function"]["name"] for t in _build_llm_tools(OWNER, only={"update_expense"})}
    assert named == {"update_expense"}


@pytest.mark.parametrize("user", [ACCOUNTANT, TEACHER], ids=["accountant", "teacher"])
def test_smaller_roles_also_benefit_but_keep_their_everyday_tools(user):
    """Unlike the old trim, deferral applies to every role — but core work stays loaded."""
    advertised = _advertised(user)
    authorized = _authorized(user)
    assert advertised <= authorized
    for name in ("get_student_profile", "search_tools"):
        if name in authorized:
            assert name in advertised


def test_everyday_work_is_never_deferred():
    """Marking attendance and taking a fee must not cost an extra round-trip."""
    advertised = _advertised(OWNER)
    for name in ("mark_attendance", "record_fee_payment", "get_fee_defaulters",
                 "get_student_profile", "get_daily_brief"):
        assert name in advertised, f"{name} is everyday work and must stay loaded"


def test_no_tool_is_hidden_from_the_model_entirely():
    """The property the old trim could not offer: everything is at least NAMED."""
    from routes.chat import _authorized_tool_names

    names = _authorized_tool_names(OWNER)
    catalogue = tool_search.catalogue_block(names)
    advertised = _advertised(OWNER)
    for name in names:
        assert name in advertised or name in catalogue, f"{name} is invisible to the model"


@pytest.mark.parametrize("user", [OWNER, PRINCIPAL], ids=["owner", "principal"])
def test_every_delete_the_caller_may_run_is_reachable(user):
    """Owner instruction 2026-08-07: Flo must never claim it cannot delete something
    it is authorised to delete. Deletes may be deferred, but must be findable."""
    from routes.chat import _authorized_tool_names

    names = _authorized_tool_names(user)
    catalogue = tool_search.catalogue_block(names)
    advertised = _advertised(user)
    available = {n: d for n, d in TOOL_REGISTRY.items()
                 if is_tool_authorized(user, d) and not tool_search.is_core(n)}
    for name in (n for n in names if n.startswith("delete_")):
        assert name in advertised or name in catalogue
        assert tool_search.rank(f"select:{name}", available, limit=1) == [name]


def test_deleting_a_class_is_reachable_by_the_principal():
    available = {n: d for n, d in TOOL_REGISTRY.items()
                 if is_tool_authorized(PRINCIPAL, d) and not tool_search.is_core(n)}
    assert "delete_class" in tool_search.rank("delete class", available, limit=8)
