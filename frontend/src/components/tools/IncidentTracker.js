/**
 * Story 13: Incident, Complaint & Visitor Management
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useUser } from '../../contexts/UserContext';
import { useTheme } from '../../contexts/ThemeContext';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, Badge, ActionBtn, FormField, DataTable } from './ToolPage';
import { Plus, MessageSquare, UserCheck, AlertTriangle } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function h() { return getAuthHeaders(); }

const SEVERITY_COLORS = { low: '#34d399', medium: '#facc15', high: '#f87171' };
const STATUS_COLORS = { open: '#fb923c', in_progress: '#60a5fa', resolved: '#34d399' };

export default function IncidentTracker() {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [tab, setTab] = useState('incidents'); // 'incidents' | 'visitors'
  const [incidents, setIncidents] = useState([]);
  const [visitors, setVisitors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ description: '', severity: 'low', involved_parties: '', category: 'general' });
  const [visitorForm, setVisitorForm] = useState({ name: '', purpose: '', student_or_staff_involved: '', outcome: '' });
  const [threadMsg, setThreadMsg] = useState('');
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const bg = isDark ? '#1a1a1a' : '#f5f5f5';
  const card = isDark ? '#1e1e1e' : '#fff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#737373';

  const loadIncidents = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (statusFilter) params.append('status', statusFilter);
    if (searchQ) params.append('q', searchQ);
    try {
      const res = await fetch(`${API}/ops/incidents?${params}`, { headers: h() });
      const data = await res.json();
      if (data.success) setIncidents(data.data || []);
    } catch {}
    setLoading(false);
  }, [statusFilter, searchQ]);

  const loadVisitors = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/ops/visitors`, { headers: h() });
      const data = await res.json();
      if (data.success) setVisitors(data.data || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    if (tab === 'incidents') loadIncidents();
    else loadVisitors();
  }, [tab, loadIncidents, loadVisitors]);

  const openDetail = async (id) => {
    try {
      const res = await fetch(`${API}/ops/incidents/${id}`, { headers: h() });
      const data = await res.json();
      if (data.success) setSelected(data.data);
    } catch {}
  };

  const createIncident = async (e) => {
    e.preventDefault();
    if (!form.description) { setFormError('Description required'); return; }
    setSaving(true);
    setFormError('');
    const res = await fetch(`${API}/ops/incidents`, {
      method: 'POST',
      headers: { ...h(), 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    });
    const data = await res.json();
    if (data.success) { setShowForm(false); setForm({ description: '', severity: 'low', involved_parties: '', category: 'general' }); loadIncidents(); }
    else setFormError(data.detail || 'Failed to create');
    setSaving(false);
  };

  const createVisitor = async (e) => {
    e.preventDefault();
    setSaving(true);
    const res = await fetch(`${API}/ops/visitors`, {
      method: 'POST',
      headers: { ...h(), 'Content-Type': 'application/json' },
      body: JSON.stringify(visitorForm),
    });
    const data = await res.json();
    if (data.success) { setShowForm(false); setVisitorForm({ name: '', purpose: '', student_or_staff_involved: '', outcome: '' }); loadVisitors(); }
    setSaving(false);
  };

  const addThread = async () => {
    if (!threadMsg.trim() || !selected) return;
    const res = await fetch(`${API}/ops/incidents/${selected.id}/thread`, {
      method: 'POST',
      headers: { ...h(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: threadMsg }),
    });
    const data = await res.json();
    if (data.success) {
      setThreadMsg('');
      openDetail(selected.id);
    }
  };

  const fi = k => v => setForm(p => ({ ...p, [k]: v }));
  const fv = k => v => setVisitorForm(p => ({ ...p, [k]: v }));

  return (
    <ToolPage
      title="Incidents & Visitors"
      subtitle="Log, track, and resolve"
      onRefresh={() => tab === 'incidents' ? loadIncidents() : loadVisitors()}
      loading={loading}
      actions={<ActionBtn label="New" icon={<Plus size={11} />} onClick={() => setShowForm(true)} />}
    >
      {/* Tab switcher */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {['incidents', 'visitors'].map(t => (
          <button
            key={t}
            onClick={() => { setTab(t); setSelected(null); setShowForm(false); }}
            style={{
              padding: '7px 16px', borderRadius: 8, fontSize: 12, cursor: 'pointer', fontWeight: 600,
              background: tab === t ? '#4f8ff7' : (isDark ? '#252525' : '#f5f5f5'),
              color: tab === t ? '#fff' : text,
              border: `1px solid ${tab === t ? '#4f8ff7' : border}`,
            }}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Create form */}
      {showForm && tab === 'incidents' && (
        <div style={{ background: card, border: `1px solid ${border}`, borderRadius: 11, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: text, marginBottom: 14 }}>Log Incident</h3>
          <form onSubmit={createIncident}>
            <FormField label="Description" value={form.description} onChange={fi('description')} placeholder="What happened?" required />
            <FormField label="Involved Parties" value={form.involved_parties} onChange={fi('involved_parties')} placeholder="Names or groups involved" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Severity" type="select" value={form.severity} onChange={fi('severity')}
                options={[{ value: 'low', label: 'Low' }, { value: 'medium', label: 'Medium' }, { value: 'high', label: 'High (owner notified)' }]} />
              <FormField label="Category" type="select" value={form.category} onChange={fi('category')}
                options={[{ value: 'general', label: 'General' }, { value: 'discipline', label: 'Discipline' }, { value: 'safety', label: 'Safety' }, { value: 'property', label: 'Property' }]} />
            </div>
            {formError && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 8 }}>{formError}</div>}
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={saving ? 'Saving...' : 'Log Incident'} type="submit" disabled={saving} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => setShowForm(false)} />
            </div>
          </form>
        </div>
      )}

      {showForm && tab === 'visitors' && (
        <div style={{ background: card, border: `1px solid ${border}`, borderRadius: 11, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: text, marginBottom: 14 }}>Log Visitor</h3>
          <form onSubmit={createVisitor}>
            <FormField label="Visitor Name" value={visitorForm.name} onChange={fv('name')} placeholder="Full name" required />
            <FormField label="Purpose" value={visitorForm.purpose} onChange={fv('purpose')} placeholder="Meeting, delivery, inspection..." />
            <FormField label="Student/Staff Involved" value={visitorForm.student_or_staff_involved} onChange={fv('student_or_staff_involved')} placeholder="Name of person being visited" />
            <FormField label="Outcome" value={visitorForm.outcome} onChange={fv('outcome')} placeholder="Result of visit" />
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={saving ? 'Saving...' : 'Log Visitor'} type="submit" disabled={saving} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => setShowForm(false)} />
            </div>
          </form>
        </div>
      )}

      {tab === 'incidents' && !selected && (
        <>
          {/* Filters */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <input
                value={searchQ}
                onChange={e => setSearchQ(e.target.value)}
                placeholder="Search incidents..."
                style={{ width: '100%', background: isDark ? '#252525' : '#f5f5f5', border: `1px solid ${border}`, borderRadius: 7, padding: '8px 10px', color: text, fontSize: 12, boxSizing: 'border-box' }}
                onKeyDown={e => e.key === 'Enter' && loadIncidents()}
              />
            </div>
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              style={{ background: isDark ? '#252525' : '#f5f5f5', border: `1px solid ${border}`, borderRadius: 7, padding: '8px 12px', color: text, fontSize: 12 }}
            >
              <option value="">All statuses</option>
              <option value="open">Open</option>
              <option value="in_progress">In Progress</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>

          {loading ? (
            <div style={{ color: muted, textAlign: 'center', padding: 40 }}>Loading...</div>
          ) : incidents.length === 0 ? (
            <div style={{ color: muted, textAlign: 'center', padding: 40 }}>No incidents logged yet.</div>
          ) : (
            incidents.map(inc => (
              <div
                key={inc.id}
                onClick={() => openDetail(inc.id)}
                style={{
                  background: card, border: `1px solid ${border}`, borderRadius: 11, padding: 14, marginBottom: 10, cursor: 'pointer',
                  transition: 'border-color 0.12s',
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = '#4f8ff7'}
                onMouseLeave={e => e.currentTarget.style.borderColor = border}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: text, flex: 1, marginRight: 12 }}>
                    {inc.description?.slice(0, 80)}{inc.description?.length > 80 ? '…' : ''}
                  </span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <Badge label={inc.severity} color={SEVERITY_COLORS[inc.severity] || '#888'} />
                    <Badge label={inc.status} color={STATUS_COLORS[inc.status] || '#888'} />
                  </div>
                </div>
                <div style={{ fontSize: 11, color: muted }}>
                  {inc.created_at?.slice(0, 10)} · by {inc.logged_by_name || 'Unknown'}
                  {inc.thread?.length > 0 && <span style={{ marginLeft: 8 }}>· <MessageSquare size={10} style={{ display: 'inline', verticalAlign: 'middle' }} /> {inc.thread.length}</span>}
                </div>
              </div>
            ))
          )}
        </>
      )}

      {tab === 'incidents' && selected && (
        <div>
          <ActionBtn label="Back to list" variant="secondary" onClick={() => setSelected(null)} />
          <div style={{ marginTop: 16, background: card, border: `1px solid ${border}`, borderRadius: 11, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: text, margin: 0 }}>Incident Detail</h3>
              <div style={{ display: 'flex', gap: 6 }}>
                <Badge label={selected.severity} color={SEVERITY_COLORS[selected.severity] || '#888'} />
                <Badge label={selected.status} color={STATUS_COLORS[selected.status] || '#888'} />
              </div>
            </div>
            <p style={{ fontSize: 13, color: text, marginBottom: 8 }}>{selected.description}</p>
            {selected.involved_parties && <p style={{ fontSize: 12, color: muted }}>Parties: {selected.involved_parties}</p>}
            <p style={{ fontSize: 11, color: muted }}>Logged {selected.created_at?.slice(0, 16)} by {selected.logged_by_name}</p>

            {/* Thread */}
            <div style={{ marginTop: 16, borderTop: `1px solid ${border}`, paddingTop: 12 }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: muted, marginBottom: 8 }}>THREAD</p>
              {(selected.thread || []).length === 0 && <p style={{ color: muted, fontSize: 12 }}>No follow-ups yet.</p>}
              {(selected.thread || []).map(entry => (
                <div key={entry.id} style={{ padding: '8px 0', borderBottom: `1px solid ${border}` }}>
                  <div style={{ fontSize: 11, color: muted, marginBottom: 3 }}>
                    <strong style={{ color: isDark ? '#ccc' : '#555' }}>{entry.author_name}</strong> · {entry.timestamp?.slice(0, 16)}
                  </div>
                  <div style={{ fontSize: 12, color: text }}>{entry.content}</div>
                </div>
              ))}
              <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
                <textarea
                  value={threadMsg}
                  onChange={e => setThreadMsg(e.target.value)}
                  placeholder="Add a follow-up..."
                  rows={2}
                  style={{ flex: 1, background: isDark ? '#252525' : '#f5f5f5', border: `1px solid ${border}`, borderRadius: 7, padding: '8px 10px', color: text, fontSize: 12, resize: 'none' }}
                />
                <ActionBtn label="Post" onClick={addThread} disabled={!threadMsg.trim()} />
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'visitors' && (
        loading ? (
          <div style={{ color: muted, textAlign: 'center', padding: 40 }}>Loading...</div>
        ) : visitors.length === 0 ? (
          <div style={{ color: muted, textAlign: 'center', padding: 40 }}>No visitors logged today.</div>
        ) : (
          <DataTable
            headers={['Name', 'Purpose', 'Person Visited', 'Time In', 'Time Out', 'Outcome']}
            rows={visitors.map(v => [
              v.name,
              v.purpose || '—',
              v.student_or_staff_involved || '—',
              v.time_in?.slice(11, 16) || v.created_at?.slice(11, 16) || '—',
              v.time_out?.slice(11, 16) || '—',
              v.outcome || '—',
            ])}
          />
        )
      )}
    </ToolPage>
  );
}
