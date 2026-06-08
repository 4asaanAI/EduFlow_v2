# Epic F — Compliant & Operable (DPDP + safety-ops + parity harness)

**Status:** ✅ DONE — all 11 stories implemented, epic-close multi-lens review complete.
**Date:** 2026-06-08
**Suite:** 967 passed / 10 mongo_real deselected / **0 new failures** vs the pinned 25-failure baseline.

## What shipped (story → artifact)

| Story | FR | Implementation |
|---|---|---|
| F.1 PII minimization | FR19/20/23 | `backend/ai/redaction.py:redact_for_llm()` — THE canonical redactor; `_safe_tool_result_for_chat` delegates. Surgical: masks special-category keys (DOB/contact/health/full-address/Aadhaar + secrets); names/ids/counts/amounts pass through. |
| F.2 Redacted traces + audited minor reads | FR21 | `_audit_minor_read` + `MINOR_READ_TOOLS` (PII-free `minor_record_read` audit, fail-open). `contains_unredacted_pii()` scanner. |
| F.3 Per-step re-scoping | FR16-18 | `plan_executor._assert_step_scope` → `PlanScopeViolationError`→403 if a step names a foreign branch/school. |
| F.4 Kill-switch | FR24 | `services/ai_kill_switch.py` (`db.system_flags.ai_writes_enabled`, fails open, ≤30s cache); checked before rate gate + consume. |
| F.5 Shadow/dry-run | FR25 | `services/ai_shadow_mode.py` (`ai_dry_run`, default OFF) → aborted-txn `would_change`, no side-effects. |
| F.6 Parity harness + CI gate | FR15 | `tests/backend/parity/{normalizer.py,corpus.py,test_parity_corpus.py}` — shared ruleset + drift gate (14/14 write tools mapped). |
| F.7 Observability | FR24-25 | `services/ai_metrics.py:record_ai_metric`→`db.ai_metrics`, PII-free, fail-open. |
| F.8 Closeout | — | `project-context.md` invariants table + `CLAUDE.md` ADRs + tracker row 17 + runbook §8. |
| F.9 Remediation runbook | — | `docs/deployment-runbook.md` §8.3 (find dispatch via `ai_dispatch_audit_log`/`audit_logs`, reverse through UI, restore deletes from backup). |
| F.10 Two-step destructive + deletion audit | FR42 | `DESTRUCTIVE_TOOL_NAMES`/`FORBIDDEN_AI_TOOLS`/`_token_meta_destructive_steps`/`_audit_destructive_step`; 409 `destructive_confirmation_required` until `destructive_ack=True`; student delete/erase refused. |
| F.11 Phase-1 lockdown | FR43 | `services/ai_action_policy.py` single switch `LOCKDOWN_ENABLED`, applied in `_is_tool_authorized`; writes = Owner+Principal only; reads (incl. student) unaffected. |

## Epic-close review findings (multi-lens: adversarial, edge-case, test-review, trace, nfr)

| # | Sev | File | Issue | Fix | Regression test |
|---|---|---|---|---|---|
| 1 | High | `routes/chat.py` | Kill-switch + destructive-ack checks ran AFTER the rate-limit increment, so a blocked / ack-less attempt burned a rate slot. | Reordered: peek → kill-switch → destructive-ack → rate gate → consume. | `test_chat_dispatch_epicF.py::test_kill_switch_blocks_write` (tool never runs); destructive two-step proves token not burned. |
| 2 | Med | `ai/redaction.py` | Bare `"health"` substring would mask non-PII keys like `system_health` (IT-tech dashboard read) — over-blocking, against the user's "don't over-guardrail" directive. | Narrowed `_RESTRICTED_SUBSTRINGS` to `medical/aadhaar/disabilit`; health PII covered by explicit exact keys. | `test_ai_redaction_f1_f2.py::test_identifiers_and_task_fields_pass_through`. |
| 3 | Low | `routes/chat.py` | Deletion audit must not fire on dry-run / idempotent replay (nothing deleted). | Guarded `_audit_destructive_step` on `exec_result.status == "committed"`. | covered by `test_destructive_requires_second_ack_then_audits` (asserts exactly 1 delete row). |

### Dismissed (with reason)
- **Dry-run "commits nothing" not provable on FakeDb.** FakeCollection has no transactions, so an aborted txn doesn't roll back. This is a known substrate limitation (D.1) — true no-commit is a `@pytest.mark.mongo_real` concern; the unit/integration tier asserts the wiring (flag→dry_run→`would_change` shape, side-effects skipped). Not a code bug.
- **`_is_tool_authorized` rewrite changes semantics?** Verified equivalent for the sub_category gate (None → pass; non-admin → pass; admin not-in-list → deny) and the full pre-existing suite stays green; the lockdown is an additive write-only gate.
- **Metrics emitted outside the txn could survive a rollback.** Intentional: metrics run after `run()` returns (txn already committed) and terminal/error metrics must persist even when the dispatch aborts. `in_transaction` defaults False.

## Guardrail calibration (user directive — 2026-06-08)
The user explicitly required the DPDP controls NOT over-block the LLM into refusals/non-compliance. Verified:
- Redaction masks special-category keys only; names/ids/amounts/counts/statuses pass through.
- Kill-switch fails OPEN; dry-run defaults OFF; minor-read audit + metrics are fail-open and never block a read/response.
- Lockdown gates WRITE/action tools only — every read tool (incl. all student tools) is unaffected.

## scoped_filter / scoped_query audit
`backend/routes/chat.py` — 5 `scoped_filter` hits, all pre-existing conversation/message scoping (per-user collections; branch isolation N/A). New Epic-F code uses `get_school_id()` + `write_audit(school_id=…)`. **Clean.**
