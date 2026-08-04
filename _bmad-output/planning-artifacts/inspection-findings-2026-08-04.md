# Platform Inspection — Findings Register (2026-08-04)

Source: read-only inspection of `main` @ `d5a93d9` covering the backend, the frontend and the
AI layer. Report: `https://claude.ai/code/artifact/d43debb3-779b-4068-bc3e-7988e78a1541`

This file is the **single source of truth for what remains to be done**. The executing agent
updates the Status column here at the end of every task. Nothing lives only in a chat transcript.

Numbering is `NEW-nn` so it never collides with the existing `D-nn` defect log in
`_bmad-output/implementation-artifacts/ui-sweep/DEFERRED-AND-DISCOVERIES.md`.

---

## Execution order (deterministic — do NOT reorder)

Blocks of five. A run = one block. See
`_bmad-output/INSPECTION-REMEDIATION-PROTOCOL-2026-08-04.md` for the process and the fixed
handoff prompt.

| # | Task | Finding | Status |
|---|------|---------|--------|
| **BLOCK 1 — make it correct, make the safety net trustworthy** ||||
| T1 | Certificate/ID-card permission decision + implement | NEW-01 | ✅ Done (2026-08-04) |
| T2 | Return the backend suite to zero failures | NEW-02 | ✅ Done (2026-08-04) |
| T3 | Route the 113 bypassing calls through the refreshing wrapper | NEW-03 | ✅ Done (2026-08-04) |
| T4 | One shared server-address definition; fix the 7 missed files | NEW-08 | ✅ Done (2026-08-04) |
| T5 | Remove or correct the two dead fee-discount helpers | NEW-11 | ✅ Done (2026-08-04) |
| **BLOCK 2 — correctness under real data volume, and cost** ||||
| T6 | Stop silent truncation at 500 rows | NEW-05 | ⬜ Not started |
| T7 | Remove the 53 one-query-per-row loops (AI layer first) | NEW-04 | ⬜ Not started |
| T8 | Cut the per-message AI cost | NEW-12 | ⬜ Not started |
| T9 | Establish a real AI answer-quality baseline | NEW-13 | ⬜ Not started |
| T10 | Run the write-rollback safety tests once, for real | NEW-06 | ⬜ Not started |
| **BLOCK 3 — hygiene and standing risk** ||||
| T11 | Clear the 48 warnings and turn the build gate on | NEW-09 | ⬜ Not started |
| T12 | Repair the tool-routing tests | NEW-10 | ⬜ Not started |
| T13 | Error shape + internal-id exclusions | NEW-07 | ⬜ Not started |
| T14 | Remove the standing AWS permission | NEW-14 | ⬜ Not started |

Status values: `⬜ Not started` · `🔵 In progress` · `✅ Done (date)` · `⏸ Blocked on owner (reason)` · `❌ Dropped (reason)`

---

## BLOCK 1 — CLOSED 2026-08-04

Branch `inspection-remediation-2026-08-04`, **not merged to main**.
Logs: `_bmad-output/implementation-artifacts/inspection-2026-08-04/block-1-completed.md`
and `block-1-review.md`.

**Gate at close:** backend **1991 passed / 0 failed / 14 deselected**; frontend
**282 passed / 2 failed** (both `LayoutRouting.test.js`, pre-existing, owned by T12);
production build compiles with the same 48 warnings as before (T11 owns those).

**Outcomes worth carrying forward:**
- T1's decision: **Owner + Principal only.** Abhimanyu will name **one additional office
  position** later; until he does, the menus still offer these tools more widely than the
  server allows (logged as D-49).
- T4's open question is answered: the deployed `REACT_APP_BACKEND_URL` **is already https**,
  so the 7 files missing the http→https upgrade were never breaking anything live.
- The real count for T3 was **178 calls across 21 files**, not 113 across 18 — the register
  counted only the tool directory.
- Three defects were found and fixed inside the block: a stale Confirm button would have
  signed the person out (`confirm_tokens.py` answered 401 where 403 was correct); the live
  notification stream reconnected forever with a dead token instead of renewing it; and a
  refused certificate/ID-card download failed **silently**, which T1 made reachable.
