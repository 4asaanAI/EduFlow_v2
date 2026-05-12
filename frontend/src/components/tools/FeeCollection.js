import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle, Edit3, Percent, Phone, RefreshCw, Save } from 'lucide-react';
import {
  applyFeeDiscount,
  correctFeeTransaction,
  createFeeContactLog,
  createDiscountType,
  getDiscountSummary,
  getDiscountTypes,
  getFeeDiscounts,
  getFeeSummary,
  getFeeTransactions,
  getStudents,
  recordFeePayment,
} from '../../lib/api';

const today = new Date().toISOString().slice(0, 10);
const initialPayment = { student_id: '', fee_period: '', fee_head: 'tuition', amount: '', payment_mode: 'upi', status: 'paid', due_date: today, transaction_ref: '' };
const initialCorrection = { transaction_id: '', amount: '', status: '', reason: '' };
const initialContact = { fee_transaction_id: '', student_id: '', contact_type: 'call', outcome: '', notes: '', date: today };
const initialDiscountType = { name: '', value: '', value_type: 'percentage', recurrence: 'per-term', reason_note: '' };
const initialDiscountApply = { student_id: '', discount_type_id: '', original_amount: '', effective_from: today, note: '' };

function money(value) {
  return `Rs ${Number(value || 0).toLocaleString('en-IN')}`;
}

