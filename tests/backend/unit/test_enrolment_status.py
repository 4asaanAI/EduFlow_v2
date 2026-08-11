from __future__ import annotations

"""The three states before a record is destroyed, and the way back.

Owner requests 9 and 10, 2026-08-06. Aman described the school's actual practice: a
student who stops attending goes onto an "NSO" list and **keeps appearing in the daily
attendance register** until the transfer certificate is issued, at which point the name
comes off. The platform had a single on/off switch and no word for the middle.

The case that matters most here is the one that caused the report: before
`set_enrolment_state` existed, `is_active` was absent from UPDATABLE_FIELDS, so nothing
in the entire product could turn a student back on. A student deactivated during a demo
was unreachable, and the only visible symptom was a headcount one short.
"""

import pytest

from backend.services import enrolment_status as es


# ─── Reading a stored record ────────────────────────────────────────────────────

def test_a_plain_active_student_reads_as_active():
    assert es.normalise({"is_active": True, "status": "active"}) == es.ACTIVE


def test_an_nso_student_reads_as_nso_even_though_they_are_switched_off():
    assert es.normalise({"is_active": False, "status": "nso"}) == es.NSO


def test_a_legacy_withdrawn_row_reads_as_tc_issued():
    # Every student deactivated before this existed carries status "withdrawn" and no
    # NSO concept. Reading those as TC issued keeps them off the register, which is
    # exactly how they behaved the day before - no existing row changes meaning.
    assert es.normalise({"is_active": False, "status": "withdrawn"}) == es.TC_ISSUED


def test_a_row_with_no_status_at_all_falls_back_to_the_switch():
    assert es.normalise({"is_active": True}) == es.ACTIVE
    assert es.normalise({"is_active": False}) == es.TC_ISSUED


def test_an_empty_or_missing_record_does_not_explode():
    # This reads rows written by three versions of the product; a throw here would
    # take out the whole student list rather than one row.
    assert es.normalise(None) == es.ACTIVE
    assert es.normalise({}) == es.ACTIVE


def test_a_junk_status_is_not_mistaken_for_a_real_state():
    assert es.normalise({"is_active": False, "status": "<script>"}) == es.TC_ISSUED


# ─── Writing a state ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("state,expected_active", [
    (es.ACTIVE, True),
    (es.NSO, False),
    (es.TC_ISSUED, False),
])
def test_both_fields_are_always_written_together(state, expected_active):
    # The whole point of this module. Writing `status` alone is what left a student
    # labelled "active" while `is_active` stayed False and every screen kept hiding
    # them.
    fields = es.fields_for(state)
    assert fields == {"is_active": expected_active, "status": state}


def test_an_unknown_state_is_refused_rather_than_written():
    with pytest.raises(ValueError):
        es.fields_for("deleted")


def test_erasure_is_not_a_settable_state():
    # Permanent erasure destroys the record and demands a written reason. It is a
    # different operation in a different, owner-only route - not a fourth position on
    # this switch.
    assert "erased" not in es.SETTABLE_STATES
    assert set(es.SETTABLE_STATES) == {es.ACTIVE, es.NSO, es.TC_ISSUED}


# ─── Who is on the register ─────────────────────────────────────────────────────

def _matches(filt: dict, doc: dict) -> bool:
    """Evaluate the small subset of Mongo these filters use, in memory."""
    if "$or" in filt:
        return any(_matches(clause, doc) for clause in filt["$or"])
    for key, expected in filt.items():
        actual = doc.get(key)
        if isinstance(expected, dict) and "$ne" in expected:
            if actual == expected["$ne"]:
                return False
        elif actual != expected:
            return False
    return True


def test_an_nso_student_is_still_on_the_daily_register():
    """THE rule Aman asked for. If this ever goes false, an NSO student silently stops
    being marked and the school loses the very signal the list exists to give."""
    assert _matches(es.on_register_filter(), {"is_active": False, "status": es.NSO})


def test_an_active_student_is_on_the_register():
    assert _matches(es.on_register_filter(), {"is_active": True, "status": es.ACTIVE})


def test_a_student_with_a_tc_is_off_the_register():
    assert not _matches(es.on_register_filter(), {"is_active": False, "status": es.TC_ISSUED})


def test_a_legacy_withdrawn_student_is_off_the_register():
    assert not _matches(es.on_register_filter(), {"is_active": False, "status": "withdrawn"})


def test_nso_is_on_the_register_but_not_on_the_roll():
    # A school with three NSO students has 1,801 students and 1,804 names to mark.
    # Conflating those two numbers is how a headcount goes wrong.
    assert es.is_on_roll(es.NSO) is False
    assert es.is_on_roll(es.ACTIVE) is True


# ─── The recycle bin ────────────────────────────────────────────────────────────

def test_the_recycle_bin_holds_everything_off_the_roll():
    for doc in (
        {"is_active": False, "status": es.NSO},
        {"is_active": False, "status": es.TC_ISSUED},
        {"is_active": False, "status": "withdrawn"},
    ):
        assert _matches(es.in_recycle_bin_filter(), doc), doc


def test_the_student_deactivated_during_the_demo_is_findable():
    """The exact shape `DELETE /api/students/{id}` writes. It has to turn up in the
    restore list, or owner request 9 has no answer."""
    demo_row = {"is_active": False, "status": "withdrawn", "withdrawal_date": "2026-08-05"}
    assert _matches(es.in_recycle_bin_filter(), demo_row)


def test_an_active_student_is_not_in_the_recycle_bin():
    assert not _matches(es.in_recycle_bin_filter(), {"is_active": True, "status": es.ACTIVE})
