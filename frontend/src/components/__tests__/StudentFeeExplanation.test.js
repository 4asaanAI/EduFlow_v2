/**
 * Release 2 audit, 2026-08-12 - the fee rules are visible on the record, not only in chat.
 *
 * The concessions, the Right to Education mark and the class band all existed on the
 * platform and Flo could explain them, while the student screen showed none of it. A rule
 * the office cannot see on the record is a rule the office cannot check.
 *
 * The route behind this is finance-only, so for the management head and everybody else it
 * simply returns nothing and the whole section is absent. That is deliberate: an empty
 * section is quieter than a refusal, and the server is the real guarantee
 * (tests/backend/api/test_concession_routes_guard.py).
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import StudentDatabase from '../tools/StudentDatabase';

jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));
jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'a1', role: 'admin', sub_category: 'accountant', name: 'Sonu Ruhal' } }),
}));
jest.mock('../../lib/authSession', () => ({ getAuthHeaders: () => ({}) }));
jest.mock('react-router-dom', () => ({
  useSearchParams: () => [new URLSearchParams('focus=stu-1'), jest.fn()],
}));

const student = {
  id: 'stu-1', name: 'A Child', admission_number: '221802', is_active: true,
  siblings: ['221858'], guardians: [],
};

const explanation = {
  student: { id: 'stu-1', name: 'A Child' },
  band: { quarterly_amount: 9750, annual_amount: 39000, structure_name: '6th fees' },
  right_to_education: false,
  concessions: {
    lines: [{ rule: 'sibling', label: 'Sibling concession', amount: 1800,
              why: 'an elder child in a family; the youngest pays full' }],
    total: 1800, gross: 9750, net: 7950,
  },
  siblings: ['221858'],
  transport: { uses_the_bus: true, monthly_fare: 650, route: '8 - JOYA' },
  payments: [], total_paid: 15900,
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
    getStudents: async () => ({ success: true, data: [student], meta: { total: 1 } }),
    getStudent: async () => ({ success: true, data: student }),
    getStudentFeeStatus: async () => ({ success: true, data: { status: 'unpaid' } }),
    explainStudentFee: async () => ({ success: true, data: global.__explanation }),
    getClasses: async () => ({ success: true, data: [] }),
    setStudentConcession: (...args) => { global.__calls.push(['concession', args[0]]); return Promise.resolve({ success: true }); },
    recordAdmissionConcession: (...args) => { global.__calls.push(['one-time', args[0]]); return Promise.resolve({ success: true }); },
    setRightToEducation: (...args) => { global.__calls.push(['rte', args[0]]); return Promise.resolve({ success: true }); },
  });
});

beforeEach(() => { global.__explanation = explanation; global.__calls = []; });

test('the office can see the band, the concession and what is actually payable', async () => {
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Fees, and why/i)).toBeInTheDocument());

  expect(screen.getByText(/9,750 a quarter/)).toBeInTheDocument();
  // The label now appears on the row AND on the button beside it, so scope to the row.
  expect(screen.getAllByText(/Sibling concession/).length).toBeGreaterThan(0);
  expect(screen.getByText(/-₹1,800/)).toBeInTheDocument();
  // The figure that matters: what this family is actually asked for.
  expect(screen.getByText(/7,950 a quarter/)).toBeInTheDocument();
  expect(screen.getByText(/15,900/)).toBeInTheDocument();
});

test('the school bus says eleven months, so nobody wonders about June', async () => {
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Fees, and why/i)).toBeInTheDocument());
  expect(screen.getByText(/11 months \(no June\)/)).toBeInTheDocument();
});

test('a Right to Education child reads as owing nothing, not as a full discount', async () => {
  global.__explanation = { ...explanation, right_to_education: true };
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Fees, and why/i)).toBeInTheDocument());
  expect(screen.getByText(/government-paid Right to Education place/i)).toBeInTheDocument();
  // No band, no concession arithmetic: there is no fee to reduce.
  expect(screen.queryByText(/9,750 a quarter/)).not.toBeInTheDocument();
});

test('the section is simply absent for anyone the route refuses', async () => {
  global.__explanation = null;
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Admission No\./i)).toBeInTheDocument());
  expect(screen.queryByText(/Fees, and why/i)).not.toBeInTheDocument();
});

test('the office can grant a concession from the record, not only through chat', async () => {
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Fees, and why/i)).toBeInTheDocument());

  // The sibling concession is already on this child, so the button offers to remove it.
  await userEvent.click(screen.getByRole('button', { name: /Remove Sibling concession/i }));
  expect(global.__calls).toContainEqual(['concession',
    { student_id: 'stu-1', concession: 'sibling', granted: false }]);

  // The employee one is not, so it offers to give it.
  await userEvent.click(screen.getByRole('button', { name: /Give Employee/i }));
  expect(global.__calls).toContainEqual(['concession',
    { student_id: 'stu-1', concession: 'employee_child', granted: true }]);
});

test('a one-time amount cannot be recorded without naming who agreed it', async () => {
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Fees, and why/i)).toBeInTheDocument());

  await userEvent.click(screen.getByRole('button', { name: /One-time amount agreed at admission/i }));
  await userEvent.type(screen.getByPlaceholderText(/Amount in rupees/i), '6000');
  expect(screen.getByRole('button', { name: /^Record it$/i })).toBeDisabled();

  await userEvent.type(screen.getByPlaceholderText(/Who agreed it/i), 'Aman Litt');
  await userEvent.click(screen.getByRole('button', { name: /^Record it$/i }));
  expect(global.__calls).toContainEqual(['one-time',
    { student_id: 'stu-1', amount: 6000, authorised_by: 'Aman Litt' }]);
});

test('a Right to Education child is not offered concessions to reduce a fee they do not owe', async () => {
  // The real service returns no concession lines for these children: there is no fee to
  // reduce, so there is nothing to list.
  global.__explanation = {
    ...explanation, right_to_education: true,
    concessions: { lines: [], total: 0, gross: 0, net: 0 },
  };
  render(<StudentDatabase />);
  await waitFor(() => expect(screen.getByText(/Fees, and why/i)).toBeInTheDocument());
  expect(screen.getByRole('button', { name: /Give Sibling concession/i })).toBeDisabled();
  expect(screen.getByRole('button', { name: /Remove Right to Education place/i })).toBeEnabled();
});
