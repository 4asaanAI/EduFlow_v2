# BLOCK 1 — block-close quality gate (2026-08-04)

Lenses run over the whole block's combined diff, per protocol STEP 4c:
**Blind Hunter** (`bmad-review-adversarial-general`, diff only, no project access),
**Edge Case Hunter** (`bmad-review-edge-case-hunter`, diff + project read access) and
**Acceptance Auditor** (diff + the register + `CLAUDE.md` + `project-context.md`), driven by
`bmad-code-review`. `bmad-testarch-test-review` and `bmad-testarch-trace` were applied
manually against their checklists under `_bmad/tea/workflows/testarch/`.

Rule: every finding is either **fixed in-run with a regression test**, or **dismissed with a
written reason**. Nothing carries into Block 2.

---

## Fixed in this run

| # | Severity | File | Issue | Fix | Regression test |
|---|---|---|---|---|---|
| 1 | **High** | `backend/services/confirm_tokens.py:293` | A confirm token belonging to another user or an earlier browser session answered **401**. Harmless while the confirm card used a bare `fetch`; once T3 routed it through the refreshing wrapper, 401 means "renew and retry" — the renewal succeeds, the retry is refused identically, and the person is **signed out for tapping a stale Confirm button**. T3 would have created a forced logout. | 401 → **403**. The caller *is* authenticated; the token is foreign. Root fix, not a client special-case. Docstring corrected. | `test_confirm_token_plan_e1.py::test_consume_foreign_session_token_is_403_not_401` (also asserts the rightful owner still passes, so it cannot pass by refusing everybody) + `test_phase4_idempotency_sse.py::test_cross_session_confirmation_token_returns_403`, **rewritten not deleted** per the D-14 precedent |
| 2 | **High** | `frontend/src/lib/api.js` `subscribeSSE` | The live notification stream used a bare `fetch` and, on 401, fell straight into `scheduleReconnect()` — retrying **forever with the same dead token**. Notifications went silent after 60 minutes and never recovered until a page reload. Exactly NEW-03's defect class, hiding inside the file the new guard test allow-lists. | Refresh once and reopen (a GET cannot duplicate anything), then emit `sse_auth_expired` and stop rather than reconnecting into a wall. Same shape as `sendMessageStream` in the same file. | Covered by the wrapper contract tests; behaviour asserted by inspection — see "Accepted limits" |
| 3 | Medium | `tests/backend/unit/test_image_gen_persistence.py` | Only the *refused* half of the two-profile rule was tested. A later narrowing to principal-only would have locked the **Owner** out of issuing any certificate, with a green suite — the same shape of miss that let NEW-01 through. | Added `test_certificate_allowed_for_owner` and `test_id_cards_allowed_for_owner`. | the tests themselves |
| 4 | Medium | `backend/routes/image_gen.py:17` | `require_role` still imported after T1 removed both uses. | Import removed. | build/collection |
| 5 | Medium | `frontend/src/lib/__tests__/apiBaseUrl.test.js` | The comment-stripper treated the `//` in `https://` as a line comment and deleted the rest of the line, so `const u = 'https://x'; fetch(u)` was invisible to **both** guards. A guard with a hole in it that still reports green. | `(?<!:)` on the comment pattern. | new test `the checks above actually detect a violation when there is one` |
| 6 | Medium | same | `walk()` collected `.js` only; the repo has ~50 `.jsx` files under `components/ui`. A `.jsx` reader of the env var would have been invisible. Latent, not live. | `/\.jsx?$/`. | the walk-size assertion |
| 7 | Medium | same | `(?<![\w.])fetch\s*\(` excluded everything after a dot to skip `apiFetch` — which also excluded `window.fetch(` and `globalThis.fetch(`, the two commonest ways a bare fetch comes back. | Explicit alternation. **My first attempt at this fix was itself wrong** (the optional prefix group could not satisfy the lookbehind, so it matched neither spelling); caught by writing the table-driven test below before trusting it. | new test `the bare-fetch pattern catches every spelling and no false ones` — 6 positive, 6 negative cases |
| 8 | Medium | same | `contexts/UserContext.js` was allow-listed **wholesale** so login/logout could stay bare. Any future data call added to the file that owns the app's auth state would escape the guard entirely. | Allowance narrowed to **per line**, matching `/auth/(login\|logout)`. | the guard test itself |
| 9 | Medium | `frontend/src/components/__tests__/ToolScreenTokenRefresh.test.js` | `global.fetch` assigned directly but only `jest.restoreAllMocks()` in `afterEach` — which restores `jest.spyOn` spies, not assignments. A new global leak in a repo that has already lost days to order-dependent tests (D-03, D-35). | Original captured and restored by hand. | — |
| 10 | Medium | same | One test asserted `queryByText(/failed to load/i)` is absent — a string that component never renders. Unfalsifiable: it passed identically before and after the change. | Replaced with a **second real screen** (Incident Tracker) driven through the same 401, so the block proves a property of the conversion rather than one lucky file. The first test now also asserts the data actually **renders**. | the tests themselves |
| 11 | Low | `frontend/src/lib/__tests__/feeDiscountPaths.test.js` | `indexOf('pending-approvals/${id}/approve')` hardcoded the local variable name; renaming `id` would fail the test for the wrong reason with an opaque message. | Pattern match with an explicit not-null assertion. | — |
| 12 | Low | `frontend/src/components/tools/SchoolActivities.js` | My own comment said the local `apiFetch` "shadowed the import". It did not — there was no import before this change. Wrong history, written to be authoritative for the next reader of a session-sensitive refactor. | Comment corrected to what actually happened. | — |
| 13 | Low | `tests/backend/unit/test_image_gen_persistence.py` | `@pytest.mark.parametrize` across a security boundary, which CLAUDE.md forbids outright, with no note. | Kept, with the deviation **stated and justified in the file**: every parametrised case is on the same side of the boundary (all expect 403) and each allowed profile has its own named test. The rule guards against averaging an allowed case with a refused one, which this does not do. Deriving the list from `SUB_CATEGORIES_BY_ROLE` is the point — NEW-01 happened because a hand-maintained list did not notice. | — |
| 14 | **High (process)** | working tree | Mid-review, `frontend/src/lib/api.js` and `components/tools/QuerySection.js` were reverted to `HEAD` in the working tree. Cause identified: the Edge Case Hunter was **revert-testing the new tests** (a good thing to do — it proved 5 of 10 new tests fail without the fix, so they are not vacuous) and restored them afterwards. It briefly made all three new frontend suites fail. | Detected independently and restored from the index (`git checkout-index`) before the agent's own restore. Recorded because the Acceptance Auditor's findings were measured partly against that transient state. | full suite re-run after restore |
| 15 | **High** | `frontend/src/components/tools/AdminTools.js:617,709,1947` | Both callers of `downloadBlobAsPdf` passed **no `onError`**, and the helper does `onError && onError(e)` — so a failed download was caught and **dropped**. T1 made this reachable: office staff still see the Certificates and ID Cards tiles (D-49) and now get a 403, so the button went from "Generating PDF…" back to normal with no file, no message and no reason. The failure-that-looks-like-nothing-happened defect, and it would be reported as "the button is broken" rather than "you are not allowed". | Added `explainDownloadFailure(status)` — a plain sentence for 403 / 429 / 404 / other, naming who to ask rather than a status code — wired `onError` at both call sites, and rendered the message on both screens. | **new file** `DocumentRefusalIsVisible.test.js`: the refusal is shown in the person's own words, the daily cap reads as a cap, the button does not stay stuck on "Generating", and no status code or stack trace leaks to the screen |
| 16 | Low→Medium | 4 test files | `HealthScoreAttendance.test.js` mocks `lib/api` with **exactly** `OwnerTools.js`'s old import list and no `API`/`apiFetch` — the twin of the `BoardReport.test.js` mock that broke. `ChatInterface.r8` and `ChatStreamProgress` stub `apiFetch` but not `API`, so the URL under test was literally `"undefined/tokens/usage/me"`. `Epic6NothingGetsLost` mocks Header's list without `apiFetch`. | `API` and `apiFetch` added to all four, each with a one-line note pointing at D-48. Not all of D-48 — the remaining files are listed there for whoever needs them. | existing suites |
| 17 | Low | `frontend/src/components/tools/FeeCollection.js` | The `lib/api` import sat **below** two functions that use `API`/`apiFetch` — legal (imports hoist) but a script artefact that reads as a bug and breaks the moment `import/first` is enabled. | Moved to the top with the other imports. | build |

