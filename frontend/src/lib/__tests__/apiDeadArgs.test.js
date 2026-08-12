/**
 * D-62 guard - nobody may hand the signed-in user to a helper that does not take one.
 *
 * Why this test exists rather than a code comment:
 *
 *   D-61 was a live defect on the school's attendance register. The Attendance
 *   Recorder called `getTodayAttendance(classId, currentUser)` where the second
 *   parameter is the DATE. Every request went out as `?date=[object Object]`, the
 *   server matched nothing, and the register showed every child as unmarked over
 *   attendance that had already been taken. Nobody spotted it for months because
 *   `somethingApi(currentUser)` is such a normal-looking line in this codebase that
 *   the eye slides straight over it.
 *
 *   The whole class of mistake exists because several `lib/api.js` helpers USED to
 *   take a `user` first argument and ignored it. That parameter was removed in the
 *   D-62 sweep, so every remaining `helper(currentUser)` is either dead weight or,
 *   as in D-61, an argument silently landing in a real slot.
 *
 * This test reads the actual source files, so it keeps working as screens are added.
 */

const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, '..', '..');

/**
 * Helpers that take NO user argument at all. A call site that passes one is at best
 * dead code and at worst the D-61 bug again.
 */
const NO_USER_HELPERS = [
  'getStudents', 'createStudent', 'getFeeTransactions', 'recordFeePayment',
  'getAllClasses', 'getTodayAttendance', 'bulkMarkAttendance', 'executeTool',
  'getMessages', 'createConversation', 'getConversations', 'getAuthHeaders',
];

/**
 * D-64 - CLOSED 2026-08-04, and the exemption list is now deliberately EMPTY.
 *
 * `Layout.js` called `getConversations(currentUser)`. `getConversations` spreads its
 * argument into the query string, so the signed-in person's id, name, email and role
 * were serialised into the URL of every conversation lookup, and from there into the
 * server and CloudFront access logs, on every chat load. The screen looked correct
 * throughout, which is exactly why it survived. That was a REAL leak, not dead weight.
 * `createConversation(currentUser)` on the same file was dead weight only.
 *
 * Both are fixed. This list stays empty: an entry here means personal data is being
 * written into a URL somewhere and nobody is stopping it.
 */
const KNOWN_OPEN = [];

function collectJsFiles(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === '__tests__' || entry.name === 'node_modules') continue;
      collectJsFiles(full, out);
    } else if (entry.name.endsWith('.js')) {
      out.push(full);
    }
  }
  return out;
}

test('no screen passes the signed-in user to a helper that does not accept one', () => {
  // A user-ish argument: `currentUser`, `user`, or `props.user`. Deliberately narrow -
  // this must never fire on a legitimate `getStudents({ limit: 500 })`.
  const pattern = new RegExp(
    `\\b(${NO_USER_HELPERS.join('|')})\\s*\\(\\s*(?:[^()]*?,\\s*)?(currentUser|user)\\s*[),]`,
  );

  const offenders = [];
  for (const file of collectJsFiles(SRC)) {
    const rel = path.relative(SRC, file);
    const lines = fs.readFileSync(file, 'utf8').split('\n');
    lines.forEach((line, i) => {
      const match = line.match(pattern);
      if (!match) return;
      const excused = KNOWN_OPEN.some((k) => rel === k.file && match[1] === k.helper);
      if (excused) return;
      offenders.push(`${rel}:${i + 1}  ${line.trim()}`);
    });
  }

  expect(offenders).toEqual([]);
});

test('the api helpers this guards really do not declare a user parameter', () => {
  // If someone re-adds a `user` parameter, the guard above becomes wrong rather than
  // merely unnecessary - so assert the premise, not just the conclusion.
  const api = fs.readFileSync(path.join(SRC, 'lib', 'api.js'), 'utf8');
  for (const helper of ['getStudents', 'createStudent', 'getFeeTransactions', 'recordFeePayment']) {
    const decl = api.match(new RegExp(`export async function ${helper}\\(([^)]*)\\)`));
    expect(decl).not.toBeNull();
    expect(decl[1]).not.toMatch(/\buser\b/);
  }
});
