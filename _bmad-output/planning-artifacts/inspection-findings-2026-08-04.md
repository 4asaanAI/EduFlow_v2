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
| T6 | Stop silent truncation at 500 rows | NEW-05 | ✅ Done (2026-08-04) |
| T7 | Remove the 53 one-query-per-row loops (AI layer first) | NEW-04 | ✅ Done (2026-08-04) |
| T8 | Cut the per-message AI cost | NEW-12 | ✅ Done (2026-08-04) |
| T9 | Establish a real AI answer-quality baseline | NEW-13 | ⏸ Blocked on owner (no Azure OpenAI credentials on this machine) |
| T10 | Run the write-rollback safety tests once, for real | NEW-06 | ✅ Done (2026-08-04) |
| **BLOCK 3 — hygiene and standing risk** ||||
| T11 | Clear the 48 warnings and turn the build gate on | NEW-09 | ✅ Done (2026-08-04) |
| T12 | Repair the tool-routing tests | NEW-10 | ✅ Done (2026-08-04) |
| T13 | Error shape + internal-id exclusions | NEW-07 | ✅ Done (2026-08-04) |
| T14 | Remove the standing AWS permission | NEW-14 | ⏸ Blocked on owner (only Abhimanyu can remove it; agent cannot even read it) |

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

> **✅ DONE 2026-08-04.** The cap stays at 500 (a bigger page would just spend the token
> budget the sibling task T8 is cutting); what changed is that it can no longer be silent.
> `_find_capped()` in `ai/tool_functions_v2.py` fetches `limit + 1` rows so it knows more
> existed, then counts ONLY in that case, and `_ok(..., total=)` puts `total`,
> `showing_first` and `truncated` in the tool result plus a plain sentence Flo can relay.
> Applied to the two named reads and to three more found in the audit that can genuinely
> pass 500 in this school: a teacher's own roster, the same roster feeding the overdue-books
> check, and school-wide fee transactions. `member_count` on a house is now the true roll,
> not the page size (it was understating). A fixed `.to_list(20)` on a teacher's class-name
> lookup was replaced with the number of ids actually asked for. Caps that cannot reach
> 1,802 (staff at ~90, one class at ~60) are left alone with a note. Regression tests:
> `tests/backend/unit/test_inspection_block2_scale.py`.

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

> **✅ DONE 2026-08-04.** A repeatable detector (walk the file, track `for`/`while` bodies,
> flag any `await db.*.find*` inside one) found **27** live sites, not 53 — the register's
> count was per-statement across both AI tool files and double-counted. All 27 were worked:
> AI layer first (`tool_functions.py`, `tool_functions_v2.py`, `context_builder.py`), then
> `academics.py`, `attendance.py`, `fees.py`, `operations.py`, `payroll.py`, `search.py`,
> `sms.py`, `import_data.py`. Worst cases removed: the 501-round-trip student search; a
> late-arrival check that ran 5 queries per staff member (~450 for one question); a
> substitution planner running 3 queries per timetable slot; a class fee summary running
> 2 queries per class; the SMS send doing 2 lookups per recipient (up to 1,000 per send);
> and the context builder doing 16 counts on every single message. Two remaining sites are
> deliberately NOT batched and now carry a comment saying why: both are the read-before-write
> of an upsert loop, which must see rows written earlier in the same run. Detector re-run at
> block close reports those two and nothing else. Regression guard: a call-counting fake
> collection asserts the student search issues exactly one class read for 300 students, and
> none at all when no student has a class.

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

