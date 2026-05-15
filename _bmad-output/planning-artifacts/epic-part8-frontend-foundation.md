---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 8'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 8
part_name: 'Frontend Foundation'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy']
test_baseline: '387 backend tests passing, 0 skipped; 4 e2e specs (chat, auth, students, rate-limit)'
---

# EduFlow Quality Sweep — Part 8: Frontend Foundation

## Context

Part 8 targets structural correctness and resilience of the shared frontend layer: the AI chat interface, the confirm-action card, the message renderer, the error boundary, the tool layout primitives, the API client, and cross-cutting concerns such as theme consistency and sidebar active-state management. Issues were found by auditing the following files:

- `frontend/src/components/ChatInterface.js`
- `frontend/src/components/ConfirmActionCard.js`
- `frontend/src/components/MessageRenderer.js`
- `frontend/src/components/ErrorBoundary.js`
- `frontend/src/components/tools/ToolPage.js`
- `frontend/src/lib/api.js` (first 150 lines, `sendMessageStream`, `apiFetch`, `subscribeSSE`)
- `frontend/src/components/Layout.js` (activeTool state machine)
- `frontend/src/components/Sidebar.js` (active tool highlight)

**Entering baseline:** 387 backend tests passing, 4 e2e specs.

---

## Epic P8: Frontend Foundation Hardening

### Story P8.1: SSE stream — add exponential back-off reconnect and clear thinking state on hard error

**Problem:** `sendMessageStream` in `api.js` (lines 81–125) is a plain `fetch` call that reads the stream with a `while (true)` loop. On network drop mid-stream, the `while` loop exits via `done = true` from the reader — which falls through to the post-`await` cleanup block (lines 455–469 in `ChatInterface.js`) that marks streaming done. This path works for a clean close, but:

1. There is no retry / reconnect. A mobile user who loses signal for 2 seconds gets a "(Response interrupted)" message with no automatic recovery.
2. The "thinking" steps are left in an active/done state from before the drop — if the drop happens before any `text_delta` arrives, `thinkingCollapsed` is never set to `true` and the thinking panel stays expanded with stale "running" steps.
3. `subscribeSSE` (lines 137+) has its own reconnect loop but `sendMessageStream` is a separate path with none.

**Scope:**
- Add an exponential back-off reconnect to `sendMessageStream`: on stream error (caught exception), wait `min(2^attempt * 500ms, 8000ms)`, then re-issue the POST with the same `convId` and `text`. Maximum 3 retries; after exhaustion surface the error to the caller.
- On every caught error in `sendMessageStream` (before retrying), emit a synthetic `{type: 'thinking_clear'}` event to the caller so `ChatInterface.js` can reset the thinking panel.
- Handle the `thinking_clear` synthetic event in `ChatInterface.js` to call `setThinkingSteps([])` and `setThinkingCollapsed(false)`.
- Add a `retryCount` display to the "interrupted" fallback message: "Connection interrupted — retrying (1/3)..." so the user can see that recovery is in progress.
- Add unit tests: mock fetch to fail once → expect retry; mock fail 3× → expect error surfaced.

**Acceptance Criteria:**
- `sendMessageStream` retries up to 3× with exponential back-off on network error
- "Thinking" panel is cleared on each retry attempt (not left in stale state)
- After 3 failures the user sees the interrupted message with retry count
- At least 2 unit tests covering retry logic
- Existing 387 backend tests still pass

---

### Story P8.2: ConfirmActionCard — idempotent double-submit guard

**Problem:** `ConfirmActionCard.js` `handleClick` (line 131) already guards `status === 'loading'` at the top of the callback — which prevents a second click while the first request is in flight. However:

1. The guard uses `status` from the `useCallback` closure, which is stale if React batches a re-render. A rapid double-click within the same event-loop tick can bypass the guard because both clicks read the same pre-update `status = 'pending'`.
2. There is no `disabled` attribute coordination between the guard and the React `disabled` prop on the button (line 447): the button has `disabled={status === 'loading' || ...}` but `handleClick` still fires via keyboard (Enter/Space) even when `disabled` because `disabled` only prevents pointer events in some browsers when the handler is attached via `onClick` rather than native button `onclick`.
3. If the network is slow (> 5s), the user has no visual indication beyond the spinner inside the button. The outer card does not show a progress message.

