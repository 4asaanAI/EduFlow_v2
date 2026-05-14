"""Meta-test: enforce sanitized 403 error messages across the codebase.

Part 1.5 Patch B — three routes still leaked `"Owner only"` strings,
which let an attacker enumerate owner-gated endpoints from a generic 403.
This meta-test fails if any future code introduces a fresh leak.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ROUTES_DIR = Path(__file__).resolve().parent.parent.parent / "backend" / "routes"

FORBIDDEN_PATTERNS = [
    re.compile(r'"Owner only"'),
    re.compile(r'"Owner-only"'),
    re.compile(r'"Owners? only"'),
    re.compile(r"'Owner only'"),
]


def test_no_owner_only_strings_in_routes():
    offenders = []
    for path in ROUTES_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pat in FORBIDDEN_PATTERNS:
            for m in pat.finditer(text):
                line_no = text[: m.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(ROUTES_DIR.parent.parent)}:{line_no}: {m.group(0)}")
    assert not offenders, (
        "403 error messages must say 'Forbidden', not leak role names. "
        "Offenders:\n  " + "\n  ".join(offenders)
    )
