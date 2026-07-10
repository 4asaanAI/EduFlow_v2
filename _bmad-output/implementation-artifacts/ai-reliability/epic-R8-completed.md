# Epic R8 — Frontend Chat Resilience — COMPLETED

**Date:** 2026-07-10 · **Branch:** `ai-reliability-r1-turn-completion`
**Fixes:** FH1, FH2, FH3, FH4, FH5, FM1, FM3, FM4, FL
**Goal met:** every frontend chat failure mode is now visible and recoverable — a 401,
a failed new-conversation, a failed history load, a dropped stream, an exhausted
token budget, and a failed recharge all surface a clear message and a way forward,
instead of a silent no-op or a permanently locked input.

**Baseline in (frontend):** 43 passed / 2 pre-existing `LayoutRouting` failures.
**Baseline out (frontend):** 47 passed / same 2 pre-existing `LayoutRouting` failures
(unchanged — they fail on `main` too; see review §pre-existing). Backend suite
untouched by R8 and still **1444 passed / 0 failed / 14 deselected**.

---

## R8.1 — Auth + conversation lifecycle failures visible (FH1, FH2, FM3)

**FH1 (`lib/api.js` `sendMessageStream`)** — A 401 on the initial chat response used to
redirect immediately (a silent no-op if the redirect was already debounced). Now it
refreshes the token **once** and retries the POST (safe: a 401 there means auth failed
*before* any assistant output or token debit, so no write can be duplicated). Only if
the retry is still 401 does it emit a **visible `error` event** and then redirect.
- **AC1** ✅ `test FH1: an initial 401 refreshes once, retries, and then streams`;
  `test FH1: a still-401 retry emits a visible error event`.

**FH2 (`ChatInterface.handleSend` + `InputBar.handleSend`)** — `createConversation`
failure used to silently `return` while the input was already cleared, losing the
user's text. Now `handleSend` returns `false` on failure; `InputBar` snapshots the
typed text, clears optimistically, and **restores it** if the send couldn't start; a
`sendError` banner explains why.
- **AC2** ✅ `InputBar.r8` restore test; `ChatInterface.r8` uses the same path.

**FM3 (`ChatInterface.loadMessages`)** — a failed history load was swallowed
(`catch {}`) and looked identical to an empty conversation. Now sets a `loadError`
state that renders a **"Couldn't load this conversation's history — Retry"** banner.
- **AC3** ✅ implemented; `loadError` banner + retry wired to `loadMessages(convId)`.

## R8.2 — State hygiene across conversations (FH4, FM4)

**FH4** — a conversation switch cleared messages but left `confirmAction` / `followup`
/ `aiUnavailable` / `thinkingSteps` / stream state from the previous thread (a stale
confirm card could post an action into the wrong conversation). New `resetTurnState()`
wipes **all** turn-scoped state on switch (guarded by `justCreatedRef` so an in-flight
just-created conversation isn't aborted).
- **AC1** ✅ implemented in the `[convId, currentUser.id]` effect.

**FM4** — the terminal handlers (`done` / `error` / `stream_error`) ran side effects
(`setMessages`, ref writes) *inside* `setCurrentStreamMsg(prev => …)` updaters, which
StrictMode double-invokes. The live stream message is now mirrored in `streamMsgRef`
and mutated via a single `setStream(next)` helper; every terminal handler reads the
ref and runs its side effects **outside** any updater.
- **AC2** ✅ implemented; verified by the R8 render tests (no double bubbles).

## R8.3 — Token exhaustion & recharge dead-end (FH5, FM1)

**FM1** — `token_exhausted` before any text delta made the question vanish. Now it
renders a **visible assistant bubble** ("You've reached your AI usage limit…") and
finalizes any partial content first.
- **AC1** ✅ `test FM1/R8.3 AC1: token_exhausted renders a visible assistant bubble`.

**FH5** — a failed recharge checkout was swallowed while the input stayed disabled by
`tokenExhausted` (permanent lock). `handleRecharge` now surfaces a `rechargeError`
message and the recharge button stays live to retry — never a dead-end.
- **AC2** ✅ implemented; `rechargeError` surface near the token bar.

## R8.4 — Stream retry + renderer fixes (FH3, FL)

**FH3** — `stream_error` showed a fake "retrying (x/3)" string but never actually
reconnected. Now a **transient network** `stream_error` triggers **one automatic
reconnect** (`autoRetryRef`, reset on `done`/manual retry), resending without a
duplicate user bubble; a second failure falls back to the manual Retry button.
- **AC1** ✅ implemented.

**FL bundle:**
- **`handleRetry`** no longer stacks a duplicate user bubble — it strips the
  interrupted error bubble(s) and resends with `skipUserBubble`. **AC2** ✅
  (`test …retry does not duplicate the question`).
- **Sanitizer/renderer reconciliation** — the old `FORBID_ATTR:['style']` stripped the
  renderer's own inline styling, so AI markdown rendered as unstyled plain text. Fixed
  by emitting **bare tags** and relying on the existing theme-aware `.prose-chat` CSS
  (element selectors in `index.css`, already complete). The sanitizer stays **strict**
  (drops style/class/handlers, restricts tags to the safe set, constrains link
  protocols) — safer than allowing `style` (DOMPurify does not reliably neutralize
  `url(javascript:…)` under jsdom). Markdown links now get a real, protocol-checked
  `href` (were rendered hrefless/unclickable). **AC3** ✅ (`MessageRenderer.test.js`).
- **SSE buffer tail flush** (`api.js`) — the decoder + buffer tail is flushed on stream
  end so a final frame (often the terminal `done`) not followed by a trailing blank
  line is no longer dropped. **AC4** ✅ (`test R8.4 AC4: the final SSE frame is flushed`).

## Beyond the stories (found + fixed in-run, R8-scoped)
- **`executeAction` now routes through `apiFetch`** (was raw `fetch`, no 401 refresh) —
  an expired token no longer silently fails a confirm-card action.
- **Client terminal backstop hardened (latent drop fix):** when every SSE frame
  (including `done`) arrives in a single React batch, `streaming` never commits `true`,
  so the streaming-transition flush effect sees no change and the finalized reply was
  dropped. The post-`await` backstop now flushes `pendingFinalMsgRef` **directly**
  (dedupe by id), so a fully-buffered fast response can't produce a silent empty turn.
  This is the client-side mirror of the R1 Turn Completion Contract.

## Deferred items handled this run
- **R1.1 AC4 (frontend event-switch jest test)** — DONE. `ChatInterface.r8.test.js`
  drives `error`, `token_exhausted`, an unrecognised event type, and the happy path,
  asserting the switch always renders something and retry doesn't duplicate.
- **R1 backend early-return persistence** — remains a **backend** single-exit refactor,
  out of R8's frontend scope; kept deferred to a dedicated `chat.py` story. The
  strengthened client backstop means any residual backend bare-return still surfaces a
  visible fallback to the user (the incident's user-facing symptom is covered).

## Test infra
- Added a global `scrollIntoView` no-op polyfill to `setupTests.js` (jsdom lacks it;
  ChatInterface calls it in an effect). Enables component-render tests for the chat
  surface. (Did not resolve the separate pre-existing `LayoutRouting` `AggregateError`.)

## Files touched
`frontend/src/lib/api.js`, `frontend/src/components/ChatInterface.js`,
`frontend/src/components/InputBar.js`, `frontend/src/components/MessageRenderer.js`,
`frontend/src/setupTests.js` + 4 test files (`sendMessageStream.r8`, `InputBar.r8`,
`ChatInterface.r8`, updated `MessageRenderer.test.js`).
