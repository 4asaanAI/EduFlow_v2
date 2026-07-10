"""Agentic planner (AI Layer Hardening — Epic E, AD1/AD2/P3).

The model *proposes* an ordered plan of EXISTING tools; the server *authorizes,
resolves, and executes*. This module turns one instruction into a resolved,
authorized `steps[]` (the canonical P3 shape) that chat.py binds into a single
plan-confirm token. It is NOT a new tool and it NEVER writes — write steps are
collected and deferred to `plan_executor` after one confirmation.

Determinism (AD10/NFR23): `build_plan` takes the raw model plan via
`request_plan` (a callable). Tests inject a recorded plan fixture; the live
Azure call lives behind that seam, so the planner's logic is unit-tested without
a network call.

Borrowed from Odysseus (clone-from-Odysseus directive): the plan-mode shape and
the server-side `ask_user`/disambiguation pattern — adapted to EduFlow's scoped
`resolve_params` and tool registry rather than cloned wholesale.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

# AD2/FR5: planning/read iterations are bounded by MAX_TOOL_ROUNDS (chat.py);
# plan SIZE is bounded separately so a multi-step job is not starved by the
# read-round cap. Confirmed write execution (the /confirm request) consumes
# neither budget.
MAX_PLAN_STEPS = 8

READ = "read"
WRITE = "write"

# Planner outcome statuses.
PLAN = "plan"  # a resolved, authorized, executable plan
DISAMBIGUATION = "disambiguation"  # a name matched >1 record — ask the user
UNAUTHORIZED = "unauthorized"  # a step is outside the user's role/sub_category
TOO_LONG = "too_long"  # plan exceeds MAX_PLAN_STEPS
CANNOT_PLAN = "cannot_plan"  # the model produced nothing actionable (E.6)


# Tool → (collection, id-param) used to derive a freshness precondition (AD5)
# on each write step. Existence is always checked inside the txn; a monotonic
# version is added by services that maintain one. A tool absent here gets no
# precondition (logged by the executor, not silently swallowed).
_PRECONDITION_TARGETS = {
    "approve_leave": ("leaves", "leave_id"),
    "record_fee_payment": ("students", "student_id"),
    "apply_discount": ("students", "student_id"),
    "mark_attendance": ("classes", "class_id"),
    "correct_attendance": ("students", "student_id"),
    "award_house_points": ("houses", "house_id"),
    "decide_approval_request": ("approval_requests", "request_id"),
    "update_incident_status": ("incidents", "record_id"),
    "assign_followup": ("incidents", "record_id"),
    "add_thread_entry": ("incidents", "record_id"),
    "initiate_substitution": ("staff", "staff_id"),
    "log_contact_event": ("students", "student_id"),
    "confirm_resolution": ("incidents", "record_id"),
}


@dataclass
class PlannerResult:
    status: str
    steps: list = field(default_factory=list)  # canonical resolved P3 step dicts
    message: str = ""
    unauthorized_tool: Optional[str] = None
    unauthorized_step_idx: Optional[int] = None
    deep_link: Optional[str] = None
    # I.3: on a DISAMBIGUATION result, the candidate records the user picks from
    # (each: {"label", "value"}). Empty when resolution produced no candidates.
    options: list = field(default_factory=list)

    @property
    def has_writes(self) -> bool:
        return any(s.get("kind") == WRITE for s in self.steps)


def _derive_precondition(tool: str, params: dict) -> Optional[dict]:
    """Build the AD5 freshness precondition for a write step from its target."""
    target = _PRECONDITION_TARGETS.get(tool)
    if not target:
        return None
    collection, id_param = target
    record_id = params.get(id_param)
    if not record_id:
        return None
    pre = {"collection": collection, "id": record_id}
    # A monotonic version, when the planner observed one, lets the executor
    # detect a lost update rather than mere deletion.
    if params.get("_precondition_version") is not None:
        pre["version"] = params["_precondition_version"]
    return pre


async def build_plan(
    *,
    instruction: str,
    user: dict,
    db,
    scope,
    registry: dict,
    write_tools: set,
    is_authorized: Callable[[dict, dict], bool],
    resolve_params: Callable[..., Awaitable[dict]],
    request_plan: Callable[..., Awaitable[list]],
    deep_link_for: Optional[Callable[[str], Optional[str]]] = None,
) -> PlannerResult:
    """Turn one instruction into a resolved, authorized plan.

    Steps in resolution order:
      1. Get the raw ordered plan from the model (or a recorded fixture).
      2. Bound plan size (MAX_PLAN_STEPS).
      3. Authorize EVERY step up-front — any unauthorized step rejects the
         WHOLE plan with which-step feedback (AD14: never silently truncated).
      4. Resolve entity names server-side; a name matching >1 record returns a
         disambiguation prompt and issues NO token (E.4).
      5. Attach a freshness precondition to each write step (AD5).
    """
    raw_steps = await request_plan(instruction=instruction, user=user, scope=scope)
    if not raw_steps:
        return PlannerResult(
            status=CANNOT_PLAN,
            message="I couldn't turn that into a concrete set of actions.",
        )

    if len(raw_steps) > MAX_PLAN_STEPS:
        return PlannerResult(
            status=TOO_LONG,
            message=(
                f"That needs {len(raw_steps)} steps, but I can only run up to "
                f"{MAX_PLAN_STEPS} in one go. Please split it into smaller requests."
            ),
        )

    # ── 3. Authorize the whole plan before resolving/issuing anything ──
    for idx, raw in enumerate(raw_steps):
        tool = raw.get("tool") or raw.get("action")
        tool_def = registry.get(tool)
        if not tool_def:
            return PlannerResult(
                status=CANNOT_PLAN,
                message=f"I don't have a tool to do step {idx + 1} of that.",
            )
        if not is_authorized(user, tool_def):
            return PlannerResult(
                status=UNAUTHORIZED,
                unauthorized_tool=tool,
                unauthorized_step_idx=idx,
                message=(
                    f"Step {idx + 1} ({tool.replace('_', ' ')}) is outside what "
                    "your role can do, so I can't run this plan."
                ),
                deep_link=deep_link_for(tool) if deep_link_for else None,
            )

    # ── 4 + 5. Resolve, classify, attach preconditions ──
    # XM2: the executor runs ONLY write steps — read steps in a confirmed plan
    # never execute. Advertising them on the confirm card is a false promise, so
    # read steps are dropped from the resolved plan entirely and write steps are
    # re-indexed sequentially (idempotency keys derive from `idx`).
    resolved_steps: list = []
    for raw in raw_steps:
        tool = raw.get("tool") or raw.get("action")
        params = raw.get("params") or {}
        kind = WRITE if tool in write_tools else READ
        if kind != WRITE:
            continue
        resolved = await resolve_params(params, db, scope)
        if resolved.get("_resolution_error"):
            return PlannerResult(
                status=DISAMBIGUATION,
                message=resolved["_resolution_error"],
                options=resolved.get("_resolution_options") or [],
            )
        # Public params only — drop resolution-internal keys (prefixed `_`) so
        # the plan_hash binds exactly what executes and the card shows nothing
        # internal.
        public = {k: v for k, v in resolved.items() if not k.startswith("_")}
        idx = len(resolved_steps)
        step: dict[str, Any] = {"idx": idx, "tool": tool, "kind": kind, "params": public}
        pre = _derive_precondition(tool, resolved)
        if pre is not None:
            step["precondition"] = pre
        else:
            logger.warning(
                "planner: no precondition derivable for write tool %s — "
                "executor will stale-guard on existence only",
                tool,
            )
        resolved_steps.append(step)

    return PlannerResult(status=PLAN, steps=resolved_steps)
