/**
 * All Notifications — Epic 6, Story 6.3. Owner item 14, the "View all" half.
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
 *    table with a row count and a page indicator — an empty list would render as
 *    a notification telling you everything is fine.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCheck, ExternalLink, Inbox } from 'lucide-react';
import { useUser } from '../../contexts/UserContext';
import { getNotifications, markAllNotificationsRead, markNotificationRead } from '../../lib/api';
import { getToolForNotification, TOOL_LABELS } from '../../lib/notifRouting';
import NotificationDetailModal from '../NotificationDetailModal';
import DataTable from '../ui/DataTable';
import { Button, EmptyState, Pill } from '../ui/primitives';
import { useTablePageSize } from '../../hooks/useTablePrefs';

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
      const res = await getNotifications({
        page, limit: pageSize, sort,
        unread_only: unreadOnly ? 'true' : undefined,
        include_digest: 'false',
      });
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
      render: (n) => <Pill tone={TONE_BY_TYPE[n.type] || 'neutral'}>{n.type || 'info'}</Pill>,
    },
    {
      key: 'read', label: 'Status',
      // Status carries a word, never colour alone (WCAG color-not-only).
      render: (n) => <Pill tone={n.read ? 'neutral' : 'blue'}>{n.read ? 'Read' : 'Unread'}</Pill>,
    },
    {
      // The sortable heading FR82 requires. It is a real <button> inside its
      // <th> with aria-sort on the <th> — DataTable handles both — and the
      // SERVER re-orders the whole result set and hands back page 1. Ordering
      // only the rows already on screen would be a lie on 300 notifications.
      key: 'created_at', label: 'When', sortKey: 'created_at',
      render: (n) => formatWhen(n.created_at),
    },
    {
      key: 'go', label: '',
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
        padding: '7px 14px', minHeight: 36,
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
          lost — on a page called Nothing Gets Lost. */}
      <p style={{
        margin: '0 0 16px', maxWidth: 720,
        fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', lineHeight: 1.5,
      }}>
        This is everything the platform has saved for you. Live summaries — pending approvals,
        overdue fees, today's announcements — are worked out fresh each time and shown in the
        bell, so they are not stored here.
      </p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        {filterTab('All', !unreadOnly, () => changeFilter(false), 'notif-filter-all')}
        {filterTab('Unread', unreadOnly, () => changeFilter(true), 'notif-filter-unread')}
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
      ) : rows.length === 0 ? (
        // Three empty states, three different meanings (UX-DR6). "Nothing is
        // unread" is not "nothing ever arrived", and neither is "this failed".
        unreadOnly ? (
          <EmptyState
            kind="empty"
            icon={CheckCheck}
            data-testid="all-notifications-none-unread"
            title="Nothing unread"
            message="You have read everything. Switch to All to see them again — nothing is ever deleted."
            action={<Button variant="secondary" onClick={() => changeFilter(false)}>Show all</Button>}
          />
        ) : (
          <EmptyState
            kind="empty"
            icon={Inbox}
            data-testid="all-notifications-empty"
            title="No notifications yet"
            message="When the platform needs to tell you something — an approval, a payment, an incident — it will be saved here."
          />
        )
      ) : (
        <DataTable
          tableId="notifications"
          caption="Your saved notifications, newest first"
          columns={columns}
          rows={rows}
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
        />
      )}

      {detail && <NotificationDetailModal notification={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}
