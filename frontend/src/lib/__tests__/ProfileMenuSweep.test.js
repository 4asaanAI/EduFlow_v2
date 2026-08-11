/**
 * R2-13 — the menu half of the all-nine-profile sweep.
 *
 * The Flo-tool and API-route halves are
 * `tests/backend/unit/test_all_nine_profiles_sweep_r2_13.py`. This is the third
 * surface: what each profile is OFFERED in the menus.
 *
 * NINE profiles, not the four in this release. A sweep covering only the profiles
 * under discussion cannot see the other five being silently stripped or widened.
 *
 * WHAT FAILS THIS FILE, on purpose:
 *   - adding a screen and forgetting to say who it belongs to (default deny means it
 *     reaches nobody, which is safe but is still somebody's screen going missing);
 *   - a profile's menu changing without anyone deciding to change it;
 *   - the checked-in matrix mirror going stale.
 */
import { canUseTool, filterToolsForUser, canSeeMoney } from '../toolPermissions';
import { PROFILE_MATRIX, ALL_SCREENS, LIVE_PROFILES, DORMANT_PROFILES } from '../profileMatrix.generated';

const userFor = (name) => (
  name === 'owner'
    ? { id: 'u-owner', role: 'owner', sub_category: 'owner' }
    : { id: `u-${name}`, role: 'admin', sub_category: name }
);

const PROFILE_NAMES = Object.keys(PROFILE_MATRIX);

// What each profile is offered today. A number moving here is not a test to silence:
// it means somebody's menu changed. If you meant it, update the number and say why in
// the commit message and in PROGRESS.md.
const EXPECTED_SCREEN_COUNT = {
  owner: ALL_SCREENS,
  principal: ALL_SCREENS,
  // 23 until 2026-08-11; +2 = the certificate and ID-card screens Abhimanyu gave the
  // accountant head, which he may open and request from but not issue (R2-9).
  accountant: 25,
  // 48 until 2026-08-11. +1 governance-ai-hub (the group holding seven screens he was
  // granted and could not reach), -2 board-report and custom-report-builder (both carry
  // money, decision 1). See the named tests below.
  management: 47,
  transport_head: 6,
  receptionist: 9,
  it_tech: 4,
  maintenance: 3,
  support_staff: 2,
};

test('all nine profiles are in the matrix, four live and five dormant', () => {
  expect(PROFILE_NAMES.length).toBe(9);
  expect(LIVE_PROFILES.sort()).toEqual(['accountant', 'management', 'owner', 'principal']);
  expect(DORMANT_PROFILES.length).toBe(5);
});

test('the matrix is default deny — an unknown screen reaches nobody but leadership', () => {
  // Leadership holds everything by design, so it is the one exception. Every other
  // profile must refuse a screen nobody has granted it, which is what stops a screen
  // built next month landing in the management head's menu silently.
  PROFILE_NAMES.forEach((name) => {
    const allowed = canUseTool(userFor(name), 'a-screen-nobody-has-granted-anyone');
    if (PROFILE_MATRIX[name].screens === ALL_SCREENS) {
      expect(allowed).toBe(true);
    } else {
      expect(allowed).toBe(false);
    }
  });
});

test('an admin desk we do not recognise is refused everything', () => {
  const stranger = { id: 'x', role: 'admin', sub_category: 'not_a_real_desk' };
  expect(canUseTool(stranger, 'student-database')).toBe(false);
  expect(canSeeMoney(stranger)).toBe(false);
});

test('a teacher or student keeps their own menu and is not caught by this table', () => {
  // They are not in the matrix; their screens come from their own role lists. Refusing
  // them here would empty a teacher's sidebar.
  expect(canUseTool({ role: 'teacher' }, 'class-attendance-marker')).toBe(true);
  expect(canUseTool({ role: 'student' }, 'ai-tutor')).toBe(true);
  // Except the three office-desk screens whose server routes refuse them outright.
  expect(canUseTool({ role: 'teacher' }, 'certificate-generator')).toBe(false);
  expect(canUseTool({ role: 'teacher' }, 'audit-log')).toBe(false);
});

describe.each(PROFILE_NAMES)('%s', (name) => {
  const user = userFor(name);
  const entry = PROFILE_MATRIX[name];

  test('is offered exactly what the matrix grants it', () => {
    if (entry.screens === ALL_SCREENS) {
      expect(canUseTool(user, 'anything-at-all')).toBe(true);
      return;
    }
    entry.screens.forEach((id) => expect(canUseTool(user, id)).toBe(true));
    expect(filterToolsForUser(user, entry.screens)).toHaveLength(entry.screens.length);
  });

  test('its menu has not changed by accident', () => {
    const expected = EXPECTED_SCREEN_COUNT[name];
    if (expected === ALL_SCREENS) {
      expect(entry.screens).toBe(ALL_SCREENS);
      return;
    }
    expect(entry.screens).toHaveLength(expected);
  });

  test('sees money only if it holds the finance domain', () => {
    expect(canSeeMoney(user)).toBe(entry.toolDomains.includes('finance'));
  });

  test('a dormant profile can write nothing and remove nobody', () => {
    if (entry.status !== 'dormant') return;
    expect(entry.mayWrite).toBe(false);
    expect(entry.mayDeletePeople).toBe(false);
    expect(entry.toolDomains).toEqual([]);
  });
});

test('only the school owner and the principal may take a person off the roll', () => {
  const allowed = PROFILE_NAMES.filter((n) => PROFILE_MATRIX[n].mayDeletePeople);
  expect(allowed.sort()).toEqual(['owner', 'principal']);
});

test('the management head is offered no finance screen at all', () => {
  const FINANCE_SCREENS = [
    'finance-commercial-hub', 'fee-collection', 'fee-sync', 'fee-tracker',
    'smart-fee-defaulter', 'financial-reports', 'accounting-periods',
    'payroll-manager', 'expense-tracker',
  ];
  FINANCE_SCREENS.forEach((id) => {
    expect(canUseTool(userFor('management'), id)).toBe(false);
  });
});

test('the management head is offered no leadership-private screen', () => {
  // R2-7, 2026-08-11: 'governance-ai-hub' came OFF this list. It is the department
  // GROUP, not a screen — the four screens above are what is private, and holding the
  // group does not reveal them because the rows inside are filtered one by one. While
  // the group was on this list the management head was granted seven screens that live
  // inside it and could open none of them: the grant was real and the door was missing.
  ['audit-log', 'what-ive-learned', 'conversation-trace', 'ai-health-report']
    .forEach((id) => expect(canUseTool(userFor('management'), id)).toBe(false));
});

test('holding the governance group still hides the four private screens inside it', () => {
  expect(canUseTool(userFor('management'), 'governance-ai-hub')).toBe(true);
  ['audit-log', 'what-ive-learned', 'conversation-trace', 'ai-health-report']
    .forEach((id) => expect(canUseTool(userFor('management'), id)).toBe(false));
});

test('the management head is offered no money-bearing report screen', () => {
  // Removed 2026-08-11. Board Report totals the school's expenses; Custom Reports
  // offers Fee Transactions and Expenses as data sources. Decision 1: he never sees a
  // rupee figure.
  ['board-report', 'custom-report-builder']
    .forEach((id) => expect(canUseTool(userFor('management'), id)).toBe(false));
});

test('the management head is not offered the school settings screen', () => {
  // It is a dead button for him: the screen is backed by update_school_settings, which
  // the registry marks owner-only and which R2-3 refuses him.
  expect(canUseTool(userFor('management'), 'school-settings')).toBe(false);
});
