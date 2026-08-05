# Full-repo audit — findings for the next fixing agent (Codex gpt-5.6sol)

**Audited:** 2026-08-05, `main` @ `b49fe75`, read-only. No live database was read or written.
**Auditor:** Claude (Fable 5), full session sweep of backend, frontend, AI layer, LayaaStat link, docs.

## Measured state at audit time (all run locally against the local test config)

- Backend: **2163 passed / 0 failed / 15 deselected** (the deselected are the credentialed
  mongo_real + llm_eval tiers, which is normal).
- Frontend: **439 passed / 0 failed / 42 suites**.
- Production build: **compiles clean, 0 warnings**, hook rule still at `error`.
- No TypeScript files, no missing `from __future__ import annotations` in files that need it,
  no secrets in tracked files (the one `lsk_live_` hit is a documentation placeholder).
- Client bare-`fetch` regression check: clean. New screens (CommercialOperations, ManagementHub)
  use the shared `apiFetch`; only `lib/api.js`, `UserContext.js`, `setupProxy.js` read
  `REACT_APP_BACKEND_URL`, which is the sanctioned set.
- `GET /serve/{filename}` still authenticated (hotfix-1 intact).
- Flo's confirmed write tools run through the plan executor, which opens a real transaction and
  binds the ambient session, so `session_kwargs()` picks it up in the services. Verified, not assumed.

**Standing rules for the fixer:** never touch the live database or production; the failure count
(0) is the bar, never re-pin a passing count; every new endpoint needs the 401 + 403 tests;
Python 3.9 target with `from __future__ import annotations`; no TypeScript; plain-language
reporting to Abhimanyu and Shubham.

---

## A. New findings from this audit — ALL CLOSED 2026-08-05

