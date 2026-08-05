import { canUseTool } from './toolPermissions';

export const MANAGEMENT_HUBS = [
  {
    id: 'overview-hub', name: 'School Overview', subtitle: 'Daily priorities and alerts', color: 'var(--tool-hex-fb923c)',
    items: [
      ['school-pulse', 'School Pulse', "Today's school-wide picture", 'owner'],
      ['principal-daily', 'Principal Daily', 'Absences and substitutions', 'principal'],
      ['attendance-overview', 'Attendance Overview', 'Student attendance trends', 'both'],
      ['smart-alerts', 'Smart Alerts', 'Exceptions needing attention', 'both'],
    ],
  },
  {
    id: 'school-database-hub', name: 'School Database', subtitle: 'Students, guardians and staff', color: 'var(--tool-hex-4f8ff7)',
    items: [
      ['school-directory', 'School Directory', 'Find any student or staff member', 'both'],
      ['student-database', 'Students & Guardians', 'Profiles, status and linked guardians', 'both'],
      ['staff-tracker', 'Teachers & Staff', 'Profiles, roles and employment records', 'both'],
      ['data-import', 'Data Import', 'Validate and import student records', 'owner'],
      ['certificate-generator', 'Certificates', 'TC, bonafide and school documents', 'both'],
      ['id-card-generator', 'ID Cards', 'Generate and print student cards', 'both'],
      ['document-scanner', 'Document Scanner', 'Extract and file documents', 'principal'],
    ],
  },
  {
    id: 'finance-commercial-hub', name: 'Finance & Campus Sales', subtitle: 'Fees, payroll, expenses and retail', color: 'var(--tool-hex-34d399)',
    items: [
      ['fee-collection', 'Fee Collection', 'Payments, receipts and exports', 'owner'],
      ['fee-sync', 'Fee Sync', 'External fee-system conflicts', 'owner'],
      ['fee-tracker', 'Fee Tracker', 'Class summary and dues', 'principal'],
      ['smart-fee-defaulter', 'Fee Defaulters', 'Overdue fees and reminders', 'both'],
      ['financial-reports', 'Financial Reports', 'Revenue and expense reporting', 'owner'],
      ['accounting-periods', 'Accounting Periods', 'Posting locks and controls', 'owner'],
      ['payroll-manager', 'Payroll & Payslips', 'Salary runs and corrections', 'owner'],
      ['expense-tracker', 'Expenses', 'Track and approve expenditure', 'owner'],
      ['commercial-operations', 'Commercial Operations', 'CRM, legal entities and campus retail', 'both'],
    ],
  },
  {
    id: 'admissions-communication-hub', name: 'Admissions & Communication', subtitle: 'Prospects, enrolment and outreach', color: 'var(--tool-hex-a78bfa)',
    items: [
      ['admission-funnel', 'Admission Funnel', 'Enquiries and conversions', 'owner'],
      ['enquiry-register', 'Admissions CRM', 'Leads, follow-ups and pipeline', 'principal'],
      ['circular-sender', 'Circulars', 'School notices and announcements', 'principal'],
      ['announcement-broadcaster', 'Announcements', 'Broadcast school updates', 'owner'],
      ['parent-message', 'Parent Messages', 'Direct guardian communication', 'principal'],
      ['student-transfer', 'Student Transfer', 'Withdrawal and transfer certificate', 'principal'],
      ['student-leave-manager', 'Student Leave', 'Requests, policy and decisions', 'both'],
    ],
  },
  {
    id: 'academics-activities-hub', name: 'Academics & Activities', subtitle: 'Classes, exams, quizzes and houses', color: 'var(--tool-hex-fbbf24)',
    items: [
      ['academic-structure', 'Academic Structure', 'Classes, subjects and teacher mapping', 'principal'],
      ['timetable-builder', 'Timetable', 'Build and manage schedules', 'principal'],
      ['exam-manager', 'Exams', 'Schedules, marks and results', 'both'],
      ['quiz-manager', 'Quizzes', 'Author, publish and review attempts', 'both'],
      ['school-activities', 'School Activities', 'Houses, sports, clubs and awards', 'both'],
      ['attendance-recorder', 'Student Attendance', 'Mark and correct attendance', 'principal'],
    ],
  },
  {
    id: 'people-operations-hub', name: 'People & Attendance', subtitle: 'Staff attendance, leave and performance', color: 'var(--tool-hex-22d3ee)',
    items: [
      ['staff-attendance-tracker', 'Staff Attendance', 'Presence and late patterns', 'owner'],
      ['staff-performance', 'Staff Performance', 'Performance overview and trends', 'both'],
      ['staff-leave-manager', 'Staff Leave', 'Review and decide leave requests', 'both'],
      ['attendance-alerts', 'Attendance Alerts', 'Threshold alerts and messages', 'both'],
    ],
  },
  {
    id: 'campus-library-hub', name: 'Campus, Library & Assets', subtitle: 'Library, rooms, stock and facilities', color: 'var(--tool-hex-f472b6)',
    items: [
      ['library-circulation', 'Library', 'Catalogue, circulation and overdue loans', 'both'],
      ['resource-calendar', 'Rooms & Resources', 'Book rooms, labs and equipment', 'both'],
      ['asset-tracker', 'Asset Register', 'School assets and inventory records', 'both'],
      ['asset-custody', 'Asset Custody', 'Issue and return school assets', 'both'],
      ['procurement-inventory', 'Procurement & Inventory', 'Requisitions, orders and stock', 'both'],
      ['facility-requests', 'Facility Requests', 'Maintenance work queue', 'both'],
      ['maintenance-schedule', 'Maintenance Schedule', 'Preventive maintenance calendar', 'owner'],
      ['vendor-log', 'Vendors', 'Contractors and service providers', 'owner'],
      ['raise-maintenance', 'Report an Issue', 'Raise a campus maintenance request', 'principal'],
    ],
  },
  {
    id: 'transport-hub', name: 'Transport', subtitle: 'Routes, vehicles and optimisation', color: 'var(--tool-hex-fb923c)',
    items: [
      ['transport-manager', 'Routes & Vehicles', 'Transport operations and assignments', 'principal'],
      ['transport-optimisation', 'Route Optimisation', 'Geocoding and cluster analysis', 'principal'],
    ],
  },
  {
    id: 'governance-ai-hub', name: 'Reports, AI & Governance', subtitle: 'Reports, Flo, audit and settings', color: 'var(--color-text-secondary)',
    items: [
      ['custom-report-builder', 'Custom Reports', 'Build operational reports', 'owner'],
      ['board-report', 'Board Report', 'Trust and management reporting', 'owner'],
      ['automated-report', 'Automated Reports', 'Scheduled report delivery', 'principal'],
      ['ai-health-report', 'AI Health', 'Flo reliability and usage summary', 'owner'],
      ['what-ive-learned', "What Flo Has Learned", 'Review memories and routines', 'both'],
      ['conversation-trace', 'Conversation Trace', 'Inspect whether Flo replied', 'owner'],
      ['audit-log', 'Audit Log', 'Who changed what and when', 'both'],
      ['incident-tracker', 'Incidents & Visitors', 'Safety and visitor records', 'both'],
      ['query-section', 'Query & Support', 'Requests, issues and resolutions', 'both'],
      ['school-settings', 'School Settings', 'Identity and profile settings', 'owner'],
      ['custom-form-builder', 'Form Builder', 'Build school forms and surveys', 'both'],
    ],
  },
];

export const MANAGEMENT_HUB_IDS = MANAGEMENT_HUBS.map(hub => hub.id);

export function hubsForUser(user) {
  if (user?.role === 'owner') return MANAGEMENT_HUBS;
  if (user?.role === 'admin' && user?.sub_category === 'principal') return MANAGEMENT_HUBS;
  return [];
}

export function hubItemsForUser(hub, user) {
  if (!hubsForUser(user).some(item => item.id === hub?.id)) return [];
  const audience = user?.role === 'owner' ? 'owner' : 'principal';
  return (hub?.items || []).filter(([id, , , access]) =>
    (audience === 'owner' || access === 'both' || access === audience) && canUseTool(user, id));
}
