"""The one way to run a registry tool (D-25).

There were two doors into `TOOL_REGISTRY`: the chat tool-loop (`routes/chat.py`) and
the tool-panel endpoint (`routes/tools.py`). Story 4.5 made them share the *gate*
(`ai/tool_access.is_tool_authorized`) but everything around the gate was still written
twice: looking the tool up, deciding whether writes are allowed here, resolving the
caller's branch scope, working out whether the function takes `scope`, calling it, and
turning a failure into something safe to show. Two copies that agree today is exactly
how the double-envelope defect survived the R4 hardening epic — nobody greps for the
second caller, because it is thought of as "the tools API" rather than as a caller.

This module is that end state: `invoke_tool(name, params, user, scope) -> envelope`.
Both doors call it and neither keeps its own copy of any step.

**What this module does NOT do, deliberately.**

- It does not catch exceptions raised by the tool. The confirm/executor path
  (`routes/chat.py` `_make_runner`) runs tools inside a MongoDB transaction and needs
  the exception to reach the executor so the write rolls back. Swallowing it here
  would silently turn a failed write into a successful-looking turn. Each door still
  owns how it *reports* a failure; `safe_failure()` below gives them one shape for it.
- It does not re-wrap the tool's result. Every tool already returns the one envelope
  (`_env` / `_ok`: `{success, data, meta, message, denied}`). Adding a second wrapper
  here is the exact Story 4.1 defect that showed eleven screens as zeros.
- It does not decide *policy*. Whether writes are permitted at a door is the door's
  decision, passed in as `require_read_only`; the gate itself stays in `tool_access`.
"""

from __future__ import annotations

import inspect
import logging
import uuid
from typing import Any, Callable, Dict, Optional

from ai.scope_resolver import resolve_scope
from ai.tool_access import is_read_only_tool, is_tool_authorized
from ai.tool_functions_v2 import TOOL_REGISTRY

logger = logging.getLogger(__name__)

# Why a tool could not be run. Kept as plain strings so a caller can branch on them
# without importing an enum, and so they read clearly in a log line.
UNKNOWN = "unknown"            # no such tool in the registry
FORBIDDEN = "forbidden"        # real tool, this caller may not use it
WRITE_BLOCKED = "write_blocked"  # real tool, caller may use it, but not through this door


class ToolNotAvailable(Exception):
    """A tool could not be run, with the reason kept separate from the wording.

    The two doors word the refusal differently on purpose: chat says
    "I don't have a capability called X" so the person is not told a feature exists
    that does not, while the tool-panel endpoint answers 403 for both unknown and
    forbidden so an authenticated caller cannot map the registry by comparing status
    codes. Keeping `reason` structured lets each door keep its own wording without
    keeping its own logic.
    """

    def __init__(self, tool_name: str, reason: str):
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"tool '{tool_name}' unavailable: {reason}")


def resolve_tool(
    name: str,
    user: Dict[str, Any],
    *,
    require_read_only: bool = False,
    authorize: Optional[Callable[[Dict[str, Any], Dict[str, Any]], bool]] = None,
) -> Dict[str, Any]:
    """Look the tool up and apply the gate. Raises `ToolNotAvailable`, never returns None.

    `authorize` exists so `routes/chat.py` can pass its own `_is_tool_authorized`
    alias, which is the symbol its tests import. It defaults to the shared gate; there
    is still only one implementation.
    """
    check = authorize or is_tool_authorized
    tool_def = TOOL_REGISTRY.get(name)
    if not tool_def:
        raise ToolNotAvailable(name, UNKNOWN)
    if not check(user, tool_def):
        raise ToolNotAvailable(name, FORBIDDEN)
    if require_read_only and not is_read_only_tool(tool_def):
        # A write reaching a plain request/response door would skip the two-step
        # confirm, the AI-write kill-switch (F.4), the destructive acknowledgment
        # (F.10) and the write-ahead audit row (P4). Writes go through chat, which
        # has all of them.
        raise ToolNotAvailable(name, WRITE_BLOCKED)
    return tool_def


def tool_accepts_scope(tool_def: Dict[str, Any]) -> bool:
    """True if the tool's function takes `(params, user, scope)` rather than `(params, user)`.

    Every one of the 112 registered tools takes three arguments today, so this is a
    compatibility check rather than a live branch. It is kept because the two-argument
    shape is still what older tools were written with, and because the tool-panel door
    used to call with three arguments unconditionally: the day someone adds a
    two-argument tool, that door would have raised a TypeError and reported it as
    "Tool execution failed", which says nothing about the real cause.
    """
    fn = (tool_def or {}).get("fn")
    if fn is None:
        return False
    try:
        return len(inspect.signature(fn).parameters) >= 3
    except (TypeError, ValueError):
        return False


async def invoke_tool(
    name: str,
    params: Optional[Dict[str, Any]],
    user: Dict[str, Any],
    scope: Any = None,
    *,
    db: Any = None,
    require_read_only: bool = False,
    authorize: Optional[Callable[[Dict[str, Any], Dict[str, Any]], bool]] = None,
    tool_def: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Gate, scope, call, return the tool's own envelope.

    `scope=None` with a `db` resolves the caller's scope here. Chat resolves scope once
    per turn and passes it in; the tool-panel door has no turn, so it lets this resolve.
    Passing neither leaves `scope=None`, which is how a branch-bound caller used to read
    every branch's figures, so it is only ever right for a tool that takes two arguments.

    Pass `tool_def` when the caller has already resolved and gated it (the confirm
    executor does, because it gates before opening the transaction) to skip a second
    lookup. The gate still runs unless the def is passed.
    """
    if tool_def is None:
        tool_def = resolve_tool(
            name, user, require_read_only=require_read_only, authorize=authorize
        )

    if scope is None and db is not None:
        scope = await resolve_scope(user, db)

    if tool_accepts_scope(tool_def):
        return await tool_def["fn"](params or {}, user, scope)
    return await tool_def["fn"](params or {}, user)


def safe_failure(name: str, exc: BaseException) -> Dict[str, Any]:
    """Log the real failure, return something safe to show, and tie the two together.

    Error opacity (Part 2, patch P3): the caller never sees `str(exc)`, which can carry
    the database address, collection names or stack-frame paths. The correlation id is
    the only thing that leaves the server, and it is in the log line too, so a support
    question quoting it can be traced to the exact failure.
    """
    correlation_id = str(uuid.uuid4())
    logger.exception("Tool execution error (%s) [%s]", name, correlation_id)
    return {"error": "data_unavailable", "correlation_id": correlation_id}
