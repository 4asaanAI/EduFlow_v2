/**
 * UI Sweep Epic 5 — the streaming turn.
 *
 * 5.1: one progress account, one left edge (owner item 12, UX-DR8).
 * 5.2: a stall says so instead of spinning forever (owner item 13, NFR-P3).
 */
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'u1', role: 'owner', name: 'Aman' } }),
}));
jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));
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

import ChatInterface, { STREAM_GUTTER, STALL_SLOW_MS, STALL_DEAD_MS } from '../ChatInterface';
import {
  createConversation, executeTool, getMessages, sendMessageStream, uploadChatFile,
} from '../../lib/api';

beforeEach(() => {
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: async () => ({ success: false }) }));
  window.HTMLElement.prototype.scrollIntoView = jest.fn();
  // CRA's jest config sets `resetMocks: true`, which wipes the implementations given
  // in the module factory before every test. Re-establish them here, or the first
  // effect that calls one gets `undefined` back and throws on `.then`.
  createConversation.mockResolvedValue({ success: true, data: { id: 'c1' } });
  getMessages.mockResolvedValue({ success: true, data: [] });
  executeTool.mockResolvedValue({ success: false });
  uploadChatFile.mockResolvedValue({ success: false });
});
afterEach(() => {
  jest.clearAllMocks();
  jest.useRealTimers();
});

function renderChat() {
  return render(<ChatInterface activeConvId="c1" activeConvTitle="T" onConvCreated={() => {}} />);
}

async function send(text = 'how many students are absent?') {
  const input = await screen.findByTestId('chat-input');
  fireEvent.change(input, { target: { value: text } });
  fireEvent.click(screen.getByTestId('chat-send'));
}

/** Hold the stream open so the streaming block stays mounted. */
function holdStreamOpen(onReady) {
  sendMessageStream.mockImplementation((cid, text, user, onEvent) => {
    onReady?.(onEvent);
    return new Promise(() => {});   // never resolves
  });
}

// ── Story 5.1 — one progress account, one left edge ─────────────────────────────

test('a running tool is announced once, by the panel, not also by a badge', async () => {
  // The panel is fed tool_start/tool_done, so rendering ToolCallBadge alongside it
  // announced the SAME tool twice in two shapes. That is owner item 12.
  let emit;
  holdStreamOpen((onEvent) => { emit = onEvent; });
  renderChat();
  await send();

  await act(async () => {
    emit({ type: 'tool_call', tool: 'get_school_pulse', status: 'running' });
    emit({ type: 'thinking', step: 'tool_start', label: 'get_school_pulse', status: 'active' });
  });

  await waitFor(() => expect(screen.getByTestId('chat-progress-panel')).toBeInTheDocument());
  expect(screen.queryByTestId('chat-tool-badge')).not.toBeInTheDocument();
});

test('with no progress steps the badge is still shown, so nothing is lost', async () => {
  let emit;
  holdStreamOpen((onEvent) => { emit = onEvent; });
  renderChat();
  await send();

  await act(async () => {
    emit({ type: 'tool_call', tool: 'get_fee_summary', status: 'running' });
  });

  await waitFor(() => expect(screen.getByTestId('chat-tool-badge')).toBeInTheDocument());
  expect(screen.queryByTestId('chat-progress-panel')).not.toBeInTheDocument();
});

test('everything stacked in the turn shares one left edge', async () => {
  // Asserted as a value rather than eyeballed: three stacked elements at 42px, 0px
  // and 42px is exactly the defect a screenshot review keeps missing.
  let emit;
  holdStreamOpen((onEvent) => { emit = onEvent; });
  renderChat();
  await send();

  await act(async () => {
    emit({ type: 'thinking', step: 'tool_start', label: 'get_school_pulse', status: 'active' });
  });

  const panel = await screen.findByTestId('chat-progress-panel');
  expect(panel).toHaveStyle(`padding-left: ${STREAM_GUTTER}px`);
});

test('the typing indicator and the progress panel are never both shown', async () => {
  let emit;
  holdStreamOpen((onEvent) => { emit = onEvent; });
  renderChat();
  await send();

  await act(async () => {
    emit({ type: 'thinking', step: 'searching', label: 'students', status: 'active' });
  });

  await waitFor(() => expect(screen.getByTestId('chat-progress-panel')).toBeInTheDocument());
  expect(screen.queryByTestId('flo-typing-avatar')).not.toBeInTheDocument();
});

// ── Story 5.2 — a stall says so ────────────────────────────────────────────────

test('silence eventually says Flo is taking longer than usual', async () => {
  jest.useFakeTimers();
  holdStreamOpen();
  renderChat();
  await send();

  expect(screen.queryByTestId('chat-stall-notice')).not.toBeInTheDocument();

  await act(async () => { jest.advanceTimersByTime(STALL_SLOW_MS + 100); });

  expect(screen.getByTestId('chat-stall-notice')).toHaveTextContent(/taking longer than usual/i);
});

test('prolonged silence declares the turn failed and suggests retrying', async () => {
  jest.useFakeTimers();
  holdStreamOpen();
  renderChat();
  await send();

  await act(async () => { jest.advanceTimersByTime(STALL_DEAD_MS + 100); });

  expect(screen.getByTestId('chat-stall-notice')).toHaveTextContent(/try sending it again/i);
});

test('any activity resets the watchdog, so a slow but working answer is never called stalled', async () => {
  // THE test for this story. A keepalive or a thinking step is proof of life.
  jest.useFakeTimers();
  let emit;
  holdStreamOpen((onEvent) => { emit = onEvent; });
  renderChat();
  await send();

  for (let i = 0; i < 4; i += 1) {
    await act(async () => { jest.advanceTimersByTime(STALL_SLOW_MS - 1000); });
    await act(async () => { emit({ type: 'thinking', step: 'analyzing', status: 'active' }); });
  }

  expect(screen.queryByTestId('chat-stall-notice')).not.toBeInTheDocument();
});

test('the stall notice is announced to assistive technology', async () => {
  jest.useFakeTimers();
  holdStreamOpen();
  renderChat();
  await send();

  await act(async () => { jest.advanceTimersByTime(STALL_SLOW_MS + 100); });

  const notice = screen.getByTestId('chat-stall-notice');
  expect(notice).toHaveAttribute('role', 'status');
  expect(notice).toHaveAttribute('aria-live', 'polite');
});

test('unmounting mid-stream leaves no timer to fire at a dead component', async () => {
  jest.useFakeTimers();
  holdStreamOpen();
  const { unmount } = renderChat();
  await send();

  const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
  unmount();
  await act(async () => { jest.advanceTimersByTime(STALL_DEAD_MS + 1000); });

  expect(spy).not.toHaveBeenCalledWith(
    expect.stringContaining('unmounted component'), expect.anything(), expect.anything(),
  );
  spy.mockRestore();
});
