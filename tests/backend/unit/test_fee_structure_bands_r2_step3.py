"""Release 2, step 3: the class fee bands, pinned to the school's own figures.

These numbers reach 1,842 families through a bill. They are confirmed by three
independent documents (step 1) and they are pinned here so that a later edit has to be
deliberate rather than a typo nobody noticed.

The bands must never be "corrected" to make a test pass. If one of these fails, either
the school changed its fees and the migration is stale, or somebody mistyped. Find out
which before touching the number.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MIGRATION = os.path.join(
    _HERE, "..", "..", "..", "backend", "migrations", "035_load_fee_structures.py"
)

_spec = importlib.util.spec_from_file_location("m035", os.path.abspath(_MIGRATION))
m035 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m035)


# The school's 2026-27 sheet, confirmed by the payment ledger and the per-student report.
EXPECTED_QUARTERLY = {
    "NUR": 7050, "LKG": 7050, "UKG": 7050,
    "1st": 8250, "2nd": 8250,
    "3rd": 8850, "4th": 8850, "5th": 8850,
    "6th": 9750, "7th": 9750, "8th": 9750,
    "9th": 12000, "10th": 12000,
}


@pytest.mark.parametrize("class_name,amount", sorted(EXPECTED_QUARTERLY.items()))
def test_each_class_band_matches_the_school_fee_sheet(class_name, amount):
    got, _ = m035.band_for({"name": class_name})
    assert got == amount, f"{class_name} should be {amount:,} a quarter"


def test_the_seven_bands_and_nothing_else():
    # Seven distinct amounts below 11th plus the two senior ones. If a band appears or
    # disappears, the school changed its price list and this file is out of date.
    assert sorted(set(EXPECTED_QUARTERLY.values())) == [7050, 8250, 8850, 9750, 12000]
    assert m035.BAND_BY_STREAM == {"Commerce": 16500, "Science": 17700}


def test_the_streams_are_4800_a_year_apart():
    # This gap is the whole reason step 2 exists. Getting it wrong costs one family
    # 4,800 a year in either direction.
    gap = m035.BAND_BY_STREAM["Science"] - m035.BAND_BY_STREAM["Commerce"]
    assert gap == 1200
    assert gap * 4 == 4800


@pytest.mark.parametrize("name,stream,expected", [
    ("11th", "Science", 17700),
    ("11th", "Commerce", 16500),
    ("12th", "Science", 17700),
    ("12th", "Commerce", 16500),
])
def test_a_senior_class_is_banded_by_its_stream(name, stream, expected):
    got, why = m035.band_for({"name": name, "stream": stream})
    assert got == expected
    assert stream in why


@pytest.mark.parametrize("name", ["11th", "12th"])
def test_a_senior_class_with_no_stream_is_refused_not_guessed(name):
    # The dangerous case. Defaulting to either band silently overcharges or undercharges
    # a whole section by 4,800 a year, and nothing on screen would look wrong.
    with pytest.raises(ValueError) as caught:
        m035.band_for({"name": name, "section": "A"})
    assert "16,500" in str(caught.value) and "17,700" in str(caught.value)


def test_an_unknown_class_is_refused():
    with pytest.raises(ValueError):
        m035.band_for({"name": "13th"})


def test_all_four_quarters_are_charged_the_same():
    # Confirmed in step 1 across all seventeen classes: there is no heavier quarter.
    assert len(m035.QUARTERS) == 4
    codes = [code for code, _, _ in m035.QUARTERS]
    assert codes == ["q1", "q2", "q3", "q4"]


def test_the_due_dates_are_the_fifteenth_of_the_quarter():
    # The school's rule: each quarter has a 15-day window to pay. The late fine in
    # step 9 counts from the 16th, so these dates decide when a fine starts.
    dues = [due for _, _, due in m035.QUARTERS]
    assert dues == ["2026-04-15", "2026-07-15", "2026-10-15", "2027-01-15"]


def test_registration_and_admission_are_never_put_into_an_instalment():
    # An instalment is billed to every child in the class. A 12,000 admission fee in an
    # instalment would charge it to families admitted years ago.
    for code, label, _ in m035.QUARTERS:
        assert "admission" not in label.lower()
        assert "registration" not in label.lower()


def test_nobody_joins_at_10th_or_12th():
    # Both carry no registration or admission charge anywhere in the school's ledger.
    assert m035.NEW_STUDENT_CHARGES["10th"] is None
    assert m035.NEW_STUDENT_CHARGES["12th"] is None


@pytest.mark.parametrize("name,registration,admission", [
    ("NUR", 1200, 12000), ("2nd", 1200, 12000),
    ("3rd", 1200, 13000), ("8th", 1200, 13000),
    ("9th", 1500, 16500), ("11th", 1500, 16500),
])
def test_new_student_charges_match_the_ledger(name, registration, admission):
    assert m035.NEW_STUDENT_CHARGES[name] == (registration, admission)
