/**
 * NEW-03 — an expired login on a tool screen must renew itself, not surface an error.
 *
 * Access tokens last 60 minutes. Renewal only ever happened on app load, or when a 401
 * passed through `apiFetch`. 113 calls across 18 tool screens used a bare `fetch`, so
 * they never triggered it and not one of them handled a 401 itself: after an hour, an
 * accountant opening Fee Collection or a teacher opening their class list got a blank
 * screen or "failed to load" while the rest of the app quietly healed itself.
 *
 * This is the same defect as D-43 (chat upload, fixed 2026-07-23 by routing ONE call
 * through `apiFetch`); these tests prove the tool screens now behave the same way.
 * `apiBaseUrl.test.js` is the structural half — it fails if a bare `fetch` comes back.
 * This is the behavioural half: it drives the real screen code through a real 401.
 */
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';

import {
  resetAuthRedirectGuardForTests,
  setAuthRedirectHandlerForTests,
  setAuthSession,
} from '../../lib/authSession';

// The screen only needs to make its calls. Stubbing the two providers keeps the real
// UserProvider's own refresh-on-mount out of the call counts we are asserting on.
jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({
    currentUser: { id: 'u-1', role: 'admin', sub_category: 'accountant', name: 'A' },
    token: 'expired-token',
  }),
}));
jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));

function response(status, data = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => data,
    text: async () => JSON.stringify(data),
    blob: async () => new Blob([]),
  };
}

/**
 * The server as it behaves for someone whose access token expired an hour ago:
 * every data call 401s until the refresh cookie is exchanged for a new token.
 */
function expiredSessionServer(payload) {
  const calls = { data: 0, refresh: 0 };
  let refreshed = false;
  global.fetch = jest.fn((url) => {
    const href = String(url);
    if (href.includes('/auth/refresh')) {
      calls.refresh += 1;
      refreshed = true;
      return Promise.resolve(response(200, { access_token: 'fresh-token', user: { id: 'u-1' } }));
    }
    calls.data += 1;
    return Promise.resolve(refreshed ? response(200, payload) : response(401, { detail: 'Not authenticated' }));
  });
  return calls;
}

// `jest.restoreAllMocks()` only undoes `jest.spyOn` — a direct assignment to
// `global.fetch` survives it. This repo has already lost days to order-dependent
// tests (D-03, D-35), so the original is captured and put back by hand.
const realFetch = global.fetch;

beforeEach(() => {
  setAuthSession('expired-token', { id: 'u-1', role: 'admin', sub_category: 'accountant', name: 'A' });
  resetAuthRedirectGuardForTests();
});

afterEach(() => {
  jest.restoreAllMocks();
  resetAuthRedirectGuardForTests();
  global.fetch = realFetch;
});

test('a tool screen with an expired token refreshes once and shows its data', async () => {
  const calls = expiredSessionServer({
    success: true,
    data: [{ id: 'q-1', title: 'Bus route change', message: 'Please confirm', status: 'open' }],
  });
  const navigate = jest.fn();
  setAuthRedirectHandlerForTests(navigate);

  const { QuerySection } = await import('../tools/QuerySection');
  render(<QuerySection />);

  await waitFor(() => expect(calls.refresh).toBe(1));

  // The point of the whole task: the person SEES THEIR DATA. Before this change the
  // screen swallowed the 401 in a `catch {}` and rendered an empty list forever.
  expect(await screen.findByText('Bus route change')).toBeInTheDocument();
  // The retry succeeded, so they are NOT bounced to the login page.
  expect(navigate).not.toHaveBeenCalled();
  // ...and the call was made twice: the original 401 and the retry after refresh.
  expect(calls.data).toBeGreaterThanOrEqual(2);
});

// The two tests below exercise `apiFetch` directly. They would ALSO pass on the code
// before this change, because the wrapper and its refresh-and-retry already existed —
// what was missing was the tool screens using it. They are kept deliberately, as the
// contract the screens now depend on: if someone "simplifies" the wrapper, the screen
// test above says something broke and these two say exactly what.
test('the retried call carries the NEW token, not the expired one', async () => {
  expiredSessionServer({ success: true, data: [] });
  setAuthRedirectHandlerForTests(jest.fn());

  const { apiFetch } = await import('../../lib/api');
  const { getAuthHeaders } = await import('../../lib/authSession');

  const res = await apiFetch('/api/queries', { headers: getAuthHeaders() });

  expect(res.status).toBe(200);
  const retry = global.fetch.mock.calls.find(
    ([url, opts], i) => i > 0 && !String(url).includes('/auth/refresh') && opts?.headers
  );
  expect(retry[1].headers.Authorization).toBe('Bearer fresh-token');
});

test('when the refresh itself fails, the person is sent to log in once — not left on a broken screen', async () => {
  global.fetch = jest.fn((url) =>
    Promise.resolve(response(401, { detail: String(url).includes('/auth/refresh') ? 'expired' : 'Not authenticated' }))
  );
  const navigate = jest.fn();
  setAuthRedirectHandlerForTests(navigate);

  const { apiFetch } = await import('../../lib/api');
  await Promise.all([
    apiFetch('/api/queries', { headers: {} }),
    apiFetch('/api/fees/class-summary', { headers: {} }),
  ]);

  await waitFor(() => expect(navigate).toHaveBeenCalledTimes(1));
});

// A second, unrelated screen — so this proves a property of the conversion rather than
// one lucky file. Incident Tracker was one of the 18 affected screens (6 bare calls).
test('a different tool screen also renews instead of failing', async () => {
  const calls = expiredSessionServer({ success: true, data: [] });
  const navigate = jest.fn();
  setAuthRedirectHandlerForTests(navigate);

  const { default: IncidentTracker } = await import('../tools/IncidentTracker');
  render(<IncidentTracker />);

  await waitFor(() => expect(calls.refresh).toBe(1));
  expect(navigate).not.toHaveBeenCalled();
});
