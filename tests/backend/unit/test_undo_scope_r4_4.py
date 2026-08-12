"""R4-4 - undo what hurts, and guide the rest.

The test that matters most is `test_the_management_head_cannot_undo_a_fee_entry`. A fee
entry hurts when it is wrong, so it belongs on the undoable list. But the management head
may not touch money at all, and if "this kind of change is undoable" were the only test,
undo would become a way round the Release 2 permission table that looked like a feature.
Both questions have to be asked, every time.
"""

from __future__ import annotations

import pytest

from services import undo_scope as us


OWNER = {"role": "owner", "sub_category": "owner", "id": "aman"}
PRINCIPAL = {"role": "admin", "sub_category": "principal", "id": "adesh"}
ACCOUNTANT = {"role": "admin", "sub_category": "accountant", "id": "sonu"}
MANAGEMENT = {"role": "admin", "sub_category": "management", "id": "lalit"}
TEACHER = {"role": "teacher", "id": "t1"}


def _entry(changes, collection="students"):
    return {"id": "a1", "collection": collection, "entity_id": "x", "changes": changes}


# ---------------------------------------------------------------------------
# Two tests, always. The kind of change AND the person.
# ---------------------------------------------------------------------------

def test_the_management_head_cannot_undo_a_fee_entry():
    """Undoing must never become a back door into money (decision 1, 2026-08-10)."""
    assert us.hurts("fee_transactions") is True
    assert us.may_reverse(MANAGEMENT, "fee_transactions") is False
    reason = us.refusal_reason(MANAGEMENT, _entry({}, "fee_transactions"))
    assert "your profile" in reason


def test_the_accountant_head_can_undo_a_fee_entry():
    assert us.may_reverse(ACCOUNTANT, "fee_transactions") is True
    assert us.refusal_reason(ACCOUNTANT, _entry({}, "fee_transactions")) == ""


def test_the_management_head_can_undo_a_child_record():
    assert us.may_reverse(MANAGEMENT, "students") is True


def test_the_accountant_head_cannot_undo_attendance():
    """Money is his side of the wall; the roll is not."""
    assert us.may_reverse(ACCOUNTANT, "attendance") is False


def test_the_owner_and_principal_can_reverse_both_sides():
    for user in (OWNER, PRINCIPAL):
        assert us.may_reverse(user, "fee_transactions") is True
        assert us.may_reverse(user, "attendance") is True


def test_somebody_outside_the_permission_table_can_reverse_nothing():
    assert us.may_reverse(TEACHER, "students") is False
    assert us.may_reverse({}, "students") is False


def test_a_kind_of_change_that_does_not_hurt_is_refused_with_a_reason():
    reason = us.refusal_reason(OWNER, _entry({}, "house_points"))
    assert "not something the platform does automatically" in reason


def test_every_entry_on_the_hurts_list_says_why_it_is_there():
    for collection, rule in us.HURTS.items():
        assert len(rule["why"]) > 60, f"{collection}: no real reason given"
        assert rule["domain"] in {us.FINANCE, us.NON_FINANCE, us.LEADERSHIP}


# ---------------------------------------------------------------------------
# Guidance: the larger half of decision 4
# ---------------------------------------------------------------------------

def test_an_edit_produces_the_exact_value_to_type_back():
    entry = _entry({"house": {"previous": "Red", "new": "Blue"}})
    out = us.guidance(entry)
    assert out["can_guide"] is True
    joined = " ".join(out["steps"])
    assert '"Red"' in joined and '"Blue"' in joined


def test_a_field_that_was_empty_is_described_as_empty_not_as_a_blank_step():
    entry = _entry({"nickname": {"previous": None, "new": "Chotu"}})
    joined = " ".join(us.guidance(entry)["steps"])
    assert "back to empty" in joined


def test_guidance_refuses_rather_than_inventing_a_step_it_cannot_support():
    """The most common legacy shape: new values only, no before value."""
    out = us.guidance(_entry({"house": "Blue"}))
    assert out["can_guide"] is False
    assert "not what they were before" in out["reason"]
    assert out["steps"] == []


def test_fields_with_no_recorded_before_value_are_named_out_loud():
    """A confident list that silently omits two fields reads as "that is everything"."""
    entry = _entry({
        "house": {"previous": "Red", "new": "Blue"},
        "roll_number": {"new": "13"},
    })
    out = us.guidance(entry)
    assert out["can_guide"] is True
    joined = " ".join(out["steps"])
    assert "roll_number" in joined
    assert "never recorded" in joined


def test_a_created_record_is_guided_towards_the_right_person():
    out = us.guidance(_entry({"created": {"id": "s1", "name": "Rohan"}}))
    assert out["can_guide"] is True
    assert any("removing it again" in s for s in out["steps"])
    assert any("owner" in s and "principal" in s for s in out["steps"])


def test_a_deleted_record_is_guided_from_the_copy_that_was_kept():
    out = us.guidance(_entry({"deleted": {"id": "s1", "name": "Rohan", "house": "Red"}}))
    assert out["can_guide"] is True
    joined = " ".join(out["steps"])
    assert "name" in joined and "house" in joined


def test_a_bulk_change_says_plainly_that_it_cannot_help():
    out = us.guidance(_entry({"count_marked": 41, "date": "2026-08-12"}))
    assert out["can_guide"] is False
    assert "41 records" in out["reason"]
    assert out["steps"] == []


def test_guidance_never_returns_steps_when_it_cannot_guide():
    """A half-answer here sends somebody to overwrite a good value with a blank."""
    for changes in ({}, {"house": "Blue"}, {"count_marked": 3}, None):
        out = us.guidance(_entry(changes))
        if not out["can_guide"]:
            assert out["steps"] == []
            assert out["reason"]
