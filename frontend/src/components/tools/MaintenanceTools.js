/**
 * Story 11 + 12 + Maintenance Module: Maintenance Admin & IT/Tech Admin issue tracker panels,
 * plus MaintenanceSchedule, VendorLog, and RaiseMaintenanceRequest components.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useUser } from '../../contexts/UserContext';
import { useTheme } from '../../contexts/ThemeContext';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, Badge, ActionBtn, FormField, DataTable } from './ToolPage';
import { Plus, RefreshCw, MessageSquare, CheckCircle, Calendar, Users, Wrench, AlertTriangle, ClipboardList, Camera, X as XIcon } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function h() { return getAuthHeaders(); }

const STATUS_COLORS = {
  open: 'var(--tool-hex-fb923c)',
  accepted: 'var(--tool-hex-fbbf24)',
  in_progress: 'var(--tool-hex-facc15)',
  pending_parts: 'var(--tool-hex-818cf8)',
  pending_owner_confirmation: 'var(--tool-hex-a78bfa)',
  done: 'var(--tool-hex-34d399)',
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
  const [saveError, setSaveError] = useState('');
  const bg = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-fff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-888)' : 'var(--tool-hex-737373)';

  const isOwner = role === 'owner';
  const isMaint = subCategory === 'maintenance';
  const isIT = subCategory === 'it_tech';
  const type = item.issue_type || item.type;
  const statusOptions = isMaint
    ? ['open', 'accepted', 'in_progress', 'pending_parts', 'pending_owner_confirmation', 'done']
    : isIT
    ? ['open', 'accepted', 'in_progress', 'pending_parts', 'done', 'closed']
    : ['open', 'accepted', 'in_progress', 'pending_parts', 'pending_owner_confirmation', 'done', 'closed'];

  const handleSave = async () => {
    setSaving(true);
    setSaveError('');
    const ok = await onUpdate(item.id, { status: newStatus, note: note.trim() || undefined }, type);
    if (ok) {
      setNote('');
      setShowNote(false);
    } else {
      setSaveError('Failed to update. Check your permissions and try again.');
    }
    setSaving(false);
  };

  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 11, padding: 16, marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: text }}>{item.description}</span>
          {item.location && <span style={{ fontSize: 11, color: muted, marginLeft: 8 }}>@ {item.location}</span>}
          {item.overdue && <span style={{ marginLeft: 8 }}><Badge label="Overdue" color="var(--tool-hex-f87171)" /></span>}
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Badge label={item.category?.replace(/_/g, ' ')} color="var(--tool-hex-6366f1)" />
          <StatusBadge status={item.status} />
        </div>
      </div>

      <div style={{ fontSize: 11, color: muted, marginBottom: 10 }}>
        Logged by {item.logged_by_name || 'Unknown'} · {item.created_at?.slice(0, 10)}
        {item.sla_due_at ? ` · SLA ${item.sla_due_at.slice(0, 10)}` : ''}
        {item.estimated_cost ? ` · Est. Rs. ${item.estimated_cost}` : ''}
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
              {saveError && <div style={{ color: 'var(--tool-hex-f87171)', fontSize: 11, marginBottom: 6 }}>{saveError}</div>}
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                <ActionBtn label={saving ? 'Saving...' : 'Save'} onClick={handleSave} disabled={saving} />
                <ActionBtn label="Cancel" variant="secondary" onClick={() => { setShowNote(false); setNote(''); setNewStatus(item.status); setSaveError(''); }} />
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
  const [form, setForm] = useState({ description: '', location: '', category: type === 'facility' ? 'plumbing' : 'hardware', priority: 'medium' });
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  const facilityCategories = ['plumbing', 'electrical', 'civil', 'cleaning', 'security', 'carpentry', 'painting', 'pest_control', 'hvac', 'fire_safety', 'landscaping', 'other'];
  const techCategories = ['hardware', 'software', 'network', 'printer', 'projector', 'other'];
  const priorities = ['low', 'medium', 'high', 'urgent'];

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
      if (data.success) { setShowForm(false); setForm({ description: '', location: '', category: type === 'facility' ? 'plumbing' : 'hardware', priority: 'medium' }); load(); }
      else setFormError(data.detail || 'Failed to create');
    } catch { setFormError('Network error'); }
    setSaving(false);
  };

  const handleUpdate = async (id, updates, issueType) => {
    const resolvedType = issueType || type;
    try {
      const res = await fetch(`${API}/issues/${resolvedType}/${id}`, {
        method: 'PATCH',
        headers: { ...h(), 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      const data = await res.json();
      load();
      return data.success === true;
    } catch {
      return false;
    }
  };

  const handleConfirm = async (id) => {
    await fetch(`${API}/issues/facility/${id}/confirm-resolution`, { method: 'POST', headers: h() });
    load();
  };

  const canCreate = currentUser.role === 'owner'
    || (currentUser.role === 'admin' && currentUser.sub_category === (type === 'facility' ? 'maintenance' : 'it_tech'));

  const open = items.filter(i => !['done', 'closed'].includes(i.status));
  const closed = items.filter(i => ['done', 'closed'].includes(i.status));

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
            {type === 'facility' && (
              <FormField label="Priority" type="select" value={form.priority} onChange={f('priority')}
                options={priorities.map(p => ({ value: p, label: p.replace(/\b\w/g, x => x.toUpperCase()) }))} />
            )}
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

// ─── PRIORITY helpers ────────────────────────────────────────────────────────
const PRIORITY_COLORS = {
  urgent: 'var(--tool-hex-f87171)',
  high: 'var(--tool-hex-fb923c)',
  medium: 'var(--tool-hex-facc15)',
  low: 'var(--tool-hex-34d399)',
};
function PriorityBadge({ priority }) {
  return <Badge label={priority || 'medium'} color={PRIORITY_COLORS[priority] || 'var(--tool-hex-888)'} />;
}

// ─── Photo Uploader (up to 3 photos, uploads to S3 via /api/uploads) ─────────
function PhotoUploader({ photos, onChange, isDark }) {
  const [uploading, setUploading] = useState(false);
  const border = isDark ? 'var(--tool-hex-333)' : 'var(--tool-hex-e5e5e5)';
  const muted = isDark ? 'var(--tool-hex-888)' : 'var(--tool-hex-737373)';

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file || photos.length >= 3) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('entity_type', 'maintenance_request');
      const res = await fetch(`${API}/uploads`, { method: 'POST', headers: h(), body: fd });
      const data = await res.json();
      if (data.success) onChange([...photos, data.data.file_url]);
    } catch {}
    setUploading(false);
    e.target.value = '';
  };

  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ fontSize: 10, color: muted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>Photos (up to 3)</label>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {photos.map((url, i) => (
          <div key={i} style={{ position: 'relative', width: 72, height: 72 }}>
            <img src={url} alt="" style={{ width: 72, height: 72, objectFit: 'cover', borderRadius: 8, border: `1px solid ${border}` }} />
            <button type="button" onClick={() => onChange(photos.filter((_, j) => j !== i))}
              style={{ position: 'absolute', top: -6, right: -6, background: 'var(--tool-hex-f87171)', border: 'none', borderRadius: '50%', width: 18, height: 18, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0 }}>
              <XIcon size={10} color="#fff" />
            </button>
          </div>
        ))}
        {photos.length < 3 && (
          <label style={{ width: 72, height: 72, border: `2px dashed ${border}`, borderRadius: 8, cursor: uploading ? 'wait' : 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
            <Camera size={18} color={muted} />
            <span style={{ fontSize: 9, color: muted }}>{uploading ? 'Uploading...' : 'Add photo'}</span>
            <input type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFile} disabled={uploading} />
          </label>
        )}
      </div>
    </div>
  );
}

// ─── Maintenance Schedule ─────────────────────────────────────────────────────
const RECURRENCE_OPTIONS = ['one_time', 'weekly', 'monthly', 'quarterly', 'annual'];
const SCHEDULE_STATUS_OPTIONS = ['scheduled', 'in_progress', 'done', 'skipped'];

export function MaintenanceSchedule() {
  const { isDark } = useTheme();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: '', description: '', scheduled_date: '', recurrence: 'one_time', category: 'other', assigned_to: '', vendor_id: '' });
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/issues/maintenance/schedule?limit=50`, { headers: h() });
      const data = await res.json();
      if (data.success) setEntries(data.data || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.title || !form.scheduled_date) { setFormError('Title and date are required'); return; }
    setSaving(true);
    setFormError('');
    try {
      const res = await fetch(`${API}/issues/maintenance/schedule`, {
        method: 'POST',
        headers: { ...h(), 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (data.success) { setShowForm(false); setForm({ title: '', description: '', scheduled_date: '', recurrence: 'one_time', category: 'other', assigned_to: '', vendor_id: '' }); load(); }
      else setFormError(data.detail || 'Failed to create');
    } catch { setFormError('Network error'); }
    setSaving(false);
  };

  const handleStatusChange = async (id, status) => {
    await fetch(`${API}/issues/maintenance/schedule/${id}`, {
      method: 'PATCH',
      headers: { ...h(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    load();
  };

  const bg = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-fff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-888)' : 'var(--tool-hex-737373)';

  return (
    <ToolPage title="Maintenance Schedule" subtitle="Preventive maintenance calendar" onRefresh={load} loading={loading}
      actions={<ActionBtn label="Add Entry" icon={<Plus size={11} />} onClick={() => setShowForm(true)} />}>

      {showForm && (
        <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 11, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: text, marginBottom: 14 }}>New Schedule Entry</h3>
          <form onSubmit={handleCreate}>
            <FormField label="Title" value={form.title} onChange={f('title')} placeholder="Annual generator service..." required />
            <FormField label="Description" value={form.description} onChange={f('description')} placeholder="Details..." />
            <FormField label="Date" type="date" value={form.scheduled_date} onChange={f('scheduled_date')} required />
            <FormField label="Recurrence" type="select" value={form.recurrence} onChange={f('recurrence')}
              options={RECURRENCE_OPTIONS.map(r => ({ value: r, label: r.replace(/_/g, ' ').replace(/\b\w/g, x => x.toUpperCase()) }))} />
            <FormField label="Category" type="select" value={form.category} onChange={f('category')}
              options={['plumbing', 'electrical', 'civil', 'cleaning', 'security', 'hvac', 'fire_safety', 'other'].map(c => ({ value: c, label: c.replace(/_/g, ' ').replace(/\b\w/g, x => x.toUpperCase()) }))} />
            <FormField label="Assigned To" value={form.assigned_to} onChange={f('assigned_to')} placeholder="Staff name or vendor..." />
            <FormField label="Vendor ID" value={form.vendor_id} onChange={f('vendor_id')} placeholder="Optional preferred vendor id" />
            {formError && <div style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 8 }}>{formError}</div>}
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={saving ? 'Saving...' : 'Save'} type="submit" disabled={saving} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => { setShowForm(false); setFormError(''); }} />
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div style={{ color: muted, textAlign: 'center', padding: 40 }}>Loading...</div>
      ) : entries.length === 0 ? (
        <div style={{ color: muted, textAlign: 'center', padding: 40 }}>No schedule entries yet.</div>
      ) : (
        <DataTable
          headers={['Title', 'Date', 'Recurrence', 'Category', 'Assigned To', 'Status', 'SLA', 'Action']}
          rows={entries.map(e => [
            <span style={{ color: text, fontSize: 12, fontWeight: 600 }}>{e.title}</span>,
            <span style={{ color: muted, fontSize: 11 }}>{e.scheduled_date}</span>,
            <Badge label={e.recurrence?.replace(/_/g, ' ')} color="var(--tool-hex-818cf8)" />,
            <span style={{ color: muted, fontSize: 11 }}>{e.category}</span>,
            <span style={{ color: muted, fontSize: 11 }}>{e.assigned_to || '—'}</span>,
            <Badge label={e.status} color={e.status === 'done' ? 'var(--tool-hex-34d399)' : e.status === 'skipped' ? 'var(--tool-hex-888)' : 'var(--tool-hex-facc15)'} />,
            e.overdue ? <Badge label="Overdue" color="var(--tool-hex-f87171)" /> : <span style={{ color: muted, fontSize: 11 }}>On track</span>,
            <select value={e.status} onChange={ev => handleStatusChange(e.id, ev.target.value)}
              style={{ background: isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-f5f5f5)', border: `1px solid ${border}`, borderRadius: 6, padding: '3px 8px', color: text, fontSize: 11, cursor: 'pointer' }}>
              {SCHEDULE_STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>,
          ])}
        />
      )}
    </ToolPage>
  );
}

// ─── Vendor Log ───────────────────────────────────────────────────────────────
export function VendorLog() {
  const { isDark } = useTheme();
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', category: 'general', contact_person: '', phone: '', email: '', address: '', gst_number: '', rating: 0 });
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/issues/maintenance/vendors?limit=100`, { headers: h() });
      const data = await res.json();
      if (data.success) setVendors(data.data || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.name) { setFormError('Vendor name is required'); return; }
    setSaving(true);
    setFormError('');
    try {
      const res = await fetch(`${API}/issues/maintenance/vendors`, {
        method: 'POST',
        headers: { ...h(), 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (data.success) { setShowForm(false); setForm({ name: '', category: 'general', contact_person: '', phone: '', email: '', address: '', gst_number: '', rating: 0 }); load(); }
      else setFormError(data.detail || 'Failed to add vendor');
    } catch { setFormError('Network error'); }
    setSaving(false);
  };

  const toggleActive = async (vendor) => {
    await fetch(`${API}/issues/maintenance/vendors/${vendor.id}`, {
      method: 'PATCH',
      headers: { ...h(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: !vendor.is_active }),
    });
    load();
  };

  const bg = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-fff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-888)' : 'var(--tool-hex-737373)';

  return (
    <ToolPage title="Vendor Log" subtitle={`${vendors.filter(v => v.is_active).length} active vendors`} onRefresh={load} loading={loading}
      actions={<ActionBtn label="Add Vendor" icon={<Plus size={11} />} onClick={() => setShowForm(true)} />}>

      {showForm && (
        <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 11, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: text, marginBottom: 14 }}>New Vendor</h3>
          <form onSubmit={handleCreate}>
            <FormField label="Vendor Name" value={form.name} onChange={f('name')} placeholder="ABC Plumbing Services..." required />
            <FormField label="Category" type="select" value={form.category} onChange={f('category')}
              options={['general', 'plumbing', 'electrical', 'civil', 'cleaning', 'security', 'hvac', 'it', 'landscaping', 'other'].map(c => ({ value: c, label: c.replace(/\b\w/g, x => x.toUpperCase()) }))} />
            <FormField label="Contact Person" value={form.contact_person} onChange={f('contact_person')} placeholder="Name..." />
            <FormField label="Phone" value={form.phone} onChange={f('phone')} placeholder="98XXXXXXXX" />
            <FormField label="Email" value={form.email} onChange={f('email')} placeholder="vendor@email.com" />
            <FormField label="Address" value={form.address} onChange={f('address')} placeholder="Full address..." />
            <FormField label="GST Number" value={form.gst_number} onChange={f('gst_number')} placeholder="27XXXXX..." />
            <FormField label="Rating" type="number" value={form.rating} onChange={f('rating')} placeholder="0 to 5" />
            {formError && <div style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 8 }}>{formError}</div>}
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={saving ? 'Saving...' : 'Add Vendor'} type="submit" disabled={saving} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => { setShowForm(false); setFormError(''); }} />
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div style={{ color: muted, textAlign: 'center', padding: 40 }}>Loading...</div>
      ) : vendors.length === 0 ? (
        <div style={{ color: muted, textAlign: 'center', padding: 40 }}>No vendors added yet.</div>
      ) : (
        <DataTable
          headers={['Name', 'Category', 'Contact', 'Phone', 'GST', 'Rating', 'Status', 'Action']}
          rows={vendors.map(v => [
            <span style={{ color: text, fontSize: 12, fontWeight: 600 }}>{v.name}</span>,
            <Badge label={v.category} color="var(--tool-hex-6366f1)" />,
            <span style={{ color: muted, fontSize: 11 }}>{v.contact_person || '—'}</span>,
            <span style={{ color: muted, fontSize: 11 }}>{v.phone || '—'}</span>,
            <span style={{ color: muted, fontSize: 11 }}>{v.gst_number || '—'}</span>,
            <span style={{ color: muted, fontSize: 11 }}>{Number(v.rating || 0).toFixed(1)}</span>,
            <Badge label={v.is_active ? 'Active' : 'Inactive'} color={v.is_active ? 'var(--tool-hex-34d399)' : 'var(--tool-hex-888)'} />,
            <ActionBtn label={v.is_active ? 'Deactivate' : 'Activate'} variant="secondary" onClick={() => toggleActive(v)} />,
          ])}
        />
      )}
    </ToolPage>
  );
}

// ─── Raise Maintenance Request (teachers / non-maintenance staff) ─────────────
export function RaiseMaintenanceRequest() {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [myRequests, setMyRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ description: '', location: '', category: 'other', priority: 'medium' });
  const [formPhotos, setFormPhotos] = useState([]);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  const facilityCategories = ['plumbing', 'electrical', 'civil', 'cleaning', 'security', 'carpentry', 'painting', 'pest_control', 'hvac', 'fire_safety', 'landscaping', 'other'];
  const priorities = ['low', 'medium', 'high', 'urgent'];

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/issues/facility?limit=20`, { headers: h() });
      const data = await res.json();
      if (data.success) setMyRequests(data.data || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.description) { setFormError('Please describe the issue'); return; }
    setSaving(true);
    setFormError('');
    setSuccess('');
    try {
      const res = await fetch(`${API}/issues/facility`, {
        method: 'POST',
        headers: { ...h(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, photos: formPhotos }),
      });
      const data = await res.json();
      if (data.success) {
        setShowForm(false);
        setForm({ description: '', location: '', category: 'other', priority: 'medium' });
        setFormPhotos([]);
        setSuccess('Request submitted! The maintenance team has been notified.');
        load();
        setTimeout(() => setSuccess(''), 5000);
      } else setFormError(data.detail || 'Failed to submit');
    } catch { setFormError('Network error'); }
    setSaving(false);
  };

  const bg = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-fff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-888)' : 'var(--tool-hex-737373)';

  const open = myRequests.filter(i => !['done', 'closed'].includes(i.status));
  const closed = myRequests.filter(i => ['done', 'closed'].includes(i.status));

  return (
    <ToolPage
      title="Raise Maintenance Request"
      subtitle={`${open.length} open · ${closed.length} resolved`}
      onRefresh={load}
      loading={loading}
      actions={<ActionBtn label="New Request" icon={<Plus size={11} />} onClick={() => setShowForm(true)} />}
    >
      {success && (
        <div style={{ background: 'var(--tool-hex-22c55e)18', border: '1px solid var(--tool-hex-22c55e)', borderRadius: 9, padding: '10px 14px', marginBottom: 14, color: 'var(--tool-hex-22c55e)', fontSize: 13 }}>
          {success}
        </div>
      )}

      {showForm && (
        <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 11, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: text, marginBottom: 14 }}>Report an Issue</h3>
          <form onSubmit={handleCreate}>
            <FormField label="What's the issue?" value={form.description} onChange={f('description')} placeholder="e.g. Leaking tap in Classroom 5A..." required />
            <FormField label="Location" value={form.location} onChange={f('location')} placeholder="Room number, floor, wing..." />
            <FormField label="Category" type="select" value={form.category} onChange={f('category')}
              options={facilityCategories.map(c => ({ value: c, label: c.replace(/_/g, ' ').replace(/\b\w/g, x => x.toUpperCase()) }))} />
            <FormField label="How urgent is it?" type="select" value={form.priority} onChange={f('priority')}
              options={priorities.map(p => ({ value: p, label: p.replace(/\b\w/g, x => x.toUpperCase()) }))} />
            <PhotoUploader photos={formPhotos} onChange={setFormPhotos} isDark={isDark} />
            {formError && <div style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 8 }}>{formError}</div>}
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={saving ? 'Submitting...' : 'Submit Request'} type="submit" disabled={saving} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => { setShowForm(false); setFormError(''); }} />
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div style={{ color: muted, textAlign: 'center', padding: 40 }}>Loading...</div>
      ) : myRequests.length === 0 ? (
        <div style={{ color: muted, textAlign: 'center', padding: 40 }}>No requests yet. Use the button above to report an issue.</div>
      ) : (
        <>
          {open.length > 0 && (
            <>
              <p style={{ fontSize: 11, fontWeight: 600, color: muted, marginBottom: 8, letterSpacing: '0.06em' }}>MY OPEN REQUESTS</p>
              {open.map(item => (
                <div key={item.id} style={{ background: bg, border: `1px solid ${border}`, borderRadius: 10, padding: 12, marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: text, flex: 1 }}>{item.description}</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <PriorityBadge priority={item.priority} />
                      <StatusBadge status={item.status} />
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: muted }}>{item.category} · {item.location || 'No location'} · Submitted {item.created_at?.slice(0, 10)}</div>
                </div>
              ))}
            </>
          )}
          {closed.length > 0 && (
            <>
              <p style={{ fontSize: 11, fontWeight: 600, color: muted, marginBottom: 8, marginTop: 16, letterSpacing: '0.06em' }}>RESOLVED</p>
              {closed.slice(0, 5).map(item => (
                <div key={item.id} style={{ background: bg, border: `1px solid ${border}`, borderRadius: 10, padding: 12, marginBottom: 8, opacity: 0.7 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: 13, color: text }}>{item.description}</span>
                    <StatusBadge status={item.status} />
                  </div>
                </div>
              ))}
            </>
          )}
        </>
      )}
    </ToolPage>
  );
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
