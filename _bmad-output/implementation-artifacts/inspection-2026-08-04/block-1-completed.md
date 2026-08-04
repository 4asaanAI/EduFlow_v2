# BLOCK 1 — Make it correct, make the safety net trustworthy (2026-08-04)

Tasks T1–T5 of the Inspection Remediation initiative.
Register: `_bmad-output/planning-artifacts/inspection-findings-2026-08-04.md`
Protocol: `_bmad-output/INSPECTION-REMEDIATION-PROTOCOL-2026-08-04.md`
Branch: `inspection-remediation-2026-08-04` — **not merged to main.**

| Task | Finding | Status |
|---|---|---|
| T1 | NEW-01 certificate/ID-card permission | ✅ Done — owner decided in-session |
| T2 | NEW-02 suite back to zero failures | ✅ Done |
| T3 | NEW-03 113 calls bypassing the refreshing wrapper | ✅ Done |
| T4 | NEW-08 one shared server address | ✅ Done |
| T5 | NEW-11 two dead fee-discount helpers | ✅ Done |

---

## T1 · NEW-01 — who may issue an official school document

**Owner decision, taken before any code was written (rule 9).** Asked in plain English;
Abhimanyu's answer, verbatim: *"only owner, principal and an additional admin staff (i'll
let you know the position later on as i also don't know rn) should be able to print the
certificates. For now keep it to only owner and principal."*

So: reverted to **Owner + Principal**. The third office position is **open** and is on the
human-verification checklist for him to name.

- `backend/routes/image_gen.py:398` `POST /api/image-gen/certificate` and `:457`
  `POST /api/image-gen/id-cards` — `Depends(require_role("admin", "owner"))` →
  `Depends(require_owner_or_principal)`.
- A comment on each records the decision, its date, and why R9.5's forgery argument does
  not answer the authority question — so a future reader does not "correct" it back.
- `require_role` is no longer imported in that file.

