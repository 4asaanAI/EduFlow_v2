# BLOCK 3 — completed (T11–T14), 2026-08-04

Branch `inspection-remediation-2026-08-04`. **Not merged to main.**
Theme: hygiene and standing risk. This closes the initiative's implementation work.

| Task | Finding | Status |
|---|---|---|
| T11 | NEW-09 48 warnings and no gate | ✅ Done — 48 → 0, gate on and proven |
| T12 | NEW-10 tool-routing tests crash on render | ✅ Done — frontend suite fully green |
| T13 | NEW-07 error shape + internal-id exclusions | ✅ Done |
| T14 | NEW-14 standing AWS permission | ⏸ Blocked on owner — cannot even be read from here |

Two of the four were run by parallel subagents (T11 and T12) with strict file fences;
T13 and T14 were done in the main session. All findings were re-verified independently
here before the block closed, and one of them produced a fix of its own (see F-1).

---

## T11 · NEW-09 — 48 warnings, and no gate

**48 → 0**, and **not one scoped eslint-disable was added**. Every warning had a real fix.
The single pre-existing disable at `ToolPage.js` (`useToolData`) was left untouched and is
now cited in the config as the reference pattern.

Grouped by the kind of fix:

| Fix | Count | Where |
|---|---|---|
| Fetcher wrapped in `useCallback`, then listed in the effect | 20 | `AdminTools` (9), `OwnerTools` (7), `TeacherTools` (2), `StudentTools` (1), `QuerySection` (1) |
| Missing dependency simply added (value already stable) | 24 | `AdminTools` (13), `StudentTools` (7), `TeacherTools` (3), `ChatInterface` (1) |
| Fixed properly instead of by adding a dependency | 3 | `Sidebar` ×2, `ToolPage` ×1 |
| Reasoned through a re-run risk, then listed it | 1 | `ChatInterface` conversation switch |

The three that needed more than a dependency:

- **`Sidebar` conversation menu.** The outside-click listener wanted `onClose`, which the
  parent passes as a fresh inline arrow every render. Listing it would have torn down and
  re-added a document listener on every single render. The latest `onClose` now lives in a
  ref and the listener registers once.
- **`Sidebar` auto-open group.** This one would genuinely have looped: the effect calls
  `setOpenGroups(new Set(...))`, which re-renders, which would mint a new config object,
  which would re-run the effect. It is safe only because `getGroupConfig()` returns a
  reference into a module-level constant. **Independently verified here** rather than
  taken on trust.
- **`ToolPage` `DataTable`.** `safeRows` fed a `useMemo` sort, and its `: []` fallback
  minted a new array every render, so the whole table re-sorted on every render. Now
  memoised.

The 24 "just add it" cases were almost all `currentUser`. It is context **state**, not a
rebuilt object, so adding it cannot loop; what it does fix is a screen showing the previous
person's data after a session change. That was checked before it was applied 24 times, not
after.

**The gate.** In `frontend/craco.config.js`, `react-hooks/exhaustive-deps` was `"warn"`.
It is now **`"error"` on the production build** and stays `"warn"` under `craco start`, so
a half-written effect does not block the dev server mid-edit. Run it with
**`cd frontend && npx craco build`** (`CI=true` is no longer needed, though it still works).
There is no CI workflow in this repo, so the build command IS the gate. A comment in the
config explains the history and tells the next person to use a scoped disable rather than
relaxing the rule back.

**Proven, not assumed:** a dependency was deliberately removed again and the build printed
`Failed to compile.` naming the rule, then it was restored and the build went clean. That
check was run here in the main session, not accepted from the agent's report.

## T12 · NEW-10 — the tool-routing tests

**Frontend suite is fully green for the first time: 284 → 286 passed, 0 failed**, stable
across repeated runs including a serial one.

The `AggregateError` was React swallowing the real error thrown inside a mount effect.
Unwrapped it was `getMyTokenUsage is not a function` and
`getUnreadNotificationCount is not a function` — **exactly D-48**. The test mocked
`lib/api` with a factory listing 8 names; the real module exports **123**, and the shell
calls about fifteen. Every unlisted name was `undefined`, so the first effect to fire blew
up before any assertion ran.

