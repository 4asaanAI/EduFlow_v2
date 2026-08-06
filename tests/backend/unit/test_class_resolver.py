"""The class-label resolver (owner report, 2026-08-07).

The bug these pin: classes store grade and section apart (``name="4th"``,
``section="C"``) but every screen shows them joined ("4th-C"), so the label a person
reads off the screen was the one form the old `name`-only regex could never match.
Asked "who is in 4-C", the assistant answered "nobody" about a class with a child in it.
"""

from __future__ import annotations

import pytest

from ai.class_resolver import (
    describe_no_match,
    find_classes,
    match_classes,
    resolve_class,
)


def _cls(name, section, cid=None):
    return {"id": cid or f"cls-{name}-{section}".lower(), "name": name, "section": section}


AARYANS = [
    _cls("4th", "A"), _cls("4th", "B"), _cls("4th", "C"),
    _cls("1st", "B"), _cls("10th", "B"), _cls("12th", "A"),
    _cls("UKG", "C"), _cls("LKG", "A"), _cls("NUR", "C"),
]


class FakeClasses:
    def __init__(self, docs):
        self.docs = docs
        self.last_query = None

    def find(self, query, projection=None):
        self.last_query = query
        docs = self.docs

        class _Cursor:
            async def to_list(self, n):
                return list(docs)[:n]

        return _Cursor()


class FakeDB:
    def __init__(self, docs):
        self.classes = FakeClasses(docs)


# ── The reported failure ─────────────────────────────────────────────────────

@pytest.mark.parametrize("label", [
    "4-C", "4C", "4 C", "4th-C", "4th C", "4thc",
    "class 4-C", "Class 4 C", "grade 4-C", "std 4-C",
    "IV-C", "iv c", "Class IV-C",
])
def test_every_way_of_writing_4_C_finds_the_same_class(label):
    matches = match_classes(AARYANS, label)
    assert [c["id"] for c in matches] == ["cls-4th-c"], f"{label!r} did not resolve"


def test_pre_primary_labels_resolve( ):
    assert [c["id"] for c in match_classes(AARYANS, "UKG-C")] == ["cls-ukg-c"]
    assert [c["id"] for c in match_classes(AARYANS, "NUR-C")] == ["cls-nur-c"]
    assert [c["id"] for c in match_classes(AARYANS, "nursery C")] == ["cls-nur-c"]
    assert [c["id"] for c in match_classes(AARYANS, "kg2-c")] == ["cls-ukg-c"]


def test_two_digit_grades_are_not_confused_with_one_digit():
    # "1-B" must not drag in 10th-B or 12th-A.
    assert [c["id"] for c in match_classes(AARYANS, "1-B")] == ["cls-1st-b"]
    assert [c["id"] for c in match_classes(AARYANS, "10-B")] == ["cls-10th-b"]


def test_grade_without_a_section_matches_every_section_of_it():
    ids = {c["id"] for c in match_classes(AARYANS, "4th")}
    assert ids == {"cls-4th-a", "cls-4th-b", "cls-4th-c"}


def test_exact_section_match_is_ranked_before_grade_wide_matches():
    assert match_classes(AARYANS, "4-C")[0]["id"] == "cls-4th-c"


# ── The silent-failure half of the bug ───────────────────────────────────────

async def test_resolve_returns_none_for_an_unknown_class():
    # The caller must be able to SAY it could not find the class. Before this,
    # a miss dropped the filter and answered about the whole school.
    assert await resolve_class(FakeDB(AARYANS), "7-Z") is None


async def test_resolve_returns_none_when_the_label_is_ambiguous():
    # "4th" is three classes; picking one silently would report the wrong roll.
    assert await resolve_class(FakeDB(AARYANS), "4th") is None


async def test_resolve_returns_none_for_an_empty_label():
    assert await resolve_class(FakeDB(AARYANS), "") is None


async def test_resolve_finds_the_single_match():
    found = await resolve_class(FakeDB(AARYANS), "4-C")
    assert found["id"] == "cls-4th-c"


# ── Tenant scoping ───────────────────────────────────────────────────────────

async def test_the_callers_scope_is_passed_through_to_the_query():
    # The old per-tool lookups queried db.classes with NO scoping, so a class name
    # could resolve across schools. The scope must reach the query.
    db = FakeDB(AARYANS)
    await find_classes(db, "4-C", {"schoolId": "aaryans-joya", "branch_id": "branch-joya"})
    assert db.classes.last_query == {"schoolId": "aaryans-joya", "branch_id": "branch-joya"}


# ── The message shown when nothing matches ───────────────────────────────────

def test_no_match_message_lists_what_the_school_actually_has():
    msg = describe_no_match("4-Z", AARYANS)
    assert "4-Z" in msg
    assert "4th-C" in msg


def test_no_match_message_survives_a_school_with_no_classes():
    assert "7-A" in describe_no_match("7-A", [])
