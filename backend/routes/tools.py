"""Direct tool execution endpoint - the tool-panel (non-chat) door into TOOL_REGISTRY.

UI Sweep Epic 4 rewrote this file. Two defects lived here, both invisible from the
outside:

1. **Story 4.1 - the double envelope.** Every tool returns `_env()`
   (`{success, data, meta, message, denied}`) since the R4 epic made that the one
   tool-result envelope. This endpoint then wrapped it again in
   `{"success": True, "data": <envelope>}`, so every tool screen read `r.data.summary`
   - which was the *envelope*, not the payload - got `undefined`, and fell through to
   its `|| 0` default. Eleven screens showed zeros. The owner reported it as "the
   Board Report shows zeros"; it was never about the Board Report.

   The endpoint now returns the tool's own envelope unchanged. There is exactly one.

2. **Story 4.5 - three gaps versus the chat door.** This file had not changed since
   Part 1.5 and never learned what the assistant learned afterwards. It gated on
   `user["role"]` alone; it could invoke write tools with no confirm token,
   kill-switch, lockdown or audit; and it passed no `scope`, so a branch-bound caller
   read every branch. All three are closed below. Approved by the owner before
   implementation, because all three change what a person is allowed to do.

**D-25 (2026-08-04) finished what Story 4.5 started.** Every step of running a tool
now lives in `ai/tool_invoker.py`, and this file keeps only what is genuinely local to
this door: that it serves reads, and that an unknown tool and a forbidden one must look
identical from outside. It no longer holds its own copy of the lookup, the gate, the
scope resolution or the calling convention.

One real difference the unification removed: this door called every tool with three
arguments unconditionally, while chat checked the function's signature first. All 112
registered tools take three today, so nothing was broken - but the first two-argument
tool anyone added would have failed here as a generic "Tool execution failed" with a
TypeError buried in the log, and passed fine through chat.
"""

from fastapi import APIRouter, HTTPException, Request

from ai.tool_invoker import ToolNotAvailable, invoke_tool, safe_failure
from database import get_db
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/tools", tags=["tools"])


def get_user(req: Request):
    return get_current_user(req)


@router.post("/{tool_id}/execute")
async def execute_tool(tool_id: str, request: Request):
    user = get_user(request)
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    params = body.get("params", {})

    try:
        # `require_read_only=True` is this door's own policy, not a global rule: writes
        # go through chat because that is where the confirm token, the kill-switch, the
        # destructive acknowledgment and the write-ahead audit row live.
        # `scope=None` + `db` means the invoker resolves the caller's branch scope, so a
        # branch-bound admin cannot read another branch's figures.
        return await invoke_tool(
            tool_id, params, user, db=get_db(), require_read_only=True
        )
    except ToolNotAvailable:
        # Unknown, forbidden and write-through-the-wrong-door all answer 403 with the
        # same wording on purpose, so an authenticated caller cannot map the registry by
        # comparing 404s against 403s. The reason is on the exception for the log, not
        # for the response.
        raise HTTPException(403, "Forbidden")
    except HTTPException:
        raise
    except Exception as exc:
        # Error opacity (P3): the caller never sees str(e). The correlation id is logged
        # alongside the real traceback by the shared helper.
        failure = safe_failure(tool_id, exc)
        raise HTTPException(
            500,
            f"Tool execution failed (reference {failure['correlation_id']})",
        )