**Scope:**
- Add a `useRef` submitting guard (`submittingRef`) that is set to `true` synchronously at the top of `handleClick` and cleared in the `finally` block. Check this ref before the `status` state check so rapid double-clicks are caught even within the same React render cycle.
- Ensure the `disabled` prop on the button element matches the `submittingRef` state, not only the `status` state, so keyboard activation is also blocked.
- Add a subtle progress label below the action details when status is `loading` and more than 2 seconds have elapsed: "Applying changes..." (use a `useEffect` with a 2-second timer).
- Add unit tests: render card in pending state, fire two rapid click events on the confirm button, assert `fetch` is called exactly once.

**Acceptance Criteria:**
- Rapid double-click on Confirm issues exactly one HTTP request (verified by test)
- Keyboard activation (Enter) on the confirm button is also blocked while loading
- "Applying changes..." label appears after 2 seconds of `loading` state
- At least 2 unit tests covering double-submit protection
- Existing 387 backend tests still pass

---

### Story P8.3: MessageRenderer — DOMPurify is applied but inline style injection is not blocked

**Problem:** `MessageRenderer.js` applies `DOMPurify.sanitize(markdownFn(message.content))` at line 301. This is correct for preventing script injection. However:

1. `processInline` (lines 75–84) builds HTML strings by interpolating user-facing text (e.g. the cell content in `renderTable` at line 67 passes `processInline(cell, true)` directly into an `<td>` HTML string). If AI-generated content contains a string like `"><img src=x onerror=alert(1)>` inside a table cell, `processInline` would inject raw HTML before `DOMPurify` runs. DOMPurify catches this — BUT it only runs on the final output of `markdownFn`, so the risk is that future changes to `parseMarkdownText` could introduce a sanitisation gap between construction and DOMPurify.
2. The `DOMPurify.sanitize` call uses default config which allows inline `style` attributes. An AI response like `<span style="background:url(javascript:...)">` passes DOMPurify's default config in some browser/version combinations.
3. Action button `label` values from `richBlocks` are rendered as React children (line 184) with no sanitisation — this is safe for text but could be a risk if labels contain HTML-like strings rendered outside the DOMPurify boundary.

**Scope:**
- Pass `{ FORBID_ATTR: ['style', 'onerror', 'onload', 'onfocus'] }` as the second argument to `DOMPurify.sanitize` to block inline style and event-handler attributes.
- Add a test fixture: a message content containing `<img onerror=alert(1)>` inside a table cell — assert the rendered output contains no `onerror` attribute.
- Add a test fixture: a message content containing `<span style="background:url(javascript:...)">` — assert no `style` attribute survives.
- Document the sanitisation config choice in a comment above the `DOMPurify.sanitize` call.

**Acceptance Criteria:**
- `DOMPurify.sanitize` is called with `FORBID_ATTR` config for `style`, `onerror`, `onload`, `onfocus`
- Test: `onerror` attribute is stripped from table cell content
- Test: `style` attribute containing `javascript:` is stripped
- Comment documents the config rationale
- Existing 387 backend tests still pass

---

### Story P8.4: ErrorBoundary — narrow scope to individual tool panels, not the whole app

**Problem:** `ErrorBoundary.js` currently wraps the entire React tree (or a large portion of it). The render fallback is `minHeight: '100vh'` with a full-page "Something went wrong" overlay. This means:

1. If a single tool panel (e.g. `FeeCollection`) throws a render error, the entire application — including the chat, sidebar, and other tools — becomes inaccessible.
2. The error boundary does not expose an `id` or `name` prop to contextualise what crashed, so the support message is always generic.
3. There is no error reporting hook — `componentDidCatch` only calls `console.error`, which is invisible in production.