- New discoveries **D-47…D-53** are in `ui-sweep/DEFERRED-AND-DISCOVERIES.md`. The one worth
  reading first is **D-52**: the register framed NEW-02 as "a test went stale", but the test
  did its job — a red suite was merged and deployed anyway and stayed red for ten days.
  Nothing blocks that today, so it will happen again somewhere else.

### T1 · NEW-01 — Certificate and ID-card issuance was widened without a decision
**Severity:** high · **Type:** permissions · **Needs owner input: YES, before any code**

`backend/routes/image_gen.py:398` (`POST /api/image-gen/certificate`) and `:457`
(`POST /api/image-gen/id-cards`) were changed on 2026-07-25 (commit `1011034`, Shubham) from
`Depends(require_owner_or_principal)` to `Depends(require_role("admin", "owner"))`.

That widens issuance from 2 profiles to Owner plus **all 8 admin sub-categories** listed in
`backend/middleware/auth.py:89` — `principal, accountant, transport_head, receptionist,
it_tech, maintenance, management, support_staff`.

The commit's stated reasoning (R9.5 resolves student identity from the database, so contents
cannot be forged) is correct but addresses forgery of content, not authority to issue an
official document. The authority change was not raised with the Owner.

**Do:** ask Abhimanyu which it should be, in plain English, BEFORE editing. Then either
(a) revert both routes to `require_owner_or_principal`, or (b) keep the wider gate and update
the test in T2 to encode the new rule. Whichever way, add a comment recording the decision and
its date so a future reader does not "correct" it back.

---

### T2 · NEW-02 — The backend suite has been red since 2026-07-25
**Severity:** high · **Type:** safety net · **Depends on: T1**

`tests/backend/unit/test_image_gen_persistence.py::test_certificate_denied_for_non_principal_admin`
asserts 403 and receives 200. It **fails in isolation**, so it is NOT the order-dependent D-03
class — do not diagnose it that way.

Current measured baseline on `main`: **1967 passed / 1 failed / 14 deselected.**
The recorded note "1968 passed / 0 failed" was true on 2026-07-23 and went stale four days later.

> **CLOSED 2026-08-04 — the baseline is 0 failures again.** T1 restored the contract, so the
> test passes without being weakened. The ID-card route had **no** permission test at all,
> which is why half the widening was invisible; both routes now have refusal tests derived
> from `SUB_CATEGORIES_BY_ROLE` plus owner/principal allow tests and the two 401 tests.
> Stale counts corrected in `CLAUDE.md` and `ui-sweep/DEFERRED-AND-DISCOVERIES.md`;
> `AGENTS.md` still carries its own stale line and is logged as D-51.

**Do:** whichever way T1 is decided, the suite returns to **0 failures**. If T1 keeps the wider
gate, rewrite the test to assert the new contract (do not delete it) and add a companion test
proving the roles that are still refused. Then correct the baseline everywhere it is recorded.

---

### T3 · NEW-03 — 113 calls across 18 screens cannot survive an expired login
**Severity:** high · **Type:** frontend sessions · **This is the highest day-to-day-value task**

Access tokens last 60 minutes (`backend/middleware/auth.py:75`). Renewal happens only on app
load or when a 401 passes through `apiFetch` (`frontend/src/lib/api.js:39`), which refreshes and
retries. **113 calls in 18 component files use a bare `fetch` instead**, so they never trigger
the refresh. Zero of them handle a 401 themselves (verified: no occurrence of `401` anywhere in
`frontend/src/components/tools/`).

Worst files: `AdminTools.js` (33), `TeacherTools.js` (18), `OwnerTools.js` (14),
`MaintenanceTools.js` (12), `IncidentTracker.js` (6), `PrincipalDailyOps.js` (6),
`QuerySection.js` (5), `StudentTools.js` (5), `TimetableBuilder.js` (4), plus
`ChatInterface`, `ConfirmActionCard`, `Header`, `SettingsModal`, `AttendanceRecorder`,
`AuditLog`, `FeeSync`, `FileUpload`, `FeeCollection`.

This is the exact bug class as **D-43** (chat upload, fixed 2026-07-23 by routing one call
through `apiFetch`). The same flaw remains in 113 other places.

