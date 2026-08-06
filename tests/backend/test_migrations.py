from __future__ import annotations
"""
CI guard: every migration file must be listed in run_all.py, in order.
These tests catch the class of bug where a migration file is added to
backend/migrations/ but forgotten in the runner's MIGRATIONS list.
"""

import os
import re
import importlib
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "backend" / "migrations"
RUN_ALL_PATH = MIGRATIONS_DIR / "run_all.py"


def _migration_files():
    """Return sorted list of migration stem names (e.g. '001_add_branches')."""
    files = sorted(
        p.stem
        for p in MIGRATIONS_DIR.glob("*.py")
        if p.stem not in ("__init__", "run_all")
    )
    return files


def _run_all_text():
    return RUN_ALL_PATH.read_text()


def test_all_migration_files_in_run_all():
    """Every .py file in backend/migrations/ must be referenced in run_all.py."""
    text = _run_all_text()
    missing = []
    for stem in _migration_files():
        if stem not in text:
            missing.append(stem)
    assert missing == [], (
        f"The following migration files are NOT referenced in run_all.py: {missing}"
    )


def test_run_all_has_correct_order():
    """
    Migration references in run_all.py must appear in ascending numeric order
    (001 → 002 → … → latest).
    """
    text = _run_all_text()
    # Extract all NNN_ prefixes that appear in the MIGRATIONS list lines
    # Match strings like "001_add_branches" inside the MIGRATIONS list
    found = re.findall(r'"(\d{3}_[^"]+)"', text)
    # Filter to only the ones that look like migration entries (not descriptions)
    migration_entries = [f for f in found if re.match(r'^\d{3}_', f)]
    # Deduplicate preserving order (each appears twice: name + maybe description)
    seen = []
    for entry in migration_entries:
        if entry not in seen:
            seen.append(entry)

    numbers = [int(entry[:3]) for entry in seen]
    assert numbers == sorted(numbers), (
        f"Migrations in run_all.py are out of order: {seen}"
    )
    # Also verify they are consecutive with no gaps beyond what already exists
    expected = list(range(numbers[0], numbers[-1] + 1))
    assert numbers == expected, (
        f"Migration numbers have gaps. Found: {numbers}, expected consecutive: {expected}"
    )


@pytest.mark.asyncio
async def test_commercial_migration_is_repeatable_and_index_only():
    migration = importlib.import_module("backend.migrations.029_commercial_operations")
    calls = []

    class Collection:
        def __init__(self, name):
            self.name = name

        async def create_index(self, *args, **kwargs):
            calls.append((self.name, args, kwargs))

        def __getattr__(self, operation):
            if operation in {"insert_one", "insert_many", "update_one", "update_many", "delete_one", "delete_many"}:
                raise AssertionError(f"Migration 029 attempted data mutation: {self.name}.{operation}")
            raise AttributeError(operation)

    class Database:
        def __getattr__(self, name):
            return Collection(name)

    await migration.migrate(Database())
    once = list(calls)
    await migration.migrate(Database())
    assert once
    assert calls == once + once


@pytest.mark.asyncio
async def test_profile_notes_migration_is_repeatable_and_index_only():
    """Migration 030 exists because `_create_indexes()` does not run in production, so
    a migration is the ONLY way an index reaches the school's cluster.

    This is one of the few migrations in the folder that is safe to run against the
    live database, and this test is what makes that claim checkable: it fails loudly if
    the migration ever gains a write. Six of its neighbours insert convincing fake data
    (bus routes, library books, fee profiles), which is why "index-only" has to be
    proven rather than asserted in a docstring.
    """
    migration = importlib.import_module("backend.migrations.030_profile_notes_index")
    calls = []

    class Collection:
        def __init__(self, name):
            self.name = name

        async def create_index(self, *args, **kwargs):
            calls.append((self.name, args, kwargs))

        def __getattr__(self, operation):
            if operation in {"insert_one", "insert_many", "update_one", "update_many", "delete_one", "delete_many"}:
                raise AssertionError(f"Migration 030 attempted data mutation: {self.name}.{operation}")
            raise AttributeError(operation)

    class Database:
        def __getattr__(self, name):
            return Collection(name)

    await migration.migrate(Database())
    once = list(calls)
    await migration.migrate(Database())
    assert once, "the migration created no index at all"
    assert calls == once + once, "running it twice must be harmless"

    # It touches the notes collection and nothing else.
    assert {name for name, _, _ in once} == {"profile_notes"}


@pytest.mark.asyncio
async def test_profile_notes_index_matches_the_one_declared_in_database_py():
    """The migration and `database._create_indexes()` must declare the SAME index.

    If they drift, production and development disagree about what is indexed, and the
    difference surfaces months later as a mysteriously slow screen on the live site
    only.

    The migration side is checked by RUNNING it and capturing the real arguments,
    rather than by matching source text: an earlier version of this test compared
    strings and failed purely because the field list was wrapped across lines with a
    trailing comma, which is a formatting difference and not a drift.
    """
    migration = importlib.import_module("backend.migrations.030_profile_notes_index")
    captured = []

    class Collection:
        def __init__(self, name):
            self.name = name

        async def create_index(self, keys, **kwargs):
            captured.append(list(keys))

    class Database:
        def __getattr__(self, name):
            return Collection(name)

    await migration.migrate(Database())
    assert captured, "the migration created no index"
    actual = [tuple(pair) for pair in captured[0]]

    expected = [
        ("schoolId", 1),
        ("author_id", 1),
        ("subject_type", 1),
        ("subject_id", 1),
        ("created_at", -1),
    ]
    # Order matters: it IS the meaning of a compound index.
    assert actual == expected, f"the migration's index shape changed: {actual}"

    # And database.py must still declare the same fields in the same order.
    database_py = (MIGRATIONS_DIR.parent / "database.py").read_text(encoding="utf-8")
    declared = re.search(
        r"db\.profile_notes\.create_index\(\s*\[(.*?)\]", database_py, re.DOTALL
    )
    assert declared, "database.py no longer declares a profile_notes index"
    names_in_db = re.findall(r'\("(\w+)",\s*(-?1)\)', declared.group(1))
    assert [(n, int(d)) for n, d in names_in_db] == expected, (
        f"database.py and the migration disagree: {names_in_db}"
    )
