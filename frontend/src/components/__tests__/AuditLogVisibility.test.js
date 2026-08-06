/**
 * The action log is owner and principal only (owner request 10, 2026-08-06).
 *
 * There are three places that decide whether the log is OFFERED to someone: the
 * Help & Support menu, the sidebar's admin sub-category allow-list, and the
 * command palette (which goes through `canUseTool`). All three have to agree with
 * `AUDIT_READER_SUB_CATEGORIES` on the server, or a staff member is shown a screen
 * that refuses them when they press it.
 */

import { canUseTool } from '../../lib/toolPermissions';
import { helpToolsForUser } from '../../lib/helpMenu';

const ids = (tools) => tools.map((t) => t.id);

describe('who is offered the audit log', () => {
  it('offers it to the school owner', () => {
    const owner = { role: 'owner', sub_category: 'owner' };
    expect(canUseTool(owner, 'audit-log')).toBe(true);
    expect(ids(helpToolsForUser(owner))).toContain('audit-log');
  });

  it('offers it to the principal', () => {
    const principal = { role: 'admin', sub_category: 'principal' };
    expect(canUseTool(principal, 'audit-log')).toBe(true);
    expect(ids(helpToolsForUser(principal))).toContain('audit-log');
  });

  it.each(['it_tech', 'management', 'accountant', 'receptionist', 'maintenance', 'transport_head'])(
    'does not offer it to the %s profile',
    (sub) => {
      const user = { role: 'admin', sub_category: sub };
      expect(canUseTool(user, 'audit-log')).toBe(false);
      expect(ids(helpToolsForUser(user))).not.toContain('audit-log');
    },
  );

  it.each(['teacher', 'student', 'parent'])('does not offer it to a %s', (role) => {
    const user = { role };
    expect(canUseTool(user, 'audit-log')).toBe(false);
    expect(ids(helpToolsForUser(user))).not.toContain('audit-log');
  });
});
