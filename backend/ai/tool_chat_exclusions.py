"""NEW-12 / T8 — which tools are ADVERTISED to the model in chat.

**Superseded for cost purposes on 2026-08-08.** This file used to also carry a
role-based exclusion list (`EXCLUDE_FOR_ROLE`) that dropped structural/configuration
tools from an owner's or principal's advertised list to save tokens. That approach had
a real cost of its own: a hidden tool is indistinguishable, to the model, from a tool
that does not exist, which is how the school's owner once got told an operation "is not
available to me" about something they were fully authorised to do.

`ai/tool_search.py` now solves the same token problem without that failure mode —
non-core tools are listed by NAME and their schemas fetched on demand, so nothing is
ever invisible and Flo can never deny a capability it has. The exclusion list is gone.

What remains here is the one rule that was never about cost: a *relevance* rule.

**This file changes what is OFFERED, never what is ALLOWED.** Authorization stays
exactly where it was, in `ai/tool_access.is_tool_authorized`, and is still the only
thing consulted at dispatch.
"""

from __future__ import annotations

from typing import Any, Dict

from school_identity import default_branch_id

# Deliberately empty: the cost-motivated trim moved to ai/tool_search.py (2026-08-08).
# Kept as a named, empty mapping rather than deleted so the seam — and the reason it is
# empty — stays visible to the next person tempted to re-add a hide-by-role list.
EXCLUDE_FOR_ROLE: Dict[str, frozenset] = {}


def _role_key(user: Dict[str, Any] | None) -> str:
    u = user or {}
    role = u.get("role")
    if role == "admin":
        return f"admin:{u.get('sub_category')}"
    return role or ""


def is_chat_advertised(user: Dict[str, Any] | None, tool_name: str) -> bool:
    """True if this tool should appear in the chat `tools` list for this caller.

    NOT an authorization check. Never call this at dispatch — `is_tool_authorized`
    is the gate, and it is unchanged.
    """
    caller = user or {}
    # Joya currently has one active branch, so a comparison cannot answer anything.
    # Keep this contextual and outside EXCLUDE_FOR_ROLE: read tools must never be
    # globally trimmed, and this automatically stops applying to a school-level token.
    if (
        tool_name == "get_branch_comparison"
        and caller.get("branch_id") == default_branch_id()
        and _role_key(caller) in {"owner", "admin:principal"}
    ):
        return False
    return tool_name not in EXCLUDE_FOR_ROLE.get(_role_key(caller), frozenset())
