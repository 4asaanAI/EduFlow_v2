import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import Layout from '../Layout';

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({
    currentUser: { id: 'owner-1', role: 'owner', name: 'Owner User' },
    logout: () => {},
  }),
}));

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true, theme: 'dark', toggleTheme: () => {} }),
}));

// D-48: a hand-written mock factory does NOT fall through to the real module, so
// every export the factory forgets is `undefined`. The shell calls ~15 API helpers
// across Sidebar/Header/ChatInterface, and the old factory listed 8 — the missing
// ones threw inside effects and surfaced as an unreadable AggregateError at render().
// Derive the stub from the real module's export list instead, so API helpers added
// later cannot silently break this suite again.
//
// The stubs are PLAIN functions, not jest.fn(): Create React App's Jest preset sets
// `resetMocks: true`, which strips the implementation off every jest.fn() before each
// test. jest.fn(async () => ...) would therefore return `undefined`, and the shell's
// `.then(...)` calls would throw all over again.
jest.mock('../../lib/api', () => {
  const actual = jest.requireActual('../../lib/api');
  const stub = {};
  Object.keys(actual).forEach((key) => {
    stub[key] = typeof actual[key] === 'function'
      ? async () => ({ success: true, data: [] })
      : actual[key];
  });
  stub.createConversation = async () => ({ success: true, data: { id: 'conv-1' } });
  stub.sendMessageStream = () => {};
  stub.subscribeSSE = () => ({ close: () => {} });
  stub.getBrowserSseSessionId = () => 'test-session';
  return stub;
});

// Layout clears `?tool=` once per browser session, the first time it sees a user id
// it has not recorded (the "someone else logged in" reset). Marking the session as
// already belonging to this user is what a normal in-session navigation or reload
// looks like, which is the case these tests are about.
beforeEach(() => {
  sessionStorage.setItem('eduflow_session_user', 'owner-1');
});

afterEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
}

function Harness({ initialEntries }) {
  return (
    <MemoryRouter initialEntries={initialEntries}>
      <LocationProbe />
      <Layout />
    </MemoryRouter>
  );
}

test('restores active tool from URL search param', async () => {
  render(<Harness initialEntries={['/?tool=attendance-recorder']} />);

  // The shell is in tool mode, not chat mode.
  expect(await screen.findByTestId('back-to-chat-btn')).toBeInTheDocument();

  // The tool named in the URL is the one that actually mounted. This test id
  // belongs to AttendanceRecorder itself, so it can only appear if that specific
  // panel rendered — not a spinner, not a placeholder, not a different tool.
  expect(await screen.findByTestId('attendance-recorder-tool')).toBeInTheDocument();
  expect(screen.queryByText('Loading tool...')).not.toBeInTheDocument();
  expect(screen.queryByText(/Something went wrong/i)).not.toBeInTheDocument();

  // A different tool must NOT be showing.
  expect(screen.queryByTestId('fee-sync-tool')).not.toBeInTheDocument();

  // The URL was not rewritten behind our back.
  expect(screen.getByTestId('location-search')).toHaveTextContent('tool=attendance-recorder');
});

test('tool selection updates URL search param', async () => {
  render(<Harness initialEntries={['/?tool=attendance-recorder']} />);
  expect(await screen.findByTestId('attendance-recorder-tool')).toBeInTheDocument();
  expect(screen.getByTestId('location-search')).toHaveTextContent('tool=attendance-recorder');

  // Fee Sync lives inside the owner sidebar's collapsed "Fee Summary" group.
  fireEvent.click(screen.getByText('Fee Summary'));
  fireEvent.click(await screen.findByTestId('tool-btn-fee-sync'));

  // The address bar follows the selection — this is what D-44's deep linking
  // is going to build on, so it has to be nailed down.
  await waitFor(() => {
    expect(screen.getByTestId('location-search')).toHaveTextContent('tool=fee-sync');
  });
  expect(screen.getByTestId('location-search')).not.toHaveTextContent('attendance-recorder');

  // And the newly named tool is the one on screen, replacing the previous one.
  expect(await screen.findByTestId('fee-sync-tool')).toBeInTheDocument();
  expect(screen.queryByTestId('attendance-recorder-tool')).not.toBeInTheDocument();
});
