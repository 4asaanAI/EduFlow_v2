"""The single authorization gate for the tool registry (UI Sweep, Epic 4 / Story 4.5).

There are two doors into `TOOL_REGISTRY`: the chat tool-loop (`routes/chat.py`) and
the tool-panel endpoint (`routes/tools.py`). They grew separately, and the second one
never learned what the first one knows — it gated on `user["role"]` alone, so the 49
registry entries carrying `sub_categories` and the Phase-1 action lockdown were both
invisible to it.

Keeping two gates "in sync by discipline" is what produced that drift, so the gate now
lives here and both doors import it. `routes/chat.py` keeps the name
`_is_tool_authorized` bound to `is_tool_authorized` so existing call sites and tests
that patch that symbol are unaffected.
"""

from __future__ import annotations

from typing import Any, Dict

from services.ai_action_policy import is_action_authorized_phase1, is_action_tool


def is_tool_authorized(user: Dict[str, Any], tool_def: Dict[str, Any]) -> bool:
    """Check role + sub_category + Phase-1 lockdown against a TOOL_REGISTRY entry.

    sub_categories: None means no sub_category restriction (any admin).
    sub_categories: [...] means admin must have a matching sub_category;
    non-admin roles that appear in roles[] are never blocked by sub_categories.
    """
    if (user or {}).get("role") not in (tool_def or {}).get("roles", []):
        return False
    sub_categories = (tool_def or {}).get("sub_categories")
    if sub_categories is not None and (user or {}).get("role") == "admin":
        if (user or {}).get("sub_category") not in sub_categories:
            return False
    # F.11/FR43: Phase-1 lockdown — AI write/action tools are Owner+Principal only
    # (pilot scope), even where the registry roles permit broader staff. Read
    # tools (incl. all student tools) are unaffected. Single switch lives in
    # services/ai_action_policy.py; Phase 2 (Epic H) widens it with no engine change.
    if not is_action_authorized_phase1(user, tool_def):
        return False
    return True


def is_read_only_tool(tool_def: Dict[str, Any]) -> bool:
    """True iff this tool may be invoked through a plain request/response endpoint.

    A write tool reaching the tool-panel endpoint would bypass every protection the
    confirm flow provides: the two-step confirm token, the AI-write kill-switch
    (F.4), the Phase-1 lockdown (F.11), the destructive-acknowledgment step (F.10)
    and the write-ahead audit row (P4). So writes go through chat, which has all of
    them, and this endpoint serves reads.

    `is_action_tool` is the same predicate `WRITE_TOOL_NAMES` is derived from, so
    there is one definition of "this tool writes" rather than two that agree today.
    """
    return not is_action_tool(tool_def)
