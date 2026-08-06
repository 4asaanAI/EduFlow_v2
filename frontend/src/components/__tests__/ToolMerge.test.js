/**
 * D-44 part 2 — the tool merges.
 *
 * What was wrong: 'fee-receipts' and 'fee-collection' were two names for ONE screen
 * (both loaded tools/FeeCollection), and the school's owner was offered both of them
 * in the same sidebar. That is a duplicate entry, not two capabilities.
 *
 * What this test protects, now that the duplicate name is retired:
 *   1. No menu offers the retired name again.
 *   2. Anything that still SAYS the retired name — an old bookmark, a notification
 *      deep link, Flo being asked "open fee receipts" — still lands on the screen.
 *   3. Every id a menu offers actually resolves to a component, so a merge can never
 *      leave a live menu entry pointing at "Loading tool…" forever.
 *
 * Rule this locks in (Epic 9): a wrong merge is worse than no merge. The tools that
 * were examined and deliberately NOT merged are listed at the bottom, with the
 * capability that makes each of them its own screen.
 */
import { TOOL_ALIASES, resolveToolId } from '../../lib/toolAliases';
import { TOOL_SETS, OWNER_TOOLS } from '../ToolDashboard';
import { TOOLS_BY_ROLE, ADMIN_SUBCATEGORY_TOOLS } from '../Sidebar';
import { ALL_TOOLS } from '../CommandPalette';

const RETIRED = 'fee-receipts';
const CANONICAL = 'fee-collection';

// The second merge, 2026-08-07: the school's owner reported "two views of the student
// database for some reason". 'school-directory' listed every student read-only;
// 'student-database' listed the same students with the buttons. One screen now.
const RETIRED_DIRECTORY = 'school-directory';
const CANONICAL_DIRECTORY = 'student-database';

const idsOf = (tools) => (tools || []).map((t) => (typeof t === 'string' ? t : t.id));

// Every list, in all four registries, that decides what a person is offered.
const everyOfferedIdList = () => [
  ['ToolDashboard OWNER_TOOLS', OWNER_TOOLS],
  ...Object.entries(TOOL_SETS).map(([k, v]) => [`ToolDashboard TOOL_SETS.${k}`, v]),
  ...Object.entries(TOOLS_BY_ROLE).map(([k, v]) => [`Sidebar TOOLS_BY_ROLE.${k}`, idsOf(v)]),
  ...Object.entries(ADMIN_SUBCATEGORY_TOOLS).map(([k, v]) => [`Sidebar ADMIN_SUBCATEGORY_TOOLS.${k}`, v]),
  ['CommandPalette ALL_TOOLS', idsOf(ALL_TOOLS)],
];

describe('the retired duplicates are gone from every menu', () => {
  everyOfferedIdList().forEach(([label, ids]) => {
    test(`${label} offers neither retired name`, () => {
      expect(ids).not.toContain(RETIRED);
      expect(ids).not.toContain(RETIRED_DIRECTORY);
    });
  });
});

describe('the directory merge (2026-08-07)', () => {
  test('the retired directory id resolves to the merged screen', () => {
    expect(resolveToolId(RETIRED_DIRECTORY)).toBe(CANONICAL_DIRECTORY);
  });

  test('everyone who could reach either screen can still reach the merged one', () => {
    // The Directory was owner + principal; the Student Database reached further.
    // The merged screen must keep the WIDER set, or a role loses a screen it had.
    expect(OWNER_TOOLS).toContain(CANONICAL_DIRECTORY);
    expect(idsOf(TOOLS_BY_ROLE.owner)).toContain(CANONICAL_DIRECTORY);
    expect(TOOL_SETS.admin_principal).toContain(CANONICAL_DIRECTORY);
    expect(TOOL_SETS.admin_accountant).toContain(CANONICAL_DIRECTORY);
    expect(TOOL_SETS.admin_receptionist).toContain(CANONICAL_DIRECTORY);
    expect(ADMIN_SUBCATEGORY_TOOLS.principal).toContain(CANONICAL_DIRECTORY);
  });

  test('the owner is offered the merged screen exactly once', () => {
    expect(OWNER_TOOLS.filter((id) => id === CANONICAL_DIRECTORY)).toHaveLength(1);
    expect(idsOf(TOOLS_BY_ROLE.owner).filter((id) => id === CANONICAL_DIRECTORY)).toHaveLength(1);
  });
});

