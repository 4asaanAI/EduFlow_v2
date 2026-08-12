/**
 * What sits under "Help & Support" in the account menu.
 *
 * WHY THIS FILE EXISTS. These rows used to be `TOOL_GROUPS[role].bottom` inside
 * Sidebar.js. The 2026-08-05 enterprise release rebuilt the owner and principal
 * navigation around the nine management hubs and set their `bottom` to `[]` - which
 * emptied this menu without anyone noticing, because the menu renders exactly that
 * list and an empty list renders as nothing. Aman reported a Help & Support menu that
 * opens onto nothing (owner request 6, 2026-08-06). The two screens it used to reach,
 * the action log and the query desk, were never removed from the product; only the
 * link to them was.
 *
 * Keeping the answer here, next to a note saying why, is what stops a future
 * navigation rebuild from silently emptying it again.
 *
 * AUDIT LOG IS OWNER AND PRINCIPAL ONLY (owner request 10, 2026-08-06). It is a record
 * of who changed what in the school's data, and Aman asked that nobody else be able to
 * read it. The server enforces the same rule; this only decides what is offered.
 */

import { FilePlus, LifeBuoy, ScrollText, Wrench } from 'lucide-react';

const AUDIT_LOG = { id: 'audit-log', name: 'Audit Log', icon: ScrollText, color: '#737373' };
const QUERY_SECTION = { id: 'query-section', name: 'Query & Support', icon: LifeBuoy, color: '#22d3ee' };
const FORM_SUBMISSIONS = { id: 'form-submissions', name: 'Forms', icon: FilePlus, color: '#22d3ee' };
const RAISE_MAINTENANCE = { id: 'raise-maintenance', name: 'Report an Issue', icon: Wrench, color: '#fb923c' };

export function helpToolsForUser(user) {
  const role = user?.role;
  const sub = user?.sub_category;
  if (role === 'owner') return [AUDIT_LOG, QUERY_SECTION];
  if (role === 'admin') {
    // The principal reads the log; every other office profile gets the query desk
    // only. `it_tech` used to reach the log too - removed with owner request 10.
    return sub === 'principal' ? [AUDIT_LOG, QUERY_SECTION] : [QUERY_SECTION];
  }
  if (role === 'teacher' || role === 'student') return [FORM_SUBMISSIONS, RAISE_MAINTENANCE];
  return [];
}

export default helpToolsForUser;
