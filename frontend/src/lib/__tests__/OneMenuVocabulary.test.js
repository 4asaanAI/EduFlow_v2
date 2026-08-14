/**
 * R2-7 - one vocabulary. Everybody in the school navigates by the same nine department
 * names, and sees only the rows their profile grants.
 *
 * Decided 2026-08-10: Sonu and Lalit keep the same department groups Aman and Adesh
 * see, by name. Do not invent per-person group names - one word for one thing across
 * the school, so Releases 3 to 7 slot straight in rather than each adding its own
 * dialect. The problem this fixes was never the names themselves: it was that Sonu got
 * 2 of the 9 groups and Lalit got 18 rows meant for other people.
 *
 * Most of that was settled by R2-1 and R2-5, which made every profile below leadership
 * ask the same grant table. What this file pins is the part that is easy to lose:
 *
 *   1. The names are shared and nobody has a private set.
 *   2. A group with nothing in it does not appear at all, rather than opening onto an
 *      empty page. An empty group is the same defect as a dead button - the person
 *      concludes the platform is broken rather than that the row was not theirs.
 *   3. Every screen a profile is granted is actually reachable from a group. A granted
 *      screen that appears in no group is a screen nobody can find.
 */
import { MANAGEMENT_HUBS, hubsForUser, hubItemsForUser } from '../managementHubs';
import { PROFILE_MATRIX, ALL_SCREENS } from '../profileMatrix.generated';

const EXPECTED_GROUP_NAMES = [
  'School Overview',
  'School Database',
  'Finance',
  'Admissions & Communication',
  'Academics & Activities',
  'People & Attendance',
  'Campus, Library & Assets',
  'Transport',
  'Reports, AI & Governance',
];

const LIVE = {
  owner: { id: 'u-o', role: 'owner', sub_category: 'owner' },
  principal: { id: 'u-p', role: 'admin', sub_category: 'principal' },
  accountant: { id: 'u-a', role: 'admin', sub_category: 'accountant' },
  management: { id: 'u-m', role: 'admin', sub_category: 'management' },
};

test('there are nine department groups and these are their names', () => {
  expect(MANAGEMENT_HUBS.map(h => h.name)).toEqual(EXPECTED_GROUP_NAMES);
});

describe('nobody has a private vocabulary', () => {
  Object.entries(LIVE).forEach(([name, user]) => {
    test(`every group ${name} sees is one of the nine, spelled the same way`, () => {
      hubsForUser(user).forEach((hub) => {
        expect(EXPECTED_GROUP_NAMES).toContain(hub.name);
      });
    });
  });
});

describe('a group with nothing in it is not offered', () => {
  Object.entries(LIVE).forEach(([name, user]) => {
    test(`${name} is never shown an empty group`, () => {
      const empty = hubsForUser(user)
        .filter(hub => hubItemsForUser(hub, user).length === 0)
        .map(hub => hub.name);
      expect(empty).toEqual([]);
    });
  });
});

describe('every granted screen can actually be found in a group', () => {
  const inSomeGroup = new Set(MANAGEMENT_HUBS.flatMap(h => h.items.map(([id]) => id)));
  const groupIds = new Set(MANAGEMENT_HUBS.map(h => h.id));

  // Screens reached from inside another screen rather than from the menu. `staff-tracker`
  // is opened by clicking a colleague's row in the School Directory (owner note,
  // 2026-08-07: "let's just have a single place with all the information rather than 3
  // places"), so it keeps its permission entry and has no menu row of its own by design.
  // Anything added here needs a sentence saying where it IS opened from.
  const OPENED_FROM_ANOTHER_SCREEN = new Set(['staff-tracker']);

  ['accountant', 'management'].forEach((name) => {
    test(`${name}: no granted screen is unreachable from the menu`, () => {
      const screens = PROFILE_MATRIX[name].screens;
      expect(screens).not.toBe(ALL_SCREENS);
      // The group ids are themselves granted as screens (that is how a profile is
      // given a group), so they are not expected to appear inside one.
      const orphans = screens.filter(
        id => !groupIds.has(id) && !inSomeGroup.has(id) && !OPENED_FROM_ANOTHER_SCREEN.has(id),
      );
      expect(orphans).toEqual([]);
    });
  });

  ['accountant', 'management'].forEach((name) => {
    test(`${name}: every group they hold is one they can put something in`, () => {
      const user = LIVE[name];
      const held = hubsForUser(user).map(h => h.id);
      PROFILE_MATRIX[name].screens
        .filter(id => groupIds.has(id))
        .forEach((groupId) => {
          expect(held).toContain(groupId);
        });
    });
  });

  // The sharper version of the same question, and the one that caught the real defect
  // on 2026-08-11: a screen can sit inside a group the profile does NOT hold, in which
  // case the grant is real and the door is missing. The management head was granted
  // seven screens in Reports, AI & Governance and did not hold that group, so Custom
  // Reports, Board Report, Automated Reports, Incidents, Query & Support, Form Builder
  // and Tech Issues were all granted and all unreachable.
  //
  // Holding a group is not the same as seeing everything in it: the rows are filtered
  // one by one, so the four leadership-private screens in that group stay hidden.
  ['accountant', 'management'].forEach((name) => {
    test(`${name}: every granted screen sits in a group they can actually open`, () => {
      const user = LIVE[name];
      const reachable = new Set(
        hubsForUser(user).flatMap(hub => hubItemsForUser(hub, user).map(([id]) => id)),
      );
      const unreachable = PROFILE_MATRIX[name].screens.filter(
        id => !groupIds.has(id)
          && !OPENED_FROM_ANOTHER_SCREEN.has(id)
          && !reachable.has(id),
      );
      expect(unreachable).toEqual([]);
    });
  });
});
