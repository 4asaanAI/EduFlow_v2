"""UI Sweep Epic 4 — the tool-panel endpoint.

Stories 4.1 (one envelope) and 4.5 (the same gate as the assistant).

`POST /api/tools/{tool_id}/execute` is the endpoint behind every tool screen and it
had **no tests of any kind**. That is why a double result envelope — added when the
R4 epic made `_env()` the one tool-result shape — survived an entire initiative while
eleven screens printed 0.

The regression test that matters is `test_response_is_the_tools_own_envelope`: it runs
a real registry tool through the real route and asserts the body IS that tool's own
envelope. A test that mocks the tool and checks "it passed something through" would
have passed against the bug.
"""
from __future__ import annotations

import pytest

from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio

TOOL_URL = "/api/tools/{}/execute"


def _bearer(payload: dict) -> dict:
    # NOTE: the claim is `user_id`, not `id` — `decode_jwt` reads `payload["user_id"]`
    # and defaults to "". Tests that only exercise role checks never notice; anything
    # that resolves a Scope does, because Scope refuses an empty user_id.
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner():
    return _bearer({"user_id": "e4-owner", "role": "owner", "name": "Owner"})


def _principal(branch: str = "branch-a"):
    return _bearer({
        "user_id": "e4-prin", "role": "admin", "sub_category": "principal",
        "branch_id": branch, "name": "Principal",
    })


def _student():
    return _bearer({"user_id": "e4-stu", "role": "student", "name": "Student"})


def _receptionist():
    return _bearer({
        "user_id": "e4-rec", "role": "admin", "sub_category": "receptionist", "name": "Reception",
    })


# The FakeDb is a session-wide singleton, so a blanket `docs[:] = []` would delete
# rows other test files seeded — that is how this file first broke six parity tests.
# Snapshot and restore instead: these tests get a clean slate and give back exactly
# what they were handed.
_TOUCHED = ("students", "staff", "student_attendance", "staff_attendance",
            "fee_transactions", "leave_requests", "classes", "school_settings")


@pytest.fixture(autouse=True)
def _clean(fake_db):
    saved = {name: list(getattr(fake_db, name).docs) for name in _TOUCHED}
    for name in _TOUCHED:
        getattr(fake_db, name).docs[:] = []
    yield
    for name in _TOUCHED:
        getattr(fake_db, name).docs[:] = saved[name]


# ── Story 4.1 — one envelope ─────────────────────────────────────────────────

def _is_envelope(value) -> bool:
    return isinstance(value, dict) and {"success", "data", "meta"} <= set(value.keys())


