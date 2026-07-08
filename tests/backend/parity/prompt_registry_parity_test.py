"""R3.4 (audit XM8) — the prompt ↔ registry parity gate.

The LLM only ever sees the tool catalogue embedded in its system prompt
(`ai/prompts.py:TOOLS_BY_ROLE`). Dispatch/authorization is driven by the separate
`ai/tool_functions_v2.py:TOOL_REGISTRY`. When the two drift, the model is taught a
tool that doesn't exist (H2), isn't authorized for its role (C4), or has the wrong
required params (H1/H3/L4) — every such attempt fails at runtime. This gate makes
that drift a merge-blocking CI failure.

Assertions (architecture §4), for EVERY (role, sub_category) prompt variant:
 1. Every advertised tool name exists in TOOL_REGISTRY.
 2. The advertising role/sub_category is authorized for it by the registry.
 3. Every advertised REQUIRED param is satisfiable against the registry (directly
    or via a known name→id resolution alias).
 4. Coverage: every registry tool authorized for some variant is advertised to one
    of them, unless explicitly allow-listed as intentionally unadvertised; and the
    "must advertise everywhere" tools appear for every authorized variant.
 5. Prompt sub_category keys are a subset of the canonical set in middleware/auth.py.

Note on authorization: this gate checks REGISTRY-level authorization (role +
sub_category) only. The Phase-1 action lockdown (`ai_action_policy`) is an
orthogonal, temporary policy overlay that restricts *execution* of write tools to
Owner/Principal — it does not change which tools *exist* for a role, so the prompt
legitimately advertises the eventual (Phase-2) capability and the gate must not
fold the lockdown in.
"""

from __future__ import annotations

from ai.prompts import TOOLS_BY_ROLE
from ai.tool_functions_v2 import TOOL_REGISTRY
from middleware.auth import VALID_SUB_CATEGORIES

# All assertions here are pure/synchronous — no asyncio marker needed.


# Known name→id resolution aliases applied by chat._resolve_params before dispatch.
# A prompt may advertise the friendly name (class_name) while the registry/impl
# consumes the resolved id (class_id) — that is correct, not drift.
RESOLUTION_ALIASES = {
    "class_name": "class_id",
    "student_name": "student_id",
    "search_term": "student_id",
    "staff_name": "staff_id",
    "house_name": "house_id",
    "days": "start_date",
}

# Registry tools deliberately NOT surfaced in any AI prompt (panel-driven CRUD /
# ops actions). These are the architecture's "explicitly allow-listed as
# unadvertised". A NEW authorized-but-unadvertised tool that isn't added here
# fails assertion 4a — forcing a conscious decision.
UNADVERTISED_OK = frozenset({
    "add_transport_vehicle", "assign_query_ticket", "checkout_visitor",
    "correct_fee_transaction", "create_asset", "create_certificate",
    "create_query_ticket", "create_transport_route", "decide_announcement",
    "decide_certificate", "delete_announcement", "delete_asset", "delete_expense",
    "delete_fee_transaction", "delete_query_ticket", "delete_transport_route",
    "delete_visitor", "get_fee_sync_status", "log_visitor", "mark_staff_attendance",
    "reopen_query_ticket", "resolve_query_ticket", "trigger_fee_sync",
    "update_asset", "update_expense", "update_transport_route",
})

# Tools that MUST be advertised to every variant authorized for them (closes L5:
# recall_history was authorized for principals but never advertised to them).
MUST_ADVERTISE_EVERYWHERE = frozenset({"recall_history"})


def _registry_authorized(role: str, sub_category, tool_def: dict) -> bool:
    """Registry-level auth: role in roles AND (no sub restriction, or non-admin,
    or matching admin sub_category). Mirrors _is_tool_authorized minus lockdown."""
    if role not in tool_def.get("roles", []):
        return False
    subs = tool_def.get("sub_categories")
    if subs is not None and role == "admin":
        if sub_category not in subs:
            return False
    return True


def _advertised_params(tool: dict) -> dict:
    return tool.get("params_schema") or {}


def _registry_params(name: str) -> set:
    return set((TOOL_REGISTRY.get(name, {}).get("params_schema") or {}).keys())


