"""Generate the frontend's mirror of the profile matrix.

The matrix lives in Python because the server and Flo are the surfaces that actually
enforce it. The menus need the same answer, and the alternative — teaching Jest and
Vite to shell out to Python during a build — buys a build step, a new failure mode on
the Amplify runner, and nothing else.

So the mirror is generated and CHECKED IN, and
`tests/backend/unit/test_profile_matrix_drift.py` fails the suite if the checked-in
file stops matching. The checked-in file is the convenience. The drift test is the
point: it is what makes one source of truth true rather than aspirational.

    backend/.venv/Scripts/python.exe scripts/generate_profile_matrix.py

Writes `frontend/src/lib/profileMatrix.generated.js`. Read-only apart from that one
file: no network, no database.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from services.profile_matrix import ALL_SCREENS, PROFILE_MATRIX  # noqa: E402

TARGET = REPO_ROOT / "frontend" / "src" / "lib" / "profileMatrix.generated.js"

HEADER = """/**
 * GENERATED FILE — DO NOT EDIT BY HAND.
 *
 * Mirror of `backend/services/profile_matrix.py`, which is the source of truth for
 * who may reach what. Regenerate with:
 *
 *     backend/.venv/Scripts/python.exe scripts/generate_profile_matrix.py
 *
 * `tests/backend/unit/test_profile_matrix_drift.py` fails if this file stops
 * matching the Python. Editing this file by hand does not change permissions; it
 * only breaks that test, which is the intended outcome.
 *
 * Read the Python file for the reasoning behind every line below.
 */

"""


def _entry_to_json(entry: dict) -> dict:
    screens = entry["screens"]
    return {
        "person": entry["person"],
        "title": entry["title"],
        "status": entry["status"],
        "screens": ALL_SCREENS if screens == ALL_SCREENS else sorted(screens),
        "toolDomains": sorted(entry["tool_domains"]),
        "mayWrite": entry["may_write"],
        "mayDeletePeople": entry["may_delete_people"],
    }


def render() -> str:
    payload = {name: _entry_to_json(entry) for name, entry in PROFILE_MATRIX.items()}
    body = json.dumps(payload, indent=2, sort_keys=True)
    return (
        HEADER
        + f"export const ALL_SCREENS = {json.dumps(ALL_SCREENS)};\n\n"
        + f"export const PROFILE_MATRIX = {body};\n\n"
        + "export const LIVE_PROFILES = "
        + json.dumps(
            sorted(n for n, e in PROFILE_MATRIX.items() if e["status"] == "live")
        )
        + ";\n\nexport const DORMANT_PROFILES = "
        + json.dumps(
            sorted(n for n, e in PROFILE_MATRIX.items() if e["status"] == "dormant")
        )
        + ";\n"
    )


def main() -> int:
    text = render()
    previous = TARGET.read_text(encoding="utf-8") if TARGET.exists() else None
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    if previous == text:
        print(f"unchanged: {TARGET.relative_to(REPO_ROOT)}")
    else:
        print(f"written:   {TARGET.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
