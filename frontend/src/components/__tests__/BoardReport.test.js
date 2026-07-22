/**
 * UI Sweep Epic 4, Story 4.2 — the Board Report.
 *
 * The screen the owner opens before a trust meeting. It used to load six sources
 * under one Promise.all, catch everything into one banner, and then show nothing at
 * all — while every figure that failed rendered as 0.
 *
 * The fixtures below are the shape the FIXED server returns: one envelope, `data` is
 * the payload. A fixture shaped to match whatever the component happens to expect
 * would be the same disease as the browser-test double that hid this for a whole
 * initiative.
 */
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { BoardReport } from '../tools/OwnerTools';

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true }),
}));
jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'o1', role: 'owner', name: 'Owner' } }),
}));
jest.mock('../../lib/authSession', () => ({
  getAuthHeaders: () => ({ 'Content-Type': 'application/json' }),
}));

const mockExecuteTool = jest.fn();
jest.mock('../../lib/api', () => ({
  executeTool: (...args) => mockExecuteTool(...args),
  updateLeave: jest.fn(),
  getStaff: jest.fn(),
  fetchPlatformHealth: jest.fn(),
}));

// One envelope. `data` is the payload — never another envelope.
const envelope = (data) => ({ success: true, data, meta: { count: 1 }, message: '', denied: false });

const PULSE = envelope({
  summary: {
    total_students: 1802, total_staff: 88,
    attendance_rate: 'not marked yet', attendance_marked_today: false,
  },
  staff_absent_today: [], pending_leave_requests: [],
});
const FEE = envelope({
  stats: {
    total_collected: '₹0', total_outstanding: '₹0', collection_rate: '0%',
    students_with_dues: 0, overdue_60_days: 0, transactions_on_file: 1,
  },
  defaulters: [],
});
const ALERTS = envelope({ alerts: [], total_alerts: 0 });
const ATT = envelope({
  avg_attendance_rate: 'not recorded', has_attendance_records: false,
  class_stats_today: [], total_records: 0,
});

beforeEach(() => {
  mockExecuteTool.mockReset();
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, data: [] }) })
  );
});

function mockTools({ feeFails = false } = {}) {
  mockExecuteTool.mockImplementation((name) => {
    if (name === 'get_school_pulse') return Promise.resolve(PULSE);
    if (name === 'get_fee_summary') {
      return feeFails
        ? Promise.reject(new Error('network down'))
        : Promise.resolve(FEE);
    }
    if (name === 'get_smart_alerts') return Promise.resolve(ALERTS);
    if (name === 'get_attendance_overview') return Promise.resolve(ATT);
    return Promise.resolve(envelope({}));
  });
}

async function generate() {
  render(<BoardReport />);
  fireEvent.click(screen.getByTestId('board-generate'));
}

test('reads the real figure out of the single envelope', async () => {
  // The defect: every screen read r.data.summary, which was the envelope, and fell
  // through to `|| 0`. With one envelope the real number appears.
  mockTools();
  await generate();

  await waitFor(() => {
    expect(screen.getByTestId('board-total-students')).toHaveTextContent('1802');
  });
  // The defect rendered a bare "0" where the figure should be. (Not `not
  // toHaveTextContent('0')` — "1802" contains a 0 and that assertion always fails.)
  expect(screen.getByTestId('board-total-students')).toHaveAttribute('data-stat-state', 'ok');
});

test('a genuine zero carries the reason it is zero', async () => {
  mockTools();
  await generate();

  await waitFor(() => {
    expect(screen.getByTestId('board-total-collected')).toHaveTextContent('₹0');
  });
  expect(screen.getByTestId('board-total-collected')).toHaveTextContent(/1 fee record on file/i);
  expect(screen.getByTestId('board-total-collected')).toHaveAttribute('data-stat-state', 'ok');
});

test('unmarked attendance says so rather than showing 0%', async () => {
  mockTools();
  await generate();

  await waitFor(() => {
    expect(screen.getByTestId('board-attendance-today')).toHaveTextContent(/not marked yet/i);
  });
  expect(screen.getByTestId('board-attendance-today')).not.toHaveTextContent('0%');
});

test('one failed section does not cost the other five', async () => {
  mockTools({ feeFails: true });
  await generate();

  // The fee section says it failed…
  await waitFor(() => {
    expect(screen.getByTestId('board-section-error-fee')).toBeInTheDocument();
  });
  expect(screen.getByTestId('board-section-error-fee')).toHaveTextContent(/not a zero/i);
  // …and shows no figure at all, rather than a fabricated ₹0. A failed section is
  // replaced by one clear message and a retry, not by six "Unavailable" cards.
  expect(screen.queryByTestId('board-total-collected')).not.toBeInTheDocument();
  expect(screen.queryByText('₹0')).not.toBeInTheDocument();
  // …while the sections that loaded are still shown.
  expect(screen.getByTestId('board-total-students')).toHaveTextContent('1802');
  expect(screen.getByTestId('board-teachers')).toBeInTheDocument();
});

