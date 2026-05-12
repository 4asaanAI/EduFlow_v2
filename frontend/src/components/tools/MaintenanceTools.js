/**
 * Story 11 + 12: Maintenance Admin & IT/Tech Admin issue tracker panels
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useUser } from '../../contexts/UserContext';
import { useTheme } from '../../contexts/ThemeContext';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, Badge, ActionBtn, FormField, DataTable } from './ToolPage';
import { Plus, RefreshCw, MessageSquare, CheckCircle } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function h() { return getAuthHeaders(); }

const STATUS_COLORS = {
  open: 'var(--tool-hex-fb923c)',
  in_progress: 'var(--tool-hex-facc15)',
  pending_owner_confirmation: 'var(--tool-hex-818cf8)',
  closed: 'var(--tool-hex-34d399)',
};

function StatusBadge({ status }) {
  return (
    <Badge
      label={status?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
      color={STATUS_COLORS[status] || 'var(--tool-hex-888)'}
    />
  );
}

function RequestCard({ item, onUpdate, onConfirm, role, subCategory, isDark }) {
  const [showNote, setShowNote] = useState(false);
  const [note, setNote] = useState('');
  const [newStatus, setNewStatus] = useState(item.status);
  const [saving, setSaving] = useState(false);
  const bg = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-fff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-888)' : 'var(--tool-hex-737373)';

  const isOwner = role === 'owner';
  const isMaint = subCategory === 'maintenance';
  const isIT = subCategory === 'it_tech';
  const type = item.issue_type || item.type;
  const statusOptions = isMaint
    ? ['open', 'in_progress', 'pending_owner_confirmation']
    : isIT
    ? ['open', 'in_progress', 'closed']
    : ['open', 'in_progress', 'pending_owner_confirmation', 'closed'];

  const handleSave = async () => {
    setSaving(true);
    await onUpdate(item.id, { status: newStatus, note: note.trim() || undefined }, type);
    setNote('');
    setShowNote(false);
    setSaving(false);
  };

  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 11, padding: 16, marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: text }}>{item.description}</span>
          {item.location && <span style={{ fontSize: 11, color: muted, marginLeft: 8 }}>@ {item.location}</span>}
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Badge label={item.category?.replace(/_/g, ' ')} color="var(--tool-hex-6366f1)" />
          <StatusBadge status={item.status} />
        </div>
      </div>

      <div style={{ fontSize: 11, color: muted, marginBottom: 10 }}>
        Logged by {item.logged_by_name || 'Unknown'} · {item.created_at?.slice(0, 10)}
      </div>

      {item.notes?.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          {item.notes.slice(-2).map(n => (
            <div key={n.id} style={{ fontSize: 11, color: muted, padding: '4px 0', borderTop: `1px solid ${border}` }}>
              <span style={{ fontWeight: 600, color: isDark ? 'var(--tool-hex-bbb)' : 'var(--tool-hex-555)' }}>{n.author_name}:</span> {n.content}
              <span style={{ float: 'right' }}>{n.timestamp?.slice(0, 10)}</span>
            </div>
          ))}
        </div>
      )}

      {item.status !== 'closed' && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {!showNote ? (
            <ActionBtn label="Add Note / Update" icon={<MessageSquare size={11} />} onClick={() => setShowNote(true)} variant="secondary" />
          ) : (
            <div style={{ width: '100%' }}>
              <select
                value={newStatus}
                onChange={e => setNewStatus(e.target.value)}
                style={{ background: isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-f5f5f5)', border: `1px solid ${border}`, borderRadius: 7, padding: '6px 10px', color: text, fontSize: 12, marginBottom: 8, width: '100%' }}
              >
                {statusOptions.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
              </select>
              <textarea
                value={note}
                onChange={e => setNote(e.target.value)}
                placeholder="Add a note (optional)..."
                rows={2}
                style={{ width: '100%', background: isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-f5f5f5)', border: `1px solid ${border}`, borderRadius: 7, padding: '8px 10px', color: text, fontSize: 12, resize: 'vertical', boxSizing: 'border-box' }}
              />
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                <ActionBtn label={saving ? 'Saving...' : 'Save'} onClick={handleSave} disabled={saving} />
                <ActionBtn label="Cancel" variant="secondary" onClick={() => { setShowNote(false); setNote(''); setNewStatus(item.status); }} />
              </div>
            </div>
          )}

          {isOwner && item.status === 'pending_owner_confirmation' && type === 'facility' && (
            <ActionBtn
              label="Confirm Resolution"
              icon={<CheckCircle size={11} />}
              onClick={() => onConfirm(item.id)}
              style={{ background: 'var(--tool-hex-22c55e)', color: 'var(--tool-hex-fff)' }}
            />
          )}
        </div>
      )}
    </div>
  );
}

function IssuePanel({ type, title }) {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ description: '', location: '', category: type === 'facility' ? 'plumbing' : 'hardware' });
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  const facilityCategories = ['plumbing', 'electrical', 'civil', 'cleaning', 'security', 'other'];
  const techCategories = ['hardware', 'software', 'network', 'printer', 'projector', 'other'];

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API}/issues/${type}`, { headers: h() });
      const data = await res.json();
      if (data.success) setItems(data.data || []);
      else setError(data.detail || 'Failed to load');
    } catch {
      setError('Network error');
    }
    setLoading(false);
  }, [type]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.description) { setFormError('Description is required'); return; }
    setSaving(true);
    setFormError('');
    try {
      const res = await fetch(`${API}/issues/${type}`, {
        method: 'POST',
        headers: { ...h(), 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (data.success) { setShowForm(false); setForm({ description: '', location: '', category: type === 'facility' ? 'plumbing' : 'hardware' }); load(); }
      else setFormError(data.detail || 'Failed to create');
    } catch { setFormError('Network error'); }
    setSaving(false);
  };

  const handleUpdate = async (id, updates, issueType) => {
    await fetch(`${API}/issues/${issueType}/${id}`, {
      method: 'PATCH',
      headers: { ...h(), 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    load();
  };

  const handleConfirm = async (id) => {
    await fetch(`${API}/issues/facility/${id}/confirm-resolution`, { method: 'POST', headers: h() });
    load();
  };

  const canCreate = currentUser.role === 'owner'
    || (currentUser.role === 'admin' && currentUser.sub_category === (type === 'facility' ? 'maintenance' : 'it_tech'));

  const open = items.filter(i => i.status !== 'closed');
  const closed = items.filter(i => i.status === 'closed');

  return (
    <ToolPage
      title={title}
      subtitle={`${open.length} open · ${closed.length} resolved`}
      onRefresh={load}
      loading={loading}
      actions={canCreate ? <ActionBtn label="New Request" icon={<Plus size={11} />} onClick={() => setShowForm(true)} /> : null}
    >
      {error && <div style={{ color: 'var(--tool-hex-f87171)', fontSize: 13, marginBottom: 12 }}>{error}</div>}

      {showForm && (
        <div style={{ background: isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-fff)', border: `1px solid ${isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)'}`, borderRadius: 11, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)', marginBottom: 14 }}>New {type === 'facility' ? 'Facility' : 'Tech'} Request</h3>
          <form onSubmit={handleCreate}>
            <FormField label="Description" value={form.description} onChange={f('description')} placeholder="Describe the issue..." required />
            <FormField label="Location" value={form.location} onChange={f('location')} placeholder="Classroom, lab, office..." />
            <FormField
              label="Category"
              type="select"
              value={form.category}
              onChange={f('category')}
              options={(type === 'facility' ? facilityCategories : techCategories).map(c => ({ value: c, label: c.replace(/_/g, ' ').replace(/\b\w/g, x => x.toUpperCase()) }))}
            />
            {formError && <div style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 8 }}>{formError}</div>}
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={saving ? 'Submitting...' : 'Submit Request'} type="submit" disabled={saving} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => { setShowForm(false); setFormError(''); }} />
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div style={{ color: isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)', fontSize: 13, textAlign: 'center', padding: 40 }}>Loading...</div>
      ) : items.length === 0 ? (
        <div style={{ color: isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)', fontSize: 13, textAlign: 'center', padding: 40 }}>No requests yet. Submit one above.</div>
      ) : (
        <>
          {open.length > 0 && (
            <>
              <p style={{ fontSize: 11, fontWeight: 600, color: isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)', marginBottom: 8, letterSpacing: '0.06em' }}>OPEN</p>
              {open.map(item => (
                <RequestCard
                  key={item.id}
                  item={item}
                  onUpdate={handleUpdate}
                  onConfirm={handleConfirm}
                  role={currentUser.role}
                  subCategory={currentUser.sub_category}
                  isDark={isDark}
                />
              ))}
            </>
          )}
          {closed.length > 0 && (
            <>
              <p style={{ fontSize: 11, fontWeight: 600, color: isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)', marginBottom: 8, marginTop: 16, letterSpacing: '0.06em' }}>RESOLVED</p>
              {closed.slice(0, 5).map(item => (
                <RequestCard
                  key={item.id}
                  item={item}
                  onUpdate={handleUpdate}
                  onConfirm={handleConfirm}
                  role={currentUser.role}
                  subCategory={currentUser.sub_category}
                  isDark={isDark}
                />
              ))}
            </>
          )}
        </>
      )}
    </ToolPage>
  );
}

export function MaintenanceFacilityTracker() {
  return <IssuePanel type="facility" title="Facility Requests" />;
}

export function ITTechIssueTracker() {
  return <IssuePanel type="tech" title="Tech Issue Tracker" />;
}

export function AllIssuesView() {
  const { isDark } = useTheme();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const { currentUser } = useUser();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/issues?type=all`, { headers: h() });
      const data = await res.json();
      if (data.success) setItems(data.data || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = filter === 'all' ? items : items.filter(i => i.issue_type === filter || i.status === filter);

  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-888)' : 'var(--tool-hex-737373)';

  return (
    <ToolPage title="All Issues" subtitle={`${items.filter(i => i.status !== 'closed').length} open`} onRefresh={load} loading={loading}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {['all', 'facility', 'tech', 'open', 'closed'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: '5px 12px', borderRadius: 7, fontSize: 12, cursor: 'pointer',
              background: filter === f ? 'var(--tool-hex-4f8ff7)' : (isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-f5f5f5)'),
              color: filter === f ? 'var(--tool-hex-fff)' : text,
              border: `1px solid ${filter === f ? 'var(--tool-hex-4f8ff7)' : (isDark ? 'var(--tool-hex-333)' : 'var(--tool-hex-e5e5e5)')}`,
              fontWeight: 500,
            }}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>
      {loading ? (
        <div style={{ color: muted, textAlign: 'center', padding: 40 }}>Loading...</div>
      ) : filtered.length === 0 ? (
        <div style={{ color: muted, textAlign: 'center', padding: 40 }}>No issues found.</div>
      ) : (
        <DataTable
          headers={['Type', 'Description', 'Category', 'Location', 'Status', 'Date']}
          rows={filtered.map(i => [
            <Badge label={i.issue_type || i.type} color={i.issue_type === 'facility' ? 'var(--tool-hex-fb923c)' : 'var(--tool-hex-818cf8)'} />,
            <span style={{ color: text, fontSize: 12 }}>{i.description?.slice(0, 60)}{i.description?.length > 60 ? '…' : ''}</span>,
            i.category,
            i.location || '—',
            <StatusBadge status={i.status} />,
            i.created_at?.slice(0, 10),
          ])}
        />
      )}
    </ToolPage>
  );
}
