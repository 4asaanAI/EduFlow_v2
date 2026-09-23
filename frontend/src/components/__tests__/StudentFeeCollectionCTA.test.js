/**
 * Fee Collection CTA on a student's profile (2026-09-23).
 *
 * Gated to the exact same role set as the backend's `require_finance_profile` on
 * `backend/routes/fees.py` (owner, or admin+principal/accountant/accounts) so the
 * button never appears somewhere the panel behind it would just 403. Student-only,
 * per the intent - staff profiles never show it (covered separately in StaffTracker).
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import StudentDatabase from '../tools/StudentDatabase';

jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));

let mockCurrentUser = { id: 'a1', role: 'admin', sub_category: 'accountant', name: 'Sonu Ruhal' };
jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: mockCurrentUser }),
}));
jest.mock('../../lib/authSession', () => ({ getAuthHeaders: () => ({}) }));
jest.mock('react-router-dom', () => ({
  useSearchParams: () => [new URLSearchParams('focus=stu-1'), jest.fn()],
}));

const student = {
  id: 'stu-1', name: 'A Child', admission_number: '221802', is_active: true,
  siblings: [], guardians: [],
};

const transactions = [
  { id: 't1', student_id: 'stu-1', fee_period: '2026-04', fee_head: 'tuition', amount: 5000, status: 'paid', due_date: '2026-04-10' },
  { id: 't2', student_id: 'stu-1', fee_period: '2026-05', fee_head: 'tuition', amount: 5000, status: 'pending', due_date: '2026-05-10' },
];

jest.mock('../../lib/api', () => {
  const actual = jest.requireActual('../../lib/api');
  const stub = {};
  Object.keys(actual).forEach((key) => {
    stub[key] = typeof actual[key] === 'function'
      ? async () => ({ success: true, data: [] })
      : actual[key];
  });
  return Object.assign(stub, {
    getStudent: async () => ({ success: true, data: student }),
    getStudentFeeStatus: async () => ({ success: true, data: { status: null } }),
    explainStudentFee: async () => ({ success: true, data: null }),
    getFeeTransactions: async ({ student_id } = {}) => ({
      success: true,
      data: student_id === 'stu-1' ? global.__transactions : [],
    }),
    correctFeeTransaction: (...args) => { global.__calls.push(['correct', args]); return Promise.resolve({ success: true, data: {} }); },
    deleteFeeTransaction: (...args) => {
      global.__calls.push(['delete', args]);
      return Promise.resolve(global.__deleteResult || { success: true, data: {} });
    },
  });
});

beforeEach(() => {
  mockCurrentUser = { id: 'a1', role: 'admin', sub_category: 'accountant', name: 'Sonu Ruhal' };
  global.__transactions = transactions;
  global.__calls = [];
  global.__deleteResult = null;
  jest.spyOn(window, 'confirm').mockReturnValue(true);
});

afterEach(() => {
  jest.restoreAllMocks();
});

test('an accountant sees the Fee Collection CTA on a student profile', async () => {
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  expect(screen.getByRole('button', { name: /Fee Collection/i })).toBeInTheDocument();
});

test('the owner sees the Fee Collection CTA', async () => {
  mockCurrentUser = { id: 'o1', role: 'owner', name: 'Aman Litt' };
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  expect(screen.getByRole('button', { name: /Fee Collection/i })).toBeInTheDocument();
});

test('a teacher (non-finance role) does not see the Fee Collection CTA', async () => {
  mockCurrentUser = { id: 'te1', role: 'teacher', name: 'A Teacher' };
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  expect(screen.queryByRole('button', { name: /Fee Collection/i })).not.toBeInTheDocument();
});

test('an admin without a finance sub_category does not see the CTA', async () => {
  mockCurrentUser = { id: 'a2', role: 'admin', sub_category: 'support_staff', name: 'IT Person' };
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  expect(screen.queryByRole('button', { name: /Fee Collection/i })).not.toBeInTheDocument();
});

test('clicking Fee Collection opens the panel with this student\'s totals and history', async () => {
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());

  await userEvent.click(screen.getByRole('button', { name: /Fee Collection/i }));

  await screen.findByTestId('student-fee-panel');
  expect(await screen.findByTestId('fee-panel-collected-total')).toHaveTextContent('₹5,000');
  expect(screen.getByTestId('fee-panel-pending-total')).toHaveTextContent('₹5,000');
});

test('editing a history row requires a reason and calls correctFeeTransaction', async () => {
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: /Fee Collection/i }));
  await screen.findByTestId('student-fee-panel');

  await userEvent.click(screen.getByRole('button', { name: /Edit 2026-04 tuition/i }));

  // Saving without a reason is refused client-side, before any API call.
  await userEvent.click(screen.getByTestId('save-fee-correction'));
  expect(await screen.findByText(/A reason is required/i)).toBeInTheDocument();
  expect(global.__calls.find(([op]) => op === 'correct')).toBeUndefined();

  await userEvent.type(screen.getByLabelText('Reason for correction'), 'Bank slip amount was wrong');
  await userEvent.clear(screen.getByLabelText('Corrected amount'));
  await userEvent.type(screen.getByLabelText('Corrected amount'), '4500');
  await userEvent.click(screen.getByTestId('save-fee-correction'));

  await waitFor(() => expect(global.__calls.some(([op]) => op === 'correct')).toBe(true));
  const [, [transactionId, payload]] = global.__calls.find(([op]) => op === 'correct');
  expect(transactionId).toBe('t1');
  expect(payload).toEqual(expect.objectContaining({ reason: 'Bank slip amount was wrong', amount: 4500 }));
});

test('deleting a history row asks for confirmation and calls deleteFeeTransaction', async () => {
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: /Fee Collection/i }));
  await screen.findByTestId('student-fee-panel');

  await userEvent.click(screen.getByRole('button', { name: /Delete 2026-05 tuition/i }));

  expect(window.confirm).toHaveBeenCalled();
  await waitFor(() => expect(global.__calls.some(([op]) => op === 'delete')).toBe(true));
  const [, [transactionId]] = global.__calls.find(([op]) => op === 'delete');
  expect(transactionId).toBe('t2');
});

test('declining the confirm dialog does not delete', async () => {
  window.confirm.mockReturnValue(false);
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: /Fee Collection/i }));
  await screen.findByTestId('student-fee-panel');

  await userEvent.click(screen.getByRole('button', { name: /Delete 2026-05 tuition/i }));

  expect(window.confirm).toHaveBeenCalled();
  expect(global.__calls.find(([op]) => op === 'delete')).toBeUndefined();
});

test('a "not found" delete response (already gone) is treated as success, not shown as an error', async () => {
  global.__deleteResult = { success: false, detail: 'Fee transaction not found' };
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: /Fee Collection/i }));
  await screen.findByTestId('student-fee-panel');

  await userEvent.click(screen.getByRole('button', { name: /Delete 2026-05 tuition/i }));

  await waitFor(() => expect(global.__calls.some(([op]) => op === 'delete')).toBe(true));
  expect(screen.queryByText(/not found/i)).not.toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
