/**
 * Epic R8 — FH2 (R8.1 AC2): a send that can't start must not eat the user's text.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'u1', role: 'owner', name: 'Test' } }),
}));

import InputBar from '../InputBar';

test('FH2: input is restored when the send reports it could not start', async () => {
  const onSend = jest.fn(() => Promise.resolve(false)); // handleSend returns false
  render(<InputBar onSend={onSend} disabled={false} />);
  const input = screen.getByTestId('chat-input');
  fireEvent.change(input, { target: { value: 'record fee for Rahul' } });
  fireEvent.click(screen.getByTestId('chat-send'));
  expect(onSend).toHaveBeenCalledWith('record fee for Rahul', null);
  await waitFor(() => expect(input.value).toBe('record fee for Rahul'));
});

test('a normal send clears the input (onSend resolves undefined)', async () => {
  const onSend = jest.fn(() => Promise.resolve());
  render(<InputBar onSend={onSend} disabled={false} />);
  const input = screen.getByTestId('chat-input');
  fireEvent.change(input, { target: { value: 'hi' } });
  fireEvent.click(screen.getByTestId('chat-send'));
  await waitFor(() => expect(input.value).toBe(''));
});
