import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import StaffTracker from '../StaffTracker';

/**
 * D-44 (deep-link half) - a Directory row opens that PERSON, not just the list.
 *
 * The Directory sends `?tool=staff-tracker&focus=<id>`. Staff Tracker paginates on
 * the server, so it cannot assume the person is on whatever page is loaded: it has
 * to fetch the record by id. These tests cover the three things that can happen.
 *
 * The important one is `opens the record even when that person is not on the loaded
 * page`. A test that seeded the person into the list would pass against a version
 * that only searched what was already on screen, which is the version that does not
 * work for 88 staff across several pages.
 */

const calls = { byId: [] };

jest.mock('../../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'u-owner', role: 'owner', name: 'Owner' } }),
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'dark' }),
}));

// D-48/D-60: derive the stub from the real module's export list so a helper added
// later cannot silently break this file, and use plain functions because the Jest
// preset sets `resetMocks: true` and strips the implementation off any jest.fn().
jest.mock('../../../lib/api', () => {
  const actual = jest.requireActual('../../../lib/api');
  const stub = {};
  Object.keys(actual).forEach((key) => {
    stub[key] = typeof actual[key] === 'function'
      ? async () => ({ success: true, data: [] })
      : actual[key];
  });
  // The loaded page deliberately does NOT contain the person being deep-linked to.
  stub.getStaff = async () => ({
    success: true,
    data: [{ id: 'other-1', name: 'Someone Else', employee_id: 'E-999' }],
    meta: { total: 88 },
  });
  stub.getStaffMember = async (id) => {
    calls.byId.push(id);
    if (id === 'staff-42') {
      return {
        success: true,
        data: {
          id: 'staff-42', name: 'Meera Sharma', employee_id: 'E-042',
          staff_type: 'teacher', role: 'teacher', department: 'Science',
        },
      };
    }
    return { success: false, detail: 'Forbidden' };
  };
  stub.subscribeSSE = () => () => {};
  return stub;
});

beforeEach(() => {
  calls.byId.length = 0;
});

function renderAt(url) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <StaffTracker />
    </MemoryRouter>,
  );
}

test('opens the record even when that person is not on the loaded page', async () => {
  renderAt('/?tool=staff-tracker&focus=staff-42');

  // It asked the server for that exact person rather than hunting the current page.
  await waitFor(() => expect(calls.byId).toContain('staff-42'));
  // And the editor is open on them.
  await waitFor(() => expect(screen.getByDisplayValue('Meera Sharma')).toBeInTheDocument());
});

test('says so plainly when the record cannot be opened', async () => {
  renderAt('/?tool=staff-tracker&focus=not-allowed');

  await waitFor(() => expect(screen.getByTestId('staff-focus-error')).toBeInTheDocument());
  // The list is still usable underneath; a refused deep link is not a dead screen.
  expect(screen.getByText('Someone Else')).toBeInTheDocument();
});

test('no focus parameter opens no editor at all', async () => {
  renderAt('/?tool=staff-tracker');

  await waitFor(() => expect(screen.getByText('Someone Else')).toBeInTheDocument());
  expect(calls.byId).toHaveLength(0);
  expect(screen.queryByTestId('staff-focus-error')).not.toBeInTheDocument();
});

test('the record is fetched once, not on every render', async () => {
  renderAt('/?tool=staff-tracker&focus=staff-42');

  await waitFor(() => expect(screen.getByDisplayValue('Meera Sharma')).toBeInTheDocument());
  // The parameter is stripped after it is applied, so closing the editor or
  // reloading does not reopen it, and the guard ref stops a second fetch.
  expect(calls.byId).toEqual(['staff-42']);
});
