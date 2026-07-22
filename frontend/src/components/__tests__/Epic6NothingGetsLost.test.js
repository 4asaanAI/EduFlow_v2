/**
 * UI Sweep Epic 6 — Nothing Gets Lost.
 *
 * 6.1: the bell counts what is actually unread (owner item 14).
 * 6.3: every notification is reachable, not just the newest twenty.
 * 6.5: every chat is reachable, searchable, and clearable in bulk (owner item 16).
 */
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'u1', role: 'owner', name: 'Aman' } }),
}));
jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true, toggleTheme: jest.fn() }),
}));
jest.mock('../../lib/api', () => ({
  getAcademicYear: jest.fn(),
  getNotifications: jest.fn(),
  getUnreadNotificationCount: jest.fn(),
  markAllNotificationsRead: jest.fn(),
  markNotificationRead: jest.fn(),
  getConversations: jest.fn(),
  bulkDeleteConversations: jest.fn(),
  deleteConversation: jest.fn(),
  updateConversation: jest.fn(),
}));

import Header from '../Header';
import AllNotifications from '../tools/AllNotifications';
import AllChats, { MAX_BULK_DELETE } from '../tools/AllChats';
import { PAGE_SIZES } from '../../hooks/useTablePrefs';
import {
  bulkDeleteConversations,
  deleteConversation,
  getAcademicYear,
  getConversations,
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
  updateConversation,
} from '../../lib/api';

const notif = (i, over = {}) => ({
  id: `n-${i}`, type: 'info', title: `Notification ${i}`, message: `Message ${i}`,
  read: false, created_at: `2026-07-0${(i % 9) + 1}T10:00:00`, ...over,
});

const conv = (i, over = {}) => ({
  id: `c-${i}`, title: `Chat ${i}`, is_pinned: false, is_starred: false,
  created_at: '2026-07-01T09:00:00', updated_at: `2026-07-0${(i % 9) + 1}T10:00:00`, ...over,
});

const listResponse = (data, meta = {}) => ({
  success: true, data,
  meta: { page: 1, limit: 15, total: data.length, digest_count: 0, has_fallback: false, unread_total: 0, ...meta },
});

beforeEach(() => {
  // CRA's jest config sets `resetMocks: true`, which wipes the implementations
  // declared in the module factory above before every test. Epic 5 lost a whole
  // first run to this. Re-establish them here, every time.
  getAcademicYear.mockResolvedValue({ success: true, data: { name: '2026-27' } });
  getNotifications.mockResolvedValue(listResponse([]));
  getUnreadNotificationCount.mockResolvedValue({ success: true, data: { unread_count: 0 } });
  markAllNotificationsRead.mockResolvedValue({ success: true });
  markNotificationRead.mockResolvedValue({ success: true });
  getConversations.mockResolvedValue({ success: true, data: [], meta: { page: 1, limit: 15, total: 0, sort: 'recent' } });
  bulkDeleteConversations.mockResolvedValue({ success: true, data: { deleted: 0, not_found: 0 } });
  deleteConversation.mockResolvedValue({ success: true });
  updateConversation.mockResolvedValue({ success: true });
  window.localStorage.clear();
});

afterEach(() => jest.clearAllMocks());

const renderHeader = () => render(<Header activeTool={null} onBackToChat={() => {}} onOpenProfile={() => {}} onOpenSettings={() => {}} onToggleSidebar={() => {}} />);

// ── Story 6.1: the bell ──────────────────────────────────────────────────────

