/**
 * R11.5 — Conversation Trace Viewer.
 * Verifies both outcomes render AND (confidentiality, non-negotiable) that no
 * underlying LLM provider/model string leaks into the rendered output. The only
 * assistant label allowed is the branded "Layaa AI".
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true }),
}));
jest.mock('../../lib/api', () => ({
  getConversationTrace: jest.fn(),
}));

import ConversationTrace from '../tools/ConversationTrace';
import { getConversationTrace } from '../../lib/api';

afterEach(() => jest.clearAllMocks());

const TRACE = {
  success: true,
  data: [
    {
      message_id: 'm1',
      created_at: '2026-07-10T09:15:00',
      outcome: 'answered',
      language: 'en',
      tools: [{ tool: 'get_fee_summary', status: 'done' }],
      assistant: 'Layaa AI',
      finish_reason: 'stop',
      ok: true,
      error_type: null,
      tokens: 312,
    },
    {
      message_id: 'm2',
      created_at: '2026-07-10T09:16:00',
      outcome: 'unavailable',
      language: 'en',
      tools: [],
      assistant: 'Layaa AI',
      finish_reason: null,
      ok: false,
      error_type: 'upstream_unavailable',
      tokens: 0,
    },
  ],
  meta: { count: 2, conversation_id: 'conv-123' },
};

async function loadTrace() {
  getConversationTrace.mockResolvedValueOnce(TRACE);
  render(<ConversationTrace />);
  fireEvent.change(screen.getByTestId('trace-conv-id-input'), { target: { value: 'conv-123' } });
  fireEvent.click(screen.getByTestId('trace-load-btn'));
  await waitFor(() => expect(screen.getByTestId('trace-timeline')).toBeInTheDocument());
}

test('renders both answered and unavailable outcomes', async () => {
  await loadTrace();
  expect(getConversationTrace).toHaveBeenCalledWith('conv-123');
  expect(screen.getByTestId('trace-outcome-answered')).toBeInTheDocument();
  expect(screen.getByTestId('trace-outcome-unavailable')).toBeInTheDocument();
  expect(screen.getByText('Answered')).toBeInTheDocument();
  expect(screen.getByText('Unavailable')).toBeInTheDocument();
  // error_type surfaces for the failed turn
  expect(screen.getByText(/upstream_unavailable/)).toBeInTheDocument();
});

test('never leaks the underlying LLM provider/model (confidentiality)', async () => {
  await loadTrace();
  const rendered = document.body.textContent.toLowerCase();
  expect(rendered).not.toMatch(/azure/);
  expect(rendered).not.toMatch(/openai/);
  expect(rendered).not.toMatch(/gpt/);
  // The only assistant label shown is the branded name.
  expect(screen.getAllByText('Layaa AI').length).toBeGreaterThan(0);
});
