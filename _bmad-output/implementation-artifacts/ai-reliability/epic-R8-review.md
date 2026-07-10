# Epic R8 — Epic-Close Quality Gate Review

**Date:** 2026-07-10 · **Reviewer:** executing agent (self-review across the 5 lenses)
**Scope:** combined R8 diff — `lib/api.js`, `components/{ChatInterface,InputBar,MessageRenderer}.js`,
`setupTests.js` + 4 frontend test files.

## STEP 4a — Tests
- **Frontend** (`CI=true craco test --watchAll=false`) → **47 passed, 2 failed**. The
  2 failures are `LayoutRouting.test.js`, which **fail on `main` too** (confirmed by
  stashing the R8 diff and re-running: 2 failed on baseline). Pre-existing, unrelated
  to R8 — see §pre-existing. Every other suite green, including the 4 new/updated R8
  suites (11 R8 tests) and the existing `api.test.js`, `MessageRenderer.test.js`,
  `ChatFollowup.test.js`, `ConfirmActionCard.test.js`.
- **Backend** (`pytest tests/backend/`) → **1444 passed, 0 failed, 14 deselected, 0
  skipped**. R8 touched no backend file; re-run confirms no interference from this run
  or the pre-R8 R5–R7 review fixes.

## STEP 4b — Review lenses (applied manually)

| Lens | Finding | Resolution |
|------|---------|------------|
| code-review (correctness) | 401 refresh-retry re-issues the POST; is that a double-write risk? No — a 401 on the *initial* response means auth failed before the handler created a message or debited tokens; the retry is safe. Documented inline. | No change. |
| adversarial | Auto-reconnect could loop forever. `autoRetryRef` caps it at 1 and resets on `done`/manual-retry; only a `stream_network_error` (not `stream_closed_without_done`) is auto-retried. | Accepted; bounded. |
| adversarial | Allowing `style` in the sanitizer to restore styling — does DOMPurify neutralize `url(javascript:…)`? **NO under jsdom** (the R8 test caught a surviving `background:url(javascript:…)`). | **Reversed the approach in-run:** emit bare tags + rely on `.prose-chat` CSS; sanitizer stays strict (strips style/class/handlers). Safer AND passes the existing "strip style" security test. |
| edge-case | If every SSE frame incl. `done` lands in ONE React batch, `streaming` never commits `true`, the streaming-transition flush effect sees no change, and the finalized reply is silently dropped. | **Fixed in-run:** the post-`await` backstop now flushes `pendingFinalMsgRef` directly (dedupe by id). Regression: `ChatInterface.r8` happy-path (synchronous mock exercises exactly this batch). |
| edge-case | `handleRetry` scanning `messages` for the last user turn could hit a stale closure during an auto-retry. | Auto-retry passes `text`/`imageData`/`forceCid` explicitly (no message scan, no stale-`convId` re-create); manual retry (a user click) reads current `messages`. |
| edge-case | Markdown link with a `javascript:`/malformed URL. | `processInline` only emits `<a href>` for a safe protocol (else plain text); DOMPurify `ALLOWED_URI_REGEXP` is the backstop. Test: `…javascript: link is not rendered as an anchor`. |
| testarch-trace | Every R8 AC traced to a test or a rendered assertion (see epic-R8-completed.md). | R8.1 AC1/AC2/AC3, R8.2 AC1/AC2, R8.3 AC1/AC2, R8.4 AC1/AC2/AC3/AC4 covered. |
| testarch-nfr | Auto-reconnect adds ≤1 retry; sanitizer allowlist is O(nodes); no new polling. StrictMode-safety improved (side effects out of updaters). No secret/PII exposure introduced. | Acceptable. |

## STEP 4c — Findings fixed in-run
1. Sanitizer: switched from "allow style" (unsafe under jsdom) to bare-tags + `.prose-chat` CSS + strict sanitizer.
2. Client terminal backstop: direct flush of the pending finalized message (single-batch drop).
3. `executeAction` routed through `apiFetch` (401 refresh on confirm-card actions).

## STEP 4d — Scoped grep audit
N/A for this epic — R8 is frontend-only; no backend tenant queries (`scoped_filter`/
`scoped_query`) were added or touched.

## STEP 4e — Golden eval
R8 changed **no** backend AI file (`prompts.py`, `tool_functions*.py`,
`context_builder.py`, `llm_client.py`, chat tool-loop). The always-on structural +
judge-logic eval tier is therefore unaffected (last recorded: **18 passed**); the
credentialed LLM-judge tier stays deferred (no dev creds — DEFERRED row 21). No
prompt/tool-schema drift → parity gate untouched.

## Pre-existing (not R8; deferred like the pinned baseline failures)
- `LayoutRouting.test.js` (2 tests) throws an opaque `AggregateError` on `render(<Harness>)`.
  Confirmed failing on `main` (pre-R8). The `scrollIntoView` polyfill added this run did
  NOT resolve it, so the cause is a separate jsdom/React-19 gap in that specific harness.
  Logged in DEFERRED-AND-DISCOVERIES.md as a test-infra item; not chased mid-epic.

## Verdict
Gate clean for R8's scope. No R8-born defect carried forward. Two in-run discoveries
(the sanitizer safety reversal and the single-batch reply drop) were fixed with tests.
The only red suite is a pre-existing, unrelated `LayoutRouting` failure.
