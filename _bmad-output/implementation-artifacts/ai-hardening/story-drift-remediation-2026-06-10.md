# Post-Phase-1 Drift Remediation + Owner Coverage Gap-Close — 2026-06-10

**Trigger:** Owner master request ("AI must CRUD every owner tool/section"). Audit found
Phase 1 (Epics A–G) complete, but commit `ff2e929` (post-Phase-1) had added 4 AI write
tools **bypassing the F.6 drift gate** — exactly the drift the initiative exists to stop.
The gate's own CI tests were failing and caught it.

## Findings → fixes

| # | Severity | Issue | Fix | Regression guard |
|---|----------|-------|-----|------------------|
| 1 | HIGH | `create_expense`/`create_enquiry`/`update_enquiry_status`/`create_incident` added with direct-write bodies, no corpus entry, no confirm-gate params; AI and REST field sets had already diverged (AI stamped `branch_id`+JWT schoolId; REST didn't; enquiry AI skipped the stage-transition guard entirely) | Extracted `services/expense_service.py`, `services/enquiry_service.py`, `incident_service.create_incident`; REST routes + AI tools both call them (AD7); tools registered in `WRITE_TOOL_REQUIRED_PARAMS` + `PARITY_CORPUS` | `ops_crud_parity_test.py` (7 tests incl. `test_ai_enquiry_transition_guard_now_matches_rest`) + F.6 gate green |
| 2 | HIGH | "Mark all staff present today" impossible via AI — no staff-attendance write tool; REST `POST /attendance/staff/bulk` had no audit and no status validation | New `services/staff_attendance_service.py` (EC-14.1 single audit row per bulk, status whitelist); REST refactored onto it; new `mark_staff_attendance` tool with mark-all-active-staff expansion | `staff_attendance_parity_test.py` (3 tests) |
| 3 | MED | Fee-transaction correction + soft-delete (recent UI feature) unreachable by AI ("delete duplicate fee entries") | `fees_service.correct_transaction` / `delete_transaction` extracted from routes (EC-10.3/10.5 preserved, accountant own-txn rule via actor_ctx); tools `correct_fee_transaction` + `delete_fee_transaction` (destructive → F.10 two-step) | `fee_txn_parity_test.py` (3 tests) |
| 4 | MED | Fee sync not triggerable/queryable via AI | New `services/fee_sync_service.py` (EC-10.1 idempotency, hung-job expiry, injectable fetch); tools `trigger_fee_sync` + `get_fee_sync_status` | `fee_txn_parity_test.py` (2 tests) |
| 5 | LOW | 3 stale tests asserting removed/changed behavior (ee92f4e SMTP removal; 500-cap pagination; fee DELETE route now exists as soft-delete) | Deleted `test_auth_password_reset.py` (admin reset covered in `test_it_tech_p13.py`); rewrote pagination test asserting default 20 + cap 500; rewrote fee-delete test asserting soft-delete + 404 | `test_fee_transaction_delete_is_soft_never_hard`, `test_list_pagination_default_and_cap` |

## Security posture (unchanged invariants)

- All 10 new/remediated write tools auto-covered by **F.11 Phase-1 lockdown** (Owner+Principal only)
  and the **F.4 kill-switch** — both derive from registry `dispatch_type`/`requires_confirmation` flags.
- Deletes (`delete_expense`, `delete_fee_transaction`) flagged `destructive: True` → F.10 two-step
  confirm + actor-tagged deletion audit. Student delete/erase remain FORBIDDEN_AI_TOOLS.
- Fee transaction delete is **soft** (financial trail kept) on both entrypoints.
- scoped_filter audit clean on all touched files (new intentional school-scope hits commented).

## Result

- Registry: **91 tools / 46 write tools**, F.6 drift gate green again.
- Suite: **1161 passed, 0 new failures** vs pinned 25-failure baseline (`ai-hardening-epic-a-baseline.txt`);
  16 new parity/guardrail tests.
- Data-import remains UI-only by design (file-upload validate/commit flow — not a chat surface).
