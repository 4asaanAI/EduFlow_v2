import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ConfirmActionCard from '../ConfirmActionCard';

const action = {
  action_id: 'act-1',
  token: 'tok-1',
  tool: 'record_fee_payment',
  display: 'Record fee payment',
  params: { student_id: 'student-1' },
  buttons: [{ action: 'confirm', label: 'Confirm' }, { action: 'cancel', label: 'Cancel' }],
};

beforeEach(() => {
  global.fetch = jest.fn();
});

afterEach(() => {
  jest.useRealTimers();
  jest.restoreAllMocks();
});

test('rapid confirm clicks issue one request', async () => {
  let resolveFetch;
  global.fetch.mockReturnValue(new Promise(resolve => { resolveFetch = resolve; }));

  render(<ConfirmActionCard action={action} conversationId="conv-1" sessionId="tab-1" />);

  const confirm = screen.getByRole('button', { name: /confirm/i });
  fireEvent.click(confirm);
  fireEvent.click(confirm);

  expect(global.fetch).toHaveBeenCalledTimes(1);

  await act(async () => {
    resolveFetch({ ok: true, status: 200, json: async () => ({ success: true }) });
  });
  await waitFor(() => expect(screen.getByText(/action confirmed/i)).toBeInTheDocument());
});

test('shows delayed progress label while request is loading', async () => {
  jest.useFakeTimers();
  global.fetch.mockReturnValue(new Promise(() => {}));

  render(<ConfirmActionCard action={action} conversationId="conv-1" sessionId="tab-1" />);
  fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

  expect(screen.queryByText(/applying changes/i)).not.toBeInTheDocument();
  act(() => { jest.advanceTimersByTime(2000); });
  expect(screen.getByText(/applying changes/i)).toBeInTheDocument();
});

// ── I.1: multi-step plan card ───────────────────────────────────────────────

const planAction = {
  action_id: 'plan-1',
  token: 'plan-tok-1',
  tool: 'plan',
  is_plan: true,
  display: "I'll run these steps in order — confirm to proceed:",
  steps: [
    { idx: 0, tool: 'mark_attendance', kind: 'write', destructive: false, display: 'Mark attendance for Class 4B' },
    { idx: 1, tool: 'create_announcement', kind: 'write', destructive: false, display: 'Post the holiday announcement' },
    { idx: 2, tool: 'deactivate_record', kind: 'write', destructive: true, display: 'Archive the old notice' },
  ],
  buttons: [{ action: 'confirm', label: 'Confirm' }, { action: 'cancel', label: 'Cancel' }],
};

test('I.1 renders all plan steps in order under one confirm/cancel', () => {
  render(<ConfirmActionCard action={planAction} conversationId="conv-1" sessionId="tab-1" />);
  const stepsList = screen.getByTestId('confirm-plan-steps');
  expect(stepsList).toBeInTheDocument();
  expect(screen.getByText('Mark attendance for Class 4B')).toBeInTheDocument();
  expect(screen.getByText('Post the holiday announcement')).toBeInTheDocument();
  expect(screen.getByText('Archive the old notice')).toBeInTheDocument();
  // Exactly one confirm and one cancel.
  expect(screen.getAllByRole('button', { name: /^confirm$/i })).toHaveLength(1);
  expect(screen.getAllByRole('button', { name: /^cancel$/i })).toHaveLength(1);
  // Order preserved.
  const rows = screen.getAllByTestId(/confirm-plan-step-/);
  expect(rows).toHaveLength(3);
  expect(rows[0]).toHaveTextContent('Mark attendance for Class 4B');
  expect(rows[2]).toHaveTextContent('Archive the old notice');
});

test('I.1 marks a destructive step', () => {
  render(<ConfirmActionCard action={planAction} conversationId="conv-1" sessionId="tab-1" />);
  expect(screen.getByText(/destructive/i)).toBeInTheDocument();
});

test('I.1 rapid confirm clicks on a plan issue one request', async () => {
  let resolveFetch;
  global.fetch.mockReturnValue(new Promise(resolve => { resolveFetch = resolve; }));
  render(<ConfirmActionCard action={planAction} conversationId="conv-1" sessionId="tab-1" />);
  const confirm = screen.getByRole('button', { name: /^confirm$/i });
  fireEvent.click(confirm);
  fireEvent.click(confirm);
  expect(global.fetch).toHaveBeenCalledTimes(1);
  await act(async () => {
    resolveFetch({ ok: true, status: 200, json: async () => ({ success: true, data: { message: 'Completed all 3 steps.' } }) });
  });
  await waitFor(() => expect(screen.getByText(/action confirmed/i)).toBeInTheDocument());
});

