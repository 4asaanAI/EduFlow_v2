# BLOCK 3 — quality gate output (T11–T14), 2026-08-04

Lenses applied over the whole block's combined diff: code review, adversarial-general,
edge-case hunter, test review, and requirements trace. The BMAD skills were not invoked as
skills in this harness; the equivalent passes were run manually against the same criteria,
which the protocol permits.

Two tasks were executed by parallel subagents. **Their reports were treated as claims, not
as results.** Every number quoted below was re-run in the main session, and the two riskiest
pieces of their reasoning (the gate actually failing, and the one effect that could have
looped) were verified independently rather than accepted.

## Findings

| # | Sev | File | Issue | Fix | Regression test |
|---|---|---|---|---|---|
| F-1 | **high** | `frontend/src/components/tools/AdminTools.js` | **A live defect, found while clearing warnings.** The Attendance Recorder called `getTodayAttendance(classId, date)` with `currentUser` in the date slot, so every request carried `?date=[object Object]`. The server matched that literal string, found nothing, and the register showed **every child as "not marked" whatever had actually been recorded** — on today's date as much as any other — and changing the date changed nothing. Anyone could have re-marked over a register that was already taken. | Pass `date`. | `AttendanceRecorderDate.test.js` — two tests: the request carries a real `YYYY-MM-DD`, and changing the date changes what is asked for. **Verified fails-before / passes-after** by reinstating the old call. |
| F-2 | medium | `frontend/src/components/Sidebar.js` | The auto-open-group effect would genuinely have looped once `groupConfig` was listed (effect sets state → re-render → new config object → effect again). | Safe only because `getGroupConfig()` returns a reference into a module-level constant. **Independently confirmed here**, not taken on trust. | Covered by the full frontend suite; a loop would hang the test run. |
| F-3 | medium | `frontend/src/components/Sidebar.js` | Listing `onClose` directly would have torn down and re-added a document listener on every parent render, because it is passed as a fresh inline arrow. | Latest `onClose` held in a ref; listener registers once. | Full suite. |
| F-4 | medium | `frontend/src/components/tools/ToolPage.js` | `safeRows`'s `: []` fallback minted a new array every render, so the memoised sort re-sorted every render. | `useMemo`. | Full suite. |
| F-5 | medium | `backend/routes/chat.py` + `frontend` | Converting the refusals to real HTTP errors would, on its own, have **lost** the specific message: the frontend checked `res.success` and would have fallen through to a generic "Action failed" for every 403. | Frontend normalises both shapes in the same change; the stream path parses `detail` instead of throwing raw JSON at the user. | `test_unauthorized_action_is_403_and_says_why` asserts the sentence is present. |

## Dismissed, with reasons

| Concern | Why dismissed |
|---|---|
| "24 added `currentUser` dependencies will cause fetch loops." | `currentUser` is context **state**, not an object rebuilt per render, so its identity only changes on an actual session change. Checked before the change was applied, and the full suite would hang if it were wrong. |
| "The gate is claimed, not proven." | Not accepted on the claim. A dependency was deliberately removed here, the build printed `Failed to compile.` naming the rule, and it was then restored and the build went clean. |
| "T13 should add `{"_id": 0}` to all 48 reads, as the register says." | The register's count came from a grep that over-counts. Measured properly there are 52, and only 4 reach a response body. Adding a projection to internal lookups is churn with real breakage risk — one of them (`image_gen` quota) increments **by** `_id` and would break outright. The rule is "never expose `_id` in responses", and that is now true. |
| "T14 should have been confirmed before being marked blocked." | It could not be read. Three separate read-only calls were denied. Recording "cannot confirm" is the honest outcome; claiming the permission is or is not there would be a guess. |
| Two parallel agents editing the same tree. | Fenced by file: one owned application components and build config, the other owned only the routing test file. Verified after the fact: `git status` shows no overlap, the T13 frontend edits made in the main session survived intact, and the full suite is green. |
| Frontend line endings are inconsistent across files. | Real but cosmetic, pre-existing, and outside this block. Each file's existing endings were preserved rather than normalised, which would have produced a diff nobody could read. Logged. |

## Test review

- The new frontend test uses the `requireActual`-derived mock and plain functions, i.e. it
  is written to the pattern that came out of T12 rather than repeating the trap that caused
  T12 in the first place.
- F-1's guard was explicitly run against the **old** code to confirm it fails, then against
  the fixed code. A regression test that was never seen to fail is not a regression test.
- The T13 tests assert the **absence** of the old shape (`"success" not in resp.json()`),
  not merely the presence of the new status, so a belt-and-braces handler that returned both
  would still fail.
- Every new backend test file carries `from __future__ import annotations`.
- The action endpoint got its unauthenticated-401 test, per the standing security
  convention.

## Trace (requirement → proof)

| Requirement | Proof |
|---|---|
| NEW-09 warnings cleared | `npx craco build` → 0 occurrences of the rule |
| NEW-09 gate cannot regrow | violation reintroduced → `Failed to compile.`; restored → clean |
| NEW-09 no silencing | zero new eslint-disables in the diff |
| NEW-10 both tests green | 286 passed / 0 failed, repeated runs |
| NEW-10 tests prove the behaviour | assertions on tool-specific test ids, on the URL, and on the *absence* of the other tool |
| NEW-07 refusals are real errors | `test_unknown_action_is_404…`, `test_unauthorized_action_is_403…`, `test_empty_message_is_400`, `test_bad_attachment_is_400` |
| NEW-07 no internal ids in bodies | `test_internal_ids_are_not_in_response_bodies` |
| NEW-14 present or absent | **cannot be determined from here** — three read-only attempts denied, recorded as such |
| F-1 attendance date | `AttendanceRecorderDate.test.js`, fails-before / passes-after |

## Final counts

- Backend suite: **2012 passed / 0 failed / 14 deselected**
- Frontend: **286 passed / 0 failed / 32 suites**
- Production build: clean, **0** `react-hooks/exhaustive-deps`, gate at error
- Evals (structural + judge-logic): **18 passed / 1 deselected**

## scoped_filter / scoped_query audit

Re-run on every backend file touched in this block (`chat.py`, `fees.py`, `issues.py`,
`settings.py`). The diff introduces **no new `scoped_filter(` hits**; the four projection
changes reuse the existing scoped query in place. The standing backlog is unchanged and
remains D-17 / D-58.

## AI-layer eval gate

`routes/chat.py` was touched (the refusal shapes), so the gate applies. Structural and
judge-logic evals: green. The credentialed LLM-judge tier remains blocked on T9.
