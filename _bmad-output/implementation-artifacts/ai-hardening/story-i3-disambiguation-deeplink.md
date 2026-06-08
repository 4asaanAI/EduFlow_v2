# Story I.3 — Disambiguation prompt & UI deep-link fallback

**Epic:** I | **Date:** 2026-06-08

## Story
As an Owner/Principal, I want to pick between ambiguous matches in chat and get a panel link when the assistant can't proceed, so I'm never stuck (UX-DR3, UX-DR4).

## Backend additions (minimal, to feed the I.3 frontend)
- `chat.py _resolve_params`: on a student/staff/search ambiguity, attach `_resolution_options`
  (≤5 `{label, value}`; `value` = admission number when present, else the record id). Underscore-
  prefixed so it is stripped from the plan/plan_hash (no leak) — consistent with Epic E.
- `ai/planner.py`: `PlannerResult.options` carries the candidates on a `DISAMBIGUATION` result.
- `chat.py _stream_plan`: when status is `DISAMBIGUATION` **and** there are options, emit a structured
  `{type:"disambiguation", message, options}` SSE event (no token, no write, no deep-link). A
  can't-complete/unauthorized/too-long fallback keeps the existing `{type:"navigate", url}` deep-link.

## Frontend
- New `ChatFollowup.js` (rendered inside the existing chat — no new page/surface):
  - `disambiguation`: selectable option chips; picking one fires `onPick(opt)`. Empty-options → renders nothing (the streamed assistant text already carries the question — no dead-end card).
  - `deeplink`: an "Open the … panel" button; `toolFromDeepLink(url)` parses `?tool=` and dispatches the existing `eduflow-navigate` event. The deep-link is shown as a click target — never an automatic jump.
- `ChatInterface.js`: handles the `disambiguation` event and the `navigate`+`url` deep-link; `onPick` re-sends the option `value` into the chat to **continue the flow** (only when the value is non-empty); `navigate.tool_id` legacy behavior preserved.

## "No partial write" guarantee
Both branches occur in `_stream_plan` **before** any confirm token is issued — no write, no token. Verified by `test_stream_plan_e5_e6.py` (`db.confirm_tokens.docs == []`).

## Tests
- Backend: `test_planner_e2.py` (options propagated + default empty); `test_stream_plan_e5_e6.py` (disambiguation event with options, no token; deep-link navigate, no token).
- Frontend: `ChatFollowup.test.js` (`toolFromDeepLink` parsing; option render + onPick continue-flow; empty-options renders nothing; deep-link render + onOpenPanel parses tool).
