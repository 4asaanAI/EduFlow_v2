/**
 * Who may see which tool, where the menus and the server have to agree.
 *
 * D-49 (closed 2026-08-04): the menus offered Certificates and ID Cards to more
 * staff than `backend/routes/image_gen.py` accepts, so a receptionist could open
 * the tool and then be refused when they pressed the button. The four places that
 * build a tool list (Sidebar, ToolDashboard, CommandPalette, and the sidebar's
 * grouped navigation) each had their own copy of the answer, which is exactly how
 * they drifted apart. This module is the one copy.
 *
 * The server is still the real gate — this only decides what is offered.
 *
 * Server rule being mirrored (owner decision 2026-08-04, decision 2):
 *   POST /api/image-gen/certificate and /api/image-gen/id-cards are allowed for
 *   the school's owner, admin+principal, and admin+accountant. Nobody else.
 *   Backend helper: `middleware.auth.require_owner_principal_or_accountant`.
 */

// Tools whose server route refuses anyone outside a named set of profiles.
// Anything not listed here is unrestricted as far as this module is concerned.
export const DOCUMENT_ISSUER_TOOLS = ['certificate-generator', 'id-card-generator'];

export const FINANCE_TOOL_IDS = new Set([
  'finance-commercial-hub', 'fee-collection', 'fee-sync', 'fee-tracker',
  'smart-fee-defaulter', 'financial-reports', 'accounting-periods',
  'payroll-manager', 'expense-tracker', 'commercial-operations',
]);

const FINANCE_SHARED_TOOL_IDS = new Set(['school-database-hub', 'student-database']);
const LEADERSHIP_ONLY_TOOL_IDS = new Set([
  'audit-log', 'what-ive-learned', 'conversation-trace', 'ai-health-report',
  'governance-ai-hub',
]);

const DOCUMENT_ISSUER_ADMIN_SUB_CATEGORIES = ['principal', 'management'];

/**
 * Admin sub-categories allowed per restricted tool.
 *
 * `audit-log` — owner request 10, 2026-08-06. The action log is a record of who
 * changed what in the school's data, and Aman asked that only the owner and the
 * principal be able to read it. The server enforces the same list in
 * `backend/routes/audit.py` (`AUDIT_READER_SUB_CATEGORIES`); the Help & Support
 * menu applies it separately in `helpMenu.js`. Offering it to an `it_tech` or
 * `management` profile now only produces a refusal when they press it.
 */
const RESTRICTED_TOOL_ADMIN_SUB_CATEGORIES = {
  'certificate-generator': DOCUMENT_ISSUER_ADMIN_SUB_CATEGORIES,
  'id-card-generator': DOCUMENT_ISSUER_ADMIN_SUB_CATEGORIES,
  'audit-log': ['principal'],
};

/**
 * May this user be OFFERED this tool?
 *
 * The owner check short-circuits before any sub_category test — the school owner's
 * sub_category is 'owner', so testing it against the admin list would hide the tool
 * from the one person who certainly may use it. Same trap as on the server.
 */
export function canUseTool(user, toolId) {
  if (!user) return false;
  if (user.role === 'owner') return true;
  if (user.role === 'admin' && user.sub_category === 'principal') return true;
  if (user.role === 'admin' && user.sub_category === 'accountant') {
    return FINANCE_TOOL_IDS.has(toolId) || FINANCE_SHARED_TOOL_IDS.has(toolId);
  }
  if (user.role === 'admin' && user.sub_category === 'management') {
    return !FINANCE_TOOL_IDS.has(toolId) && !LEADERSHIP_ONLY_TOOL_IDS.has(toolId);
  }

  const allowedSubs = RESTRICTED_TOOL_ADMIN_SUB_CATEGORIES[toolId];
  if (!allowedSubs) return true;
  if (user.role !== 'admin') return false;
  return allowedSubs.includes(user.sub_category);
}

/** Drop every tool this user may not use. Accepts ids or objects with an `id`. */
export function filterToolsForUser(user, tools) {
  return (tools || []).filter((t) => canUseTool(user, typeof t === 'string' ? t : t?.id));
}
