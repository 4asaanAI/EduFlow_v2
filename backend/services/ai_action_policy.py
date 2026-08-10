"""Central Flo authorization overlay for privileged school profiles.

The registry remains the source of truth for ordinary roles. Four named authority
profiles have broader, domain-based access: owner and principal get the complete
school-management surface, accountant gets finance plus the lookups finance needs,
and management gets every non-finance surface. Leadership notes and audit history
remain owner/principal-only. Other staff keep the former action lockdown.
"""

from __future__ import annotations

from typing import Any, Dict

# Kept for backwards compatibility and as the single guard for roles outside the
# four reviewed profiles. Teachers and narrower admins do not silently gain writes.
LOCKDOWN_ENABLED = True


def is_action_tool(tool_def: Dict[str, Any]) -> bool:
    """True iff this registry entry is a write/action tool (vs a read tool).

    Mirrors `WRITE_TOOL_NAMES` derivation in tool_functions_v2.py so the lockdown
    and the confirm-flow agree on exactly which tools are 'actions'.
    """
    if not tool_def:
        return False
    return bool(
        tool_def.get("requires_confirmation")
        or tool_def.get("dispatch_type") == "write"
    )


def is_owner_or_principal(user: Dict[str, Any]) -> bool:
    """Profiles with full Flo school-management authority."""
    role = (user or {}).get("role")
    if role == "owner":
        return True
    if role == "admin" and (user or {}).get("sub_category") == "principal":
        return True
    return False


def privileged_profile(user: Dict[str, Any]) -> str:
    role = (user or {}).get("role")
    sub_category = (user or {}).get("sub_category")
    if role == "owner":
        return "leadership"
    if role == "admin" and sub_category == "principal":
        return "leadership"
    if role == "admin" and sub_category == "accountant":
        return "finance"
    if role == "admin" and sub_category == "management":
        return "non_finance"
    return ""


def profile_authorization_decision(
    user: Dict[str, Any], tool_def: Dict[str, Any]
) -> "bool | None":
    """Return an authoritative decision for a reviewed profile, else ``None``.

    Profile expansion applies only to school-management tools already assigned to
    owner/admin somewhere in the registry. It never grants student/guardian self tools.
    """
    profile = privileged_profile(user)
    if not profile:
        return None
    # Domain expansion is registry metadata. Synthetic definitions used by unit
    # tests and callers outside TOOL_REGISTRY retain ordinary role semantics.
    if "access_domain" not in (tool_def or {}):
        return None
    roles = set((tool_def or {}).get("roles") or ())
    if not roles.intersection({"owner", "admin"}):
        return False
    domain = (tool_def or {}).get("access_domain")
    # Leadership (the school's owner and the principal) hold the complete
    # school-management surface by design, pinned by test_epic_k_crud_guardrails and
    # test_owner_part3_qa. The registry's `roles` list is not narrowed for them.
    if profile == "leadership":
        return True
    # R2-3: for everyone below leadership, honour the registry's own `roles` list.
    # This decision short-circuits the ordinary role check in `ai/tool_access.py`, so
    # asking only whether `roles` *intersects* {owner, admin} let a tool marked
    # roles=["owner"] through, after which the domain check handed it to whichever
    # profile matched. That is how the management head reached year_end_transition
    # (which moves every student up a class), the branch CRUD and
    # update_school_settings, and how the accountant head reached the legal-entity
    # CRUD. Owner-only stays owner-only whatever the access_domain says.
    #
    # `sub_categories` is deliberately still NOT honoured here: it is the narrow
    # legacy tagging (mostly ["principal"]) that these domain profiles exist to widen,
    # and enforcing it would strip the management head of the attendance and academic
    # tools he is supposed to have. R2-1 replaces both mechanisms with one written
    # grant table, and that is where the sub_category question is settled properly.
    if (user or {}).get("role") not in roles:
        return False
    # R2-5: the matrix may name individual tools, in both directions. The four domains
    # cannot express "the accountant head yes, the management head no" — both would
    # have to be called finance, and a school bus route is not money. A denial wins
    # over a grant, always, because the safe answer to a contradiction is no.
    from services.profile_matrix import PROFILE_MATRIX, profile_of

    matrix_row = PROFILE_MATRIX.get(profile_of(user)) or {}
    tool_name = (tool_def or {}).get("tool_name")
    if tool_name:
        if tool_name in (matrix_row.get("denied_tools") or ()):
            return False
        if tool_name in (matrix_row.get("extra_tools") or ()):
            return True
    if profile == "finance":
        return domain in {"finance", "shared"}
    return domain in {"non_finance", "shared"}


def is_action_authorized_phase1(user: Dict[str, Any], tool_def: Dict[str, Any]) -> bool:
    """Retained action gate for roles not covered by the profile matrix."""
    if not LOCKDOWN_ENABLED:
        return True
    if not is_action_tool(tool_def):
        return True
    return bool(privileged_profile(user))
