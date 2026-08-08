/**
 * D-49 — the menus must offer Certificates and ID Cards to exactly the people the
 * server lets use them, and nobody else.
 *
 * The bug being locked down: a receptionist saw the ID Cards button, opened it, and
 * was refused when they pressed Generate. Four separate places build tool lists
 * (the sidebar's flat list, the sidebar's sub-role allow-lists, the tool dashboard,
 * and the ⌘K palette), each with its own copy of the answer.
 *
 * The reviewed profile rule: school owner, admin+principal, and admin+management.
 * Accountant is finance-only. It is restated here in ONE place and every menu is checked
 * against it, so a menu can no longer drift on its own.
 */
import { canUseTool, DOCUMENT_ISSUER_TOOLS } from '../../lib/toolPermissions';
import { TOOL_SETS, OWNER_TOOLS } from '../ToolDashboard';
import { TOOLS_BY_ROLE, ADMIN_SUBCATEGORY_TOOLS, getSidebarTools } from '../Sidebar';
import { ALL_TOOLS } from '../CommandPalette';

// Every admin sub_category the platform recognises — the same list as
// SUB_CATEGORIES_BY_ROLE['admin'] in backend/middleware/auth.py.
const ADMIN_SUB_CATEGORIES = [
  'principal', 'accountant', 'transport_head', 'receptionist',
  'it_tech', 'maintenance', 'management', 'support_staff',
];

const ALLOWED_PROFILES = [
  { id: 'u-owner', role: 'owner', sub_category: 'owner' },
  { id: 'u-principal', role: 'admin', sub_category: 'principal' },
  { id: 'u-management', role: 'admin', sub_category: 'management' },
];

const REFUSED_PROFILES = [
  ...ADMIN_SUB_CATEGORIES
    .filter(sc => sc !== 'principal' && sc !== 'management')
    .map(sc => ({ id: `u-${sc}`, role: 'admin', sub_category: sc })),
  { id: 'u-admin-none', role: 'admin' },              // admin with no sub_category
  { id: 'u-teacher', role: 'teacher', sub_category: 'class_teacher' },
  { id: 'u-student', role: 'student', sub_category: 'student' },
];

describe('the shared permission check mirrors the server gate', () => {
  ALLOWED_PROFILES.forEach((user) => {
    DOCUMENT_ISSUER_TOOLS.forEach((toolId) => {
      test(`${user.role}/${user.sub_category || '-'} may be offered ${toolId}`, () => {
        expect(canUseTool(user, toolId)).toBe(true);
      });
    });
  });

  REFUSED_PROFILES.forEach((user) => {
    DOCUMENT_ISSUER_TOOLS.forEach((toolId) => {
      test(`${user.role}/${user.sub_category || '-'} is not offered ${toolId}`, () => {
        expect(canUseTool(user, toolId)).toBe(false);
      });
    });
  });

  test('an unrelated tool is not affected by this check', () => {
    expect(canUseTool({ role: 'admin', sub_category: 'receptionist' }, 'student-database')).toBe(true);
  });
});

const idsOf = (tools) => tools.map(t => (typeof t === 'string' ? t : t.id));

describe('the sidebar never offers a document tool to someone the server refuses', () => {
  // One-directional on purpose. "Refused ⇒ absent" is the property that closes D-49.
  // The reverse is NOT asserted for every profile, because the school owner does not
  // use the flat sidebar list at all (their tools come from the dashboard set below),
  // so "allowed ⇒ present" is only true where the sidebar is that person's menu.
  REFUSED_PROFILES.forEach((user) => {
    const label = `${user.role}/${user.sub_category || '-'}`;
    DOCUMENT_ISSUER_TOOLS.forEach((toolId) => {
      test(`${label} is not offered ${toolId}`, () => {
        expect(idsOf(getSidebarTools(user))).not.toContain(toolId);
      });
    });
  });

  ['principal', 'management'].forEach((sub) => {
    DOCUMENT_ISSUER_TOOLS.forEach((toolId) => {
      test(`the ${sub} IS offered ${toolId}`, () => {
        expect(idsOf(getSidebarTools({ id: `u-${sub}`, role: 'admin', sub_category: sub })))
          .toContain(toolId);
      });
    });
  });

  test('the sub-role allow-lists themselves carry no forbidden entry', () => {
    Object.entries(ADMIN_SUBCATEGORY_TOOLS).forEach(([sub, ids]) => {
      DOCUMENT_ISSUER_TOOLS.forEach((toolId) => {
        if (ids.includes(toolId)) {
          expect(canUseTool({ role: 'admin', sub_category: sub }, toolId)).toBe(true);
        }
      });
    });
  });

  test('no non-admin role list carries a document tool', () => {
    ['teacher', 'student'].forEach((role) => {
      DOCUMENT_ISSUER_TOOLS.forEach((toolId) => {
        expect(idsOf(TOOLS_BY_ROLE[role])).not.toContain(toolId);
      });
    });
  });
});

describe('the tool dashboard sets match the server gate', () => {
  test('the owner set offers both document tools', () => {
    DOCUMENT_ISSUER_TOOLS.forEach((toolId) => {
      expect(OWNER_TOOLS).toContain(toolId);
    });
  });

  test('only the principal and management admin sets carry them', () => {
    Object.entries(TOOL_SETS).forEach(([key, ids]) => {
      if (!key.startsWith('admin_')) return;
      const sub = key.slice('admin_'.length);
      DOCUMENT_ISSUER_TOOLS.forEach((toolId) => {
        expect(ids.includes(toolId)).toBe(canUseTool({ role: 'admin', sub_category: sub }, toolId));
      });
    });
  });

  test('the receptionist set no longer offers ID Cards', () => {
    expect(TOOL_SETS.admin_receptionist).not.toContain('id-card-generator');
  });
});

describe('the command palette gates on sub_category, not role alone', () => {
  const paletteFor = (user) => ALL_TOOLS
    .filter(t => t.roles.includes(user.role))
    .filter(t => canUseTool(user, t.id))
    .map(t => t.id);

  [...ALLOWED_PROFILES, ...REFUSED_PROFILES].forEach((user) => {
    const label = `${user.role}/${user.sub_category || '-'}`;
    DOCUMENT_ISSUER_TOOLS.forEach((toolId) => {
      test(`${label} → ${toolId}`, () => {
        expect(paletteFor(user).includes(toolId)).toBe(canUseTool(user, toolId));
      });
    });
  });
});
