"""Epic E.2/E.3/E.4 — structured planner, round/size bounds, entity resolution.

The planner is exercised with a recorded plan fixture (injected `request_plan`),
so its logic is deterministic with no live Azure call. Covers: ordered resolved
steps with per-write preconditions, MAX_PLAN_STEPS bound, whole-plan rejection
on an unauthorized step, and disambiguation when a name matches >1 record.
"""

from __future__ import annotations

import pytest

from ai import planner

pytestmark = pytest.mark.asyncio


# A minimal registry + helpers wired the way chat.py wires the real ones.
_REGISTRY = {
    "approve_leave": {"roles": ["owner", "admin"], "sub_categories": ["principal"]},
    "create_announcement": {"roles": ["owner", "admin"]},
    "get_leave_requests": {"roles": ["owner", "admin"]},
    "record_fee_payment": {"roles": ["owner", "admin"]},
}
_WRITE_TOOLS = {"approve_leave", "create_announcement", "record_fee_payment"}


def _is_authorized(user, tool_def):
    if user.get("role") not in tool_def.get("roles", []):
        return False
    subs = tool_def.get("sub_categories")
    if subs is None or user.get("role") != "admin":
        return True
    return user.get("sub_category") in subs


def _fixture(steps):
    async def _request_plan(*, instruction, user, scope):
        return steps
    return _request_plan


async def _identity_resolve(params, db, scope=None):
    return dict(params)


_OWNER = {"id": "o1", "role": "owner", "branch_id": "b1"}


async def test_builds_ordered_resolved_plan_with_preconditions():
    steps = [
        {"tool": "get_leave_requests", "params": {}},
        {"tool": "approve_leave", "params": {"leave_id": "lv-9", "action": "approve"}},
        {"tool": "create_announcement", "params": {"title": "T", "content": "C"}},
    ]
    res = await planner.build_plan(
        instruction="x", user=_OWNER, db=None, scope=None,
        registry=_REGISTRY, write_tools=_WRITE_TOOLS,
        is_authorized=_is_authorized, resolve_params=_identity_resolve,
        request_plan=_fixture(steps),
    )
    assert res.status == planner.PLAN
    assert [s["idx"] for s in res.steps] == [0, 1, 2]
    assert res.steps[0]["kind"] == planner.READ
    assert res.steps[1]["kind"] == planner.WRITE
    # The write step targeting a leave_id gets a freshness precondition.
    assert res.steps[1]["precondition"] == {"collection": "leaves", "id": "lv-9"}
    assert res.has_writes


async def test_plan_exceeding_max_steps_is_rejected():
    steps = [{"tool": "create_announcement", "params": {"title": str(i), "content": "c"}}
             for i in range(planner.MAX_PLAN_STEPS + 1)]
    res = await planner.build_plan(
        instruction="x", user=_OWNER, db=None, scope=None,
        registry=_REGISTRY, write_tools=_WRITE_TOOLS,
        is_authorized=_is_authorized, resolve_params=_identity_resolve,
        request_plan=_fixture(steps),
    )
    assert res.status == planner.TOO_LONG
    assert str(planner.MAX_PLAN_STEPS) in res.message


async def test_unauthorized_step_rejects_whole_plan_with_which_step():
    # An admin WITHOUT principal sub_category cannot approve_leave → whole plan rejected.
    admin = {"id": "a1", "role": "admin", "sub_category": "accountant", "branch_id": "b1"}
    steps = [
        {"tool": "create_announcement", "params": {"title": "T", "content": "C"}},
        {"tool": "approve_leave", "params": {"leave_id": "lv-1", "action": "approve"}},
    ]
    res = await planner.build_plan(
        instruction="x", user=admin, db=None, scope=None,
        registry=_REGISTRY, write_tools=_WRITE_TOOLS,
        is_authorized=_is_authorized, resolve_params=_identity_resolve,
        request_plan=_fixture(steps), deep_link_for=lambda t: f"/app?tool={t}",
    )
    assert res.status == planner.UNAUTHORIZED
    assert res.unauthorized_tool == "approve_leave"
    assert res.unauthorized_step_idx == 1
    assert "Step 2" in res.message
    assert res.deep_link == "/app?tool=approve_leave"


async def test_ambiguous_entity_returns_disambiguation_no_steps():
    async def _ambiguous_resolve(params, db, scope=None):
        out = dict(params)
        out["_resolution_error"] = "Multiple students named 'Rahul'."
        return out

    steps = [{"tool": "record_fee_payment", "params": {"student_name": "Rahul", "amount": 100}}]
    res = await planner.build_plan(
        instruction="x", user=_OWNER, db=None, scope=None,
        registry=_REGISTRY, write_tools=_WRITE_TOOLS,
        is_authorized=_is_authorized, resolve_params=_ambiguous_resolve,
        request_plan=_fixture(steps),
    )
    assert res.status == planner.DISAMBIGUATION
    assert "Rahul" in res.message
    assert res.steps == []


async def test_unknown_tool_cannot_plan():
    steps = [{"tool": "make_coffee", "params": {}}]
    res = await planner.build_plan(
        instruction="x", user=_OWNER, db=None, scope=None,
        registry=_REGISTRY, write_tools=_WRITE_TOOLS,
        is_authorized=_is_authorized, resolve_params=_identity_resolve,
        request_plan=_fixture(steps),
    )
    assert res.status == planner.CANNOT_PLAN


async def test_empty_plan_cannot_plan():
    res = await planner.build_plan(
        instruction="x", user=_OWNER, db=None, scope=None,
        registry=_REGISTRY, write_tools=_WRITE_TOOLS,
        is_authorized=_is_authorized, resolve_params=_identity_resolve,
        request_plan=_fixture([]),
    )
    assert res.status == planner.CANNOT_PLAN


async def test_resolution_internal_keys_stripped_from_plan():
    async def _resolve_with_internal(params, db, scope=None):
        out = dict(params)
        out["student_id"] = "stu-7"
        out["_resolved_student"] = "Rahul Kumar"  # internal — must not leak into plan
        return out

    steps = [{"tool": "record_fee_payment", "params": {"student_name": "Rahul", "amount": 100}}]
    res = await planner.build_plan(
        instruction="x", user=_OWNER, db=None, scope=None,
        registry=_REGISTRY, write_tools=_WRITE_TOOLS,
        is_authorized=_is_authorized, resolve_params=_resolve_with_internal,
        request_plan=_fixture(steps),
    )
    assert res.status == planner.PLAN
    assert "_resolved_student" not in res.steps[0]["params"]
    assert res.steps[0]["params"]["student_id"] == "stu-7"
    assert res.steps[0]["precondition"] == {"collection": "students", "id": "stu-7"}
