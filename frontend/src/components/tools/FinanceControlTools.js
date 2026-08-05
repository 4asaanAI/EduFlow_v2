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
  if (!response.ok) throw new Error(body.detail || 'Financial operation failed');
  return body;
}

function downloadJson(data, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}

export function AccountingPeriods() {
  const [periods, setPeriods] = useState([]);
  const [form, setForm] = useState({ name: '', start_date: '', end_date: '' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    try { const body = await request(`${API}/accounting/periods`); setPeriods(body.data || []); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  async function create(event) {
    event.preventDefault();
    try { await request(`${API}/accounting/periods`, { method: 'POST', body: JSON.stringify(form) }); setForm({ name: '', start_date: '', end_date: '' }); await load(); }
    catch (err) { setError(err.message); }
  }
  async function change(item) {
    const status = item.status === 'open' ? 'closed' : 'open';
    const reason = status === 'open' ? window.prompt('Reason for reopening this period') : '';
    if (status === 'open' && !reason) return;
    try { await request(`${API}/accounting/periods/${item.id}/status`, { method: 'PATCH', body: JSON.stringify({ status, reason }) }); await load(); }
    catch (err) { setError(err.message); }
  }
  return <ToolPage title="Accounting Periods" subtitle="Control which dates accept financial postings" loading={loading} onRefresh={load}>
    {error && <ErrorText text={error} />}
    <form onSubmit={create} className="responsive-form-grid" style={formPanel}>
      <FormField label="Period name" value={form.name} onChange={value => setForm(item => ({ ...item, name: value }))} required />
      <FormField label="Starts" type="date" value={form.start_date} onChange={value => setForm(item => ({ ...item, start_date: value }))} required />
      <FormField label="Ends" type="date" value={form.end_date} onChange={value => setForm(item => ({ ...item, end_date: value }))} required />
      <div style={{ alignSelf: 'end' }}><ActionBtn label="Create period" type="submit" /></div>
    </form>
    <DataTable headers={['Period', 'Dates', 'Status', 'Control']}
      rows={periods.map(item => [item.name, `${item.start_date} to ${item.end_date}`, <Badge text={item.status} color={item.status === 'open' ? 'green' : 'red'} />, <ActionBtn label={item.status === 'open' ? 'Close' : 'Reopen'} variant={item.status === 'open' ? 'danger' : 'secondary'} onClick={() => change(item)} />])}
      emptyMsg="No accounting periods. Financial writes remain backward-compatible until the first period is created." />
  </ToolPage>;
}

export function PayrollManager() {
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState({ base_salary: '', allowances: '', deductions: '', status: '', reason: '' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    try { const body = await request(`${API}/payroll/disbursements`); setRows(body.data || []); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  function edit(row) {
    setSelected(row);
    setForm({ base_salary: row.base_salary, allowances: row.allowances, deductions: row.deductions, status: row.status, reason: '' });
  }
  async function payslip(row) {
    try { const body = await request(`${API}/payroll/disbursements/${row.id}/payslip`); downloadJson(body.data, `${body.data.payslip_number}.json`); }
    catch (err) { setError(err.message); }
  }
  async function correct(event) {
    event.preventDefault();
    const changes = { base_salary: Number(form.base_salary), allowances: Number(form.allowances), deductions: Number(form.deductions), status: form.status };
    try { await request(`${API}/payroll/disbursements/${selected.id}/correct`, { method: 'PATCH', body: JSON.stringify({ changes, reason: form.reason }) }); setSelected(null); await load(); }
    catch (err) { setError(err.message); }
  }
  return <ToolPage title="Payroll & Payslips" subtitle="Payslip generation and versioned payroll corrections" loading={loading} onRefresh={load}>
    {error && <ErrorText text={error} />}
    {selected && <form onSubmit={correct} className="responsive-form-grid" style={formPanel}>
      <FormField label="Base salary" type="number" value={form.base_salary} onChange={value => setForm(item => ({ ...item, base_salary: value }))} />
      <FormField label="Allowances" type="number" value={form.allowances} onChange={value => setForm(item => ({ ...item, allowances: value }))} />
      <FormField label="Deductions" type="number" value={form.deductions} onChange={value => setForm(item => ({ ...item, deductions: value }))} />
      <FormField label="Status" type="select" value={form.status} onChange={value => setForm(item => ({ ...item, status: value }))} options={['pending', 'paid', 'processed', 'reversed'].map(value => ({ value, label: value }))} />
      <FormField label="Correction reason" value={form.reason} onChange={value => setForm(item => ({ ...item, reason: value }))} required />
      <div style={{ alignSelf: 'end', display: 'flex', gap: 7 }}><ActionBtn label="Save correction" type="submit" /><ActionBtn label="Cancel" variant="secondary" onClick={() => setSelected(null)} /></div>
    </form>}
    <DataTable headers={['Staff', 'Month', 'Gross', 'Deductions', 'Net', 'Revision', 'Actions']}
      rows={rows.map(row => [row.staff_name || row.staff_id, row.month, Number(row.base_salary || 0) + Number(row.allowances || 0), row.deductions, row.net_amount, row.revision || 0, <div style={{ display: 'flex', gap: 6 }}><ActionBtn label="Payslip" onClick={() => payslip(row)} /><ActionBtn label="Correct" variant="secondary" onClick={() => edit(row)} /></div>])}
      emptyMsg="No payroll disbursements" />
  </ToolPage>;
}

export function MyPayslips() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    try { const body = await request(`${API}/payroll/my-disbursements`); setRows(body.data || []); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  async function download(row) {
    try { const body = await request(`${API}/payroll/disbursements/${row.id}/payslip`); downloadJson(body.data, `${body.data.payslip_number}.json`); }
    catch (err) { setError(err.message); }
  }
  return <ToolPage title="My Payslips" subtitle="Private salary disbursements and corrected payslip versions" loading={loading} onRefresh={load}>
    {error && <ErrorText text={error} />}
    <DataTable headers={['Month', 'Net amount', 'Status', 'Revision', 'Payslip']}
      rows={rows.map(row => [row.month, `Rs ${Number(row.net_amount || 0).toLocaleString('en-IN')}`, <Badge text={row.status} color={row.status === 'paid' || row.status === 'processed' ? 'green' : 'yellow'} />, row.revision || 0, <ActionBtn label="Download" onClick={() => download(row)} />])}
      emptyMsg="No payslips available" />
  </ToolPage>;
}

function ErrorText({ text }) { return <div role="alert" style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 12 }}>{text}</div>; }
const formPanel = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(170px, 100%), 1fr))', gap: 10, background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 14, marginBottom: 16 };