**Do:** route every one through the shared refreshing wrapper. Export `apiFetch` from
`lib/api.js` and use it; do not write a second copy. Add a test that an expired token on a tool
screen refreshes and retries rather than surfacing an error.

---

### T4 · NEW-08 — One server address, not 25 copies
**Severity:** medium · **Type:** frontend architecture · **Same root cause as T3 — do them together**

25 files each declare their own `process.env.REACT_APP_BACKEND_URL` base
(`grep -rl "REACT_APP_BACKEND_URL" frontend/src/`). That is why commit `80d803b`
("Fix mixed-content fetch errors on CloudFront", 2026-07-25) reached 13 tool files and **missed 7**:

`contexts/UserContext.js` (login and token refresh) · `components/ChatInterface.js` ·
`components/InputBar.js` · `components/Header.js` · `components/ConfirmActionCard.js` ·
`components/SettingsModal.js` · `components/NotificationDetailModal.js`

Those 7 still use the bare `process.env.REACT_APP_BACKEND_URL + '/api'` with no http→https
upgrade. Live impact depends on whether the deployed `REACT_APP_BACKEND_URL` is already https —
**check the Amplify console before assuming either way**, and report which it is.

> **ANSWERED 2026-08-04 — it is already https, so the live impact was NIL.** Read
> read-only from the Amplify app's own configuration (no school data touched):
> `REACT_APP_BACKEND_URL = https://dapbq24rsje5g.cloudfront.net` and
> `REACT_APP_UPLOAD_URL` is the same value. The 7 files that lacked the upgrade were
> therefore never producing a blocked request. The consolidation removes the trap; it did
> not close an outage, and must not be reported as one.

**Do:** a single exported base (and `apiFetch`) in `lib/api.js`; every file imports it. Delete the
24 local copies. Add a test or lint rule that fails if `REACT_APP_BACKEND_URL` is read anywhere
except `lib/api.js` and `setupProxy.js`.

---

### T5 · NEW-11 — Two dead fee-discount helpers
**Severity:** low · **Type:** dead link · **Small; finishes the block**

`frontend/src/lib/api.js:576` `approveFeeDiscount` and `:583` `rejectFeeDiscount` call
`POST /api/fees/discounts/{id}/approve|reject`. The server only serves
`PATCH /api/fees/discounts/pending-approvals/{approval_id}/approve|reject`
(`backend/routes/fees.py:603`, `:626`). Wrong path **and** wrong method.

Nothing is broken today: the live screen (`FeeCollection.js:156,166`) calls the correct address
directly. These two exports are unused leftovers that look ready to use.

**Do:** delete them, or correct them to match the server. Prefer deletion unless a caller is
planned. Verified by the full app-to-server audit: these are the only two mismatches out of 192
client paths against 274 server routes.

---

## BLOCK 2

### T6 · NEW-05 — Silent truncation at 500 rows in a 1,802-student school
**Severity:** medium · **Type:** correctness under real data**

Several reads cap results with no signal that more existed. Most caps are fine (a class is never
more than ~60). Two are not:
- `backend/ai/tool_functions_v2.py:372` — student search, `.to_list(500)`, reachable with no
  class filter, so it can silently answer for 500 of 1,802.
- `backend/ai/tool_functions_v2.py:1028` — house members, `.to_list(500)`; four houses across
  1,802 students puts each right at the edge.

The correct pattern already exists in this codebase: `backend/routes/sms.py:146` refuses above
500 with a clear message rather than quietly sending fewer.

**Do:** either raise the ceiling above the school's real size or return a `total` /
`showing_first` marker so Flo can say "500 of 1,802". Silence is the only unacceptable option.
Audit the other 32 sub-1802 caps found and annotate the legitimately-scoped ones so the next
audit does not re-derive them.

---

### T7 · NEW-04 — 53 one-query-per-row loops
**Severity:** medium · **Type:** performance · **AI layer first — those run while a person waits**

Database calls made inside a `for`/`while` body, which CLAUDE.md explicitly forbids
("N+1 queries: batch with `{"id": {"$in": [...]}}` + build a dict, never loop queries").