**Scope:**
- Add a `name` prop to `ErrorBoundary` (e.g. `<ErrorBoundary name="FeeCollection">`). Use it in the fallback UI: "Something went wrong in FeeCollection. Other tools are still available."
- Change the fallback UI to a contained card (not full-screen overlay): `minHeight: 200px`, showing the tool name, error summary (dev only), and a "Reload this panel" button that calls `setState({ hasError: false })` rather than `window.location.reload()`.
- Wrap each tool panel individually in `ToolView.js` (or equivalent) with a named `ErrorBoundary` so that a tool crash does not affect the chat or sidebar.
- Add an optional `onError` prop: a callback called with `(error, info)` to enable future error reporting integration.
- Add a test: render a child that throws, assert the fallback shows the `name` and a "Reload" button, assert clicking Reload clears the error state.

**Acceptance Criteria:**
- `ErrorBoundary` accepts `name` prop and shows it in the fallback
- Fallback is a contained card, not a full-screen overlay
- "Reload this panel" resets `hasError` without page reload
- `onError` callback prop is wired to `componentDidCatch`
- Each tool panel is individually wrapped in a named `ErrorBoundary`
- At least 1 unit test covering boundary reset
- Existing 387 backend tests still pass

---

### Story P8.5: ToolPage — `useToolData` does not surface error state; `loading` prop unused in ToolPage header

**Problem:** `ToolPage.js` exposes a `useToolData` hook (lines 194–206) that returns `{ data, loading, error, reload }`. However:

1. `ToolPage` component itself accepts a `loading` prop (line 8) and passes it to the RefreshCw spinner but does NOT render a skeleton or loading indicator in the content area — the `children` are rendered regardless.
2. `useToolData` catches errors with `setError(e.message)` but the error message is only available to the parent component that calls `useToolData`. There is no shared `<ErrorCard>` utility component — each tool panel that uses `useToolData` must manually render error state, and several panels do not (`PrincipalDailyOps` checks `error` but `FeeSync` does not use `useToolData` at all).
3. `DataTable` renders `emptyMsg` when `rows.length === 0` but has no way to distinguish "loading" from "actually empty" — a brief flash of "No data found" appears while data is loading.

**Scope:**
- Add a `<LoadingCard>` export to `ToolPage.js`: a simple div with a subtle animated pulse placeholder, shown when `loading === true` and `rows` is empty.
- Update `DataTable` to accept a `loading` boolean prop; when `true`, render `<LoadingCard>` instead of `emptyMsg`.
- Add an `<ErrorCard>` export to `ToolPage.js`: takes `message` and `onRetry` props; renders a contained error state with retry button.
- Update `useToolData` to accept an optional `renderError` prop (component or null) and document the expected pattern.
- Update `PrincipalDailyOps`, `FeeSync`, and any other tool using `useToolData` or manual fetch to use `<ErrorCard>` for error state and `loading` for the DataTable loading prop.
- Add tests: `DataTable` with `loading=true` and empty `rows` shows loading placeholder, not `emptyMsg`.

**Acceptance Criteria:**
- `DataTable` renders `<LoadingCard>` when `loading=true` and `rows` is empty
- `<ErrorCard>` component exported from `ToolPage.js`
- `PrincipalDailyOps` and `FeeSync` use `<ErrorCard>` for error state
- At least 2 unit tests (DataTable loading state; DataTable empty state)
- Existing 387 backend tests still pass

---

### Story P8.6: api.js — 401 race condition with concurrent requests

**Problem:** `apiFetch` in `api.js` (lines 26–47) handles 401 by calling `refreshAccessToken`, then retrying the original request. However:

1. If two concurrent requests both receive 401 (e.g. after a token expiry during the initial page load burst), both will call `refreshAccessToken` simultaneously. This can cause a "refresh race" — two simultaneous refresh calls to `POST /api/auth/refresh`, of which only one will succeed (the other gets 401 back from the refresh endpoint because the refresh token was already consumed). The second concurrent refresh attempt then calls `clearAuthSession()` and redirects to login.
2. There is no in-flight deduplication: `refreshAccessToken` in `authSession.js` is not guarded by a singleton promise.
3. The `sendMessageStream` function (line 81) does NOT use `apiFetch` — it calls `fetch` directly (line 85). This means it never retries on 401; it redirects immediately (line 95). This is intentional for the chat path (the conversation is already in progress) but there is no comment documenting this.

