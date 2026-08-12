"""R4-2 - which write paths record what they did, and which do not.

--------------------------------------------------------------------------------
Why a register rather than "just add the missing ones"
--------------------------------------------------------------------------------

Twenty of the platform's seventy-five writing modules recorded nothing at all. Closing
those quietly would leave the platform in exactly the state that caused the problem: no
way to tell a module that deliberately does not record from one that was forgotten. A
year from now the next gap arrives the same way the last twenty did, one file at a time,
each individually reasonable.

So every module that writes to the database appears below with a verdict:

    RECORDS  - changes here are written to the audit trail.
    EXCUSED  - deliberately not recorded, WITH A REASON, decided by a person.

There is no third state. `tests/backend/unit/test_audit_coverage_r4_2.py` fails when a
module writes to the database and is in neither list, so a new gap cannot be introduced
without somebody writing down why.

--------------------------------------------------------------------------------
What "excused" is allowed to mean
--------------------------------------------------------------------------------

Excused is for machinery, never for the school's records. The test of it: **would anyone
at the school ever ask "who did that, and when?"** Nobody asks who incremented a token
counter. Everybody asks who changed a child's class.

Excused also covers writes that ARE the record. A message already lives in the message
table; an SMS already lives in the SMS log. Auditing those a second time stores the same
fact twice and doubles the bill for no new information (decision 13). What must still be
recorded in those areas is anything that CHANGES or REMOVES the existing record, because
that is the part the existing record cannot tell you about itself.
"""

from __future__ import annotations

from typing import Dict

#: Modules whose changes reach the audit trail.
RECORDS = {
    # Route files
    "routes/academics.py", "routes/activities.py", "routes/attendance.py",
    "routes/auth.py", "routes/chat.py", "routes/chat_upload.py", "routes/fees.py",
    "routes/image_gen.py", "routes/import_data.py", "routes/issues.py",
    "routes/notifications.py", "routes/operations.py", "routes/payroll.py",
    "routes/settings.py", "routes/staff.py", "routes/students.py",
    "routes/upload.py", "routes/messaging.py", "routes/operator.py",
    # Services
    "services/audit_retention.py",
    "services/ai_kill_switch.py", "services/enquiry_service.py",
    "services/campus_ops_service.py", "services/quiz_service.py",
    "services/razorpay_service.py",
    "services/payroll_service.py",
    "services/academic_structure_service.py", "services/account_management_service.py",
    "services/accounting_period_service.py", "services/admission_charge_service.py",
    "services/admissions_service.py", "services/announcement_service.py",
    "services/approvals_service.py", "services/asset_service.py",
    "services/attendance_correction_service.py", "services/attendance_service.py",
    "services/certificate_service.py", "services/commercial_service.py",
    "services/contact_log_service.py", "services/custom_form_service.py",
    "services/data_import_service.py", "services/discount_service.py",
    "services/document_export.py", "services/expense_service.py",
    "services/fee_config_service.py", "services/fee_lifecycle_service.py",
    "services/fee_sync_service.py", "services/fees_service.py",
    "services/house_points_service.py", "services/incident_service.py",
    "services/leave_service.py", "services/messaging_service.py",
    "services/org_config_service.py", "services/profile_notes_service.py",
    "services/query_ticket_service.py", "services/staff_attendance_service.py",
    "services/staff_service.py", "services/student_concession_service.py",
    "services/student_leave_service.py", "services/student_service.py",
    "services/substitution_service.py", "services/transport_service.py",
    "services/undo_service.py", "services/visitor_service.py",
    "ai/tool_functions_v2.py",
}

#: Modules that deliberately do not record, and the reason each one was excused.
#:
#: Every entry here was a decision. If you are adding one, the question to answer is
#: "would anyone at the school ever ask who did this, and when?" If they might, it does
#: not belong here.
EXCUSED: Dict[str, str] = {
    # ---- Machinery. Nobody has ever asked who did these. ----
    "services/token_service.py":
        "Counts LLM tokens used. A counter going up is not an act by a person.",
    "services/confirm_tokens.py":
        "Short-lived tokens backing confirm-before-you-act cards. The ACTION they "
        "confirm is audited; the token itself is plumbing that expires in minutes.",
    "services/auth_tokens.py":
        "Refresh tokens for staying signed in. Signing in and out is audited in "
        "routes/auth.py; storing the token is not a separate act.",
    "services/idempotency.py":
        "Remembers which requests have already run so a retry cannot double-charge. "
        "The underlying write is audited; this row only stops it happening twice.",
    "services/ai_rate_limiter.py":
        "Hourly counters of AI use per person. An operator CHANGING a limit is a "
        "decision and is audited in routes/operator.py; the counter is not.",
    "services/ai_metrics.py":
        "Measurements of how the AI layer is performing. Numbers about the platform, "
        "not changes to the school's records.",
    "services/ai_shadow_mode.py":
        "Dry-run mode deliberately aborts its transaction and commits NOTHING. There "
        "is no change to record, and recording one would describe a change that never "
        "happened.",
    "ai/plan_executor.py":
        "Runs an AI plan inside a transaction. Every write it performs is audited by "
        "the service that performs it, and those audit rows are enlisted in the same "
        "transaction, so a rolled-back plan leaves no orphan audit row.",

    # ---- Flo's own memory. Not the school's records. ----
    "services/memory/store.py":
        "Flo's working memory of a conversation. Notes it keeps to itself so it can "
        "follow a thread; nothing here is a school record and nobody would ask who "
        "changed one.",
    "services/memory/chat_integration.py":
        "Wires that working memory into a chat turn. It stores what Flo recalled, not "
        "anything about the school that changed.",
    "services/memory/feedback_store.py":
        "Records whether an answer Flo gave was useful, so it can do better. A rating "
        "of the assistant, not a change to the school's data.",
    "services/memory/skills_store.py":
        "Remembers how this school likes things done, learned over time. It changes "
        "how Flo behaves, never what the school's records say.",

    # ---- Writes that ARE the record. Auditing them stores one fact twice. ----
    "services/notification_service.py":
        "A notification is itself a durable, timestamped, addressed record. Copying it "
        "into the audit trail stores the same fact twice (decision 13, cost).",
    "services/school_summary_service.py":
        "Generated summaries of data that is already recorded elsewhere. Derived, not "
        "entered by anyone.",
    "routes/sms.py":
        "Every send already writes an SMS log row carrying recipient, body, time and "
        "outcome. That IS the record. The DECISION to message families in bulk is "
        "audited in services/messaging_service.py, which is the part the SMS log "
        "cannot tell you about itself.",
}


def verdict(module: str) -> str:
    """RECORDS, EXCUSED or UNDECIDED for a module path like 'services/foo.py'."""
    key = module.replace("\\", "/")
    if key in RECORDS:
        return "RECORDS"
    if key in EXCUSED:
        return "EXCUSED"
    return "UNDECIDED"