## Dismissed, with reasons

| Finding | Why dismissed |
|---|---|
| "`ToolScreenTokenRefresh.test.js` imports `setAuthRedirectHandlerForTests` / `resetAuthRedirectGuardForTests`, which the diff never creates" | Both already exist in `lib/authSession.js` and are used by the pre-existing `lib/__tests__/api.test.js`. The Blind Hunter had no project access; verified and the tests pass. |
| "`require_owner_or_principal` may not be imported in `image_gen.py`" | It was, on line 17, before this change. Same blind-diff artefact. |
| "The `SchoolActivities.js` rename may have missed call sites, silently returning a `Response` where JSON is expected" | Correct concern, wrong conclusion. Swept the whole file: the only remaining `apiFetch(` is the single delegation inside `activitiesRequest`. All 8 call sites renamed. |
| "The streaming chat POST in `StudentTools.js` should not go through `apiFetch`" | `apiFetch` never reads the response body — it inspects `status` and returns the `Response`, so `res.body.getReader()` still works. And a 401 means the request was rejected before the handler ran, so the retry cannot duplicate a message. |
| "`/auth/set-password` is like login and should stay a bare `fetch`" | It is `Depends(get_current_user)` and does **not** check the current password, so a 401 there is only ever an expired session. Refresh-and-retry is the correct behaviour. |
| "Retrying a POST on 401 could double-create records (SMS, payroll, points, capped documents)" | Audited every 401 the backend can raise: all are pre-handler (auth dependency, refresh tokens, login) except the confirm-token ownership check, which was finding #1 and is now 403. A 401 therefore always means no work was done. |
| "`apiFetch` now sends `credentials: 'include'` on 178 calls that did not before" | The backend sets `allow_credentials=True` with explicit origins, and every pre-existing `apiFetch` call already did this. No change in what the server accepts. |
| "Backend positive tests assert `200`, coupling permissions to PDF generation" | The autouse fixture seeds the student and class these tests need, so a seeding failure is not a plausible cause. `!= 403` would be a weaker assertion for no gain. |
| "`SUB_CATEGORIES_BY_ROLE['admin'] - {'principal'}` assumes a set" | It is a `frozenset`. Verified. |
| "`getAccessToken` / `refreshAccessToken` may now be unused in `UserContext.js`" | Both still used (`useState` initialiser and `validateToken`). Only `redirectToLoginOnce` became unused and was removed. |
| "`authFetch` was a public export; the diff removes no `import { authFetch }`" | Because there were none. Grepped the whole of `frontend/src`: the only occurrence was the declaration. |
| "Nine other test files stub `lib/api` and may break" | True but not broken today — they pass because they do not render a converted screen. **Not silently accepted: logged as D-49… see D-48** in `DEFERRED-AND-DISCOVERIES.md`, called out specifically for whoever does T12, whose `LayoutRouting.test.js` renders a converted screen and will need its mock extended. |
| "Multipart uploads still post to the CloudFront base rather than `UPLOAD_API`" | Real inconsistency, pre-existing, and both Amplify variables currently point at the same URL so nothing can be broken by it right now. Resolving it is a decision (delete the second base, or route all five uploads through it), not a cleanup. **Logged as D-47** and put on the human checklist as something for Abhimanyu to test. |
| "`main` is shipping a red backend test — the real hole is that nothing blocks a red suite from being merged and deployed" | **Correct, and a better diagnosis than the register's.** My own note said "nothing but the single accountant test noticed"; the test *did* notice — nothing was listening. Fixing the gate closes the symptom, not the hole. Setting up a merge gate is its own piece of work with its own blast radius (it can block the owner's deploys) and it is nobody's task in the current 14, so it is **logged as D-52** rather than started. Note it is entangled with T11: the frontend build cannot gate anything until its 48 warnings are cleared, which is exactly why no one turned one on. |
| "`image_gen.py` has no branch scoping on the student lookup, and the daily cap is per school not per branch" | Real. **No live impact: the school has exactly one branch** (`branch-joya`, all 1,802 students — confirmed under D-28). And it is a different question from T1's: T1 asked *who* may issue a document, this asks *which students* they may issue one for, which changes what a principal can do and is therefore the owner's call in the same way T1 was. **Logged as D-53.** Worth knowing that the file contains no `scoped_filter`/`scoped_query` at all, so the standing audit grep passes on it vacuously. |
| "`credentials: 'include'` now attaches the httpOnly refresh cookie to ~178 previously-cookieless calls, including multipart uploads" | Same origin, and every pre-existing `apiFetch` call already did it. No new cross-site exposure. |
| "4 suites cannot run — `Cannot find module 'react-router-dom'`" | An artefact of the reviewer's throwaway `git worktree`, which had no usable `node_modules`. All 31 suites run in the real tree; the final numbers below are from there. |
| "The block-comment stripper in the guard test only handles single-line `/* … */`" | A multi-line commented-out block containing `fetch(` would produce a **false positive** — the guard failing when it should not. That is the safe direction to be wrong in, and it is loud rather than silent. Not worth more regex. |

