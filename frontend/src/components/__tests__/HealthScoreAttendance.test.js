/**
 * UI Sweep Epic 4 — regression for a defect this epic's own review found.
 *
 * Making `attendance_rate` honest ("not marked yet" instead of "0%") broke two health
 * scores that did `parseFloat(rate) || 0`. They would have scored a school as failing
 * every morning before the register was taken — the same "absence of data read as a
 * bad number" defect the epic exists to remove, reintroduced in a new place.
 *
 * The shared-field lesson from the previous retrospective, caught by applying it.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { AiHealthReport } from '../tools/OwnerTools';

jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));
jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'o1', role: 'owner', name: 'Owner' } }),
}));
jest.mock('../../lib/authSession', () => ({ getAuthHeaders: () => ({}) }));

const mockExecuteTool = jest.fn();
jest.mock('../../lib/api', () => ({
  executeTool: (...a) => mockExecuteTool(...a),
  updateLeave: jest.fn(),
  getStaff: jest.fn(),
  fetchPlatformHealth: jest.fn(),
}));

const pulse = (summary) => ({
  success: true,
  data: { summary, staff_absent_today: [], pending_leave_requests: [], chronic_absent_students: [] },
  meta: { count: 0 }, message: '', denied: false,
});

beforeEach(() => {
  mockExecuteTool.mockReset();
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, data: [] }) }));
});

test('unmarked attendance is excluded from the score, not scored as zero', async () => {
  mockExecuteTool.mockResolvedValue(pulse({
    total_students: 1802, total_staff: 88,
    attendance_rate: 'not marked yet', attendance_marked_today: false,
    fee_collection_rate: '95%', pending_leaves: 0,
  }));

  render(<AiHealthReport />);
  screen.getByRole('button', { name: /generate/i }).click();

  await waitFor(() => {
    expect(screen.getByText(/has not been marked yet today/i)).toBeInTheDocument();
  });
  // Never phrased as a percentage, and never as a deduction.
  expect(screen.queryByText(/attendance at 0%/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/attendance at NaN/i)).not.toBeInTheDocument();
});

test('a marked attendance figure is still scored normally', async () => {
  mockExecuteTool.mockResolvedValue(pulse({
    total_students: 1802, total_staff: 88,
    attendance_rate: '91.5%', attendance_marked_today: true,
    fee_collection_rate: '95%', pending_leaves: 0,
  }));

  render(<AiHealthReport />);
  screen.getByRole('button', { name: /generate/i }).click();

  await waitFor(() => {
    expect(screen.getByText(/attendance at 91.5% — on track/i)).toBeInTheDocument();
  });
});