describe('6.1 the bell tells the truth about what is waiting', () => {
  test('asks the endpoint written for the question, not page 1 of the list', async () => {
    renderHeader();
    await waitFor(() => expect(getUnreadNotificationCount).toHaveBeenCalled());
  });

  test('a read notification produces NO badge', async () => {
    // The original defect: it filtered on `n.is_read`, a field that does not
    // exist, so this case painted the dot anyway and never cleared it.
    getUnreadNotificationCount.mockResolvedValue({ success: true, data: { unread_count: 0 } });
    getNotifications.mockResolvedValue(listResponse([notif(1, { read: true })], { total: 1 }));

    renderHeader();

    await waitFor(() => expect(getUnreadNotificationCount).toHaveBeenCalled());
    expect(screen.queryByTestId('notif-badge')).toBeNull();
  });

  test('shows the number, and it is the count across every page', async () => {
    getUnreadNotificationCount.mockResolvedValue({ success: true, data: { unread_count: 7 } });

    renderHeader();

    const badge = await screen.findByTestId('notif-badge');
    expect(badge).toHaveTextContent('7');
    expect(badge).toHaveAttribute('aria-label', '7 unread notifications');
  });

  test('caps the display at 9+ while the label states the real figure', async () => {
    getUnreadNotificationCount.mockResolvedValue({ success: true, data: { unread_count: 312 } });

    renderHeader();

    const badge = await screen.findByTestId('notif-badge');
    expect(badge).toHaveTextContent('9+');
    expect(badge).toHaveAttribute('aria-label', '312 unread notifications');
  });

  test('a failed count leaves the previous figure standing, never zero', async () => {
    getUnreadNotificationCount.mockResolvedValue({ success: true, data: { unread_count: 4 } });
    renderHeader();
    await screen.findByTestId('notif-badge');

    // "Nothing is waiting" claimed on the strength of a network error is the
    // Epic 4 defect — a failure that looks like a figure — in a new place.
    getUnreadNotificationCount.mockRejectedValue(new Error('offline'));
    fireEvent.click(screen.getByTestId('notifications-btn'));
    fireEvent.click(screen.getByTestId('notifications-btn'));

    await waitFor(() => expect(screen.getByTestId('notif-badge')).toHaveTextContent('4'));
  });

  test('the panel reports the server total, not the rows it happens to hold', async () => {
    getNotifications.mockResolvedValue(listResponse([notif(1), notif(2)], { total: 60, unread_total: 60 }));
    getUnreadNotificationCount.mockResolvedValue({ success: true, data: { unread_count: 60 } });

    renderHeader();
    fireEvent.click(await screen.findByTestId('notifications-btn'));

    // It used to say "2 unread" here — the number of rows in front of it.
    expect(await screen.findByTestId('notif-panel-subtitle')).toHaveTextContent('60 unread');
  });

  test('mark all read re-reads instead of assuming zero', async () => {
    getNotifications.mockResolvedValue(listResponse([notif(1)], { total: 30, unread_total: 30 }));
    renderHeader();
    fireEvent.click(await screen.findByTestId('notifications-btn'));
    await screen.findByText('Mark all read');

    getNotifications.mockResolvedValue(listResponse([notif(1, { read: true })], { total: 30, unread_total: 0 }));
    fireEvent.click(screen.getByText('Mark all read'));

    await waitFor(() => expect(markAllNotificationsRead).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId('notif-panel-subtitle')).toHaveTextContent('All caught up'));
  });

  test('says WHY a count survives mark-all-read rather than looking broken', async () => {
    getNotifications.mockResolvedValue(listResponse([notif(1)], { total: 5, unread_total: 5 }));
    renderHeader();
    fireEvent.click(await screen.findByTestId('notifications-btn'));
    await screen.findByText('Mark all read');

    // mark-all-read deliberately spares whatever arrived mid-request. Correct —
    // and a bare non-zero number afterwards reads as "the button failed".
    getNotifications.mockResolvedValue(listResponse([notif(9)], { total: 6, unread_total: 1 }));
    fireEvent.click(screen.getByText('Mark all read'));

    await waitFor(() => expect(screen.getByTestId('notif-panel-subtitle')).toHaveTextContent('1 arrived just now'));
  });

  test('the panel footer is a way through, not a dead count label', async () => {
    getNotifications.mockResolvedValue(listResponse([notif(1)], { total: 41 }));
    const opened = [];
    window.addEventListener('open-tool', e => opened.push(e.detail));

    renderHeader();
    fireEvent.click(await screen.findByTestId('notifications-btn'));
    fireEvent.click(await screen.findByTestId('notif-view-all'));

    expect(opened).toContain('all-notifications');
  });

  test('no colour is decided in JavaScript any more (D-22)', () => {
    // eslint-disable-next-line global-require
    const src = require('fs').readFileSync(require.resolve('../Header.js'), 'utf8');
    const offenders = src.split('\n').filter(l => /isDark \?/.test(l) && !l.trim().startsWith('//'));
    expect(offenders).toEqual([]);
  });
});