def test_assertion1_every_advertised_tool_exists():
    missing = []
    for (role, sub), tools in TOOLS_BY_ROLE.items():
        for tool in tools:
            if tool["name"] not in TOOL_REGISTRY:
                missing.append((role, sub, tool["name"]))
    assert not missing, f"Advertised tools absent from TOOL_REGISTRY (dead tool calls): {missing}"


def test_assertion2_advertising_role_is_authorized():
    unauthorized = []
    for (role, sub), tools in TOOLS_BY_ROLE.items():
        for tool in tools:
            td = TOOL_REGISTRY.get(tool["name"])
            if td and not _registry_authorized(role, sub, td):
                unauthorized.append((role, sub, tool["name"]))
    assert not unauthorized, (
        "Prompt advertises tools the registry does NOT authorize for that "
        f"role/sub_category (guaranteed 403s): {unauthorized}"
    )


def test_assertion3_required_params_are_satisfiable():
    bad = []
    for (role, sub), tools in TOOLS_BY_ROLE.items():
        for tool in tools:
            name = tool["name"]
            if name not in TOOL_REGISTRY:
                continue
            reg_params = _registry_params(name)
            for pname, desc in _advertised_params(tool).items():
                if not str(desc).strip().lower().startswith("required"):
                    continue
                alias = RESOLUTION_ALIASES.get(pname)
                if pname in reg_params or (alias and alias in reg_params):
                    continue
                bad.append((role, sub, name, pname, sorted(reg_params)))
    assert not bad, (
        "Prompt marks a REQUIRED param the implementation/registry does not accept "
        f"(name mismatch → the call breaks): {bad}"
    )


def test_assertion4a_every_authorized_tool_is_advertised_or_allowlisted():
    variants = list(TOOLS_BY_ROLE.keys())
    advertised = {}
    for (role, sub), tools in TOOLS_BY_ROLE.items():
        for tool in tools:
            advertised.setdefault(tool["name"], set()).add((role, sub))
    dead_in_prompt = []
    for name, td in TOOL_REGISTRY.items():
        if name in UNADVERTISED_OK:
            continue
        auth_variants = {v for v in variants if _registry_authorized(v[0], v[1], td)}
        if auth_variants and not (advertised.get(name, set()) & auth_variants):
            dead_in_prompt.append(name)
    assert not dead_in_prompt, (
        "These registry tools are authorized for a role but advertised in NO prompt "
        "(users can never reach them via the assistant). Advertise them, or add to "
        f"UNADVERTISED_OK if panel-only: {sorted(dead_in_prompt)}"
    )


def test_assertion4b_must_advertise_everywhere():
    variants = list(TOOLS_BY_ROLE.keys())
    advertised = {}
    for (role, sub), tools in TOOLS_BY_ROLE.items():
        for tool in tools:
            advertised.setdefault(tool["name"], set()).add((role, sub))
    gaps = []
    for name in MUST_ADVERTISE_EVERYWHERE:
        td = TOOL_REGISTRY.get(name)
        assert td is not None, f"{name} in MUST_ADVERTISE_EVERYWHERE but not in registry"
        auth = {v for v in variants if _registry_authorized(v[0], v[1], td)}
        missing = auth - advertised.get(name, set())
        if missing:
            gaps.append((name, sorted(missing)))
    assert not gaps, f"Tools authorized but not advertised to every authorized variant: {gaps}"


def test_assertion5_prompt_sub_categories_are_canonical():
    unknown = []
    for (role, sub) in TOOLS_BY_ROLE.keys():
        if sub is None:
            continue
        # A role name reused as its own "sub" sentinel (owner/owner, student/student)
        # is allowed; otherwise the sub must be canonical.
        if sub == role:
            continue
        if sub not in VALID_SUB_CATEGORIES:
            unknown.append((role, sub))
    assert not unknown, (
        "Prompt tool-list keys use non-canonical sub_categories (would silently route "
        f"to a fallback list — audit C4). Fix the key or VALID_SUB_CATEGORIES: {unknown}"
    )


def test_accountant_gets_accounts_not_principal_tools():
    """C4 regression: accountant must resolve to the accounts tool list, never fall
    through to principal (which would over-expose leave/attendance)."""
    from ai.prompts import _resolve_tools
    tools = {t["name"] for t in _resolve_tools("admin", "accountant")}
    assert "record_fee_payment" in tools
    assert "approve_leave" not in tools  # principal-only — must not leak
    assert "mark_attendance" not in tools