> **✅ DONE 2026-08-04 — both halves, (2) with the owner's explicit approval this session.**
>
> (1) `ai/tool_chat_exclusions.py` holds `EXCLUDE_FOR_ROLE` and is consulted ONLY where the
> chat tool list is built (`_build_llm_tools`, and only when no tool is named explicitly).
> It changes what is OFFERED, never what is ALLOWED: `ai/tool_access.is_tool_authorized`
> is untouched and is still the only thing consulted at dispatch, so an excluded tool is
> still permitted, still reachable from the tool panel and from a suggested action. 26
> structural configuration tools are trimmed (branches, classes, houses, fee structures,
> discount types, asset and transport registers, school settings, year-end transition,
> list-screen deletes) for owner and principal only. Owner: **107 → 81 tools**, the tools
> block drops from ~11,700 to ~8,750 tokens. Everyday work (record a payment, mark
> attendance, apply a discount, create a student, draft a document) is explicitly asserted
> to stay. Every other role is untouched, asserted by test.
>
> (2) **Abhimanyu approved turning the typing-out effect off** (asked in plain English,
> answered "Turn typing-out off"). Implemented as `AI_STREAM_SECOND_CALL`, defaulting
> **off**; set it to `true` in the environment to restore the effect with no code change.
> The R11.3 streaming contract test now switches it on explicitly rather than being
> weakened, and a new test asserts that at the default NO second model call is made and the
> answer still arrives and is still saved. Combined with (1), an owner turn drops from
> ~43,000 input tokens to roughly ~17,000.
>
> Structural + judge-logic evals green (the AI layer was touched).

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

> **⏸ BLOCKED ON OWNER 2026-08-04 — the corpus half is done, the credentialed run is not.**
> The coverage gap is closed: three `draft_document` conversations were added to the corpus
> (owner letter, principal circular, Hinglish teacher note), each with a rubric that
> explicitly requires the **download link** to be present, since a document with no way to
> fetch it is the exact D-37 failure. Corpus is now **55** conversations; the structural and
> judge-logic evals are green with them in.
>
> The credentialed run could NOT be done: this machine has no Azure OpenAI endpoint or key
> (checked `.env` and `backend/.env` — neither carries one), so `pytest -m llm_eval` has
> nothing to call. Per the register's own instruction, no substitute-model baseline was
> committed. **What is needed from Abhimanyu:** the production Azure OpenAI endpoint and key
> for the `gpt-5.3-chat` deployment, or a machine that already has them. The run then costs
> 55 model calls plus judging, once.

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

> **✅ DONE 2026-08-04 — and the first run found a defect of its own.**
> The tier collects **13** tests, not 14. On the first attempt every one of them ERRORED
> before a single assertion ran: `mongo_real/conftest.py` created the Motor client in a
> module-scoped async fixture and handed it to function-scoped tests, and Motor binds to
> the loop it was created on ("attached to a different loop"). That is precisely why the
> tier had never passed *or* failed — it was un-runnable, and being deselected by default
> meant nobody found out. Fixed by splitting the fixture (URL + container lifecycle stay
> module-scoped; the client is created per test). **Result: 13 passed** — transaction
> commit/rollback, executor rollback, idempotency under concurrency, precondition
> revalidation, atomic multi-step plans, dry-run persisting nothing, cross-tenant
> transaction scoping.
>
> Environment gotcha worth keeping: MongoDB **8.3** (the winget package) will not start on
> this Windows 10 build — `STATUS_ENTRYPOINT_NOT_FOUND`, no log, and the installed service
> cannot start either. MongoDB **7.0.16** from the fastdl zip works. The exact one-line
> repeat command is at the top of `tests/backend/mongo_real/README.md`.

---

## BLOCK 3 — CLOSED 2026-08-04

Branch `inspection-remediation-2026-08-04`, **not merged to main**.
Logs: `_bmad-output/implementation-artifacts/inspection-2026-08-04/block-3-completed.md`
and `block-3-review.md`.

**Gate at close:** backend **2012 passed / 0 failed / 14 deselected**; frontend
**286 passed / 0 failed** (the suite is fully green for the first time); production build
**compiles clean with 0 warnings** and the gate set to error, demonstrated to fail on a
reintroduced violation; evals **18 passed**; no new `scoped_filter(` hits.