// ── Story 6.3: the All Notifications page ────────────────────────────────────

describe('6.3 every notification is reachable', () => {
  test('asks the server to leave the synthetic rows out', async () => {
    render(<AllNotifications />);
    await waitFor(() => expect(getNotifications).toHaveBeenCalled());

    // An "All Good" row inside a table with a row count and a page indicator is
    // a notification telling you everything is fine, invented on the spot.
    expect(getNotifications.mock.calls[0][0]).toMatchObject({ include_digest: 'false' });
  });

  test('the server pages — the size goes to the API, not a client-side slice', async () => {
    getNotifications.mockResolvedValue(listResponse([notif(1)], { total: 300, unread_total: 0 }));
    render(<AllNotifications />);
    await screen.findByTestId('notifications-datatable');

    fireEvent.change(screen.getByTestId('notifications-page-size'), { target: { value: '25' } });

    await waitFor(() => {
      const last = getNotifications.mock.calls[getNotifications.mock.calls.length - 1][0];
      expect(last).toMatchObject({ limit: 25, page: 1 });
    });
  });

  test('changing the size returns to page 1 rather than stranding the reader', async () => {
    getNotifications.mockResolvedValue(listResponse([notif(1)], { total: 300 }));
    render(<AllNotifications />);
    await screen.findByTestId('notifications-datatable');

    fireEvent.click(screen.getByTestId('notifications-next'));
    await waitFor(() => {
      const last = getNotifications.mock.calls[getNotifications.mock.calls.length - 1][0];
      expect(last.page).toBe(2);
    });
    // The re-fetch swaps the table for a loading line; wait for it back before
    // touching a control inside it.
    await screen.findByTestId('notifications-page-size');

    fireEvent.change(screen.getByTestId('notifications-page-size'), { target: { value: '30' } });

    await waitFor(() => {
      const last = getNotifications.mock.calls[getNotifications.mock.calls.length - 1][0];
      expect(last.page).toBe(1);
    });
  });

  test('the column heading asks the SERVER to re-order everything (FR82)', async () => {
    getNotifications.mockResolvedValue(listResponse([notif(1), notif(2)], { total: 300 }));
    render(<AllNotifications />);
    await screen.findByTestId('notifications-datatable');

    fireEvent.click(screen.getByTestId('notifications-sort-created_at'));

    await waitFor(() => {
      const last = getNotifications.mock.calls[getNotifications.mock.calls.length - 1][0];
      expect(last).toMatchObject({ sort: 'oldest', page: 1 });
    });
  });

  test('"nothing unread" and "nothing ever arrived" are different messages', async () => {
    getNotifications.mockResolvedValue(listResponse([], { total: 0 }));
    const { rerender } = render(<AllNotifications />);
    await screen.findByTestId('all-notifications-empty');

    rerender(<AllNotifications />);
    fireEvent.click(screen.getByTestId('notif-filter-unread'));

    await screen.findByTestId('all-notifications-none-unread');
    expect(screen.queryByTestId('all-notifications-empty')).toBeNull();
  });

  test('a load failure is an error with a retry, never an empty list', async () => {
    getNotifications.mockResolvedValue({ success: false, detail: 'upstream is down' });

    render(<AllNotifications />);

    const err = await screen.findByTestId('all-notifications-error');
    expect(err).toHaveTextContent('upstream is down');
    expect(err).toHaveAttribute('role', 'alert');
    expect(screen.queryByTestId('all-notifications-empty')).toBeNull();
  });

  test('mark-all states its real scope, not the rows on screen', async () => {
    getNotifications.mockResolvedValue(listResponse([notif(1)], { total: 312, unread_total: 312 }));

    render(<AllNotifications />);

    // "Mark all read" above fifteen visible rows plainly means "these fifteen".
    expect(await screen.findByTestId('all-notifications-mark-all')).toHaveTextContent('Mark all 312 as read');
  });

  test('explains that live summaries are not stored here', async () => {
    getNotifications.mockResolvedValue(listResponse([notif(1)], { total: 1 }));
    render(<AllNotifications />);

    // Otherwise this is the screen on which the leave-approval you saw in the
    // bell appears to have been lost — on a page called Nothing Gets Lost.
    expect(await screen.findByText(/shown in the\s+bell, so they are not stored here/i)).toBeTruthy();
  });

  test('offers no way to delete a notification — the Owner said never', async () => {
    getNotifications.mockResolvedValue(listResponse([notif(1)], { total: 1 }));
    render(<AllNotifications />);
    await screen.findByTestId('notifications-datatable');

    expect(screen.queryByLabelText(/delete/i)).toBeNull();
    expect(screen.queryByText(/^delete$/i)).toBeNull();
  });

  test('remembers its page size under its own key, not the shared one', async () => {
    getNotifications.mockResolvedValue(listResponse([notif(1)], { total: 90 }));
    render(<AllNotifications />);
    await screen.findByTestId('notifications-datatable');

    fireEvent.change(screen.getByTestId('notifications-page-size'), { target: { value: '5' } });

    await waitFor(() => expect(window.localStorage.getItem('eduflow.table.notifications.pageSize')).toBe('5'));
    expect(window.localStorage.getItem('eduflow.table.students.pageSize')).toBeNull();
  });
});

