"""R4-1 - undo now reads every recorded shape, and refuses the dishonest ones.

Before this change `undo_service` hand-checked a single shape and refused everything
else. Two consequences, and they pull in opposite directions:

* It refused changes it could honestly have reversed, because the same before-value was
  written in different words on different paths. A person was told to ask the principal
  for a change the platform could perfectly well have put back.
* It had no way to tell "this field used to be empty" from "nobody wrote down what this
  field used to be", so widening it naively would have started ERASING values while
  reporting success.

These tests pin both halves. Widening without the second half would be worse than the
narrowness it replaced.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services import undo_service
from services.actor_context import ActorContext


def _ctx():
    return ActorContext(
        user_id="lalit", role="admin", sub_category="management",
        school_id="aaryans-joya", branch_id="branch-joya", actor_name="Lalit Thomas",
    )


def _entry(changes, *, action="update", entity_type="student"):
    return {
        "id": "audit-1",
        "entity_type": entity_type,
        "entity_id": "stu-1",
        "action": action,
        "changed_by": "lalit",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "changes": changes,
    }


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Wider: shapes that carry a real before-value are now accepted
# ---------------------------------------------------------------------------

def test_the_original_shape_still_works():
    entry = _entry({"name": {"previous": "Rohan", "new": "Rohan Kumar"}})
    assert undo_service.explain_refusal(entry, _ctx(), _now()) == ""
    assert undo_service.undoable_fields(entry) == {"name": "Rohan"}


def test_before_after_wording_is_now_reversible():
    """Same information, different words. Previously refused for no good reason."""
    entry = _entry({"before": {"house": "Red"}, "after": {"house": "Blue"}})
    assert undo_service.explain_refusal(entry, _ctx(), _now()) == ""
    assert undo_service.undoable_fields(entry) == {"house": "Red"}


def test_nested_previous_state_wording_is_now_reversible():
    entry = _entry({"previous_state": {"roll_number": {"previous": "12", "new": "13"}}})
    assert undo_service.explain_refusal(entry, _ctx(), _now()) == ""
    assert undo_service.undoable_fields(entry) == {"roll_number": "12"}


def test_a_field_that_was_genuinely_empty_can_be_put_back_to_empty():
    entry = _entry({"nickname": {"previous": None, "new": "Chotu"}})
    assert undo_service.explain_refusal(entry, _ctx(), _now()) == ""
    assert undo_service.undoable_fields(entry) == {"nickname": None}


# ---------------------------------------------------------------------------
# Still honest: shapes with no before-value are still refused, and say why
# ---------------------------------------------------------------------------

def test_new_values_only_is_refused_because_putting_none_back_would_erase():
    """The most common legacy shape on the platform. Widening must NOT swallow it."""
    entry = _entry({"name": "Rohan Kumar", "house": "Blue"})
    reason = undo_service.explain_refusal(entry, _ctx(), _now())
    assert "does not include what the value was before" in reason
    assert undo_service.undoable_fields(entry) == {}


def test_a_bulk_summary_is_refused():
    entry = _entry({"count_marked": 41, "date": "2026-08-12"})
    assert undo_service.explain_refusal(entry, _ctx(), _now()) != ""
    assert undo_service.undoable_fields(entry) == {}


def test_an_empty_record_of_a_change_is_refused():
    assert undo_service.explain_refusal(_entry({}), _ctx(), _now()) != ""


# ---------------------------------------------------------------------------
# The old guards are untouched. Reading more shapes must not grant more reach.
# ---------------------------------------------------------------------------

def test_money_is_still_refused_whatever_shape_it_arrives_in():
    entry = _entry({"before": {"salary": 20000}, "after": {"salary": 99000}})
    reason = undo_service.explain_refusal(entry, _ctx(), _now())
    assert "cannot be put back this way" in reason
    assert undo_service.undoable_fields(entry) == {}


def test_the_refusal_names_the_real_field_not_the_words_before_and_after():
    """A `before`/`after` row used to have its own wrapper keys read as field names.

    The refusal then told the user their change to "after" could not be put back, which
    is not a field, not something they typed, and not actionable.
    """
    entry = _entry({"before": {"fees": 100}, "after": {"fees": 200}})
    reason = undo_service.explain_refusal(entry, _ctx(), _now())
    assert "fees" in reason
    assert "after" not in reason.split("which cannot")[0]


def test_somebody_elses_change_is_still_refused_first():
    entry = _entry({"name": {"previous": "A", "new": "B"}})
    entry["changed_by"] = "sonu"
    assert "somebody else" in undo_service.explain_refusal(entry, _ctx(), _now())


def test_yesterdays_change_is_still_refused():
    entry = _entry({"name": {"previous": "A", "new": "B"}})
    entry["created_at"] = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    assert "not made today" in undo_service.explain_refusal(entry, _ctx(), _now())


def test_a_collection_outside_students_and_staff_is_still_refused():
    entry = _entry({"name": {"previous": "A", "new": "B"}}, entity_type="fee_transactions")
    assert "student or staff record" in undo_service.explain_refusal(entry, _ctx(), _now())


def test_a_create_is_still_refused_because_undoing_it_means_deleting():
    entry = _entry({"created": {"id": "stu-1", "name": "Rohan"}}, action="create")
    assert undo_service.explain_refusal(entry, _ctx(), _now()) != ""
