# Epic 5 — A Conversation That Feels Alive — COMPLETED

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`
**Owner items:** 9, 10, 12, 13

---

## What was found before the stories were written

The chat surface has been hardened twice already (epic R8 for resilience, Epic 9 for
the visual language). So the honest first move was to establish what is *still* broken
rather than rebuild what already works.

**Already correct, and deliberately left alone:**
- The composer auto-grows to a 160px ceiling, sends on Enter, opens a newline on
  Shift+Enter, and has its focus ring on the pill rather than the inner field.
- A stream that ends without its terminal `done`, drops mid-flight, or returns 401
  already surfaces a visible, retryable error. The decoder tail is flushed so a final
  frame is never lost.
- The server sends an SSE keepalive every 5 seconds.

Reporting that honestly matters more than padding the epic: **owner items 9 and 10 were
examined and found already addressed** by that earlier work.

## Story 5.1 — One progress box, lined up with everything else

| | |
|---|---|
| Files | `ChatInterface.js` |
| Tests | `ChatStreamProgress.test.js` (4 of 9) |

**The defect:** while streaming, the chat rendered a `ToolCallBadge` for
`currentStreamMsg.toolCall` **and** a `ThinkingProcess` panel fed by `thinkingSteps`,
which already contains `tool_start` / `tool_done` for the same tool. The same work was
announced twice, in two different shapes. That is owner item 12.

**And they did not line up.** The badge was indented 42px to clear the avatar gutter;
the panel had no left padding at all; the reply body began at 42px again. Three stacked
elements, three left edges, gaps of 4px / 8px / 24px.

- The panel is now the single account of progress. The badge renders only when there is
  no panel — so nothing is lost when a tool runs without steps.
- `STREAM_GUTTER` (42) and `STREAM_GAP` (8) are exported constants, and the test
  asserts the **value** rather than a person eyeballing a screenshot. This is exactly
  the class of defect a visual review keeps missing.

## Story 5.2 — A reply that stalls says so, instead of spinning forever

| | |
|---|---|
| Files | `ChatInterface.js` |
| Tests | `ChatStreamProgress.test.js` (5 of 9) |

**The gap:** every *detectable* failure was handled. What was not handled is a
connection that is accepted and then goes quiet — a wedged server, or a network that
drops without a FIN. `reader.read()` waits forever and the typing dots animate with
nothing behind them. NFR-P3 ("first token ≤ 3s") had nothing enforcing it.

- A client-side watchdog starts when the turn begins, not on first token — a request
  accepted and never answered is precisely the case being caught.
- **Two thresholds, two different statements.** At 12s: "Flo is taking longer than
  usual. Still working…". At 45s: "No response yet. The connection may have dropped".
  Conflating those would send the owner to retry a request about to succeed.
- **Any inbound event resets it** — a token, a thinking step, a keepalive. A long but
  genuinely-working answer is never declared stalled, and a test proves it across four
  near-threshold cycles.
- Cleared on success, on error and on unmount. A timer outliving the component is where
  "cannot update state on an unmounted component" warnings and phantom banners come
  from, and there is a test for that too.
- Announced with `role="status"` / `aria-live="polite"`.

## Test counts

| | Before | After | New |
|---|---|---|---|
| Backend | 1915 passed / 2 pinned | **1915 passed / 2 pinned** | 0 (frontend-only epic) |
| Frontend | 196 passed / 2 pre-existing | **205 passed / 2 pre-existing** | **9** |

Production build passes. No backend files touched, so the scoped-filter audit is not
applicable — confirmed by the unchanged backend count.
