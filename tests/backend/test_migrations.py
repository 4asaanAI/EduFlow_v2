from __future__ import annotations
"""
CI guard: every migration file must be listed in run_all.py, in order.
These tests catch the class of bug where a migration file is added to
backend/migrations/ but forgotten in the runner's MIGRATIONS list.
"""

import os
import re
from pathlib import Path

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
