import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Header from '../Header';

// Search-result profile open (2026-09-23). A student/staff result clicked in the
// top-bar search used to open a list/wrong screen instead of that person's actual
// profile - unlike School Directory, which deep-links `?tool=&focus=<id>` straight
// into the profile drawer. This asserts the search panel now dispatches the same
// `{tool, focus}` `open-tool` event Directory's own click handler implies, instead
// of a bare tool-id string.

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'owner-1', role: 'owner', name: 'Owner User' } }),
}));

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true, theme: 'dark', toggleTheme: () => {} }),
}));

jest.mock('../../contexts/MessagingContext', () => ({
  useMessaging: () => ({ available: false, unreadCount: 0 }),
}));

let mockSearchResults = [];

jest.mock('../../lib/api', () => {
  const actual = jest.requireActual('../../lib/api');
  const stub = {};
  Object.keys(actual).forEach((key) => {
    stub[key] = typeof actual[key] === 'function'
      ? async () => ({ success: true, data: [] })
      : actual[key];
  });
  // `Header`'s search panel calls the raw `apiFetch` (not a named api.js helper)
  // and awaits `.json()` on the result - the wholesale stub above returns a plain
  // object, so this one path needs its own shape.
  stub.apiFetch = async (url) => {
    if (String(url).includes('/search?q=')) {
      return { json: async () => ({ success: true, data: mockSearchResults }) };
    }
    return { json: async () => ({ success: true, data: [] }) };
  };
  return stub;
});

beforeEach(() => {
  mockSearchResults = [];
});

function openSearchAndType(query) {
  fireEvent.click(screen.getByText(/Search students, staff/));
  const input = screen.getByLabelText('Search tools, students and staff');
  fireEvent.change(input, { target: { value: query } });
}

test('clicking a student search result dispatches open-tool with {tool: student-database, focus: id}', async () => {
  mockSearchResults = [{ type: 'student', id: 'student-42', name: 'Aman Litt', subtitle: '10th A' }];
  const handler = jest.fn();
  window.addEventListener('open-tool', handler);

  render(<MemoryRouter><Header /></MemoryRouter>);
  openSearchAndType('Aman');

  const result = await screen.findByText('Aman Litt');
  act(() => { fireEvent.click(result); });

  await waitFor(() => expect(handler).toHaveBeenCalled());
  expect(handler.mock.calls[0][0].detail).toEqual({ tool: 'student-database', focus: 'student-42' });

  window.removeEventListener('open-tool', handler);
});

test('clicking a staff search result dispatches open-tool with {tool: staff-tracker, focus: id}', async () => {
  mockSearchResults = [{ type: 'staff', id: 'staff-7', name: 'Chaman Singh', subtitle: 'Transport Head' }];
  const handler = jest.fn();
  window.addEventListener('open-tool', handler);

  render(<MemoryRouter><Header /></MemoryRouter>);
  openSearchAndType('Chaman');

  const result = await screen.findByText('Chaman Singh');
  act(() => { fireEvent.click(result); });

  await waitFor(() => expect(handler).toHaveBeenCalled());
  expect(handler.mock.calls[0][0].detail).toEqual({ tool: 'staff-tracker', focus: 'staff-7' });

  window.removeEventListener('open-tool', handler);
});

test('clicking a tool search result still dispatches the plain tool-id string (unchanged)', async () => {
  mockSearchResults = [{ type: 'tool', id: 'attendance-recorder', name: 'Attendance', subtitle: 'tool' }];
  const handler = jest.fn();
  window.addEventListener('open-tool', handler);

  render(<MemoryRouter><Header /></MemoryRouter>);
  openSearchAndType('Attend');

  const result = await screen.findByText('Attendance');
  act(() => { fireEvent.click(result); });

  await waitFor(() => expect(handler).toHaveBeenCalled());
  expect(handler.mock.calls[0][0].detail).toBe('attendance-recorder');

  window.removeEventListener('open-tool', handler);
});
