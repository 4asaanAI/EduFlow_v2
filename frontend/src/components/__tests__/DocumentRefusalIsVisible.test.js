/**
 * NEW-01 fallout - a refused document must SAY it was refused.
 *
 * T1 narrowed certificate and ID-card issuing, and D-53 then settled the final list:
 * the school's owner, admin+principal and admin+accountant, nobody else. D-49 took the
 * tiles out of the menus of everyone else, so a receptionist should not see the button
 * at all - but the menus are not the gate, the server is, and a refusal still has to
 * explain itself rather than look like a broken button.
 *
 * Both callers of `downloadBlobAsPdf` passed no `onError`, and the helper's `catch` did
 * `onError && onError(e)` - so the failure was caught and dropped on the floor. The button
 * went from "Generating PDF…" back to normal with no file, no message and no reason. That
 * is the failure-that-looks-like-nothing-happened defect, and it would have been read as
 * "the button is broken" rather than "you are not allowed to do this".
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({
    // R2-9, 2026-08-10: this file used to act as a receptionist. Decision 6 now splits
    // the screen in two - the owner and the principal get a Download button, everybody
    // else gets an Ask-for-approval button - so the download path this file exists to
    // test is only reachable as one of those two. The principal it is. What is under
    // test has not changed: a refused download must say why, in a person's own words.
    currentUser: { id: 'u-1', role: 'admin', sub_category: 'principal', name: 'Adesh' },
  }),
}));
jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));

// `lib/authSession` is deliberately NOT mocked. A partial factory mock does not fall
// through to the real module, so every name it omits becomes `undefined` - which is the
// exact trap logged as D-48, and which this file walked straight into on the first try.
// The real module is cheap; just give it a session.
import { setAuthSession, resetAuthRedirectGuardForTests } from '../../lib/authSession';

const STUDENTS = {
  success: true,
  data: [{ id: 's-1', name: 'Aarav Sharma', class_id: 'c-1', admission_number: 'ADM1', roll_number: '1' }],
};

function jsonOk(payload) {
  return { ok: true, status: 200, json: async () => payload, text: async () => JSON.stringify(payload) };
}

/** Lists load fine; only the document generation is refused. */
function serverRefusingDocuments(status) {
  global.fetch = jest.fn((url) => {
    const href = String(url);
    if (href.includes('/image-gen/')) {
      return Promise.resolve({
        ok: false,
        status,
        text: async () => 'Forbidden',
        json: async () => ({ detail: 'Forbidden' }),
        blob: async () => new Blob([]),
      });
    }
    if (href.includes('/students')) return Promise.resolve(jsonOk(STUDENTS));
    return Promise.resolve(jsonOk({ success: true, data: [] }));
  });
}

const realFetch = global.fetch;

beforeEach(() => {
  setAuthSession('a-valid-token', { id: 'u-1', role: 'admin', sub_category: 'principal' });
  resetAuthRedirectGuardForTests();
});

afterEach(() => {
  jest.restoreAllMocks();
  global.fetch = realFetch;
  resetAuthRedirectGuardForTests();
});

test('a refused ID-card download tells the person why, in their own words', async () => {
  serverRefusingDocuments(403);
  const { IdCardGenerator } = await import('../tools/AdminTools');

  render(<IdCardGenerator />);
  await screen.findByText('Aarav Sharma');

  fireEvent.click(screen.getByText(/Select All/i));
  fireEvent.click(await screen.findByText(/Download 1 ID Cards PDF/i));

  const error = await screen.findByTestId('id-card-error');
  // R2-9, 2026-08-11: it must name who can issue directly AND say what everybody else
  // does instead, because the office and the accounts desk are not refused outright -
  // they send the document for approval. A message that only says "not allowed" sends
  // them away from work they are entitled to do.
  expect(error).toHaveTextContent(/school owner/i);
  expect(error).toHaveTextContent(/principal/i);
  expect(error).toHaveTextContent(/approval/i);
  // Not a status code, not a stack trace, not silence.
  expect(error).not.toHaveTextContent(/403|Forbidden|Error:/);
});

test('the daily cap is explained as a cap, not as a generic failure', async () => {
  serverRefusingDocuments(429);
  const { IdCardGenerator } = await import('../tools/AdminTools');

  render(<IdCardGenerator />);
  await screen.findByText('Aarav Sharma');

  fireEvent.click(screen.getByText(/Select All/i));
  fireEvent.click(await screen.findByText(/Download 1 ID Cards PDF/i));

  await waitFor(() =>
    expect(screen.getByTestId('id-card-error')).toHaveTextContent(/limit .* has been reached/i)
  );
});

test('the button does not stay stuck on "Generating" after a refusal', async () => {
  serverRefusingDocuments(403);
  const { IdCardGenerator } = await import('../tools/AdminTools');

  render(<IdCardGenerator />);
  await screen.findByText('Aarav Sharma');

  fireEvent.click(screen.getByText(/Select All/i));
  fireEvent.click(await screen.findByText(/Download 1 ID Cards PDF/i));

  await screen.findByTestId('id-card-error');
  expect(screen.queryByText(/Generating PDF/i)).not.toBeInTheDocument();
});
