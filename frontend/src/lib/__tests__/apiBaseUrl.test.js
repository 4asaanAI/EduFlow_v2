/**
 * NEW-08 — one definition of the server's address.
 *
 * 25 files each declared their own `process.env.REACT_APP_BACKEND_URL` base. That is
 * why commit 80d803b ("Fix mixed-content fetch errors on CloudFront") reached 13 files
 * and missed 7 — including the login and token-refresh path, where getting it wrong
 * logs the whole school out. This test fails the build the moment a 26th reader appears.
 *
 * NEW-03 — one refreshing wrapper.
 *
 * 113 calls used a bare `fetch`, so an access token that expired mid-morning surfaced
 * as "something went wrong" instead of quietly renewing. Every call now goes through
 * `apiFetch`. This test fails if a screen goes back to calling the server directly.
 */
const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, '..', '..');

const BASE_URL_ALLOWED = new Set([
  path.join('lib', 'api.js'),
]);

// `lib/api.js` IS the wrapper, and `lib/authSession.js` owns the refresh call itself —
// routing either through the wrapper that calls them would loop.
const BARE_FETCH_ALLOWED = new Set([
  path.join('lib', 'api.js'),
  path.join('lib', 'authSession.js'),
]);

// `contexts/UserContext.js` is exempt PER CALL, not per file: login and logout
// deliberately use a plain `fetch` because a 401 there is a wrong password, not an
// expired session. Exempting the whole file would let a future data call be added to
// the file that owns the app's auth state and escape the guard entirely.
const BARE_FETCH_ALLOWED_LINES = {
  [path.join('contexts', 'UserContext.js')]: /\/auth\/(login|logout)/,
};

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === '__tests__' || entry.name === 'node_modules') continue;
      walk(full, out);
    } else if (/\.jsx?$/.test(entry.name) && !/\.test\.jsx?$/.test(entry.name)) {
      // `.jsx` too: the repo has ~50 of them under components/ui, and a rule that
      // only looks at `.js` is a rule with a door left open in it.
      out.push(full);
    }
  }
  return out;
}

const FILES = walk(SRC).map((full) => ({ rel: path.relative(SRC, full), full }));

// Comments are allowed to name either thing — the notes explaining WHY these rules
// exist have to be able to say what they are about.
function codeLines(full) {
  return fs
    .readFileSync(full, 'utf8')
    // Split on \r?\n: a trailing \r is a line terminator, which `.` does not match,
    // so `//.*$` would silently fail to strip a comment on a CRLF checkout.
    .split(/\r?\n/)
    .map((line) =>
      line
        // Strip a line comment, but NOT the `//` in a URL. `(?<!:)` is the whole
        // point: without it, `const u = 'https://x'; fetch(u)` was truncated at the
        // scheme and the `fetch(` after it went unseen — a hole straight through
        // the guard this file exists to be.
        .replace(/(?<!:)\/\/.*$/, '')
        .replace(/\/\*.*?\*\//g, '')
    )
    .filter((line) => !/^\s*\*/.test(line));
}

test('the app has files to check (guards against a broken walk silently passing)', () => {
  expect(FILES.length).toBeGreaterThan(40);
});

test('REACT_APP_BACKEND_URL is read in lib/api.js only', () => {
  const offenders = FILES.filter(
    ({ rel, full }) =>
      !BASE_URL_ALLOWED.has(rel) &&
      codeLines(full).some((line) => line.includes('REACT_APP_BACKEND_URL'))
  ).map((f) => f.rel);

  expect(offenders).toEqual([]);
});

// Matches a direct call to the platform `fetch`, however it is spelled:
//   `fetch(`  `window.fetch(`  `globalThis.fetch(`  `self.fetch(`
// but NOT `apiFetch(`, `activitiesRequest(`, `prefetch(` or `.refetch(`.
// Excluding everything after a `.` (the obvious way to skip `apiFetch`) would have
// let the two commonest ways of writing a bare fetch straight back in.
const BARE_FETCH = /(?:(?:window|globalThis|self)\.fetch|(?<![\w.])fetch)\s*\(/;

test('no screen calls the server with a bare fetch instead of apiFetch', () => {
  const offenders = [];

  for (const { rel, full } of FILES) {
    if (BARE_FETCH_ALLOWED.has(rel)) continue;
    const perLineAllowance = BARE_FETCH_ALLOWED_LINES[rel];
    codeLines(full).forEach((line, i) => {
      if (!BARE_FETCH.test(line)) return;
      if (perLineAllowance && perLineAllowance.test(line)) return;
      offenders.push(`${rel}:${i + 1}`);
    });
  }

  expect(offenders).toEqual([]);
});

// Guards the guard. Both checks above are "expect nothing to be found", which is the
// shape of assertion that keeps passing after it has quietly stopped working — the
// comment-stripper swallowing `https://` did exactly that until it was caught.
test('the checks above actually detect a violation when there is one', () => {
  const offendingSource = [
    "const base = process.env.REACT_APP_BACKEND_URL;",
    "const u = 'https://example.test/x';",
    "fetch(u);",
  ];
  const stripped = offendingSource.map((line) =>
    line.replace(/(?<!:)\/\/.*$/, '').replace(/\/\*.*?\*\//g, '')
  );

  expect(stripped.some((l) => l.includes('REACT_APP_BACKEND_URL'))).toBe(true);
  expect(stripped.some((l) => BARE_FETCH.test(l))).toBe(true);
  // ...and a genuine comment is still ignored.
  expect('// we read REACT_APP_BACKEND_URL here'.replace(/(?<!:)\/\/.*$/, '')).toBe('');
});

test('the bare-fetch pattern catches every spelling and no false ones', () => {
  ['fetch(url)', 'window.fetch(url)', 'globalThis.fetch(url)', 'self.fetch(url)',
   'const r = await fetch(`${API}/x`)', 'return fetch (u)'].forEach((line) => {
    expect(BARE_FETCH.test(line)).toBe(true);
  });

  ['apiFetch(url)', 'await apiFetch(`${API}/x`)', 'activitiesRequest(url)',
   'prefetch(url)', 'query.refetch()', 'uploadChatFile(f)'].forEach((line) => {
    expect(BARE_FETCH.test(line)).toBe(false);
  });
});
