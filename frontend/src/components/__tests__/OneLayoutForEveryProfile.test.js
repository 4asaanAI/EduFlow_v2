/**
 * R4-6 / decision 9 - one layout, and nothing dropped.
 *
 * There used to be three arrangements: the owner and principal got hubs painted flat,
 * the other office desks got hubs plus a flat tail, teachers and students got tabs. So
 * what somebody learned on one profile did not transfer to the next.
 *
 * The load-bearing test here is `nothing a profile is offered falls out of its menu`.
 * A layout change is only safe if it moves entries around and never loses one: to the
 * person looking, a screen that has quietly gone is identical to access being withdrawn.
 * That rule is what saved Staff Tracker after Release 3 and it has not been relaxed.
 */

import { getSidebarTools, getGroupConfig } from '../Sidebar';
import { PROFILE_MATRIX } from '../../lib/profileMatrix.generated';

const ROLE_NAMED = ['teacher', 'student', 'parent'];

const userFor = (name) => {
  if (name === 'owner') return { id: 'u-owner', role: 'owner', sub_category: 'owner' };
  if (ROLE_NAMED.includes(name)) return { id: `u-${name}`, role: name };
  return { id: `u-${name}`, role: 'admin', sub_category: name };
};

const PROFILES = Object.keys(PROFILE_MATRIX);

const idsInLayout = (config) => new Set([
  ...(config.top || []),
  ...(config.groups || []).flatMap(group => group.tools || []),
]);

describe('one layout for every profile', () => {
  test('there are profiles to check at all', () => {
    // A sweep that silently iterates nothing passes every assertion below.
    expect(PROFILES.length).toBeGreaterThanOrEqual(12);
  });

  PROFILES.forEach((name) => {
    describe(name, () => {
      const user = userFor(name);
      const tools = getSidebarTools(user);
      const config = getGroupConfig(user, tools);

      test('nothing a profile is offered falls out of its menu', () => {
        const offered = new Set(tools.map(tool => tool.id));
        const shown = idsInLayout(config);
        const missing = [...offered].filter(id => !shown.has(id));
        expect(missing).toEqual([]);
      });

      test('the menu shows nothing the profile was not offered', () => {
        // Grouping never grants. A tab may only rearrange what the profile already has.
        const offered = new Set(tools.map(tool => tool.id));
        const extra = [...idsInLayout(config)].filter(id => !offered.has(id));
        expect(extra).toEqual([]);
      });

      test('uses the same arrangement as everybody else', () => {
        // One layout means one shape: tabs, never a flat ribbon of top-level entries.
        expect(config.top).toEqual([]);
        if (tools.length) expect(config.groups.length).toBeGreaterThan(0);
      });

      test('no screen is listed in two places', () => {
        const all = (config.groups || []).flatMap(group => group.tools || []);
        expect(all.length).toBe(new Set(all).size);
      });

      test('every tab has a name and at least one screen', () => {
        (config.groups || []).forEach((group) => {
          expect(group.name).toBeTruthy();
          expect((group.tools || []).length).toBeGreaterThan(0);
        });
      });

      test('no leftovers tab, because every screen has a home', () => {
        // Abhimanyu, 2026-08-14: the "More" tab held exactly one screen, Staff Tracker,
        // and a whole tab holding one entry reads as a drawer rather than a place. It was
        // removed by giving that screen a home in People & Attendance.
        //
        // The fallback in `getGroupConfig` STAYS, because deleting it would mean the next
        // tool with no hub silently disappears from the menu, which to the person looking
        // is identical to access being taken away. This test is what keeps the net empty:
        // it fails on the tool, at the moment it is added, naming it.
        const leftovers = (config.groups || []).find(group => group.id === 'more');
        expect(leftovers?.tools || []).toEqual([]);
      });
    });
  });
});

/**
 * R3-2, 2026-08-15 - the home page and the sidebar have to offer the same screens.
 *
 * The sweep above checks the SIDEBAR. The home page is built separately, in
 * `ToolDashboard.js`, and for the four still-dormant office desks it is built from a
 * hand-written list of screen ids that nothing keeps in step with the permission table.
 *
 * That list is intersected with the table, so it can only ever take away, never grant.
 * But taking away silently is the harm: the moment R3-2 gave the transport head the
 * servicing calendar and the contractor list, his sidebar offered eight screens and his
 * home page showed five, and to the person looking a screen that has quietly gone is
 * identical to access being withdrawn.
 *
 * He was moved onto `hubsForUser`, which asks the grant table the same question the
 * sidebar asks. This is what stops the two drifting apart again, for him and for each of
 * the remaining four as their own release lands.
 */
describe('the home page offers what the sidebar offers', () => {
  const LIVE = Object.keys(PROFILE_MATRIX).filter(
    (name) => PROFILE_MATRIX[name].status === 'live' && PROFILE_MATRIX[name].screens !== '__all_screens__'
  );

  test('there are live profiles to check', () => {
    expect(LIVE).toContain('transport_head');
  });

  LIVE.forEach((name) => {
    test(`${name} loses nothing between the two`, () => {
      const user = userFor(name);
      const sidebar = new Set(getSidebarTools(user).map((tool) => tool.id));
      const granted = PROFILE_MATRIX[name].screens;

      // Every screen the table grants reaches the sidebar...
      const missingFromSidebar = granted.filter((id) => !sidebar.has(id));
      expect(missingFromSidebar).toEqual([]);

      // ...and lands inside a hub, which is what the home page paints. A screen in no
      // hub at all would vanish from the home page while still showing in the sidebar,
      // which is the exact drift this test exists to catch.
      // Hub rows are [id, name, subtitle, audience] tuples, and a hub id is itself a
      // screen a profile can be granted, so both count as a home.
      // eslint-disable-next-line global-require
      const { MANAGEMENT_HUBS } = require('../../lib/managementHubs');
      const inSomeHub = new Set([
        ...MANAGEMENT_HUBS.map((hub) => hub.id),
        ...MANAGEMENT_HUBS.flatMap((hub) => (hub.items || []).map((row) => row[0])),
      ]);
      // Staff Tracker is the ONE screen deliberately in a sidebar and on no home page.
      // The owner asked on 2026-08-07 for a single directory rather than three, so it is
      // placed through the tab map, which decides sidebar position without painting a
      // landing-page tile. Named here rather than allowed by a loosened rule, so the NEXT
      // screen to go missing is still caught.
      const DELIBERATELY_NOT_ON_A_HOME_PAGE = ['staff-tracker'];
      const homeless = granted
        .filter((id) => !inSomeHub.has(id))
        .filter((id) => !DELIBERATELY_NOT_ON_A_HOME_PAGE.includes(id));
      expect(homeless).toEqual([]);
    });
  });
});
