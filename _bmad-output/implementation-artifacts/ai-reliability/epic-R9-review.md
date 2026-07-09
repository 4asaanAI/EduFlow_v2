# Epic R9 — Epic-Close Quality Gate Review

**Date:** 2026-07-10 · **Reviewer:** executing agent (self-review across the 5 lenses)
**Scope:** combined R9 diff — `ai/{llm_client,content_filter,redaction}.py`,
`services/{ai_kill_switch,layaastat}.py`, `routes/{chat,chat_upload,image_gen}.py`,
`server.py`, docs (`deployment-runbook §8`, `.env.example`, `CLAUDE.md`),
`conftest.py` + tests.

## STEP 4a — Tests
- Full backend suite → **1456 passed / 0 failed / 14 deselected / 0 skipped**
  (baseline 1444 → +12 net). Pinned baseline unchanged.
- Always-on eval tier (structural + judge-logic) → **18 passed**. R9 changed no
  `prompts.py` / tool schema, so the parity gate and prose-quality corpus are
  unaffected; credentialed judge tier stays deferred (no dev creds).

## STEP 4b — Review lenses (applied manually)

| Lens | Finding | Resolution |
|------|---------|------------|
| adversarial | Does the kill-switch `force_fresh` still fail OPEN on a Mongo error? Yes — the try/except path returns True regardless of force_fresh, preserving the "safety brake ≠ availability dependency" posture. | Verified. |
| adversarial | Removing the bare `\bbomb\b` pattern — does a real threat still get caught? "make/plant/set off/bring a bomb", "bomb the school", "how to make a bomb", "pipe bomb", "IED" all still match; only mention (history/curriculum) is allowed. | Accepted; test-covered. |
| adversarial | `\byou\s+are\s+(?:now\s+)?DAN\b` under IGNORECASE could match "you are dan" (a rare name statement). Trade-off accepted — the classic "You are DAN" jailbreak is the real risk; a mid-sentence name like "my friend Dan" (the audit's example) is NOT blocked. | Accepted. |
| edge-case (M10) | After removing topic-blocking from tool JSON, is PII still stripped? Yes — `_safe_tool_result_for_chat` → `redact_for_llm` runs upstream (chat.py:1900/2195); rich blocks get an explicit `redact_for_llm` PII pass. | Verified. |
| edge-case (X8) | `_validate_image_data` sizes from the base64 length BEFORE decoding, so a 100 MB blob is rejected without allocating it; the zip guard reads `ZipInfo.file_size` from the directory BEFORE `zf.read`, so a bomb is never expanded. | Verified by tests. |
| edge-case (X9) | Cert with a valid `student_id` but the student belongs to another school? `get_db()` injects `schoolId`, so `find_one({"id": student_id})` is school-scoped — a cross-school id returns 404. Owner/principal are cross-BRANCH by design (require_owner_or_principal). | Verified. |
| correctness | `image_gen` renamed the local `date` → `issued` to avoid shadowing the new `from datetime import date` import; both usages (`.format(date=issued)`, `f"Date: {issued}"`) updated. | Verified (tests generate a PDF). |
| testarch-trace | Every R9 AC traced to a test (see epic-R9-completed.md). | R9.1 AC1-3, R9.2 AC1-3, R9.3 AC1-3, R9.4 AC1-3, R9.5 AC1-3 covered. |
| testarch-nfr | force_fresh adds one Mongo read per confirmed WRITE (not per read) — negligible and correct. Streaming upload caps memory at the chunk size. Removing Gemini eliminates an external round-trip + cost. No new PII to any provider. | Improvement. |

## STEP 4c — Findings fixed in-run
1. Existing `test_image_gen_persistence.py` mocked the removed `_gemini_image`/`GEMINI_API_KEY` → rewritten to the new DB-resolved / owner-principal / no-Gemini contract.
2. Existing F.1 redaction test asserted `blood_group` masking → updated to the R9.2 AC3 contract (blood_group allowed; medical still masked).
3. `conftest.FakeDb` lacked `image_gen_quota` → added.
4. Shared-singleton `fake_db` pollution: image-gen tests now non-destructively ensure `student-1`/`class-1` exist (the DB records R9.5 resolves).

## STEP 4d — Scoped grep audit
No `scoped_filter(`/`scoped_query(` added or touched in the R9 files. `image_gen`
reads via `get_db()` (school auto-scoped); owner/principal are cross-branch by
design (require_owner_or_principal), so no branch clause is required or appropriate.

## STEP 4e — Golden eval
Structural + judge-logic green (18). No prompt/tool-schema change → no drift.

## Verdict
Gate clean for R9's scope. No R9-born defect carried forward. Two existing tests
were updated to R9's intentional contract changes (documented, not silenced).
R9 is the last epic before the GATED ones — R10 (self-learning Phase 2) and R11
(excellence) require Abhimanyu's explicit go-ahead; this run stops here.
