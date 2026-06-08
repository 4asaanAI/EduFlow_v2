"""CI drift gate (Story F.6): every AI write tool must have a parity corpus entry.

Fails if a tool in `WRITE_TOOL_NAMES` lacks a `PARITY_CORPUS` mapping, OR if a
mapped parity test file is missing on disk. This is the gate that prevents a new
write tool/route from shipping without continuous AI-vs-UI parity proof.
"""

from __future__ import annotations

import os

import pytest

from ai.tool_functions_v2 import WRITE_TOOL_NAMES
from tests.backend.parity.corpus import PARITY_CORPUS


_PARITY_DIR = os.path.dirname(__file__)


def test_every_write_tool_has_a_parity_corpus_entry():
    missing = sorted(set(WRITE_TOOL_NAMES) - set(PARITY_CORPUS))
    assert not missing, (
        f"These AI write tools have no parity corpus entry (F.6 drift gate): {missing}. "
        "Add a dual-entrypoint parity test and register it in parity/corpus.py."
    )


def test_corpus_entries_reference_existing_test_files():
    absent = sorted(
        {fn for fn in PARITY_CORPUS.values() if not os.path.exists(os.path.join(_PARITY_DIR, fn))}
    )
    assert not absent, f"Parity corpus references missing test files: {absent}"


def test_corpus_has_no_stale_entries():
    stale = sorted(set(PARITY_CORPUS) - set(WRITE_TOOL_NAMES))
    assert not stale, f"Parity corpus references tools not in WRITE_TOOL_NAMES: {stale}"
