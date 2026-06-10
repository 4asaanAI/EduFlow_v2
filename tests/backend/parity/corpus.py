"""Parity corpus registry + CI drift gate source (Story F.6).

Maps every AI write tool to the parity test module that proves its AI entrypoint
and its REST entrypoint produce byte-identical DB state (modulo the volatile
allowlist in `normalizer.py`). The CI drift gate (`test_parity_corpus.py`) fails
if a tool in `WRITE_TOOL_NAMES` has no entry here — so a new write tool/route
cannot ship without a parity corpus entry, and drift can never silently reappear.

When Epics J/K add CRUD write tools, add their parity test here in the same PR.
"""

from __future__ import annotations

# tool name -> relative parity test module under tests/backend/parity/
PARITY_CORPUS = {
    "mark_attendance": "attendance_parity_test.py",
    "correct_attendance": "attendance_correction_parity_test.py",
    "approve_leave": "leave_parity_test.py",
    "decide_approval_request": "approvals_parity_test.py",
    "create_announcement": "announcement_parity_test.py",
    "log_contact_event": "contact_log_parity_test.py",
    "initiate_substitution": "substitution_parity_test.py",
    "record_fee_payment": "fees_parity_test.py",
    "apply_discount": "discount_parity_test.py",
    "award_house_points": "house_points_parity_test.py",
    "assign_followup": "incident_parity_test.py",
    "add_thread_entry": "incident_parity_test.py",
    "update_incident_status": "incident_parity_test.py",
    "confirm_resolution": "incident_resolution_test.py",
    # Epic J — student & staff CRUD
    "create_student": "student_parity_test.py",
    "update_student": "student_parity_test.py",
    "set_student_status": "student_parity_test.py",
    "manage_student_guardians": "student_parity_test.py",
    "create_staff": "staff_parity_test.py",
    "update_staff": "staff_parity_test.py",
    # Epic K.1 — fee-config CRUD
    "create_fee_structure": "fee_config_parity_test.py",
    "update_fee_structure": "fee_config_parity_test.py",
    "create_discount_type": "fee_config_parity_test.py",
    "update_discount_type": "fee_config_parity_test.py",
    "delete_discount_type": "fee_config_parity_test.py",
    # Epic K.2 — academic-structure CRUD
    "create_class": "academic_structure_parity_test.py",
    "update_class": "academic_structure_parity_test.py",
    "delete_class": "academic_structure_parity_test.py",
    "create_house": "academic_structure_parity_test.py",
    "update_house": "academic_structure_parity_test.py",
    "delete_house": "academic_structure_parity_test.py",
    # Epic K.3 — org-config CRUD
    "create_branch": "org_config_parity_test.py",
    "update_branch": "org_config_parity_test.py",
    "delete_branch": "org_config_parity_test.py",
    "update_school_settings": "org_config_parity_test.py",
    "year_end_transition": "org_config_parity_test.py",
    # Drift-gate remediation — operations tools added post-Phase-1 (ff2e929)
    "create_expense": "ops_crud_parity_test.py",
    "update_expense": "ops_crud_parity_test.py",
    "delete_expense": "ops_crud_parity_test.py",
    "create_enquiry": "ops_crud_parity_test.py",
    "update_enquiry_status": "ops_crud_parity_test.py",
    "create_incident": "ops_crud_parity_test.py",
    # Owner coverage gap-close — staff attendance + fee transaction lifecycle
    "mark_staff_attendance": "staff_attendance_parity_test.py",
    "correct_fee_transaction": "fee_txn_parity_test.py",
    "delete_fee_transaction": "fee_txn_parity_test.py",
    "trigger_fee_sync": "fee_txn_parity_test.py",
}
