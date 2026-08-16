import React, { useCallback, useEffect, useState } from 'react';
import { API, apiFetch } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';
import { ActionBtn, Badge, DataTable, FormField, ToolPage } from './ToolPage';

async function request(url, options = {}) {
  const response = await apiFetch(url, {
    ...options,
    headers: { ...getAuthHeaders(), ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Couldn't update student leave");
  return body;
}

export default function StudentLeaveManager() {
  const [requests, setRequests] = useState([]);
  const [policy, setPolicy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [requestBody, policyBody] = await Promise.all([
        request(`${API}/student-leave/requests`), request(`${API}/student-leave/policy`),
      ]);
      setRequests(requestBody.data || []);
      setPolicy(policyBody.data);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function decide(id, decision) {
    const note = decision === 'reject' ? window.prompt('Reason for rejection') : '';
    if (decision === 'reject' && !note) return;
    setSaving(true);
    try {
      await request(`${API}/student-leave/requests/${encodeURIComponent(id)}/decision`, {
        method: 'PATCH', body: JSON.stringify({ decision, note }),
      });
      await load();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  async function savePolicy(event) {
    event.preventDefault();
    setSaving(true);
    try {
      const body = await request(`${API}/student-leave/policy`, {
        method: 'PUT', body: JSON.stringify(policy),
      });
      setPolicy(body.data);
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  return (
    <ToolPage title="Student Leave Manager" subtitle="Policy-controlled class teacher and principal approvals" loading={loading} onRefresh={load}>
      {error && <div role="alert" style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 12 }}>{error}</div>}
      {policy && <form onSubmit={savePolicy} className="responsive-form-grid" style={policyPanel}>
        <FormField label="Principal approval above (days)" type="number" value={policy.principal_approval_after_days} onChange={value => setPolicy(item => ({ ...item, principal_approval_after_days: Number(value) }))} />
        <FormField label="Maximum consecutive days" type="number" value={policy.maximum_consecutive_days} onChange={value => setPolicy(item => ({ ...item, maximum_consecutive_days: Number(value) }))} />
        <label style={checkLabel}><input type="checkbox" checked={policy.teacher_approval_required} onChange={event => setPolicy(item => ({ ...item, teacher_approval_required: event.target.checked }))} />Require class teacher approval</label>
        <div style={{ alignSelf: 'end' }}><ActionBtn label="Save policy" disabled={saving} /></div>
      </form>}
      <DataTable headers={['Student', 'Dates', 'Days', 'Reason', 'Status', 'Decision']}
        rows={requests.map(item => [
          item.student_name || item.student_id, `${item.start_date} to ${item.end_date}`, item.days,
          item.reason, <Badge text={item.status?.replace('_', ' ')} color={item.status === 'approved' ? 'green' : item.status === 'rejected' ? 'red' : 'yellow'} />,
          item.status?.startsWith('pending') ? <div style={{ display: 'flex', gap: 6 }}><ActionBtn label="Approve" onClick={() => decide(item.id, 'approve')} disabled={saving} /><ActionBtn label="Reject" variant="danger" onClick={() => decide(item.id, 'reject')} disabled={saving} /></div> : 'Completed',
        ])}
        emptyMsg="No student leave requests"
      />
    </ToolPage>
  );
}

const policyPanel = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(190px, 100%), 1fr))', gap: 10, background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 14, marginBottom: 16 };
const checkLabel = { display: 'flex', alignItems: 'center', gap: 7, color: 'var(--c-muted)', fontSize: 12, alignSelf: 'center' };
