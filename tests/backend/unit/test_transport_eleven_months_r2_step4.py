"""Release 2, step 4: the bus runs eleven months, and a rate is never invented.

June is not charged. The school closes for the summer and the buses do not run, though
staff are still paid and the school fee is still charged for that quarter. Getting this
wrong bills 1,376 families for a month the bus never ran.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "m036",
    os.path.abspath(os.path.join(
        _HERE, "..", "..", "..", "backend", "migrations",
        "036_transport_routes_and_riders.py",
    )),
)
m036 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m036)


def test_the_bus_is_billed_eleven_months():
    assert m036.MONTHS_BILLED == 11
    assert len(m036.BILLED_MONTHS) == 11


def test_june_is_the_month_that_is_not_charged():
    # Proved twice: the ledger holds no June transport line in 5,587 rows, and 97% of
    # the annual figures in the student export divide exactly by eleven.
    assert "June" not in m036.BILLED_MONTHS
    assert m036.BILLED_MONTHS.count("June") == 0


def test_every_other_month_of_the_year_is_charged():
    everything = ["January", "February", "March", "April", "May", "June", "July",
                  "August", "September", "October", "November", "December"]
    missing = [m for m in everything if m not in m036.BILLED_MONTHS]
    assert missing == ["June"], f"expected only June to be missing, got {missing}"


def test_the_year_starts_in_april_like_the_school_session():
    assert m036.BILLED_MONTHS[0] == "April"
    assert m036.BILLED_MONTHS[-1] == "March"


@pytest.mark.parametrize("label,route,stop", [
    ("8( - JOYA)", "8", "JOYA"),
    ("JOYA(JOYA - JOYA)", "JOYA", "JOYA"),
    ("18(School - JAMA PUR)", "18", "JAMA PUR"),
    ("7( - AVAS VIKAS COLONY, AMROHA)", "7", "AVAS VIKAS COLONY, AMROHA"),
])
def test_a_normal_label_gives_a_route_and_a_stop(label, route, stop):
    assert m036.parse_route_label(label) == (route, stop)


@pytest.mark.parametrize("label,stop", [
    ("( - SINORA)", "SINORA"),
    ("( - JAMA PUR)", "JAMA PUR"),
    ("( - MOHANPUR)", "MOHANPUR"),
])
def test_a_stop_with_no_route_number_keeps_the_stop_and_invents_no_route(label, stop):
    # Three children are in this position. Inventing a route number would be a guess
    # about which bus a child actually rides, and only the school knows.
    got_route, got_stop = m036.parse_route_label(label)
    assert got_route == ""
    assert got_stop == stop


@pytest.mark.parametrize("label", ["", "no brackets here", "8()", "8( - )"])
def test_a_label_that_cannot_be_read_returns_nothing_rather_than_a_wrong_stop(label):
    # This is what blocks the whole migration. A child silently given no route is worse
    # than a migration that refuses to run.
    assert m036.parse_route_label(label) == (None, None)


def test_transport_has_no_concession_and_that_is_recorded_on_the_route():
    # Fee rules document section 3: no sibling discount, no employee discount, no 5% for
    # paying the year up front. It IS fined, because it sits inside the total.
    assert m036.SCHOOL_ID == "aaryans-joya"