export default function FeeCollection() {
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
  const [discountTypes, setDiscountTypes] = useState([]);
  const [discountSummary, setDiscountSummary] = useState(null);
  const [discountBreakdown, setDiscountBreakdown] = useState(null);
  const [discountTypeForm, setDiscountTypeForm] = useState(initialDiscountType);
  const [discountApply, setDiscountApply] = useState(initialDiscountApply);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [summaryRes, txnRes, overdueRes, studentRes, discountTypesRes, discountSummaryRes] = await Promise.all([
        getFeeSummary(payment.fee_period ? { fee_period: payment.fee_period } : {}),
        getFeeTransactions(null, {}),
        getFeeTransactions(null, { overdue_days: overdueDays }),
        getStudents(null, { limit: 200 }),
        getDiscountTypes(),
        getDiscountSummary(),
      ]);
      if (!summaryRes.success) throw new Error(summaryRes.detail || 'Unable to load fee summary');
      if (!txnRes.success) throw new Error(txnRes.detail || 'Unable to load fee transactions');
      setSummary(summaryRes.data);
      setTransactions(txnRes.data || []);
      setStudents(studentRes.data || []);
      setContact(prev => ({ ...prev, overdue: overdueRes.data || [] }));
      setDiscountTypes(discountTypesRes.data || []);
      if (discountSummaryRes.success) setDiscountSummary(discountSummaryRes.data);
    } catch (err) {
      setError(err.message || 'Unable to load fee data. Check whether the last payment was partially written before retrying.');
    } finally {
      setLoading(false);
    }
  }, [payment.fee_period, overdueDays]);

  useEffect(() => { loadData(); }, [loadData]);

  const selectedTxn = useMemo(() => transactions.find(t => t.id === correction.transaction_id), [transactions, correction.transaction_id]);
  const overdue = contact.overdue || [];

  async function savePayment() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      if (!payment.student_id || !payment.fee_period || !payment.fee_head || !payment.amount) {
        throw new Error('Student, period, fee head, and amount are required.');
      }
      const key = `${payment.student_id}:${payment.fee_period}:${payment.fee_head}`;
      const res = await recordFeePayment(null, { ...payment, amount: Number(payment.amount), fee_type: payment.fee_head }, key);
      if (!res.success) throw new Error(res.detail || 'Payment could not be saved');
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
      const res = await applyFeeDiscount({ ...discountApply, original_amount: Number(discountApply.original_amount) });
      if (!res.success) throw new Error(res.detail || 'Discount could not be applied');
      setDiscountApply(initialDiscountApply);
      setNotice('Discount applied.');
      await loadData();
      await loadDiscountBreakdown(res.data.student_id);
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

  return (
    <div data-testid="fee-collection-tool" style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', marginBottom: 20, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 650, margin: 0, color: 'var(--c-text)' }}>Fee collection</h1>
          <p style={{ margin: '6px 0 0', color: 'var(--c-faint)', fontSize: 12 }}>Payments, corrections, defaulters, and contact recovery</p>
        </div>
        <button onClick={loadData} disabled={loading} title="Refresh fee data" style={iconButton}>
          <RefreshCw size={16} />
        </button>
      </div>

      {error && <div role="alert" style={alertStyle('#f87171')}><AlertTriangle size={16} />{error}</div>}
      {notice && <div style={alertStyle('#34d399')}><CheckCircle size={16} />{notice}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 18 }}>
        {[
          ['Collected', money(summary?.total_collected), '#34d399'],
          ['Outstanding', money(summary?.total_outstanding), '#f87171'],
          ['Defaulters', summary?.defaulters || 0, '#fbbf24'],
          ['Discounts', money(discountSummary?.total_discount_value), '#a78bfa'],
        ].map(([label, value, color]) => (
          <div key={label} style={panelStyle}>
            <div style={{ color, fontSize: 20, fontWeight: 750 }}>{value}</div>
            <div style={{ color: 'var(--c-faint)', fontSize: 10, fontWeight: 700, textTransform: 'uppercase' }}>{label}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 14, marginBottom: 18 }}>
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
          <input value={payment.transaction_ref} onChange={e => setPayment(prev => ({ ...prev, transaction_ref: e.target.value }))} placeholder="Transaction reference" style={inputStyle} />
          <button onClick={savePayment} disabled={saving} style={primaryButton('#4f8ff7')}>Save payment</button>
        </section>

        <section style={panelStyle}>
          <h2 style={panelTitle}><Edit3 size={16} />Correct record</h2>
          <select value={correction.transaction_id} onChange={e => setCorrection(prev => ({ ...prev, transaction_id: e.target.value }))} style={inputStyle}>
            <option value="">Select transaction</option>
            {transactions.map(t => <option key={t.id} value={t.id}>{t.student_name || t.student_id} - {t.fee_type} - {money(t.amount)}</option>)}
          </select>
          {selectedTxn && <div style={{ color: 'var(--c-faint)', fontSize: 12 }}>Current: {selectedTxn.status} / {money(selectedTxn.amount)}</div>}
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
          <button onClick={saveCorrection} disabled={saving} style={primaryButton('#6366f1')}>Save correction</button>
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
          <button onClick={saveContact} disabled={saving} style={primaryButton('#10b981')}>Log contact</button>
        </section>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 14, marginBottom: 18 }}>
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
          <button onClick={saveDiscountType} disabled={saving} style={primaryButton('#a78bfa')}>Save discount type</button>
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
          <button onClick={applyDiscount} disabled={saving} style={primaryButton('#8b5cf6')}>Apply discount</button>
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
              <div style={{ ...lineItem, borderTop: '1px solid var(--c-border)', paddingTop: 10, color: '#34d399' }}>
                <span>Payable</span><strong>{money(discountBreakdown.payable_amount)}</strong>
              </div>
            </div>
          )}
        </section>
      </div>

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
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Student', 'Class', 'Head', 'Amount', 'Due', 'Status'].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
            <tbody>
              {overdue.map((txn, index) => (
                <tr key={txn.id} style={{ borderTop: index ? '1px solid var(--c-border)' : 'none' }}>
                  <td style={tdStyle}>{txn.student_name || txn.student_id}</td>
                  <td style={tdStyle}>{txn.class_name || 'N/A'}</td>
                  <td style={tdStyle}>{txn.fee_head || txn.fee_type}</td>
                  <td style={{ ...tdStyle, color: '#f87171', fontWeight: 700 }}>{money(txn.amount)}</td>
                  <td style={tdStyle}>{txn.due_date || '-'}</td>
                  <td style={tdStyle}>{txn.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

const panelStyle = { background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: 14 };
const panelTitle = { display: 'flex', alignItems: 'center', gap: 8, margin: '0 0 10px', color: 'var(--c-text)', fontSize: 13, fontWeight: 750 };
const inputStyle = { minHeight: 40, width: '100%', boxSizing: 'border-box', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 10px', color: 'var(--c-text)', fontSize: 13, outline: 'none', marginBottom: 8 };
const textareaStyle = { ...inputStyle, minHeight: 76, resize: 'vertical' };
const twoCol = { display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 };
const primaryButton = background => ({ minHeight: 44, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, background, border: 'none', borderRadius: 8, padding: '11px 18px', color: '#fff', fontSize: 13, fontWeight: 750, cursor: 'pointer' });
const iconButton = { minHeight: 44, minWidth: 44, display: 'grid', placeItems: 'center', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, color: 'var(--c-text)', cursor: 'pointer' };
const alertStyle = color => ({ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, padding: 12, border: `1px solid ${color}55`, borderRadius: 8, background: `${color}12`, color, fontSize: 13 });
const thStyle = { padding: '10px 12px', textAlign: 'left', color: 'var(--c-faint)', fontSize: 10, textTransform: 'uppercase', background: 'var(--c-deep)' };
const tdStyle = { padding: '10px 12px', color: 'var(--c-text)', fontSize: 13 };
const emptyStyle = { padding: 30, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 };
const lineItem = { display: 'flex', justifyContent: 'space-between', gap: 12, padding: '7px 0', color: 'var(--c-text)', fontSize: 13 };