**Scope:**
- In `authSession.js` (or wherever `refreshAccessToken` lives), add a singleton promise guard: if a refresh is already in progress, all subsequent callers await the same promise rather than issuing a second refresh call.
- In `api.js`, document the intentional `sendMessageStream` 401 redirect with a comment: `// SSE path: 401 mid-stream → redirect immediately, no retry (conversation already in-progress)`.
- Add a unit test: mock two simultaneous `apiFetch` calls that both receive 401 — assert `refreshAccessToken` is called exactly once, and both calls eventually resolve (or both redirect).
- Add a unit test: mock `refreshAccessToken` to fail — assert `clearAuthSession` is called and `window.location.href` is set to `/`.

**Acceptance Criteria:**
- Concurrent 401s trigger exactly one `refreshAccessToken` call (singleton promise)
- Comment in `sendMessageStream` documents the intentional non-retry behaviour
- At least 2 unit tests for 401 race condition scenarios
- Existing 387 backend tests still pass

---

### Story P8.7: Theme consistency — tool panels bypass ThemeContext via hardcoded CSS variable names

**Problem:** `ToolPage.js` uses CSS variable references in the format `var(--tool-hex-<value>)` (e.g. `var(--tool-hex-1a1a1a)`, `var(--tool-hex-f5f5f5)`) rather than using `isDark` from `useTheme()`. These variable names are literal hex-colour stand-ins, not semantic theme tokens. If `ThemeContext` switches to a new colour scheme (e.g. a high-contrast mode), the tool panels will not respond. Meanwhile, `FeeCollection.js` uses CSS variables named `var(--c-bg)`, `var(--c-text)`, `var(--c-border)` — which ARE semantic. This split convention means tools look inconsistent and the theme switch does not apply uniformly.

**Scope:**
- Audit all tool panel files for `var(--tool-hex-...)` usage and `var(--c-...)` usage.
- Define a consistent set of semantic CSS variables in `index.css` / `theme.css` that map to the existing hex values in both light and dark modes: `--color-surface`, `--color-border`, `--color-text-primary`, `--color-text-muted`, `--color-text-secondary`, `--color-accent-blue`, `--color-success`, `--color-danger`, `--color-warning`.
- Update `ToolPage.js` to use the semantic variable names instead of `var(--tool-hex-...)`.
- Update `FeeCollection.js` and `FeeSync.js` to use the same semantic variable names (replacing `var(--c-bg)`, `var(--c-text)`, etc. with the new names).
- Verify `ChatInterface.js`, `MessageRenderer.js`, and `ConfirmActionCard.js` also use the semantic variables.
- Add a lint rule comment (or CI grep) that flags any new `var(--tool-hex-` or `var(--c-` usage in favour of the semantic names.

**Acceptance Criteria:**
- Zero `var(--tool-hex-` references remain in `ToolPage.js` after migration
- Zero `var(--c-` references remain in `FeeCollection.js` and `FeeSync.js` after migration
- Semantic variables are defined in both light and dark theme CSS files
- A comment in `index.css` / `theme.css` documents the intended variable naming convention
- Existing 387 backend tests still pass

---

### Story P8.8: Sidebar active state — URL-direct navigation does not highlight active tool

**Problem:** `Layout.js` manages `activeTool` as React state (initialized to `null`, line 72). The tool is set by calling `setActiveTool(toolId)` from the sidebar click handler or from a `CustomEvent('eduflow-navigate')`. However:

