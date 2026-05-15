import { apiFetch, sendMessageStream, subscribeSSE } from '../api';
import { waitFor } from '@testing-library/react';
import {
  resetAuthRedirectGuardForTests,
  setAuthRedirectHandlerForTests,
  setAuthSession,
} from '../authSession';

function response(status, data = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => data,
    text: async () => JSON.stringify(data),
  };
}

beforeEach(() => {
  global.fetch = jest.fn();
  setAuthSession('expired-token', { id: 'user-1' });
  resetAuthRedirectGuardForTests();
});

afterEach(() => {
  jest.useRealTimers();
  jest.restoreAllMocks();
  resetAuthRedirectGuardForTests();
});

test('apiFetch shares one refresh call across concurrent 401 responses', async () => {
  let apiCalls = 0;
  let refreshCalls = 0;
  global.fetch.mockImplementation((url) => {
    if (String(url).includes('/auth/refresh')) {
      refreshCalls += 1;
      return Promise.resolve(response(200, { access_token: 'fresh-token', user: { id: 'user-1' } }));
    }
    apiCalls += 1;
    return Promise.resolve(apiCalls <= 2 ? response(401) : response(200, { success: true }));
  });

  const [first, second] = await Promise.all([
    apiFetch('/api/a', { headers: {} }),
    apiFetch('/api/b', { headers: {} }),
  ]);

  expect(refreshCalls).toBe(1);
  expect(first.status).toBe(200);
  expect(second.status).toBe(200);
});

test('failed shared refresh triggers one login navigation for many callers', async () => {
  const navigate = jest.fn();
  setAuthRedirectHandlerForTests(navigate);
  global.fetch.mockImplementation((url) => {
    if (String(url).includes('/auth/refresh')) return Promise.resolve(response(401));
    return Promise.resolve(response(401));
  });

  await Promise.all(Array.from({ length: 8 }, (_, i) => apiFetch(`/api/${i}`, { headers: {} })));

  expect(navigate).toHaveBeenCalledTimes(1);
  expect(navigate).toHaveBeenCalledWith('/');
});

test('chat stream drop does not auto-issue another POST', async () => {
  const onEvent = jest.fn();
  global.fetch.mockResolvedValue({
    status: 200,
    ok: true,
    body: {
      getReader: () => ({
        read: jest.fn().mockRejectedValue(new Error('network drop')),
      }),
    },
  });

  await sendMessageStream('conv-1', 'hello', { id: 'user-1' }, onEvent, 'tab-1');

  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(onEvent).toHaveBeenCalledWith({ type: 'thinking_clear' });
  expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({ type: 'stream_error', retryable: true }));
});

test('subscribeSSE uses exponential reconnect for non-chat streams', async () => {
  global.fetch.mockResolvedValue(response(503));
  const onEvent = jest.fn();

  const stop = subscribeSSE('/notifications/stream', onEvent, { maxRetries: 1 });

  await waitFor(() => {
    expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({ type: 'sse_reconnecting', retryCount: 1, delayMs: 500 }));
  });
  stop();
});
