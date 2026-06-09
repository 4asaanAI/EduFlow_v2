/**
 * Story 33: Audit Log UI — Owner/Principal view of all system changes
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useUser } from '../../contexts/UserContext';
import { useTheme } from '../../contexts/ThemeContext';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, ActionBtn } from './ToolPage';
import { ChevronDown, ChevronRight, Search, Filter } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function h() { return getAuthHeaders(); }
const tint = (color, amount) => `color-mix(in srgb, ${color} ${amount}%, transparent)`;

const ACTION_COLORS = {
  create: 'var(--tool-hex-34d399)',
  update: 'var(--tool-hex-facc15)',
  delete: 'var(--tool-hex-f87171)',
  correct: 'var(--tool-hex-818cf8)',
  submit: 'var(--tool-hex-60a5fa)',
  approve: 'var(--tool-hex-34d399)',
  reject: 'var(--tool-hex-f87171)',
};

function getActionColor(action = '') {
  const key = Object.keys(ACTION_COLORS).find(k => action.includes(k));
  return ACTION_COLORS[key] || 'var(--tool-hex-888)';
}

function AuditRow({ entry, isDark }) {
  const [expanded, setExpanded] = useState(false);
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-888)' : 'var(--tool-hex-737373)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const card = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-fff)';
  const actionColor = getActionColor(entry.action);

  const hasDiff = entry.changes && (entry.changes.previous || entry.changes.new || Object.keys(entry.changes).length > 0);

  return (
    <div style={{ borderBottom: `1px solid ${border}` }}>
      <div
        onClick={() => hasDiff && setExpanded(p => !p)}
        style={{
          display: 'flex', alignItems: 'center', padding: '10px 0',
          cursor: hasDiff ? 'pointer' : 'default', gap: 10,
        }}
      >
        <span style={{ width: 20, color: muted, flexShrink: 0 }}>
          {hasDiff ? (expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : null}
        </span>
        <span style={{ width: 140, flexShrink: 0, fontSize: 11, color: muted }}>{entry.created_at?.slice(0, 16).replace('T', ' ')}</span>
        <span style={{
          minWidth: 90, flexShrink: 0, padding: '2px 8px', borderRadius: 5, fontSize: 11, fontWeight: 600,
          background: tint(actionColor, 10), color: actionColor, textAlign: 'center',
        }}>
          {entry.action?.replace(/_/g, ' ').slice(0, 18)}
        </span>
        <span style={{ flex: 1, fontSize: 12, color: text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {entry.collection || entry.entity_type || '—'} · {entry.entity_id?.slice(0, 8) || '—'}
        </span>
        <span style={{ fontSize: 11, color: muted, minWidth: 100, textAlign: 'right' }}>
          {entry.changed_by_name || entry.changed_by?.slice(0, 8) || '—'}
          {entry.changed_by_role && <span style={{ marginLeft: 4, opacity: 0.6 }}>({entry.changed_by_role})</span>}
        </span>
      </div>

      {expanded && hasDiff && (
        <div style={{ marginLeft: 30, marginBottom: 10, background: isDark ? 'var(--tool-hex-161616)' : 'var(--tool-hex-f9f9f9)', borderRadius: 8, padding: 12, fontSize: 11 }}>
          {entry.changes.previous !== undefined && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ color: 'var(--tool-hex-f87171)', fontWeight: 600 }}>Before: </span>
              <code style={{ color: muted }}>{JSON.stringify(entry.changes.previous, null, 2)}</code>
            </div>
          )}
          {entry.changes.new !== undefined && (
            <div>
              <span style={{ color: 'var(--tool-hex-34d399)', fontWeight: 600 }}>After: </span>
              <code style={{ color: muted }}>{JSON.stringify(entry.changes.new, null, 2)}</code>
            </div>
          )}
          {entry.changes.previous === undefined && entry.changes.new === undefined && (
            <pre style={{ color: muted, margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(entry.changes, null, 2)}</pre>
          )}
          {entry.reason && <div style={{ marginTop: 6, color: muted }}>Reason: {entry.reason}</div>}
        </div>
      )}
    </div>
  );
}

export default function AuditLog() {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({ collection: '', changed_by: '', date_from: '', date_to: '', q: '' });
  const [showFilters, setShowFilters] = useState(false);

  const LIMIT = 50;
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-888)' : 'var(--tool-hex-737373)';
  const card = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-fff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';

  const load = useCallback(async (pg = 1) => {
    setLoading(true);
    setError('');
    const params = new URLSearchParams({ page: pg, limit: LIMIT });
    Object.entries(filters).forEach(([k, v]) => { if (v) params.append(k, v); });
    try {
      const res = await fetch(`${API}/audit-log?${params}`, { headers: h() });
      const data = await res.json();
      if (data.success) {
        setEntries(data.data || []);
        setTotal(data.meta?.total || 0);
        setPage(pg);
      } else {
        setError(data.detail || 'Failed to load audit log');
      }
    } catch { setError('Network error'); }
    setLoading(false);
  }, [filters]);

  useEffect(() => { load(1); }, [load]);

  const f = k => v => setFilters(p => ({ ...p, [k]: v }));
  const totalPages = Math.ceil(total / LIMIT);

  return (
    <ToolPage
      title="Audit Log"
      subtitle={`${total.toLocaleString()} entries`}
      onRefresh={() => load(page)}
      loading={loading}
      actions={
        <button
          onClick={() => setShowFilters(p => !p)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px',
            background: showFilters ? 'var(--tool-hex-4f8ff7)' : (isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-fff)'),
            border: `1px solid ${showFilters ? 'var(--tool-hex-4f8ff7)' : border}`,
            borderRadius: 9, color: showFilters ? 'var(--tool-hex-fff)' : text, fontSize: 12, cursor: 'pointer',
          }}
        >
          <Filter size={13} />
          Filters
        </button>
      }
    >
      {error && <div style={{ color: 'var(--tool-hex-f87171)', fontSize: 13, marginBottom: 12 }}>{error}</div>}

      {showFilters && (
        <div style={{ background: card, border: `1px solid ${border}`, borderRadius: 11, padding: 16, marginBottom: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(140px, 100%), 1fr))', gap: 10 }}>
          <div>
            <label style={{ fontSize: 11, color: muted, fontWeight: 600, display: 'block', marginBottom: 4 }}>Collection</label>
            <input
              value={filters.collection}
              onChange={e => f('collection')(e.target.value)}
              placeholder="e.g. students, fees..."
              style={{ width: '100%', background: 'var(--c-input)', border: `1px solid ${border}`, borderRadius: 7, padding: '7px 10px', color: text, fontSize: 12, boxSizing: 'border-box', outline: 'none' }}
            />
          </div>
          <div>
            <label style={{ fontSize: 11, color: muted, fontWeight: 600, display: 'block', marginBottom: 4 }}>Date From</label>
            <input
              type="date"
              value={filters.date_from}
              onChange={e => f('date_from')(e.target.value)}
              style={{ width: '100%', background: 'var(--c-input)', border: `1px solid ${border}`, borderRadius: 7, padding: '7px 10px', color: text, fontSize: 12, boxSizing: 'border-box', outline: 'none', colorScheme: isDark ? 'dark' : 'light' }}
            />
          </div>
          <div>
            <label style={{ fontSize: 11, color: muted, fontWeight: 600, display: 'block', marginBottom: 4 }}>Date To</label>
            <input
              type="date"
              value={filters.date_to}
              onChange={e => f('date_to')(e.target.value)}
              style={{ width: '100%', background: 'var(--c-input)', border: `1px solid ${border}`, borderRadius: 7, padding: '7px 10px', color: text, fontSize: 12, boxSizing: 'border-box', outline: 'none', colorScheme: isDark ? 'dark' : 'light' }}
            />
          </div>
          <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <div style={{ position: 'relative', flex: 1, minWidth: 160 }}>
              <Search size={12} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: muted }} />
              <input
                value={filters.q}
                onChange={e => f('q')(e.target.value)}
                placeholder="Search by user or record ID..."
                style={{ width: '100%', background: 'var(--c-input)', border: `1px solid ${border}`, borderRadius: 7, padding: '7px 10px 7px 28px', color: text, fontSize: 12, boxSizing: 'border-box', outline: 'none' }}
              />
            </div>
            <ActionBtn label="Search" onClick={() => load(1)} />
            <ActionBtn label="Clear" variant="secondary" onClick={() => { setFilters({ collection: '', changed_by: '', date_from: '', date_to: '', q: '' }); }} />
          </div>
        </div>
      )}

      {/* Audit table with horizontal scroll on mobile */}
      <div className="audit-table-wrapper" style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <div style={{ minWidth: 480 }}>
          {/* Column headers */}
          <div style={{ display: 'flex', padding: '0 0 6px', gap: 10, borderBottom: `2px solid ${border}`, marginBottom: 4 }}>
            <span style={{ width: 20 }} />
            <span style={{ width: 140, flexShrink: 0, fontSize: 11, fontWeight: 600, color: muted }}>TIMESTAMP</span>
            <span style={{ minWidth: 90, flexShrink: 0, fontSize: 11, fontWeight: 600, color: muted }}>ACTION</span>
            <span style={{ flex: 1, fontSize: 11, fontWeight: 600, color: muted }}>RECORD</span>
            <span style={{ minWidth: 100, flexShrink: 0, fontSize: 11, fontWeight: 600, color: muted, textAlign: 'right' }}>CHANGED BY</span>
          </div>

          {loading ? (
            <div style={{ color: muted, textAlign: 'center', padding: 40 }}>Loading...</div>
          ) : entries.length === 0 ? (
            <div style={{ color: muted, textAlign: 'center', padding: 40 }}>No audit entries found.</div>
          ) : (
            entries.map((entry, i) => (
              <AuditRow key={entry.id || i} entry={entry} isDark={isDark} />
            ))
          )}
        </div>
      </div>

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
          <ActionBtn label="Prev" variant="secondary" onClick={() => load(page - 1)} disabled={page <= 1} />
          <span style={{ fontSize: 12, color: muted, padding: '7px 12px' }}>{page} / {totalPages}</span>
          <ActionBtn label="Next" variant="secondary" onClick={() => load(page + 1)} disabled={page >= totalPages} />
        </div>
      )}
    </ToolPage>
  );
}
