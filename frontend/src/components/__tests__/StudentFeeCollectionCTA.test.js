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

// t1 and t2 deliberately share a quarter (April-June/"q1") with different fee
// heads - tuition + transport due the same quarter is the normal case that
// broke the original per-transaction fine calculation (see spec change log).
const transactions = [
  {
    id: 't1', student_id: 'stu-1', fee_period: '2026-04', fee_head: 'tuition', amount: 5000,
    status: 'paid', due_date: '2026-04-10', created_at: '2026-04-01T10:00:00', updated_at: '2026-04-02T11:00:00',
  },
  {
    id: 't2', student_id: 'stu-1', fee_period: '2026-05', fee_head: 'transport', amount: 5000,
    status: 'pending', due_date: '2026-05-10', created_at: '2026-04-20T09:00:00',
  },
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
    getFeeTransactions: async ({ student_id } = {}) => {
      if (typeof global.__feeTransactionsResult === 'function') return global.__feeTransactionsResult();
      if (global.__feeTransactionsResult) return global.__feeTransactionsResult;
      return { success: true, data: student_id === 'stu-1' ? global.__transactions : [] };
    },
    getFeeDiscounts: async () => ({ success: true, data: { total_discount: global.__totalDiscount } }),
    // Mirrors the real endpoint (services/late_fine_service.py:assess_quarters),
    // which echoes back `quarter` on every result item - the frontend matches on
    // that field, not on array position.
    calculateLateFine: async (body) => ({
      success: true,
      data: { quarters: body.quarters.map((q) => ({ quarter: q.quarter, total: global.__fineByQuarter[q.quarter] ?? 0 })) },
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
  global.__feeTransactionsResult = null;
  global.__calls = [];
  global.__deleteResult = null;
  global.__totalDiscount = 500;
  global.__fineByQuarter = { q1: 100 };
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

test('the history table shows total fees, fees paid, discount, fine, created/edited dates, and a total row', async () => {
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: /Fee Collection/i }));
  await screen.findByTestId('student-fee-panel');

  const rowT1 = screen.getByRole('button', { name: /Edit 2026-04 tuition/i }).closest('tr');
  expect(rowT1).toHaveTextContent('₹5,000'); // Total Fees
  expect(rowT1).toHaveTextContent('2026-04-01'); // Created At
  expect(rowT1).toHaveTextContent('2026-04-02'); // Last Edited

  const rowT2 = screen.getByRole('button', { name: /Edit 2026-05 transport/i }).closest('tr');
  expect(rowT2).toHaveTextContent('2026-04-20'); // Created At
  expect(rowT2).toHaveTextContent('-'); // Last Edited never set

  await waitFor(() => {
    const total = screen.getByTestId('fee-history-total-row');
    expect(total).toHaveTextContent('₹10,000'); // Total Fees summed
    expect(total).toHaveTextContent('₹5,000'); // Fees Paid summed (only t1 is paid)
    expect(total).toHaveTextContent('₹500'); // Discount - single figure, not summed across rows
    expect(total).toHaveTextContent('₹100'); // Fine - one figure per quarter, not per row
  });
});

test('two transactions due the same quarter (tuition + transport) share one correct fine instead of the group blanking out', async () => {
  // This is exactly the case that broke the original per-transaction fine calculation:
  // late_fine_service raises when the same quarter looks like it's accruing twice.
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: /Fee Collection/i }));
  await screen.findByTestId('student-fee-panel');

  const rowT1 = screen.getByRole('button', { name: /Edit 2026-04 tuition/i }).closest('tr');
  const rowT2 = screen.getByRole('button', { name: /Edit 2026-05 transport/i }).closest('tr');
  await waitFor(() => {
    expect(rowT1).toHaveTextContent('₹100');
    expect(rowT2).toHaveTextContent('₹100');
  });
});

test('a second, distinct quarter is summed separately in the Total row, not multiplied by row count', async () => {
  global.__transactions = [
    ...transactions,
    {
      id: 't3', student_id: 'stu-1', fee_period: '2026-08', fee_head: 'tuition', amount: 2000,
      status: 'pending', due_date: '2026-08-10', created_at: '2026-07-25T09:00:00',
    },
  ];
  global.__fineByQuarter = { q1: 100, q2: 40 };

  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: /Fee Collection/i }));
  await screen.findByTestId('student-fee-panel');

  await waitFor(() => {
    const total = screen.getByTestId('fee-history-total-row');
    expect(total).toHaveTextContent('₹140'); // q1 (100) + q2 (40), each counted once
  });
});

test('a failed transaction load shows the error and no fine/total row, never a stale-looking figure', async () => {
  global.__feeTransactionsResult = { success: false, detail: 'Could not reach the server' };
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: /Fee Collection/i }));
  await screen.findByTestId('student-fee-panel');

  expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server');
  expect(screen.queryByTestId('fee-history-total-row')).not.toBeInTheDocument();
});

test('a reload that fails after a successful load clears the old rows instead of leaving them next to the error', async () => {
  let calls = 0;
  global.__feeTransactionsResult = () => {
    calls += 1;
    return calls === 1
      ? { success: true, data: transactions }
      : { success: false, detail: 'Could not reach the server' };
  };

  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: /Fee Collection/i }));
  await screen.findByTestId('student-fee-panel');
  expect(screen.getByTestId('fee-history-total-row')).toBeInTheDocument();

  // Deleting re-triggers load(), which now fails on this second call.
  await userEvent.click(screen.getByRole('button', { name: /Delete 2026-05 transport/i }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server');
  expect(screen.queryByTestId('fee-history-total-row')).not.toBeInTheDocument();
  expect(screen.queryByText('2026-04')).not.toBeInTheDocument();
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

  await userEvent.click(screen.getByRole('button', { name: /Delete 2026-05 transport/i }));

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

  await userEvent.click(screen.getByRole('button', { name: /Delete 2026-05 transport/i }));

  expect(window.confirm).toHaveBeenCalled();
  expect(global.__calls.find(([op]) => op === 'delete')).toBeUndefined();
});

test('a "not found" delete response (already gone) is treated as success, not shown as an error', async () => {
  global.__deleteResult = { success: false, detail: 'Fee transaction not found' };
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: /Fee Collection/i }));
  await screen.findByTestId('student-fee-panel');

  await userEvent.click(screen.getByRole('button', { name: /Delete 2026-05 transport/i }));

  await waitFor(() => expect(global.__calls.some(([op]) => op === 'delete')).toBe(true));
  expect(screen.queryByText(/not found/i)).not.toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
