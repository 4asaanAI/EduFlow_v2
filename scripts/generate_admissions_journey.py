"""Generate the frontend's mirror of the admissions journey vocabulary.

Same reasoning as `generate_profile_matrix.py`: the vocabulary lives in Python because
the server is what answers with it, the screens need the same answer, and teaching the
frontend build to shell out to Python buys a new failure mode on the Amplify runner and
nothing else. So the mirror is generated and CHECKED IN, and
`tests/backend/unit/test_admissions_journey_drift.py` fails the suite if it goes stale.

    backend/.venv/Scripts/python.exe scripts/generate_admissions_journey.py

Writes `frontend/src/lib/admissionsJourney.generated.js`. No network, no database.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from services.admissions_journey import (  # noqa: E402
    APPLICATION_STAGE_TO_STEP,
    ENQUIRY_STAGE_TO_STEP,
    JOURNEY_STEPS,
)

TARGET = REPO_ROOT / "frontend" / "src" / "lib" / "admissionsJourney.generated.js"

HEADER = """/**
 * GENERATED FILE - DO NOT EDIT BY HAND.
 *
 * Mirror of `backend/services/admissions_journey.py`, which is the source of truth for
 * how the enquiry and application vocabularies line up. Regenerate with:
 *
 *     backend/.venv/Scripts/python.exe scripts/generate_admissions_journey.py
 *
 * `tests/backend/unit/test_admissions_journey_drift.py` fails if this file stops
 * matching the Python. Editing this file by hand changes nothing about what the server
 * answers; it only breaks that test, which is the intended outcome.
 *
 * Read the Python file for the reasoning behind every line below.
 */

"""


def render() -> str:
    steps = [{"step": key, "label": label} for key, label in JOURNEY_STEPS]
    return (
        HEADER
        + f"export const JOURNEY_STEPS = {json.dumps(steps, indent=2)};\n\n"
        + "export const STEP_LABELS = "
        + json.dumps({key: label for key, label in JOURNEY_STEPS}, indent=2, sort_keys=True)
        + ";\n\nexport const ENQUIRY_STAGE_TO_STEP = "
        + json.dumps(ENQUIRY_STAGE_TO_STEP, indent=2, sort_keys=True)
        + ";\n\nexport const APPLICATION_STAGE_TO_STEP = "
        + json.dumps(APPLICATION_STAGE_TO_STEP, indent=2, sort_keys=True)
        + ";\n"
    )


def main() -> int:
    text = render()
    previous = TARGET.read_text(encoding="utf-8") if TARGET.exists() else None
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(("unchanged: " if previous == text else "written:   ")
          + str(TARGET.relative_to(REPO_ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
