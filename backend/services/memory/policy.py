"""R10.5 — the single MEMORY_ROLES policy switch (mirrors `ai_action_policy.LOCKDOWN_ENABLED`).

Phase-1 self-learning is **Owner + Principal ONLY** (Story F.11 / FR43). Widening
memory/skills to other staff roles is a one-line, greppable **CONFIG** change here —
never an engine change (identical spirit to the action-lockdown single switch).

Two tiers, deliberately separated so widening is safe and staged (R10.5 AC1/AC2):

- **Recall** (`can_recall_memories`) — who gets learned notes/routines *read back* into
  their turns (read-only; no new data captured).
- **Capture** (`can_capture_memories`) — who the assistant auto-*learns from* (auto-save,
  skill proposal, inline remember/forget). A newly recall-widened role is **recall-only**
  until a SEPARATE explicit decision also adds it to capture (AC2). Capture ⊆ Recall is a
  hard invariant enforced below and by the parity guard.

Default: both extra-role sets are EMPTY, so the effective subject stays Owner/Principal
and widening is OFF. Roles are addressed by a token: a plain role (`"teacher"`) or, for
admin sub-roles, `"admin:<sub_category>"` (e.g. `"admin:accountant"`).
"""

from __future__ import annotations

from typing import Any, Dict, Set

from services.ai_action_policy import is_owner_or_principal

# ── The switch (edit to widen; recall FIRST, capture is a separate second decision) ──
# Extra roles granted memory RECALL beyond Owner/Principal. Empty ⇒ widening OFF.
MEMORY_RECALL_EXTRA_ROLES: Set[str] = set()
# Extra roles granted memory CAPTURE (auto-learning). MUST be a subset of recall (AC2).
MEMORY_CAPTURE_EXTRA_ROLES: Set[str] = set()


def role_token(user: Dict[str, Any]) -> str:
    """Stable identity for the policy sets: `admin:<sub>` for admins, else the role."""
    user = user or {}
    role = user.get("role") or ""
    if role == "admin":
        return f"admin:{user.get('sub_category') or ''}"
    return role


def can_recall_memories(user: Dict[str, Any]) -> bool:
    """True iff `user` may have learned memories/skills recalled into their turns."""
    if is_owner_or_principal(user or {}):
        return True
    return role_token(user) in MEMORY_RECALL_EXTRA_ROLES


def can_capture_memories(user: Dict[str, Any]) -> bool:
    """True iff the assistant may auto-learn from `user` (save/propose/inline edit).

    AC2 invariant: a role can capture ONLY if it is BOTH recall-widened AND explicitly
    added to the capture set — recall widening alone never enables capture.
    """
    if is_owner_or_principal(user or {}):
        return True
    token = role_token(user)
    return token in MEMORY_CAPTURE_EXTRA_ROLES and token in MEMORY_RECALL_EXTRA_ROLES
