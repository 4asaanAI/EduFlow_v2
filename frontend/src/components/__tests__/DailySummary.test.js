/**
 * The whole school on one page (Abhimanyu, 2026-08-12).
 *
 * What this screen showed BEFORE was two hardcoded rows, "Weekly Attendance Report" and
 * "Monthly Fee Summary", each with a green Active badge, for reports that had never
 * existed and were never sent. So the first thing worth pinning is that nothing on it is
 * invented, and the second is that it does not claim to deliver anything.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { AutomatedReport } from '../tools/AdminTools';

jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));
jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'aman', role: 'owner', name: 'Aman Litt' } }),
}));
jest.mock('../../lib/authSession', () => ({ getAuthHeaders: () => ({}) }));

const summary = {
  day: '2026-08-12',
  freshly_produced: true,
  school: { students_on_the_roll: 1842, staff: 110 },
  attendance: { marked: true, children_marked: 1800, present: 1700, absent: 100,
                present_percent: 94.4 },
  money: { collected_today: 125000, receipts_today: 14, outstanding_in_total: 350000,
           children_with_something_outstanding: 42, bills_past_their_due_date: 61 },
  waiting_for_you: { total: 3, documents_awaiting_approval: 2,
                     staff_leave_requests_waiting: 1, other_approvals_waiting: 0,
                     discounts_awaiting_approval: 0 },
  what_changed: { total: 12, money_changes: 4, by_person: [], worth_a_look: [] },
};

jest.mock('../../lib/api', () => {
  const actual = jest.requireActual('../../lib/api');
  const stub = {};
  Object.keys(actual).forEach((key) => {
    stub[key] = typeof actual[key] === 'function'
      ? async () => ({ success: true, data: [] })
      : actual[key];
  });
  return Object.assign(stub, {
    getSchoolSummary: async () => global.__summary,
    getSchoolSummaryHistory: async () => ({ success: true, data: global.__history }),
  });
});

beforeEach(() => {
  global.__summary = { success: true, data: summary };
  global.__history = [];
});

test('the day is on one page: roll, attendance, money, approvals and changes', async () => {
  render(<AutomatedReport />);
  await waitFor(() => expect(screen.getByText('2026-08-12')).toBeInTheDocument());

  expect(screen.getByText(/1,842 children, 110 staff/)).toBeInTheDocument();
  expect(screen.getByText(/1700 of 1800 present \(94.4%\), 100 absent/)).toBeInTheDocument();
  expect(screen.getByText(/₹1,25,000 across 14 receipts/)).toBeInTheDocument();
  expect(screen.getByText(/₹3,50,000 across 42 children/)).toBeInTheDocument();
  expect(screen.getByText(/61 bills/)).toBeInTheDocument();
  expect(screen.getByText(/3 thing\(s\) to approve/)).toBeInTheDocument();
  expect(screen.getByText(/12, of which 4 touched money/)).toBeInTheDocument();
});

test('it does not pretend to send anything to anybody', async () => {
  // The defect this screen replaces was a green Active badge on a report nobody received.
  render(<AutomatedReport />);
  await waitFor(() => expect(screen.getByText('2026-08-12')).toBeInTheDocument());

  expect(screen.getByText(/is not emailed or sent to you/i)).toBeInTheDocument();
  expect(screen.queryByText(/Weekly Attendance Report/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/Monthly Fee Summary/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/^Active$/)).not.toBeInTheDocument();
});

test('a day with no attendance says so rather than showing zero present', async () => {
  global.__summary = {
    success: true,
    data: { ...summary, attendance: { marked: false } },
  };
  render(<AutomatedReport />);
  await waitFor(() => expect(screen.getByText('2026-08-12')).toBeInTheDocument());
  expect(screen.getByText(/Not marked yet today/i)).toBeInTheDocument();
});

test('anyone the page is not for is told whose it is, not shown an empty report', async () => {
  global.__summary = { success: false, detail: 'Forbidden' };
  render(<AutomatedReport />);
  await waitFor(() =>
    expect(screen.getByText(/for the school's owner and the Principal/i)).toBeInTheDocument());
  expect(screen.queryByText(/Collected today/)).not.toBeInTheDocument();
});

test('earlier days are listed once there are any', async () => {
  global.__history = [
    { id: '1', day: '2026-08-12', money: { collected_today: 125000 },
      attendance: { marked: true, present_percent: 94.4 } },
    { id: '2', day: '2026-08-11', money: { collected_today: 90000 },
      attendance: { marked: true, present_percent: 91 } },
  ];
  render(<AutomatedReport />);
  await waitFor(() => expect(screen.getByText('Earlier days')).toBeInTheDocument());
  expect(screen.getByText(/collected ₹90,000 · 91% present/)).toBeInTheDocument();
});
