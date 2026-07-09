/**
 * Epic R8 — Frontend Chat Resilience: api.sendMessageStream.
 * FH1 (R8.1 AC1): a 401 refreshes once and retries; a still-401 retry surfaces a
 * VISIBLE error event (never a silent redirect/no-op).
 * R8.4 AC4: the SSE buffer tail is flushed so a final frame without a trailing
 * blank line is not silently dropped.
 */
import { sendMessageStream } from '../api';
import {
  resetAuthRedirectGuardForTests,
  setAuthRedirectHandlerForTests,
  setAuthSession,
} from '../authSession';

function jsonResponse(status, data = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => data,
    text: async () => JSON.stringify(data),
  };
}

function streamResponse(chunks) {
  const encoder = new TextEncoder();
  let i = 0;
  return {
    status: 200,
    ok: true,
    body: {
      getReader: () => ({
        read: () => {
          if (i < chunks.length) {
            const value = encoder.encode(chunks[i]);
            i += 1;
            return Promise.resolve({ done: false, value });
          }
          return Promise.resolve({ done: true, value: undefined });
        },
      }),
    },
  };
}

beforeEach(() => {
  global.fetch = jest.fn();
  setAuthSession('expired-token', { id: 'user-1' });
  resetAuthRedirectGuardForTests();
});

afterEach(() => {
  jest.restoreAllMocks();
  resetAuthRedirectGuardForTests();
});

test('FH1: an initial 401 refreshes once, retries, and then streams normally', async () => {
  let chatCalls = 0;
  let refreshCalls = 0;
  global.fetch.mockImplementation((url) => {
    if (String(url).includes('/auth/refresh')) {
      refreshCalls += 1;
      return Promise.resolve(jsonResponse(200, { access_token: 'fresh', user: { id: 'user-1' } }));
    }
    chatCalls += 1;
    if (chatCalls === 1) return Promise.resolve(jsonResponse(401));
    return Promise.resolve(streamResponse(['data: {"type":"done","message_id":"m1"}\n\n']));
  });

  const onEvent = jest.fn();
  await sendMessageStream('c1', 'hi', { id: 'user-1' }, onEvent, 'tab-1');

  expect(refreshCalls).toBe(1);
  expect(chatCalls).toBe(2); // original + one retry
  expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({ type: 'done', message_id: 'm1' }));
});

test('FH1: a still-401 retry emits a visible error event (not a silent redirect)', async () => {
  const navigate = jest.fn();
  setAuthRedirectHandlerForTests(navigate);
  global.fetch.mockImplementation((url) => {
    if (String(url).includes('/auth/refresh')) {
      return Promise.resolve(jsonResponse(200, { access_token: 'fresh', user: { id: 'user-1' } }));
    }
    return Promise.resolve(jsonResponse(401));
  });

  const onEvent = jest.fn();
  await sendMessageStream('c1', 'hi', { id: 'user-1' }, onEvent, 'tab-1');

  expect(onEvent).toHaveBeenCalledWith({ type: 'thinking_clear' });
  expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({ type: 'error' }));
  expect(navigate).toHaveBeenCalledWith('/');
});

test('R8.4 AC4: the final SSE frame is flushed even without a trailing blank line', async () => {
  // No trailing "\n\n": before the tail-flush fix this frame stayed stuck in the
  // buffer and `done` was never delivered (the turn ended as a stream_error).
  global.fetch.mockResolvedValue(streamResponse(['data: {"type":"done","message_id":"m2"}']));

  const onEvent = jest.fn();
  await sendMessageStream('c1', 'hi', { id: 'user-1' }, onEvent, 'tab-1');

  expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({ type: 'done', message_id: 'm2' }));
  expect(onEvent).not.toHaveBeenCalledWith(expect.objectContaining({ type: 'stream_error' }));
});
