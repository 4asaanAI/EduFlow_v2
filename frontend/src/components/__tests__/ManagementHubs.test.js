import { MANAGEMENT_HUBS, MANAGEMENT_HUB_IDS, hubItemsForUser } from '../../lib/managementHubs';
import { OWNER_TOOLS, TOOL_SETS } from '../ToolDashboard';

describe('owner and principal management hubs', () => {
  test('replace dozens of top-level destinations with nine clear divisions', () => {
    expect(MANAGEMENT_HUB_IDS).toHaveLength(9);
    expect(MANAGEMENT_HUB_IDS.length).toBeLessThan(OWNER_TOOLS.length / 2);
    expect(MANAGEMENT_HUB_IDS.length).toBeLessThan(TOOL_SETS.admin_principal.length / 2);
  });

  test('cover the divisions school leaders use to find information', () => {
    const names = MANAGEMENT_HUBS.map(hub => hub.name);
    expect(names).toEqual(expect.arrayContaining([
      'School Database', 'Finance & Campus Sales', 'Admissions & Communication',
      'Academics & Activities', 'Campus, Library & Assets', 'Transport',
    ]));
  });

  // Owner note, 2026-08-07: "school directory could be the sole directory... let's
  // just have single place with all the information rather than 3 places". The two
  // duplicate tiles were removed from the School Database hub. They are NOT stranded:
  // the Directory lists everybody and carries a button through to each full screen,
  // which is where adding, restoring and erasing still live.
  //
  // They are listed here by name rather than the guard being loosened, so a future
  // navigation change still has to justify anything else it drops.
  // Updated 2026-08-07 when the merge actually landed: 'school-directory' and
  // 'student-database' were two screens listing the same students, and are now one,
  // under the id 'student-database' and the name "School Directory". So the directory
  // IS the student-database tile, and only Staff Tracker is reached through it.
  const REACHED_THROUGH_THE_DIRECTORY = ['staff-tracker'];
  const DIRECTORY = 'student-database';

  test('preserve access to every legacy owner and principal destination through a hub', () => {
    const ownerItems = new Set(MANAGEMENT_HUBS.flatMap(hub => hubItemsForUser(hub, { role: 'owner' }).map(item => item[0])));
    const principalItems = new Set(MANAGEMENT_HUBS.flatMap(hub => hubItemsForUser(hub, { role: 'admin', sub_category: 'principal' }).map(item => item[0])));
    [DIRECTORY, 'fee-collection', 'library-circulation', 'school-activities', 'audit-log'].forEach(id => expect(ownerItems.has(id)).toBe(true));
    [DIRECTORY, 'enquiry-register', 'library-circulation', 'transport-manager', 'audit-log'].forEach(id => expect(principalItems.has(id)).toBe(true));
    const reachable = (set) => (id) => set.has(id) || REACHED_THROUGH_THE_DIRECTORY.includes(id);
    expect(OWNER_TOOLS.filter(id => !reachable(ownerItems)(id))).toEqual([]);
    expect(TOOL_SETS.admin_principal.filter(id => !reachable(principalItems)(id))).toEqual([]);
  });

  test('the merged directory is the only front door to student and staff records', () => {
    const ownerItems = new Set(MANAGEMENT_HUBS.flatMap(hub => hubItemsForUser(hub, { role: 'owner' }).map(item => item[0])));
    // One tile, not three. This is the thing the owner actually asked for, so it is
    // asserted rather than left to be undone by the next person tidying the hub.
    expect(ownerItems.has(DIRECTORY)).toBe(true);
    REACHED_THROUGH_THE_DIRECTORY.forEach(id => expect(ownerItems.has(id)).toBe(false));
  });

  test('gives the reviewed principal full finance and settings access', () => {
    const principalItems = new Set(MANAGEMENT_HUBS.flatMap(hub => hubItemsForUser(hub, { role: 'admin', sub_category: 'principal' }).map(item => item[0])));
    expect(principalItems.has('financial-reports')).toBe(true);
    expect(principalItems.has('payroll-manager')).toBe(true);
    expect(principalItems.has('school-settings')).toBe(true);
  });
});
