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
      // Owner note, 2026-08-07: "school directory could be the sole directory... so,
      // let's just have single place with all the information rather than 3 places".
      // The Directory already listed everyone; it now carries the full information
      // and the search, and opening a row still leads to the same profile screens for
      // editing. `student-database` and `staff-tracker` remain reachable by deep link
      // (the Directory's own rows point at them) and stay in the permission lists -
      // only the duplicate front doors are gone.
      ['student-database', 'School Directory', 'Every student, guardian and staff member in one place', 'both'],
      ['data-import', 'Data Import', 'Update records from a sheet, or add new students', 'both'],
      ['certificate-generator', 'Certificates', 'TC, bonafide and school documents', 'both'],
      ['id-card-generator', 'ID Cards', 'Generate and print student cards', 'both'],
      ['document-scanner', 'Document Scanner', 'Extract and file documents', 'principal'],
    ],
  },
  {
    id: 'finance-commercial-hub', name: 'Finance', subtitle: 'Fees, payroll and expenses', color: 'var(--tool-hex-34d399)',
    items: [
      ['fee-collection', 'Fee Collection', 'Payments, receipts and exports', 'owner'],
      ['fee-sync', 'Fee Sync', 'External fee-system conflicts', 'owner'],
      ['fee-tracker', 'Fee Tracker', 'Class summary and dues', 'principal'],
      ['smart-fee-defaulter', 'Fee Defaulters', 'Overdue fees and reminders', 'both'],
      ['financial-reports', 'Financial Reports', 'Revenue and expense reporting', 'owner'],
      ['accounting-periods', 'Accounting Periods', 'Posting locks and controls', 'owner'],
      ['payroll-manager', 'Payroll & Payslips', 'Salary runs and corrections', 'owner'],
      ['expense-tracker', 'Expenses', 'Track and approve expenditure', 'owner'],
      ['commercial-operations', 'Commercial Operations', 'Admissions CRM and legal entities', 'both'],
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
      // Staff Tracker is NOT listed here on purpose, and it is not an omission. It sits
      // under this tab in the sidebar via `HUB_TAB_FOR_TOOL` below. Adding it here would
      // also paint a tile on the People & Attendance landing page, giving staff records a
      // second front door beside School Directory - the exact duplication the school's
      // owner asked to be removed on 2026-08-07, and which
      // `ManagementHubs.test.js::the merged directory is the only front door` guards.
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
      // R2-7, 2026-08-11: this screen was granted to the management head and appeared in
      // no group at all, so the only people who could open it were the profiles that
      // navigate by the flat sidebar list. A granted screen nobody can find is the same
      // defect as a button that refuses when pressed, only quieter.
      ['tech-issues', 'Tech Issues', 'Raise and track IT problems', 'both'],
      ['school-settings', 'School Settings', 'Identity and profile settings', 'owner'],
      ['custom-form-builder', 'Form Builder', 'Build school forms and surveys', 'both'],
    ],
  },
];

export const MANAGEMENT_HUB_IDS = MANAGEMENT_HUBS.map(hub => hub.id);

/**
 * Which sidebar tab a screen sits under, when it has no tile in a hub.
 *
 * Renamed from `HUB_FOR_CLASSROOM_TOOL` on 2026-08-14: it is no longer classroom-only.
 * The distinction it draws is not "classroom or office", it is **tab placement without a
 * landing-page tile**, and Staff Tracker needs exactly that. Reading this map decides
 * where an entry appears in the sidebar; `hubItemsForUser`, which paints the hub landing
 * pages, does NOT read it, so nothing here can add a second front door to a record.
 *
 * Originally: where a classroom-side screen belongs, for the teacher, student and
 * guardian menus.
 *
 * Reported 2026-08-12: every profile except the owner's and the principal's showed one
 * long flat list, and the decision was that all profiles carry THE SAME tab names, with
 * each profile seeing only what it is allowed to open.
 *
 * The hubs above already name every owner and office screen. These are the ones that
 * exist only for a teacher, a student or a guardian, so they had no hub to fall into.
 *
 * This map grants NOTHING. It answers "which tab does this sit under" and nothing else.
 * Who may open a screen is still decided by the profile's own tool list, exactly as
 * before, so regrouping a menu can never widen anybody's reach - a thing worth keeping
 * true, because a menu is the easiest place to hand out access by accident.
 */