**Outcomes worth carrying forward:**
- **A live defect was found while clearing the warnings** and is the single most important
  thing in this block: the attendance register never showed what had already been marked,
  on any date including today, because the screen asked the server a malformed question.
  Logged as **D-61**, fixed, and guarded by a test confirmed to fail on the old code.
- T12's real cause was **D-48**, exactly as suspected. Two of the two failing assertions
  were also looking for text that does not exist anywhere in the app, so those tests could
  never have passed. Eight other test files carry the same trap and are logged as **D-60**.
- T13's "48 reads" was re-measured: **52** reads lack the projection, but only **4** reach
  a response body. Blanket-adding the rest would have been churn, and one of them would
  have broken outright.
- **T14 could not even be read.** Three read-only attempts were all denied. "Cannot
  confirm" is recorded rather than a guess in either direction.
- New discoveries **D-59…D-63**. The one to read first is **D-59**: a link straight to a
  screen does not survive a fresh browser tab, which is exactly what D-44's deep-linking
  work intends to build on, so it needs deciding before that work starts.

## Task detail

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

> **✅ DONE 2026-08-04. 48 → 0, and NOT ONE scoped eslint-disable was added** — every
> warning had a real fix. The single pre-existing disable at `ToolPage.js` (`useToolData`)
> was left alone and is now cited in the config as the reference pattern.
>
> 20 sites got the proper `useCallback` treatment; 24 were a genuinely stable dependency
> (almost all `currentUser`, which is context **state**, so it cannot loop and its absence
> was why some screens showed the previous person's data); 4 needed real thought:
> - The sidebar conversation menu was re-registering a document listener on every render
>   once `onClose` was listed. Held in a ref instead.
> - The sidebar's auto-open-group effect **would genuinely have looped** (sets state →
>   re-render → new config object → effect again). It is safe only because
>   `getGroupConfig()` returns a reference into a module-level constant. Verified, not
>   assumed.
> - `DataTable`'s `safeRows` re-sorted the whole table on every render because its `: []`
>   branch minted a new array each time.
>
> **The gate:** `react-hooks/exhaustive-deps` is now **`"error"` on the production build**
> and stays `"warn"` under `craco start`. Run it with `cd frontend && npx craco build`.
> There is no CI workflow in this repo, so the build command IS the gate. **Proven**: a
> dependency was deliberately removed again, the build printed `Failed to compile.` naming
> the rule, then it was restored and the build went clean.
>
> **A live defect was found on the way and fixed** (F-1 in `block-3-review.md`): the
> Attendance Recorder was passing the signed-in user where the date belongs, so it asked
> the server for `?date=[object Object]`, matched nothing, and showed **every child as
> "not marked" regardless of what had actually been recorded** — on today's date as much
> as any other. Someone could have re-marked over a register that was already taken.
> Guarded by `AttendanceRecorderDate.test.js`, confirmed to fail on the old code.
> This supersedes **D-16**.

---

### T12 · NEW-10 — The tool-routing tests crash on render
**Severity:** medium · **Type:** untested**

`frontend/src/components/__tests__/LayoutRouting.test.js` — both tests fail with an
`AggregateError` at `render()`, meaning the component throws before anything is asserted. They
guard "a link opens the right tool" and "switching tools updates the address bar". Recorded for
weeks as "2 pre-existing failures", which is accurate and has become an excuse.

**Do:** fix the harness (likely a missing provider or mock), get both green. This behaviour is
what D-44's deep-linking work wants to build on, so it needs to be guarded first.

