"""R2-1 - the checked-in JS mirror must still match the Python matrix.

`backend/services/profile_matrix.py` is the source of truth for who may reach what.
`frontend/src/lib/profileMatrix.generated.js` is a generated mirror, checked in so
that Jest and Vite never have to run Python during a build.

A checked-in generated file is only worth having if something notices when it goes
stale. That is this test. If it fails, the fix is to run:

    backend/.venv/Scripts/python.exe scripts/generate_profile_matrix.py

and commit the result - never to hand-edit the JS, which changes nothing about
permissions and only hides the drift.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATOR = REPO_ROOT / "scripts" / "generate_profile_matrix.py"
MIRROR = REPO_ROOT / "frontend" / "src" / "lib" / "profileMatrix.generated.js"


def _load_generator():
    spec = importlib.util.spec_from_file_location("_generate_profile_matrix", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_generated_mirror_is_present():
    assert MIRROR.exists(), (
        "the frontend mirror of the profile matrix is missing; run "
        "scripts/generate_profile_matrix.py"
    )


def test_the_generated_mirror_matches_the_python_matrix():
    generator = _load_generator()
    expected = generator.render()
    actual = MIRROR.read_text(encoding="utf-8")
    assert actual == expected, (
        "frontend/src/lib/profileMatrix.generated.js has drifted from "
        "backend/services/profile_matrix.py. Run "
        "`backend/.venv/Scripts/python.exe scripts/generate_profile_matrix.py` and "
        "commit the result. Do not hand-edit the JS."
    )
