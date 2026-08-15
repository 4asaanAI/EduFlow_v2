/**
 * R3-2, 2026-08-15 - a delete the transport head is not allowed to do on his own has to
 * SAY so on the screen.
 *
 * Abhimanyu's decision: the transport head may delete a route, and the school's owner or
 * the principal has to agree first. So the server records the request and answers 202
 * with `awaiting_approval`, and it does NOT delete.
 *
 * That answer also carries `success: true`, because a request correctly recorded is a
 * success. The Delete button's old code was `if (res.success) load()`, so it reloaded the
 * list, the route was still sitting there, and the person was told nothing whatsoever.
 * Pressing Delete and watching the row stay with no explanation is a button that looks
 * broken, which is the fault this platform keeps finding in itself and the exact thing
 * the 202 exists to prevent.
 *
 * This file is what stops that regressing. It renders the real screen and reads the words
 * a person would see, rather than checking a variable.
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { TransportManager } from '../AdminTools';

let mockApiHandler;

jest.mock('../../../contexts/UserContext', () => ({
  useUser: (() => {
    const currentUser = {
      id: 'chaman-1', role: 'admin', sub_category: 'transport_head', name: 'Chaman Singh',
    };
    return () => ({ currentUser });
  })(),
}));

jest.mock('../../../lib/api', () => {
  const actual = jest.requireActual('../../../lib/api');
  return {
    ...actual,
    API: 'http://api',
    apiFetch: (...args) => mockApiHandler(...args),
    getStudents: async () => ({ success: true, data: [] }),
    getAllClasses: async () => ({ success: true, data: [] }),
  };
});

const response = (body, ok = true) => ({ ok, json: async () => body });

const A_ROUTE = {
  id: 'route-9', route_name: 'Joya Town', start_point: 'Gate', end_point: 'Market',
  is_active: true, student_count: 0,
};

beforeEach(() => {
  window.confirm = () => true;
  mockApiHandler = async () => response({ success: true, data: [A_ROUTE] });
});

test('a delete sent for agreement says so, and the route stays on the list', async () => {
  mockApiHandler = async (url, options = {}) => {
    if (options.method === 'DELETE') {
      return response({
        success: true,
        awaiting_approval: true,
        data: { approval_id: 'ap-1' },
        message: 'This needs the school’s owner or the principal to agree, so it has been sent to both of them and nothing has been deleted yet.',
      });
    }
    return response({ success: true, data: [A_ROUTE] });
  };

  render(<TransportManager />);
  await screen.findByText('Joya Town');
  fireEvent.click(screen.getByText('Delete'));

  const notice = await screen.findByTestId('transport-delete-notice');
  // The words matter more than the element. "Sent" and "nothing has been deleted" are
  // the two facts the person needs, and either one alone would mislead.
  expect(notice).toHaveTextContent(/sent to both of them/i);
  expect(notice).toHaveTextContent(/nothing has been deleted yet/i);

  // And the route is still there, which is the truth the message is describing.
  expect(screen.getByText('Joya Town')).toBeInTheDocument();
});

test('an ordinary delete still just deletes, with no notice', async () => {
  let deleted = false;
  mockApiHandler = async (url, options = {}) => {
    if (options.method === 'DELETE') {
      deleted = true;
      return response({ success: true });
    }
    return response({ success: true, data: deleted ? [] : [A_ROUTE] });
  };

  render(<TransportManager />);
  await screen.findByText('Joya Town');
  fireEvent.click(screen.getByText('Delete'));

  await waitFor(() => expect(deleted).toBe(true));
  expect(screen.queryByTestId('transport-delete-notice')).not.toBeInTheDocument();
});

test('a refused delete says why instead of failing silently', async () => {
  // Children still assigned to the route. The server answers 409 and the person used to
  // see nothing at all, which is the same silent-button fault in a different coat.
  mockApiHandler = async (url, options = {}) => {
    if (options.method === 'DELETE') {
      return response(
        { detail: '3 active student(s) are assigned to this route - reassign them first' },
        false,
      );
    }
    return response({ success: true, data: [A_ROUTE] });
  };

  render(<TransportManager />);
  await screen.findByText('Joya Town');
  fireEvent.click(screen.getByText('Delete'));

  const notice = await screen.findByTestId('transport-delete-notice');
  expect(notice).toHaveTextContent(/reassign them first/i);
});