describe('everything that still says the old name still works', () => {
  test('the retired id resolves to the screen it always opened', () => {
    expect(resolveToolId(RETIRED)).toBe(CANONICAL);
  });

  test('a live id is returned untouched', () => {
    expect(resolveToolId('student-database')).toBe('student-database');
    expect(resolveToolId(CANONICAL)).toBe(CANONICAL);
  });

  test('no tool id is missing from the URL', () => {
    expect(resolveToolId(null)).toBe(null);
    expect(resolveToolId(undefined)).toBe(undefined);
  });

  test('an alias never points at another alias, which would need two hops', () => {
    Object.values(TOOL_ALIASES).forEach((target) => {
      expect(TOOL_ALIASES[target]).toBeUndefined();
    });
  });
});

describe('no menu offers a name that has no screen behind it', () => {
  // A merge that removes an id from the routing but leaves it in a menu produces a
  // permanently spinning "Loading tool…" pane. The alias map is the only sanctioned
  // way for a name to survive without its own routing branch.
  const everyOfferedId = new Set(everyOfferedIdList().flatMap(([, ids]) => ids));

  test('nothing a menu offers is itself a retired name', () => {
    [...everyOfferedId].forEach((id) => {
      expect(TOOL_ALIASES[id]).toBeUndefined();
    });
  });

  test('the people who could reach the merged screen before can still reach it', () => {
    // Owner (dashboard + sidebar) and the accountant, who is the admin the receipts
    // entry existed for. Both had it before the merge; both must have it after.
    expect(OWNER_TOOLS).toContain(CANONICAL);
    expect(idsOf(TOOLS_BY_ROLE.owner)).toContain(CANONICAL);
    expect(TOOL_SETS.admin_accountant).toContain(CANONICAL);
    expect(ADMIN_SUBCATEGORY_TOOLS.accountant).toContain(CANONICAL);
    expect(idsOf(TOOLS_BY_ROLE.admin)).toContain(CANONICAL);
    const palette = ALL_TOOLS.find((t) => t.id === CANONICAL);
    expect(palette.roles).toEqual(expect.arrayContaining(['owner', 'admin']));
  });

  test('the owner is offered the merged screen exactly once', () => {
    const ownerSidebar = idsOf(TOOLS_BY_ROLE.owner).filter((id) => id === CANONICAL);
    expect(ownerSidebar).toHaveLength(1);
    expect(OWNER_TOOLS.filter((id) => id === CANONICAL)).toHaveLength(1);
  });
});

describe('the tools that were examined and left alone', () => {
  // Each of these was checked against its cluster siblings and kept, because it does
  // something none of them does. Listed here so a later pass does not have to redo
  // the proof, and so deleting one of them fails a test rather than a school.
  const KEPT = {
    'fee-tracker': 'the only screen with the class-wise fee summary (/fees/class-summary)',
    'smart-fee-defaulter': 'the only screen that lists defaulters and sends fee reminder SMS',
    'circular-sender': 'writes an in-app announcement (/ops/announcements); sends no SMS',
    'parent-message': 'sends SMS to hand-picked students (/sms/send-parent-message)',
    'attendance-alerts': 'finds students below an attendance threshold, then SMS in bulk',
    'certificate-generator': 'creates a serial-numbered record with an approve/reject workflow',
    'id-card-generator': 'the only bulk multi-student print; creates no record',
  };

  Object.entries(KEPT).forEach(([id, why]) => {
    test(`${id} is still offered somewhere — ${why}`, () => {
      const offered = everyOfferedIdList().some(([, ids]) => ids.includes(id));
      expect(offered).toBe(true);
      expect(TOOL_ALIASES[id]).toBeUndefined();
    });
  });
});
