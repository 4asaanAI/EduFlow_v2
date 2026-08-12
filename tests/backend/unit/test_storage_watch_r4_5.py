"""R4-5 - the storage watch, and the one thing it must never do.

The failure this file is really guarding against is the same one that runs through the
whole of Release 4: **"we could not find out" must never come out looking like "you are
fine".** A storage check that returns quietly when the database will not answer reads,
on a screen, exactly like a school with plenty of room, right up until the day nothing
saves.

The rest of it is the cost rule from Part 4a: no threshold is invented. Until somebody
tells the platform what its limit is, it reports the number and declines to judge it.
"""

from __future__ import annotations

import pytest

from services import storage_watch


class _Db:
    """Just enough database to answer, or refuse to answer, a dbStats command."""

    def __init__(self, stats=None, fail=False):
        self._stats = stats or {}
        self._fail = fail

    async def command(self, name, *args, **kwargs):
        if self._fail:
            raise RuntimeError("not authorised to run dbStats")
        return self._stats


_HEALTHY = {"storageSize": 100 * 1024 * 1024, "indexSize": 20 * 1024 * 1024,
            "dataSize": 150 * 1024 * 1024, "collections": 40, "objects": 120_000}


# ── Measuring ─────────────────────────────────────────────────────────────────

async def test_it_reports_what_is_actually_on_disk_not_the_logical_size():
    """`storageSize` + `indexSize` is what a hosting limit counts. `dataSize` is bigger
    and using it would raise the alarm months early, which trains people to ignore it."""
    reading = await storage_watch.measure(_Db(_HEALTHY))
    assert reading["measured"] is True
    assert reading["used_mb"] == 120.0
    assert reading["data_mb"] == 150.0


async def test_being_unable_to_measure_is_not_the_same_as_being_fine():
    reading = await storage_watch.measure(_Db(fail=True))
    assert reading["measured"] is False

    verdict = storage_watch.assess(reading)
    assert verdict["level"] == "unknown"
    assert verdict["should_report"] is True
    # And it says so in words, to whoever reads it.
    assert "not the same as there being plenty of room" in verdict["message"]


# ── Judging ───────────────────────────────────────────────────────────────────

async def test_with_no_ceiling_configured_it_gives_the_number_and_no_verdict(monkeypatch):
    """Part 4a: measure before optimising. A made-up threshold makes made-up alarms."""
    monkeypatch.delenv(storage_watch.CEILING_ENV, raising=False)
    verdict = storage_watch.assess(await storage_watch.measure(_Db(_HEALTHY)))
    assert verdict["level"] == "fine"
    assert verdict["should_report"] is False
    assert "cannot say whether that is a lot" in verdict["message"]


async def test_a_ceiling_that_is_not_a_number_is_treated_as_no_ceiling(monkeypatch):
    monkeypatch.setenv(storage_watch.CEILING_ENV, "loads")
    assert storage_watch.ceiling_mb() is None


@pytest.mark.parametrize("used_mb,limit,expected", [
    (100, 1000, "fine"),      # a tenth
    (699, 1000, "fine"),      # just under seven tenths
    (700, 1000, "concern"),   # exactly at it
    (899, 1000, "concern"),
    (900, 1000, "urgent"),    # exactly at nine tenths
    (1200, 1000, "urgent"),   # already over
])
async def test_the_levels_land_where_they_are_supposed_to(used_mb, limit, expected):
    reading = {"measured": True, "used_mb": float(used_mb)}
    assert storage_watch.assess(reading, ceiling=float(limit))["level"] == expected


async def test_a_concern_says_how_much_is_left_in_words_a_person_reads():
    verdict = storage_watch.assess({"measured": True, "used_mb": 750.0}, ceiling=1000.0)
    assert "750 MB of 1000 MB" in verdict["message"]
    assert "250 MB left" in verdict["message"]
    # Not alarming about something that is not yet a problem.
    assert "Nothing is broken" in verdict["message"]


async def test_running_out_says_what_will_actually_happen():
    verdict = storage_watch.assess({"measured": True, "used_mb": 950.0}, ceiling=1000.0)
    assert verdict["level"] == "urgent"
    assert "stop being able to save anything new" in verdict["message"]


async def test_large_sizes_are_given_in_gigabytes():
    verdict = storage_watch.assess({"measured": True, "used_mb": 4096.0}, ceiling=5120.0)
    assert "4.0 GB" in verdict["message"]


# ── Reporting, at most once per problem ───────────────────────────────────────

class _FakeTickets:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.inserted = []

    async def find_one(self, query, projection=None):
        return self.docs[0] if self.docs else None

    async def insert_one(self, doc):
        self.inserted.append(doc)

    async def update_one(self, *a, **k):
        return None


class _ReportDb(_Db):
    def __init__(self, stats, tickets):
        super().__init__(stats)
        self.platform_tickets = tickets

    async def list_collection_names(self):
        return []


async def test_nothing_is_reported_when_there_is_plenty_of_room(monkeypatch):
    monkeypatch.setenv(storage_watch.CEILING_ENV, "10000")
    db = _ReportDb(_HEALTHY, _FakeTickets())
    result = await storage_watch.maybe_report(db)
    assert result["reported"] is False
    assert db.platform_tickets.inserted == []


async def test_the_same_problem_is_not_reported_twice(monkeypatch):
    """Reported once per problem, not once per check. An inbox that gets the same
    ticket every day is an inbox nobody opens."""
    monkeypatch.setenv(storage_watch.CEILING_ENV, "100")
    already = _FakeTickets([{"id": "t-1", "title": "Storage: 120 MB in use", "status": "open"}])
    db = _ReportDb(_HEALTHY, already)
    result = await storage_watch.maybe_report(db)
    assert result["reported"] is False
    assert result["reason"] == "already reported and still open"
    assert already.inserted == []


async def test_it_stays_quiet_rather_than_risking_a_ticket_storm(monkeypatch):
    """If we cannot tell whether we already said it, say nothing. A missed repeat is a
    small harm; the same ticket every minute for a week is how tickets get ignored."""
    monkeypatch.setenv(storage_watch.CEILING_ENV, "100")

    class _Broken(_FakeTickets):
        async def find_one(self, query, projection=None):
            raise RuntimeError("index missing")

    db = _ReportDb(_HEALTHY, _Broken())
    result = await storage_watch.maybe_report(db)
    assert result["reported"] is False
    assert db.platform_tickets.inserted == []
