# Story I.2 — Status & error messaging (409 taxonomy + reconciliation)

**Epic:** I | **Date:** 2026-06-08

## Story
As an Owner/Principal, I want clear, distinct messages for the failure modes, so I know whether to re-confirm, re-plan, or that something needs manual attention (UX-DR5, UX-DR2).

## Backend contract (Epic D/E)
`POST /confirm` failure bodies (FastAPI HTTPException → `{"detail": ...}`):
- 409 `{detail:{code:"plan_tampered", message}}` — integrity check failed → re-ask.
- 409 `{detail:{code:"plan_stale", message}}` — data changed → re-plan.
- 409 `{detail:{code:"plan_expired", message}}` — token expired while reading → re-ask.
- 409 `{detail:{code:"needs_manual_reconciliation", message}}` — partial-failure, nothing applied → manual.
- 502 `{detail:{code:"side_effect_failed", message}}` — records written, side-effect (e.g. SMS) failed.
- 500 `{detail:"An internal error occurred (id=<corr>)"}` — opaque; only the correlation id is surfaced.
- 429 — rate-limited (handled by the existing pre-I.2 cooldown path, untouched).

## Implementation
`ConfirmActionCard.js` → `classifyConfirmError(httpStatus, body)`:
- Reads `body.detail.code`/`body.detail.message`; extracts a correlation id from a top-level field, the detail object, OR an opaque `(id=…)` detail string.
- Maps each code to a specific human message; non-recoverable codes (`plan_*`, `needs_manual_reconciliation`, `side_effect_failed`) set `retryable:false` (no Retry button — the token is spent); opaque ≥500 and network errors set `retryable:true`.
- No internal detail leaks: the opaque branch surfaces only "Nothing was applied… Reference: <corr>".

## Tests (`ConfirmActionCard.test.js`)
plan_stale · plan_tampered · plan_expired · needs_manual_reconciliation · side_effect_failed(502) · opaque 500 (correlation id shown, raw string hidden, retry offered).
