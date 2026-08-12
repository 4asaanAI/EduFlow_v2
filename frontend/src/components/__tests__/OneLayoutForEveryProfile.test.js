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
    });
  });
});
