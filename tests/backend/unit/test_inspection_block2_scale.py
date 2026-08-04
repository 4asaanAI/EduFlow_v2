"""Inspection Remediation BLOCK 2 — T6 (NEW-05) and T7 (NEW-04).

T6: a read that hits its row cap must SAY SO. Before this block, the AI student
search answered for 500 of 1,802 students in silence, and a house with more than
500 members reported the wrong member count.

T7: the same search issued one `db.classes.find_one` per returned student — up to
501 round trips for a single question. The counting collection below is the
regression guard: it fails if anyone reintroduces a per-row lookup.
"""

from __future__ import annotations

import pytest

from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio

SCHOOL = "aaryans-joya"


class CountingCollection(FakeCollection):
    """FakeCollection that records how many reads it served."""

    def __init__(self, docs=None):
        super().__init__(docs)
        self.find_calls = 0
        self.find_one_calls = 0

    def find(self, query=None, projection=None, **kwargs):
        self.find_calls += 1
        return super().find(query, projection, **kwargs)

    async def find_one(self, query=None, projection=None, sort=None, **kwargs):
        self.find_one_calls += 1
        return await super().find_one(query, projection, sort, **kwargs)


def _db(**collections):
    class _D:
        def __getattr__(self, name):
            col = FakeCollection([])
            object.__setattr__(self, name, col)
            return col

    d = _D()
    for name, docs_or_col in collections.items():
        col = docs_or_col if isinstance(docs_or_col, FakeCollection) else FakeCollection(docs_or_col)
        object.__setattr__(d, name, col)
    return d


def _student(sid, name, cls="c1", house=None):
    doc = {"id": sid, "schoolId": SCHOOL, "name": name, "class_id": cls,
           "is_active": True, "status": "active", "roll_number": sid}
    if house:
        doc["house_id"] = house
    return doc


def _many_students(n, cls="c1", house=None):
    return [_student(f"s{i}", f"Student {i}", cls, house) for i in range(n)]


CLASS_C1 = {"id": "c1", "schoolId": SCHOOL, "name": "5", "section": "A"}
OWNER = {"id": "own1", "role": "owner"}


# ── T6 / NEW-05 — truncation is never silent ──────────────────────────────────

async def test_student_search_over_the_cap_reports_the_true_total(monkeypatch):
    import ai.tool_functions_v2 as v2

    db = _db(students=_many_students(1802), classes=[CLASS_C1])
    monkeypatch.setattr(v2, "get_db", lambda: db)

    res = await v2.tool_get_student_database({}, OWNER, None)

    assert res["success"] is True
    assert len(res["data"]) == v2.ROW_CAP
    assert res["meta"]["truncated"] is True
    assert res["meta"]["total"] == 1802
    assert res["meta"]["showing_first"] == v2.ROW_CAP
    # The message is what Flo relays to the person asking — it must carry both numbers.
    assert "500" in res["message"] and "1802" in res["message"]


async def test_student_search_under_the_cap_claims_no_truncation(monkeypatch):
    import ai.tool_functions_v2 as v2

    db = _db(students=_many_students(12), classes=[CLASS_C1])
    monkeypatch.setattr(v2, "get_db", lambda: db)

    res = await v2.tool_get_student_database({}, OWNER, None)

    assert len(res["data"]) == 12
    assert "truncated" not in res["meta"]
    assert "total" not in res["meta"]
    assert res["message"] == ""


async def test_house_details_member_count_is_the_true_total(monkeypatch):
    import ai.tool_functions_v2 as v2

    db = _db(
        students=_many_students(720, house="h1"),
        classes=[CLASS_C1],
        houses=[{"id": "h1", "schoolId": SCHOOL, "name": "Ganga", "color": "blue"}],
    )
    monkeypatch.setattr(v2, "get_db", lambda: db)

    res = await v2.tool_get_house_details({"house_name": "Ganga"}, OWNER, None)

    row = res["data"][0]
    assert row["member_count"] == 720, "member_count must be the real roll, not the page size"
    assert row["members_listed"] == v2.ROW_CAP
    assert "720" in res["message"]


async def test_house_captain_past_the_page_is_still_found(monkeypatch):
    """Found in this block's own review: captains were sliced out of the capped
    member page, so a captain at row 600 disappeared while member_count still
    claimed 720. They are now asked for by role."""
    import ai.tool_functions_v2 as v2

    students = _many_students(720, house="h1")
    students[600]["house_role"] = "captain"
    students[600]["name"] = "Late Roll Captain"
    db = _db(
        students=students,
        classes=[CLASS_C1],
        houses=[{"id": "h1", "schoolId": SCHOOL, "name": "Ganga", "color": "blue"}],
    )
    monkeypatch.setattr(v2, "get_db", lambda: db)

    res = await v2.tool_get_house_details({"house_name": "Ganga"}, OWNER, None)

    names = {c["name"] for c in res["data"][0]["captains"]}
    assert "Late Roll Captain" in names


# ── T7 / NEW-04 — no per-row database lookups ─────────────────────────────────

async def test_student_search_does_one_class_read_not_one_per_student(monkeypatch):
    import ai.tool_functions_v2 as v2

    classes = CountingCollection([CLASS_C1])
    db = _db(students=_many_students(300), classes=classes)
    monkeypatch.setattr(v2, "get_db", lambda: db)

    res = await v2.tool_get_student_database({}, OWNER, None)

    assert len(res["data"]) == 300
    assert res["data"][0]["class"] == "5-A", "batching must not lose the class label"
    assert classes.find_one_calls == 0, "per-student find_one is the N+1 this task removed"
    assert classes.find_calls == 1, "one batched $in read, whatever the number of students"


async def test_class_lookup_is_skipped_entirely_when_no_student_has_a_class(monkeypatch):
    import ai.tool_functions_v2 as v2

    classes = CountingCollection([CLASS_C1])
    students = [{"id": "s1", "schoolId": SCHOOL, "name": "Unassigned",
                 "is_active": True, "status": "active"}]
    db = _db(students=students, classes=classes)
    monkeypatch.setattr(v2, "get_db", lambda: db)

    res = await v2.tool_get_student_database({}, OWNER, None)

    assert res["data"][0]["class"] == "N/A"
    assert classes.find_calls == 0, "an empty id list must cost no query at all"
