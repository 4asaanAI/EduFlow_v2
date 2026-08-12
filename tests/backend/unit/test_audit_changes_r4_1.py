"""R4-1 - the one shape for a recorded change.

The test that matters most in this file is
`test_empty_before_is_distinguishable_from_unrecorded_before`. Every other assertion
here is scaffolding around that one distinction, because it is the ambiguity that makes
an undo dishonest: a field that used to be blank and a field whose earlier value nobody
wrote down look identical in every legacy shape, and an undo that confuses them will
erase a real value while reporting success.
"""

from __future__ import annotations

import pytest

from services import audit_changes as ac


# ---------------------------------------------------------------------------
# The distinction the whole module exists for
# ---------------------------------------------------------------------------

def test_empty_before_is_distinguishable_from_unrecorded_before():
    was_empty = ac.edit({"phone": None}, {"phone": "99999"})
    never_recorded = ac.edit(None, {"phone": "99999"})

    assert was_empty["fields"]["phone"]["previous_known"] is True
    assert never_recorded["fields"]["phone"]["previous_known"] is False

    # Both carry previous=None. Only the flag tells them apart, which is the point:
    # without it these two rows are byte-identical and one of them is a lie.
    assert was_empty["fields"]["phone"]["previous"] is None
    assert never_recorded["fields"]["phone"]["previous"] is None


def test_unrecorded_before_is_never_offered_as_reversible():
    """Putting None back into a field whose old value was never recorded ERASES it."""
    never_recorded = ac.edit(None, {"name": "Rohan"})
    assert ac.reversible_fields(never_recorded) == {}


def test_genuinely_empty_before_is_reversible():
    was_empty = ac.edit({"nickname": None}, {"nickname": "Chotu"})
    assert ac.reversible_fields(was_empty) == {"nickname": None}


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

def test_edit_records_previous_and_new():
    changes = ac.edit({"name": "Aman"}, {"name": "Aman Litt"})
    assert changes["kind"] == "edit"
    assert changes["fields"]["name"] == {
        "previous": "Aman", "new": "Aman Litt", "previous_known": True,
    }


def test_edit_drops_fields_that_did_not_change():
    changes = ac.edit({"name": "Aman", "class_id": "5A"}, {"name": "Aman", "class_id": "5B"})
    assert set(changes["fields"]) == {"class_id"}


def test_edit_with_nothing_changed_says_so_rather_than_recording_an_empty_edit():
    changes = ac.edit({"name": "Aman"}, {"name": "Aman"})
    assert changes["kind"] == "none"
    assert "already held that value" in changes["why"]


def test_edit_ignores_platform_bookkeeping_fields():
    changes = ac.edit({"name": "A"}, {"name": "B", "updated_at": "now", "_id": "x"})
    assert set(changes["fields"]) == {"name"}


def test_edit_can_be_limited_to_named_fields():
    changes = ac.edit({"a": 1, "b": 1}, {"a": 2, "b": 2}, fields=["a"])
    assert set(changes["fields"]) == {"a"}


def test_create_and_delete_carry_a_snapshot():
    assert ac.created({"id": "s1", "name": "Rohan"})["kind"] == "create"
    assert ac.removed({"id": "s1", "name": "Rohan"})["snapshot"]["name"] == "Rohan"


def test_delete_without_a_copy_says_so_instead_of_pretending():
    changes = ac.removed(None)
    assert changes["kind"] == "none"
    assert "before a copy" in changes["why"]


def test_bulk_keeps_the_count_at_the_top_level():
    changes = ac.bulk({"date": "2026-08-12"}, affected=41)
    assert changes["kind"] == "bulk"
    assert changes["affected"] == 41


def test_none_refuses_to_record_an_empty_reason():
    assert ac.none("")["why"] == "No reason was recorded."


# ---------------------------------------------------------------------------
# Reading: every legacy shape lands in the one shape
# ---------------------------------------------------------------------------

