/**
 * R2-2 - the screens half of "Lalit never sees a rupee figure".
 *
 * Decision 1, 2026-08-10: the management head sees whether a child's fees are paid,
 * as a flag, and never an amount anywhere. Two shared screens showed him money:
 * School Pulse had "Fees Collected" and "Overdue Fees" tiles, and Smart Alerts
 * carried the fee rows.
 *
 * Neither screen is hidden from him. He needs the attendance and staffing half of
 * both, every day. So this checks the variant: the money tiles are gone and the rest
 * of the screen is still there and still useful.
 *
 * The server is the real guarantee - the amounts never reach him in the first place,
 * which `tests/backend/api/test_management_money_leaks_r2_2.py` and the fee-category
 * filter in `ai/tool_functions.py` assert. This is the second lock, not the only one.
 */
import { render, screen, waitFor } from '@testing-library/react';
import SchoolPulse from '../tools/SchoolPulse';

jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));

let mockUser = { id: 'o1', role: 'owner', sub_category: 'owner', name: 'Aman Litt' };
jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: mockUser }),
}));
jest.mock('../../lib/authSession', () => ({ getAuthHeaders: () => ({}) }));

const mockExecuteTool = jest.fn();
jest.mock('../../lib/api', () => {
  // D-60: derived from the real export list rather than hand-written - a factory mock
  // does not fall through, so any name nobody thought to stub comes back undefined and
  // React reports an error pointing nowhere near the cause.
  const actual = jest.requireActual('../../lib/api');
  const stub = {};
  Object.keys(actual).forEach((key) => {
    stub[key] = typeof actual[key] === 'function'
      ? async () => ({ success: true, data: [] })
      : actual[key];
  });
  return Object.assign(stub, {
    API: '/api',
    apiFetch: (...a) => global.fetch(...a),
    executeTool: (...a) => mockExecuteTool(...a),
  });
});

const OWNER = { id: 'o1', role: 'owner', sub_category: 'owner', name: 'Aman Litt' };
const MANAGEMENT = { id: 'm1', role: 'admin', sub_category: 'management', name: 'Lalit Thomas' };

const pulseData = {
  success: true,
  data: {
    summary: {
      total_students: 1876,
      total_staff: 88,
      attendance_rate: '92%',
      fee_collected: '₹12,40,000',
    },
    fee_stats: { paid: '₹12,40,000', overdue: '₹3,80,000', collection_rate: '76%' },
    staff_absent_today: ['A Teacher', 'Another Teacher'],
    pending_leave_requests: [{ id: 'l1' }, { id: 'l2' }, { id: 'l3' }],
    chronic_absent_students: [],
  },
  meta: { count: 0 },
  message: '',
  denied: false,
};

beforeEach(() => {
  mockExecuteTool.mockReset();
  mockExecuteTool.mockResolvedValue(pulseData);
  global.fetch = jest.fn(() => Promise.resolve({
    ok: true, json: () => Promise.resolve({ success: true, data: [] }),
  }));
});

test('the school owner still sees the money tiles on School Pulse', async () => {
  mockUser = OWNER;
  render(<SchoolPulse />);

  await waitFor(() => expect(screen.getByText(/Fees Collected/i)).toBeInTheDocument());
  expect(screen.getByText(/Overdue Fees/i)).toBeInTheDocument();
  expect(screen.getByText('₹3,80,000')).toBeInTheDocument();
});

test('the management head sees School Pulse with no money on it', async () => {
  mockUser = MANAGEMENT;
  render(<SchoolPulse />);

  // The screen loaded and the half he needs is there.
  await waitFor(() => expect(screen.getByText(/Enrolled Students/i)).toBeInTheDocument());
  // getAllByText: the screen names attendance in more than one place, which is fine.
  expect(screen.getAllByText(/Today's Attendance/i).length).toBeGreaterThan(0);

  // The money is gone: the tiles, the figures, and the fee-collection alert line.
  expect(screen.queryByText(/Fees Collected/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/Overdue Fees/i)).not.toBeInTheDocument();
  expect(screen.queryByText('₹12,40,000')).not.toBeInTheDocument();
  expect(screen.queryByText('₹3,80,000')).not.toBeInTheDocument();
  expect(screen.queryByText(/Fee collection:/i)).not.toBeInTheDocument();
});

test('the management head gets two tiles he can act on in their place', async () => {
  mockUser = MANAGEMENT;
  render(<SchoolPulse />);

  // Replacing the money with blanks would leave him a worse screen than before.
  // getAllByText: the screen already had a "staff absent today" list further down, so
  // the phrase now appears twice. The tile is the new one.
  await waitFor(() => expect(screen.getAllByText(/Staff Absent Today/i).length).toBeGreaterThan(0));
  expect(screen.getByText(/Leave Awaiting Approval/i)).toBeInTheDocument();
});
