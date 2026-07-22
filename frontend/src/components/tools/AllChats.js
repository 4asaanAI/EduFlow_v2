/**
 * All Chats — Epic 6, Story 6.5. Owner item 16.
 *
 * The sidebar showed whatever the server returned, and the server returned the
 * newest fifty with no way to ask for more. The fifty-first-oldest conversation
 * was unreachable by any route in the product — not by scrolling, not by
 * searching, not by URL. For someone who uses the assistant daily that is a few
 * weeks of history quietly falling off the end.
 *
 * THREE DELIBERATE DECISIONS THAT LOOK LIKE OMISSIONS:
 *
 * 1. You see only YOUR OWN chats. Put to the Owner on 2026-07-23 and refused:
 *    reading staff conversations would be a new power over people, needing its
 *    own permissions, its own audit trail, and a decision about telling them.
 *    The owner-only Conversation Trace tool already covers support.
 * 2. Selection covers the VISIBLE PAGE ONLY. A "select all" that reached across
 *    forty pages of search results would let one tick and one typed number
 *    destroy an entire history. Clearing 300 chats costs ten rounds, which is
 *    the right price for something that cannot be undone.
 * 3. Search matches chat NAMES, not message text — and the empty state says so.
 *    Searching message bodies would need a text index over every message in the
 *    school and turn this into full-text search across children's data.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { MessageCircle, Pin, Search, Star, Trash2 } from 'lucide-react';
import {
  bulkDeleteConversations,
  deleteConversation,
  getConversations,
  updateConversation,
} from '../../lib/api';
import DataTable from '../ui/DataTable';
import { Button, EmptyState, Pill, inputStyle } from '../ui/primitives';
import { useTablePageSize } from '../../hooks/useTablePrefs';

/**
 * Mirrors CONVERSATION_BULK_DELETE_MAX in backend/models/schemas.py.
 *
 * The reader can never assemble a selection the server would refuse, because
 * selection covers the visible page only and the largest page size on offer is
 * 30 (PAGE_SIZES in useTablePrefs). This is asserted in the tests rather than
 * enforced again here — a second guard that can never fire is a guard nobody
 * maintains. If either number ever moves, that test is what notices.
 */
export const MAX_BULK_DELETE = 100;

const SORTS = [
  { value: 'recent', label: 'Most recent' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'title', label: 'By name' },
];

/**
 * What a chat is called on screen.
 *
 * "New conversation", exactly as the sidebar renders it — NOT "not recorded",
 * which would imply a field somebody failed to fill in rather than a chat that
 * never got a name. `.trim()` because a title of one space is not a title.
 */
const chatName = (conv) => (conv.title || '').trim() || 'New conversation';

