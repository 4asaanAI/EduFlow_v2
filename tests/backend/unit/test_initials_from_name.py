"""Badge letters are derived from the name (owner report, 2026-08-07).

The principal's badge read "PS" beside the name "ADESH SINGH". Seven accounts still
carried the initials of the placeholder name they were created under, because renaming
a person never refreshed the stored field.
"""

from __future__ import annotations

import pytest

from routes.auth import _initials_from_name, _jwt_payload_from_auth


@pytest.mark.parametrize("name,expected", [
    ("ADESH SINGH", "AS"),           # the reported case: stored "PS"
    ("Accountant", "A"),             # stored "MG"
    ("Transport Desk", "TD"),        # stored "SY"
    ("Reception Desk", "RD"),        # stored "KS"
    ("IT Desk", "ID"),               # stored "RT"
    ("Maintenance Desk", "MD"),      # stored "AM"
    ("Management Desk", "MD"),       # stored "RM"
])
def test_the_seven_wrong_badges_now_follow_the_name(name, expected):
    assert _initials_from_name(name) == expected


def test_titles_are_not_treated_as_a_name():
    assert _initials_from_name("DR PERMENDRA KUMAR") == "PK"
    assert _initials_from_name("Dr. Permendra Kumar") == "PK"


def test_a_single_name_gives_one_letter():
    assert _initials_from_name("DEEPANSHI") == "D"


def test_only_the_first_two_words_count():
    assert _initials_from_name("Anjali Chaudhary Devi") == "AC"


def test_no_name_gives_nothing_rather_than_crashing():
    assert _initials_from_name("") == ""
    assert _initials_from_name(None) == ""


def test_the_token_carries_the_derived_badge_not_the_stored_one():
    payload, _ = _jwt_payload_from_auth({
        "user_info": {"id": "u1", "role": "admin", "sub_category": "principal",
                      "name": "ADESH SINGH", "initials": "PS"},
    })
    assert payload["initials"] == "AS"


def test_an_account_with_no_name_still_falls_back_to_what_was_stored():
    # Never leave the badge blank - a stored value beats nothing at all.
    payload, _ = _jwt_payload_from_auth({
        "user_info": {"id": "u2", "role": "admin", "name": "", "initials": "XX"},
    })
    assert payload["initials"] == "XX"