> **✅ DONE 2026-08-04. Frontend suite is now fully green: 284 passed / 0 failed**, stable
> across three runs including a serial one.
>
> The `AggregateError` was React swallowing the real error thrown inside a mount effect.
> Unwrapped, it was `getMyTokenUsage is not a function` and
> `getUnreadNotificationCount is not a function` — **exactly D-48**. The test mocked
> `lib/api` with an explicit factory listing 8 functions; the real module exports **123**,
> and the shell calls about fifteen of them. Every unlisted name was `undefined`, so the
> first effect to fire blew up before any assertion ran.
>
> Two traps underneath it, both worth knowing before anyone touches the other eight files
> carrying the same stub:
> 1. Create React App's Jest preset sets **`resetMocks: true`**, which strips the
>    implementation off every `jest.fn()` before each test. So `jest.fn(async () => …)`
>    returns `undefined`, not a promise, and the obvious fix fails confusingly. The stubs
>    must be plain functions.
> 2. **Two of the old assertions were simply wrong.** They looked for the text
>    "Attendance Recorder" and a header matching `/Tools \(/`; neither string exists
>    anywhere in the app. These tests could never have passed even with a working harness.
>    They were stale, not merely broken.
>
> The mock is now derived from the real module's export list, so a new API helper can never
> silently break this suite again. Assertions were strengthened, not just repaired: test 1
> proves the URL-named tool mounted, is not the spinner or the error boundary, that a
> different tool is NOT showing, and that the URL was not rewritten; test 2 proves the
> address bar gains `tool=fee-sync`, loses the old one, and that the panel actually swapped.
> Only the test file changed — no application code, no configuration.
>
> **One real application defect found and deliberately NOT fixed** (logged as D-59):
> deep links do not survive a cold browser tab. This is precisely what D-44 wants to build
> on, so it must be decided before that work starts.

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

> **✅ DONE 2026-08-04.** Four refusals converted, and the frontend was updated in the same
> change so nobody loses a message they used to see:
> - unknown action → **404** with the action name (was 200 + `{"success": False}`)
> - action not permitted → **403** "You do not have permission to run this action."
> - empty message → **400** (this one mattered: the browser used to receive a 200 and try
>   to read it as a live stream, which produced a silent turn)
> - rejected image attachment → **400**
>
> Frontend: `ChatInterface.executeAction` now normalises both shapes so the person still
> sees the real reason instead of a generic "Action failed", and `sendMessageStream` pulls
> the sentence out of `{"detail": ...}` instead of throwing raw JSON at the user.
>
> Second half: the "48 reads without `{"_id": 0}`" figure was re-measured properly (the
> naive grep over-counts, because the projection is often on the next line). The real
> number is **52** reads without the exclusion, and of those only **4** actually reach a
> response body: a student's own fee transactions, the pending-discount approvals list, a
> single facility request, and the token-usage records. Those four are fixed. The other 48
> are internal lookups whose fields are copied into a hand-built response, or need `_id`
> (`image_gen` quota increments by it), or are write-path re-reads. Blanket-adding a
> projection to those would have been churn with a real chance of breaking something, so
> it was not done. Tests: `tests/backend/api/test_inspection_block3_error_shape.py`.

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

> **⏸ BLOCKED ON OWNER 2026-08-04.** Part (a) could NOT be completed and this is worth
> recording rather than glossing: the permission cannot be *read* either. Three read-only
> attempts were made and all three were denied — `iam:ListUserPolicies` as the `Claude`
> user, `iam:GetUserPolicy` as `claude-hosting` itself, and `iam:SimulatePrincipalPolicy`
> as a last resort. So the agent can neither confirm nor deny that the permission is still
> attached, and D-34's original finding stands unchanged as the last known state.
>
> Part (b) is done — the click path is in front of Abhimanyu, in the human checklist:
> **IAM → Users → `claude-hosting` → Permissions → `s3-file-storage-policy` → Remove.**
> Removing it breaks nothing: the running app authenticates as the EC2 instance role, and
> `EduFlowFileStorage` on that role is what serves files. Stays blocked until he confirms.

---

## Carried forward, NOT in these blocks

Already in `_bmad-output/implementation-artifacts/ui-sweep/DEFERRED-AND-DISCOVERIES.md` and
re-confirmed still true on 2026-08-04. Listed so nobody re-raises them as new:

