# Epic R11.1 — Golden Eval Corpus + LLM-judge CI · Epic-Close Quality Gate

Review lenses (code-review / adversarial / edge-case-hunter / test-review / trace /
nfr) applied over the whole R11.1 diff.

## Test results
- Full backend suite: **1344 passed, 0 failed, 0 skipped, 14 deselected** (13 mongo_real + 1 llm_eval). Baseline (post-R3) 1326; +18 always-on eval tests.
- `pytest tests/backend/evals`: 18 passed, 1 deselected (the credentialed tier) — confirms the LLM-judge tier is *deselected*, not skipped, so it never violates the 0-skips rule.

## Grep audit (scoped_filter / scoped_query)
- **No backend source files modified** in R11.1 (test harness + corpus data + docs + pytest.ini only). The audit is trivially clean — the harness adds no DB queries; it reuses `build_system_prompt` and `LLMClient.chat` unchanged.

## Findings (self-review) & resolution

| # | Severity | Area | Issue | Resolution |
|---|----------|------|-------|------------|
| 1 | By design | LLM-judge tier | Cannot run in this credential-less environment. | Marked `llm_eval` + deselected (0 skips); logic is fully unit-tested with a fake judge; baseline is established on the first credentialed run. Documented in plain English (protocol's "needs real credentials" clause). |
| 2 | Low | corpus/coverage | `('owner','owner')` and `('student','student')` alias keys in TOOLS_BY_ROLE are covered via their `None`-sub entries. | Coverage test treats role==sub sentinel keys as satisfied by the role's None entry — intentional, documented in the test. |
| 3 | Low | judge robustness | A judge that returns prose/garbage or omits a dimension could inflate scores. | `parse_judge_scores` defaults missing/non-numeric dimensions to 0.0 (worst-case) and clamps to [0,1]; unit-tested. |

## Edge cases walked (edge-case-hunter lens)
- **Silent turn (the incident class):** an assistant reply of `""`/`ok=False` is recorded as an error and scores 0.0 in the aggregate — it can never be silently excused. Unit-tested (`test_run_eval_records_empty_assistant_reply_as_error`). ✅
- **Per-conversation crash:** `run_eval` wraps each conversation; an exception becomes a recorded error (score 0), never aborts the whole corpus. ✅
- **No baseline yet:** `regression_check` accepts and reports (establishes baseline) rather than dividing-by-nothing or blocking spuriously. ✅
- **Denial coherence:** a denial entry whose tool is (wrongly) advertised to the role fails the structural eval — so the corpus can't encode a fake denial. ✅
- **Corpus↔system drift:** if a future change removes/renames a tool a corpus entry expects, the structural eval fails — the corpus stays honest. ✅

## NFR lens
- **Reliability/observability:** this epic is itself the permanent quality-regression instrument for the whole initiative. The incident conversation is a first-class corpus entry, so the exact failure that started this work is now a standing regression check.
- **Security/tenancy:** no new data paths; harness reads prompts/registry only; no credentials committed; judge scores are PII-free aggregates.
- **Portability:** corpus is committed data; always-on tiers need no network; the credentialed tier degrades to a clear skip-with-reason only when explicitly selected without creds.

## AC → test traceability
- AC1 → `test_corpus_has_at_least_40_conversations`, `test_corpus_covers_every_role_and_sub_category`, `test_corpus_covers_required_scenario_tags`, `test_expected_tools_are_coherent_with_the_advertised_toolset`.
- AC2 → `test_eval_llm_judge.py::test_golden_corpus_quality_no_regression` (credentialed) + judge-logic unit tests (`regression_check`, `aggregate`, `run_eval` fakes).
- AC3 → protocol doc directive + `pytest.ini` marker + `README.md` (verified present).
