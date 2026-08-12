import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import Layout from '../Layout';

// The signed-in user is a mutable module-level value so a test can render the shell
// as a SECOND person - which is what D-59's safety property is about. Reset in
// beforeEach so one test cannot leak its user into the next. The `mock` prefix is
// required: jest.mock() factories may only reference out-of-scope names spelled that way.
let mockCurrentUser = { id: 'owner-1', role: 'owner', name: 'Owner User' };

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({
    currentUser: mockCurrentUser,
    logout: () => {},
  }),
}));

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true, theme: 'dark', toggleTheme: () => {} }),
}));

jest.mock('../../contexts/MessagingContext', () => ({
  useMessaging: () => ({ available: false, unreadCount: 0 }),
}));

// D-48: a hand-written mock factory does NOT fall through to the real module, so
// every export the factory forgets is `undefined`. The shell calls ~15 API helpers
// across Sidebar/Header/ChatInterface, and the old factory listed 8 - the missing
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

// D-59, fixed 2026-08-04: this used to seed `eduflow_session_user` before every test,
// because Layout cleared `?tool=` whenever the tab held no record of the current user
// - which on a fresh tab is always. That seeding was a workaround for the bug, and the
// bug is gone: a first visit now records the user and leaves the URL alone. Seeding it
// here would hide a regression of exactly that behaviour, so storage starts EMPTY, the
// way a real new tab does. The "different person" case seeds deliberately, in the test
// that is about it.
beforeEach(() => {
  sessionStorage.clear();
  mockCurrentUser = { id: 'owner-1', role: 'owner', name: 'Owner User' };
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
  // panel rendered - not a spinner, not a placeholder, not a different tool.
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

  // R4-6 (2026-08-12): every profile now uses the SAME tab layout, so the owner's hubs
  // live inside tabs rather than sitting flat at the top of the sidebar. The Finance hub
  // is reached by opening its tab first. Only the route to the button changed; the deep
  // link below is unchanged and is still the canonical destination.
  fireEvent.click(await screen.findByTestId('tool-group-finance-commercial-hub'));
  fireEvent.click(await screen.findByTestId('tool-btn-finance-commercial-hub'));
  expect(await screen.findByTestId('management-hub-finance-commercial-hub')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Open Fee Sync' }));

  // The address bar follows the selection - this is what D-44's deep linking
  // is going to build on, so it has to be nailed down.
  await waitFor(() => {
    expect(screen.getByTestId('location-search')).toHaveTextContent('tool=fee-sync');
  });
  expect(screen.getByTestId('location-search')).not.toHaveTextContent('attendance-recorder');

  // And the newly named tool is the one on screen, replacing the previous one.
  expect(await screen.findByTestId('fee-sync-tool')).toBeInTheDocument();
  expect(screen.queryByTestId('attendance-recorder-tool')).not.toBeInTheDocument();
});


// ─── D-59: a link straight to a screen, in a fresh browser tab ────────────────
// Owner decision 2026-08-04 (decision 3): links must always work, with the shared-
// computer safety check made smarter rather than removed. Both directions are
// tested; the second one is the safety property and matters more than the first.

test('a deep link survives a cold browser tab with no session record', async () => {
  // A genuinely fresh tab: nothing recorded at all. This is the case that used to
  // dump the visitor on the chat screen.
  expect(sessionStorage.getItem('eduflow_session_user')).toBeNull();

  render(<Harness initialEntries={['/?tool=attendance-recorder']} />);

  expect(await screen.findByTestId('attendance-recorder-tool')).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.getByTestId('location-search')).toHaveTextContent('tool=attendance-recorder');
  });

  // ...and the tab now remembers who this was, so the next person is detectable.
  expect(sessionStorage.getItem('eduflow_session_user')).toBe('owner-1');
});

test('a genuinely different user still gets the previous tool cleared', async () => {
  // Someone else used this tab first and their id is on record. This is the shared-
  // school-computer case the check exists for: the link must NOT open.
  sessionStorage.setItem('eduflow_session_user', 'someone-else-9');

  render(<Harness initialEntries={['/?tool=attendance-recorder']} />);

  await waitFor(() => {
    expect(screen.getByTestId('location-search')).not.toHaveTextContent('tool=');
  });
  expect(screen.queryByTestId('attendance-recorder-tool')).not.toBeInTheDocument();
  expect(screen.queryByTestId('back-to-chat-btn')).not.toBeInTheDocument();

  // The tab is re-stamped with the person actually signed in now.
  expect(sessionStorage.getItem('eduflow_session_user')).toBe('owner-1');
});