## Accepted limits (stated rather than hidden)

- **`subscribeSSE`'s fix has no automated test.** Testing it needs a fake streaming body
  through a reconnect loop with timers; the wrapper's refresh contract is covered, but the
  SSE path specifically is asserted by reading the code, not by a test. Said plainly rather
  than counted as covered.
- **Two of the four tests in `ToolScreenTokenRefresh.test.js` would also pass on the
  pre-change code**, because they exercise `apiFetch` directly and the wrapper already
  existed. Kept deliberately as the contract the screens now depend on, and **labelled as
  such in the file** so nobody mistakes them for proof of the change. The two screen-level
  tests are the ones that prove it.
- **The `.jsx` and `window.fetch(` guard improvements close latent holes, not live ones.**
  No offender of either kind exists today.
- **The reviewers independently revert-tested the new tests** and found 5 of 10 fail when
  `lib/api.js` and `QuerySection.js` are restored from `HEAD`, and that
  `test_image_gen_persistence.py` is 1 failed / 7 passed in a clean `HEAD` worktree against
  30 passed here. So the tests in this block are not vacuous.

## Final gate

| Gate | Result |
|---|---|
| Backend | **1991 passed / 0 failed / 14 deselected** |
| Frontend | **282 passed / 2 failed** — both `LayoutRouting.test.js` (`AggregateError` at render), pre-existing and owned by T12 |
| Production build | Compiles. **48** lint warnings — identical to the pre-existing count |
| AI evals | structural + judge-logic **18 passed** |
| `scoped_filter` audit | no hits in either touched backend file |