// ── Story 6.5: the All Chats page ────────────────────────────────────────────

const chatList = (rows, total = rows.length) => ({
  success: true, data: rows, meta: { page: 1, limit: 15, total, sort: 'recent' },
});

describe('6.5 every chat is reachable and clearable', () => {
  test('opening a chat takes the reader back to it', async () => {
    getConversations.mockResolvedValue(chatList([conv(1)]));
    const opened = [];
    window.addEventListener('open-conversation', e => opened.push(e.detail));

    render(<AllChats />);
    fireEvent.click(await screen.findByTestId('chat-open-c-1'));

    expect(opened).toContain('c-1');
  });

  test('an unnamed chat reads "New conversation", not "not recorded"', async () => {
    getConversations.mockResolvedValue(chatList([conv(1, { title: '' })]));

    render(<AllChats />);

    expect(await screen.findByTestId('chat-open-c-1')).toHaveTextContent('New conversation');
    expect(screen.queryByText(/not recorded/i)).toBeNull();
  });

  test('search is sent to the server, which pages the whole history', async () => {
    getConversations.mockResolvedValue(chatList([conv(1)], 400));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');

    fireEvent.change(screen.getByTestId('chats-search'), { target: { value: 'fees' } });

    await waitFor(() => {
      const last = getConversations.mock.calls[getConversations.mock.calls.length - 1][0];
      expect(last).toMatchObject({ search: 'fees', page: 1 });
    });
  });

  test('an empty search result says WHICH field was searched', async () => {
    getConversations.mockResolvedValue(chatList([conv(1)], 1));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');

    getConversations.mockResolvedValue(chatList([], 0));
    fireEvent.change(screen.getByTestId('chats-search'), { target: { value: 'zzz' } });

    // The likeliest disappointment in this epic: someone searches for a word
    // they remember SAYING and concludes the chat is gone.
    const empty = await screen.findByTestId('all-chats-no-matches');
    expect(empty).toHaveTextContent(/searches chat names, not what was said inside them/i);
  });

  test('"no chats at all" is a different message from "nothing matched"', async () => {
    getConversations.mockResolvedValue(chatList([], 0));
    render(<AllChats />);

    await screen.findByTestId('all-chats-empty');
    expect(screen.queryByTestId('all-chats-no-matches')).toBeNull();
  });

  test('a load failure offers a retry and is announced', async () => {
    getConversations.mockResolvedValue({ success: false, detail: 'could not reach the server' });

    render(<AllChats />);

    const err = await screen.findByTestId('all-chats-error');
    expect(err).toHaveAttribute('role', 'alert');
    expect(screen.getByText('Try again')).toBeTruthy();
  });

  test('select-all covers the visible page only', async () => {
    // A select-all reaching across forty pages of search results would let one
    // tick and one typed number destroy an entire history.
    getConversations.mockResolvedValue(chatList([conv(1), conv(2)], 400));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');

    fireEvent.click(screen.getByTestId('chats-select-all'));

    expect(await screen.findByTestId('chats-bulk-delete')).toHaveTextContent('Delete 2 selected');
  });

  test('changing page clears the selection', async () => {
    getConversations.mockResolvedValue(chatList([conv(1), conv(2)], 400));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');
    fireEvent.click(screen.getByTestId('chats-select-all'));
    await screen.findByTestId('chats-bulk-delete');

    fireEvent.click(screen.getByTestId('chats-next'));

    await waitFor(() => expect(screen.queryByTestId('chats-bulk-delete')).toBeNull());
  });

  test('the confirmation states the count and stays disabled until it is typed', async () => {
    getConversations.mockResolvedValue(chatList([conv(1), conv(2), conv(3)], 3));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');
    fireEvent.click(screen.getByTestId('chats-select-all'));
    fireEvent.click(await screen.findByTestId('chats-bulk-delete'));

    const dialog = await screen.findByTestId('bulk-delete-dialog');
    expect(dialog).toHaveAttribute('role', 'alertdialog');
    // The heading interpolates the count, so it is several text nodes rather
    // than one — match on the assembled text.
    expect(within(dialog).getByRole('heading').textContent).toMatch(/Delete 3 chats\?/);
    expect(screen.getByTestId('bulk-delete-confirm')).toBeDisabled();

    fireEvent.change(screen.getByTestId('bulk-delete-confirm-input'), { target: { value: '2' } });
    expect(screen.getByTestId('bulk-delete-confirm')).toBeDisabled();

    fireEvent.change(screen.getByTestId('bulk-delete-confirm-input'), { target: { value: '3' } });
    expect(screen.getByTestId('bulk-delete-confirm')).not.toBeDisabled();
  });

  test('names pinned or starred chats caught in the selection', async () => {
    getConversations.mockResolvedValue(chatList([conv(1, { is_pinned: true }), conv(2)], 2));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');
    fireEvent.click(screen.getByTestId('chats-select-all'));
    fireEvent.click(await screen.findByTestId('chats-bulk-delete'));

    // Not protected — the Owner chose plain bulk delete — but silently
    // destroying something deliberately kept is the difference between a fast
    // tool and a trap.
    const dialog = await screen.findByTestId('bulk-delete-dialog');
    expect(dialog.textContent).toMatch(/1 of them is pinned or starred/i);
  });

  test('Escape closes the confirmation without deleting anything', async () => {
    getConversations.mockResolvedValue(chatList([conv(1)], 1));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');
    fireEvent.click(screen.getByTestId('chat-select-c-1'));
    fireEvent.click(await screen.findByTestId('chats-bulk-delete'));
    await screen.findByTestId('bulk-delete-dialog');

    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => expect(screen.queryByTestId('bulk-delete-dialog')).toBeNull());
    expect(bulkDeleteConversations).not.toHaveBeenCalled();
  });

  test('deleting tells the shell, so the sidebar and chat view do not go stale', async () => {
    getConversations.mockResolvedValue(chatList([conv(1)], 1));
    bulkDeleteConversations.mockResolvedValue({ success: true, data: { deleted: 1, not_found: 0 } });
    const events = [];
    window.addEventListener('conversations-changed', e => events.push(e.detail));

    render(<AllChats />);
    await screen.findByTestId('chats-datatable');
    fireEvent.click(screen.getByTestId('chat-select-c-1'));
    fireEvent.click(await screen.findByTestId('chats-bulk-delete'));
    fireEvent.change(screen.getByTestId('bulk-delete-confirm-input'), { target: { value: '1' } });
    fireEvent.click(screen.getByTestId('bulk-delete-confirm'));

    await waitFor(() => expect(events.length).toBeGreaterThan(0));
    expect(events[0].deletedIds).toEqual(['c-1']);
  });

  test('a partial delete is reported as partial, never as success', async () => {
    getConversations.mockResolvedValue(chatList([conv(1), conv(2)], 2));
    bulkDeleteConversations.mockResolvedValue({ success: true, data: { deleted: 1, not_found: 1 } });

    render(<AllChats />);
    await screen.findByTestId('chats-datatable');
    fireEvent.click(screen.getByTestId('chats-select-all'));
    fireEvent.click(await screen.findByTestId('chats-bulk-delete'));
    fireEvent.change(screen.getByTestId('bulk-delete-confirm-input'), { target: { value: '2' } });
    fireEvent.click(screen.getByTestId('bulk-delete-confirm'));

    expect(await screen.findByTestId('all-chats-notice')).toHaveTextContent('1 of 2 deleted');
  });

  test('pin and star reuse the endpoints that already exist', async () => {
    getConversations.mockResolvedValue(chatList([conv(1)], 1));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');

    fireEvent.click(screen.getByTestId('chat-pin-c-1'));
    await waitFor(() => expect(updateConversation).toHaveBeenCalledWith('c-1', { is_pinned: true }));

    fireEvent.click(screen.getByTestId('chat-star-c-1'));
    await waitFor(() => expect(updateConversation).toHaveBeenCalledWith('c-1', { is_starred: true }));
  });

  test('deleting ONE chat is confirmed exactly like deleting many', async () => {
    // The sidebar deletes a chat on one unguarded click. Copying that here —
    // beside a bulk action gated by a typed count — would mean the careful gate
    // is the one you get for many and the bare click is the one you get for the
    // chat you are actually looking at.
    getConversations.mockResolvedValue(chatList([conv(1)], 1));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');

    fireEvent.click(screen.getByTestId('chat-delete-c-1'));

    const dialog = await screen.findByTestId('bulk-delete-dialog');
    expect(within(dialog).getByRole('heading').textContent).toMatch(/Delete 1 chat\?/);
    expect(deleteConversation).not.toHaveBeenCalled();

    fireEvent.change(screen.getByTestId('bulk-delete-confirm-input'), { target: { value: '1' } });
    fireEvent.click(screen.getByTestId('bulk-delete-confirm'));

    await waitFor(() => expect(deleteConversation).toHaveBeenCalledWith('c-1'));
  });

  test('cancelling a single delete deletes nothing', async () => {
    getConversations.mockResolvedValue(chatList([conv(1)], 1));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');

    fireEvent.click(screen.getByTestId('chat-delete-c-1'));
    await screen.findByTestId('bulk-delete-dialog');
    fireEvent.click(screen.getByTestId('bulk-delete-cancel'));

    await waitFor(() => expect(screen.queryByTestId('bulk-delete-dialog')).toBeNull());
    expect(deleteConversation).not.toHaveBeenCalled();
  });

  test('emptying the last page steps back rather than saying "no chats yet"', async () => {
    // Deleting the last rows on page 2 of 2 leaves the reader on a page that no
    // longer exists — which renders as "No chats yet" while they still have 300.
    getConversations.mockResolvedValue(chatList([conv(1)], 16));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');

    fireEvent.click(screen.getByTestId('chats-next'));
    await waitFor(() => {
      const last = getConversations.mock.calls[getConversations.mock.calls.length - 1][0];
      expect(last.page).toBe(2);
    });
    await screen.findByTestId('chats-datatable');

    deleteConversation.mockResolvedValue({ success: true });
    fireEvent.click(screen.getByTestId('chat-delete-c-1'));
    await screen.findByTestId('bulk-delete-dialog');
    fireEvent.change(screen.getByTestId('bulk-delete-confirm-input'), { target: { value: '1' } });
    fireEvent.click(screen.getByTestId('bulk-delete-confirm'));

    await waitFor(() => {
      const last = getConversations.mock.calls[getConversations.mock.calls.length - 1][0];
      expect(last.page).toBe(1);
    });
  });

  test('a selection can never exceed what the server accepts', () => {
    // Selection is page-only, so the largest possible selection is the largest
    // page size. This is the test that notices if either number moves.
    expect(Math.max(...PAGE_SIZES)).toBeLessThanOrEqual(MAX_BULK_DELETE);
  });

  test('remembers its page size under its own key', async () => {
    getConversations.mockResolvedValue(chatList([conv(1)], 90));
    render(<AllChats />);
    await screen.findByTestId('chats-datatable');

    fireEvent.change(screen.getByTestId('chats-page-size'), { target: { value: '10' } });

    await waitFor(() => expect(window.localStorage.getItem('eduflow.table.chats.pageSize')).toBe('10'));
    expect(window.localStorage.getItem('eduflow.table.notifications.pageSize')).toBeNull();
  });
});
