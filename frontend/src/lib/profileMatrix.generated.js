/**
 * GENERATED FILE - DO NOT EDIT BY HAND.
 *
 * Mirror of `backend/services/profile_matrix.py`, which is the source of truth for
 * who may reach what. Regenerate with:
 *
 *     backend/.venv/Scripts/python.exe scripts/generate_profile_matrix.py
 *
 * `tests/backend/unit/test_profile_matrix_drift.py` fails if this file stops
 * matching the Python. Editing this file by hand does not change permissions; it
 * only breaks that test, which is the intended outcome.
 *
 * Read the Python file for the reasoning behind every line below.
 */

export const ALL_SCREENS = "__all_screens__";

export const PROFILE_MATRIX = {
  "accountant": {
    "deniedTools": [],
    "extraTools": [
      "add_transport_vehicle",
      "create_transport_route",
      "delete_transport_route",
      "get_attendance_overview",
      "get_class_wise_attendance",
      "get_leave_requests",
      "get_today_class_attendance",
      "get_transport_status",
      "query_attendance_status",
      "update_staff",
      "update_transport_route"
    ],
    "mayDeletePeople": false,
    "mayWrite": true,
    "person": "Sonu Ruhal",
    "screens": [
      "accounting-periods",
      "attendance-overview",
      "campus-library-hub",
      "certificate-generator",
      "commercial-operations",
      "data-import",
      "expense-tracker",
      "fee-collection",
      "fee-sync",
      "fee-tracker",
      "finance-commercial-hub",
      "financial-reports",
      "id-card-generator",
      "overview-hub",
      "payroll-manager",
      "people-operations-hub",
      "school-database-hub",
      "smart-fee-defaulter",
      "staff-attendance-tracker",
      "staff-leave-manager",
      "student-database",
      "transport-hub",
      "transport-manager",
      "transport-optimisation",
      "vendor-log"
    ],
    "status": "live",
    "title": "Accountant head",
    "toolDomains": [
      "finance",
      "shared"
    ]
  },
  "it_tech": {
    "deniedTools": [],
    "extraTools": [],
    "mayDeletePeople": false,
    "mayWrite": false,
    "person": null,
    "screens": [
      "custom-form-builder",
      "query-section",
      "raise-maintenance",
      "tech-issues"
    ],
    "status": "dormant",
    "title": "IT and technical",
    "toolDomains": []
  },
  "maintenance": {
    "deniedTools": [],
    "extraTools": [],
    "mayDeletePeople": false,
    "mayWrite": false,
    "person": null,
    "screens": [
      "maintenance-schedule",
      "raise-maintenance",
      "vendor-log"
    ],
    "status": "dormant",
    "title": "Maintenance",
    "toolDomains": []
  },
  "management": {
    "deniedTools": [
      "add_transport_vehicle",
      "create_transport_route",
      "delete_transport_route",
      "enroll_admission_application",
      "get_transport_status",
      "issue_admission_offer",
      "update_transport_route"
    ],
    "extraTools": [],
    "mayDeletePeople": false,
    "mayWrite": true,
    "person": "Lalit Thomas",
    "screens": [
      "academic-structure",
      "academics-activities-hub",
      "admissions",
      "admissions-communication-hub",
      "announcement-broadcaster",
      "asset-custody",
      "asset-tracker",
      "attendance-alerts",
      "attendance-overview",
      "attendance-recorder",
      "automated-report",
      "campus-library-hub",
      "certificate-generator",
      "circular-sender",
      "custom-form-builder",
      "data-import",
      "document-scanner",
      "exam-manager",
      "facility-requests",
      "governance-ai-hub",
      "id-card-generator",
      "incident-tracker",
      "library-circulation",
      "maintenance-schedule",
      "overview-hub",
      "parent-message",
      "people-operations-hub",
      "principal-daily",
      "procurement-inventory",
      "query-section",
      "quiz-manager",
      "raise-maintenance",
      "resource-calendar",
      "school-activities",
      "school-database-hub",
      "school-pulse",
      "smart-alerts",
      "staff-attendance-tracker",
      "staff-leave-manager",
      "staff-performance",
      "staff-tracker",
      "student-database",
      "student-leave-manager",
      "student-transfer",
      "tech-issues",
      "timetable-builder"
    ],
    "status": "live",
    "title": "Management, day-to-day data",
    "toolDomains": [
      "non_finance",
      "shared"
    ]
  },
  "owner": {
    "deniedTools": [],
    "extraTools": [],
    "mayDeletePeople": true,
    "mayWrite": true,
    "person": "Aman Litt",
    "screens": "__all_screens__",
    "status": "live",
    "title": "Owner",
    "toolDomains": [
      "finance",
      "leadership",
      "non_finance",
      "shared"
    ]
  },
  "parent": {
    "deniedTools": [],
    "extraTools": [],
    "mayDeletePeople": false,
    "mayWrite": false,
    "person": null,
    "screens": [
      "guardian-portal"
    ],
    "status": "dormant",
    "title": "Guardian",
    "toolDomains": []
  },
  "principal": {
    "deniedTools": [],
    "extraTools": [],
    "mayDeletePeople": true,
    "mayWrite": true,
    "person": "Adesh Singh",
    "screens": "__all_screens__",
    "status": "live",
    "title": "Principal",
    "toolDomains": [
      "finance",
      "leadership",
      "non_finance",
      "shared"
    ]
  },
  "receptionist": {
    "deniedTools": [],
    "extraTools": [],
    "mayDeletePeople": false,
    "mayWrite": false,
    "person": null,
    "screens": [
      "admissions",
      "asset-tracker",
      "custom-form-builder",
      "incident-tracker",
      "parent-message",
      "raise-maintenance",
      "student-database"
    ],
    "status": "dormant",
    "title": "Front desk",
    "toolDomains": []
  },
  "student": {
    "deniedTools": [],
    "extraTools": [],
    "mayDeletePeople": false,
    "mayWrite": false,
    "person": null,
    "screens": [
      "ai-tutor",
      "attendance-self-check",
      "career-guidance",
      "doubt-solver",
      "fee-status-viewer",
      "form-submissions",
      "homework-viewer",
      "library-circulation",
      "practice-test",
      "ptm-summary-viewer",
      "raise-maintenance",
      "result-viewer",
      "student-leave-request",
      "study-planner"
    ],
    "status": "dormant",
    "title": "Student",
    "toolDomains": []
  },
  "support_staff": {
    "deniedTools": [],
    "extraTools": [],
    "mayDeletePeople": false,
    "mayWrite": false,
    "person": null,
    "screens": [
      "custom-form-builder",
      "raise-maintenance"
    ],
    "status": "dormant",
    "title": "Support staff",
    "toolDomains": []
  },
  "teacher": {
    "deniedTools": [],
    "extraTools": [],
    "mayDeletePeople": false,
    "mayWrite": false,
    "person": null,
    "screens": [
      "assignment-generator",
      "class-attendance-marker",
      "class-performance-analytics",
      "curriculum-tracker",
      "exam-manager",
      "form-submissions",
      "leave-application",
      "lesson-plan-generator",
      "library-circulation",
      "my-payslips",
      "ptm-notes",
      "question-paper-creator",
      "quiz-manager",
      "raise-maintenance",
      "report-card-builder",
      "resource-calendar",
      "student-performance-viewer",
      "substitution-viewer",
      "worksheet-creator"
    ],
    "status": "dormant",
    "title": "Teacher",
    "toolDomains": []
  },
  "transport_head": {
    "deniedTools": [],
    "extraTools": [],
    "mayDeletePeople": false,
    "mayWrite": false,
    "person": "Chaman Singh",
    "screens": [
      "asset-tracker",
      "custom-form-builder",
      "raise-maintenance",
      "student-database",
      "transport-manager",
      "transport-optimisation"
    ],
    "status": "dormant",
    "title": "Transport head",
    "toolDomains": []
  }
};

export const LIVE_PROFILES = ["accountant", "management", "owner", "principal"];

export const DORMANT_PROFILES = ["it_tech", "maintenance", "parent", "receptionist", "student", "support_staff", "teacher", "transport_head"];
