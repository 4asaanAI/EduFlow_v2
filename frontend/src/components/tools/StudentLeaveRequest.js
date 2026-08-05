import React, { useCallback, useEffect, useState } from 'react';
import { CalendarDays } from 'lucide-react';
import { API, apiFetch } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';
import { ActionBtn, Badge, DataTable, FormField, ToolPage } from './ToolPage';

const initial = { start_date: '', end_date: '', leave_type: 'planned', reason: '' };

async function request(url, options = {}) {
  const response = await apiFetch(url, {
    ...options,
    headers: { ...getAuthHeaders(), ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'Unable to update student leave');
  return body;
}

export default function StudentLeaveRequest() {
  const [policy, setPolicy] = useState(null);
  const [requests, setRequests] = useState([]);
  const [form, setForm] = useState(initial);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [policyBody, requestBody] = await Promise.all([
        request(`${API}/student-leave/policy`),
        request(`${API}/student-leave/requests`),
      ]);
      setPolicy(policyBody.data);
      setRequests(requestBody.data || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await request(`${API}/student-leave/requests`, { method: 'POST', body: JSON.stringify(form) });
      setForm(initial);
      setNotice('Leave request submitted for approval.');
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const field = name => value => setForm(current => ({ ...current, [name]: value }));
  return (
    <ToolPage title="Student Leave" subtitle="Request leave and follow its approval" loading={loading} onRefresh={load}>
      {policy && <div style={policyStyle}><CalendarDays size={15} />Up to {policy.maximum_consecutive_days} consecutive days. Principal approval is required above {policy.principal_approval_after_days} days.</div>}
      {error && <div role="alert" style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 10 }}>{error}</div>}
      {notice && <div role="status" style={{ color: 'var(--tool-hex-34d399)', fontSize: 12, marginBottom: 10 }}>{notice}</div>}
      <form onSubmit={submit} style={formStyle} className="responsive-form-grid">
        <FormField label="Start date" type="date" value={form.start_date} onChange={field('start_date')} required />
        <FormField label="End date" type="date" value={form.end_date} onChange={field('end_date')} required />
        <FormField label="Leave type" type="select" value={form.leave_type} onChange={field('leave_type')} options={[
          { value: 'planned', label: 'Planned' }, { value: 'medical', label: 'Medical' }, { value: 'other', label: 'Other' },
        ]} />
        <FormField label="Reason" value={form.reason} onChange={field('reason')} placeholder="Reason for absence" required />
        <div style={{ alignSelf: 'end' }}><ActionBtn label={saving ? 'Submitting...' : 'Submit request'} disabled={saving} /></div>
      </form>
      <DataTable headers={['Dates', 'Days', 'Type', 'Status', 'Latest decision']}
        rows={requests.map(item => [
          `${item.start_date} to ${item.end_date}`, item.days, item.leave_type,
          <Badge text={item.status?.replace('_', ' ')} color={item.status === 'approved' ? 'green' : item.status === 'rejected' ? 'red' : 'yellow'} />,
          item.decisions?.at(-1)?.note || item.decisions?.at(-1)?.role || 'Awaiting review',
        ])}
        emptyMsg="No student leave requests"
      />
    </ToolPage>
  );
}

const policyStyle = { display: 'flex', alignItems: 'center', gap: 7, background: 'color-mix(in srgb, var(--tool-hex-4f8ff7) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--tool-hex-4f8ff7) 25%, transparent)', color: 'var(--tool-hex-93c5fd)', borderRadius: 8, padding: 10, marginBottom: 14, fontSize: 11 };
const formStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(180px, 100%), 1fr))', gap: 10, alignItems: 'start', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 14, marginBottom: 16 };
