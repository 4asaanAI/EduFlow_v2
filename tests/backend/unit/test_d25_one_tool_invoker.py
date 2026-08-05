"""D-25 — there is one way to run a registry tool, not two.

The chat tool-loop and the tool-panel endpoint were two doors into `TOOL_REGISTRY`,
each with its own lookup, gate, scope resolution, calling convention and failure shape.
Story 4.5 unified the gate; this file holds the line on the rest.

The test that matters is `test_no_door_calls_a_tool_function_directly`. Every other test
here checks behaviour that is correct today; that one fails the moment someone adds a
third door, or reintroduces a direct `tool_def["fn"](...)` call in an existing one,
which is how the drift happened both previous times.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ai.tool_invoker import (
    FORBIDDEN,
    UNKNOWN,
    WRITE_BLOCKED,
    ToolNotAvailable,
    invoke_tool,
    resolve_tool,
    tool_accepts_scope,
)

BACKEND = Path(__file__).resolve().parents[3] / "backend"

OWNER = {"id": "d25-owner", "role": "owner", "name": "Owner"}
STUDENT = {"id": "d25-stu", "role": "student", "name": "Student"}


# ── The structural guard ─────────────────────────────────────────────────────

def test_no_door_calls_a_tool_function_directly():
    """Nobody may reach into a registry entry and call `fn` themselves.

    `ai/tool_invoker.py` is the one place allowed to, because it IS the invoker.
    A new door that calls `tool_def["fn"](params, user)` directly gets its own idea
    of the gate, the scope and the failure shape within a release or two — that is
    the whole of D-25, twice over.
    """
    pattern = re.compile(r"""\[["']fn["']\]\s*\(""")
    offenders = []
    for path in BACKEND.rglob("*.py"):
        if path.name == "tool_invoker.py":
            continue
        if "__pycache__" in path.parts:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(BACKEND)}:{i}  {line.strip()}")

    assert not offenders, (
        "These call a tool's function directly instead of going through "
        "ai.tool_invoker.invoke_tool:\n  " + "\n  ".join(offenders)
    )


def test_both_doors_import_the_invoker():
    """A door that stops importing it has almost certainly grown its own copy."""
    for door in ("routes/chat.py", "routes/tools.py"):
        source = (BACKEND / door).read_text(encoding="utf-8")
        assert "from ai.tool_invoker import" in source, f"{door} no longer uses the shared invoker"


# ── The gate, once ───────────────────────────────────────────────────────────

def test_unknown_tool_raises_with_reason_unknown():
    with pytest.raises(ToolNotAvailable) as exc:
        resolve_tool("no_such_tool_at_all", OWNER)
    assert exc.value.reason == UNKNOWN


def test_forbidden_tool_raises_with_reason_forbidden():
    """A real tool the caller may not use is a different answer from an unknown one.

    Both doors need this distinction and word it differently: chat must not tell
    someone a capability does not exist when it does, and the tool panel must give
    the same 403 either way so the registry cannot be mapped by comparing statuses.
    """
    from ai.tool_functions_v2 import TOOL_REGISTRY

    owner_only = next(
        name for name, td in TOOL_REGISTRY.items()
        if "owner" in td.get("roles", []) and "student" not in td.get("roles", [])
    )
    with pytest.raises(ToolNotAvailable) as exc:
        resolve_tool(owner_only, STUDENT)
    assert exc.value.reason == FORBIDDEN


def test_write_tool_is_refused_only_when_the_door_asks_for_reads():
    """`require_read_only` is the door's policy, not a property of the tool.

    The tool panel passes it (writes there would skip the confirm token, the
    kill-switch, the destructive acknowledgment and the audit row). Chat does not,
    because chat is where all of those live.
    """
    from ai.tool_functions_v2 import TOOL_REGISTRY, WRITE_TOOL_NAMES

    write_tool = next(n for n in WRITE_TOOL_NAMES if "owner" in TOOL_REGISTRY[n].get("roles", []))

    with pytest.raises(ToolNotAvailable) as exc:
        resolve_tool(write_tool, OWNER, require_read_only=True)
    assert exc.value.reason == WRITE_BLOCKED

    # Same tool, same caller, no read-only requirement: allowed through.
    assert resolve_tool(write_tool, OWNER) is TOOL_REGISTRY[write_tool]


def test_authorize_override_is_honoured():
    """`routes/chat.py` passes its own `_is_tool_authorized` alias, which is the
    symbol its tests import. It must actually be the function that runs."""
    from ai.tool_functions_v2 import TOOL_REGISTRY

    name = next(iter(TOOL_REGISTRY))
    calls = []

    def _refuse_everything(user, tool_def):
        calls.append(tool_def)
        return False

    with pytest.raises(ToolNotAvailable) as exc:
        resolve_tool(name, OWNER, authorize=_refuse_everything)
    assert exc.value.reason == FORBIDDEN
    assert calls, "the supplied authorize callable was never consulted"


# ── The calling convention, once ─────────────────────────────────────────────

async def test_two_argument_tool_is_called_with_two_arguments():
    """The tool-panel door used to pass scope unconditionally.

    Every registered tool takes three arguments today, so this never bit — but the
    first two-argument tool would have raised a TypeError there and been reported as
    a generic "Tool execution failed", while chat handled it fine. One invoker means
    one answer.
    """
    seen = {}

    async def _two_args(params, user):
        seen["args"] = 2
        return {"success": True, "data": [], "meta": {"count": 0}}

    tool_def = {"fn": _two_args, "roles": ["owner"]}
    assert tool_accepts_scope(tool_def) is False

    await invoke_tool("fake_two_arg", {}, OWNER, scope="a-scope", tool_def=tool_def)
    assert seen["args"] == 2


async def test_three_argument_tool_receives_the_scope():
    """The scope is what stops a branch-bound caller reading another branch."""
    seen = {}

    async def _three_args(params, user, scope):
        seen["scope"] = scope
        return {"success": True, "data": [], "meta": {"count": 0}}

    tool_def = {"fn": _three_args, "roles": ["owner"]}
    assert tool_accepts_scope(tool_def) is True

    await invoke_tool("fake_three_arg", {}, OWNER, scope="branch-a-scope", tool_def=tool_def)
    assert seen["scope"] == "branch-a-scope"


async def test_none_params_become_an_empty_dict():
    """A door that has no parameters must not hand the tool `None`."""
    seen = {}

    async def _fn(params, user, scope):
        seen["params"] = params
        return {"success": True, "data": [], "meta": {"count": 0}}

    await invoke_tool("fake", None, OWNER, scope=None, tool_def={"fn": _fn, "roles": ["owner"]})
    assert seen["params"] == {}


# ── The envelope, unchanged ──────────────────────────────────────────────────

async def test_the_invoker_returns_the_tools_own_envelope_untouched():
    """Story 4.1's defect was a SECOND envelope added by one of the doors.

    The invoker is now in the position that door was in, so it is the place a third
    envelope would be introduced. It must return the identical object.
    """
    envelope = {"success": True, "data": {"summary": {"x": 1}}, "meta": {"count": 1},
                "message": "", "denied": False}

    async def _fn(params, user, scope):
        return envelope

    result = await invoke_tool("fake", {}, OWNER, scope=None, tool_def={"fn": _fn, "roles": ["owner"]})
    assert result is envelope


async def test_a_failing_tool_raises_rather_than_being_swallowed():
    """The confirm/executor path runs tools inside a transaction and needs the
    exception to reach the executor so the write rolls back. An invoker that caught
    it would turn a failed write into a successful-looking turn."""
    async def _boom(params, user, scope):
        raise RuntimeError("mongodb://user:hunter2@cluster.example/eduflow")

    with pytest.raises(RuntimeError):
        await invoke_tool("fake", {}, OWNER, scope=None, tool_def={"fn": _boom, "roles": ["owner"]})


def test_safe_failure_never_carries_the_exception_text():
    from ai.tool_invoker import safe_failure

    try:
        raise RuntimeError("mongodb://user:hunter2@cluster.example/eduflow")
    except RuntimeError as exc:
        result = safe_failure("some_tool", exc)

    assert result["error"] == "data_unavailable"
    assert result["correlation_id"]
    assert "hunter2" not in str(result)
    assert "mongodb" not in str(result).lower()
