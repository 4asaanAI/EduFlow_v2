"""Epic R5 — Tenancy & Scope Fail-Closed (tool tier, H4).

Every read tool now branch-scopes off the JWT (`_branch_id(user, scope)`), and the
`find_one` lookups in get_student_profile / award_house_points / mark_attendance are
branch-scoped too. A branch-A user must never see (or write against) branch-B rows;
an owner (no JWT branch) still sees every branch.
"""

from __future__ import annotations

import pytest

from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio

SCHOOL = "aaryans-joya"


def _db(**collections):
    class _D:
        def __getattr__(self, name):
            col = FakeCollection([])
            object.__setattr__(self, name, col)
            return col
    d = _D()
    for name, docs in collections.items():
        object.__setattr__(d, name, FakeCollection(docs))
    return d


def _student(sid, name, branch, cls="c1"):
    return {"id": sid, "schoolId": SCHOOL, "branch_id": branch, "name": name,
            "class_id": cls, "is_active": True, "status": "active"}


# ── R5.1: read tool branch isolation (get_student_database) ────────────────

async def test_student_database_branch_admin_sees_only_own_branch(monkeypatch):
    import ai.tool_functions_v2 as v2
    db = _db(
        students=[_student("a1", "Anaya", "branch-A"), _student("b1", "Bhavya", "branch-B")],
        classes=[{"id": "c1", "schoolId": SCHOOL, "name": "5", "section": "A"}],
    )
    monkeypatch.setattr(v2, "get_db", lambda: db)

    user_a = {"id": "adminA", "role": "admin", "branch_id": "branch-A"}
    res = await v2.tool_get_student_database({}, user_a, None)
    names = {r["name"] for r in res["data"]}
    assert names == {"Anaya"}, f"branch-A admin leaked cross-branch rows: {names}"


async def test_student_database_owner_sees_all_branches(monkeypatch):
    import ai.tool_functions_v2 as v2
    db = _db(
        students=[_student("a1", "Anaya", "branch-A"), _student("b1", "Bhavya", "branch-B")],
        classes=[{"id": "c1", "schoolId": SCHOOL, "name": "5", "section": "A"}],
    )
    monkeypatch.setattr(v2, "get_db", lambda: db)

    owner = {"id": "own1", "role": "owner"}  # no branch_id → school-wide
    res = await v2.tool_get_student_database({}, owner, None)
    names = {r["name"] for r in res["data"]}
    assert names == {"Anaya", "Bhavya"}


# ── R5.1: more read tools isolate by branch (class_list, house_standings) ──

async def test_class_list_branch_isolation(monkeypatch):
    import ai.tool_functions_v2 as v2
    db = _db(classes=[
        {"id": "cA", "schoolId": SCHOOL, "branch_id": "branch-A", "name": "Class 1", "section": "A"},
        {"id": "cB", "schoolId": SCHOOL, "branch_id": "branch-B", "name": "Class 1", "section": "B"},
    ])
    monkeypatch.setattr(v2, "get_db", lambda: db)
    res = await v2.tool_get_class_list({}, {"id": "a", "role": "admin", "branch_id": "branch-A"}, None)
    assert res["meta"]["count"] == 1


async def test_house_standings_branch_isolation(monkeypatch):
    import ai.tool_functions_v2 as v2
    db = _db(
        houses=[
            {"id": "hA", "schoolId": SCHOOL, "branch_id": "branch-A", "name": "Atulya"},
            {"id": "hB", "schoolId": SCHOOL, "branch_id": "branch-B", "name": "Agrim"},
        ],
        house_points=[],
    )
    monkeypatch.setattr(v2, "get_db", lambda: db)
    res = await v2.tool_get_house_standings({}, {"id": "a", "role": "admin", "branch_id": "branch-A"}, None)
    names = {r["house_name"] for r in res["data"]}
    assert names == {"Atulya"}


# ── R5.2: get_student_profile find_one is branch-scoped ────────────────────

async def test_student_profile_cross_branch_lookup_blocked(monkeypatch):
    import ai.tool_functions_v2 as v2
    db = _db(
        students=[_student("b1", "Bhavya", "branch-B")],
        classes=[{"id": "c1", "schoolId": SCHOOL, "name": "5", "section": "A"}],
    )
    monkeypatch.setattr(v2, "get_db", lambda: db)

    user_a = {"id": "adminA", "role": "admin", "branch_id": "branch-A"}
    res = await v2.tool_get_student_profile({"student_id": "b1"}, user_a, None)
    # Branch-A admin must NOT read a branch-B student's profile.
    assert res["success"] is True
    assert res["data"] == [] or res.get("meta", {}).get("count", 0) == 0


async def test_student_profile_same_branch_lookup_succeeds(monkeypatch):
    import ai.tool_functions_v2 as v2
    db = _db(
        students=[_student("a1", "Anaya", "branch-A")],
        classes=[{"id": "c1", "schoolId": SCHOOL, "name": "5", "section": "A"}],
    )
    monkeypatch.setattr(v2, "get_db", lambda: db)

    user_a = {"id": "adminA", "role": "admin", "branch_id": "branch-A"}
    res = await v2.tool_get_student_profile({"student_id": "a1"}, user_a, None)
    assert res["success"] is True
    assert res["data"][0]["name"] == "Anaya"


# ── R5.2: award_house_points name lookup cannot cross branch ────────────────

async def test_award_house_points_cross_branch_student_not_found(monkeypatch):
    import ai.tool_functions_v2 as v2
    db = _db(
        students=[{**_student("b1", "Bhavya", "branch-B"), "house_id": "h1"}],
        houses=[{"id": "h1", "schoolId": SCHOOL, "name": "Atulya"}],
    )
    monkeypatch.setattr(v2, "get_db", lambda: db)

    user_a = {"id": "priA", "role": "admin", "branch_id": "branch-A"}
    scope = {"can_write": True}
    res = await v2.tool_award_house_points(
        {"student_name": "Bhavya", "points": 5, "reason": "x"}, user_a, scope,
    )
    # A branch-A user must not resolve (and write points to) a branch-B student.
    assert res["success"] is False
    assert "not found" in res["message"].lower()


# ── R5.2: mark_attendance rejects a directly-supplied cross-branch class_id ──

async def test_mark_attendance_direct_cross_branch_class_id_rejected(monkeypatch):
    import ai.tool_functions_v2 as v2
    db = _db(
        classes=[{"id": "clsB", "schoolId": SCHOOL, "branch_id": "branch-B",
                  "name": "Class 4", "section": "A"}],
    )
    monkeypatch.setattr(v2, "get_db", lambda: db)

    user_a = {"id": "priA", "role": "admin", "branch_id": "branch-A"}
    res = await v2.tool_mark_attendance(
        {"class_id": "clsB", "attendance": [{"student_id": "s1", "status": "present"}]},
        user_a, {"can_write": True},
    )
    assert res["success"] is False
    assert "branch" in res["message"].lower()
