/**
 * The school's three words for where a person stands, in one place.
 *
 * Owner request 10, 2026-08-06. Aman described what the school actually does and the
 * platform had no word for the middle of it:
 *
 *   "There are students who stop reporting to the school without any contact - they
 *   get transferred to another region and do not come to take the TC. The school puts
 *   those students into a list called NSO. Their names STILL APPEAR in everyday
 *   attendance. After the TC, the name is removed from attendance."
 *
 * Decision 2 of the same night (Abhimanyu): this applies to students, staff AND
 * teachers, with the same three stages for all of them. That is why this file talks
 * about "a person" and is imported by both the student screen and the staff screen -
 * two copies of these words is exactly how the two screens would drift apart.
 *
 * The server half is `backend/services/enrolment_status.py`. The state names and the
 * view names here are the strings that endpoint accepts; keep them in lockstep.
 */

export const ACTIVE = 'active';
export const NSO = 'nso';
export const TC_ISSUED = 'tc_issued';

/** The three a person can be moved between. Permanent erasure is not one of them. */
export const ENROLMENT_STATES = [
  {
    value: ACTIVE,
    label: 'On the roll',
    forStaff: 'On the staff roll',
    help: 'Attending as normal. Counted in the school roll and marked every day.',
    tone: 'green',
  },
  {
    value: NSO,
    label: 'NSO - stopped attending',
    forStaff: 'NSO - stopped reporting',
    help: 'No longer attending and no TC issued yet. Still appears on the daily register every day, so a teacher marks them absent and the school notices if they come back.',
    tone: 'orange',
  },
  {
    value: TC_ISSUED,
    label: 'TC issued - left the school',
    forStaff: 'Left the school',
    help: 'The leaving certificate is out. Off the daily register, and the record is kept in the recycle bin so it can still be brought back.',
    tone: 'neutral',
  },
];

export const STATE_BY_VALUE = Object.fromEntries(ENROLMENT_STATES.map((s) => [s.value, s]));

/** Short badge wording for a table row. */
export function stateBadge(state) {
  if (state === NSO) return { text: 'NSO', tone: 'orange' };
  if (state === TC_ISSUED) return { text: 'TC issued', tone: 'neutral' };
  return { text: 'On the roll', tone: 'green' };
}

/**
 * Read the state off a row.
 *
 * The server sends `enrolment_state` on every row now, but rows also arrive from
 * older cached responses and from screens that build their own list, so this falls
 * back to the same rule the server uses rather than showing a blank badge.
 */
export function readState(row) {
  if (!row) return ACTIVE;
  if (row.enrolment_state) return row.enrolment_state;
  const status = String(row.status || '').trim().toLowerCase();
  if (status === NSO) return NSO;
  if (row.is_active) return ACTIVE;
  if (row.is_active === false) return TC_ISSUED;
  return ACTIVE;
}

/** The named lists a screen can ask the server for. Mirrors LIST_VIEWS on the server. */
export const ON_ROLL_VIEW = 'active';
export const NSO_VIEW = 'nso';
export const TC_ISSUED_VIEW = 'tc_issued';
export const OFF_ROLL_VIEW = 'off_roll';
export const ON_REGISTER_VIEW = 'on_register';
export const ALL_VIEW = 'all';

/**
 * What the "Who to show" control offers.
 *
 * This replaced an "Include inactive" tick box. The tick was the whole recovery
 * story: it was the only way to reach a student who had been switched off, it said
 * nothing about why they were off, and it did not distinguish a child who had
 * stopped attending from one who had formally left. Aman asked for a recycle bin,
 * and a recycle bin is a place you go, not a checkbox you remember exists.
 */
export const ENROLMENT_VIEWS = [
  { value: ON_ROLL_VIEW, label: 'On the roll', help: 'Everyone attending as normal.' },
  { value: ON_REGISTER_VIEW, label: 'On the daily register', help: 'On the roll plus the NSO list - the names marked every morning.' },
  { value: NSO_VIEW, label: 'NSO list', help: 'Stopped attending, no TC yet.' },
  { value: TC_ISSUED_VIEW, label: 'Left the school', help: 'TC issued.' },
  { value: OFF_ROLL_VIEW, label: 'Recycle bin', help: 'Everyone off the roll - NSO and left - so they can be put back or removed for good.' },
  { value: ALL_VIEW, label: 'Everyone', help: 'Every record, whatever state it is in.' },
];

/** Views that show someone who is off the roll. Owner and principal only. */
export const RESTRICTED_VIEWS = [NSO_VIEW, TC_ISSUED_VIEW, OFF_ROLL_VIEW, ALL_VIEW];

/**
 * The shortest reason the server will accept before it destroys a record for good.
 *
 * Both erase routes refuse anything under ten characters. The screen has to say so
 * BEFORE the button is pressed - owner request 10 - or a person types "x", is
 * refused, and learns nothing about why the box was there.
 */
export const MIN_ERASE_REASON = 10;

export default ENROLMENT_STATES;
