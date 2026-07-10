# Epic R6 — Epic-Close Quality Gate

**Date:** 2026-07-08 · **Reviewed diff:** `services/memory/{extractor,chat_integration,store,vector}.py`, `server.py`, `routes/staff.py` + 1 new test file + 1 extended test file.

## STEP 4a — Tests
`python -m pytest tests/backend/ -q` → **1425 passed, 14 deselected, 0 skipped** (baseline 1411 → +14 new R6 tests). 0 regressions (all 27 existing Epic-G memory tests still green).
Eval structural + judge-logic tier → **18 passed**. No `prompts.py` change in R6; credentialed LLM-judge tier deferred (no creds — DEFERRED row 21).

## STEP 4b — Review lenses (applied manually per protocol)

| Lens | Findings | Resolution |
|------|----------|------------|
| code-review | Two-step forget deletes by explicit shown ids; pending guarded by TTL + next-turn clear; cap evicts lowest-value; sweeps paginated. Verified each path. | No change needed. |
| adversarial-general | Can the hijack return via another verb? `forget that i …` still enters the memory flow — but that is genuinely memory-oriented phrasing, and bare `delete/remove/note/save + object` now fall through. | Accepted; covered by tests. |
| adversarial-general | Prompt-injection via a recalled memory that reads like a command. | Fixed: recall block fenced + explicitly marked non-authoritative (XM3). |
| edge-case-hunter | `parse_inline_forget("forget the note")` returns `""` → forget flow lists ALL memories (≤ MAX_FORGET_MATCHES) and asks confirm. Intended, not destructive. | No change needed. |
| edge-case-hunter | Immediate self-eviction: adding a below-cap-value memory when at cap evicts the just-added lowest-value one. Correct (least valuable), and logged/audited. | No change needed. |
| edge-case-hunter | `_pending_fresh` allows a pending with NO `set_at_ts` (legacy/hand-built) — new pendings always carry it via `_set_pending`. | Backward-compatible by design; stale-rejection covered by `test_stale_pending_memory_not_confirmed`. |
| testarch-trace | R6.1 AC1/AC2/AC3, R6.2 AC1, R6.3 AC1/AC2, R6.4 XM5/XM10 each traced to a test. | See epic-R6-completed.md. |
| testarch-nfr | Per-owner cap (500) bounds recall scan cost; sweeps paginated (no unbounded load); redaction preserves DPDP; erasure covers right-to-erasure. | Acceptable. |

## STEP 4c — Findings fixed in-run
None beyond the story scope; the `memory_followup_question` redaction (XM4) was extended to both the persisted pending text and the appended question.

## STEP 4d — Scoped grep audit (touched files)
- `services/memory/*.py`: three `scoped_filter(...)` hits, all conversation-doc updates keyed by `{id, user_id, schoolId}`. Conversations/memories are **user-owned within a school** — no branch dimension applies, so branch scoping is correctly absent. Memory store filters via `_scope(ctx) = {schoolId, user_id}` directly.
- `server.py` / `routes/staff.py` / `vector.py`: no new tenant queries (startup hook uses scoped `get_db()`; staff erase delegates to the store).

## STEP 4e — Eval
Structural/judge-logic green (18). No prompt prose changed.

## Verdict
Gate clean. No findings carried into R7.