**Why the original change was wrong even though its reasoning was right.** Commit `1011034`
argued that R9.5 resolves student identity from the database, so certificate *contents*
cannot be forged. That is true and unchanged. It is an answer to a different question:
who has the *authority* to put the school's name on an official document. Widening from 2
profiles to Owner + all 8 admin sub-categories (accountant, transport_head, receptionist,
it_tech, maintenance, management, support_staff, principal) was a permission decision, and
permission decisions belong to the Owner (D-18's lesson).

## T2 · NEW-02 — the suite back to zero failures

`test_certificate_denied_for_non_principal_admin` (red since 2026-07-25, and red **in
isolation**, so not the D-03 order-dependent class) passes again because T1 restored the
contract it was asserting. It was **not** rewritten to match the weaker gate.

The real defect T2 exposes is not the one red test — it is that **the ID-card route had no
permission test at all**, which is why half the widening was invisible. Added in
`tests/backend/unit/test_image_gen_persistence.py`:

- `test_certificate_refused_for_every_non_principal_admin` and
  `test_id_cards_refused_for_every_non_principal_admin` — parametrised over
  `SUB_CATEGORIES_BY_ROLE["admin"] - {"principal"}`, **derived from the auth module** so a
  sub_category added next year is covered the day it is added, not the day someone
  remembers this list.
- `test_certificate_allowed_for_principal` / `..._for_owner`, and the same pair for ID
  cards. Both halves of a two-profile rule need a test: without the owner cases, a later
  narrowing to principal-only would lock the Owner out with a green suite.
- `test_certificate_refused_for_teacher`, `test_id_cards_refused_for_student`.
- `test_certificate_unauthenticated_returns_401`, `test_id_cards_unauthenticated_returns_401`
  (the standing security convention, which these two endpoints did not have).

**Measured:** `main` was 1967 passed / 1 failed / 14 deselected.
This branch is **1991 passed / 0 failed / 14 deselected**. Baseline corrected wherever it
was recorded (see "Records corrected" below).

## T3 · NEW-03 — 178 calls that could not survive an expired login

Access tokens last 60 minutes. Renewal happened only on app load or when a 401 passed
through `apiFetch`. Every other call used a bare `fetch` and **none of them handled a 401**,
so after an hour a tool screen showed an empty list or an error while the rest of the app
quietly healed itself. Same defect class as D-43 (chat upload, fixed 2026-07-23 by routing
*one* call through `apiFetch`).

The register counted 113 calls in 18 files from the tool directory. The real total, counting
the shared components as well, is **178 calls across 21 files**; all were converted.

Three separate copies of the wrapper existed and are now one:

1. `apiFetch` in `lib/api.js` — **the** wrapper. Unchanged behaviour; now used everywhere.
2. `authFetch` in `contexts/UserContext.js` — a second implementation with **zero callers
   anywhere in the app**. Deleted.
3. `apiFetch` in `components/tools/SchoolActivities.js` — a **local function with the same
   name** that called bare `fetch`. Every call in that file looked like it used the shared
   wrapper and did not. Renamed `activitiesRequest` and now delegates to the real one; the
   name was the entire disguise.

**Deliberately left as a plain `fetch`, with the reason in a comment:** login and logout in
`UserContext.js`. A 401 there is a wrong password, not an expired session; refresh-and-retry
would try to renew a login that does not exist yet and bounce the person to the page they
are already on.

**Checked and found safe rather than assumed:**
- `apiFetch` retries once on 401. Every 401 in this backend is raised *before* a handler
  does any work (auth dependency, refresh tokens, login), so a retried POST cannot
  double-create. The one exception was found and fixed — see "Defect found and fixed" below.
- `apiFetch` never reads the response body, so the streaming chat POST in `StudentTools.js`
  and every blob download still work.
- `/auth/set-password` is bearer-authenticated and does not check the current password, so a
  401 there really is an expired session and refresh-and-retry is correct.
- `apiFetch` adds `credentials: 'include'`. The backend sets `allow_credentials=True` with
  explicit origins, and every pre-existing `apiFetch` call already did this.

**Tests:** `frontend/src/components/__tests__/ToolScreenTokenRefresh.test.js` — drives two
different real tool screens (Queries, Incident Tracker) through a real 401 and asserts the
refresh happens, the data renders, and nobody is bounced to the login page; plus the
retry-carries-the-new-token and failed-refresh-redirects-once contracts.
`frontend/src/lib/__tests__/apiBaseUrl.test.js` is the structural half: it fails the build
if any file goes back to a bare `fetch`.

## T4 · NEW-08 — one server address, not 25 copies

25 files each declared their own `process.env.REACT_APP_BACKEND_URL` base. That is why
commit `80d803b`'s http→https fix reached 13 files and missed 7 — including
`UserContext.js`, which owns login and token refresh.

`lib/api.js` now exports `API` and `BACKEND`; the other 24 declarations are deleted and
every file imports them. `setupProxy.js` still reads the variable directly and always will —
it runs in Node inside the dev server, before any app module exists.

**The live impact question the register told us to answer rather than assume: none.**
Checked the Amplify app's own configuration read-only —
`REACT_APP_BACKEND_URL = https://dapbq24rsje5g.cloudfront.net`. It is **already https**, so
the 7 files that lacked the http→https upgrade were never producing a blocked request for
the school. The fix removes the trap; it did not close a live outage. Saying otherwise would
be the D-15b mistake in reverse.

**Test:** `apiBaseUrl.test.js` fails if a 26th reader of the variable appears.

## T5 · NEW-11 — two dead fee-discount helpers

`approveFeeDiscount` and `rejectFeeDiscount` in `lib/api.js` called
`POST /api/fees/discounts/{id}/approve|reject`. The server serves only
`PATCH /api/fees/discounts/pending-approvals/{approval_id}/approve|reject` — wrong path
**and** wrong method. Nothing called them; the live Fee Collection screen already calls the
correct address itself.

**Deleted**, not corrected: a helper that looks ready to use and would 404 on first use is
worse than no helper. A comment records the correct route for whoever needs one.

**Test:** `frontend/src/lib/__tests__/feeDiscountPaths.test.js` — the exports do not come
back, no discount-approval address omits the `pending-approvals` segment, and the live
screen uses `PATCH`.

---

## Defect found and fixed inside this block

**A stale Confirm button would have signed the person out.**
`backend/services/confirm_tokens.py:293` answered **401** when a confirmation token belonged
to another user or an earlier browser session. That was harmless while the confirm card used
a bare `fetch` — it just showed an error. The moment every call went through the refreshing
wrapper, 401 came to mean "renew and retry": the renewal succeeds, the retry is refused
identically, and `apiFetch` signs the person out. So T3 would have turned a stale Confirm tap
into a forced logout.

Fixed at the root rather than special-cased in the client: the caller **is** authenticated;
it is the token that is foreign. That is a **403**. Changed, with the reasoning in the code,
the docstring corrected, and a regression test
(`test_consume_foreign_session_token_is_403_not_401`) that also asserts the rightful owner
still gets through, so it cannot pass by refusing everybody.

No frontend change needed: `classifyConfirmError` switches on a `code` field this refusal
does not carry, so the message the person sees is identical either way.

---

## Records corrected (T2 asked for this explicitly)

- `CLAUDE.md` — the current-initiative banner and the "must show 420 passed" line.
- `_bmad-output/implementation-artifacts/ui-sweep/DEFERRED-AND-DISCOVERIES.md` — D-03's
  "1968 passed / 0 failed" reading, which was true on 2026-07-23 and went stale on 07-25.
- The agent memory note that recorded `main` as 1967/1.

## Gates

| Gate | Result |
|---|---|
| Backend suite | **1991 passed / 0 failed / 14 deselected** (baseline restored per rule 8; `main` was 1967/1) |
| Frontend tests | **282 passed / 2 failed** — the 2 are `LayoutRouting.test.js`, pre-existing `AggregateError`, owned by T12 in Block 3 |
| Production build | Compiles. **48** `react-hooks/exhaustive-deps` warnings — exactly the pre-existing count, none added (T11, Block 3) |
| `scoped_filter` audit | `image_gen.py` and `confirm_tokens.py`: **no** `scoped_filter`/`scoped_query` calls in either; nothing to annotate |
| AI evals | **Green (18 passed)** — structural + judge-logic. Strictly not required (no change to `ai/prompts.py`, `ai/tool_functions*.py`, `ai/context_builder.py`, `ai/llm_client.py` or the tool-loop), but `confirm_tokens.py` sits on the chat confirm path, so the gate was run rather than argued away |
| Production systems | **None touched.** One read-only read of the Amplify app's own configuration (no school data), to answer the question T4 required |

Review findings and their disposition: `block-1-review.md`.
