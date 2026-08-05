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

  test('preserve access to every legacy owner and principal destination through a hub', () => {
    const ownerItems = new Set(MANAGEMENT_HUBS.flatMap(hub => hubItemsForUser(hub, { role: 'owner' }).map(item => item[0])));
    const principalItems = new Set(MANAGEMENT_HUBS.flatMap(hub => hubItemsForUser(hub, { role: 'admin', sub_category: 'principal' }).map(item => item[0])));
    ['student-database', 'fee-collection', 'library-circulation', 'school-activities', 'audit-log'].forEach(id => expect(ownerItems.has(id)).toBe(true));
    ['student-database', 'enquiry-register', 'library-circulation', 'transport-manager', 'audit-log'].forEach(id => expect(principalItems.has(id)).toBe(true));
    expect(OWNER_TOOLS.filter(id => !ownerItems.has(id))).toEqual([]);
    expect(TOOL_SETS.admin_principal.filter(id => !principalItems.has(id))).toEqual([]);
  });

  test('keeps owner-only financial and settings screens out of principal hubs', () => {
    const principalItems = new Set(MANAGEMENT_HUBS.flatMap(hub => hubItemsForUser(hub, { role: 'admin', sub_category: 'principal' }).map(item => item[0])));
    expect(principalItems.has('financial-reports')).toBe(false);
    expect(principalItems.has('payroll-manager')).toBe(false);
    expect(principalItems.has('school-settings')).toBe(false);
  });
});
