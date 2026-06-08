# Epic J — Epic-Close Multi-Lens Review

**Epic:** J — Student & staff CRUD (hardened AI tools) · **Date:** 2026-06-08
**Branch:** `ai-layer-hardening-plan` · **Reviewer:** Claude (Opus 4.8)

Scope reviewed: `services/student_service.py`, `services/staff_service.py`,
`routes/students.py`, `routes/staff.py`, `ai/tool_functions_v2.py` (4 student + 2 staff
tools + adapters + registry), `routes/chat.py` (required-params + labels),
`tests/backend/parity/{student,staff}_parity_test.py`,
`tests/backend/unit/test_epic_j_crud_guardrails.py`, `tests/backend/parity/corpus.py`.

## Result
**Suite:** 1005 passed, 25 failed (pinned pre-existing baseline — unchanged), 0 skipped,
0 NEW failures vs `/tmp/baseline_failures.txt`. +38 net new passing tests.
All Epic J stories' ACs met; parity byte-identical on both stories; Phase-1 lockdown verified.

## Lenses run
- **bmad-code-review** (correctness/quality of the diff)
- **bmad-review-adversarial-general** (escalation / authority holes)
- **bmad-review-edge-case-hunter** (no-op, dup, empty/None, non-list inputs)
- **bmad-testarch-test-review** (false-green, assertions, isolation)
- **bmad-testarch-trace** (AC→test)
- **bmad-testarch-nfr** (parity integrity / DPDP / security)

## Findings & fixes

| # | Sev | Lens | File | Issue | Fix | Regression test |
|---|-----|------|------|-------|-----|-----------------|
| 1 | High | adversarial / AD7 | `routes/staff.py` | After extracting `staff_service`, the route kept an orphaned `_create_or_link_user` + `_default_username` + `_can_set_privileged_fields` — a **duplicate write path** that could silently drift from the service (defeats AD7). | Removed all orphaned write/auth helpers + now-unused imports (`hash_password`, `Staff`, `write_audit`, `re`). Single write path = the service. | full suite + `staff_parity_test.py` green after removal |
| 2 | High | adversarial | `routes/students.py` | Same: orphaned `_validate_class`, `_get_current_academic_year`, `_is_transport_head`, `Student`/`Guardian` imports, and a stale `UPDATABLE_FIELDS` copy that would diverge from the service whitelist. | Removed; left a comment pinning the whitelist to the service only. | `student_parity_test.py` + `test_students.py` green |
| 3 | High | integration | `routes/chat.py` | New write tools were absent from `WRITE_TOOL_REQUIRED_PARAMS` → `test_missing_required_params_cover_all_confirmed_write_actions` failed (a real confirm-gate coverage gap: no missing-param prompt for the new tools). | Added all 6 J tools to `WRITE_TOOL_REQUIRED_PARAMS` + labels to `WRITE_TOOL_PARAM_LABELS`. | the existing coverage test now passes |
| 4 | High | security / DPDP | `ai/tool_functions_v2.py` | `create_staff` returns a plaintext temporary password; surfacing it into chat would leak a credential to the LLM transcript. | AI `tool_create_staff` drops `temporary_password` from returned data, emits an out-of-band-delivery note; REST still returns it once for the operator. DB state identical → parity holds. | `test_create_staff_ai_does_not_leak_temp_password` |
| 5 | Med | adversarial | `services/staff_service.py` | Must guarantee a Principal (admin) cannot mint owner/admin or sub_category accounts via the AI path. | Privileged-account gate (`_is_owner`) lives in the service → applied on both entrypoints. | `test_principal_cannot_create_privileged_staff` |
| 6 | Med | adversarial | `services/staff_service.py` | OWNER_ONLY_FIELDS (`role/sub_category/salary/is_active`) must be silently stripped for non-owners on the AI update path, not just REST. | Strip logic moved into the service. | `test_principal_owner_only_fields_silently_stripped_on_update` |
| 7 | Med | edge-case | `services/student_service.py` | No-op paths (update with no changes, set-status to same value) must not write spurious audit rows; duplicate admission must 409; non-list guardians must reject. | Verified via service; tool maps to clean failures. | `test_set_student_status_noop_when_unchanged`, `test_update_student_no_updatable_fields_raises`, `test_create_student_duplicate_admission_raises`, `test_manage_guardians_non_list_rejected` |
| 8 | Med | trace / AD15 | parity tests | AC: "no `delete_student`/`erase_student` AI tool" + Phase-1 lockdown coverage. | Added explicit absence test + parametrized lockdown allow/deny matrix over all 6 tools × 3 disallowed roles. | `test_no_ai_student_delete_or_erase_tool`, `test_phase1_lockdown_{allows,blocks}_*` |

## Non-bugs / deliberate decisions (dismissed with reason)
- **DPDP-to-LLM on the write result:** The confirmed-write result is returned as a JSON
  response from `/api/chat/confirm` to the client — it is **not** re-fed to the LLM. Only
  LLM-bound *read* results pass through `_safe_tool_result_for_chat → redact_for_llm`
  (verified: `dob`/`medical_notes`/`blood_group`/`phone` masked). So Epic J introduces no
  new special-category leak to the LLM; posture is identical to the reviewed Epics A–F.
- **Student/staff are school-scoped (no branch):** every `scoped_filter(..., get_school_id())`
  hit on the touched routes is a pre-existing read or an untouched route (self-update, photo,
  erase, leave). The new services mirror the exact school-scoped behavior (parity proves
  byte-identical). No `scoped_query(branch_id=…)` is expected for this whole-school domain.
  Audit clean: my refactored handlers contain **no** inline mutation/scoping.
- **Sync tests under module `pytestmark = asyncio`** emit a cosmetic PytestWarning but execute
  correctly; this matches the established platform convention (`test_student_p15.py`,
  `test_leave_approval.py`). Not false-green — assertions run.
- **Photo upload has no AI tool:** binary upload is impractical from chat; `photo_url` is
  settable via `update_student`. The REST photo route is characterized and untouched.

## scoped_filter / scoped_query audit
`routes/students.py`, `routes/staff.py` — all hits reviewed (see above): pre-existing,
school-scoped, correct. No new scoping introduced in route handlers (delegated to services).

## Parity corpus / CI drift gate
6 new entries added (`create_student`, `update_student`, `set_student_status`,
`manage_student_guardians`, `create_staff`, `update_staff`); `test_parity_corpus.py` green.