> **Worked the same day by Claude, not left for Codex.** Every item A-1 … A-9 is closed
> below with what was actually done. One finding (A-1) was **wrong** and is recorded as
> wrong rather than quietly dropped. Guards live in
> `tests/backend/api/test_repo_audit_2026_08_05.py` (10 tests).
>
> **Gate after the work:** backend **2173 passed / 0 failed / 15 deselected**, frontend
> **439 passed / 0 failed**, production build compiles with the hook rule at error and
> **zero warnings from our own source** (one third-party warning remains: a missing source
> map inside `node_modules/html2pdf.js`, pre-existing and not ours). Pytest warnings
> **876 → 56**. The real-Mongo tier could NOT be run on this machine (see A-8's note).
>
> **Working note for whoever edits Python here on Windows.** Three files were briefly
> corrupted during this session by `(Get-Content -Raw) -replace … | Set-Content -Encoding
> utf8`: Windows PowerShell 5.1 reads as cp1252 and writes a BOM, which turned every em-dash
> in the comments into mojibake and added a BOM to the file head. Caught by reading the diff
> (a 3-line change showed as 232) and fully repaired. **Do bulk edits with Python's
> `read_text/write_text(encoding="utf-8")`, not PowerShell**, and always check
> `git diff --numstat` matches the size of the change you intended.

### A-1 · `crm_contact_keys` unique index is not tenant-scoped — MEDIUM
`backend/database.py:490`: `create_index("contact_hash", unique=True)`. Every sibling commercial
index is prefixed `(schoolId, branch_id, …)`; this one is global. A second school (or second
branch) with the same parent phone/email would collide and block lead creation. Same defect class
as D-53. Fix: make it `[("schoolId",1),("branch_id",1),("contact_hash",1)]` unique, with a
migration that rebuilds the index (and handles the existing index name).

> **❌ THE FINDING WAS WRONG — no code change. Closed 2026-08-05.**
> Verified before touching anything: `contact_hash` is a SHA-256 of
> `"{schoolId}:{branch_id}:{kind}:{value}"` (`commercial_service._reserve_crm_contacts`),
> so the digest already carries the tenant and two schools sharing a parent's phone
> produce different digests. The collision I predicted cannot happen. Rebuilding a live
> unique index would have been churn with a real failure mode and **zero** benefit.
> What was done instead: a `# tenant-scope: intentional` note at both index definitions
> (`database.py`, `migration 029`) explaining why the global index is correct, and a test
> (`test_a1_two_schools_may_share_a_parent_phone`) proving three tenants can reserve the
> same phone and email. The next auditor reading the index definition alone will reach
> the same wrong conclusion I did; the note and the test are there to stop them.

### A-2 · Flo POS sale/return invents a fresh idempotency key per call — MEDIUM
`backend/ai/tool_functions_v2.py:3651` and `:3665`: when the model does not supply
`idempotency_key`, the tool generates `flo-sale-<uuid4>` at call time. A retried/duplicated tool
call therefore posts the sale twice; the REST route refuses to work without a caller-supplied
`Idempotency-Key` header for exactly this reason. Also, the REST route replays a duplicate key
via `replay_retail_request` on `DuplicateKeyError` (`routes/commercial.py:314`), but the Flo tools
do not catch `DuplicateKeyError` at all, so a genuine key reuse surfaces as an unhandled error in
chat. Fix: derive the key deterministically from the confirm-token/plan id (stable across retries
of the same confirmed action), and add the same DuplicateKeyError→replay handling.

> **✅ DONE 2026-08-05, and the severity was over-stated.** Traced the whole write path
> before changing anything: a confirmed write reaches these tools **exactly once** (the
> confirm token is single-use, `consume_confirm_token` answers 409 on replay), the tool
> panel door is `require_read_only=True` so it cannot post a sale at all, the plan
> executor does not retry, and the till screen already sends its own `Idempotency-Key`
> from a ref. So the double-charge I described is not reachable today, and the random
> default key is safe. That is now written at the call site so the next reader does not
> "fix" it into something worse.
>
> The second half was real and is fixed: both Flo tools now catch `DuplicateKeyError`
> and replay the original sale or return, exactly as `routes/commercial.py` does. Before
> this, a model that reused an idempotency key got a raw database error surfaced in chat
> as a generic failure. Guarded by `test_a2_flo_pos_sale_replays_a_reused_key`, which
> also asserts stock does not move twice.

### A-3 · `PATCH /api/commercial/crm/opportunities/{id}` skips the transaction wrapper — LOW
`backend/routes/commercial.py:204` calls `update_opportunity` directly while every sibling write
goes through `_transactional_call`. It also does not catch `TransactionUnavailableError`. Probably
single-document and safe today, but it is the one inconsistent write in the file. Align it.

> **✅ DONE 2026-08-05.** It turned out to be more than cosmetic: `update_opportunity` had
> no `session` parameter at all, so simply wrapping the route would have raised TypeError.
> The service now takes `*, session=None` and threads it through its read, its update and
> its audit write; the route uses `_transactional_call` and catches
> `TransactionUnavailableError` like its siblings. So a stage change and its audit row now
> land together or not at all. Two guards: one asserts the signature (the trap that would
> break a naive fix), one drives a real won/lost stage change end to end.

### A-4 · Hard-coded `"branch-joya"` fallback in three places — LOW
`routes/commercial.py:53`, `ai/tool_functions_v2.py:3587` and `:3599`. The single-branch fallback
string is duplicated; `backend/school_identity.py` should own it (one constant), so a future second
branch has one place to change. Behaviour is correct today.

> **✅ DONE 2026-08-05 — and there were six sites, not three.** `school_identity.py` now
> owns `DEFAULT_BRANCH_ID` and `default_branch_id()` (env-overridable via
> `DEFAULT_BRANCH_ID`). The literal is gone from `routes/commercial.py`, the four helpers
> in `ai/tool_functions_v2.py`, and two more the audit had missed: `routes/accounting.py`
> (×2, one of them the accounting-period query) and `routes/fees.py:495` (the fee checkout).
> A test walks every backend `.py` file and fails if the literal reappears anywhere except
> `school_identity.py` and the seed scripts, which legitimately create the branch record.

### A-5 · Federation tokens with no expiry are accepted forever — MEDIUM
`backend/routes/federation.py:32` decodes the LayaaStat federation JWT without requiring `exp`
(python-jose only validates `exp` when present). A minted token with no expiry is a permanent
credential to school incident/cost metadata. Fix: `jwt.decode(..., options={"require_exp": True})`
(and agree the claim with LayaaStat's token minter first).

> **✅ DONE 2026-08-05.** `jwt.decode` now passes
> `options={"require_exp": True, "verify_exp": True}`, plus an explicit `"exp" not in
> payload → 401` check because some python-jose builds accept `require_exp` without
> enforcing it. Three new tests, and there were **no** federation tests before this:
> a token with no expiry is refused, a normal token still works, and the wrong role
> still gets 403 while no token gets 401.
>
> **One thing to check with LayaaStat before the next deploy:** if its token minter is
> currently issuing federation tokens with no `exp` claim, those tokens stop working the
> moment this ships. That is the point of the change, but it is a coordination step, not
> a silent one.

### A-6 · Federation reads are unscoped raw-db reads — LOW (one school today)
`routes/federation.py` uses `get_raw_db()` for tenants/cost/incidents with no school filter.
Correct for a single-school deployment and the payloads are metadata-only (severity, status,
counts, no student data), but it is the same "guards a future second school" class as D-53.
Annotate as intentional or scope it.

> **✅ ANNOTATED 2026-08-05, deliberately not changed.** Federation is a provider-level
> read across the whole deployment by design, which is exactly why it uses `get_raw_db()`.
> Scoping it to one school would break its purpose. A `# tenant-scope: intentional` block
> at the top of `routes/federation.py` now records what does and does not leave through
> it (metadata only, no student, staff, fee or conversation content) and states the
> precondition: if a second school is ever hosted in this database, these three reads must
> gain a school filter first.

### A-7 · Per-line product lookup inside the sale loop — LOW
`services/commercial_service.py:746`: one `commercial_products.find_one` per cart line. Carts are
small so this is not the D-44/NEW-04 class in practice; batch with `$in` if touched anyway.

> **✅ DONE 2026-08-05.** One batched `{"id": {"$in": [...]}}` read builds a dict before the
> loop, per CLAUDE.md's no-loop-queries rule. Price-change, missing-product and stock-race
> behaviour is unchanged. Guarded by a call-counting test: a four-line cart must issue
> exactly ONE product read, and the assertion checks the query really used `$in`.

### A-8 · 876 pytest warnings, including a real test defect — LOW
The suite prints 876 warnings. At least two tests in `tests/backend/unit/test_wave2_patches.py`
(`:527` area) are synchronous functions carrying the module-level asyncio mark, which pytest flags.
Sweep the warnings the way the 48 build warnings were swept (T11): fix real ones, silence nothing
without a reason. A warnings gate is optional but keeps this from regrowing.

> **✅ DONE 2026-08-05. 876 → 56 warnings, and nothing was silenced.**
> It was not "at least two tests"; a static scan found **611 sync tests across 69 files**
> carrying a module-level `pytestmark = pytest.mark.asyncio`. The root cause is that
> `pytest.ini` has set **`asyncio_mode = auto`** all along, which marks every `async def`
> test automatically. So the hand-written module mark was redundant for the async tests
> and landed wrongly on every sync test in the same file, one warning each.
>
> Fix: removed that one redundant line from the 69 files that mix sync and async tests
> (files that are purely async keep it harmlessly; tier markers like
> `pytestmark = [pytest.mark.mongo_real]` were left alone). No test was lost or skipped:
> the suite went from 2163 to 2173 passed, and the 10 new ones are this audit's own guards.
>
> **The rule in `CLAUDE.md` and `AGENTS.md` was the cause and has been corrected** — it
> said the mark "goes in EVERY async test file", which is what generated 611 of these.
> Both now say not to add it, and explain why.
>
> The 56 that remain are third-party deprecations (Pydantic V1-style validators in
> `routes/auth.py`, starlette's multipart import). They are real upgrade debt but they are
> not this audit's scope, and fixing them means touching auth validation, which should be
> its own change.
>
> **Not verified: the real-Mongo tier.** It could not be run on this machine. Only
> MongoDB **8.3** is installed and it still dies silently with no log on this Windows 10
> build, exactly as `tests/backend/mongo_real/README.md` records; the working 7.0.16 build
> is no longer present. So the 13 transaction/rollback tests were not re-run after the A-3
> change. A-3 is covered on the fake-DB tier instead. Worth one run on a machine that has
> 7.0.16 before the next deploy.

### A-9 · Stale baselines still printed in two docs — LOW (recurring D-51 class)
`AGENTS.md` and `CLAUDE.md` still carry "2012 passed / 286 frontend, measured 2026-08-04";
today's measured numbers are 2163 / 439. `KNOWN_TEST_FAILURES.md` still opens with a 2026-07-08
"1278 passed" story. Reword all three to state only "the bar is 0 failures" and point at the
commands, so counts can never go stale again.

> **✅ DONE 2026-08-05.** Every pass count is out of `CLAUDE.md` and `AGENTS.md`; both now
> say the bar is ZERO failures and tell the reader to run the command and read what it
> prints, with a line explaining that written-down counts have gone stale and been reused
> as targets. `KNOWN_TEST_FAILURES.md` gained a header marking it a closed July 2026
> post-mortem, explicitly not the current baseline, and its "1278 passed" figure is gone.
>
> One genuinely misleading line was found while doing this and is worth naming: `CLAUDE.md`
> still told the reader to expect **"2 pre-existing failures in LayoutRouting.test.js"**.
> Those were fixed by T12 on 2026-08-04. Anyone following that instruction would have
> accepted a red frontend suite as normal, which is the D-52 failure mode over again.

---

## B. Known-open items confirmed still open (most need Abhimanyu, not code)

Verified against the registers and the code this session. Do NOT re-derive these as new.

**Doable with the owner's approval first:**
- **Data load (D-06…D-10 / Task 2):** read-only comparison is done (`f82f685`); writing awaits
  the owner's yes. Non-negotiable rules in `_bmad-output/HANDOFF-2026-08-04-evening.md`: match on
  admission number only; never take class/section from the 2025-26 detainees workbook.

**Blocked on credentials / environment, not code:**
- **T9 / NEW-13** AI answer-quality baseline: 55-conversation corpus ready, needs the production
  Azure OpenAI key for one credentialed run.
- **D-33, D-30/D-31** unproven live abilities (server-side file write, photo read, image input;
  scanned PDFs, on-demand vision).
- **D-32** stall thresholds deliberately left unmeasured.

**Owner-only (remind, do not attempt):**
- **Deploy verification** — see section C; this is the big one.
- **T14 / D-34** remove `iam:PutRolePolicy` from the `claude-hosting` IAM user.
- **D-46** WAF to Block mode, exclusion first.
- **D-64** purge of old CloudFront/server logs carrying personal query strings.
- **D-52** make the Tests check required in GitHub branch settings.
- Amplify: delete the now-unused `REACT_APP_UPLOAD_URL`.

**Watch:** D-65, the once-seen flaky frontend failure around the Owner AI-health test. Did not
reproduce this session (three runs green). If seen again, treat as real.

---

## C. LayaaStat visibility — the platform-awareness question

The code side is complete and healthy: env-gated ingest client with retry + store-and-forward
(`backend/services/layaastat/`), LLM spans from `llm_client`, product events from auth/chat/memory,
a 60-second PII-free health heartbeat from `server.py`, the federation read API, and the two D-41
payload bugs (wrong `event_name` field, bogus `service_id`) fixed and unit-tested.

**But none of that proves production is sending.** Two conditions must hold on the live backend
and neither is verifiable from this machine:
1. The build containing the D-41 fixes must actually be deployed. The last release note says
   backend deployment is **not verified** — the configured AWS identity cannot see any Elastic
   Beanstalk application in any region.
2. `LAYAASTAT_URL` and `LAYAASTAT_INGEST_KEY` must be set in the live backend environment;
   without both the integration is fully dormant by design.

**Action for Abhimanyu (not Codex):** after the next deploy, open the LayaaStat dashboard and
confirm three signals arrive: the `service_health` heartbeat (every minute), an LLM span after one
Flo message, and a product event after one login. Until that is seen, assume you and Shubham are
NOT getting telemetry, per D-41's last verified state.

---

## D. What was checked and found clean (so it is not re-audited next time)

- RBAC on the new commercial routes: six distinct gates, owner-only for entities, consolidated
  reporting owner-only; the auto-enumerating 401 surface test covers the new routes.
- POS money math: paise-integer arithmetic, split-payment validation, per-mode refund caps,
  price-change and stock-race conflicts, unique receipt numbers per entity, open-shift uniqueness
  via partial index, shift-closed race guarded by `activity_version` touch.
- Migration 029 registered in `run_all.py`; migration test present.
- Tenant scoping: all new collections carry `schoolId` + `branch_id` (except A-1's index and
  A-6's intentional raw reads).
- AI layer: kill switch, lockdown policy, parity corpus + drift gate extended to the commercial
  write tools; stop-slop habit is code-resident, no data flows into it.
- No `db.notifications.insert_one` outside the canonical service; `get_raw_db` uses are the
  documented infrastructure set (federation, operator, razorpay, server bootstrap).
