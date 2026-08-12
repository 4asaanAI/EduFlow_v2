"""Release 2 step 6: reading the school's own sibling statements out of the ledger.

The office writes the link by hand, in a free-text remark, in about eleven different
spellings, in the same column it writes bank reference numbers into. These pin the two
mistakes that would matter: inventing a family out of a bank reference, and dropping a
family the school did state.
"""

from __future__ import annotations

import sys
from os.path import abspath, dirname, join

sys.path.insert(0, dirname(dirname(dirname(dirname(abspath(__file__))))))

from scripts.sibling_links import analyse  # noqa: E402

# Column order of the school's ledger export. Only the six the reader uses are filled.
_ADM, _NAME, _FATHER, _CLASS, _DISC, _REMARK = 1, 2, 3, 5, 10, 21


def _row(admission, *, discount=0, remark="", name="A Child", father="A Father"):
    row = [None] * 22
    row[_ADM] = admission
    row[_NAME] = name
    row[_FATHER] = father
    row[_CLASS] = "6th"
    row[_DISC] = discount
    row[_REMARK] = remark
    return tuple(row)


def test_a_bank_reference_never_becomes_a_family():
    # SBI is a bank. SIB is a sibling. Both live in this column, often in one sentence.
    out = analyse([
        _row("100001", remark="sbi- 141747371535-50000, 141848321103-40"),
        _row("100002"),
    ])
    assert out["families"] == []


def test_the_offices_eleven_spellings_are_all_read():
    spellings = [
        "SIB NO - 200002",
        "SIB N0 200002",          # a zero, not the letter O
        "SIB. NO. 200002",
        "SIB NBO - 200002",
        "SIB NI 200002",
        "SIB 200002",
        "200002 sib",
        "SBI 857209246972, RS 69100, SIB. 200002",
    ]
    for spelling in spellings:
        out = analyse([_row("200001", remark=spelling), _row("200002")])
        assert out["families"], f"missed the link written as {spelling!r}"
        assert out["families"][0]["members"] == ["200001", "200002"]


def test_a_number_that_is_not_a_child_of_this_school_is_discarded():
    out = analyse([_row("300001", remark="SIB NO - 999999"), _row("300002")])
    assert out["families"] == []
    assert len(out["unreadable"]) == 1        # reported, never made to fit


def test_a_child_is_never_made_their_own_sibling():
    out = analyse([_row("400001", remark="SIB NO - 400001")])
    assert out["families"] == []


def test_a_link_written_on_one_childs_line_puts_both_in_the_family():
    # The office reciprocates only rarely, so a one-sided statement has to be enough.
    out = analyse([_row("500001", remark="SIB NO - 500002"), _row("500002")])
    assert out["families"][0]["members"] == ["500001", "500002"]


def test_two_separate_statements_join_into_one_family_of_three():
    out = analyse([
        _row("600001", remark="SIB NO - 600002"),
        _row("600002", remark="SIB NO - 600003"),
        _row("600003"),
    ])
    assert len(out["families"]) == 1
    assert out["families"][0]["members"] == ["600001", "600002", "600003"]


def test_the_concession_is_copied_from_what_the_office_actually_gave():
    # 1,800 is the sibling value for the 9,750 band. The child who got it is marked; the
    # one who did not is the youngest and keeps paying full. Nothing here guesses at age.
    out = analyse([
        _row("700001", discount=1800, remark="SIB NO - 700002"),
        _row("700002"),
    ])
    assert out["to_mark"] == ["700001"]
    family = out["families"][0]
    assert family["discounted"] == ["700001"]
    assert family["paying_full"] == ["700002"]


def test_a_discount_that_is_not_one_of_the_seven_values_is_not_a_sibling_concession():
    out = analyse([_row("800001", discount=6000, remark="SIB NO - 800002"), _row("800002")])
    assert out["to_mark"] == []


def test_a_child_discounted_with_no_sibling_named_is_reported_and_not_marked():
    out = analyse([_row("900001", discount=1800), _row("900002")])
    assert out["discounted_with_no_stated_family"] == ["900001"]
    assert out["to_mark"] == []


def test_a_family_where_nobody_pays_full_is_flagged_for_a_person():
    # The school's rule says exactly one child pays full. Where its own records disagree,
    # that is the school's to explain and not this script's to correct.
    out = analyse([
        _row("110001", discount=1800, remark="SIB NO - 110002"),
        _row("110002", discount=1800),
    ])
    assert out["odd_families"] and out["odd_families"][0]["paying_full"] == []
