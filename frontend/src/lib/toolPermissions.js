/**
 * Who may be OFFERED which screen.
 *
 * R2-1 (2026-08-10): this module used to grant access by SUBTRACTION. "Management"
 * meant *everything not tagged finance*, and anything a profile was not explicitly
 * refused, it got — the last line of the old `canUseTool` was `return true`. That is
 * how the management head came to be offered the school settings screen, and it is
 * why every screen built next month would have landed in his menu silently.
 *
 * It now reads one grant table, `backend/services/profile_matrix.py`, through its
 * checked-in mirror `profileMatrix.generated.js`. The table is **default deny**: a
 * profile that is not in it, or a screen that is not named for that profile, is
 * refused. Adding a screen now requires somebody to decide who owns it.
 *
 * The server is still the real gate — this only decides what is offered. The two
 * must agree, and R2-13's sweep is what proves they do.
 *
 * D-49 (closed 2026-08-04) is the reason this module exists at all: the menus offered
 * Certificates and ID Cards to more staff than `backend/routes/image_gen.py` accepts,
 * so a receptionist could open the tool and then be refused when they pressed the
 * button. Four places built their own tool list and drifted apart. This is the one
 * copy. That rule now lives in the matrix, in each profile's `screens` list, rather
 * than in a separate exception map.
 *
 * Server rule being mirrored (owner decision 2026-08-04, decision 2):
 *   POST /api/image-gen/certificate and /api/image-gen/id-cards are allowed for the
 *   school's owner, admin+principal, and admin+management. Nobody else.
 *   Backend helper: `middleware.auth.require_owner_principal_or_accountant`.
 */

import { ALL_SCREENS, PROFILE_MATRIX } from './profileMatrix.generated';

// Tools whose server route refuses anyone outside a named set of profiles. Kept as a
// named export because other modules import it to explain a refusal to the user.
export const DOCUMENT_ISSUER_TOOLS = ['certificate-generator', 'id-card-generator'];

export const FINANCE_TOOL_IDS = new Set([
  'finance-commercial-hub', 'fee-collection', 'fee-sync', 'fee-tracker',
  'smart-fee-defaulter', 'financial-reports', 'accounting-periods',
  'payroll-manager', 'expense-tracker', 'commercial-operations',
]);

/**
 * Screens no one outside the matrix may ever be offered, whatever their role.
 *
 * The matrix answers for the school's owner and the eight admin desks. It says
 * nothing about teachers, students and guardians, who have their own role lists — so
 * those roles are passed through rather than refused, or a teacher's sidebar would
 * come back empty. These three screens are the exception: their server routes accept
 * only a named set of office profiles, so offering them to a teacher or a student
 * produces a button that answers "no".
 *
 *   certificate-generator, id-card-generator — D-49, `routes/image_gen.py`
 *   audit-log — owner request 10, 2026-08-06, `routes/audit.py`
 */
const OFFICE_DESK_ONLY_TOOLS = new Set([...DOCUMENT_ISSUER_TOOLS, 'audit-log']);

/**
 * Which matrix row governs this user, or null if none does.
 *
 * The school's owner carries role 'owner'; everyone else in the table is an 'admin'
 * told apart by sub_category. Teachers, students and guardians are not in this table
 * and are handled by their own role lists.
 */
function profileOf(user) {
  if (!user) return null;
  if (user.role === 'owner') return 'owner';
  if (user.role !== 'admin') return null;
  return PROFILE_MATRIX[user.sub_category] ? user.sub_category : null;
}

/**
 * May this user be OFFERED this screen?
 *
 * Default deny. Note the owner check resolves before any sub_category test — the
 * school owner's sub_category is 'owner', so testing it against an admin list would
 * hide the screen from the one person who certainly may use it. Same trap as on the
 * server.
 *
 * Roles outside the matrix (teacher, student, parent) are not this module's business:
 * their menus come from their own role lists, so they are passed through rather than
 * refused. Refusing them here would empty a teacher's sidebar.
 */
export function canUseTool(user, toolId) {
  if (!user) return false;
  const profile = profileOf(user);
  if (!profile) {
    // Not an owner and not a recognised admin sub-category. An admin whose
    // sub_category we do not recognise is refused (that is the default-deny half);
    // a teacher or student falls through to their own role list.
    if (user.role === 'admin') return false;
    return !OFFICE_DESK_ONLY_TOOLS.has(toolId);
  }
  const { screens } = PROFILE_MATRIX[profile];
  if (screens === ALL_SCREENS) return true;
  return screens.includes(toolId);
}

/** Drop every tool this user may not use. Accepts ids or objects with an `id`. */
export function filterToolsForUser(user, tools) {
  return (tools || []).filter((t) => canUseTool(user, typeof t === 'string' ? t : t?.id));
}
