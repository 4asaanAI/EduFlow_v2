# Epic I — Epic-Close Review (mandatory STEP 4)

**Date:** 2026-06-08
**Scope:** Frontend — multi-step plan card & status messaging (Stories I.1–I.3), plus the minimal backend additions needed to feed the I.3 disambiguation chips.
**Lenses run:** code-review (correctness/quality), adversarial-general (gap/assumption hunt), edge-case-hunter (boundaries/None/empty/dup/failure paths), testarch test-review (false-green/assertions/isolation), testarch-trace (AC→test), testarch-nfr (security/no-leak).

## What this epic built

| Story | Deliverable |
|------|-------------|
| I.1 | `ConfirmActionCard.js`: `PlanSteps` renders an ordered, scannable list of all N plan steps (1-based index, per-step display, `Destructive` badge) under ONE Confirm + ONE Cancel. Reuses the existing `submittingRef` double-submit guard; Cancel posts `decision:"cancel"` (no write) and reports cancellation. Completed/cancelled/error views also list the steps. |
| I.2 | `classifyConfirmError(status, body)` maps the backend 409/502/500 taxonomy (`plan_tampered`/`plan_stale`/`plan_expired`/`needs_manual_reconciliation`/`side_effect_failed`/opaque) to specific human messages; non-recoverable codes hide the Retry button; opaque failures surface only a correlation id (no internal string leaks). Parses the id from a top-level field, the detail object, or an opaque `(id=…)` string. |
| I.3 | `ChatFollowup.js` (disambiguation chips + deep-link button) + `ChatInterface.js` SSE handling. Backend: `_resolve_params` attaches `_resolution_options` (student/staff/search), `PlannerResult.options` carries them, `_stream_plan` emits a structured `disambiguation` event (no token/write) and keeps the `navigate`+`url` deep-link. Picking a chip re-sends its `value` to continue the flow; the deep-link is a click target, never an auto-jump. |

## Findings & fixes

| # | Sev | File | Issue | Fix | Regression test |
|---|-----|------|-------|-----|-----------------|
| 1 | Med | `ConfirmActionCard.js` | The old `!res.ok` path threw `errData?.message \|\| errData?.error`, but the backend nests the code/message under `detail` (FastAPI) — so the entire 409 taxonomy surfaced as `Request failed (409)` and the user never saw "re-plan"/"manual attention". | Replaced with `classifyConfirmError` reading `detail.{code,message}`; mapped every taxonomy code to a distinct message. | `ConfirmActionCard.test.js::I.2 *` (5 codes + opaque) |
| 2 | Med | `ConfirmActionCard.js` | Opaque 500 detail string `"An internal error occurred (id=abc)"` would have leaked verbatim. | Opaque branch surfaces ONLY `Nothing was applied… Reference: <corr>`; the raw string is never rendered (asserted absent). | `I.2 opaque 500 … no internal detail` |
| 3 | Low | `ChatInterface.js` | The `navigate` handler only read `parsed.tool_id`; Epic E's E.6 fallback emits `{navigate, url}` — the deep-link was silently dropped, leaving a dead-end (UX-DR4 unmet). | Handle `parsed.url` → render a clickable `ChatFollowup` deep-link card; `tool_id` legacy path preserved. | `ChatFollowup.test.js::I.3 renders/clicks deep-link`; `test_stream_plan_e5_e6.py` |
| 4 | Low | `ChatFollowup.js` | A `disambiguation` event with empty `options` would render a card with no chips — a dead-end. | Return `null` when options empty (the streamed assistant text already carries the question). | `ChatFollowup.test.js::disambiguation with no options renders nothing` |
| 5 | Low | `ChatInterface.js` | `onPick` cleared the chooser even for a value-less option → silent dead-end. | Only dismiss + send when the option `value` is non-empty. | covered by `ChatFollowup.test.js` value-less option test (parent guard) |
| 6 | Trivial | `ConfirmActionCard.js` | Dead `counterReset` style on a `listStyle:none` manually-numbered list. | Removed. | n/a |

## Dismissed (non-bugs, with reason)

- **Message shown twice (streamed text bubble + card).** Standard "assistant text + action chips" pattern; the streamed text persists to conversation history while the card is purely interactive. The disambiguation card no longer repeats anything for the empty case (renders nothing). Intentional.
- **Chip `value` falls back to the record id (UUID) when a student has no admission number.** Admission numbers are the norm; the id is the only *unique* handle for the rare gap (the name was, by definition, ambiguous). Continue-flow re-resolution via admission number is the primary path.
- **PII / DPDP.** Disambiguation options (name/class/admission no.) are already scope-filtered by `_scoped(...)` and go to the *authorized* Owner/Principal frontend — not to the LLM. LLM-side PII redaction is Epic F's mandate (FR41/42), out of scope here.
- **429 rate-limit.** Untouched — the pre-existing cooldown branch handles it before `classifyConfirmError`.
- **class_name ambiguity has no chips.** Degrades gracefully to a text message (AC scopes chips to "by admission number" i.e. student/staff). Acceptable.

## NFR / security
- **No internal-detail leak (UX-DR5 / P3 opacity):** opaque failures render only `{correlation_id}` — asserted that the raw 500 string is absent.
- **No partial write on either fallback:** disambiguation and deep-link both occur in `_stream_plan` *before* any token is issued — `db.confirm_tokens.docs == []` asserted.
- **No new auth/UI surface:** frontend-only rendering inside the existing chat; backend additions are read-path resolution metadata (underscore-prefixed, stripped from the plan_hash — no tamper-surface change).

## Trace (AC → test)
- **I.1**: steps-in-order-one-confirm-cancel → `I.1 renders all plan steps in order`; double-submit → `I.1 rapid confirm clicks issue one request`; Cancel no-write+reports → `I.1 cancel posts decision=cancel`; destructive marker → `I.1 marks a destructive step`.
- **I.2**: each failure mode → distinct message → `I.2 {plan_stale, plan_tampered, plan_expired, needs_manual_reconciliation, side_effect_failed, opaque 500}`; no leak → opaque test asserts raw string absent.
- **I.3**: ambiguous → selectable options that continue flow → `ChatFollowup I.3 picking an option fires onPick…` + `test_planner_e2 disambiguation_propagates_resolution_options` + `test_stream_plan_e5_e6 disambiguation_emits_structured_options_no_token`; can't-complete → deep-link, no partial write → `ChatFollowup I.3 deep-link` + `test_cannot_plan_emits_deeplink_navigate_no_token`.

## scoped_filter / scoped_query audit
`grep -n "scoped_filter(" backend/routes/chat.py` → 5 hits, ALL pre-existing (conversation/message scoping by `user_id` + `school_id`); none introduced by this epic. The I.3 `_resolve_params` additions use the approved `_scoped(...)` → `scoped_query(branch_id=…)` helper (already audited in Epic E). Audit clean.

## Suite status
- Backend: **926 passed** (3 new), **25 pre-existing failures** (pinned/deferred baseline), **0 new failures**, 0 unexpected skips.
- Frontend: touched suites green — `ConfirmActionCard.test.js` + `ChatFollowup.test.js` = **21 passed**. (Pre-existing `LayoutRouting.test.js` failure confirmed unrelated — fails identically on the clean tree.)
