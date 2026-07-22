# Epic 5 — Quality Gate Output

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`

Lenses applied over the epic's diff: code review, adversarial general, edge-case
hunter, test review, AC trace, NFR.

> **Scope honesty.** This is the smallest epic of the sweep, and deliberately so. Two
> of its four owner items were found already fixed by earlier work, and inventing
> stories to cover them would have produced churn in the most safety-critical surface
> in the product. What is here is what was actually broken.

---

## Findings — all fixed in-run

| # | Sev | Where | Finding | Fix | Regression test |
|---|---|---|---|---|---|
| F-1 | 🟠 | `ChatInterface.js` | The same tool was announced twice — once by `ToolCallBadge`, once by the `ThinkingProcess` panel that already holds `tool_start`/`tool_done`. Owner item 12. | The panel is the single account; the badge is the fallback when there is no panel. | `a running tool is announced once…` |
| F-2 | 🟠 | `ChatInterface.js` | Three stacked stream elements at 42px, 0px and 42px left offset, with 4/8/24px gaps. UX-DR8. | `STREAM_GUTTER` / `STREAM_GAP` exported and shared. | `everything stacked in the turn shares one left edge` |
| F-3 | 🟠 | `ChatInterface.js` | A stream accepted and then silent spun the typing dots indefinitely. Nothing enforced NFR-P3. | Two-threshold watchdog, reset by any inbound event. | 5 tests |
| F-4 | 🟡 | `ChatStreamProgress.test.js` | **Mine.** CRA sets `resetMocks: true`, which wipes module-factory mock implementations before each test — the health widget then got `undefined` and threw on `.then`. All 9 tests failed for a reason unrelated to the code under test. | Implementations re-established in `beforeEach`. | the file passing |

## Findings dismissed, with reasons

| Finding | Why dismissed |
|---|---|
| "Rebuild the composer (item 9)" | Examined: auto-grow with a 160px ceiling, Enter to send, Shift+Enter for newline, slash and @ menus, focus ring on the pill. Already correct. Changing it would be churn in a surface the owner uses constantly. |
| "Fix sudden dumps (item 10)" | The stream renders token-by-token and the decoder tail is flushed so a final frame is never lost. The "dump" symptom is what happens when a *stall* is followed by everything arriving at once — which is F-3, and is fixed there rather than twice. |
| Making the stall thresholds configurable | Two exported constants are enough to tune and to test against. A settings surface for them would be scope no one asked for. |
| Auto-retrying on stall | The existing `stream_error` path already has a bounded auto-retry budget. Adding a second automatic retry on the watchdog risks two turns racing for one conversation. The watchdog tells the person; the person decides. |

## NFR check

| NFR | Result |
|---|---|
| NFR-P3 (first token ≤ 3s) | Cannot be *enforced* client-side, but is now *observable*: silence is surfaced at 12s rather than never. Stated plainly rather than claimed as met. |
| NFR-SSE1 / SSE4 | The keepalive is treated as proof of life, so "still working" and "nothing is coming" stay distinct statements. |
| NFR-A2 | The stall notice carries `role="status"` and `aria-live="polite"`; the panel's summary bar keeps its keyboard operation and focus state. |
| UX-DR8 | One gutter, one gap, asserted by value. |
| Memory safety | Timers cleared on success, error and unmount, with a test asserting no unmounted-component warning. |

## AC trace

Every AC on Stories 5.1 and 5.2 maps to a test. One is **not verified by this run** and
is on the human checklist: that the thresholds *feel* right to a person on a real
connection. 12s and 45s are judgements, not measurements, and only use will settle them.

## Final counts

| | Result |
|---|---|
| Backend | **1915 passed, 2 failed (pinned D-03), 14 deselected** — unchanged, no backend files touched |
| Frontend | **205 passed, 2 failed (pre-existing LayoutRouting)** |
| Production build | **passes** |
| New tests | **9** |
| Live-data writes | **0** |
