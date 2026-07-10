"""R4.2 (audit M1) — every registry READ tool returns the one envelope.

Iterates TOOL_REGISTRY, invokes each read tool against an empty (but permissive)
fake DB, and asserts the single result envelope:
`{success: bool, data, meta: {count}, message, denied: bool}`.

This doubles as an H5 robustness check: a read tool that raises on an empty DB /
missing records (instead of returning an envelope) fails here — one malformed or
absent doc must never 500 a tool.
"""

from __future__ import annotations

import pytest

from ai.tool_functions_v2 import TOOL_REGISTRY, WRITE_TOOL_NAMES
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


class _PermissiveDb:
    """Returns an empty FakeCollection for ANY collection name accessed."""

    def __getattr__(self, name):
        col = FakeCollection([])
        object.__setattr__(self, name, col)
        return col


# Read tools that are dispatched but intentionally out of this smoke's scope:
# recall_history fans out to other tools (covered by its own tests) and needs a
# subject; everything else is invoked with empty params.
_SKIP = set()

_ENVELOPE_KEYS = {"success", "data", "meta", "message", "denied"}


def _read_tools():
    return sorted(n for n in TOOL_REGISTRY if n not in WRITE_TOOL_NAMES and n not in _SKIP)


@pytest.mark.parametrize("tool_name", _read_tools())
async def test_read_tool_returns_envelope(tool_name, monkeypatch):
    import ai.tool_functions_v2 as v2
    import ai.tool_functions as v1

    db = _PermissiveDb()
    monkeypatch.setattr(v2, "get_db", lambda: db)
    monkeypatch.setattr(v1, "get_db", lambda: db)

    fn = TOOL_REGISTRY[tool_name]["fn"]
    user = {"id": "u1", "role": "owner", "name": "Tester"}

    # An empty DB / missing records must yield an envelope, never an exception (H5).
    result = await fn({}, user, None)

    assert isinstance(result, dict), f"{tool_name} did not return a dict"
    missing = _ENVELOPE_KEYS - set(result.keys())
    assert not missing, f"{tool_name} envelope missing keys: {missing} (got {sorted(result.keys())})"
    assert isinstance(result["success"], bool), f"{tool_name}.success not bool"
    assert isinstance(result["denied"], bool), f"{tool_name}.denied not bool"
    assert isinstance(result["meta"], dict) and "count" in result["meta"], f"{tool_name}.meta.count missing"
    # message is str or None
    assert result["message"] is None or isinstance(result["message"], str)


def test_every_registry_tool_is_read_or_write():
    """Sanity: the read/write partition covers the whole registry (no orphan)."""
    reads = set(_read_tools())
    writes = set(WRITE_TOOL_NAMES)
    assert reads.isdisjoint(writes)
    assert reads | writes == set(TOOL_REGISTRY.keys())
