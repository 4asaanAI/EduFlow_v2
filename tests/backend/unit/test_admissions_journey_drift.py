"""A3 - the checked-in JS mirror must still match the Python journey vocabulary.

Same shape as `test_profile_matrix_drift.py`. A checked-in generated file is only worth
having if something notices when it goes stale. If this fails, run:

    backend/.venv/Scripts/python.exe scripts/generate_admissions_journey.py

and commit the result. Never hand-edit the JS: it changes nothing about what the server
answers and only hides the drift.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATOR = REPO_ROOT / "scripts" / "generate_admissions_journey.py"
MIRROR = REPO_ROOT / "frontend" / "src" / "lib" / "admissionsJourney.generated.js"


def _load_generator():
    spec = importlib.util.spec_from_file_location("_generate_admissions_journey", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_generated_mirror_is_present():
    assert MIRROR.exists(), (
        "the frontend mirror of the admissions journey is missing; run "
        "scripts/generate_admissions_journey.py"
    )


def test_the_generated_mirror_matches_the_python_vocabulary():
    generator = _load_generator()
    assert MIRROR.read_text(encoding="utf-8") == generator.render(), (
        "frontend/src/lib/admissionsJourney.generated.js has drifted from "
        "backend/services/admissions_journey.py. Run "
        "`backend/.venv/Scripts/python.exe scripts/generate_admissions_journey.py` and "
        "commit the result. Do not hand-edit the JS."
    )


def test_every_stage_on_both_sides_has_a_step():
    """A stage with no step would show a family as position unknown, which reads as a
    broken record rather than as a stage nobody mapped."""
    from services.admissions_journey import (
        APPLICATION_STAGE_TO_STEP,
        ENQUIRY_STAGE_TO_STEP,
        STEP_KEYS,
    )
    from services.admissions_service import TRANSITIONS as APPLICATION_TRANSITIONS
    from services.enquiry_service import ALLOWED_TRANSITIONS as ENQUIRY_TRANSITIONS

    enquiry_stages = set(ENQUIRY_TRANSITIONS) | {
        target for targets in ENQUIRY_TRANSITIONS.values() for target in targets
    }
    application_stages = set(APPLICATION_TRANSITIONS) | {
        target for targets in APPLICATION_TRANSITIONS.values() for target in targets
    }
    assert enquiry_stages <= set(ENQUIRY_STAGE_TO_STEP), (
        f"enquiry stages with no journey step: {enquiry_stages - set(ENQUIRY_STAGE_TO_STEP)}"
    )
    assert application_stages <= set(APPLICATION_STAGE_TO_STEP), (
        f"application stages with no journey step: "
        f"{application_stages - set(APPLICATION_STAGE_TO_STEP)}"
    )
    for mapping in (ENQUIRY_STAGE_TO_STEP, APPLICATION_STAGE_TO_STEP):
        assert set(mapping.values()) <= set(STEP_KEYS)
