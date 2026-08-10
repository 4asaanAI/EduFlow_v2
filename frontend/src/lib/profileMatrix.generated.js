/**
 * GENERATED FILE — DO NOT EDIT BY HAND.
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
      "update_transport_route"
    ],
    "mayDeletePeople": false,
    "mayWrite": true,
    "person": "Sonu Ruhal",
    "screens": [
      "accounting-periods",
      "attendance-overview",
      "campus-library-hub",
      "commercial-operations",
      "data-import",
      "expense-tracker",
      "fee-collection",
      "fee-sync",
      "fee-tracker",
      "finance-commercial-hub",
      "financial-reports",
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
      "get_transport_status",
      "update_transport_route"
    ],
    "extraTools": [],
    "mayDeletePeople": false,
    "mayWrite": true,
    "person": "Lalit Thomas",
    "screens": [
      "academic-structure",
      "academics-activities-hub",
      "admission-funnel",
      "admissions-communication-hub",
      "announcement-broadcaster",
      "asset-custody",
      "asset-tracker",
      "attendance-alerts",
      "attendance-overview",
      "attendance-recorder",
      "automated-report",
      "board-report",
      "campus-library-hub",
      "certificate-generator",
      "circular-sender",
      "custom-form-builder",
      "custom-report-builder",
      "data-import",
      "document-scanner",
      "enquiry-register",
      "exam-manager",
      "facility-requests",
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
      "asset-tracker",
      "commercial-operations",
      "custom-form-builder",
      "enquiry-register",
      "incident-tracker",
      "parent-message",
      "raise-maintenance",
      "student-database",
      "student-transfer"
    ],
    "status": "dormant",
    "title": "Front desk",
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

export const DORMANT_PROFILES = ["it_tech", "maintenance", "receptionist", "support_staff", "transport_head"];
