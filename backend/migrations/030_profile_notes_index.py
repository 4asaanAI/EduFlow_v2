from __future__ import annotations


async def migrate(db) -> None:
    """Owner request 4 (2026-08-06): the index behind private profile notes.

    WHY A MIGRATION AT ALL. `database._create_indexes()` declares this index, but that
    function deliberately does NOT run in production (it is gated on
    `CREATE_INDEXES_ON_STARTUP` / a non-prod `ENVIRONMENT`) so that deploying code can
    never silently alter the school's data. Migrations are therefore the only way an
    index reaches the live cluster, and without this one the collection has no index at
    all beyond the default `_id`.

    WHAT IT COSTS TO SKIP. Nothing today. Every note read is already CORRECT without
    it; Mongo simply scans the collection instead of seeking. With a few dozen notes
    that is invisible. It matters once the collection grows into the thousands, which
    it will over a few years of the owner and the principal both writing notes.

    WHY THIS SHAPE. A note is private to whoever wrote it (Abhimanyu, 2026-08-06), so
    every single read is pinned to one author AND one subject, and the newest note is
    wanted first. `schoolId` leads because every query is school-scoped by
    `ScopedCollection`. The field order mirrors that access pattern exactly, and it
    mirrors the declaration in `database._create_indexes()` — if you change one, change
    both, or prod and dev will disagree about what is indexed.

    SAFE TO RUN ON THE LIVE DATABASE, unlike most of the migrations in this folder.
    It creates an index and writes no documents: it invents no bus routes, no library
    books and no fee profiles. It is also idempotent, so running it twice is harmless.

    STILL DO NOT RUN IT VIA `run_all.py`. That runner would execute every untracked
    migration alongside it, and six of those insert convincing fake data into what they
    assume is a fresh demo school. Run this one file on its own.
    """
    try:
        await db.profile_notes.create_index(
            [
                ("schoolId", 1),
                ("author_id", 1),
                ("subject_type", 1),
                ("subject_id", 1),
                ("created_at", -1),
            ]
        )
    except Exception:
        # Already present (created by _create_indexes on a dev boot, or by an earlier
        # run of this migration). Best-effort and idempotent, like the other index
        # migrations in this folder.
        pass
