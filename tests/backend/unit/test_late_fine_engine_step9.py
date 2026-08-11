"""Release 2 step 9: the school's late fine, and the way the old supplier gets it wrong.

Every figure asserted here comes from section 2 of
``_bmad-output/implementation-artifacts/release-2/fee-rules-from-sonu-2026-08-11.md``,
including Sonu's own worked example.
"""

from __future__ import annotations

from datetime import date

import pytest

from services.late_fine_service import (
    LateFineError,
    assess_quarters,
    compute_late_fine,
    due_date,
    quarter_end,
    quarter_end_charge_dates,
)

SESSION = 2026


def _fine(quarter, as_of, outstanding=9750, settled_on=None):
    return compute_late_fine(
        quarter=quarter, session_start_year=SESSION, as_of=as_of,
        outstanding_amount=outstanding, settled_on=settled_on,
    )


# ─────────────────────── the school's own calendar ─────────────────────────


@pytest.mark.parametrize("quarter,due,ends", [
    ("q1", date(2026, 4, 15), date(2026, 6, 30)),
    ("q2", date(2026, 7, 15), date(2026, 9, 30)),
    ("q3", date(2026, 10, 15), date(2026, 12, 31)),
    ("q4", date(2027, 1, 15), date(2027, 3, 31)),
])
def test_the_four_quarters_are_the_schools_four(quarter, due, ends):
    assert due_date(quarter, SESSION) == due
    assert quarter_end(quarter, SESSION) == ends


def test_a_quarter_the_school_does_not_have_refuses():
    with pytest.raises(LateFineError):
        due_date("q5", SESSION)


# ─────────────────────── Sonu's worked example ─────────────────────────────


def test_nothing_is_charged_inside_the_fifteen_day_window():
    assert _fine("q1", "2026-04-15")["total"] == 0.0


def test_the_daily_fine_starts_on_the_sixteenth():
    assert _fine("q1", "2026-04-16")["daily_days"] == 1
    assert _fine("q1", "2026-04-16")["total"] == 10.0


def test_by_thirty_june_an_unpaid_q1_stands_at_seven_hundred_and_sixty():
    # Sonu's example: 16 April to 30 June is 76 days, so 760.
    out = _fine("q1", "2026-06-30")
    assert out["daily_days"] == 76
    assert out["daily_amount"] == 760.0
    assert out["quarter_end_charges"] == 0
    assert out["total"] == 760.0


def test_on_the_first_of_july_the_thousand_lands_and_the_daily_fine_stops():
    out = _fine("q1", "2026-07-01")
    assert out["daily_days"] == 76          # not 77: it stopped on 30 June
    assert out["quarter_end_charges"] == 1
    assert out["total"] == 1760.0


def test_the_daily_fine_does_not_grow_after_the_quarter_ends():
    # The whole of Sonu's point. An unpaid Q1 stands still on its daily fine from 1 July.
    for when in ("2026-07-01", "2026-08-15", "2026-09-30"):
        assert _fine("q1", when)["daily_amount"] == 760.0


# ────────── the fault in the old system, named and pinned ──────────────────


def test_only_one_daily_fine_ever_runs_at_a_time():
    # 1 September: Q1 and Q2 both unpaid. The old supplier accrues both dailies at once,
    # which is what overcharges families. Only Q2's may run.
    out = assess_quarters(
        [{"quarter": "q1", "outstanding_amount": 9750},
         {"quarter": "q2", "outstanding_amount": 9750}],
        session_start_year=SESSION, as_of="2026-09-01",
    )
    assert out["daily_running"] == "q2"
    running = [q["quarter"] for q in out["quarters"] if q["still_accruing_daily"]]
    assert running == ["q2"]

    q1, q2 = out["quarters"]
    assert q1["daily_amount"] == 760.0                  # frozen on 30 June
    assert q2["daily_days"] == 48                       # 16 July to 1 September


def test_the_old_systems_answer_is_not_what_this_produces():
    # Vedmarg would keep Q1 accruing to 1 September: 16 April to 1 September is 139 days,
    # so 1,390 on Q1 instead of 760. The difference is money taken off a family wrongly.
    q1 = _fine("q1", "2026-09-01")
    assert q1["daily_amount"] == 760.0
    assert q1["daily_amount"] != 1390.0


