"""Phase-1 AI action-authorization lockdown (AI Layer Hardening, Story F.11 / FR43).

THE SINGLE SWITCH. During Phase 1 the *entire* AI write/action surface — every
Epic A–C hardened write tool, the CRUD tools (Epics J/K), and any destructive op
(F.10) — is permitted ONLY for **Owner** or **Principal** (`role=admin` AND
`sub_category=principal`), even where the underlying REST route permits broader
roles (e.g. teacher `mark_attendance`, accountant fee config).

This is a deliberate, reversible pilot scope, NOT a permanent RBAC change. Phase 2
(Epic H) widens it to other staff roles **without engine changes** by editing the
single `PHASE_1_ACTION_ROLES` policy below (or flipping `LOCKDOWN_ENABLED`).

Hard invariants:
- Applies to ACTION/WRITE tools only. **Student (and every) read tool is
  unaffected** — students keep their current read-only, content-filtered
  experience and are *permanently* excluded from the write/action expansion.
- Enforced at `_is_tool_authorized` (routes/chat.py) — i.e. BEFORE any confirm
  token is issued, before the rate slot is taken, and per-step for plans. A
  refused action never reaches the executor.
"""

from __future__ import annotations

from typing import Any, Dict

# Flip to False in Phase 2 (Epic H) to lift the pilot lockdown, OR widen the
# role predicate below. Kept as an explicit module constant so the cutover is a
# one-line, greppable, reviewable change.
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
    """The two acceptance-gate profiles for the Phase-1 pilot."""
    role = (user or {}).get("role")
    if role == "owner":
        return True
    if role == "admin" and (user or {}).get("sub_category") == "principal":
        return True
    return False


def is_action_authorized_phase1(user: Dict[str, Any], tool_def: Dict[str, Any]) -> bool:
    """Phase-1 gate: action tools are Owner/Principal-only; reads pass through.

    Returns True when the tool is permitted for `user` under the current phase
    policy. Read tools always return True here (the registry role check still
    applies separately upstream).
    """
    if not LOCKDOWN_ENABLED:
        return True
    if not is_action_tool(tool_def):
        return True
    return is_owner_or_principal(user)
