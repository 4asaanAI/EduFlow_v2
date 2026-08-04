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

const DOCUMENT_ISSUER_ADMIN_SUB_CATEGORIES = ['principal', 'accountant'];

/**
 * May this user be OFFERED this tool?
 *
 * The owner check short-circuits before any sub_category test — the school owner's
 * sub_category is 'owner', so testing it against the admin list would hide the tool
 * from the one person who certainly may use it. Same trap as on the server.
 */
export function canUseTool(user, toolId) {
  if (!DOCUMENT_ISSUER_TOOLS.includes(toolId)) return true;
  if (!user) return false;
  if (user.role === 'owner') return true;
  if (user.role !== 'admin') return false;
  return DOCUMENT_ISSUER_ADMIN_SUB_CATEGORIES.includes(user.sub_category);
}

/** Drop every tool this user may not use. Accepts ids or objects with an `id`. */
export function filterToolsForUser(user, tools) {
  return (tools || []).filter((t) => canUseTool(user, typeof t === 'string' ? t : t?.id));
}