# ────────────────── the 1,000 repeats, four times over ─────────────────────


def test_an_unpaid_q1_takes_the_thousand_at_all_four_quarter_ends():
    assert quarter_end_charge_dates("q1", SESSION) == [
        date(2026, 7, 1), date(2026, 10, 1), date(2027, 1, 1), date(2027, 4, 1),
    ]
    out = _fine("q1", "2027-04-01")
    assert out["quarter_end_charges"] == 4
    assert out["flat_amount"] == 4000.0
    assert out["total"] == 4760.0                       # 760 daily, plus four thousands


@pytest.mark.parametrize("quarter,expected", [("q1", 4), ("q2", 3), ("q3", 2), ("q4", 1)])
def test_a_later_quarter_has_fewer_quarter_ends_left_in_the_session(quarter, expected):
    assert len(quarter_end_charge_dates(quarter, SESSION)) == expected


def test_the_thousand_lands_at_each_boundary_and_not_between_them():
    assert _fine("q1", "2026-09-30")["quarter_end_charges"] == 1
    assert _fine("q1", "2026-10-01")["quarter_end_charges"] == 2
    assert _fine("q1", "2026-12-31")["quarter_end_charges"] == 2
    assert _fine("q1", "2027-01-01")["quarter_end_charges"] == 3


# ─────────────────────────── paying it off ─────────────────────────────────


def test_paying_on_the_twentieth_is_charged_five_days():
    # Judgement recorded in the service docstring: the day of payment counts. Worth a
    # sentence from Sonu; it is one day either way.
    out = _fine("q1", "2026-06-30", settled_on="2026-04-20")
    assert out["daily_days"] == 5
    assert out["total"] == 50.0


def test_paying_before_the_next_quarter_avoids_the_thousand():
    out = _fine("q1", "2027-04-01", settled_on="2026-06-20")
    assert out["quarter_end_charges"] == 0
    assert out["total"] == 660.0                        # 16 April to 20 June, 66 days


def test_a_quarter_with_nothing_outstanding_carries_no_fine():
    assert _fine("q1", "2027-04-01", outstanding=0)["total"] == 0.0


# ─────────────── the whole bill, transport included ────────────────────────


def test_the_fine_is_one_per_child_per_quarter_not_one_per_fee_head():
    # The daily figure is a flat 10, so the size of the bill decides only WHETHER a fine
    # runs. A child owing the school fee and transport owes one fine, not two.
    school_and_transport = _fine("q1", "2026-06-30", outstanding=9750 + 715)
    school_only = _fine("q1", "2026-06-30", outstanding=9750)
    assert school_and_transport["total"] == school_only["total"] == 760.0


def test_a_right_to_education_child_is_fined_on_transport_alone():
    # No school fee at all, so their outstanding figure is the bus and nothing else. The
    # fine follows the ordinary schedule, the 1,000 included.
    out = _fine("q1", "2026-07-01", outstanding=715)
    assert out["daily_amount"] == 760.0
    assert out["quarter_end_charges"] == 1
    assert out["total"] == 1760.0


def test_a_right_to_education_child_who_does_not_use_the_bus_owes_nothing():
    assert _fine("q1", "2027-04-01", outstanding=0)["total"] == 0.0


# ───────────────────────── reading the whole child ─────────────────────────


def test_a_family_that_has_paid_nothing_all_session():
    out = assess_quarters(
        [{"quarter": q, "outstanding_amount": 9750} for q in ("q1", "q2", "q3", "q4")],
        session_start_year=SESSION, as_of="2027-03-31",
    )
    by_quarter = {q["quarter"]: q for q in out["quarters"]}
    assert by_quarter["q1"]["quarter_end_charges"] == 3      # 1 April has not arrived
    assert by_quarter["q4"]["quarter_end_charges"] == 0
    assert by_quarter["q4"]["still_accruing_daily"] is True
    assert out["daily_running"] == "q4"
    # Daily: Q1 760, Q2 770 (16 July to 30 Sept), Q3 770 (16 Oct to 31 Dec), Q4 750
    # (16 Jan to 31 March). Flat: 3 + 2 + 1 + 0 thousands.
    assert out["total"] == 760 + 770 + 770 + 750 + 6000
