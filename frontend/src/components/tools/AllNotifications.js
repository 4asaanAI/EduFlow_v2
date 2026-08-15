/**
 * All Notifications - Epic 6, Story 6.3. Owner item 14, the "View all" half.
 *
 * Until this page existed, the bell panel fetched page 1 and offered no way to
 * ask for page 2, and there was no notification screen anywhere in the product.
 * Notification twenty-one was unreachable by any route. `meta.total` was computed,
 * returned, and displayed nowhere.
 *
 * TWO THINGS HERE ARE DELIBERATE AND LOOK LIKE OMISSIONS:
 *
 * 1. There is NO delete control. The Owner decided on 2026-07-23 that clearing a
 *    notification means marking it read and nothing is ever destroyed. Read items
 *    stay reachable under the "All" filter. Do not add one.
 * 2. It requests `include_digest=false`. The endpoint synthesises digest rows on
 *    page 1 and, when there is nothing at all, a fabricated "All Good" row. That
 *    is a sensible empty state inside a dropdown and a made-up record inside a
 *    table with a row count and a page indicator - an empty list would render as
 *    a notification telling you everything is fine.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCheck, ExternalLink, Inbox } from 'lucide-react';
import { useUser } from '../../contexts/UserContext';
import { getNotifications, markAllNotificationsRead, markNotificationRead, NOTIFICATIONS_PAGE_MAX } from '../../lib/api';
import { getToolForNotification, TOOL_LABELS } from '../../lib/notifRouting';
import { KIND_TABS, splitByKind } from '../../lib/notifKinds';
import NotificationDetailModal from '../NotificationDetailModal';
import DataTable from '../ui/DataTable';
import { Button, EmptyState, Pill } from '../ui/primitives';
import { ALL_ROWS, useTablePageSize } from '../../hooks/useTablePrefs';
import { fetchAllRows } from '../../lib/fetchAllRows';
import { collectAllRows } from '../../lib/exportTable';

const TONE_BY_TYPE = { info: 'blue', warning: 'yellow', success: 'green', error: 'red' };

function formatWhen(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export default function AllNotifications() {
  const { currentUser } = useUser();
  const [rows, setRows] = useState([]);
  // R3-2, 2026-08-15 (Abhimanyu): the same split as the bell, from the same rule in
  // `notifKinds.js`, so the two surfaces cannot tell a person different things. 'all'
  // stays the default here because this screen is the record of everything, unlike the
  // bell which is a place to act.
  // Opens on whichever half has something in it: a person blocked on a decision is the
  // reason this screen is worth opening, and landing on an empty tab with the rows
  // behind the other one is the same fault the bell's empty state had.
  const [kind, setKind] = useState('approvals');
  const [total, setTotal] = useState(0);
  const [unreadTotal, setUnreadTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState('newest');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [markingAll, setMarkingAll] = useState(false);
  const [detail, setDetail] = useState(null);

  // Its own key. Sizing this list must not resize the student list (UX-DR10).
  const [pageSize, setPageSize] = useTablePageSize('notifications');

  // Changing size, order or filter while on page 12 would strand the reader on a
  // page that no longer exists.
  const changePageSize = useCallback((n) => { setPageSize(n); setPage(1); }, [setPageSize]);
  const changeSort = useCallback(() => {
    setSort(s => (s === 'newest' ? 'oldest' : 'newest'));
    setPage(1);
  }, []);
  const changeFilter = useCallback((only) => { setUnreadOnly(only); setPage(1); }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const query = {
        sort,
        unread_only: unreadOnly ? 'true' : undefined,
        include_digest: 'false',
      };
      // "All" is a sentinel (-1), never a limit to send: this server clamps with
      // min(max(limit,1),50) and would answer with a SINGLE notification. Note the
      // page width here is 50, not 500 - this route's cap is the tightest we have.
      if (pageSize === ALL_ROWS) {
        const all = await fetchAllRows(
          ({ page: cursor, limit }) => getNotifications({ ...query, page: cursor, limit }),
          { pageMax: NOTIFICATIONS_PAGE_MAX },
        );
        if (all.success) {
          setRows(all.data);
          setTotal(all.total);
          // Every row is in hand, so the unread count is counted rather than taken
          // from a page's `meta`. Leaving the previous page's figure standing here
          // is how a badge starts disagreeing with the list beneath it.
          setUnreadTotal(all.data.filter((n) => !n.read).length);
        } else {
          setError(all.detail || 'We could not load your notifications.');
        }
        setLoading(false);
        return;
      }
      const res = await getNotifications({ ...query, page, limit: pageSize });
      if (res.success) {
        setRows(res.data || []);
        setTotal(res.meta?.total ?? 0);
        setUnreadTotal(res.meta?.unread_total ?? 0);
      } else {
        setError(res.detail || 'We could not load your notifications.');
      }
    } catch (err) {
      setError(err.message || 'We could not load your notifications.');
    }
    setLoading(false);
  }, [page, pageSize, sort, unreadOnly]);

  const exportRows = useCallback(
    () => collectAllRows(
      ({ page: cursor, limit }) => getNotifications({
        sort, unread_only: unreadOnly ? 'true' : 'false', include_digest: 'false',
        page: cursor, limit,
      }),
      { pageMax: NOTIFICATIONS_PAGE_MAX, what: 'notifications' },
    ),
    [sort, unreadOnly],
  );

  useEffect(() => { load(); }, [load]);

  const openNotification = useCallback(async (n) => {
    if (n.id && !n.read) {
      setRows(prev => prev.map(r => (r.id === n.id ? { ...r, read: true } : r)));
      setUnreadTotal(c => Math.max(0, c - 1));
      markNotificationRead(n.id).catch(() => {});
    }
    const toolId = getToolForNotification(n, currentUser.role);
    if (toolId) window.dispatchEvent(new CustomEvent('open-tool', { detail: toolId }));
    else setDetail(n);
  }, [currentUser.role]);

  const handleMarkAllRead = async () => {
    if (markingAll) return;
    setMarkingAll(true);
    try { await markAllNotificationsRead(); } catch {}
    setMarkingAll(false);
    load();
  };

  const columns = useMemo(() => [
    {
      key: 'title', label: 'Notification',
      // The screen shows the heading and the message together. A file that held only
      // the heading would lose the part someone actually needs to read back.
      exportValue: (n) => [n.title, n.message].filter(Boolean).join(' - '),
      render: (n) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, maxWidth: 460 }}>
          {!n.read && (
            <span
              aria-hidden="true"
              style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--color-accent-blue)', flexShrink: 0 }}
            />
          )}
          <div style={{ minWidth: 0 }}>
            {/* The real focusable way in. A row click is only a shortcut, and a
                keyboard user must never depend on it. */}
            <button
              data-testid={`notif-open-${n.id}`}
              onClick={e => { e.stopPropagation(); openNotification(n); }}
              style={{
                background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left',
                fontFamily: 'var(--font-display)', fontSize: 'var(--text-base)',
                fontWeight: n.read ? 500 : 700, color: 'var(--color-text-primary)',
              }}
            >
              {n.title}
            </button>
            <div style={{
              fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', marginTop: 2,
              whiteSpace: 'normal', lineHeight: 1.4,
            }}>
              {n.message}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: 'type', label: 'Kind',
      exportValue: (n) => n.type || 'info',
      render: (n) => <Pill tone={TONE_BY_TYPE[n.type] || 'neutral'}>{n.type || 'info'}</Pill>,
    },
    {
      key: 'read', label: 'Status',
      exportValue: (n) => (n.read ? 'Read' : 'Unread'),
      // Status carries a word, never colour alone (WCAG color-not-only).
      render: (n) => <Pill tone={n.read ? 'neutral' : 'blue'}>{n.read ? 'Read' : 'Unread'}</Pill>,
    },
    {
      // The sortable heading FR82 requires. It is a real <button> inside its
      // <th> with aria-sort on the <th> - DataTable handles both - and the
      // SERVER re-orders the whole result set and hands back page 1. Ordering
      // only the rows already on screen would be a lie on 300 notifications.
      key: 'created_at', label: 'When', sortKey: 'created_at',
      exportValue: (n) => n.created_at,
      render: (n) => formatWhen(n.created_at),
    },
    {
      key: 'go', label: '',
      // A button, not data.
      exportSkip: true,
      render: (n) => {
        const toolId = getToolForNotification(n, currentUser.role);
        return (
          <Button
            size="sm"
            variant="ghost"
            icon={ExternalLink}
            data-testid={`notif-go-${n.id}`}
            onClick={e => { e.stopPropagation(); openNotification(n); }}
          >
            {toolId ? (TOOL_LABELS[toolId] || 'Open') : 'Details'}
          </Button>
        );
      },
    },
  ], [currentUser.role, openNotification]);

  const filterTab = (label, active, onClick, testId) => (
    <button
      key={label}
      type="button"
      data-testid={testId}
      aria-pressed={active}
      onClick={onClick}
      style={{
        padding: '7px 14px', minHeight: 40,
        background: active ? 'var(--color-surface-raised)' : 'transparent',
        border: `1px solid ${active ? 'var(--color-accent-blue)' : 'var(--color-border)'}`,
        borderRadius: 'var(--radius-full)',
        color: active ? 'var(--color-accent-blue)' : 'var(--color-text-secondary)',
        fontFamily: 'var(--font-display)', fontSize: 'var(--text-sm)', fontWeight: 700,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );

  // R3-2: the split, from the one shared rule. The counts on the two tabs are of the rows
  // ACTUALLY LOADED, which is what a person can see; the page total above is separate and
  // stays the honest school-wide figure. Two numbers meaning two different things, each
  // labelled, rather than one number quietly meaning whichever is convenient.
  const { approvals, ordinary } = splitByKind(rows);
  // Falls back to the other half when this one is empty, exactly as the bell does. A
  // screen that opens on "Waiting on you (0)" with every row sitting behind the second
  // tab is the same fault as telling somebody they are all caught up over an empty tab.
  const activeKind = approvals.length === 0 ? 'ordinary' : kind;
  const shownRows = activeKind === 'approvals' ? approvals : ordinary;

  return (
    <div
      data-testid="all-notifications-tool"
      style={{ padding: 24, overflowY: 'auto', height: '100%', boxSizing: 'border-box' }}
    >
      <div style={{
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
        gap: 12, marginBottom: 6, flexWrap: 'wrap',
      }}>
        <div>
          <h1 style={{
            fontSize: 22, fontWeight: 700, margin: 0,
            fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)',
          }}>
            All Notifications
          </h1>
          <div
            aria-live="polite"
            data-testid="all-notifications-count"
            style={{ color: 'var(--color-text-muted)', fontSize: 12, marginTop: 3 }}
          >
            {total.toLocaleString('en-IN')} stored · {unreadTotal.toLocaleString('en-IN')} unread
          </div>
        </div>
        {unreadTotal > 0 && (
          <Button
            variant="secondary"
            icon={CheckCheck}
            data-testid="all-notifications-mark-all"
            disabled={markingAll}
            onClick={handleMarkAllRead}
          >
            {/* The scope, with the real number. "Mark all read" sitting above
                fifteen visible rows plainly means "these fifteen" to everyone who
                has not read the source. */}
            {markingAll ? 'Marking…' : `Mark all ${unreadTotal.toLocaleString('en-IN')} as read`}
          </Button>
        )}
      </div>

      {/* The bell shows two kinds of thing and this page shows one of them, so it
          will legitimately hold FEWER items than the panel the reader just came
          from. Unsaid, this is the screen on which something appears to have been
          lost - on a page called Nothing Gets Lost. */}
      <p style={{
        margin: '0 0 16px', maxWidth: 720,
        fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', lineHeight: 1.5,
      }}>
        This is everything the platform has saved for you. Live summaries - pending approvals,
        overdue fees, today's announcements - are worked out fresh each time and shown in the
        bell, so they are not stored here.
      </p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        {filterTab('All', !unreadOnly, () => changeFilter(false), 'notif-filter-all')}
        {filterTab('Unread', unreadOnly, () => changeFilter(true), 'notif-filter-unread')}
        <span style={{ width: 1, height: 22, background: 'var(--color-border)', margin: '0 4px' }} />
        {/* Abhimanyu, 2026-08-15: exactly TWO sub-tabs, here and in the bell, with the
            same names in both. There used to be three here and two there, labelled
            differently, so one inbox read as two different things depending on where a
            person stood. The names come from `notifKinds.js` so they cannot drift again.

            The old "Both" tab is gone and NOTHING is dropped with it: the two halves are
            exhaustive, so every row is still reachable, under exactly one of them. */}
        {KIND_TABS.map(({ id, label }) => filterTab(
          `${label} (${id === 'approvals' ? approvals.length : ordinary.length})`,
          activeKind === id,
          () => setKind(id),
          `notif-kind-${id}`,
        ))}
        <Button
          size="sm"
          variant="ghost"
          data-testid="notif-sort-toggle"
          onClick={changeSort}
        >
          {sort === 'newest' ? 'Newest first' : 'Oldest first'}
        </Button>
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13 }}>
          Loading notifications…
        </div>
      ) : error ? (
        <EmptyState
          kind="error"
          data-testid="all-notifications-error"
          message={error}
          action={<Button variant="secondary" onClick={load}>Try again</Button>}
        />
      ) : shownRows.length === 0 ? (
        // Three empty states, three different meanings (UX-DR6). "Nothing is
        // unread" is not "nothing ever arrived", and neither is "this failed".
        unreadOnly ? (
          <EmptyState
            kind="empty"
            icon={CheckCheck}
            data-testid="all-notifications-none-unread"
            title="Nothing unread"
            message="You have read everything. Switch to All to see them again - nothing is ever deleted."
            action={<Button variant="secondary" onClick={() => changeFilter(false)}>Show all</Button>}
          />
        ) : (
          <EmptyState
            kind="empty"
            icon={Inbox}
            data-testid="all-notifications-empty"
            title="No notifications yet"
            message="When the platform needs to tell you something - an approval, a payment, an incident - it will be saved here."
          />
        )
      ) : (
        <DataTable
          tableId="notifications"
          caption="Your saved notifications, newest first"
          columns={columns}
          rows={shownRows}
          rowKey={(n) => n.id}
          onRowClick={openNotification}
          sort="created_at"
          sortDirection={sort === 'newest' ? 'descending' : 'ascending'}
          onSortChange={changeSort}
          page={page}
          total={total}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={changePageSize}
          exportTable={{ title: 'Notifications', getRows: exportRows }}
        />
      )}

      {detail && <NotificationDetailModal notification={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}
