/**
 * Epic R8 — FH2 (R8.1 AC2): a send that can't start must not eat the user's text.
 */
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'u1', role: 'owner', name: 'Test' } }),
}));

import InputBar from '../InputBar';

let speechInstances = [];
let OriginalSpeechRecognition;

class MockSpeechRecognition {
  constructor() {
    this.start = jest.fn();
    this.stop = jest.fn(() => {
      this.onend?.();
    });
    this.abort = jest.fn(() => {
      this.onerror?.({ error: 'aborted' });
      this.onend?.();
    });
    speechInstances.push(this);
  }
}

beforeEach(() => {
  speechInstances = [];
  OriginalSpeechRecognition = window.SpeechRecognition;
  window.SpeechRecognition = MockSpeechRecognition;
});

afterEach(() => {
  if (OriginalSpeechRecognition) window.SpeechRecognition = OriginalSpeechRecognition;
  else delete window.SpeechRecognition;
});

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

test('voice input appends transcript into the composer', async () => {
  render(<InputBar onSend={() => Promise.resolve()} disabled={false} />);

  fireEvent.click(screen.getByTestId('voice-input-btn'));
  expect(speechInstances).toHaveLength(1);
  expect(speechInstances[0].start).toHaveBeenCalled();

  await act(async () => {
    speechInstances[0].onresult?.({
      resultIndex: 0,
      results: [{ 0: { transcript: 'show fee summary for today' }, isFinal: true }],
    });
  });

  await waitFor(() => expect(screen.getByTestId('chat-input').value).toBe('show fee summary for today'));
});

test('late voice callbacks cannot repopulate the input after send', async () => {
  const onSend = jest.fn(() => Promise.resolve());
  render(<InputBar onSend={onSend} disabled={false} />);

  fireEvent.click(screen.getByTestId('voice-input-btn'));
  const recognition = speechInstances[0];
  await act(async () => {
    recognition.onresult?.({
      resultIndex: 0,
      results: [{ 0: { transcript: 'prepare the principal brief' }, isFinal: false }],
    });
  });

  await waitFor(() => expect(screen.getByTestId('chat-input').value).toBe('prepare the principal brief'));

  fireEvent.click(screen.getByTestId('chat-send'));
  expect(onSend).toHaveBeenCalledWith('prepare the principal brief', null);

  await act(async () => {
    recognition.onresult?.({
      resultIndex: 0,
      results: [{ 0: { transcript: 'for tomorrow morning' }, isFinal: true }],
    });
  });

  await waitFor(() => expect(screen.getByTestId('chat-input').value).toBe(''));
});