Two traps underneath it, both worth knowing before anyone touches the eight other files
carrying the same stub (now logged as D-60):

1. Create React App's Jest preset sets **`resetMocks: true`**, which strips the
   implementation off every `jest.fn()` before each test. `jest.fn(async () => …)`
   therefore returns `undefined`, and the obvious fix fails confusingly. Plain functions.
2. **Two of the old assertions were simply wrong.** They looked for the text
   "Attendance Recorder" and a header matching `/Tools \(/`. Neither string exists
   anywhere in the app. These tests could never have passed even with a working harness.
   They were stale, not merely broken.

The mock is now derived from the real module's export list, so a helper added later cannot
silently break the suite again. Assertions were **strengthened**, not just repaired: test 1
proves the URL-named tool mounted, that it is not the spinner or the error boundary, that a
different tool is not showing, and that the URL was not rewritten; test 2 proves the address
bar gains `tool=fee-sync`, loses the old value, and that the panel actually swapped. Only the
test file changed.

## T13 · NEW-07 — error shape and internal ids

Four refusals converted from HTTP 200 + `{"success": False}` to real errors, and the
frontend updated in the same change so nobody loses a message they used to see:

| Refusal | Was | Now |
|---|---|---|
| unknown action | 200 | **404**, naming the action |
| action not permitted | 200 | **403** "You do not have permission to run this action." |
| empty message | 200 | **400** |
| rejected image attachment | 200 | **400** |

The empty-message one actually mattered beyond monitoring: the browser received a 200 and
tried to read it as a live stream, which produced a silent turn.

Frontend: `ChatInterface.executeAction` normalises both shapes so the person still sees the
real reason instead of a generic "Action failed", and `sendMessageStream` pulls the sentence
out of `{"detail": …}` rather than throwing raw JSON at the user.

**Second half, re-measured rather than trusted.** The register's "48 reads without
`{"_id": 0}`" came from a grep that over-counts, because the projection is usually on the
next line. Counted properly with a paren-matching scan, there are **52** such reads — and of
those only **4** actually reach a response body: a student's own fee transactions, the
pending-discount approvals list, a single facility request, and the token-usage records.
Those four are fixed. The other 48 are internal lookups whose fields are copied into a
hand-built response, or genuinely need `_id` (the image-generation quota increments by it),
or are write-path re-reads. Blanket-adding a projection there would have been churn with a
real chance of breaking something, so it was not done.

Tests: `tests/backend/api/test_inspection_block3_error_shape.py` (7).

## T14 · NEW-14 — ⏸ Blocked on owner

Part (a), "confirm the permission is still present if it has read access", **could not be
done, and that is worth recording rather than glossing**. Three read-only attempts were made
and all three were denied:

- `iam:ListUserPolicies` as the `Claude` user → AccessDenied
- `iam:GetUserPolicy` as `claude-hosting` itself → AccessDenied
- `iam:SimulatePrincipalPolicy` as a last resort → AccessDenied

So the agent can neither confirm nor deny that the permission is still attached. D-34's
original finding stands as the last known state. Nothing was written or changed.

Part (b) is done: the click path is in front of Abhimanyu in the human checklist.
**IAM → Users → `claude-hosting` → Permissions → `s3-file-storage-policy` → Remove.**
Removing it breaks nothing: the running app authenticates as the EC2 instance role, and
`EduFlowFileStorage` on that role is what serves files.

---

## Gate at close

- Backend: **2012 passed / 0 failed / 14 deselected**
- Frontend: **286 passed / 0 failed / 32 suites** (was 282 / 2 at block start)
- Production build: **compiles clean, 0 warnings**, with the gate set to error and
  demonstrated to fail on a reintroduced violation
- Evals (structural + judge-logic): **18 passed**
- scoped_filter/scoped_query audit on every touched backend file: **no new hits**
