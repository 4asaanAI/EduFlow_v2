"""R4-3 - two years in full, a monthly summary forever.

The tests that matter most here are the ones proving the job REFUSES. Thinning is the
only thing on the platform that deletes the school's history, so every test below is
really asking one question: can this lose something?

`test_nothing_is_deleted_when_the_summary_did_not_save` is the important one. The audit
writer elsewhere is deliberately fail-open (it logs and carries on rather than failing
somebody's save), and fail-open plus delete-first is exactly how a year of records would
disappear with nobody noticing until they went looking.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services import audit_retention as ar
from tests.backend.conftest import FakeCollection


SCHOOL = "aaryans-joya"
NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)


class _DB:
    """Just enough database for the retention job, with dict-style access."""

    def __init__(self):
        self.audit_logs = FakeCollection([])
        self.audit_summaries = FakeCollection([])

    def __getitem__(self, name):
        return getattr(self, name)


def _entry(created_at, *, who="lalit", action="update", coll="students", eid=None):
    return {
        "id": eid or f"a-{created_at}-{who}-{action}",
        "schoolId": SCHOOL,
        "created_at": created_at,
        "changed_by": who,
        "changed_by_role": "admin",
        "action": action,
        "collection": coll,
        "entity_id": "stu-1",
        "changes": {},
    }


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------

def test_the_cutoff_is_two_calendar_years_back():
    assert ar.cutoff_iso(NOW).startswith("2024-08-12")


def test_the_cutoff_does_not_drift_on_a_leap_day():
    """365-day arithmetic slips a day every leap year and eventually eats a live month."""
    leap = datetime(2028, 2, 29, tzinfo=timezone.utc)
    assert ar.cutoff_iso(leap).startswith("2026-02-2")


async def test_a_month_inside_the_window_is_refused():
    db = _DB()
    with pytest.raises(ar.RetentionRefusedError) as exc:
        await ar.thin_one_month(db, "2026-07", SCHOOL, now=NOW)
    assert "kept in full" in str(exc.value)


async def test_a_month_inside_the_window_is_refused_however_large_it_is():
    db = _DB()
    db.audit_logs = FakeCollection([_entry(f"2026-07-01T0{i}:00:00+00:00", eid=f"x{i}") for i in range(9)])
    with pytest.raises(ar.RetentionRefusedError):
        await ar.thin_one_month(db, "2026-07", SCHOOL, now=NOW)
    assert len(db.audit_logs.docs) == 9


# ---------------------------------------------------------------------------
# Nothing is lost
# ---------------------------------------------------------------------------

async def test_nothing_is_deleted_when_the_summary_did_not_save(monkeypatch):
    """The one that matters. Summary first, verified, THEN delete."""
    db = _DB()
    db.audit_logs = FakeCollection([_entry("2023-03-05T10:00:00+00:00", eid="old-1")])

    async def _insert_that_silently_does_nothing(doc, **kwargs):
        return None

    monkeypatch.setattr(db.audit_summaries, "insert_one", _insert_that_silently_does_nothing)

    with pytest.raises(ar.RetentionRefusedError) as exc:
        await ar.thin_one_month(db, "2023-03", SCHOOL, now=NOW)
    assert "Nothing was deleted" in str(exc.value)
    assert len(db.audit_logs.docs) == 1, "detail was deleted despite the summary failing"


async def test_an_unreadable_date_below_the_cutoff_is_reported_not_swallowed():
    db = _DB()
    db.audit_logs = FakeCollection([
        _entry("2023-03-05T10:00:00+00:00", eid="ok"),
        {"id": "broken", "schoolId": SCHOOL, "created_at": "", "changes": {}},
    ])
    preview = await ar.plan(db, now=NOW)
    assert preview["entries_with_unreadable_dates_left_alone"] == 1
    assert preview["months"] == {"2023-03": 1}


async def test_an_unreadable_date_above_the_cutoff_is_left_in_full():
    """Dates are compared as text, so "sometime" reads as recent. That is the safe way round.

    An entry nobody can place in time must never be summarised away. Being treated as
    recent means it is kept in full, which is the error worth making.
    """
    db = _DB()
    db.audit_logs = FakeCollection([
        {"id": "broken", "schoolId": SCHOOL, "created_at": "sometime", "changes": {}},
    ])
    preview = await ar.plan(db, now=NOW)
    assert preview["entries_to_summarise"] == 0
    await ar.run(db, SCHOOL, now=NOW)
    assert any(d["id"] == "broken" for d in db.audit_logs.docs)


async def test_plan_changes_nothing():
    db = _DB()
    db.audit_logs = FakeCollection([_entry("2023-03-05T10:00:00+00:00", eid="old-1")])
    await ar.plan(db, now=NOW)
    assert len(db.audit_logs.docs) == 1
    assert len(db.audit_summaries.docs) == 0


# ---------------------------------------------------------------------------
# Summarising
# ---------------------------------------------------------------------------

def test_a_summary_holds_counts_not_copies():
    entries = [_entry(f"2023-03-0{i}T10:00:00+00:00", eid=f"e{i}") for i in range(1, 6)]
    rows = ar.summarise(entries, "2023-03", SCHOOL)
    assert len(rows) == 1
    assert rows[0]["count"] == 5
    assert "changes" not in rows[0], "a summary must not carry copies of the detail"


def test_a_summary_is_grouped_by_person_and_kind_of_change():
    entries = [
        _entry("2023-03-01T10:00:00+00:00", who="lalit", action="update", eid="1"),
        _entry("2023-03-02T10:00:00+00:00", who="lalit", action="create", eid="2"),
        _entry("2023-03-03T10:00:00+00:00", who="sonu", action="update", eid="3"),
    ]
    rows = ar.summarise(entries, "2023-03", SCHOOL)
    assert len(rows) == 3
    assert {r["changed_by"] for r in rows} == {"lalit", "sonu"}


def test_a_summary_carries_the_school():
    rows = ar.summarise([_entry("2023-03-01T10:00:00+00:00")], "2023-03", SCHOOL)
    assert rows[0]["schoolId"] == SCHOOL


# ---------------------------------------------------------------------------
# Thinning, end to end
# ---------------------------------------------------------------------------

async def test_an_old_month_is_summarised_and_its_detail_removed():
    db = _DB()
    db.audit_logs = FakeCollection([
        _entry(f"2023-03-0{i}T10:00:00+00:00", eid=f"old-{i}") for i in range(1, 5)
    ] + [_entry("2026-08-01T10:00:00+00:00", eid="recent")])

    result = await ar.thin_one_month(db, "2023-03", SCHOOL, now=NOW)

    assert result["summarised"] == 1
    assert result["deleted"] == 4
    remaining = [d["id"] for d in db.audit_logs.docs]
    assert "recent" in remaining, "a live entry was deleted"
    assert not any(r.startswith("old-") for r in remaining)


async def test_the_thinning_writes_its_own_entry_saying_what_it_did():
    """History that quietly shrinks is the same failure as history never written."""
    db = _DB()
    db.audit_logs = FakeCollection([_entry("2023-03-01T10:00:00+00:00", eid="old-1")])

    await ar.thin_one_month(db, "2023-03", SCHOOL, now=NOW)

    rows = [d for d in db.audit_logs.docs if d.get("action") == "audit_thin"]
    assert len(rows) == 1
    assert "2023-03" in rows[0]["reason"]
    assert "kept permanently" in rows[0]["reason"]


async def test_running_twice_does_not_summarise_the_summary():
    db = _DB()
    db.audit_logs = FakeCollection([_entry("2023-03-01T10:00:00+00:00", eid="old-1")])

    await ar.thin_one_month(db, "2023-03", SCHOOL, now=NOW)
    again = await ar.thin_one_month(db, "2023-03", SCHOOL, now=NOW)

    assert again["skipped"] == "already summarised"
    assert again["deleted"] == 0
    assert len([d for d in db.audit_summaries.docs if d["month"] == "2023-03"]) == 1


async def test_a_month_with_nothing_in_it_is_a_no_op():
    db = _DB()
    result = await ar.thin_one_month(db, "2023-03", SCHOOL, now=NOW)
    assert result["skipped"] == "nothing to summarise"


async def test_run_processes_oldest_first_so_an_interruption_leaves_a_clean_boundary():
    db = _DB()
    db.audit_logs = FakeCollection([
        _entry("2022-01-05T10:00:00+00:00", eid="a"),
        _entry("2023-06-05T10:00:00+00:00", eid="b"),
        _entry("2024-01-05T10:00:00+00:00", eid="c"),
    ])
    result = await ar.run(db, SCHOOL, now=NOW, max_months=2)
    months = [m["month"] for m in result["months_processed"]]
    assert months == ["2022-01", "2023-06"]


async def test_run_leaves_everything_inside_the_window_alone():
    db = _DB()
    db.audit_logs = FakeCollection([
        _entry("2022-01-05T10:00:00+00:00", eid="old"),
        _entry("2026-08-01T10:00:00+00:00", eid="live"),
        _entry("2025-01-01T10:00:00+00:00", eid="alsolive"),
    ])
    await ar.run(db, SCHOOL, now=NOW)
    remaining = {d["id"] for d in db.audit_logs.docs if d.get("action") != "audit_thin"}
    assert {"live", "alsolive"} <= remaining
    assert "old" not in remaining