By file: `routes/academics.py` 16 · `ai/tool_functions.py` 9 · `ai/tool_functions_v2.py` 9 ·
`routes/attendance.py` 6 · `routes/import_data.py` 3 · `ai/context_builder.py` 2 ·
`routes/operations.py` 2 · `routes/sms.py` 2 · `routes/fees.py` 1 · `routes/payroll.py` 1 ·
`routes/search.py` 1 · `services/fee_sync_service.py` 1.

Clearest example: `ai/tool_functions_v2.py:376` looks up `db.classes.find_one` once per student
inside the 500-row search from T6 — up to **501 round trips for one question**.

**Do:** batch each with `{"id": {"$in": [...]}}` into a dict. Start with the AI layer. Add a
regression check (a fake collection that counts calls) on at least the student-search path.

---

### T8 · NEW-12 — Every owner message costs ~43,000 tokens before the question
**Severity:** medium · **Type:** cost · **Needs owner input on the second half**

Measured on `main`:

| Role | Tools sent | System prompt | Per model call |
|---|---|---|---|
| owner | 107 | ~9,538 | **~21,513** |
| admin/principal | 84 | ~5,518 | ~14,962 |
| admin/accountant | 34 | ~5,518 | ~8,320 |
| teacher | 18 | ~4,462 | ~6,206 |
| student | 11 | ~4,528 | ~5,196 |

And a normal turn makes **two** model calls: Phase 8 works out the answer
(`backend/routes/chat.py:2338`), Phase 13a re-synthesises the same answer purely so it can stream
word by word (`chat.py:2660`, `_stream_final_answer` at `:1672`). So an owner turn is ~43,000
input tokens before any real work.

Two independent savings:
1. **Trim the owner/principal tool lists** to what people actually ask for in chat. Shubham's
   `local_testing` branch already sketches this as `EXCLUDE_FOR_ROLE` in `ai/tool_role_config.py`
   — reuse the idea, do not merge that branch to get it.
2. **Drop the second call.** Halves the rest; the cost is that answers appear at once instead of
   typing out. **Ask Abhimanyu** — it is a visible product change. Shubham's branch gates this
   behind `AI_STREAM_SECOND_CALL` defaulting off, which is a good shape.

