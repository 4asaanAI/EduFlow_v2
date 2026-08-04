import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AttendanceRecorder } from '../AdminTools';

/**
 * Inspection Remediation BLOCK 3 — regression guard for the defect found while
 * clearing the hook-dependency warnings (T11 / NEW-09).
 *
 * The Attendance Recorder asked the server for the register with `currentUser` in
 * the slot where the date belongs, so every request carried `?date=[object Object]`.
 * The server found no rows for that literal string, so the screen showed every child
 * as "not marked" whatever had actually been recorded — on today's date as much as
 * any other — and picking a different date changed nothing.
 *
 * These two tests fail on the old call and pass on the fixed one.
 */

const calls = [];

jest.mock('../../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'admin-1', role: 'admin', name: 'Admin' } }),
}));

// D-48/D-60: derive the stub from the real module so a helper added later cannot
// silently break this file, and use plain functions because the Jest preset sets
// `resetMocks: true` and would strip the implementation off any jest.fn().
jest.mock('../../../lib/api', () => {
  const actual = jest.requireActual('../../../lib/api');
  const stub = {};
  Object.keys(actual).forEach((key) => {
    stub[key] = typeof actual[key] === 'function'
      ? async () => ({ success: true, data: [] })
      : actual[key];
  });
  stub.getAllClasses = async () => ({
    success: true,
    data: [{ id: 'c1', name: '5', section: 'A' }],
  });
  stub.getTodayAttendance = async (classId, date) => {
    calls.push({ classId, date });
    return { success: true, data: [] };
  };
  return stub;
});

beforeEach(() => {
  calls.length = 0;
});

test('asks the server for a real date, not the signed-in user', async () => {
  render(<AttendanceRecorder />);

  await waitFor(() => expect(calls.length).toBeGreaterThan(0));

  const { date } = calls[0];
  expect(typeof date).toBe('string');
  // A plain YYYY-MM-DD. The old bug put the user object here, which reached the
  // server as the literal text "[object Object]".
  expect(date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(String(date)).not.toContain('object');
});

test('changing the date actually changes what is asked for', async () => {
  render(<AttendanceRecorder />);
  await waitFor(() => expect(calls.length).toBeGreaterThan(0));
  const firstDate = calls[0].date;

  fireEvent.change(screen.getByTestId('date-picker'), { target: { value: '2026-07-15' } });

  await waitFor(() => {
    expect(calls[calls.length - 1].date).toBe('2026-07-15');
  });
  expect(calls[calls.length - 1].date).not.toBe(firstDate);
});