1. There is no URL-based routing (`react-router-dom` is not used). The URL does not change when a tool is selected (the app is a single page at `/`). This means a browser back-button press cannot navigate between tools.
2. Deep-linking to a tool is impossible: if a user is sent a link to a specific tool, the sidebar will not highlight the tool and the tool panel will not open — `activeTool` will be `null` after page load.
3. The `customEvent` handler in `Layout.js` (line 119) sets `activeTool` to `e.detail` (the tool ID) but the sidebar `activeTool` prop is only compared as a string match — if the navigate event arrives before the sidebar has mounted, it is silently dropped.

**Scope:**
- Add URL-hash-based routing: when the user selects a tool, set `window.location.hash = toolId`. On page load, read `window.location.hash` to initialise `activeTool`.
- Add a `hashchange` event listener in `Layout.js` to keep `activeTool` in sync with hash changes (back/forward navigation).
- Update the `Sidebar` to derive the active item from the hash as a fallback when `activeTool` prop is `null`.
- Add a unit test: simulate `window.location.hash = '#fee-collection'` on mount — assert `activeTool` is set to `'fee-collection'`.
- Add a unit test: programmatic back navigation (hash change) — assert `activeTool` updates correctly.

**Acceptance Criteria:**
- Selecting a tool updates `window.location.hash`
- Page reload with hash set correctly opens the tool and highlights it in sidebar
- Browser back/forward navigation between tools works via hash change
- At least 2 unit tests for hash-based routing
- Existing 387 backend tests still pass

---

## FR Coverage Map

| FR ID | Story | Description |
|-------|-------|-------------|
| FR-P8.1 | P8.1 | SSE stream reconnects with exponential back-off on network drop |
| FR-P8.2 | P8.1 | Thinking state cleared on stream error before retry |
| FR-P8.3 | P8.2 | Confirm button double-submit protected via `useRef` guard |
| FR-P8.4 | P8.2 | Progress label shown after 2s of loading state |
| FR-P8.5 | P8.3 | DOMPurify called with `FORBID_ATTR` for style and event handlers |
| FR-P8.6 | P8.4 | ErrorBoundary accepts `name` prop; fallback is contained card |
| FR-P8.7 | P8.4 | Each tool panel wrapped in named ErrorBoundary |
| FR-P8.8 | P8.5 | DataTable distinguishes loading vs empty state |
| FR-P8.9 | P8.5 | ErrorCard component available for all tool panels |
| FR-P8.10 | P8.6 | Concurrent 401 refresh de-duplicated via singleton promise |
| FR-P8.11 | P8.7 | Semantic CSS variables replace `var(--tool-hex-...)` and `var(--c-...)` |
| FR-P8.12 | P8.8 | URL hash routing for tool navigation |

---

## NFRs

| NFR ID | Category | Requirement |
|--------|----------|-------------|
| NFR-P8.1 | Resilience | SSE stream reconnect back-off must not exceed 8s between attempts |
| NFR-P8.2 | Security | DOMPurify must strip `style`, `onerror`, `onload`, `onfocus` from all AI-rendered HTML |
| NFR-P8.3 | Accessibility | Tool panel error and loading states must be announced via `role="alert"` or `aria-live` |
| NFR-P8.4 | Maintainability | All theme colours must reference semantic CSS variables; no hardcoded hex values in component inline styles |

---

## Implementation Order

1. **P8.3** (DOMPurify hardening) — pure additive, no UI changes, ship first
2. **P8.2** (double-submit guard) — isolated to ConfirmActionCard, low regression risk
3. **P8.6** (401 race condition) — foundational API client fix before other API work
4. **P8.4** (ErrorBoundary scope) — enables isolated tool crash recovery; prerequisite for P8.5
5. **P8.5** (ToolPage loading/error states) — uses ErrorBoundary from P8.4
6. **P8.1** (SSE reconnect) — needs P8.5 error states to display retry progress
7. **P8.7** (theme consistency) — CSS-only refactor, low risk, can run in parallel with P8.6
8. **P8.8** (sidebar URL routing) — last; touches Layout, Sidebar, and requires stable tool panel rendering from P8.4/P8.5

---

## Epic P8: Retrospective

A retrospective entry for Part 8 to be completed after all P8.1–P8.8 stories are done.
