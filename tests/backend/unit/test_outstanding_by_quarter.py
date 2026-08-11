"""Release 2 audit finding 9: the late fine is worked out from the child's own bills.

Before this the fine was calculated only if the caller handed in the outstanding figures
by quarter, and no caller ever did, so in practice nobody ever saw a fine at all.

The part worth testing is which bills count and which quarter each one lands in. The fine
is charged on ONE outstanding figure per quarter with transport folded into it (fee rules
section 2.2), so a bus charge has to be placed in the quarter its month belongs to.
"""

from __future__ import annotations

import pytest

from services.student_concession_service import outstanding_by_quarter


def _bill(period, amount, *, status="pending", paid=0):
    return {"installment_code": period, "amount": amount, "status": status,
            "paid_amount": paid}


def test_the_four_quarters_come_through_as_they_are():
    assert outstanding_by_quarter([_bill("q1", 9750), _bill("q3", 9750)]) == [
        {"quarter": "q1", "outstanding_amount": 9750.0},
        {"quarter": "q3", "outstanding_amount": 9750.0},
    ]


@pytest.mark.parametrize("month,quarter", [
    ("april", "q1"), ("may", "q1"),
    ("july", "q2"), ("august", "q2"), ("september", "q2"),
    ("october", "q3"), ("november", "q3"), ("december", "q3"),
    ("january", "q4"), ("february", "q4"), ("march", "q4"),
])
def test_a_bus_month_lands_in_the_quarter_it_belongs_to(month, quarter):
    out = outstanding_by_quarter([_bill(f"transport-{month}", 650)])
    assert out == [{"quarter": quarter, "outstanding_amount": 650.0}]


def test_the_bus_is_added_into_the_quarters_own_figure_not_counted_apart():
    # Section 2.2: one outstanding figure, one daily fine, one 1,000. There is no
    # separate transport fine and no separate transport due date.
    out = outstanding_by_quarter([_bill("q1", 9750), _bill("transport-april", 650),
                                  _bill("transport-may", 650)])
    assert out == [{"quarter": "q1", "outstanding_amount": 11050.0}]


def test_there_is_no_june_and_a_june_bill_would_not_be_placed():
    # The buses do not run in June and no June transport is ever charged. If one ever
    # appeared it would be a data fault, and guessing a quarter for it would fine a
    # family for a month the school does not bill.
    assert outstanding_by_quarter([_bill("transport-june", 650)]) == []


@pytest.mark.parametrize("status", ["paid", "cancelled", "waived"])
def test_a_bill_that_is_settled_or_cancelled_is_not_owed(status):
    assert outstanding_by_quarter([_bill("q1", 9750, status=status)]) == []


def test_a_part_paid_bill_counts_only_for_what_is_still_owed():
    out = outstanding_by_quarter([_bill("q1", 9750, paid=3000)])
    assert out == [{"quarter": "q1", "outstanding_amount": 6750.0}]


def test_a_bill_paid_in_full_but_still_marked_open_owes_nothing():
    assert outstanding_by_quarter([_bill("q1", 9750, paid=9750)]) == []


def test_charges_that_are_not_on_the_quarterly_clock_are_left_out():
    # Registration, admission, last session's dues. Real money, and attaching them to a
    # quarter they may not belong to would fine a family on the wrong schedule.
    out = outstanding_by_quarter([
        _bill("admission", 12000), _bill("previous-session", 5000),
        _bill("other", 1000), _bill("q1", 9750),
    ])
    assert out == [{"quarter": "q1", "outstanding_amount": 9750.0}]