**Re-verified against the code on 2026-08-04, not copied forward.** Three that this list
still carried as open are in fact **CLOSED** and must not be re-raised: `D-21` (the school's
own address/phone/email/principal — the code half shipped in Epic 4 and Abhimanyu confirmed
the stored record was updated), `D-24` (column sorting — 20 hand-rolled tables done, guarded
by `SortableHandRolledTables.test.js`; the Timetable grid is deliberately not sortable), and
`D-36` (the duplicate notifications index — `database.py` now declares it once).

**Second reconciliation, 2026-08-04 (end of day).** Ten more that this list or the defect
log still carried as open were in fact closed by the owner-decisions round and the tidy-up
sweep, verified against the code, not taken from a commit message: `D-05`, `D-17`, `D-48`,
`D-49`, `D-50`, `D-51`, `D-58`, `D-59`, `D-60`, `D-62`, `D-63`, `D-64`. Their headings in
`DEFERRED-AND-DISCOVERIES.md` now say so. **`D-59` closing means `D-44`'s deep-link work is
no longer blocked.**

### Genuinely still open — the whole list, in one place

Nothing else is open. Everything here needs either a decision from Abhimanyu, a credential
this machine does not have, or real-world use to settle it. **No item below can be closed by
an agent working alone**, which is why they are still here.

**Waiting on a decision from Abhimanyu**
- `D-29` expense export is school-wide while its neighbours are branch-scoped. Narrowing it
  changes what an accountant can see. Annotated in place. No effect while there is one branch.
- `D-46` the WAF size rule is in Count mode across the board. Deliberate, his call to flip.
- `D-47` four uploads use the ordinary server address and one uses a separate upload address.
  Both point at the same place today, so nothing is broken; the choice is to delete the second
  address or route all five through it.
- `D-53` certificates and ID cards have no branch scoping. No effect today, one branch.
- `D-57` Flo no longer volunteers 26 setup jobs in chat. Permissions unchanged. One question:
  does anyone actually want to create a fee structure by talking to Flo?
- `D-64` follow-up: existing server and CloudFront logs still contain the URLs that carried
  personal details. Whether to purge them is an operations decision.
- `T14`/`D-34` remove `iam:PutRolePolicy` from the `claude-hosting` AWS user. The agent cannot
  read it, let alone remove it.

**Waiting on a credential or a real environment**
- `T9`/`NEW-13` the AI answer-quality baseline needs the production Azure OpenAI key. The
  corpus half is done (55 conversations, three of them `draft_document`); only the
  credentialed run is left.
- `D-33` writing a file as the server, reading a photo, and whether the model accepts images
  at all: three things that are live and unproven. All three need someone to try them.
- `D-30`/`D-31` scanned PDFs and calling the vision fallback on demand.
- `D-41` backend telemetry ingest failing in production.
- `D-32` the "taking longer than usual" thresholds were reasoned, never measured on the
  school's connection on a real morning.

**Bigger pieces of work** *(three of the four were done later the same day — see below)*
- ~~`D-25` two doors into one tool registry~~ **DONE.** One `invoke_tool()`; both doors call
  it; a structural test fails if a third door ever calls a tool directly.
- `D-44` **half done.** The deep link to a person works for students and staff. The tool
  **clusters** (fee, messaging, documents) still need Abhimanyu's yes/no per cluster —
  Epic 9's rule is that a wrong merge is worse than no merge.
- ~~`D-52`/`D-54`~~ **CHECK BUILT.** The suites and the production build now run on every
  pull request, and the skipped write-rollback tier runs nightly and fails if it skips.
  **One thing left, and only Abhimanyu can do it:** make the check *required* in
  Settings → Branches. Turning that on can stop his own merges, so it was not done for him.
- `D-06`–`D-10` the data-load gaps. **Not started and not startable by an agent:** every one
  of them writes to live school data, which needs explicit approval first.