test('the banner names what is missing instead of promising a partial report', async () => {
  mockTools({ feeFails: true });
  await generate();

  await waitFor(() => {
    expect(screen.getByTestId('board-partial-banner')).toBeInTheDocument();
  });
  expect(screen.getByTestId('board-partial-banner')).toHaveTextContent(/fees/i);
});

test('a second failure reads differently from the first', async () => {
  // Otherwise he cannot tell "it tried again and failed" from "my tap did nothing",
  // and taps eleven times getting angrier.
  mockTools({ feeFails: true });
  await generate();

  await waitFor(() => expect(screen.getByTestId('board-section-error-fee')).toBeInTheDocument());
  const feeSection = screen.getByTestId('board-section-error-fee');
  const first = feeSection.textContent;

  // Scoped to this section: the fee source feeds two sections, so there are two
  // Retry buttons on screen and an unscoped query would be ambiguous.
  fireEvent.click(within(feeSection).getByRole('button', { name: /retry/i }));

  // Wait for the settled second-failure text specifically. Waiting merely for "the
  // text changed" would resolve on the interim "Retrying…" label and race the result.
  await waitFor(() => {
    expect(screen.getByTestId('board-section-error-fee')).toHaveTextContent(/still couldn't load/i);
  });
  expect(screen.getByTestId('board-section-error-fee').textContent).not.toEqual(first);
});

test('the PDF export stays available when a section failed', async () => {
  // An export that refuses because one of six promises rejected leaves him standing
  // in front of the trustees with no document at all.
  mockTools({ feeFails: true });
  await generate();

  await waitFor(() => expect(screen.getByTestId('board-partial-banner')).toBeInTheDocument());
  expect(screen.getByTestId('board-download-pdf')).not.toBeDisabled();
});

test('pressing Retry does not throw keyboard focus off the button', async () => {
  // Regression for a defect found in this epic's own review: BoardSection and
  // BoardSectionFailure were declared INSIDE the render function, so each render
  // gave them a new identity and React remounted the subtree — a keyboard user
  // pressing Retry was silently thrown back to the top of the page.
  mockTools({ feeFails: true });
  await generate();

  await waitFor(() => expect(screen.getByTestId('board-section-error-fee')).toBeInTheDocument());
  const retry = within(screen.getByTestId('board-section-error-fee')).getByRole('button', { name: /retry/i });
  retry.focus();
  expect(retry).toHaveFocus();

  fireEvent.click(retry);

  await waitFor(() => {
    expect(screen.getByTestId('board-section-error-fee')).toHaveTextContent(/still couldn't load/i);
  });
  const retryAfter = within(screen.getByTestId('board-section-error-fee')).getByRole('button', { name: /retry/i });
  expect(retryAfter).toHaveFocus();
});

test('a refused tool is shown as a refusal, never as an empty result', async () => {
  mockExecuteTool.mockImplementation((name) => {
    if (name === 'get_fee_summary') {
      return Promise.resolve({
        success: false, data: [], meta: { count: 0 },
        message: 'You do not have access to this figure.', denied: true,
      });
    }
    if (name === 'get_school_pulse') return Promise.resolve(PULSE);
    if (name === 'get_smart_alerts') return Promise.resolve(ALERTS);
    if (name === 'get_attendance_overview') return Promise.resolve(ATT);
    return Promise.resolve(envelope({}));
  });
  await generate();

  await waitFor(() => {
    expect(screen.getByTestId('board-section-error-fee')).toBeInTheDocument();
  });
  expect(screen.getByTestId('board-section-error-fee')).toHaveTextContent(/do not have access/i);
});

test('a failing staff request is not silently turned into zero staff', async () => {
  // `.catch(() => ({ data: [] }))` is how a 403 used to read as "0 teachers".
  mockTools();
  global.fetch = jest.fn((url) =>
    String(url).includes('/staff')
      ? Promise.resolve({ ok: false, status: 403, json: () => Promise.resolve({ detail: 'Forbidden' }) })
      : Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, data: [] }) })
  );
  await generate();

  await waitFor(() => {
    expect(screen.getByTestId('board-teachers')).toHaveAttribute('data-stat-state', 'unavailable');
  });
  expect(screen.getByTestId('board-teachers')).not.toHaveTextContent(/^0$/);
});
