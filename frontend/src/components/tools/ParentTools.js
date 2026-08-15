import React, { useCallback, useEffect, useState } from 'react';
import { API, apiFetch } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';
import { ActionBtn, Badge, DataTable, FormField, StatCard, ToolPage } from './ToolPage';
import SearchableSelect from '../ui/SearchableSelect';

async function request(url, options = {}) {
  const response = await apiFetch(url, {
    ...options,
    headers: { ...getAuthHeaders(), ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'Guardian portal request failed');
  return body;
}

export function GuardianPortal() {
  const [wards, setWards] = useState([]);
  const [studentId, setStudentId] = useState('');
  const [dashboard, setDashboard] = useState(null);
  const [leave, setLeave] = useState({ start_date: '', end_date: '', leave_type: 'planned', reason: '' });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const loadWards = useCallback(async () => {
    setLoading(true);
    try {
      const body = await request(`${API}/guardian/wards`);
      setWards(body.data || []);
      setStudentId(current => current || body.data?.[0]?.id || '');
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { loadWards(); }, [loadWards]);

  const loadDashboard = useCallback(async () => {
    if (!studentId) { setDashboard(null); return; }
    setLoading(true);
    try { const body = await request(`${API}/guardian/wards/${encodeURIComponent(studentId)}/dashboard`); setDashboard(body.data); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, [studentId]);
  useEffect(() => { loadDashboard(); }, [loadDashboard]);

  async function payOnline() {
    const transactionIds = (dashboard?.fees?.transactions || []).filter(item => ['pending', 'overdue', 'unpaid', 'partial'].includes(item.status)).map(item => item.id);
    if (!transactionIds.length) return;
    setBusy(true); setError('');
    try {
      const successUrl = window.location.protocol === 'https:' ? `${window.location.origin}/dashboard?tool=guardian-portal` : undefined;
      const body = await request(`${API}/fees/online-checkout`, { method: 'POST', body: JSON.stringify({ transaction_ids: transactionIds, ...(successUrl ? { success_url: successUrl } : {}) }) });
      window.open(body.data.checkout_url, '_blank', 'noopener,noreferrer');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function submitLeave(event) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      await request(`${API}/student-leave/requests`, { method: 'POST', body: JSON.stringify({ ...leave, student_id: studentId }) });
      setLeave({ start_date: '', end_date: '', leave_type: 'planned', reason: '' });
      setNotice('Student leave request submitted.'); await loadDashboard();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  const attendance = dashboard?.attendance?.last_30_days || {};
  const outstanding = dashboard?.fees?.summary?.total_outstanding ?? dashboard?.fees?.summary?.outstanding ?? 0;
  return <ToolPage title="Guardian Portal" subtitle="One protected view for each linked ward" loading={loading} onRefresh={loadDashboard}
    actions={<SearchableSelect aria-label="Select ward" value={studentId} onChange={event => setStudentId(event.target.value)} style={selectStyle}>{wards.map(ward => <option key={ward.id} value={ward.id} label={`${ward.name}${ward.admission_number ? ` (${ward.admission_number})` : ''}`} />)}</SearchableSelect>}>
    {error && <div role="alert" style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 10 }}>{error}</div>}
    {notice && <div role="status" style={{ color: 'var(--tool-hex-34d399)', fontSize: 12, marginBottom: 10 }}>{notice}</div>}
    {dashboard && <>
      <div className="responsive-stat-grid" style={stats}>
        <StatCard value={attendance.present || 0} label="PRESENT, 30 DAYS" color="var(--tool-hex-34d399)" />
        <StatCard value={attendance.absent || 0} label="ABSENT, 30 DAYS" color="var(--tool-hex-f87171)" />
        <StatCard value={`Rs ${Number(outstanding).toLocaleString('en-IN')}`} label="FEE OUTSTANDING" color="var(--tool-hex-fbbf24)" />
        <StatCard value={dashboard.assignments?.length || 0} label="ASSIGNMENTS" color="var(--tool-hex-4f8ff7)" />
      </div>
      {Number(outstanding) > 0 && <div style={{ marginBottom: 14 }}><ActionBtn label={busy ? 'Opening checkout...' : 'Pay school fees online'} onClick={payOnline} disabled={busy} /></div>}
      <div className="responsive-form-grid" style={twoColumns}>
        <form onSubmit={submitLeave} style={panel}>
          <h3 style={heading}>Request student leave</h3>
          <FormField label="Start" type="date" value={leave.start_date} onChange={value => setLeave(item => ({ ...item, start_date: value }))} required />
          <FormField label="End" type="date" value={leave.end_date} onChange={value => setLeave(item => ({ ...item, end_date: value }))} required />
          <FormField label="Reason" value={leave.reason} onChange={value => setLeave(item => ({ ...item, reason: value }))} required />
          <ActionBtn label="Submit leave" type="submit" disabled={busy} />
        </form>
        <div style={panel}><h3 style={heading}>Recent announcements</h3>{(dashboard.announcements || []).slice(0, 5).map(item => <div key={item.id} style={noticeRow}><strong>{item.title}</strong><span>{item.message || item.body}</span></div>)}{!dashboard.announcements?.length && <span style={empty}>No announcements</span>}</div>
      </div>
      <DataTable title="Results" headers={['Exam', 'Subject', 'Marks', 'Grade']} rows={(dashboard.results || []).map(item => [item.exam_name || item.exam_id, item.subject_name || item.subject_id, item.marks_obtained ?? item.marks, item.grade || '-'])} emptyMsg="No results published" />
      <DataTable title="Assignments" headers={['Assignment', 'Due', 'Status']} rows={(dashboard.assignments || []).map(item => [item.title, item.due_date || '-', <Badge text={item.status || 'assigned'} color="blue" />])} emptyMsg="No assignments" />
      <DataTable title="Library loans" headers={['Title', 'Issued', 'Due', 'Status']} rows={(dashboard.library_loans || []).map(item => [item.title, item.issued_at?.slice(0, 10), item.due_at?.slice(0, 10), <Badge text={item.status} color={item.status === 'returned' ? 'green' : 'yellow'} />])} emptyMsg="No library loans" />
      <DataTable title="Leave requests" headers={['Dates', 'Reason', 'Status']} rows={(dashboard.leave_requests || []).map(item => [`${item.start_date} to ${item.end_date}`, item.reason, <Badge text={item.status?.replace('_', ' ')} color={item.status === 'approved' ? 'green' : item.status === 'rejected' ? 'red' : 'yellow'} />])} emptyMsg="No leave requests" />
    </>}
  </ToolPage>;
}

const selectStyle = { background: 'var(--c-bg)', color: 'var(--c-text)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 10px', maxWidth: 240 };
const stats = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, marginBottom: 16 };
const twoColumns = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))', gap: 12, marginBottom: 16 };
const panel = { background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 14 };
const heading = { color: 'var(--c-text)', fontSize: 13, margin: '0 0 12px' };
const noticeRow = { display: 'flex', flexDirection: 'column', gap: 2, borderBottom: '1px solid var(--c-border)', padding: '8px 0', color: 'var(--c-muted)', fontSize: 11 };
const empty = { color: 'var(--c-faint)', fontSize: 11 };
