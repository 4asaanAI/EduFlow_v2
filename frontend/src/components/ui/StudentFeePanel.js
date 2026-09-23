/**
 * Fee Collection CTA on a student's profile (search + directory pointer, 2026-09-23).
 *
 * A finance user reaching a student through search or the directory used to have to
 * leave the profile and hunt the same student down again inside the full Fee
 * Collection tool just to see what they owed. This is the same read/write surface
 * (`GET/POST /api/fees/transactions`, gated by `require_finance_profile` on the
 * backend) embedded directly in the profile, scoped to one student.
 *
 * Deliberately NOT a reuse of `FeeCollection.js` wholesale - that screen also
 * carries payroll, discounts, fee-structure management and WhatsApp reminders,
 * none of which belong on a single student's profile. Only the payment-form field
 * set and the idempotency-key convention are shared.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Pencil, Trash2, X } from 'lucide-react';
import { correctFeeTransaction, deleteFeeTransaction, getFeeTransactions, recordFeePayment } from '../../lib/api';
import { inputStyle } from './primitives';

const overlayStyle = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 210, padding: 16,
};

const panelStyle = {
  background: 'var(--c-input)', border: '1px solid var(--c-border)',
  borderRadius: 10, padding: 22, width: 640, maxWidth: '100%',
  maxHeight: '90vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16,
};

const twoCol = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 };

const initialPayment = { fee_period: '', fee_head: 'tuition', amount: '', paid_amount: '', payment_mode: 'upi', status: 'paid', transaction_ref: '' };
const initialCorrection = { amount: '', status: '', due_date: '', payment_mode: '', transaction_ref: '', reason: '' };

function normalizeFeeKey(studentId, feePeriod, feeHead) {
  return `${studentId}|${feePeriod}|${(feeHead || '').trim().toLowerCase()}`;
}

export default function StudentFeePanel({ studentId, studentName, onClose }) {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [payment, setPayment] = useState(initialPayment);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');
  const [notice, setNotice] = useState('');
  // History CRUD (2026-09-23): edit reuses the same shared write path
  // `FeeCollection.js`'s own correction form calls (`PATCH .../correct`, reason
  // mandatory, audited); delete is the existing soft-delete route. Both are
  // already gated by `require_finance_profile` on the backend - the same gate
  // that shows this whole panel - so no new RBAC surface is introduced.
  const [correctingId, setCorrectingId] = useState(null);
  const [correction, setCorrection] = useState(initialCorrection);
  const [correctionBusy, setCorrectionBusy] = useState(false);
  const [correctionError, setCorrectionError] = useState('');
  const [deletingId, setDeletingId] = useState(null);
  // Synchronous re-entrancy guard: `deletingId` (React state) doesn't take
  // effect in the DOM until the next render, so a fast double-click on the
  // same row's delete button - or two staff viewing this student's history
  // at once - can both pass the confirm dialog before either request lands.
  // The second `DELETE` then 404s ("already deleted"), which used to surface
  // as a raw "not found" error. This ref closes that window; the 404 itself
  // is also now treated as "already gone", not a failure (see below).
  const deletingRef = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    const res = await getFeeTransactions({ student_id: studentId });
    if (res.success) setTransactions(res.data || []);
    else setLoadError(res.detail || 'Could not load this student’s fee records');
    setLoading(false);
  }, [studentId]);

  useEffect(() => { load(); }, [load]);

  // Same convention as `FeeCollection.js`: paid/partial contribute their
  // `paid_amount` (falling back to the full `amount` when unset) to collected;
  // pending/overdue/partial contribute the remainder to pending.
  const collected = transactions.reduce((sum, t) => {
    if (t.status === 'paid') return sum + Number(t.amount || 0);
    if (t.status === 'partial') return sum + Number(t.paid_amount || 0);
    return sum;
  }, 0);
  const pending = transactions.reduce((sum, t) => {
    if (t.status === 'pending' || t.status === 'overdue') return sum + Number(t.amount || 0);
    if (t.status === 'partial') return sum + Math.max(Number(t.amount || 0) - Number(t.paid_amount || 0), 0);
    return sum;
  }, 0);

  async function savePayment() {
    setFormError('');
    setNotice('');
    if (!payment.fee_period.trim() || !payment.fee_head.trim() || !payment.amount) {
      setFormError('Fee period, fee head, and amount are required.');
      return;
    }
    if (payment.status === 'partial' && !payment.paid_amount) {
      setFormError('Enter the amount actually paid for a partial payment.');
      return;
    }
    setSaving(true);
    try {
      const key = normalizeFeeKey(studentId, payment.fee_period, payment.fee_head);
      const payload = {
        ...payment,
        student_id: studentId,
        amount: Number(payment.amount),
        fee_type: payment.fee_head,
      };
      if (payment.paid_amount) payload.paid_amount = Number(payment.paid_amount);
      const res = await recordFeePayment(payload, key);
      if (!res.success) {
        setFormError(res.detail || 'Payment could not be saved');
      } else {
        setNotice(res.idempotent ? 'Duplicate submission recovered. Original payment returned.' : 'Payment saved.');
        setPayment(initialPayment);
        await load();
      }
    } catch {
      setFormError('Payment could not be saved. If the network dropped, refresh before retrying to avoid duplicates.');
    } finally {
      setSaving(false);
    }
  }

  function startEdit(t) {
    setCorrectingId(t.id);
    setCorrection({
      amount: t.amount ?? '',
      status: t.status || '',
      due_date: t.due_date || '',
      payment_mode: t.payment_mode || '',
      transaction_ref: t.transaction_ref || '',
      reason: '',
    });
    setCorrectionError('');
  }

  function cancelEdit() {
    setCorrectingId(null);
    setCorrection(initialCorrection);
    setCorrectionError('');
  }

  async function saveCorrection() {
    setCorrectionError('');
    if (!correction.reason.trim()) {
      setCorrectionError('A reason is required to change a fee record.');
      return;
    }
    setCorrectionBusy(true);
    try {
      const payload = { reason: correction.reason.trim() };
      if (correction.amount !== '') payload.amount = Number(correction.amount);
      if (correction.status) payload.status = correction.status;
      if (correction.due_date) payload.due_date = correction.due_date;
      if (correction.payment_mode) payload.payment_mode = correction.payment_mode;
      if (correction.transaction_ref) payload.transaction_ref = correction.transaction_ref;
      const res = await correctFeeTransaction(correctingId, payload);
      if (!res.success) {
        setCorrectionError(res.detail || 'Could not save the correction');
      } else {
        setNotice('Correction saved with an audit trail.');
        cancelEdit();
        await load();
      }
    } catch {
      setCorrectionError('Could not save the correction. If the network dropped, check the history before retrying.');
    } finally {
      setCorrectionBusy(false);
    }
  }

  async function removeTransaction(t) {
    if (deletingRef.current) return;
    const label = `${t.fee_period || ''} ${t.fee_head || t.fee_type || ''}`.trim() || 'this transaction';
    if (!window.confirm(`Delete ${label}? This cannot be undone.`)) return;
    deletingRef.current = true;
    setDeletingId(t.id);
    setLoadError('');
    try {
      const res = await deleteFeeTransaction(t.id);
      if (res.success) {
        if (correctingId === t.id) cancelEdit();
        await load();
      } else if (/not found/i.test(res.detail || '')) {
        // Already gone - a second click, or someone else deleted it first.
        // The end state we wanted (this row is gone) is already true, so
        // just refresh the list rather than report it as a failure.
        if (correctingId === t.id) cancelEdit();
        await load();
      } else {
        setLoadError(res.detail || 'Could not delete this transaction');
      }
    } catch {
      setLoadError('Could not delete this transaction. If the network dropped, check the history before retrying.');
    } finally {
      setDeletingId(null);
      deletingRef.current = false;
    }
  }

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={panelStyle} onClick={(e) => e.stopPropagation()} data-testid="student-fee-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--c-text)' }}>Fee Collection</div>
            <div style={{ fontSize: 12, color: 'var(--c-muted)', marginTop: 2 }}>{studentName}</div>
          </div>
          <button type="button" onClick={onClose} aria-label="Close fee collection" style={{ border: 'none', background: 'transparent', color: 'var(--c-faint)', cursor: 'pointer', padding: 4 }}>
            <X size={17} />
          </button>
        </div>

        {loadError && <div role="alert" style={{ color: '#f87171', fontSize: 12 }}>{loadError}</div>}

        {loading ? (
          <div style={{ color: 'var(--c-faint)', fontSize: 12 }}>Loading fee records…</div>
        ) : (
          <>
            <div style={{ display: 'flex', gap: 10 }}>
              <div style={{ flex: 1, border: '1px solid var(--c-border)', borderRadius: 8, padding: '10px 12px' }}>
                <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--c-faint)' }}>Collected</div>
                <div data-testid="fee-panel-collected-total" style={{ fontSize: 18, fontWeight: 700, color: '#34d399' }}>{`₹${collected.toLocaleString('en-IN')}`}</div>
              </div>
              <div style={{ flex: 1, border: '1px solid var(--c-border)', borderRadius: 8, padding: '10px 12px' }}>
                <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--c-faint)' }}>Pending</div>
                <div data-testid="fee-panel-pending-total" style={{ fontSize: 18, fontWeight: 700, color: pending > 0 ? '#fb7185' : 'var(--c-text)' }}>{`₹${pending.toLocaleString('en-IN')}`}</div>
              </div>
            </div>

            <div>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--c-faint)', marginBottom: 6 }}>History</div>
              {transactions.length === 0 ? (
                <div style={{ color: 'var(--c-faint)', fontSize: 12 }}>No fee transactions recorded yet.</div>
              ) : (
                <div style={{ maxHeight: 320, overflowY: 'auto', border: '1px solid var(--c-border)', borderRadius: 8 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr style={{ textAlign: 'left', color: 'var(--c-faint)' }}>
                        <th style={{ padding: '6px 10px' }}>Period</th>
                        <th style={{ padding: '6px 10px' }}>Head</th>
                        <th style={{ padding: '6px 10px' }}>Amount</th>
                        <th style={{ padding: '6px 10px' }}>Status</th>
                        <th style={{ padding: '6px 10px' }}>Due</th>
                        <th style={{ padding: '6px 10px' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {transactions.map((t) => (
                        <React.Fragment key={t.id}>
                          <tr style={{ borderTop: '1px solid var(--c-border)' }}>
                            <td style={{ padding: '6px 10px' }}>{t.fee_period || '-'}</td>
                            <td style={{ padding: '6px 10px' }}>{t.fee_head || t.fee_type || '-'}</td>
                            <td style={{ padding: '6px 10px' }}>{`₹${Number(t.amount || 0).toLocaleString('en-IN')}`}</td>
                            <td style={{ padding: '6px 10px' }}>{t.status || '-'}</td>
                            <td style={{ padding: '6px 10px' }}>{t.due_date || '-'}</td>
                            <td style={{ padding: '6px 10px' }}>
                              <div style={{ display: 'flex', gap: 6 }}>
                                <button
                                  type="button"
                                  onClick={() => (correctingId === t.id ? cancelEdit() : startEdit(t))}
                                  aria-label={`Edit ${t.fee_period || ''} ${t.fee_head || t.fee_type || ''}`}
                                  style={{ border: 'none', background: 'transparent', color: 'var(--c-faint)', cursor: 'pointer', padding: 2 }}
                                >
                                  <Pencil size={13} />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => removeTransaction(t)}
                                  disabled={deletingId === t.id}
                                  aria-label={`Delete ${t.fee_period || ''} ${t.fee_head || t.fee_type || ''}`}
                                  style={{ border: 'none', background: 'transparent', color: '#fb7185', cursor: deletingId === t.id ? 'not-allowed' : 'pointer', padding: 2, opacity: deletingId === t.id ? 0.5 : 1 }}
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            </td>
                          </tr>
                          {correctingId === t.id && (
                            <tr>
                              <td colSpan={6} style={{ padding: '10px', background: 'var(--color-surface-raised, rgba(255,255,255,0.03))' }}>
                                {correctionError && <div role="alert" style={{ color: '#f87171', fontSize: 12, marginBottom: 8 }}>{correctionError}</div>}
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                  <div style={twoCol}>
                                    <input
                                      aria-label="Corrected amount"
                                      value={correction.amount}
                                      onChange={(e) => setCorrection((prev) => ({ ...prev, amount: e.target.value }))}
                                      placeholder="Amount"
                                      type="number"
                                      style={inputStyle}
                                    />
                                    <select
                                      aria-label="Corrected status"
                                      value={correction.status}
                                      onChange={(e) => setCorrection((prev) => ({ ...prev, status: e.target.value }))}
                                      style={inputStyle}
                                    >
                                      <option value="">Status unchanged</option>
                                      <option value="paid">Full payment</option>
                                      <option value="partial">Partial payment</option>
                                      <option value="pending">Pending</option>
                                      <option value="overdue">Overdue</option>
                                    </select>
                                  </div>
                                  <div style={twoCol}>
                                    <input
                                      aria-label="Corrected due date"
                                      value={correction.due_date}
                                      onChange={(e) => setCorrection((prev) => ({ ...prev, due_date: e.target.value }))}
                                      placeholder="Due date (YYYY-MM-DD)"
                                      style={inputStyle}
                                    />
                                    <select
                                      aria-label="Corrected payment mode"
                                      value={correction.payment_mode}
                                      onChange={(e) => setCorrection((prev) => ({ ...prev, payment_mode: e.target.value }))}
                                      style={inputStyle}
                                    >
                                      <option value="">Mode unchanged</option>
                                      <option value="upi">UPI</option>
                                      <option value="cash">Cash</option>
                                      <option value="bank_transfer">Bank transfer</option>
                                      <option value="card">Card</option>
                                    </select>
                                  </div>
                                  <input
                                    aria-label="Corrected transaction reference"
                                    value={correction.transaction_ref}
                                    onChange={(e) => setCorrection((prev) => ({ ...prev, transaction_ref: e.target.value }))}
                                    placeholder="Transaction reference"
                                    style={inputStyle}
                                  />
                                  <input
                                    aria-label="Reason for correction"
                                    value={correction.reason}
                                    onChange={(e) => setCorrection((prev) => ({ ...prev, reason: e.target.value }))}
                                    placeholder="Reason for this change (required)"
                                    style={inputStyle}
                                  />
                                  <div style={{ display: 'flex', gap: 8 }}>
                                    <button
                                      type="button"
                                      onClick={saveCorrection}
                                      disabled={correctionBusy}
                                      data-testid="save-fee-correction"
                                      style={{
                                        background: 'var(--brand-blue-fill, #4f8ff7)', color: 'var(--on-brand-blue, #fff)',
                                        border: 'none', borderRadius: 8, padding: '8px 12px', fontSize: 12, fontWeight: 700,
                                        cursor: correctionBusy ? 'not-allowed' : 'pointer', opacity: correctionBusy ? 0.6 : 1,
                                      }}
                                    >
                                      {correctionBusy ? 'Saving…' : 'Save correction'}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={cancelEdit}
                                      style={{ background: 'transparent', color: 'var(--c-text)', border: '1px solid var(--c-border)', borderRadius: 8, padding: '8px 12px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--c-faint)', marginBottom: 6 }}>Record payment</div>
              {formError && <div role="alert" style={{ color: '#f87171', fontSize: 12, marginBottom: 8 }}>{formError}</div>}
              {notice && <div role="status" style={{ color: '#34d399', fontSize: 12, marginBottom: 8 }}>{notice}</div>}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={twoCol}>
                  <input
                    aria-label="Fee period"
                    value={payment.fee_period}
                    onChange={(e) => setPayment((prev) => ({ ...prev, fee_period: e.target.value }))}
                    placeholder="2026-05"
                    style={inputStyle}
                  />
                  <input
                    aria-label="Fee head"
                    value={payment.fee_head}
                    onChange={(e) => setPayment((prev) => ({ ...prev, fee_head: e.target.value }))}
                    placeholder="tuition"
                    style={inputStyle}
                  />
                </div>
                <div style={twoCol}>
                  <input
                    aria-label="Amount"
                    value={payment.amount}
                    onChange={(e) => setPayment((prev) => ({ ...prev, amount: e.target.value }))}
                    placeholder="Amount"
                    type="number"
                    style={inputStyle}
                  />
                  <select
                    aria-label="Payment mode"
                    value={payment.payment_mode}
                    onChange={(e) => setPayment((prev) => ({ ...prev, payment_mode: e.target.value }))}
                    style={inputStyle}
                  >
                    <option value="upi">UPI</option>
                    <option value="cash">Cash</option>
                    <option value="bank_transfer">Bank transfer</option>
                    <option value="card">Card</option>
                  </select>
                </div>
                <div style={twoCol}>
                  <select
                    aria-label="Payment status"
                    value={payment.status}
                    onChange={(e) => setPayment((prev) => ({ ...prev, status: e.target.value, paid_amount: e.target.value !== 'partial' ? '' : prev.paid_amount }))}
                    style={inputStyle}
                  >
                    <option value="paid">Full payment</option>
                    <option value="partial">Partial payment</option>
                    <option value="pending">Pending</option>
                  </select>
                  {payment.status === 'partial' && (
                    <input
                      aria-label="Partial amount"
                      value={payment.paid_amount}
                      onChange={(e) => setPayment((prev) => ({ ...prev, paid_amount: e.target.value }))}
                      placeholder="Partial amount"
                      type="number"
                      style={inputStyle}
                    />
                  )}
                </div>
                <input
                  aria-label="Transaction reference"
                  value={payment.transaction_ref}
                  onChange={(e) => setPayment((prev) => ({ ...prev, transaction_ref: e.target.value }))}
                  placeholder="Transaction reference"
                  style={inputStyle}
                />
                <button
                  type="button"
                  onClick={savePayment}
                  disabled={saving}
                  data-testid="record-fee-payment"
                  style={{
                    background: 'var(--brand-blue-fill, #4f8ff7)', color: 'var(--on-brand-blue, #fff)',
                    border: 'none', borderRadius: 8, padding: '10px 14px', fontSize: 13, fontWeight: 700,
                    cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.6 : 1,
                  }}
                >
                  {saving ? 'Saving…' : 'Save payment'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
