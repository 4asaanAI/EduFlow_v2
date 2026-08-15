/**
 * R3-2, 2026-08-15 - the one rule that splits approvals from ordinary notifications.
 *
 * Abhimanyu, 2026-08-15: approvals of any kind reach Aman and Adesh separately, and the
 * bell and the notifications screen are both split into the two.
 *
 * Two surfaces read this: the bell dropdown in `Header.js` and the All Notifications
 * screen. They fetch separately and render separately, so if they classified separately
 * the bell's count and the screen's rows would drift and a person would be told two
 * different things about the same inbox. This file is what pins the rule they share.
 */

import { isDecisionNotification, splitByKind, DECISION_NOTIFICATION_TYPES } from '../notifKinds';

describe('what counts as waiting on your decision', () => {
  test('the three kinds that ask somebody to decide', () => {
    // Taken from the server, not guessed: these are the only notification types the
    // backend writes that mean "you have to decide something".
    expect([...DECISION_NOTIFICATION_TYPES].sort()).toEqual([
      'approval_submitted',
      'certificate_approval_requested',
      'profile_change_request',
    ]);
  });

  test.each([
    'approval_submitted',
    'certificate_approval_requested',
    'profile_change_request',
  ])('%s is an approval', (type) => {
    expect(isDecisionNotification({ type })).toBe(true);
  });

  test.each([
    // These all LOOK like approvals by name and are not. Every one is an OUTCOME:
    // somebody else already decided, and telling a person the answer is news, not a task.
    // Getting this wrong is what makes a "things waiting on you" count overstate, and a
    // count that overstates is one people learn to ignore.
    'approval_decision',
    'certificate_approved',
    'certificate_rejected',
    'announcement_rejected',
    'leave_decision',
    'student_leave_decision',
    'profile_change_decision',
  ])('%s is NOT an approval, it is an outcome', (type) => {
    expect(isDecisionNotification({ type })).toBe(false);
  });

  test('an unknown kind lands in ordinary notifications, not in approvals', () => {
    // Deliberate direction. A new type in the ordinary list is a cosmetic miss; a receipt
    // in the approvals list makes the count of things waiting on you wrong.
    expect(isDecisionNotification({ type: 'something_invented_next_year' })).toBe(false);
    expect(isDecisionNotification({})).toBe(false);
    expect(isDecisionNotification(null)).toBe(false);
  });
});

describe('splitting a list', () => {
  test('every notification lands in exactly one half', () => {
    const list = [
      { id: 'a', type: 'approval_submitted' },
      { id: 'b', type: 'fee_reminder' },
      { id: 'c', type: 'certificate_approval_requested' },
      { id: 'd', type: 'approval_decision' },
    ];
    const { approvals, ordinary } = splitByKind(list);

    expect(approvals.map((n) => n.id)).toEqual(['a', 'c']);
    expect(ordinary.map((n) => n.id)).toEqual(['b', 'd']);
    // Nothing lost and nothing counted twice. A split that drops a row is the same harm
    // as a menu that drops an entry: the person cannot tell it from the thing never
    // having arrived.
    expect(approvals.length + ordinary.length).toBe(list.length);
  });

  test('an empty or missing list does not throw', () => {
    expect(splitByKind([])).toEqual({ approvals: [], ordinary: [] });
    expect(splitByKind(undefined)).toEqual({ approvals: [], ordinary: [] });
  });
});