function formatWhen(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

/**
 * The gate in front of an irreversible action.
 *
 * The Owner asked for a typed confirmation. It takes the COUNT rather than the
 * English word DELETE: the people running this school work in English and Hindi,
 * and a gate that is really a spelling test adds friction without adding safety —
 * whereas typing the number forces the one thing the gate exists for, which is
 * looking at how many you are about to destroy.
 */
function ConfirmBulkDelete({ count, keptCount, onCancel, onConfirm, busy }) {
  const [typed, setTyped] = useState('');
  const inputRef = useRef(null);
  const headingId = 'bulk-delete-heading';

  useEffect(() => {
    // Remember where focus came from and put it back on the way out. A dialog
    // announced as an alertdialog that dumps a keyboard user at the top of the
    // document is worse than one that is not announced at all.
    const opener = document.activeElement;
    inputRef.current?.focus();
    return () => { if (opener && opener.focus) opener.focus(); };
  }, []);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onCancel(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onCancel]);

  const armed = typed.trim() === String(count) && !busy;

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 210, padding: 16,
        background: 'rgba(0,0,0,0.72)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={headingId}
        data-testid="bulk-delete-dialog"
        style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-xl)', padding: 22, width: 480, maxWidth: '100%',
        }}
      >
        <h3
          id={headingId}
          style={{
            margin: '0 0 8px', fontFamily: 'var(--font-display)', fontSize: 'var(--text-lg)',
            fontWeight: 700, color: 'var(--color-text-primary)',
          }}
        >
          Delete {count} chat{count === 1 ? '' : 's'}?
        </h3>
        <p style={{
          margin: '0 0 12px', fontSize: 'var(--text-sm)',
          color: 'var(--color-text-secondary)', lineHeight: 1.55,
        }}>
          This removes {count === 1 ? 'it' : 'them'} and every message inside, for good.
          There is no undo.
          {keptCount > 0 && (
            <>
              {' '}
              <strong style={{ color: 'var(--color-warning)' }}>
                {keptCount} of {count === 1 ? 'these' : 'them'} {keptCount === 1 ? 'is' : 'are'} pinned or starred
              </strong>
              {' '}— chats you chose to keep.
            </>
          )}
        </p>
        <label
          htmlFor="bulk-delete-confirm"
          style={{
            display: 'block', marginBottom: 5,
            fontFamily: 'var(--font-display)', fontSize: 'var(--text-sm)', fontWeight: 600,
            color: 'var(--color-text-secondary)',
          }}
        >
          Type <strong style={{ color: 'var(--color-text-primary)' }}>{count}</strong> to confirm
        </label>
        <input
          id="bulk-delete-confirm"
          ref={inputRef}
          data-testid="bulk-delete-confirm-input"
          value={typed}
          inputMode="numeric"
          onChange={e => setTyped(e.target.value)}
          style={{ ...inputStyle, width: '100%', boxSizing: 'border-box' }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
          <Button variant="secondary" data-testid="bulk-delete-cancel" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="danger"
            icon={Trash2}
            data-testid="bulk-delete-confirm"
            disabled={!armed}
            onClick={onConfirm}
          >
            {busy ? 'Deleting…' : `Delete ${count}`}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function AllChats() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState('recent');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(() => new Set());
  const [confirming, setConfirming] = useState(false);
  // When set, the confirmation is standing in front of ONE chat rather than the
  // current selection. Same dialog, same typed gate — see handleSingleDelete.
  const [singleTarget, setSingleTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [notice, setNotice] = useState('');

  const [pageSize, setPageSize] = useTablePageSize('chats');

  // Anything that changes WHICH rows are on screen clears the selection —
  // otherwise a tick made on page 1 would be carried into a confirmation whose
  // count the reader is reading off page 4.
  const resetSelection = useCallback(() => setSelected(new Set()), []);

  const changePage = useCallback((n) => { setPage(n); resetSelection(); }, [resetSelection]);
  const changePageSize = useCallback((n) => { setPageSize(n); setPage(1); resetSelection(); }, [setPageSize, resetSelection]);
  const changeSort = useCallback((next) => { setSort(next); setPage(1); resetSelection(); }, [resetSelection]);

  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput.trim()); setPage(1); resetSelection(); }, 300);
    return () => clearTimeout(t);
  }, [searchInput, resetSelection]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getConversations({ page, limit: pageSize, sort, search });
      if (res.success) {
        setRows(res.data || []);
        setTotal(res.meta?.total ?? 0);
      } else {
        setError(res.detail || 'We could not load your chats.');
      }
    } catch (err) {
      setError(err.message || 'We could not load your chats.');
    }
    setLoading(false);
  }, [page, pageSize, sort, search]);

  useEffect(() => { load(); }, [load]);

  const openChat = useCallback((conv) => {
    // Layout listens for this and clears the active tool. Landing back in the
    // chat is the point of the page — a row that highlights and goes nowhere
    // would fail FR81.
    window.dispatchEvent(new CustomEvent('open-conversation', { detail: conv.id }));
  }, []);

  const afterMutation = useCallback((deletedIds = []) => {
    // The sidebar is on screen at the same time and would keep offering rows
    // that no longer exist; and the chat view must not stay pointing at a
    // conversation that has just been destroyed.
    window.dispatchEvent(new CustomEvent('conversations-changed', {
      detail: { deletedIds },
    }));
  }, []);

  const toggleOne = useCallback((id) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const visibleIds = useMemo(() => rows.map(r => r.id), [rows]);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every(id => selected.has(id));

  const toggleAllVisible = useCallback(() => {
    setSelected(prev => (
      visibleIds.length > 0 && visibleIds.every(id => prev.has(id))
        ? new Set()
        : new Set(visibleIds)
    ));
  }, [visibleIds]);

  const selectedRows = useMemo(() => rows.filter(r => selected.has(r.id)), [rows, selected]);
  const keptCount = useMemo(
    () => selectedRows.filter(r => r.is_pinned || r.is_starred).length,
    [selectedRows],
  );

  /**
   * Deleting the last rows on the last page leaves the reader on a page that no
   * longer exists — which renders as "No chats yet" while they still have three
   * hundred. Step back rather than show them an empty page and a wrong message.
   */
  const stepBackIfPageEmptied = useCallback((removedCount) => {
    if (page > 1 && removedCount >= rows.length) setPage(p => Math.max(1, p - 1));
  }, [page, rows.length]);

  const handleBulkDelete = async () => {
    const ids = selectedRows.map(r => r.id);
    setDeleting(true);
    let res;
    try {
      res = await bulkDeleteConversations(ids);
    } catch (err) {
      setDeleting(false);
      setConfirming(false);
      setError(err.message || 'We could not delete those chats.');
      return;
    }
    setDeleting(false);
    setConfirming(false);
    resetSelection();
    if (res?.success) {
      const removed = res.data?.deleted ?? 0;
      // If the server removed fewer than were asked for, say so. Reporting a
      // partial result as success is the defect this epic exists to remove.
      setNotice(
        removed === ids.length
          ? `${removed} chat${removed === 1 ? '' : 's'} deleted.`
          : `${removed} of ${ids.length} deleted — the rest were already gone.`,
      );
      afterMutation(ids);
      stepBackIfPageEmptied(removed);
      load();
    } else {
      setError(res?.detail || 'We could not delete those chats.');
    }
  };

  /**
   * Single delete goes through the SAME confirmation as bulk.
   *
   * The sidebar deletes a chat on one click with no confirmation at all. Copying
   * that here — beside a bulk action guarded by a typed count — would mean the
   * careful gate is the one you get for many and the unguarded click is the one
   * you get for the chat you are looking at.
   */
  const handleSingleDelete = async (conv) => {
    setDeleting(true);
    let res;
    try {
      res = await deleteConversation(conv.id);
    } catch (err) {
      setDeleting(false);
      setConfirming(false);
      setError(err.message || 'We could not delete that chat.');
      return;
    }
    setDeleting(false);
    setConfirming(false);
    setSingleTarget(null);
    resetSelection();
    if (res?.success) {
      setNotice('Chat deleted.');
      afterMutation([conv.id]);
      stepBackIfPageEmptied(1);
      load();
    } else {
      setError(res?.detail || 'We could not delete that chat.');
    }
  };

  const handleToggleFlag = async (conv, field) => {
    await updateConversation(conv.id, { [field]: !conv[field] });
    afterMutation();
    load();
  };

  const columns = useMemo(() => [
    {
      key: 'select',
      label: (
        <input
          type="checkbox"
          data-testid="chats-select-all"
          aria-label="Select every chat on this page"
          checked={allVisibleSelected}
          onChange={toggleAllVisible}
          style={{ cursor: 'pointer', width: 16, height: 16 }}
        />
      ),
      render: (conv) => (
        <input
          type="checkbox"
          data-testid={`chat-select-${conv.id}`}
          aria-label={`Select ${chatName(conv)}`}
          checked={selected.has(conv.id)}
          onClick={e => e.stopPropagation()}
          onChange={() => toggleOne(conv.id)}
          style={{ cursor: 'pointer', width: 16, height: 16 }}
        />
      ),
    },
    {
      key: 'title', label: 'Chat', sortKey: 'title',
      render: (conv) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <MessageCircle size={14} aria-hidden="true" style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
          <button
            data-testid={`chat-open-${conv.id}`}
            onClick={e => { e.stopPropagation(); openChat(conv); }}
            style={{
              background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left',
              fontFamily: 'var(--font-display)', fontSize: 'var(--text-base)', fontWeight: 700,
              color: 'var(--color-text-primary)',
            }}
          >
            {chatName(conv)}
          </button>
          {conv.is_pinned && <Pill tone="yellow" icon={Pin}>Pinned</Pill>}
          {conv.is_starred && <Pill tone="yellow" icon={Star}>Starred</Pill>}
        </div>
      ),
    },
    { key: 'updated_at', label: 'Last used', sortKey: 'recent', render: (conv) => formatWhen(conv.updated_at) },
    {
      key: 'actions', label: 'Actions',
      render: (conv) => (
        <div style={{ display: 'flex', gap: 5 }} onClick={e => e.stopPropagation()}>
          <Button
            size="sm" variant="ghost" icon={Pin}
            data-testid={`chat-pin-${conv.id}`}
            aria-label={conv.is_pinned ? 'Unpin this chat' : 'Pin this chat'}
            onClick={() => handleToggleFlag(conv, 'is_pinned')}
          />
          <Button
            size="sm" variant="ghost" icon={Star}
            data-testid={`chat-star-${conv.id}`}
            aria-label={conv.is_starred ? 'Unstar this chat' : 'Star this chat'}
            onClick={() => handleToggleFlag(conv, 'is_starred')}
          />
          <Button
            size="sm" variant="ghost" icon={Trash2}
            data-testid={`chat-delete-${conv.id}`}
            aria-label={`Delete ${chatName(conv)}`}
            onClick={() => { setSingleTarget(conv); setConfirming(true); }}
          />
        </div>
      ),
    },
  ], [allVisibleSelected, selected, toggleAllVisible, toggleOne, openChat]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectedCount = selectedRows.length;

  return (
    <div
      data-testid="all-chats-tool"
      style={{ padding: 24, overflowY: 'auto', height: '100%', boxSizing: 'border-box' }}
    >
      <div style={{ marginBottom: 16 }}>
        <h1 style={{
          fontSize: 22, fontWeight: 700, margin: 0,
          fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)',
        }}>
          All Chats
        </h1>
        <div
          aria-live="polite"
          data-testid="all-chats-count"
          style={{ color: 'var(--color-text-muted)', fontSize: 12, marginTop: 3 }}
        >
          {total.toLocaleString('en-IN')} conversation{total === 1 ? '' : 's'}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: '1 1 240px', maxWidth: 340 }}>
          <Search
            size={14} aria-hidden="true"
            style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)' }}
          />
          <input
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            data-testid="chats-search"
            aria-label="Search your chats by name"
            placeholder="Search chat names"
            style={{ ...inputStyle, width: '100%', paddingLeft: 34, boxSizing: 'border-box' }}
          />
        </div>
        <select
          value={sort}
          onChange={e => changeSort(e.target.value)}
          data-testid="chats-sort"
          aria-label="Sort chats by"
          style={{ ...inputStyle, width: 160 }}
        >
          {SORTS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>

        {selectedCount > 0 && (
          <Button
            variant="danger"
            icon={Trash2}
            data-testid="chats-bulk-delete"
            onClick={() => setConfirming(true)}
          >
            Delete {selectedCount} selected
          </Button>
        )}
      </div>

      {notice && (
        <div
          role="status"
          data-testid="all-chats-notice"
          style={{
            marginBottom: 12, padding: '9px 12px', borderRadius: 'var(--radius-md)',
            background: 'var(--color-surface-raised)', border: '1px solid var(--color-border)',
            fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)',
          }}
        >
          {notice}
        </div>
      )}

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13 }}>
          Loading chats…
        </div>
      ) : error ? (
        <EmptyState
          kind="error"
          data-testid="all-chats-error"
          message={error}
          action={<Button variant="secondary" onClick={load}>Try again</Button>}
        />
      ) : rows.length === 0 ? (
        // Three empty states. "Nothing matched your search" is the common one and
        // the one a bare "nothing here" would make look like data loss — on a page
        // whose whole promise is that nothing gets lost.
        search ? (
          <EmptyState
            kind="empty"
            icon={Search}
            data-testid="all-chats-no-matches"
            title={`No chat named like "${search}"`}
            message="This searches chat names, not what was said inside them — so a word you remember typing to Flo will not find it here. Try the name the chat was given, or clear the search."
            action={<Button variant="secondary" onClick={() => setSearchInput('')}>Clear search</Button>}
          />
        ) : (
          <EmptyState
            kind="empty"
            icon={MessageCircle}
            data-testid="all-chats-empty"
            title="No chats yet"
            message="Every conversation you have with Flo is kept here, however old."
          />
        )
      ) : (
        <DataTable
          tableId="chats"
          caption="Your conversations with Flo"
          columns={columns}
          rows={rows}
          rowKey={(c) => c.id}
          sort={sort === 'title' ? 'title' : 'recent'}
          sortDirection={sort === 'oldest' ? 'ascending' : 'descending'}
          // Clicking "Last used" from a title sort lands on most-recent first,
          // not on oldest — arriving at a column should show you its obvious
          // order, and only a second click reverses it.
          onSortChange={(key) => changeSort(
            key === 'title' ? 'title' : (sort === 'recent' ? 'oldest' : 'recent'),
          )}
          page={page}
          total={total}
          pageSize={pageSize}
          onPageChange={changePage}
          onPageSizeChange={changePageSize}
        />
      )}

      {confirming && (
        <ConfirmBulkDelete
          count={singleTarget ? 1 : selectedCount}
          keptCount={singleTarget ? ((singleTarget.is_pinned || singleTarget.is_starred) ? 1 : 0) : keptCount}
          busy={deleting}
          onCancel={() => { setConfirming(false); setSingleTarget(null); }}
          onConfirm={() => (singleTarget ? handleSingleDelete(singleTarget) : handleBulkDelete())}
        />
      )}
    </div>
  );
}
