"""Release 2 step 5: the school's four fee concessions.

Every figure asserted here comes from
``_bmad-output/implementation-artifacts/release-2/fee-rules-from-sonu-2026-08-11.md``,
which is the authority on how the school charges.
"""

from __future__ import annotations

import pytest

from services.concession_service import (
    ConcessionRuleError,
    SIBLING_BY_QUARTERLY_BAND,
    admission_concession,
    assert_not_transport,
    compute_concessions,
    employee_child_amount,
    full_year_amount,
    full_year_qualifies,
    sibling_amount,
)


# ───────────────────────────── sibling ─────────────────────────────────────


def test_the_seven_sibling_values_are_the_schools_seven_and_no_others():
    # The seven values already loaded on the platform, against the seven quarterly bands.
    assert sorted(SIBLING_BY_QUARTERLY_BAND.values()) == [
        1410, 1560, 1650, 1800, 2100, 2610, 2910
    ]
    assert sorted(SIBLING_BY_QUARTERLY_BAND) == [
        7050, 8250, 8850, 9750, 12000, 16500, 17700
    ]


@pytest.mark.parametrize("band,expected", sorted(SIBLING_BY_QUARTERLY_BAND.items()))
def test_sibling_amount_is_flat_per_quarter_by_the_childs_own_band(band, expected):
    assert sibling_amount(band) == float(expected)


def test_an_unknown_band_refuses_rather_than_inventing_a_value():
    with pytest.raises(ConcessionRuleError) as exc:
        sibling_amount(9999)
    assert "seven quarterly bands" in str(exc.value)


# ───────────────────────── employee's child ────────────────────────────────


def test_employee_child_is_half_the_quarters_fee():
    assert employee_child_amount(17700) == 8850.0
    assert employee_child_amount(7050) == 3525.0


def test_employee_concession_wins_over_sibling_and_they_do_not_stack():
    student = {"concessions": {"employee_child": True, "sibling": True}}
    out = compute_concessions(student, quarterly_amount=9750, installment_code="q1")
    # 50% of 9,750 is 4,875. The sibling value for that band is 1,800. Neither the sum
    # (6,675) nor the sibling figure is correct: the employee one wins by rule.
    assert out["total"] == 4875.0
    assert out["net"] == 4875.0
    rules = {line["rule"]: line["amount"] for line in out["lines"]}
    assert rules == {"employee_child": 4875.0, "sibling": 0.0}


def test_the_employee_rule_wins_even_when_the_sibling_value_would_be_larger():
    # Guards the wording: it is the employee one by RULE, never the better of the two.
    # There is no band where sibling beats 50%, so this pins the reasoning rather than
    # arithmetic: the sibling line is always reported at zero when both marks are set.
    for band in SIBLING_BY_QUARTERLY_BAND:
        out = compute_concessions(
            {"concessions": {"employee_child": True, "sibling": True}},
            quarterly_amount=band,
            installment_code="q1",
        )
        assert out["total"] == employee_child_amount(band)


# ─────────────────── the whole year paid by 30 April ───────────────────────


@pytest.mark.parametrize("paid_on,qualifies", [
    ("2026-04-01", True),
    ("2026-04-30", True),    # the deadline itself counts
    ("2026-05-01", False),   # one day late
    ("2026-08-11", False),   # the parent paying the full year in August
    (None, False),
])
def test_five_percent_needs_payment_by_30_april(paid_on, qualifies):
    assert full_year_qualifies(paid_on, session_start_year=2026) is qualifies


def test_five_percent_of_the_sessions_fee():
    assert full_year_amount(39000, "2026-04-15", session_start_year=2026) == 1950.0
    assert full_year_amount(39000, "2026-08-15", session_start_year=2026) == 0.0


# ─────────────────── the one-time concession at admission ──────────────────


def _with_admission(**over):
    record = {"amount": 6000, "authorised_by": "Aman Litt", "authorised_on": "2026-04-02"}
    record.update(over)
    return {"id": "stu-1", "concessions": {"admission_discount": record}}


def test_a_one_time_concession_must_name_who_authorised_it():
    with pytest.raises(ConcessionRuleError) as exc:
        admission_concession(_with_admission(authorised_by=""), "q1")
    assert "who authorised it" in str(exc.value)


def test_the_one_time_concession_applies_to_the_first_quarter_and_no_other():
    student = _with_admission()
    amount, _ = admission_concession(student, "q1")
    assert amount == 6000.0

    # Once an instalment has consumed it, every LATER quarter gets nothing.
    student["concessions"]["admission_discount"]["applied_to"] = "q1"
    assert admission_concession(student, "q2")[0] == 0.0
    assert admission_concession(student, "q3")[0] == 0.0
    assert admission_concession(student, "q4")[0] == 0.0
    # Re-previewing the quarter that consumed it is not a second gift; it is the same one.
    assert admission_concession(student, "q1")[0] == 6000.0


def test_the_one_time_concession_carries_the_authoriser_onto_the_bill():
    out = compute_concessions(_with_admission(), quarterly_amount=8850, installment_code="q1")
    line = [row for row in out["lines"] if row["rule"] == "admission_one_time"][0]
    assert line["authorised_by"] == "Aman Litt"
    assert line["applies_once"] is True
    assert out["net"] == 2850.0


# ────────────────────────── transport, and nothing ─────────────────────────


def test_transport_is_never_discounted_and_says_so_loudly():
    with pytest.raises(ConcessionRuleError) as exc:
        assert_not_transport("Transport Fees August")
    assert "no concession of any kind" in str(exc.value)

    with pytest.raises(ConcessionRuleError):
        compute_concessions(
            {"concessions": {"sibling": True}},
            quarterly_amount=650,
            installment_code="q1",
            fee_head="Transport Fee",
        )


def test_a_child_with_no_marks_pays_the_full_fee():
    # Every child on the platform today, so this is what step 5 changes about their bill:
    # nothing at all.
    out = compute_concessions({}, quarterly_amount=12000, installment_code="q2")
    assert out == {"lines": [], "total": 0.0, "gross": 12000.0, "net": 12000.0}


def test_concessions_never_take_a_bill_below_zero():
    student = _with_admission(amount=999999)
    out = compute_concessions(student, quarterly_amount=7050, installment_code="q1")
    assert out["net"] == 0.0
    assert out["total"] == 7050.0
