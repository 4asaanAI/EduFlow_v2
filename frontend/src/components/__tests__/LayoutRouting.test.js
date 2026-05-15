import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import Layout from '../Layout';

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({
    currentUser: { id: 'owner-1', role: 'owner', name: 'Owner User' },
    logout: jest.fn(),
  }),
}));

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true, theme: 'dark', toggleTheme: jest.fn() }),
}));

jest.mock('../../lib/api', () => ({
  createConversation: jest.fn(async () => ({ success: true, data: { id: 'conv-1' } })),
  getConversations: jest.fn(async () => ({ success: true, data: [] })),
  getMessages: jest.fn(async () => ({ success: true, data: [] })),
  updateConversation: jest.fn(),
  deleteConversation: jest.fn(),
  sendMessageStream: jest.fn(),
  executeTool: jest.fn(async () => ({ success: true, data: { message: 'Done.' } })),
  getBrowserSseSessionId: jest.fn(() => 'test-session'),
}));

function Harness({ initialEntries }) {
  return (
    <MemoryRouter initialEntries={initialEntries}>
      <LocationProbe />
      <Layout />
    </MemoryRouter>
  );
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
}

test('restores active tool from URL search param', async () => {
  render(<Harness initialEntries={['/?tool=attendance-recorder']} />);
  expect(screen.getByTestId('back-to-chat-btn')).toBeInTheDocument();
  expect(await screen.findByText('Attendance Recorder')).toBeInTheDocument();
});

test('tool selection updates URL search param', async () => {
  render(<Harness initialEntries={['/?tool=attendance-recorder']} />);
  expect(await screen.findByText('Attendance Recorder')).toBeInTheDocument();
  fireEvent.click(screen.getByText(/Tools \(/));
  fireEvent.click(screen.getByTestId('tool-btn-fee-sync'));
  await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('tool=fee-sync'));
});