def test_legacy_previous_new_shape_stays_reversible():
    legacy = {"name": {"previous": "A", "new": "B"}}
    out = ac.normalise(legacy)
    assert out["kind"] == "edit"
    assert out["fields"]["name"]["previous_known"] is True
    assert ac.reversible_fields(legacy) == {"name": "A"}


def test_legacy_before_after_shape():
    out = ac.normalise({"before": {"phone": "1"}, "after": {"phone": "2"}})
    assert out["fields"]["phone"] == {"previous": "1", "new": "2", "previous_known": True}


def test_legacy_created_and_deleted_shapes():
    assert ac.normalise({"created": {"id": "x"}})["kind"] == "create"
    assert ac.normalise({"deleted": {"id": "x"}})["kind"] == "delete"


def test_legacy_count_summary_becomes_bulk_with_the_count_surfaced():
    out = ac.normalise({"count_marked": 41, "date": "2026-08-12"})
    assert out["kind"] == "bulk"
    assert out["affected"] == 41


def test_legacy_import_batch_becomes_bulk():
    assert ac.normalise({"import_batch": "b1", "rows_written": 300})["kind"] == "bulk"


def test_legacy_nested_previous_state_shape():
    out = ac.normalise({"previous_state": {"house": {"previous": "Red", "new": "Blue"}}})
    assert out["fields"]["house"]["previous"] == "Red"


def test_legacy_new_values_only_shape_is_marked_unrecorded_not_empty():
    """The most common legacy shape, and the one that must not be flattered."""
    out = ac.normalise({"student_id": "s1", "position": "Head Boy"})
    assert out["kind"] == "edit"
    assert all(f["previous_known"] is False for f in out["fields"].values())
    assert ac.reversible_fields(out) == {}


def test_a_half_recorded_row_keeps_the_half_it_recorded():
    """Different code paths wrote different halves of the same edit.

    Rejecting the whole row on one incomplete field threw away every good before-value
    beside it, so a change that was half reversible became entirely irreversible and the
    person was told nothing could be put back when most of it could.
    """
    out = ac.normalise({
        "house": {"previous": "Red", "new": "Blue"},
        "roll_number": {"new": "13"},
    })
    assert out["fields"]["house"]["previous_known"] is True
    assert out["fields"]["roll_number"]["previous_known"] is False
    assert ac.reversible_fields(out) == {"house": "Red"}


def test_a_row_with_no_details_says_so():
    for empty in ({}, None, "", []):
        assert ac.normalise(empty)["kind"] == "none"


def test_normalise_is_idempotent():
    once = ac.normalise({"name": {"previous": "A", "new": "B"}})
    assert ac.normalise(once) == once


def test_normalise_does_not_downgrade_a_reversible_row():
    """The ordering guard: the catch-all branch must not swallow richer shapes.

    `{"before": …, "after": …}` also matches "a plain dict of values". If the catch-all
    ran first, this row would come back with previous_known=False and a reversible
    change would silently become irreversible at read time.
    """
    out = ac.normalise({"before": {"a": 1}, "after": {"a": 2}})
    assert out["fields"]["a"]["previous_known"] is True


# ---------------------------------------------------------------------------
# Describing
# ---------------------------------------------------------------------------

def test_describe_says_out_loud_when_earlier_values_are_missing():
    text = ac.describe({"position": "Head Boy"})
    assert "not recorded" in text


def test_describe_covers_every_kind():
    assert "Created" in ac.describe(ac.created({"id": "1"}))
    assert "Removed" in ac.describe(ac.removed({"id": "1"}))
    assert "41" in ac.describe(ac.bulk({}, affected=41))
    assert ac.describe(ac.none("Because."))  == "Because."


@pytest.mark.parametrize("kind_builder", [
    lambda: ac.edit({"a": 1}, {"a": 2}),
    lambda: ac.created({"a": 1}),
    lambda: ac.removed({"a": 1}),
    lambda: ac.bulk({"a": 1}),
    lambda: ac.none("why"),
])
def test_every_built_change_carries_a_kind(kind_builder):
    """A reader must never have to sniff keys to work out what a row is."""
    assert kind_builder()["kind"] in ac.VALID_KINDS