**Do:** implement (1). Ask about (2), and if approved implement it as an env-var switch, not a
deletion. Prompt/tool change ⇒ the eval gate applies (see the protocol's guardrails).

---

### T9 · NEW-13 — No baseline for AI answer quality
**Severity:** medium · **Type:** AI quality · **May need Azure credentials**

`tests/backend/evals/scores-baseline.json` does not exist, so
`test_eval_llm_judge.py` writes a fresh baseline and passes (`:61`). There is nothing to regress
against. The last credentialed run used `gpt-5.6-terra`, not production `gpt-5.3-chat`, which is
why the baseline was deliberately not committed (documented in D-37).

Known coverage gap, also from D-37: no conversation in the 52-item corpus exercises
`draft_document` and the download link, which is one of Flo's most-used abilities.

**Do:** add a `draft_document` conversation to the corpus. Then run
`pytest -m llm_eval tests/backend/evals` against the **production** deployment and commit the
resulting baseline. If the production deployment is not reachable from this machine, say so
plainly and mark T9 `⏸ Blocked on owner` rather than committing a substitute-model baseline.

---

### T10 · NEW-06 — The write-rollback safety tests have never run
**Severity:** medium · **Type:** untested · **Needs a real MongoDB replica set**

14 tests under `tests/backend/mongo_real/` are deselected on every run. They cover transaction
rollback, executor rollback, idempotency under concurrency, precondition checks, atomic
plan-from-steps, and cross-tenant transaction scoping — the protections that matter when Flo
writes to live student and fee records. They have never passed and never failed.

**Do:** stand up a local MongoDB replica set (they need transactions, so a single node with a
replica-set name is enough), run the tier once, and record the result in the review log. If any
fail, that is a finding of its own and goes in the register. Document the exact command so the
next person can repeat it in one line.

---

## BLOCK 3

### T11 · NEW-09 — 48 warnings, and no gate
**Severity:** medium · **Type:** build hygiene · **Supersedes D-16 (which estimated ~30)**

`CI=true npx craco build` fails with **48** `react-hooks/exhaustive-deps` warnings. Because there
are already so many, the strict build cannot be used as a gate, so the count only grows. These
are the cause of "it shows old data until I refresh" behaviour.

**Do:** clear them properly (usually wrapping the fetcher in `useCallback` and listing it, not
silencing the rule). Where a deps-passthrough is intentional, use a scoped
`// eslint-disable-next-line` **with a comment saying why** — the pattern already set at
`ToolPage.js:398`. Then turn the gate on so it never regrows. This must be its own change; do not
bury it inside another task's diff.

---

### T12 · NEW-10 — The tool-routing tests crash on render
**Severity:** medium · **Type:** untested**

`frontend/src/components/__tests__/LayoutRouting.test.js` — both tests fail with an
`AggregateError` at `render()`, meaning the component throws before anything is asserted. They
guard "a link opens the right tool" and "switching tools updates the address bar". Recorded for
weeks as "2 pre-existing failures", which is accurate and has become an excuse.

**Do:** fix the harness (likely a missing provider or mock), get both green. This behaviour is
what D-44's deep-linking work wants to build on, so it needs to be guarded first.

---

### T13 · NEW-07 — Error shape and internal-id exclusions have drifted
**Severity:** low · **Type:** convention drift**

Two small departures from the project's own written conventions:
1. `backend/routes/chat.py:2925` returns HTTP 200 with `{"success": False, "error": "Forbidden"}`
   when an AI action button is not permitted. The action **is** correctly blocked, so this is not
   a hole, but it will not register in any monitoring that counts rejected requests. CLAUDE.md:
   "Errors — ALWAYS raise HTTPException, never return raw dicts." Same file `:2922` and `:2883`.
2. 48 database reads across the route files do not pass `{"_id": 0}`. Mostly harmless (many
   reshape the result first), but it is the documented rule and it has slipped.

**Do:** convert the refusals to proper `HTTPException`s, checking the frontend callers handle the
status change. Add `{"_id": 0}` where the result can reach a response body.

---

### T14 · NEW-14 — Standing AWS permission that is no longer needed
**Severity:** medium · **Type:** standing risk · **OWNER ACTION — the agent cannot do this**

Verified good news: no key has ever been committed to git history. The root `.env` holds two live
AWS key pairs, but it is correctly ignored and absent from history.

The open risk is D-34: the `claude-hosting` IAM user still holds `iam:PutRolePolicy` on
`aws-elasticbeanstalk-ec2-role`. That lets whoever holds those keys rewrite what the production
servers may do. It was needed once for a July setup job that is finished.

Removing it breaks nothing: the running application authenticates as the EC2 instance role, and
`EduFlowFileStorage` on that role is what serves files. The agent **cannot** remove it —
`iam:DeleteUserPolicy` is denied to that principal by design.

**Do:** the agent's job is only to (a) confirm the permission is still present if it has read
access, and (b) put the exact click-path in front of Abhimanyu:
IAM → Users → `claude-hosting` → Permissions → `s3-file-storage-policy` → Remove.
Mark `⏸ Blocked on owner` until he confirms it is done.

---

## Carried forward, NOT in these blocks

Already in `_bmad-output/implementation-artifacts/ui-sweep/DEFERRED-AND-DISCOVERIES.md` and
re-confirmed still true on 2026-08-04. Listed so nobody re-raises them as new:

`D-21` school's own address/phone/email/principal still placeholder ·
`D-33` file writing, photo reading and image understanding live but never verified ·
`D-29` expense export is school-wide while its neighbours are branch-scoped ·
`D-36` duplicate notifications index · `D-24` ~22 tables still without column sorting ·
`D-25` two dispatch paths into one tool registry · `D-41` telemetry ingest failing ·
`D-46` WAF size rule in Count mode (deliberate, owner's call) ·
`D-44` Directory deep-link and deeper tool consolidation ·
`D-06`–`D-10` data-load gaps · `D-30`/`D-31` scanned PDFs and on-demand vision ·
`D-32` stall thresholds never measured on the school's connection.
