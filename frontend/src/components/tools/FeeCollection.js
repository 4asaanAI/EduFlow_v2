import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle, Edit3, Percent, Phone, RefreshCw, Save, FileDown, MessageSquare, Trash2, X } from 'lucide-react';
import { getAuthHeaders } from '../../lib/authSession';
import { useUser } from '../../contexts/UserContext';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

async function downloadReceipt(transactionId) {
  if (!transactionId) {
    alert('Receipt is unavailable for this record');
    return;
  }
  try {
    const res = await fetch(
      `${API}/fees/transactions/${encodeURIComponent(transactionId)}/receipt?format=json`,
      { headers: getAuthHeaders() }
    );
    if (!res.ok) throw new Error('Receipt not available');
    const data = await res.json();
    const receipt = data.data;
    const blob = new Blob([JSON.stringify(receipt, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error('Receipt download failed:', err);
    alert('Receipt generation failed');
  }
}

async function exportFeeCSV(period) {
  const params = period ? `?period=${period}` : '';
  const res = await fetch(`${API}/fees/export${params}`, { headers: getAuthHeaders() });
  if (!res.ok) { alert('Export failed'); return; }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `fees-export.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
import {
  apiFetch,
  correctFeeTransaction,
  deleteFeeTransaction,
  createFeeContactLog,
  createDiscountType,
  getDiscountSummary,
  getDiscountTypes,
  getFeeDiscounts,
  getFeeSummary,
  getFeeTransactions,
  getStudents,
  getWhatsappDefaulters,
  listPayrollDisbursements,
  recordFeePayment,
  sendFeeReminders,
  subscribeSSE,
} from '../../lib/api';

const today = new Date().toISOString().slice(0, 10);
const initialPayment = { student_id: '', fee_period: '', fee_head: 'tuition', amount: '', paid_amount: '', payment_mode: 'upi', status: 'paid', due_date: today, transaction_ref: '' };
const initialCorrection = { transaction_id: '', amount: '', status: '', reason: '' };
const initialContact = { fee_transaction_id: '', student_id: '', contact_type: 'call', outcome: '', notes: '', date: today };
const initialDiscountType = { name: '', value: '', value_type: 'percentage', recurrence: 'per-term', reason_note: '' };
const initialDiscountApply = { student_id: '', discount_type_id: '', original_amount: '', effective_from: today, note: '' };

function money(value) {
  return `Rs ${Number(value || 0).toLocaleString('en-IN')}`;
}

function lastUpdatedLabel(value) {
  if (!value) return 'Waiting for live updates';
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 5) return 'Updated just now';
  if (seconds < 60) return `Updated ${seconds}s ago`;
  return `Updated ${Math.floor(seconds / 60)}m ago`;
}

export default function FeeCollection() {
  const { currentUser } = useUser();
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [students, setStudents] = useState([]);
  const [overdueDays, setOverdueDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [payment, setPayment] = useState(initialPayment);
  const [correction, setCorrection] = useState(initialCorrection);
  const [contact, setContact] = useState(initialContact);
  const [overdueList, setOverdueList] = useState([]);
  const [discountTypes, setDiscountTypes] = useState([]);
  const [discountSummary, setDiscountSummary] = useState(null);
  const [discountBreakdown, setDiscountBreakdown] = useState(null);
  const [discountTypeForm, setDiscountTypeForm] = useState(initialDiscountType);
  const [discountApply, setDiscountApply] = useState(initialDiscountApply);
  const [feeStreamUpdatedAt, setFeeStreamUpdatedAt] = useState(null);
  const [, setClockTick] = useState(0);
  const liveUpdateLabel = lastUpdatedLabel(feeStreamUpdatedAt || summary?.generated_at);

  // Overdue edit/delete state
  const [overdueEditTxn, setOverdueEditTxn] = useState(null);
  const [overdueEditForm, setOverdueEditForm] = useState({ amount: '', status: '', payment_mode: '', due_date: '', transaction_ref: '', reason: '' });
  const [overdueDeleteId, setOverdueDeleteId] = useState(null);
  const [overdueActionError, setOverdueActionError] = useState('');

  // Payroll state
  const [disbursements, setDisbursements] = useState([]);
  const [loadingPayroll, setLoadingPayroll] = useState(false);

  // Pending discount approvals (owner only)
  const [pendingApprovals, setPendingApprovals] = useState([]);

  // WhatsApp fee reminders
  const [waDefaulters, setWaDefaulters] = useState(null);
  const [waLoading, setWaLoading] = useState(false);
  const [waSending, setWaSending] = useState(false);

  const fetchPayroll = useCallback(async () => {
    setLoadingPayroll(true);
    try {
      const data = await listPayrollDisbursements();
      setDisbursements(data.data || []);
    } catch (e) {
      console.error('Payroll load error:', e);
    } finally {
      setLoadingPayroll(false);
    }
  }, []);

  useEffect(() => { fetchPayroll(); }, [fetchPayroll]);

  const loadPendingApprovals = useCallback(async () => {
    if (currentUser?.role !== 'owner') return;
    try {
      const res = await apiFetch(`${API}/fees/discounts/pending-approvals`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setPendingApprovals(data.data || []);
      }
    } catch (e) {
      console.error('Failed to load pending approvals:', e);
    }
  }, [currentUser?.role]);

  useEffect(() => { loadPendingApprovals(); }, [loadPendingApprovals]);

  async function approveDiscount(id) {
    try {
      const res = await apiFetch(`${API}/fees/discounts/pending-approvals/${id}/approve`, {
        method: 'PATCH', headers: getAuthHeaders(),
      });
      if (res.ok) { setNotice('Discount approved.'); loadPendingApprovals(); }
      else { const d = await res.json(); setError(d.detail || 'Failed to approve discount'); }
    } catch { setError('Failed to approve discount'); }
  }

  async function rejectDiscount(id) {
    try {
      const res = await apiFetch(`${API}/fees/discounts/pending-approvals/${id}/reject`, {
        method: 'PATCH', headers: getAuthHeaders(),
      });
      if (res.ok) { setNotice('Discount rejected.'); loadPendingApprovals(); }
      else { const d = await res.json(); setError(d.detail || 'Failed to reject discount'); }
    } catch { setError('Failed to reject discount'); }
  }

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [summaryRes, txnRes, overdueRes, studentRes, discountTypesRes, discountSummaryRes] = await Promise.all([
        getFeeSummary(payment.fee_period ? { fee_period: payment.fee_period } : {}),
        getFeeTransactions(null, {}),
        getFeeTransactions(null, { overdue_days: overdueDays }),
        getStudents(null, { limit: 500 }),
        getDiscountTypes(),
        getDiscountSummary(),
      ]);
      if (!summaryRes.success) throw new Error(summaryRes.detail || 'Unable to load fee summary');
      if (!txnRes.success) throw new Error(txnRes.detail || 'Unable to load fee transactions');
      setSummary(summaryRes.data);
      setTransactions(txnRes.data || []);
      setStudents(studentRes.data || []);
      setOverdueList(overdueRes.data || []);
      setDiscountTypes(discountTypesRes.data || []);
      if (discountSummaryRes.success) setDiscountSummary(discountSummaryRes.data);
    } catch (err) {
      setError(err.message || 'Unable to load fee data. Check whether the last payment was partially written before retrying.');
    } finally {
      setLoading(false);
    }
  }, [payment.fee_period, overdueDays]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    const interval = setInterval(() => setClockTick(t => t + 1), 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => subscribeSSE('/fees/stream', (event) => {
    if (event.type === 'snapshot' || event.type === 'fee_payment_recorded' || event.type === 'fee_transaction_corrected' || event.type === 'fee_transaction_deleted' || event.type === 'fee_sync_completed' || event.type === 'fee_sync_conflict_resolved') {
      if (event.summary) setSummary(event.summary);
      setFeeStreamUpdatedAt(event.last_updated || new Date().toISOString());
      if (event.type !== 'snapshot') loadData();
    }
  }, { onReconnect: loadData }), [loadData]);

  const selectedTxn = useMemo(() => transactions.find(t => t.id === correction.transaction_id), [transactions, correction.transaction_id]);
  const overdue = overdueList;

  async function savePayment() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      if (!payment.student_id || !payment.fee_period || !payment.fee_head || !payment.amount) {
        throw new Error('Student, period, fee head, and amount are required.');
      }
      const key = `${payment.student_id}|${payment.fee_period}|${(payment.fee_head || '').trim().toLowerCase()}`;
      const payload = { ...payment, amount: Number(payment.amount), fee_type: payment.fee_head };
      if (payment.paid_amount) payload.paid_amount = Number(payment.paid_amount);
      const res = await recordFeePayment(null, payload, key);
      if (!res.success) throw new Error(res.detail || 'Payment could not be saved');

      // Auto-close matching overdue transactions for this student + fee head
      if (payment.status === 'paid' || payment.status === 'partial') {
        const matchingOverdue = overdueList.filter(
          txn => txn.student_id === payment.student_id &&
                 (txn.fee_head === payment.fee_head || txn.fee_type === payment.fee_head)
        );
        for (const txn of matchingOverdue) {
          try {
            await correctFeeTransaction(txn.id, {
              reason: 'Auto-closed: payment recorded',
              status: payment.status === 'partial' ? 'partial' : 'paid',
            });
          } catch {}
        }
      }

      setNotice(res.idempotent ? 'Duplicate submission recovered. Original payment returned.' : 'Payment saved.');
      setPayment(initialPayment);
      await loadData();
    } catch (err) {
      setError(err.message || 'Payment could not be saved. If the network dropped, refresh before retrying to avoid duplicates.');
    } finally {
      setSaving(false);
    }
  }

  async function saveCorrection() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      if (!correction.transaction_id || !correction.reason.trim()) {
        throw new Error('Select a transaction and enter a correction reason.');
      }
      const payload = { reason: correction.reason.trim() };
      if (correction.amount) payload.amount = Number(correction.amount);
      if (correction.status) payload.status = correction.status;
      const res = await correctFeeTransaction(correction.transaction_id, payload);
      if (!res.success) throw new Error(res.detail || 'Correction could not be saved');
      setCorrection(initialCorrection);
      setNotice('Fee correction saved with audit trail.');
      await loadData();
    } catch (err) {
      setError(err.message || 'Correction could not be saved.');
    } finally {
      setSaving(false);
    }
  }

  async function saveContact() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      if (!contact.fee_transaction_id || !contact.student_id || !contact.outcome || !contact.notes) {
        throw new Error('Contact log requires a fee record, outcome, and notes.');
      }
      const res = await createFeeContactLog(contact);
      if (!res.success) throw new Error(res.detail || 'Contact log could not be saved');
      setContact(initialContact);
      setNotice('Contact event logged.');
      await loadData();
    } catch (err) {
      setError(err.message || 'Contact log could not be saved.');
    } finally {
      setSaving(false);
    }
  }

  async function saveDiscountType() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      if (!discountTypeForm.name || !discountTypeForm.value || !discountTypeForm.reason_note) {
        throw new Error('Discount type requires name, value, and reason note.');
      }
      const res = await createDiscountType({ ...discountTypeForm, value: Number(discountTypeForm.value) });
      if (!res.success) throw new Error(res.detail || 'Discount type could not be saved');
      setDiscountTypeForm(initialDiscountType);
      setNotice('Discount type saved.');
      await loadData();
    } catch (err) {
      setError(err.message || 'Discount type could not be saved.');
    } finally {
      setSaving(false);
    }
  }

  async function applyDiscount() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      if (!discountApply.student_id || !discountApply.discount_type_id || !discountApply.original_amount) {
        throw new Error('Discount application requires student, discount type, and original amount.');
      }
      const res = await apiFetch(`${API}/fees/discounts/apply`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...discountApply, original_amount: Number(discountApply.original_amount) }),
      });
      if (res.status === 202) {
        const data = await res.json();
        setNotice(`Discount requires owner approval: ${data.message || 'Pending approval'}`);
        loadPendingApprovals();
        return;
      }
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Discount could not be applied');
      }
      const json = await res.json();
      if (!json.success) throw new Error(json.detail || 'Discount could not be applied');
      setDiscountApply(initialDiscountApply);
      setNotice('Discount applied.');
      await loadData();
      await loadDiscountBreakdown(json.data.student_id);
    } catch (err) {
      setError(err.message || 'Discount could not be applied.');
    } finally {
      setSaving(false);
    }
  }

  async function loadDiscountBreakdown(studentId) {
    setError('');
    try {
      const res = await getFeeDiscounts(studentId);
      if (!res.success) throw new Error(res.detail || 'Discount breakdown could not be loaded');
      setDiscountBreakdown(res.data);
    } catch (err) {
      setError(err.message || 'Discount breakdown could not be loaded.');
    }
  }

  async function loadWaDefaulters() {
    setWaLoading(true);
    try {
      const res = await getWhatsappDefaulters();
      if (res.success) setWaDefaulters(res.data);
      else setError(res.detail || 'Could not load defaulters');
    } catch (e) {
      setError('WhatsApp defaulters load failed');
    } finally {
      setWaLoading(false);
    }
  }

  function openOverdueEdit(txn) {
    setOverdueEditTxn(txn);
    setOverdueEditForm({
      amount: txn.amount || '',
      status: txn.status || '',
      payment_mode: txn.payment_mode || '',
      due_date: txn.due_date || '',
      transaction_ref: txn.transaction_ref || '',
      reason: '',
    });
    setOverdueActionError('');
  }

  async function saveOverdueEdit() {
    if (!overdueEditForm.reason.trim()) { setOverdueActionError('Reason is required.'); return; }
    setSaving(true);
    setOverdueActionError('');
    try {
      const payload = { reason: overdueEditForm.reason.trim() };
      if (overdueEditForm.amount !== '' && String(overdueEditForm.amount) !== String(overdueEditTxn.amount)) payload.amount = Number(overdueEditForm.amount);
      if (overdueEditForm.status && overdueEditForm.status !== overdueEditTxn.status) payload.status = overdueEditForm.status;
      if (overdueEditForm.payment_mode && overdueEditForm.payment_mode !== overdueEditTxn.payment_mode) payload.payment_mode = overdueEditForm.payment_mode;
      if (overdueEditForm.due_date && overdueEditForm.due_date !== overdueEditTxn.due_date) payload.due_date = overdueEditForm.due_date;
      if (overdueEditForm.transaction_ref !== overdueEditTxn.transaction_ref) payload.transaction_ref = overdueEditForm.transaction_ref;
      const res = await correctFeeTransaction(overdueEditTxn.id, payload);
      if (!res.success) { setOverdueActionError(res.detail || 'Failed to save changes'); return; }
      setOverdueEditTxn(null);
      setNotice('Record updated.');
      await loadData();
    } catch (err) {
      setOverdueActionError(err.message || 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  }

  async function deleteOverdueTxn(id) {
    setSaving(true);
    setOverdueActionError('');
    try {
      const res = await deleteFeeTransaction(id);
      if (!res.success) { setOverdueActionError(res.detail || 'Failed to delete record'); return; }
      setOverdueDeleteId(null);
      setNotice('Record deleted. Totals updated.');
      await loadData();
    } catch (err) {
      setOverdueActionError(err.message || 'Failed to delete record');
    } finally {
      setSaving(false);
    }
  }

  async function sendFeeWaReminders() {
    if (!waDefaulters?.fee_defaulters?.length) return;
    setWaSending(true);
    try {
      const res = await sendFeeReminders(waDefaulters.fee_defaulters);
      if (res.success) {
        const { sent, failed, not_configured } = res.data;
        setNotice(`WhatsApp sent: ${sent}, failed: ${failed}, not configured: ${not_configured}`);
        setWaDefaulters(null);
      } else {
        setError(res.detail || 'Send failed');
      }
    } catch (e) {
      setError('Failed to send WhatsApp reminders');
    } finally {
      setWaSending(false);
    }
  }

  return (
    <div data-testid="fee-collection-tool" style={{ padding: '20px 16px', overflowY: 'auto', height: '100%', position: 'relative' }}>
      {saving && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 9999,
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 12,
        }}>
          <div style={{
            width: 44, height: 44, border: '4px solid rgba(79,143,247,0.25)', borderTopColor: '#4f8ff7',
            borderRadius: '50%', animation: 'spin 0.7s linear infinite',
          }} />
          <div style={{ color: '#fff', fontSize: 13, fontWeight: 600 }}>Saving…</div>
        </div>
      )}
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 640px) {
          .fee-twocol { grid-template-columns: 1fr !important; }
          .fee-header { padding: 12px !important; }
          .fee-section-grid { grid-template-columns: 1fr !important; }
          .fee-txn-table { font-size: 11px !important; }
          .fee-txn-table th, .fee-txn-table td { padding: 6px 8px !important; }
          .fee-stat-grid { grid-template-columns: repeat(2, 1fr) !important; }
        }
        @media (max-width: 400px) {
          .fee-stat-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', marginBottom: 20, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 650, margin: 0, color: 'var(--color-text-primary)' }}>Fee collection</h1>
          <p style={{ margin: '6px 0 0', color: 'var(--color-text-muted)', fontSize: 12 }}>Payments, corrections, defaulters, and contact recovery</p>
          <p style={{ margin: '4px 0 0', color: 'var(--color-text-secondary)', fontSize: 11 }}>{liveUpdateLabel}</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => exportFeeCSV('')} title="Export all fees as CSV" style={iconButton}>
            <FileDown size={16} />
          </button>
          <button onClick={loadData} disabled={loading} title="Refresh fee data" style={iconButton}>
            <RefreshCw size={16} style={loading ? { animation: 'spin 0.8s linear infinite' } : {}} />
          </button>
        </div>
      </div>

      {error && <div role="alert" style={alertStyle('var(--tool-hex-f87171)')}><AlertTriangle size={16} />{error}</div>}
      {notice && <div style={alertStyle('var(--tool-hex-34d399)')}><CheckCircle size={16} />{notice}</div>}

      <div className="fee-stat-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 18 }}>
        {[
          ['Collected', money(summary?.total_collected), 'var(--tool-hex-34d399)'],
          ['Outstanding', money(summary?.total_outstanding), 'var(--tool-hex-f87171)'],
          ['Collection Rate', summary?.collection_rate || '0%', 'var(--tool-hex-4f8ff7)'],
          ['Defaulters', summary?.defaulters || 0, 'var(--tool-hex-fbbf24)'],
          ['Discounts', money(discountSummary?.total_discount_value), 'var(--tool-hex-a78bfa)'],
        ].map(([label, value, color]) => (
          <div key={label} style={panelStyle}>
            <div style={{ color, fontSize: 20, fontWeight: 750 }}>{value}</div>
            <div style={{ color: 'var(--color-text-muted)', fontSize: 10, fontWeight: 700, textTransform: 'uppercase' }}>{label}</div>
          </div>
        ))}
      </div>

      <div className="fee-section-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14, marginBottom: 18 }}>
        <section style={panelStyle}>
          <h2 style={panelTitle}><Save size={16} />Record payment</h2>
          <select value={payment.student_id} onChange={e => setPayment(prev => ({ ...prev, student_id: e.target.value }))} style={inputStyle}>
            <option value="">Select student</option>
            {students.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <div style={twoCol}>
            <input value={payment.fee_period} onChange={e => setPayment(prev => ({ ...prev, fee_period: e.target.value }))} placeholder="2026-05" style={inputStyle} />
            <input value={payment.fee_head} onChange={e => setPayment(prev => ({ ...prev, fee_head: e.target.value }))} placeholder="tuition" style={inputStyle} />
          </div>
          <div style={twoCol}>
            <input value={payment.amount} onChange={e => setPayment(prev => ({ ...prev, amount: e.target.value }))} placeholder="Amount" type="number" style={inputStyle} />
            <select value={payment.payment_mode} onChange={e => setPayment(prev => ({ ...prev, payment_mode: e.target.value }))} style={inputStyle}>
              <option value="upi">UPI</option>
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank transfer</option>
              <option value="card">Card</option>
            </select>
          </div>
          <div style={twoCol}>
            <select value={payment.status} onChange={e => setPayment(prev => ({ ...prev, status: e.target.value, paid_amount: e.target.value !== 'partial' ? '' : prev.paid_amount }))} style={inputStyle}>
              <option value="paid">Full payment</option>
              <option value="partial">Partial payment</option>
              <option value="pending">Pending</option>
            </select>
            {payment.status === 'partial' && (
              <input value={payment.paid_amount} onChange={e => setPayment(prev => ({ ...prev, paid_amount: e.target.value }))} placeholder="Partial amount" type="number" style={inputStyle} />
            )}
          </div>
          <input value={payment.transaction_ref} onChange={e => setPayment(prev => ({ ...prev, transaction_ref: e.target.value }))} placeholder="Transaction reference" style={inputStyle} />
          <button onClick={savePayment} disabled={saving} style={primaryButton('var(--tool-hex-4f8ff7)')}>Save payment</button>
        </section>

        <section style={panelStyle}>
          <h2 style={panelTitle}><Edit3 size={16} />Correct record</h2>
          <select value={correction.transaction_id} onChange={e => setCorrection(prev => ({ ...prev, transaction_id: e.target.value }))} style={inputStyle}>
            <option value="">Select transaction</option>
            {transactions.map(t => <option key={t.id} value={t.id}>{t.student_name || t.student_id} - {t.fee_type} - {money(t.amount)}</option>)}
          </select>
          {selectedTxn && <div style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>Current: {selectedTxn.status} / {money(selectedTxn.amount)}</div>}
          <div style={twoCol}>
            <input value={correction.amount} onChange={e => setCorrection(prev => ({ ...prev, amount: e.target.value }))} placeholder="Corrected amount" type="number" style={inputStyle} />
            <select value={correction.status} onChange={e => setCorrection(prev => ({ ...prev, status: e.target.value }))} style={inputStyle}>
              <option value="">Keep status</option>
              <option value="paid">Paid</option>
              <option value="pending">Pending</option>
              <option value="overdue">Overdue</option>
            </select>
          </div>
          <textarea value={correction.reason} onChange={e => setCorrection(prev => ({ ...prev, reason: e.target.value }))} placeholder="Reason required" style={textareaStyle} />
          <button onClick={saveCorrection} disabled={saving} style={primaryButton('var(--tool-hex-6366f1)')}>Save correction</button>
        </section>

        <section style={panelStyle}>
          <h2 style={panelTitle}><Phone size={16} />Contact log</h2>
          <select value={contact.fee_transaction_id} onChange={e => {
            const txn = transactions.find(t => t.id === e.target.value);
            setContact(prev => ({ ...prev, fee_transaction_id: e.target.value, student_id: txn?.student_id || prev.student_id }));
          }} style={inputStyle}>
            <option value="">Select fee record</option>
            {transactions.map(t => <option key={t.id} value={t.id}>{t.student_name || t.student_id} - {t.status}</option>)}
          </select>
          <div style={twoCol}>
            <input value={contact.date} onChange={e => setContact(prev => ({ ...prev, date: e.target.value }))} type="date" style={inputStyle} />
            <select value={contact.contact_type} onChange={e => setContact(prev => ({ ...prev, contact_type: e.target.value }))} style={inputStyle}>
              <option value="call">Call</option>
              <option value="message">Message</option>
              <option value="visit">Visit</option>
            </select>
          </div>
          <input value={contact.outcome} onChange={e => setContact(prev => ({ ...prev, outcome: e.target.value }))} placeholder="Outcome" style={inputStyle} />
          <textarea value={contact.notes} onChange={e => setContact(prev => ({ ...prev, notes: e.target.value }))} placeholder="Notes" style={textareaStyle} />
          <button onClick={saveContact} disabled={saving} style={primaryButton('var(--tool-hex-10b981)')}>Log contact</button>
        </section>
      </div>

      <div className="fee-section-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14, marginBottom: 18 }}>
        <section style={panelStyle}>
          <h2 style={panelTitle}><Percent size={16} />Discount type</h2>
          <input value={discountTypeForm.name} onChange={e => setDiscountTypeForm(prev => ({ ...prev, name: e.target.value }))} placeholder="Discount name" style={inputStyle} />
          <div style={twoCol}>
            <input value={discountTypeForm.value} onChange={e => setDiscountTypeForm(prev => ({ ...prev, value: e.target.value }))} placeholder="Value" type="number" style={inputStyle} />
            <select value={discountTypeForm.value_type} onChange={e => setDiscountTypeForm(prev => ({ ...prev, value_type: e.target.value }))} style={inputStyle}>
              <option value="percentage">Percentage</option>
              <option value="flat">Flat</option>
            </select>
          </div>
          <select value={discountTypeForm.recurrence} onChange={e => setDiscountTypeForm(prev => ({ ...prev, recurrence: e.target.value }))} style={inputStyle}>
            <option value="one-time">One-time</option>
            <option value="per-term">Per-term</option>
          </select>
          <textarea value={discountTypeForm.reason_note} onChange={e => setDiscountTypeForm(prev => ({ ...prev, reason_note: e.target.value }))} placeholder="Reason note" style={textareaStyle} />
          <button onClick={saveDiscountType} disabled={saving} style={primaryButton('var(--tool-hex-a78bfa)')}>Save discount type</button>
        </section>

        <section style={panelStyle}>
          <h2 style={panelTitle}>Apply discount</h2>
          <select value={discountApply.student_id} onChange={e => {
            setDiscountApply(prev => ({ ...prev, student_id: e.target.value }));
            if (e.target.value) loadDiscountBreakdown(e.target.value);
          }} style={inputStyle}>
            <option value="">Select student</option>
            {students.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select value={discountApply.discount_type_id} onChange={e => setDiscountApply(prev => ({ ...prev, discount_type_id: e.target.value }))} style={inputStyle}>
            <option value="">Select discount type</option>
            {discountTypes.map(d => <option key={d.id} value={d.id}>{d.name} - {d.value_type === 'percentage' ? `${d.value}%` : money(d.value)}</option>)}
          </select>
          <div style={twoCol}>
            <input value={discountApply.original_amount} onChange={e => setDiscountApply(prev => ({ ...prev, original_amount: e.target.value }))} placeholder="Original amount" type="number" style={inputStyle} />
            <input value={discountApply.effective_from} onChange={e => setDiscountApply(prev => ({ ...prev, effective_from: e.target.value }))} type="date" style={inputStyle} />
          </div>
          <input value={discountApply.note} onChange={e => setDiscountApply(prev => ({ ...prev, note: e.target.value }))} placeholder="Approval note" style={inputStyle} />
          <button onClick={applyDiscount} disabled={saving} style={primaryButton('var(--tool-hex-8b5cf6)')}>Apply discount</button>
        </section>

        <section style={panelStyle}>
          <h2 style={panelTitle}>Discount breakdown</h2>
          {!discountBreakdown ? (
            <div style={emptyStyle}>Select a student to view payable calculation.</div>
          ) : (
            <div>
              <div style={lineItem}><span>Original</span><strong>{money(discountBreakdown.original_amount)}</strong></div>
              {(discountBreakdown.discounts || []).map(item => (
                <div key={item.application_id} style={lineItem}>
                  <span>{item.label} ({item.value_type === 'percentage' ? `${item.value}%` : money(item.value)})</span>
                  <strong>-{money(item.discount_amount)}</strong>
                </div>
              ))}
              <div style={{ ...lineItem, borderTop: '1px solid var(--color-border)', paddingTop: 10, color: 'var(--tool-hex-34d399)' }}>
                <span>Payable</span><strong>{money(discountBreakdown.payable_amount)}</strong>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Payroll Disbursements */}
      <div style={panelStyle}>
        <h2 style={panelTitle}>Payroll — This Month</h2>
        {loadingPayroll ? (
          <div style={emptyStyle}>Loading payroll...</div>
        ) : disbursements.length === 0 ? (
          <div style={emptyStyle}>No disbursements recorded this month.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
        <table className="fee-txn-table" style={{ width: '100%', borderCollapse: 'collapse', minWidth: 400 }}>
            <thead>
              <tr>
                {['Staff', 'Month', 'Gross', 'Net', 'Status'].map(h => (
                  <th key={h} style={thStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {disbursements.map((d, index) => (
                <tr key={d.id} style={{ borderTop: index ? '1px solid var(--color-border)' : 'none' }}>
                  <td style={tdStyle}>{d.staff_name || d.staff_id}</td>
                  <td style={tdStyle}>{d.month}</td>
                  <td style={tdStyle}>{money(d.gross)}</td>
                  <td style={tdStyle}>{money(d.net)}</td>
                  <td style={tdStyle}>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: 11,
                      fontWeight: 600,
                      background: d.status === 'processed' ? 'color-mix(in srgb, var(--tool-hex-34d399) 18%, transparent)' : 'color-mix(in srgb, var(--tool-hex-fbbf24) 18%, transparent)',
                      color: d.status === 'processed' ? 'var(--tool-hex-34d399)' : 'var(--tool-hex-fbbf24)',
                    }}>
                      {d.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        )}
      </div>

      {currentUser?.role === 'owner' && (
        <div style={{ background: 'color-mix(in srgb, var(--tool-hex-fbbf24) 7%, transparent)', border: '1px solid color-mix(in srgb, var(--tool-hex-fbbf24) 35%, transparent)', borderRadius: 8, padding: 14, marginBottom: 18 }}>
          <h2 style={{ ...panelTitle, color: 'var(--tool-hex-fbbf24)' }}>Pending Discount Approvals</h2>
          {pendingApprovals.length === 0 ? (
            <div style={emptyStyle}>No pending discount approvals.</div>
          ) : (
            pendingApprovals.map(p => (
              <div key={p.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid color-mix(in srgb, var(--tool-hex-fbbf24) 20%, transparent)' }}>
                <span style={{ fontSize: 13, color: 'var(--color-text-primary)' }}>Student: {p.student_id} — {money(p.discount_amount)}</span>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => approveDiscount(p.id)}
                    style={{ ...primaryButton('var(--tool-hex-34d399)'), minHeight: 32, padding: '5px 12px', fontSize: 12 }}>Approve</button>
                  <button onClick={() => rejectDiscount(p.id)}
                    style={{ ...primaryButton('var(--tool-hex-f87171)'), minHeight: 32, padding: '5px 12px', fontSize: 12 }}>Reject</button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Overdue edit modal */}
      {overdueEditTxn && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 9000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 20, width: '100%', maxWidth: 420, boxShadow: '0 20px 60px rgba(0,0,0,0.4)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: 'var(--color-text-primary)' }}>Edit overdue record</h3>
              <button onClick={() => setOverdueEditTxn(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}><X size={16} /></button>
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 12 }}>{overdueEditTxn.student_name || overdueEditTxn.student_id} — {overdueEditTxn.fee_head || overdueEditTxn.fee_type}</div>
            {overdueActionError && <div style={alertStyle('var(--tool-hex-f87171)')}><AlertTriangle size={14} />{overdueActionError}</div>}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 4 }}>Amount (₹)</div>
                <input type="number" value={overdueEditForm.amount} onChange={e => setOverdueEditForm(p => ({ ...p, amount: e.target.value }))} style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 4 }}>Status</div>
                <select value={overdueEditForm.status} onChange={e => setOverdueEditForm(p => ({ ...p, status: e.target.value }))} style={inputStyle}>
                  <option value="pending">Pending</option>
                  <option value="overdue">Overdue</option>
                  <option value="paid">Paid</option>
                  <option value="partial">Partial</option>
                  <option value="waived">Waived</option>
                </select>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 4 }}>Payment mode</div>
                <select value={overdueEditForm.payment_mode} onChange={e => setOverdueEditForm(p => ({ ...p, payment_mode: e.target.value }))} style={inputStyle}>
                  <option value="">— unchanged —</option>
                  <option value="cash">Cash</option>
                  <option value="upi">UPI</option>
                  <option value="cheque">Cheque</option>
                  <option value="bank_transfer">Bank transfer</option>
                  <option value="card">Card</option>
                </select>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 4 }}>Due date</div>
                <input type="date" value={overdueEditForm.due_date} onChange={e => setOverdueEditForm(p => ({ ...p, due_date: e.target.value }))} style={inputStyle} />
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 4 }}>Transaction ref</div>
                <input type="text" value={overdueEditForm.transaction_ref} onChange={e => setOverdueEditForm(p => ({ ...p, transaction_ref: e.target.value }))} style={inputStyle} />
              </div>
            </div>
            <div style={{ marginTop: 4 }}>
              <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 4 }}>Reason for change <span style={{ color: 'var(--tool-hex-f87171)' }}>*</span></div>
              <textarea value={overdueEditForm.reason} onChange={e => setOverdueEditForm(p => ({ ...p, reason: e.target.value }))} placeholder="Required — describe correction" style={textareaStyle} />
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button onClick={saveOverdueEdit} disabled={saving} style={{ ...primaryButton('var(--tool-hex-4f8ff7)'), flex: 1, minHeight: 38, fontSize: 12 }}>{saving ? 'Saving…' : 'Save changes'}</button>
              <button onClick={() => setOverdueEditTxn(null)} style={{ flex: 1, minHeight: 38, borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text-primary)', fontSize: 12, cursor: 'pointer' }}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Overdue delete confirm modal */}
      {overdueDeleteId && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 9000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 24, maxWidth: 360, width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,0.4)' }}>
            <h3 style={{ margin: '0 0 10px', fontSize: 14, fontWeight: 700, color: 'var(--color-text-primary)' }}>Delete this record?</h3>
            <p style={{ margin: '0 0 18px', fontSize: 12, color: 'var(--color-text-muted)' }}>This will permanently remove the transaction. Outstanding totals, defaulter counts, and collection rate will update immediately.</p>
            {overdueActionError && <div style={alertStyle('var(--tool-hex-f87171)')}><AlertTriangle size={14} />{overdueActionError}</div>}
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => deleteOverdueTxn(overdueDeleteId)} disabled={saving} style={{ ...primaryButton('var(--tool-hex-f87171)'), flex: 1, minHeight: 38, fontSize: 12 }}>{saving ? 'Deleting…' : 'Yes, delete'}</button>
              <button onClick={() => { setOverdueDeleteId(null); setOverdueActionError(''); }} style={{ flex: 1, minHeight: 38, borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text-primary)', fontSize: 12, cursor: 'pointer' }}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div style={panelStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>
          <h2 style={panelTitle}>Overdue records</h2>
          <input value={overdueDays} onChange={e => setOverdueDays(e.target.value)} type="number" min="1" style={{ ...inputStyle, width: 120 }} />
        </div>
        {loading ? (
          <div style={emptyStyle}>Loading fee records...</div>
        ) : overdue.length === 0 ? (
          <div style={emptyStyle}>No overdue records at this threshold.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
          <table className="fee-txn-table" style={{ width: '100%', borderCollapse: 'collapse', minWidth: 500 }}>
            <thead><tr>{['Student', 'Class', 'Head', 'Amount', 'Due', 'Status', 'Receipt', 'Actions'].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
            <tbody>
              {overdue.map((txn, index) => (
                <tr key={txn.id} style={{ borderTop: index ? '1px solid var(--color-border)' : 'none' }}>
                  <td style={tdStyle}>{txn.student_name || txn.student_id}</td>
                  <td style={tdStyle}>{txn.class_name || 'N/A'}</td>
                  <td style={tdStyle}>{txn.fee_head || txn.fee_type}</td>
                  <td style={{ ...tdStyle, color: 'var(--tool-hex-f87171)', fontWeight: 700 }}>{money(txn.amount)}</td>
                  <td style={tdStyle}>{txn.due_date || '-'}</td>
                  <td style={tdStyle}>{txn.status}</td>
                  <td style={tdStyle}>
                    {txn.status === 'paid' && (
                      <button onClick={() => downloadReceipt(txn.id || txn.transaction_id)} title="Download PDF receipt" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--tool-hex-4f8ff7)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                        <FileDown size={13} /> PDF
                      </button>
                    )}
                  </td>
                  <td style={tdStyle}>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button onClick={() => { setOverdueActionError(''); openOverdueEdit(txn); }} title="Edit" style={{ background: 'color-mix(in srgb, var(--tool-hex-4f8ff7) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--tool-hex-4f8ff7) 30%, transparent)', borderRadius: 5, padding: '4px 8px', cursor: 'pointer', color: 'var(--tool-hex-4f8ff7)', display: 'flex', alignItems: 'center', gap: 3, fontSize: 11 }}>
                        <Edit3 size={11} />Edit
                      </button>
                      <button onClick={() => { setOverdueActionError(''); setOverdueDeleteId(txn.id); }} title="Delete" style={{ background: 'color-mix(in srgb, var(--tool-hex-f87171) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--tool-hex-f87171) 30%, transparent)', borderRadius: 5, padding: '4px 8px', cursor: 'pointer', color: 'var(--tool-hex-f87171)', display: 'flex', alignItems: 'center', gap: 3, fontSize: 11 }}>
                        <Trash2 size={11} />Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {/* WhatsApp fee reminders — owner/accountant only */}
      {(currentUser?.role === 'owner' || currentUser?.sub_category === 'accountant') && (
        <div style={{ ...panelStyle, marginTop: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <h2 style={{ ...panelTitle, margin: 0 }}><MessageSquare size={16} />WhatsApp fee reminders</h2>
            <button
              onClick={loadWaDefaulters}
              disabled={waLoading}
              style={{ ...primaryButton('var(--tool-hex-4f8ff7)'), minHeight: 36, padding: '7px 14px', fontSize: 12 }}
            >
              {waLoading ? 'Loading…' : 'Load defaulters'}
            </button>
          </div>
          {waDefaulters && (
            <>
              <p style={{ margin: '0 0 10px', color: 'var(--color-text-muted)', fontSize: 12 }}>
                {waDefaulters.fee_defaulters.length} fee defaulter(s) with phone numbers found.
              </p>
              {waDefaulters.fee_defaulters.length > 0 && (
                <button
                  onClick={sendFeeWaReminders}
                  disabled={waSending}
                  style={{ ...primaryButton('var(--tool-hex-34d399)'), minHeight: 36, padding: '7px 14px', fontSize: 12 }}
                >
                  {waSending ? 'Sending…' : `Send reminders to ${waDefaulters.fee_defaulters.length} guardian(s)`}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

const panelStyle = { background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 14 };
const panelTitle = { display: 'flex', alignItems: 'center', gap: 8, margin: '0 0 10px', color: 'var(--color-text-primary)', fontSize: 13, fontWeight: 750 };
const inputStyle = { minHeight: 40, width: '100%', boxSizing: 'border-box', background: 'var(--color-surface-raised)', border: '1px solid var(--color-border)', borderRadius: 7, padding: '8px 10px', color: 'var(--color-text-primary)', fontSize: 13, outline: 'none', marginBottom: 8 };
const textareaStyle = { ...inputStyle, minHeight: 76, resize: 'vertical' };
const twoCol = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8 };
const primaryButton = background => ({ minHeight: 44, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, background, border: 'none', borderRadius: 8, padding: '11px 18px', color: 'var(--tool-hex-fff)', fontSize: 13, fontWeight: 750, cursor: 'pointer' });
const iconButton = { minHeight: 44, minWidth: 44, display: 'grid', placeItems: 'center', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text-primary)', cursor: 'pointer' };
const alertStyle = color => ({ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, padding: 12, border: `1px solid color-mix(in srgb, ${color} 33%, transparent)`, borderRadius: 8, background: `color-mix(in srgb, ${color} 7%, transparent)`, color, fontSize: 13 });
const thStyle = { padding: '10px 12px', textAlign: 'left', color: 'var(--color-text-muted)', fontSize: 10, textTransform: 'uppercase', background: 'var(--color-surface-raised)' };
const tdStyle = { padding: '10px 12px', color: 'var(--color-text-primary)', fontSize: 13 };
const emptyStyle = { padding: 30, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13 };
const lineItem = { display: 'flex', justifyContent: 'space-between', gap: 12, padding: '7px 0', color: 'var(--color-text-primary)', fontSize: 13 };
