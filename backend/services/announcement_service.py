"""Announcement moderation service — the single source of truth for the
announcement approval gate (AI Layer Hardening, AD7 / Epic A, Story A.4).

Both `POST /api/ops/announcements` (REST) and the AI `create_announcement` tool
call `decide_announcement_status(...)`, so the moderation decision is identical
regardless of entrypoint. This removes the gate logic that was duplicated inline
in `tool_create_announcement` (project-context.md previously noted the duplication
existed "due to circular import risk" — this service resolves that).

**Parity decision (case-by-case, canonical = REST, per Story A.4 "exactly as the
route does"):** the REST route exempts owner & principal (EC-9.1 — they ARE the
approvers, so self-moderation is a pointless round-trip; documented behavior). The
old AI tool applied the content gate to *everyone*, so an owner's AI announcement was
needlessly held for approval — divergent from the panel. The AI now honors the same
role exemption. (The 5 `test_announcement_moderation.py` tests assert the pre-EC-9.1
"moderate owner too" policy and remain pinned-failing — they pre-date EC-9.1.)

Services raise domain exceptions, never `HTTPException`.
"""

from __future__ import annotations

from typing import List, Optional

from services.actor_context import ActorContext

# Roles a principal may address (everything except owner). Mirrors the route's
# Story 7-47 / EC-9.1 PRINCIPAL_ALLOWED_AUDIENCES.
PRINCIPAL_ALLOWED_AUDIENCES = {"teacher", "student", "admin", "all", "parent"}


class AnnouncementValidationError(Exception):
    """Audience guard violation (principal targeting owner) → HTTP 422."""


def decide_announcement_status(
    actor_ctx: ActorContext,
    audience_type: Optional[str],
    target_roles: Optional[List[str]],
    *,
    raw_audience_roles: Optional[List[str]] = None,
) -> str:
    """Return ``"active"`` or ``"pending_approval"`` for a new announcement.

    EC-9.1: owner and principal broadcast directly (they are the approvers).
    Story 7-47: for every other role, an announcement addressed to all/class or to
    teachers/students is held for approval.

    Raises ``AnnouncementValidationError`` when a principal targets the owner role.
    """
    role = actor_ctx.role
    if role == "admin" and actor_ctx.sub_category == "principal":
        audience_set = set(raw_audience_roles if raw_audience_roles is not None else (target_roles or []))
        if not audience_set.issubset(PRINCIPAL_ALLOWED_AUDIENCES):
            raise AnnouncementValidationError("Principal cannot target owner role")
        return "active"
    if role == "owner":
        return "active"
    requires_approval = audience_type in ("all", "class") or any(
        r in ("teacher", "student") for r in (target_roles or [])
    )
    return "pending_approval" if requires_approval else "active"
