/**
 * R3-2, 2026-08-15 - the transport head puts a figure on a vehicle repair, on the
 * platform.
 *
 * Abhimanyu, 2026-08-15: he arranges the servicing and sees what it costs, and the
 * school's owner or the principal agrees the figure BEFORE the money is committed. He
 * asked for this to be done on a screen rather than only through Flo, because a screen is
 * where he does the rest of the job.
 *
 * The load-bearing assertion is that a proposed figure is drawn as WAITING and never as
 * the cost. A number nobody has agreed to, painted like an agreed one, is how a made-up
 * figure ends up being treated as the school's real bill.
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { RaiseMaintenanceRequest } from '../MaintenanceTools';

// The screen Chaman actually holds is "Report a problem", NOT the facility queue. That
// distinction cost a round trip when this was first written: the control was built on the
// queue card, which he cannot open, so it would have shipped unreachable.

let mockApiHandler;
let mockUser;

jest.mock('../../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: mockUser }),
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: false }),
}));

jest.mock('../../../lib/api', () => {
  const actual = jest.requireActual('../../../lib/api');
  return {
    ...actual,
    API: 'http://api',
    apiFetch: (...args) => mockApiHandler(...args),
  };
});

const response = (body, ok = true) => ({ ok, json: async () => body });

// This screen loads the facility queue AND the tech queue and merges them. A mock that
// answers both with the same list renders every row twice, which is a fault in the test
// and not in the screen.
const facilityOnly = (rows) => async (url) => (
  String(url).includes('/issues/facility')
    ? response({ success: true, data: rows })
    : response({ success: true, data: [] })
);

const BUS_REPAIR = {
  id: 'fr-bus', type: 'facility', description: 'Bus 3 brakes', category: 'vehicle',
  status: 'open', priority: 'high', created_at: '2026-08-15T00:00:00',
  logged_by_name: 'Chaman Singh', notes: [],
};
const TAP_REPAIR = {
  id: 'fr-tap', type: 'facility', description: 'Leaking tap', category: 'plumbing',
  status: 'open', priority: 'low', created_at: '2026-08-15T00:00:00',
  logged_by_name: 'Someone', notes: [],
};

const CHAMAN = {
  id: 'chaman-1', role: 'admin', sub_category: 'transport_head', name: 'Chaman Singh',
};

beforeEach(() => {
  mockUser = CHAMAN;
  mockApiHandler = facilityOnly([BUS_REPAIR]);
});

test('he can propose a cost on a vehicle repair, and it is sent to be agreed', async () => {
  let sent = null;
  mockApiHandler = async (url, options = {}) => {
    if (String(url).includes('/propose-cost')) {
      sent = JSON.parse(options.body);
      return response({
        success: true,
        awaiting_approval: true,
        data: { approval_id: 'ap-1', proposed_cost: 12000 },
        message: 'Rs. 12,000 has been sent to the school’s owner and the principal to agree. Nothing is committed until one of them says yes.',
      });
    }
    return facilityOnly([BUS_REPAIR])(url);
  };

  render(<RaiseMaintenanceRequest />);
  fireEvent.click(await screen.findByText('Propose a cost'));
  fireEvent.change(screen.getByLabelText('Proposed repair cost in rupees'), {
    target: { value: '12000' },
  });
  fireEvent.click(screen.getByText('Send for agreement'));

  const notice = await screen.findByTestId('repair-cost-notice');
  expect(notice).toHaveTextContent(/sent to the school/i);
  // Both halves of the message matter. "Sent" alone would leave him thinking it is paid.
  expect(notice).toHaveTextContent(/nothing is committed/i);
  expect(sent).toEqual({ estimated_cost: 12000 });
});

test('a proposed figure is shown as waiting, never as the cost', async () => {
  mockApiHandler = facilityOnly([{ ...BUS_REPAIR, cost_awaiting_approval: 12000 }]);

  render(<RaiseMaintenanceRequest />);
  expect(await screen.findByText(/12000 proposed, waiting to be agreed/i)).toBeInTheDocument();
  // And it is not drawn as the estimate, which is the agreed figure.
  expect(screen.queryByText(/Est\. Rs\. 12000/)).not.toBeInTheDocument();
});

test('there is no cost control on a building repair', async () => {
  // He sees vehicle repair costs and not what repairs to buildings cost. The server
  // refuses it either way; this is about not offering a button that will be refused.
  mockApiHandler = facilityOnly([TAP_REPAIR]);

  render(<RaiseMaintenanceRequest />);
  await screen.findByText('Leaking tap');
  expect(screen.queryByText('Propose a cost')).not.toBeInTheDocument();
});

test('nobody else is offered the control', async () => {
  mockUser = { id: 'm1', role: 'admin', sub_category: 'maintenance', name: 'Maintenance' };
  render(<RaiseMaintenanceRequest />);
  await screen.findByText('Bus 3 brakes');
  expect(screen.queryByText('Propose a cost')).not.toBeInTheDocument();
});

test('an empty or nonsense amount is refused before anything is sent', async () => {
  let called = false;
  mockApiHandler = async (url) => {
    if (String(url).includes('/propose-cost')) called = true;
    return facilityOnly([BUS_REPAIR])(url);
  };

  render(<RaiseMaintenanceRequest />);
  fireEvent.click(await screen.findByText('Propose a cost'));
  fireEvent.click(screen.getByText('Send for agreement'));

  expect(await screen.findByRole('alert')).toHaveTextContent(/enter the amount/i);
  expect(called).toBe(false);
});
