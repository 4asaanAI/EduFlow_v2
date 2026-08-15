/**
 * R3-2, 2026-08-15 - "somebody is waiting on your decision" is not the same kind of
 * message as "here is something that happened".
 *
 * Abhimanyu, 2026-08-15: approvals of any kind should reach Aman and Adesh separately
 * from ordinary notifications, and the bell and the notifications screen should both be
 * split into the two.
 *
 * **Why this matters more than it sounds.** An approval sitting unread is a person
 * blocked. A transport head who has asked to delete a bus route is waiting; a repair that
 * cannot be paid for is waiting. Mixed into a list with "attendance marked" and "circular
 * sent", a request to decide something is exactly as easy to scroll past as a receipt, and
 * nobody finds out until somebody asks why nothing happened.
 *
 * **One rule, read by both surfaces.** The bell panel and the All Notifications screen
 * are separate components that each fetch and each render. If they classified separately,
 * the count on the bell and the rows on the screen would drift, and a person would be told
 * two different things about the same inbox.
 */

/**
 * Notification kinds that ASK for a decision.
 *
 * Taken from the server rather than guessed: these are the three types written by
 * `create_notification` anywhere in the backend that mean "you have to decide something".
 * Everything else beginning `approval_`, `certificate_` or ending `_decision` is an
 * OUTCOME - somebody else already decided - and belongs in ordinary notifications, because
 * telling a person "your request was approved" is news, not a task.
 */
export const DECISION_NOTIFICATION_TYPES = new Set([
  // An approval request routed to the owner and the principal. This is the one the
  // transport head's deletions and repair costs arrive as.
  'approval_submitted',
  // A certificate created by the accountant or management head, waiting to be issued.
  'certificate_approval_requested',
  // A change to somebody's own profile details, waiting to be allowed.
  'profile_change_request',
]);

/**
 * Is this notification asking the reader to decide something?
 *
 * Defaults to FALSE for anything unrecognised, deliberately. A new notification type
 * landing in the ordinary list is a cosmetic miss; a receipt landing in the approvals list
 * makes the count of "things waiting on you" wrong, and a count that overstates is one
 * people learn to ignore.
 */
export function isDecisionNotification(notification) {
  return DECISION_NOTIFICATION_TYPES.has((notification || {}).type);
}

/**
 * Split a list in one pass, so a notification can never land in both or in neither.
 * Returns `{ approvals, ordinary }`.
 */
export function splitByKind(notifications) {
  const approvals = [];
  const ordinary = [];
  (notifications || []).forEach((n) => {
    (isDecisionNotification(n) ? approvals : ordinary).push(n);
  });
  return { approvals, ordinary };
}

/**
 * What the two halves are CALLED, in one place.
 *
 * Abhimanyu, 2026-08-15: the bell and the notifications window should each carry the
 * same two sub-tabs. They already split by the same rule, and until now they labelled
 * that split differently and offered different numbers of tabs, so the same inbox read
 * as two different things depending on where you stood.
 *
 * The names say what is IN each half rather than naming a feature. "Approvals" was
 * accurate for the bell and wrong for the window, where a decided request also appears:
 * a person looking for the certificate they approved yesterday would not find it under
 * a heading that reads like a queue. The real distinction is a task against news.
 */
export const KIND_TABS = [
  { id: 'approvals', label: 'Waiting on you' },
  { id: 'ordinary', label: 'Already happened' },
];
