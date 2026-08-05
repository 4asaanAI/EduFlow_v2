import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle, Plus, RefreshCw, UserPlus } from 'lucide-react';
import { API, apiFetch } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';

const blank = { applicant_name: '', guardian_name: '', guardian_phone: '', class_id: '' };
const nextStage = { draft: 'submitted', submitted: 'under_review', offered: 'accepted' };

async function request(url, options = {}) {
  const response = await apiFetch(url, {
    ...options,
    headers: { ...getAuthHeaders(), ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'Admission action failed');
  return body;
}

export default function AdmissionsWorkflow({ compact = false }) {
  const [applications, setApplications] = useState([]);
  const [classes, setClasses] = useState([]);
  const [form, setForm] = useState(blank);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const [applicationBody, classBody] = await Promise.all([
        request(`${API}/admissions/applications`),
        request(`${API}/settings/classes`),
      ]);
      setApplications(applicationBody.data || []);
      setClasses(classBody.data || []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const counts = useMemo(() => applications.reduce((result, item) => {
    result[item.status] = (result[item.status] || 0) + 1;
    return result;
  }, {}), [applications]);

  async function act(id, action, body = {}) {
    setBusy(id);
    setError('');
    setNotice('');
    try {
      await request(`${API}/admissions/applications/${encodeURIComponent(id)}/${action}`, {
        method: action === 'status' ? 'PATCH' : 'POST', body: JSON.stringify(body),
      });
      setNotice('Admission workflow updated.');
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function create(event) {
    event.preventDefault();
    setBusy('new');
    setError('');
    try {
      await request(`${API}/admissions/applications`, { method: 'POST', body: JSON.stringify(form) });
      setForm(blank);
      setShowForm(false);
      setNotice('Application created as a draft.');
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy('');
    }
  }

  function issueOffer(application) {
    const valid = new Date();
    valid.setDate(valid.getDate() + 14);
    return act(application.id, 'offer', {
      class_id: application.class_id || classes[0]?.id,
      valid_until: valid.toISOString().slice(0, 10),
    });
  }

  return (
    <section aria-label="Applicant to student workflow" style={panel}>
      <div className="admissions-header">
        <div>
          <h3 style={title}><UserPlus size={16} />Applicant-to-student workflow</h3>
          <p style={hint}>Application review, offer, acceptance, and linked student enrollment.</p>
        </div>
        <div style={actions}>
          <button type="button" onClick={() => setShowForm(value => !value)} style={primary}><Plus size={13} />Application</button>
          <button type="button" onClick={load} style={icon} aria-label="Refresh applications"><RefreshCw size={14} /></button>
        </div>
      </div>
      {!compact && (
        <div className="admissions-stats">
          {['draft', 'submitted', 'under_review', 'offered', 'accepted', 'enrolled'].map(status => (
            <div key={status} style={stat}><strong>{counts[status] || 0}</strong><span>{status.replace('_', ' ')}</span></div>
          ))}
        </div>
      )}
      {error && <div role="alert" style={message('#f87171')}>{error}</div>}
      {notice && <div role="status" style={message('#34d399')}><CheckCircle size={13} />{notice}</div>}
      {showForm && (
        <form onSubmit={create} className="admissions-form responsive-form-grid">
          <input required value={form.applicant_name} onChange={e => setForm(v => ({ ...v, applicant_name: e.target.value }))} placeholder="Applicant name" style={input} />
          <input required value={form.guardian_name} onChange={e => setForm(v => ({ ...v, guardian_name: e.target.value }))} placeholder="Guardian name" style={input} />
          <input required value={form.guardian_phone} onChange={e => setForm(v => ({ ...v, guardian_phone: e.target.value }))} placeholder="Guardian phone" style={input} />
          <select required value={form.class_id} onChange={e => setForm(v => ({ ...v, class_id: e.target.value }))} style={input}>
            <option value="">Class applying</option>
            {classes.map(item => <option key={item.id} value={item.id} label={`${item.name || ''}${item.section ? ` - ${item.section}` : ''}`} />)}
          </select>
          <button type="submit" disabled={busy === 'new'} style={primary}>Save draft</button>
        </form>
      )}
      <div className="responsive-table-region" style={{ overflowX: 'auto' }}>
        <table style={table}>
          <thead><tr><th>Applicant</th><th>Class</th><th>Status</th><th>Next action</th></tr></thead>
          <tbody>
            {applications.map(application => (
              <tr key={application.id}>
                <td>{application.applicant_name}<small>{application.guardian_name || ''}</small></td>
                <td>{classes.find(item => item.id === application.class_id)?.name || application.class_applying || 'Not assigned'}</td>
                <td><span style={badge}>{application.status?.replace('_', ' ')}</span></td>
                <td><div style={actions}>
                  {nextStage[application.status] && <button type="button" disabled={busy === application.id} style={secondary} onClick={() => act(application.id, 'status', { status: nextStage[application.status] })}>Move to {nextStage[application.status].replace('_', ' ')}</button>}
                  {['under_review', 'assessed'].includes(application.status) && <button type="button" disabled={busy === application.id || !(application.class_id || classes[0]?.id)} style={secondary} onClick={() => issueOffer(application)}>Issue offer</button>}
                  {application.status === 'accepted' && <button type="button" disabled={busy === application.id} style={primary} onClick={() => act(application.id, 'enroll', {})}>Enroll student</button>}
                </div></td>
              </tr>
            ))}
            {!applications.length && <tr><td colSpan="4" style={{ textAlign: 'center', color: 'var(--c-faint)', padding: 20 }}>No applications yet</td></tr>}
          </tbody>
        </table>
      </div>
      <style>{`
        .admissions-header { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap; }
        .admissions-stats { display:grid; grid-template-columns:repeat(auto-fit, minmax(95px, 1fr)); gap:8px; margin:12px 0; }
        .admissions-form { display:grid; grid-template-columns:repeat(auto-fit, minmax(min(180px, 100%), 1fr)); gap:8px; margin:12px 0; align-items:start; }
        @media (max-width: 640px) { .admissions-header { flex-direction:column; } }
      `}</style>
    </section>
  );
}

const panel = { background: 'var(--c-bg, var(--color-bg-secondary))', border: '1px solid var(--c-border, var(--color-border))', borderRadius: 11, padding: 16, marginTop: 18 };
const title = { display: 'flex', alignItems: 'center', gap: 7, color: 'var(--c-text, var(--color-text-primary))', fontSize: 14, margin: 0 };
const hint = { color: 'var(--c-faint, var(--color-text-muted))', fontSize: 11, margin: '4px 0 0' };
const actions = { display: 'flex', flexWrap: 'wrap', gap: 7, alignItems: 'center' };
const input = { width: '100%', boxSizing: 'border-box', border: '1px solid var(--c-border, var(--color-border))', background: 'var(--c-deep, var(--color-bg-primary))', color: 'var(--c-text, var(--color-text-primary))', borderRadius: 7, padding: '8px 10px' };
const primary = { display: 'inline-flex', alignItems: 'center', gap: 5, border: 0, borderRadius: 7, padding: '8px 11px', background: 'var(--tool-hex-4f8ff7)', color: '#fff', cursor: 'pointer', fontSize: 11, fontWeight: 650 };
const secondary = { ...primary, background: 'transparent', color: 'var(--tool-hex-4f8ff7)', border: '1px solid color-mix(in srgb, var(--tool-hex-4f8ff7) 45%, transparent)' };
const icon = { ...secondary, padding: 8 };
const stat = { display: 'flex', flexDirection: 'column', gap: 2, border: '1px solid var(--c-border, var(--color-border))', borderRadius: 8, padding: 9, color: 'var(--c-text, var(--color-text-primary))', fontSize: 15 };
const message = color => ({ display: 'flex', gap: 6, alignItems: 'center', color, marginTop: 10, fontSize: 11 });
const table = { width: '100%', minWidth: 620, borderCollapse: 'collapse', color: 'var(--c-text, var(--color-text-primary))', fontSize: 12 };
const badge = { textTransform: 'capitalize', color: 'var(--tool-hex-93c5fd)', fontSize: 10 };