def test_response_is_the_tools_own_envelope(client, fake_db):
    """THE regression. Fails before the fix, passes after.

    The old endpoint returned {"success": True, "data": <envelope>}, so `data` was an
    envelope rather than the payload and every screen read one level too shallow.
    """
    fake_db.students.docs.append(
        {"id": "s1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "name": "Asha", "is_active": True}
    )

    resp = client.post(TOOL_URL.format("get_school_pulse"), json={"params": {}}, headers=_owner())
    assert resp.status_code == 200
    body = resp.json()

    assert _is_envelope(body), "the response body must itself be the tool's envelope"
    assert not _is_envelope(body["data"]), (
        "data must be the tool's PAYLOAD, never a second envelope — this is owner "
        "item 7: every screen read r.data.summary and got undefined"
    )
    # And the payload is reachable exactly where the screens look for it.
    assert "summary" in body["data"]
    assert body["data"]["summary"]["total_students"] == 1


def test_no_registry_tool_returns_a_nested_envelope(client, fake_db):
    """Asserted over the registry, not one hand-picked tool.

    This is what stops a third envelope being introduced in 2027 — a future tool that
    double-wraps fails here rather than showing zeros on a screen nobody opened.
    """
    from ai.tool_functions_v2 import TOOL_REGISTRY
    from ai.tool_access import is_read_only_tool

    checked = 0
    for name, tool_def in TOOL_REGISTRY.items():
        if not is_read_only_tool(tool_def):
            continue
        if "owner" not in tool_def.get("roles", []):
            continue
        if tool_def.get("params_schema"):
            continue  # needs arguments; covered by the per-tool tests
        resp = client.post(TOOL_URL.format(name), json={"params": {}}, headers=_owner())
        if resp.status_code != 200:
            continue
        body = resp.json()
        assert _is_envelope(body), f"{name}: response is not an envelope"
        assert not _is_envelope(body["data"]), f"{name}: data is a nested envelope"
        checked += 1

    assert checked >= 5, "expected several no-argument owner read tools to be exercised"


def test_denied_is_not_an_empty_success(client, fake_db, monkeypatch):
    """R4's denied-≠-empty principle reaches the tool panels, not just chat."""
    from ai.tool_functions_v2 import TOOL_REGISTRY

    async def _refuse(params, user, scope=None):
        return {
            "success": False, "data": [], "meta": {"count": 0},
            "message": "You do not have access to this.", "denied": True,
        }

    monkeypatch.setitem(TOOL_REGISTRY["get_school_pulse"], "fn", _refuse)
    resp = client.post(TOOL_URL.format("get_school_pulse"), json={"params": {}}, headers=_owner())

    assert resp.status_code == 200
    body = resp.json()
    assert body["denied"] is True
    assert body["success"] is False, "a refusal must not be reported as a success"


def test_tool_failure_never_leaks_the_exception(client, monkeypatch):
    """Error opacity (P3): the caller sees a generic message, not str(e)."""
    from ai.tool_functions_v2 import TOOL_REGISTRY

    async def _boom(params, user, scope=None):
        raise RuntimeError("mongodb://user:hunter2@cluster.example/eduflow")

    monkeypatch.setitem(TOOL_REGISTRY["get_school_pulse"], "fn", _boom)
    resp = client.post(TOOL_URL.format("get_school_pulse"), json={"params": {}}, headers=_owner())

    assert resp.status_code == 500
    assert "hunter2" not in resp.text
    assert "mongodb" not in resp.text.lower()


# ── Standing security convention ─────────────────────────────────────────────

def test_endpoint_unauthenticated_returns_401(client):
    resp = client.post(TOOL_URL.format("get_school_pulse"), json={"params": {}})
    assert resp.status_code == 401


def test_endpoint_wrong_role_returns_403(client):
    resp = client.post(TOOL_URL.format("get_school_pulse"), json={"params": {}}, headers=_student())
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Forbidden"


# ── Story 4.5 — the same gate as the assistant ───────────────────────────────

def test_sub_category_is_honoured_like_the_chat_path(client):
    """The endpoint gated on role alone, so 49 registry entries carrying
    `sub_categories` were invisible to it: a receptionist could run a tool the
    assistant would refuse them."""
    from ai.tool_functions_v2 import TOOL_REGISTRY
    from ai.tool_access import is_read_only_tool

    restricted = [
        name for name, td in TOOL_REGISTRY.items()
        if td.get("sub_categories")
        and "admin" in td.get("roles", [])
        and "receptionist" not in (td.get("sub_categories") or [])
        and is_read_only_tool(td)
    ]
    assert restricted, "expected read tools restricted by sub_category"

    for name in restricted[:5]:
        resp = client.post(TOOL_URL.format(name), json={"params": {}}, headers=_receptionist())
        assert resp.status_code == 403, f"{name} should be refused for a receptionist"
        assert resp.json()["detail"] == "Forbidden"


def test_write_tools_are_refused_at_this_door(client):
    """A write here would skip the confirm token, the kill-switch, the lockdown and
    the audit row. Writes go through chat, which has all of them."""
    from ai.tool_functions_v2 import TOOL_REGISTRY, WRITE_TOOL_NAMES

    assert WRITE_TOOL_NAMES, "expected the registry to contain write tools"
    owner_writes = [n for n in WRITE_TOOL_NAMES if "owner" in TOOL_REGISTRY[n].get("roles", [])]
    assert owner_writes, "expected owner-permitted write tools"

    for name in sorted(owner_writes)[:8]:
        resp = client.post(TOOL_URL.format(name), json={"params": {}}, headers=_owner())
        assert resp.status_code == 403, (
            f"{name} is a write tool and must not be invocable through the tool panel, "
            "even for the Owner"
        )


def test_every_registry_tool_declares_whether_it_writes(client):
    """Drift gate, in the spirit of the F.6 parity corpus.

    The 14 original v1 tools carry no `dispatch_type` key, so "refuse anything not
    marked read" would refuse every tool panel. The rule is therefore "refuse what is
    marked write" — which silently admits a NEW tool that forgets the key. This test
    freezes the inventory of tools lacking the key, so adding one fails here.
    """
    from ai.tool_functions_v2 import TOOL_REGISTRY

    # Frozen 2026-07-22. All 46 audited by hand and confirmed read-only.
    KNOWN_WITHOUT_DISPATCH_TYPE = {
        "draft_parent_message", "get_announcements", "get_attendance_overview",
        "get_branch_comparison", "get_class_list", "get_class_wise_attendance",
        "get_daily_brief", "get_enquiries", "get_exam_results_summary", "get_expenses",
        "get_fee_defaulters", "get_fee_structures", "get_fee_summary",
        "get_fee_sync_status", "get_fee_transactions", "get_financial_report",
        "get_house_details", "get_house_standings", "get_inventory_status",
        "get_leave_requests", "get_library_status", "get_my_attendance",
        "get_my_class_students", "get_my_fees", "get_my_results", "get_school_pulse",
        "get_smart_alerts", "get_staff_list", "get_staff_status",
        "get_student_council", "get_student_database", "get_student_profile",
        "get_timetable", "get_today_class_attendance", "get_transport_status",
        "get_upcoming_events", "query_attendance_status", "query_audit_log",
        "query_dashboard_summary", "query_fee_status", "query_incidents",
        "query_maintenance_requests", "query_staff_availability",
        "query_student_record", "recall_history", "search_students",
    }
    actual = {name for name, td in TOOL_REGISTRY.items() if "dispatch_type" not in td}

    new_tools = actual - KNOWN_WITHOUT_DISPATCH_TYPE
    assert not new_tools, (
        f"New tool(s) declare no dispatch_type: {sorted(new_tools)}. The tool-panel "
        "endpoint classifies a tool as a write by its dispatch_type/requires_confirmation "
        "flags, so a tool that omits both is silently callable through a door with no "
        "confirm token, no kill-switch and no audit. Add dispatch_type explicitly — and "
        "if it is a read, add it to this frozen set."
    )

    # None of them may be a write hiding behind the confirmation flag alone.
    for name in actual:
        assert not TOOL_REGISTRY[name].get("requires_confirmation"), (
            f"{name} requires confirmation but declares no dispatch_type"
        )


def test_unknown_tool_is_indistinguishable_from_a_forbidden_one(client):
    """The endpoint answered 404 before checking authorization, so an authenticated
    student could map the registry by comparing 404s against 403s."""
    unknown = client.post(TOOL_URL.format("no_such_tool_xyz"), json={"params": {}}, headers=_student())
    forbidden = client.post(TOOL_URL.format("get_school_pulse"), json={"params": {}}, headers=_student())

    assert unknown.status_code == forbidden.status_code == 403
    assert unknown.json() == forbidden.json()


def test_branch_bound_caller_does_not_read_another_branch(client, fake_db):
    """The endpoint called fn(params, user) — no scope — so `_tenant_query` emitted no
    branch_id clause and a branch-bound principal read every branch's figures."""
    fake_db.staff.docs.append({
        "id": "st-prin", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "user_id": "e4-prin", "name": "Principal", "is_active": True,
        "staff_type": "admin", "sub_category": "principal",
    })
    fake_db.students.docs.extend([
        {"id": "s-a", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "name": "Own Branch", "is_active": True},
        {"id": "s-b", "schoolId": "aaryans-joya", "branch_id": "branch-b",
         "name": "Other Branch", "is_active": True},
    ])

    resp = client.post(TOOL_URL.format("get_school_pulse"), json={"params": {}}, headers=_principal("branch-a"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["summary"]["total_students"] == 1, (
        "a branch-a principal counted students from branch-b — the scope was never passed"
    )


def test_owner_still_reads_across_branches(client, fake_db):
    """The branch fix must not accidentally fence the Owner into one branch."""
    fake_db.students.docs.extend([
        {"id": "s-a", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "name": "A", "is_active": True},
        {"id": "s-b", "schoolId": "aaryans-joya", "branch_id": "branch-b",
         "name": "B", "is_active": True},
    ])

    resp = client.post(TOOL_URL.format("get_school_pulse"), json={"params": {}}, headers=_owner())
    assert resp.status_code == 200
    assert resp.json()["data"]["summary"]["total_students"] == 2
