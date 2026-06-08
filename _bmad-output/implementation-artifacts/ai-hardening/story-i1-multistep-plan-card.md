# Story I.1 — Multi-step plan confirmation card

**Epic:** I — Frontend — multi-step plan card & status messaging
**Date:** 2026-06-08

## Story
As an Owner/Principal, I want one card that lists every step of the proposed plan with a single Confirm/Cancel, so that I approve a whole compound job in one glance (UX-DR1).

## Backend contract (from Epic E, `_build_plan_confirm_event` in `backend/routes/chat.py`)
A plan `confirm_action` SSE event carries:
```json
{
  "type": "confirm_action",
  "action_id": "<token>", "token": "<token>", "tool": "plan",
  "is_plan": true,
  "steps": [
    {"idx": 0, "tool": "...", "kind": "write", "destructive": false, "display": "human text"},
    ...
  ],
  "display": "I'll run these steps in order — confirm to proceed:",
  "expires_in_seconds": 300,
  "buttons": [{"label":"Confirm","action":"confirm"},{"label":"Cancel","action":"cancel"}]
}
```
A legacy single-action event has no `is_plan`/`steps` and keeps `params`/`display`.

## Acceptance Criteria
- **Given** chat.py emits a `confirm_action` event carrying an ordered plan, **When** `ConfirmActionCard.js` renders it, **Then** all N steps display in order, scannable, under one Confirm and one Cancel.
- **And** double-submit is guarded (existing Part 8 `submittingRef` pattern).
- **And** Cancel issues no write and reports cancellation.

## Implementation
- `ConfirmActionCard.js`: when `action.is_plan && Array.isArray(action.steps)`, render an ordered `<ol>` of `StepRow` (1-based index, step.display, destructive badge) instead of the single-action `ActionDetails`. One Confirm + one Cancel drive the same `handleClick` → single `/confirm` POST with the plan token. Confirmed/cancelled/error outcome states reuse the existing single-action rendering, listing the steps in the completed view too.
- Double-submit guard (`submittingRef`) is shared by both paths — unchanged.
- Cancel posts `decision:"cancel"`; backend returns `{cancelled:true}` and writes nothing.

## Tests (`ConfirmActionCard.test.js`)
- renders all plan steps in order under one confirm/cancel
- destructive step shows a destructive marker
- rapid confirm clicks on a plan card issue exactly one request (double-submit guard)
- cancel on a plan card posts decision=cancel and reports cancellation, never confirm
