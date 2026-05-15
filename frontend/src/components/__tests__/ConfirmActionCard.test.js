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