export const HUB_TAB_FOR_TOOL = {
  // People & Attendance - the staff and the register.
  //
  // Abhimanyu, 2026-08-14: Staff Tracker belonged to no hub, so it was the only entry in
  // a "More" tab of its own. A whole tab holding one screen reads as a leftovers drawer
  // rather than a place, so it moves in with the rest of the staff screens.
  //
  // This GRANTS it to nobody. `groupToolsIntoHubs` only buckets the list a profile already
  // holds, so this decides which tab it sits under and nothing else.
  'staff-tracker': 'people-operations-hub',

  // People & Attendance - being present, and being away.
  'class-attendance-marker': 'people-operations-hub',
  'substitution-viewer': 'people-operations-hub',
  'leave-application': 'people-operations-hub',
  'attendance-self-check': 'people-operations-hub',
  'student-leave-request': 'people-operations-hub',

  // Academics & Activities - teaching, learning, and being assessed.
  'lesson-plan-generator': 'academics-activities-hub',
  'curriculum-tracker': 'academics-activities-hub',
  'assignment-generator': 'academics-activities-hub',
  'worksheet-creator': 'academics-activities-hub',
  'question-paper-creator': 'academics-activities-hub',
  'report-card-builder': 'academics-activities-hub',
  'student-performance-viewer': 'academics-activities-hub',
  'class-performance-analytics': 'academics-activities-hub',
  'ai-tutor': 'academics-activities-hub',
  'doubt-solver': 'academics-activities-hub',
  'homework-viewer': 'academics-activities-hub',
  'practice-test': 'academics-activities-hub',
  'result-viewer': 'academics-activities-hub',
  'study-planner': 'academics-activities-hub',
  'career-guidance': 'academics-activities-hub',

  // Admissions & Communication - talking to families.
  'ptm-notes': 'admissions-communication-hub',
  'ptm-summary-viewer': 'admissions-communication-hub',

  // Finance - money that concerns the person looking.
  'my-payslips': 'finance-commercial-hub',
  'fee-status-viewer': 'finance-commercial-hub',

  // Reports, AI & Governance - forms and records.
  'form-submissions': 'governance-ai-hub',

  // School Overview - the guardian's single front door.
  'guardian-portal': 'overview-hub',
};

/**
 * Bucket a profile's OWN tool list into the shared hubs, in hub order.
 *
 * Takes the exact list the profile already gets and only decides which tab each one
 * sits under. Anything with no hub is returned in `ungrouped` rather than dropped:
 * a tool that quietly disappears from a menu is indistinguishable from one that was
 * taken away, and that is the mistake this whole release was written to stop.
 */
export function groupToolsIntoHubs(tools) {
  const grouped = MANAGEMENT_HUBS.map(hub => {
    const hubItemIds = new Set(hub.items.map(([id]) => id));
    const inHub = (tools || []).filter(
      tool => hubItemIds.has(tool?.id) || HUB_TAB_FOR_TOOL[tool?.id] === hub.id,
    );
    return inHub.length ? { ...hub, tools: inHub.map(tool => tool.id) } : null;
  }).filter(Boolean);

  const placed = new Set(grouped.flatMap(hub => hub.tools));
  return { groups: grouped, ungrouped: (tools || []).filter(tool => !placed.has(tool?.id)) };
}

export function hubsForUser(user) {
  if (user?.role === 'owner') return MANAGEMENT_HUBS;
  if (user?.role === 'admin' && user?.sub_category === 'principal') return MANAGEMENT_HUBS;
  // R2-1/R2-5: every profile below leadership asks the same question of the same
  // grant table. The accountant head used to have his two hubs hardcoded here - a
  // second copy of the answer, sitting inside the module written to stop there being
  // a second copy - so when decision 2 gave him attendance, vendors and transport,
  // his menu would silently have stayed at two hubs.
  if (user?.role === 'admin') {
    return MANAGEMENT_HUBS.filter(hub => canUseTool(user, hub.id));
  }
  return [];
}

/**
 * Screens the owner is NOT offered, even though the owner may open anything.
 *
 * Owner request 1, 2026-08-06: "why is principal daily appearing in the owner
 * profile?" It appeared because `hubItemsForUser` short-circuited on
 * `audience === 'owner'` and handed the owner EVERY row in a hub, including the
 * thirteen tagged `principal`.
 *
 * The list is deliberately ONE entry long. Most of those thirteen are not
 * duplicates of anything - Timetable, Academic Structure, marking attendance,
 * Transport, Parent Messages, Student Transfer exist only in the principal's set,
 * and hiding them would take real screens away from the owner to answer a
 * complaint about one. Principal Daily is different: it is the principal's own
 * morning list of absences and substitutions, and the owner's equivalent, School
 * Pulse, already sits directly beside it in the same hub.
 *
 * This hides it from the owner's MENU only. Nothing about permissions changes; an
 * owner who opens the screen by its address still gets it.
 */
const HIDDEN_FROM_OWNER = new Set(['principal-daily']);

export function hubItemsForUser(hub, user) {
  if (!hubsForUser(user).some(item => item.id === hub?.id)) return [];
  const isOwner = user?.role === 'owner';
  const audience = isOwner ? 'owner' : 'principal';
  const hasProfileMatrix = user?.role === 'admin'
    && ['principal', 'accountant', 'management'].includes(user?.sub_category);
  return (hub?.items || []).filter(([id, , , access]) => {
    if (isOwner && HIDDEN_FROM_OWNER.has(id)) return false;
    const forThisAudience = isOwner || hasProfileMatrix || access === 'both' || access === audience;
    return forThisAudience && canUseTool(user, id);
  });
}
