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

describe('every profile gets the same tab names, 2026-08-12', () => {
  // Reported live: only Aman's and Adesh's menus were clubbed into tabs. Lalit, Sonu,
  // the office desks, teachers and students all got one long flat list. The decision
  // was that ALL profiles carry the SAME tab names, each showing only what it may
  // already open.
  const { getSidebarTools } = require('../Sidebar');
  const { groupToolsIntoHubs } = require('../../lib/managementHubs');

  const PROFILES = [
    ['management head (Lalit)', { role: 'admin', sub_category: 'management' }],
    ['accountant head (Sonu)', { role: 'admin', sub_category: 'accountant' }],
    ['teacher', { role: 'teacher' }],
    ['student', { role: 'student' }],
  ];

  const { getGroupConfig } = require('../Sidebar');

  // Everywhere a screen can be reached from the menu: the top strip, the contents of
  // each expandable tab, and the contents of each hub tile the profile can open.
  const menuFor = (user) => {
    const tools = getSidebarTools(user);
    const cfg = getGroupConfig(user, tools);
    const insideHubs = MANAGEMENT_HUBS.flatMap(hub => hubItemsForUser(hub, user).map(item => item[0]));
    return new Set([...cfg.top, ...cfg.groups.flatMap(group => group.tools), ...insideHubs]);
  };

  test.each(PROFILES)('%s loses nothing to the regrouping', (_label, user) => {
    // The real risk of clubbing a menu is that a screen falls between two tabs and
    // is never painted again. To the person looking, a screen that vanished from the
    // menu and a screen that was taken away are the same event. Staff Tracker is the
    // live example: it sits in the management head's list and in no hub.
    const tools = getSidebarTools(user);
    const painted = menuFor(user);

    tools.forEach(tool => expect(painted.has(tool.id)).toBe(true));
  });

  test.each(PROFILES)('%s gets a grouped menu, not one long list', (_label, user) => {
    const tools = getSidebarTools(user).filter(t => !MANAGEMENT_HUB_IDS.includes(t.id));
    const { groups } = groupToolsIntoHubs(tools);
    expect(groups.length).toBeGreaterThan(1);
  });

  test.each(PROFILES)('%s uses only the shared tab names, never invented ones', (_label, user) => {
    const tools = getSidebarTools(user).filter(t => !MANAGEMENT_HUB_IDS.includes(t.id));
    const shared = MANAGEMENT_HUBS.map(hub => hub.name);

    groupToolsIntoHubs(tools).groups.forEach(group => {
      expect(shared).toContain(group.name);
    });
  });

  test('grouping never hands anybody a screen they did not already have', () => {
    // The whole point: this rearranges a menu, it does not grant. If a tab ever
    // contains something outside the profile's own resolved list, access has been
    // widened by a layout change, which is the quietest way to break a permission
    // table nobody meant to touch.
    PROFILES.forEach(([, user]) => {
      const tools = getSidebarTools(user).filter(t => !MANAGEMENT_HUB_IDS.includes(t.id));
      const own = new Set(tools.map(t => t.id));
      groupToolsIntoHubs(tools).groups.flatMap(g => g.tools).forEach(id => {
        expect(own.has(id)).toBe(true);
      });
    });
  });

  test('a teacher is not offered fee collection or payroll by the regrouping', () => {
    const tools = getSidebarTools({ role: 'teacher' }).filter(t => !MANAGEMENT_HUB_IDS.includes(t.id));
    const inTabs = groupToolsIntoHubs(tools).groups.flatMap(g => g.tools);
    ['fee-collection', 'payroll-manager', 'audit-log', 'accounting-periods'].forEach(id => {
      expect(inTabs).not.toContain(id);
    });
  });
});
