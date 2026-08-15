"""Parity corpus registry + CI drift gate source (Story F.6).

Maps every AI write tool to the parity test module that proves its AI entrypoint
and its REST entrypoint produce byte-identical DB state (modulo the volatile
allowlist in `normalizer.py`). The CI drift gate (`test_parity_corpus.py`) fails
if a tool in `WRITE_TOOL_NAMES` has no entry here - so a new write tool/route
cannot ship without a parity corpus entry, and drift can never silently reappear.

When Epics J/K add CRUD write tools, add their parity test here in the same PR.
"""

from __future__ import annotations

# tool name -> relative parity test module under tests/backend/parity/
PARITY_CORPUS = {
    # Parent messaging (2026-08-08) - Flo can now send to families for real, so the
    # AI path and the panel path must produce identical message_logs + audit rows.
    "send_parent_message": "messaging_parity_test.py",
    "import_data_file": "data_import_parity_test.py",
    "create_message_template": "messaging_parity_test.py",
    "update_message_template": "messaging_parity_test.py",
    "delete_message_template": "messaging_parity_test.py",
    "submit_whatsapp_template": "messaging_parity_test.py",
    "mark_attendance": "attendance_parity_test.py",
    "correct_attendance": "attendance_correction_parity_test.py",
    "approve_leave": "leave_parity_test.py",
    "decide_approval_request": "approvals_parity_test.py",
    "create_announcement": "announcement_parity_test.py",
    "log_contact_event": "contact_log_parity_test.py",
    "initiate_substitution": "substitution_parity_test.py",
    "record_fee_payment": "fees_parity_test.py",
    "apply_discount": "discount_parity_test.py",
    # Release 2 step 10 - the school's own concessions, through both doors.
    "set_student_concession": "concession_parity_test.py",
    "record_admission_concession": "concession_parity_test.py",
    "set_right_to_education": "concession_parity_test.py",
    "award_house_points": "house_points_parity_test.py",
    "assign_followup": "incident_parity_test.py",
    "add_thread_entry": "incident_parity_test.py",
    "update_incident_status": "incident_parity_test.py",
    "confirm_resolution": "incident_resolution_test.py",
    # Epic J - student & staff CRUD
    "create_student": "student_parity_test.py",
    "update_student": "student_parity_test.py",
    "set_student_status": "student_parity_test.py",
    "manage_student_guardians": "student_parity_test.py",
    "create_staff": "staff_parity_test.py",
    "update_staff": "staff_parity_test.py",
    "create_student_login": "account_management_parity_test.py",
    "set_profile_password": "account_management_parity_test.py",
    # Owner request 4 (2026-08-06) - private notes on a profile
    "add_profile_note": "profile_note_parity_test.py",
    # Epic K.1 - fee-config CRUD
    "create_fee_structure": "fee_config_parity_test.py",
    "update_fee_structure": "fee_config_parity_test.py",
    "create_discount_type": "fee_config_parity_test.py",
    "update_discount_type": "fee_config_parity_test.py",
    "delete_discount_type": "fee_config_parity_test.py",
    # Owner instruction 2026-08-07 - the deletes Flo was missing. `delete_enquiry`
    # covers records made by both `create_enquiry` and `create_crm_lead`.
    "delete_student": "new_deletes_parity_test.py",
    "delete_staff": "new_deletes_parity_test.py",
    "delete_fee_structure": "new_deletes_parity_test.py",
    "delete_incident": "new_deletes_parity_test.py",
    "delete_certificate": "new_deletes_parity_test.py",
    "delete_enquiry": "new_deletes_parity_test.py",
    # A6, 2026-08-14 - the second half of the admissions funnel reaching Flo. Each is a
    # thin adapter over the same service function `routes/admissions.py` calls.
    "create_admission_application": "admissions_parity_test.py",
    "update_admission_application_status": "admissions_parity_test.py",
    "record_admission_assessment": "admissions_parity_test.py",
    "issue_admission_offer": "admissions_parity_test.py",
    "enroll_admission_application": "admissions_parity_test.py",
    "delete_legal_entity": "new_deletes_parity_test.py",
    # Epic K.2 - academic-structure CRUD
    "create_class": "academic_structure_parity_test.py",
    "update_class": "academic_structure_parity_test.py",
    "delete_class": "academic_structure_parity_test.py",
    "create_house": "academic_structure_parity_test.py",
    "update_house": "academic_structure_parity_test.py",
    "delete_house": "academic_structure_parity_test.py",
    # Epic K.3 - org-config CRUD
    "create_branch": "org_config_parity_test.py",
    "update_branch": "org_config_parity_test.py",
    "delete_branch": "org_config_parity_test.py",
    "update_school_settings": "org_config_parity_test.py",
    "year_end_transition": "org_config_parity_test.py",
    # Drift-gate remediation - operations tools added post-Phase-1 (ff2e929)
    "create_expense": "ops_crud_parity_test.py",
    "update_expense": "ops_crud_parity_test.py",
    "delete_expense": "ops_crud_parity_test.py",
    "create_enquiry": "ops_crud_parity_test.py",
    "update_enquiry_status": "ops_crud_parity_test.py",
    "create_crm_lead": "commercial_parity_test.py",
    "update_crm_lead": "commercial_parity_test.py",
    "create_legal_entity": "commercial_parity_test.py",
    "set_default_legal_entity": "commercial_parity_test.py",
    # R4-5: the only write that leaves the school. Parity matters more here than
    # anywhere, because a difference between the button and Flo is invisible from
    # inside the school - both say "reported" - and only shows up at our end.
    "report_platform_problem": "platform_ticket_parity_test.py",
    # Finance administration added for the four reviewed Flo profiles.
    "upsert_salary_structure": "finance_admin_parity_test.py",
    "disburse_salary": "finance_admin_parity_test.py",
    "correct_salary_disbursement": "finance_admin_parity_test.py",
    "create_accounting_period": "finance_admin_parity_test.py",
    "change_accounting_period_status": "finance_admin_parity_test.py",
    # Controlled school-defined schemas and rows (safe alternative to arbitrary
    # Mongo collection/schema mutation).
    "create_custom_form": "custom_form_parity_test.py",
    "update_custom_form": "custom_form_parity_test.py",
    "add_custom_form_row": "custom_form_parity_test.py",
    "delete_custom_form": "custom_form_parity_test.py",
    "create_incident": "ops_crud_parity_test.py",
    # Owner coverage gap-close - staff attendance + fee transaction lifecycle
    "mark_staff_attendance": "staff_attendance_parity_test.py",
    "correct_fee_transaction": "fee_txn_parity_test.py",
    "delete_fee_transaction": "fee_txn_parity_test.py",
    "trigger_fee_sync": "fee_txn_parity_test.py",
    # Wave 2 - assets, visitors, certificates (ops admin surfaces)
    "create_asset": "ops_admin_parity_test.py",
    "update_asset": "ops_admin_parity_test.py",
    "delete_asset": "ops_admin_parity_test.py",
    "log_visitor": "ops_admin_parity_test.py",
    "checkout_visitor": "ops_admin_parity_test.py",
    "delete_visitor": "ops_admin_parity_test.py",
    "create_certificate": "ops_admin_parity_test.py",
    "decide_certificate": "ops_admin_parity_test.py",
    # Wave 2 - query tickets + transport + announcement moderation
    "create_query_ticket": "query_transport_parity_test.py",
    "resolve_query_ticket": "query_transport_parity_test.py",
    "reopen_query_ticket": "query_transport_parity_test.py",
    "assign_query_ticket": "query_transport_parity_test.py",
    "delete_query_ticket": "query_transport_parity_test.py",
    "create_transport_route": "query_transport_parity_test.py",
    "update_transport_route": "query_transport_parity_test.py",
    "delete_transport_route": "query_transport_parity_test.py",
    # R3-2, 2026-08-15. Both entrypoints go through `transport_service.delete_vehicle`,
    # which is also where the approval gate lives, so chat and the screen cannot give
    # different answers about whether Aman has to agree.
    "remove_transport_vehicle": "query_transport_parity_test.py",
    "add_transport_vehicle": "query_transport_parity_test.py",
    "decide_announcement": "query_transport_parity_test.py",
    "delete_announcement": "query_transport_parity_test.py",
    # Approvals workflow, 2026-08-15. One tool decides any of the six kinds, and it
    # grants nobody anything: both doors go through `approval_registry.decide`, which
    # asks each kind's own service. The parity test drives BOTH and compares the stored
    # record, and separately proves the accountant head, who holds the tool because it
    # is classified shared, is refused exactly as the screen refuses him.
    "decide_any_approval": "approvals_workflow_parity_test.py",
}
