"""NEW-12 / T8 — which tools are ADVERTISED to the model in chat.

Measured on `main` before this change, an owner's every chat message sent 107 tool
definitions (~21,500 tokens) before the question was even read. Most of that budget
went to structural configuration tools nobody asks Flo about in conversation: adding
a branch, deleting a class, editing a discount type, running the year-end transition.
Those are done deliberately, on a screen, with a form in front of you.

**This file changes what is OFFERED, never what is ALLOWED.** Authorization stays
exactly where it was, in `ai/tool_access.is_tool_authorized`, and is still the only
thing consulted at dispatch. An excluded tool that is named explicitly (the tool
panel, a suggested action, `_build_llm_tools(only={...})`) runs exactly as before.
So this is a cost change, not a permission change, and it cannot widen or narrow
anyone's access.

Exclusions apply to owner and principal only — the two roles whose lists are large
enough for the saving to matter. Every other role is untouched.
"""

from __future__ import annotations

from typing import Any, Dict

from school_identity import default_branch_id

# Structural / configuration tools: set up once (or once a year) on a screen, never
# asked for mid-conversation. Removing them from the chat advertisement is where the
# owner's token bill actually is.
#
# **No delete belongs in here (owner instruction, 2026-08-07).** The trim originally
# swept up every delete alongside the create/update it sat next to, and the effect was
# that the school's owner asked Flo to delete a class and was told "that operation is
# not available to me" — about something it was fully authorised to do. Being told the
# assistant cannot do a thing it can do costs more trust than the tokens were worth.
# Creating and editing structure stays out: those have a form on a screen, and nobody
# was asking Flo for them.
_STRUCTURAL_CONFIG_TOOLS = frozenset({
    # Organisation structure
    "create_branch", "update_branch",
    "update_school_settings", "year_end_transition",
    # Academic structure
    "create_class", "update_class",
    "create_house", "update_house",
    # Fee configuration (recording a payment or a discount is NOT here — that is
    # everyday work and stays available in chat)
    "create_fee_structure", "update_fee_structure",
    "create_discount_type", "update_discount_type",
    # Asset and transport registers
    "create_asset", "update_asset",
    "create_transport_route", "update_transport_route",
    "add_transport_vehicle",
})

EXCLUDE_FOR_ROLE: Dict[str, frozenset] = {
    "owner": _STRUCTURAL_CONFIG_TOOLS,
    "admin:principal": _STRUCTURAL_CONFIG_TOOLS,
}


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
