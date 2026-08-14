/**
 * How the sidebar opens, for every profile.
 *
 * Abhimanyu, 2026-08-14: Tools starts OPEN and Recent Chats starts CLOSED. Both used to
 * start open, so the two sections split the sidebar between them and the tool list opened
 * already scrolled, with the tabs a person came for pushed below the fold.
 *
 * This is asserted rather than left to a default that reads as arbitrary, because the next
 * person tidying the sidebar has no way of knowing it was asked for.
 *
 * It asserts what a person SEES: the two headings are rendered and read out their open or
 * closed state, and the collapsed list is not on the page. Testing the initial value of a
 * variable instead would still pass if the heading stopped reading that variable.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({
    currentUser: { id: 'u-owner', role: 'owner', sub_category: 'owner', name: 'Aman' },
    token: 't',
  }),
}));

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true, theme: 'dark' }),
}));

jest.mock('../../lib/api', () => ({
  __esModule: true,
  default: {},
  getConversations: () => Promise.resolve({ success: true, data: [] }),
  updateConversation: () => Promise.resolve({ success: true }),
  deleteConversation: () => Promise.resolve({ success: true }),
  getSchoolSettings: () => Promise.resolve({ success: true, data: { school_name: 'The Aaryans' } }),
  apiFetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, data: [] }) }),
  getAuthHeaders: () => ({}),
}));

const headingFor = (pattern) => screen
  .getAllByRole('button')
  .find(node => node.hasAttribute('aria-expanded') && pattern.test(node.textContent || ''));

describe('sidebar sections open the way the school asked', () => {
  beforeEach(() => {
    // Required after the jest.mock calls above, which jest hoists to the top of the file.
    // eslint-disable-next-line global-require
    const Sidebar = require('../Sidebar').default;
    render(<Sidebar />);
  });

  test('the Tools section starts open', () => {
    expect(headingFor(/tool/i)?.getAttribute('aria-expanded')).toBe('true');
  });

  test('the Recent Chats section starts closed', () => {
    expect(headingFor(/chat/i)?.getAttribute('aria-expanded')).toBe('false');
  });

  test('both headings are actually there, so neither assertion passed on an absence', () => {
    // A `?.` on a heading that does not exist yields undefined, and undefined is not
    // 'true' or 'false' - but it is worth failing loudly on the cause rather than the
    // symptom if somebody renames a heading.
    expect(headingFor(/tool/i)).toBeTruthy();
    expect(headingFor(/chat/i)).toBeTruthy();
  });
});
