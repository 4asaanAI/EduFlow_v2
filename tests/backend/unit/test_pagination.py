from __future__ import annotations
"""The shared page-size rule for every list endpoint.

WHAT THIS FILE IS DEFENDING (Release 3, 2026-08-12)
---------------------------------------------------
The `ALL_ROWS` sentinel is -1. Every list route used to clamp with
`max(limit, 1)`, so asking for everything asked for ONE ROW and got it, with no
error anywhere. That was live on three screens. The rule pinned here is that a
page size below 1 is refused out loud, and that there is exactly one ceiling
rather than the eight different figures the routes used to carry.
"""

import pytest
from fastapi import HTTPException

from pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    clamp_page,
    clamp_page_size,
    page_meta,
)


# ── The defect this module exists to close ───────────────────────────────────

def test_all_rows_sentinel_is_refused_not_silently_turned_into_one_row():
    """-1 used to become 1. That is the bug; it must now be an error."""
    with pytest.raises(HTTPException) as err:
        clamp_page_size(-1)
    assert err.value.status_code == 400
    # The message has to tell the caller what to do instead, because the caller
    # is a screen wanting every row and there IS a right way to get them.
    assert "1 or more" in err.value.detail
    assert "pages" in err.value.detail


@pytest.mark.parametrize("bad", [0, -1, -500, -99999])
def test_page_size_below_one_is_always_refused(bad):
    with pytest.raises(HTTPException) as err:
        clamp_page_size(bad)
    assert err.value.status_code == 400
    assert str(bad) in err.value.detail


# ── The ceiling ──────────────────────────────────────────────────────────────

def test_one_ceiling_for_every_list():
    """Two existing tests already relied on over-asking being capped, not refused."""
    assert clamp_page_size(9999) == MAX_PAGE_SIZE
    assert clamp_page_size(100000) == MAX_PAGE_SIZE
    assert clamp_page_size(MAX_PAGE_SIZE + 1) == MAX_PAGE_SIZE


@pytest.mark.parametrize("asked", [1, 5, 20, 50, 100, 250, MAX_PAGE_SIZE])
def test_a_sane_page_size_is_honoured_exactly(asked):
    """Every size on the rows-per-page menu must survive untouched."""
    assert clamp_page_size(asked) == asked


def test_a_lower_ceiling_can_be_passed_for_an_expensive_list():
    assert clamp_page_size(500, 20) == 20
    assert clamp_page_size(5, 20) == 5


def test_a_lower_ceiling_still_refuses_the_sentinel():
    """A narrower endpoint must not reintroduce the silent one-row answer."""
    with pytest.raises(HTTPException):
        clamp_page_size(-1, 20)


def test_missing_page_size_falls_back_to_the_default():
    assert clamp_page_size(None) == DEFAULT_PAGE_SIZE


def test_a_page_size_that_is_not_a_number_is_refused():
    with pytest.raises(HTTPException) as err:
        clamp_page_size("lots")
    assert err.value.status_code == 400


def test_a_numeric_string_page_size_is_accepted():
    """FastAPI coerces query params, but Flo and internal callers pass raw values."""
    assert clamp_page_size("50") == 50


# ── Page numbers ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [0, -1, -20])
def test_page_below_one_is_refused(bad):
    """It used to be silently treated as page 1, or to produce a negative skip
    that Mongo rejected as a 500. Neither told the caller what was wrong."""
    with pytest.raises(HTTPException) as err:
        clamp_page(bad)
    assert err.value.status_code == 400
    assert str(bad) in err.value.detail


def test_a_real_page_number_is_honoured():
    assert clamp_page(1) == 1
    assert clamp_page(37) == 37


def test_missing_page_is_the_first_page():
    assert clamp_page(None) == 1


def test_a_page_that_is_not_a_number_is_refused():
    with pytest.raises(HTTPException):
        clamp_page("last")


# ── The meta block ───────────────────────────────────────────────────────────

def test_meta_always_carries_the_true_total():
    """A screen showing part of a list must be able to say how much it is not
    showing. An omitted total is how a partial answer passes as a whole one."""
    meta = page_meta(page=2, per_page=500, total=1876)
    assert meta == {"page": 2, "per_page": 500, "total": 1876}


def test_meta_reports_an_empty_list_as_empty_rather_than_unknown():
    assert page_meta(page=1, per_page=20, total=0)["total"] == 0
