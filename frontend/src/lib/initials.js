/**
 * The badge letters shown for a person, worked out from their name.
 *
 * Owner report 2026-08-07: the principal's badge read "PS" when his name is Adesh
 * Singh. Every account carries an `initials` field written once when the account was
 * created, and seven of them still hold the letters of the placeholder name the
 * account was set up under ("Principal Singh" -> PS). Renaming a person never
 * refreshed it, so the badge and the name below it disagreed.
 *
 * The name is the thing that is kept correct, so the badge is derived from it and the
 * stored field is not trusted. That also means this can never drift again.
 */

/**
 * @param {string} name  the person's full name
 * @returns {string} one or two upper-case letters, or '?' when there is no name
 */
export function initialsOf(name) {
  const words = String(name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    // Titles carry no identity: "DR PERMENDRA KUMAR" should read PK, not DP.
    .filter((w) => !/^(dr|mr|mrs|ms|miss|prof|smt|shri|sh)\.?$/i.test(w));

  if (words.length === 0) return '?';
  return words
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

/**
 * The badge for a signed-in user object. Falls back to the stored value only when
 * the account has no name at all, so nothing is left blank.
 */
export function userInitials(user) {
  const derived = initialsOf(user?.name);
  if (derived !== '?') return derived;
  return (user?.initials || '?').toUpperCase();
}

export default userInitials;
