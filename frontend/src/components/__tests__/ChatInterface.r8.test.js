/**
 * Epic R8 — Frontend Chat Resilience (ChatInterface event switch + recovery).
 * Also closes the R1.1 AC4 deferred item: the event switch renders SOMETHING for
 * every backend event type, including `error` and an unrecognised type.
 */
import { render, screen, fireEvent } from '@testing-library/react';

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'u1', role: 'teacher', name: 'Test Teacher' } }),
}));
jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true }),
}));
jest.mock('../../lib/api', () => ({
  apiFetch: jest.fn(() => Promise.resolve({ json: async () => ({ success: false }) })),
  createConversation: jest.fn(() => Promise.resolve({ success: true, data: { id: 'c1' } })),
  getMessages: jest.fn(() => Promise.resolve({ success: true, data: [] })),
  getBrowserSseSessionId: () => 'tab-1',
  sendMessageStream: jest.fn(),
  executeTool: jest.fn(() => Promise.resolve({ success: false })),
  emitFeedback: jest.fn(() => Promise.resolve()),
  uploadChatFile: jest.fn(() => Promise.resolve({ success: false })),
}));

import ChatInterface from '../ChatInterface';
import { sendMessageStream } from '../../lib/api';

beforeEach(() => {
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: async () => ({ success: false }) }));
  // jsdom does not implement scrollIntoView; ChatInterface calls it in an effect.
  window.HTMLElement.prototype.scrollIntoView = jest.fn();
});

afterEach(() => jest.clearAllMocks());

function renderChat() {
  return render(<ChatInterface activeConvId="c1" activeConvTitle="Test" onConvCreated={() => {}} />);
}

async function sendText(text) {
  const input = await screen.findByTestId('chat-input');
  fireEvent.change(input, { target: { value: text } });
  fireEvent.click(screen.getByTestId('chat-send'));
}

test('happy path: streamed text_delta + done finalizes into an assistant bubble', async () => {
  sendMessageStream.mockImplementationOnce((cid, text, user, onEvent) => {
    onEvent({ type: 'text_delta', delta: 'Hello ' });
    onEvent({ type: 'text_delta', delta: 'there.' });
    onEvent({ type: 'done', message_id: 'm1' });
    return Promise.resolve();
  });
  renderChat();
  await sendText('hi');
  expect(await screen.findByText('Hello there.')).toBeInTheDocument();
});

test('R1.1 AC1: an error event renders a visible bubble + Retry; retry does not duplicate the question', async () => {
  sendMessageStream.mockImplementationOnce((cid, text, user, onEvent) => {
    onEvent({ type: 'error', message: 'The assistant hit a snag.' });
    return Promise.resolve();
  });
  renderChat();
  await sendText('show fees');
  expect(await screen.findByText('The assistant hit a snag.')).toBeInTheDocument();
  expect(screen.getAllByTestId('user-message')).toHaveLength(1);
  const retryBtns = screen.getAllByText('Retry');
  expect(retryBtns.length).toBeGreaterThanOrEqual(1);

  sendMessageStream.mockImplementationOnce((cid, text, user, onEvent) => {
    onEvent({ type: 'text_delta', delta: 'Here are the fees.' });
    onEvent({ type: 'done', message_id: 'm2' });
    return Promise.resolve();
  });
  fireEvent.click(retryBtns[retryBtns.length - 1]);
  expect(await screen.findByText('Here are the fees.')).toBeInTheDocument();
  expect(screen.getAllByTestId('user-message')).toHaveLength(1); // no duplicate user bubble
});

test('FM1/R8.3 AC1: token_exhausted renders a visible assistant bubble (question never vanishes)', async () => {
  sendMessageStream.mockImplementationOnce((cid, text, user, onEvent) => {
    onEvent({ type: 'token_exhausted', can_recharge: true });
    return Promise.resolve();
  });
  renderChat();
  await sendText('hello');
  expect(await screen.findByText(/reached your AI usage limit/i)).toBeInTheDocument();
});

test('R1.1 AC2: an unrecognised event type does not crash and the turn still renders something', async () => {
  sendMessageStream.mockImplementationOnce((cid, text, user, onEvent) => {
    onEvent({ type: 'totally_new_event', foo: 1 });
    return Promise.resolve(); // resolves without `done` → client backstop fires
  });
  renderChat();
  await sendText('hi');
  expect(await screen.findByText(/couldn't produce a reply/i)).toBeInTheDocument();
});
