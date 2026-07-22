"""Direct tool execution endpoint — the tool-panel (non-chat) door into TOOL_REGISTRY.

UI Sweep Epic 4 rewrote this file. Two defects lived here, both invisible from the
outside:

1. **Story 4.1 — the double envelope.** Every tool returns `_env()`
   (`{success, data, meta, message, denied}`) since the R4 epic made that the one
   tool-result envelope. This endpoint then wrapped it again in
   `{"success": True, "data": <envelope>}`, so every tool screen read `r.data.summary`
   — which was the *envelope*, not the payload — got `undefined`, and fell through to
   its `|| 0` default. Eleven screens showed zeros. The owner reported it as "the
   Board Report shows zeros"; it was never about the Board Report.

   The endpoint now returns the tool's own envelope unchanged. There is exactly one.

2. **Story 4.5 — three gaps versus the chat door.** This file had not changed since
   Part 1.5 and never learned what the assistant learned afterwards. It gated on
   `user["role"]` alone; it could invoke write tools with no confirm token,
   kill-switch, lockdown or audit; and it passed no `scope`, so a branch-bound caller
   read every branch. All three are closed below. Approved by the owner before
   implementation, because all three change what a person is allowed to do.
"""

import logging

from fastapi import APIRouter, Request, HTTPException

from ai.scope_resolver import resolve_scope
from ai.tool_access import is_tool_authorized, is_read_only_tool
from ai.tool_functions_v2 import TOOL_REGISTRY
from database import get_db
from middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


def get_user(req: Request):
    return get_current_user(req)


@router.post("/{tool_id}/execute")
async def execute_tool(tool_id: str, request: Request):
    user = get_user(request)
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    params = body.get("params", {})

    tool_def = TOOL_REGISTRY.get(tool_id)

    # An unknown tool and a forbidden tool are indistinguishable from outside, so an
    # authenticated caller cannot map the registry by comparing 404s against 403s.
    if not tool_def or not is_tool_authorized(user, tool_def):
        raise HTTPException(403, "Forbidden")

    # Reads only. A write reaching this door would skip the two-step confirm, the
    # AI-write kill-switch (F.4), the destructive acknowledgment (F.10) and the
    # write-ahead audit row (P4) — every protection the confirm flow exists to give.
    # Writes go through chat, which has all of them.
    if not is_read_only_tool(tool_def):
        raise HTTPException(403, "Forbidden")

    # Tool signatures are (params, user, scope). Calling with two arguments left
    # `scope=None`, so `_tenant_query` emitted no branch_id clause and a branch-bound
    # admin or principal read every branch's figures. Owners resolve to branch_id=None
    # and stay cross-branch by design.
    scope = await resolve_scope(user, get_db())

    try:
        return await tool_def["fn"](params, user, scope)
    except HTTPException:
        raise
    except Exception:
        # Error opacity (P3): the caller never sees str(e).
        logger.exception("Tool '%s' execution failed", tool_id)
        raise HTTPException(500, "Tool execution failed")
