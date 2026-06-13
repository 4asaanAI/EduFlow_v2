// Maps a notification to a sidebar tool ID, or null if a detail modal is more appropriate.
// null  → show NotificationDetailModal (tracked types with timeline)
// string → navigate directly to that tool and close the panel

const TRACKED_SOURCE_TYPES = new Set([
  'facility_request',
  'tech_request',
  'incident',
  'approval_request',
  'leave_request',
  'certificate',
]);

export function getToolForNotification(notif, userRole) {
  const src = notif.source_record_type || '';

  // Trackable types have a timeline in the detail modal — keep them there
  if (src && TRACKED_SOURCE_TYPES.has(src)) return null;

  // Explicit navigable source types
  if (src === 'fee_transaction') {
    if (userRole === 'student') return 'fee-status-viewer';
    if (userRole === 'admin') return 'fee-tracker';
    return 'fee-collection';
  }
  if (src === 'substitution') return 'substitution-viewer';
  if (src === 'visitor') return 'incident-tracker';
  if (src === 'announcement') {
    if (userRole === 'owner') return 'announcement-broadcaster';
    if (userRole === 'admin') return 'circular-sender';
    return null;
  }

  // Keyword-based for digest / generic notifications (no source_record_type)
  const text = `${notif.title || ''} ${notif.message || ''}`.toLowerCase();

  if (/fee|payment|overdue|due|receipt|defaulter|pending fee/.test(text)) {
    if (userRole === 'student') return 'fee-status-viewer';
    if (userRole === 'admin') return 'fee-tracker';
    return 'fee-collection';
  }
  if (/attendance|absent|present|low attendance/.test(text)) {
    if (userRole === 'student') return 'attendance-self-check';
    if (userRole === 'teacher') return 'class-attendance-marker';
    return 'attendance-overview';
  }
  if (/leave.*approved|leave.*rejected|your leave/.test(text) && userRole === 'teacher') return 'leave-application';
  if (/leave request|leave application/.test(text) && (userRole === 'owner' || userRole === 'admin')) return 'staff-leave-manager';
  if (/announcement|notice|broadcast/.test(text)) {
    if (userRole === 'owner') return 'announcement-broadcaster';
    if (userRole === 'admin') return 'circular-sender';
    return null;
  }
  if (/circular/.test(text) && userRole === 'admin') return 'circular-sender';
  if (/substitut/.test(text) && userRole === 'teacher') return 'substitution-viewer';
  if (/admission|enquiry|enroll/.test(text)) {
    if (userRole === 'owner') return 'admission-funnel';
    if (userRole === 'admin') return 'enquiry-register';
  }
  if (/staff|staffing/.test(text) && (userRole === 'owner' || userRole === 'admin')) return 'staff-tracker';
  if (/financial|expense|revenue/.test(text) && userRole === 'owner') return 'financial-reports';
  if (/alert|anomaly|flag/.test(text)) return 'smart-alerts';
  if (/result|exam|mark|grade/.test(text)) {
    if (userRole === 'student') return 'result-viewer';
    return 'student-performance-viewer';
  }
  if (/assignment|homework/.test(text)) {
    if (userRole === 'student') return 'homework-viewer';
    return 'assignment-generator';
  }
  if (/transport|bus|route/.test(text)) return 'transport-manager';
  if (/incident|visitor/.test(text)) return 'incident-tracker';
  if (/report card/.test(text)) return 'report-card-builder';
  if (/student/.test(text) && (userRole === 'owner' || userRole === 'admin')) return 'student-database';

  return null;
}

export const TOOL_LABELS = {
  'fee-collection': 'Fee Collection',
  'fee-tracker': 'Fee Tracker',
  'fee-status-viewer': 'My Fees',
  'attendance-overview': 'Attendance Overview',
  'attendance-self-check': 'My Attendance',
  'class-attendance-marker': 'Attendance',
  'staff-leave-manager': 'Leave Manager',
  'leave-application': 'Leave Application',
  'announcement-broadcaster': 'Announcements',
  'circular-sender': 'Circulars',
  'admission-funnel': 'Admission Funnel',
  'enquiry-register': 'Enquiry Register',
  'staff-tracker': 'Staff Tracker',
  'financial-reports': 'Financial Reports',
  'smart-alerts': 'Smart Alerts',
  'result-viewer': 'My Results',
  'student-performance-viewer': 'Student Performance',
  'assignment-generator': 'Assignments',
  'homework-viewer': 'Homework',
  'transport-manager': 'Transport',
  'incident-tracker': 'Incidents & Visitors',
  'substitution-viewer': 'Substitutions',
  'report-card-builder': 'Report Cards',
  'student-database': 'Student Database',
};