test('I.1 cancel on a plan posts decision=cancel and reports cancellation', async () => {
  global.fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ success: true, data: { cancelled: true } }) });
  render(<ConfirmActionCard action={planAction} conversationId="conv-1" sessionId="tab-1" />);
  fireEvent.click(screen.getByRole('button', { name: /^cancel$/i }));
  await waitFor(() => expect(screen.getByText(/action cancelled/i)).toBeInTheDocument());
  const body = JSON.parse(global.fetch.mock.calls[0][1].body);
  expect(body.decision).toBe('cancel');
  expect(body.confirmed).toBe(false);
});

// ── I.2: status & error messaging (409 taxonomy) ────────────────────────────

function mock409(code, message) {
  global.fetch.mockResolvedValue({
    ok: false,
    status: 409,
    headers: { get: () => null },
    json: async () => ({ detail: { code, message } }),
  });
}

test('I.2 plan_stale maps to a re-plan message and no retry', async () => {
  mock409('plan_stale', 'The data changed since you reviewed this plan.');
  render(<ConfirmActionCard action={planAction} conversationId="conv-1" sessionId="tab-1" />);
  fireEvent.click(screen.getByRole('button', { name: /^confirm$/i }));
  await waitFor(() => expect(screen.getByText(/data changed/i)).toBeInTheDocument());
  expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
});

test('I.2 plan_tampered surfaces the verify message and no retry', async () => {
  mock409('plan_tampered', 'The approved plan could not be verified and was rejected. Please ask again so a fresh plan can be built.');
  render(<ConfirmActionCard action={planAction} conversationId="conv-1" sessionId="tab-1" />);
  fireEvent.click(screen.getByRole('button', { name: /^confirm$/i }));
  await waitFor(() => expect(screen.getByText(/could not be verified/i)).toBeInTheDocument());
  expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
});

test('I.2 needs_manual_reconciliation says nothing was applied & needs manual attention', async () => {
  mock409('needs_manual_reconciliation', 'Part of this could not be completed safely.');
  render(<ConfirmActionCard action={planAction} conversationId="conv-1" sessionId="tab-1" />);
  fireEvent.click(screen.getByRole('button', { name: /^confirm$/i }));
  await waitFor(() => expect(screen.getByText(/could not be completed safely/i)).toBeInTheDocument());
});

test('I.2 plan_expired maps to a re-planable message and no retry', async () => {
  mock409('plan_expired', 'This plan expired before it was confirmed. Just ask again and I\'ll rebuild it for you.');
  render(<ConfirmActionCard action={planAction} conversationId="conv-1" sessionId="tab-1" />);
  fireEvent.click(screen.getByRole('button', { name: /^confirm$/i }));
  await waitFor(() => expect(screen.getByText(/expired before it was confirmed/i)).toBeInTheDocument());
  expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
});

test('I.2 side_effect_failed (502) says records updated but follow-up failed', async () => {
  global.fetch.mockResolvedValue({
    ok: false,
    status: 502,
    headers: { get: () => null },
    json: async () => ({ detail: { code: 'side_effect_failed', message: 'A notification could not be delivered.' } }),
  });
  render(<ConfirmActionCard action={planAction} conversationId="conv-1" sessionId="tab-1" />);
  fireEvent.click(screen.getByRole('button', { name: /^confirm$/i }));
  await waitFor(() => expect(screen.getByText(/notification could not be delivered/i)).toBeInTheDocument());
  expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
});

test('I.2 opaque 500 shows correlation id and no internal detail, with retry', async () => {
  global.fetch.mockResolvedValue({
    ok: false,
    status: 500,
    headers: { get: () => null },
    json: async () => ({ detail: 'An internal error occurred (id=abc-123)' }),
  });
  render(<ConfirmActionCard action={action} conversationId="conv-1" sessionId="tab-1" />);
  fireEvent.click(screen.getByRole('button', { name: /^confirm$/i }));
  await waitFor(() => expect(screen.getByText(/nothing was applied/i)).toBeInTheDocument());
  expect(screen.getByText(/abc-123/)).toBeInTheDocument();
  // No raw "internal error occurred" string leaks.
  expect(screen.queryByText(/internal error occurred/i)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
});
