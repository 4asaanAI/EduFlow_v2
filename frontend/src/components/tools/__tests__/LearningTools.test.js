/* R10.4 — "What I've learned" panel smoke + control-action coverage.
 * Note: CRA's jest config sets resetMocks:true, which strips factory-provided mock
 * implementations before each test — so implementations are (re)set in beforeEach. */
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: false }),
}));

jest.mock('../../../lib/api', () => ({
  getLearningOverview: jest.fn(),
  activateCorrection: jest.fn(),
  rejectCorrection: jest.fn(),
  editMemory: jest.fn(),
  deactivateMemory: jest.fn(),
  deleteMemory: jest.fn(),
  bulkDeleteMemories: jest.fn(),
  deleteSkill: jest.fn(),
}));

import LearningTools from '../LearningTools';
import * as api from '../../../lib/api';

beforeEach(() => {
  api.getLearningOverview.mockResolvedValue({
    success: true,
    data: {
      memories: [{ id: 'm1', text: 'owner prefers concise fee summaries', category: 'preference' }],
      deactivated_memories: [{ id: 'm2', text: 'old note', category: 'fact' }],
      skills: [{ id: 's1', title: 'Month-end sweep', needs_update: true }],
      pending_corrections: [{ id: 'fb1', candidate_correction: 'always include branch breakdown' }],
    },
  });
  api.activateCorrection.mockResolvedValue({ success: true });
  api.deactivateMemory.mockResolvedValue({ success: true });
});

test('R10.4: lists memories, skills (with drift flag), deactivated notes, and pending corrections', async () => {
  render(<LearningTools />);
  expect(await screen.findByText(/owner prefers concise fee summaries/)).toBeInTheDocument();
  expect(screen.getByText(/always include branch breakdown/)).toBeInTheDocument();
  expect(screen.getByText(/Month-end sweep/)).toBeInTheDocument();
  expect(screen.getByText(/needs updating/)).toBeInTheDocument();
  expect(screen.getByText(/old note/)).toBeInTheDocument();
});

test('R10.4: activating a pending correction calls the API', async () => {
  render(<LearningTools />);
  fireEvent.click(await screen.findByText(/Activate/));
  await waitFor(() => expect(api.activateCorrection).toHaveBeenCalledWith('fb1'));
});

test('R10.4: reactivate calls deactivateMemory with superseded=false', async () => {
  render(<LearningTools />);
  fireEvent.click(await screen.findByText(/Reactivate/));
  await waitFor(() => expect(api.deactivateMemory).toHaveBeenCalledWith('m2', false));
});
