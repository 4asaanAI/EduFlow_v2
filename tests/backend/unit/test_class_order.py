from __future__ import annotations

"""The school's class ordering, server side (Epic 3, Story 3.3).

These cases are deliberately the SAME cases pinned in the frontend's
``classOrder`` tests. The two implementations must agree, because one orders
the dropdowns and the other orders the 1,802-row student listing, and a user
who sorts a list by class and then filters it by class should not see two
different ideas of what order classes come in.
"""

import pytest

from utils.class_order import class_rank, class_sort_key, ordered_class_ids


class TestClassRank:
    def test_pre_primary_sorts_before_class_one(self):
        # The whole reason a plain sort fails: NUR/LKG/UKG have no numeric form
        # and alphabetically land in the middle of the list.
        assert class_rank("NUR") < class_rank("LKG") < class_rank("UKG") < class_rank("1st")

    @pytest.mark.parametrize("name,expected", [
        ("1st", 1), ("2nd", 2), ("10th", 10), ("12th", 12),
        ("Class 8", 8), ("8", 8),
    ])
    def test_arabic_forms(self, name, expected):
        assert class_rank(name) == expected

    @pytest.mark.parametrize("name,expected", [
        ("III-A", 3), ("IV", 4), ("IX", 9), ("XII Sci", 12), ("X", 10),
    ])
    def test_roman_forms_from_the_schools_paperwork(self, name, expected):
        assert class_rank(name) == expected

    def test_tenth_does_not_sort_before_first(self):
        # The specific failure of an alphabetical sort, and of the raw stored
        # order the owner reported ("11th-A, 1st-A, 2nd-C, ...").
        assert class_rank("1st") < class_rank("10th") < class_rank("11th")

    @pytest.mark.parametrize("name", [None, "", "   ", "Remedial", "???"])
    def test_unknown_names_sort_last_rather_than_raising(self, name):
        # One stray record must never break a whole listing.
        assert class_rank(name) == class_rank("Remedial")
        assert class_rank(name) > class_rank("12th")

    def test_case_and_punctuation_insensitive(self):
        assert class_rank("nur") == class_rank("NUR") == class_rank(" Nur ")
        assert class_rank("PRE-NUR") == class_rank("PRE NUR") == class_rank("pre_nur")


class TestClassSortKey:
    def test_sections_order_within_a_class(self):
        a = {"name": "5th", "section": "A"}
        c = {"name": "5th", "section": "C"}
        assert class_sort_key(a) < class_sort_key(c)

    def test_class_wins_over_section(self):
        # 1st-E must still come before 2nd-A.
        assert class_sort_key({"name": "1st", "section": "E"}) < class_sort_key({"name": "2nd", "section": "A"})


class TestOrderedClassIds:
    def test_produces_school_order(self):
        stored = [
            {"id": "c11a", "name": "11th", "section": "A"},
            {"id": "c1a", "name": "1st", "section": "A"},
            {"id": "c2c", "name": "2nd", "section": "C"},
            {"id": "lkga", "name": "LKG", "section": "A"},
            {"id": "nurd", "name": "NUR", "section": "D"},
        ]
        assert ordered_class_ids(stored) == ["nurd", "lkga", "c1a", "c2c", "c11a"]

    def test_records_without_an_id_are_dropped_not_crashed(self):
        assert ordered_class_ids([{"name": "1st", "section": "A"}]) == []

    def test_does_not_mutate_its_input(self):
        stored = [{"id": "b", "name": "2nd"}, {"id": "a", "name": "1st"}]
        ordered_class_ids(stored)
        assert [c["id"] for c in stored] == ["b", "a"]

    def test_empty_input(self):
        assert ordered_class_ids([]) == []
