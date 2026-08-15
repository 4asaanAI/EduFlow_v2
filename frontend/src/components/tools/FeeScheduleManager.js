import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CalendarDays, Plus, RefreshCw, Save, Trash2 } from 'lucide-react';
import { API, apiFetch } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';
import SearchableSelect from '../ui/SearchableSelect';

const emptyHead = () => ({ name: '', amount: '' });
const emptyInstallment = () => ({
  code: '',
  label: '',
  due_date: new Date().toISOString().slice(0, 10),
  fee_heads: [emptyHead()],
});

function normalizedInstallments(items) {
  if (!Array.isArray(items) || items.length === 0) return [emptyInstallment()];
  return items.map(item => ({
    code: item.code || '',
    label: item.label || '',
    due_date: item.due_date || '',
    fee_heads: Array.isArray(item.fee_heads) && item.fee_heads.length
      ? item.fee_heads.map(head => ({ name: head.name || '', amount: head.amount ?? '' }))
      : [emptyHead()],
  }));
}

async function responseJson(response, fallback) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || fallback);
  return body;
}

export default function FeeScheduleManager({ currentUser, onChargesGenerated }) {
  const [structures, setStructures] = useState([]);
  const [structureId, setStructureId] = useState('');
  const [installments, setInstallments] = useState([emptyInstallment()]);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const selected = useMemo(
    () => structures.find(item => item.id === structureId),
    [structures, structureId]
  );

  const loadStructures = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await apiFetch(`${API}/fees/structures`, { headers: getAuthHeaders() });
      const body = await responseJson(response, 'Unable to load fee structures');
      const items = body.data || [];
      setStructures(items);
      setStructureId(previous => previous || items[0]?.id || '');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (currentUser?.role === 'owner') loadStructures();
  }, [currentUser?.role, loadStructures]);

  useEffect(() => {
    if (!selected) return;
    setInstallments(normalizedInstallments(selected.installments));
    setPreview(null);
  }, [selected]);

  if (currentUser?.role !== 'owner') return null;

  function updateInstallment(index, field, value) {
    setInstallments(current => current.map((item, itemIndex) => (
      itemIndex === index ? { ...item, [field]: value } : item
    )));
  }

  function updateHead(installmentIndex, headIndex, field, value) {
    setInstallments(current => current.map((item, itemIndex) => {
      if (itemIndex !== installmentIndex) return item;
      return {
        ...item,
        fee_heads: item.fee_heads.map((head, index) => (
          index === headIndex ? { ...head, [field]: value } : head
        )),
      };
    }));
  }

  function addHead(index) {
    setInstallments(current => current.map((item, itemIndex) => (
      itemIndex === index ? { ...item, fee_heads: [...item.fee_heads, emptyHead()] } : item
    )));
  }

  function removeHead(installmentIndex, headIndex) {
    setInstallments(current => current.map((item, itemIndex) => {
      if (itemIndex !== installmentIndex || item.fee_heads.length === 1) return item;
      return { ...item, fee_heads: item.fee_heads.filter((_, index) => index !== headIndex) };
    }));
  }

  function payload() {
    return installments.map(item => ({
      code: item.code.trim(),
      label: item.label.trim(),
      due_date: item.due_date,
      fee_heads: item.fee_heads.map(head => ({
        name: head.name.trim(),
        amount: Number(head.amount),
      })),
    }));
  }

  async function saveSchedule() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const response = await apiFetch(`${API}/fees/structures/${encodeURIComponent(structureId)}/installments`, {
        method: 'PUT',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ installments: payload() }),
      });
      await responseJson(response, 'Unable to save installment schedule');
      setNotice('Installment schedule saved as a new structure version.');
      await loadStructures();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function previewCharges() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const response = await apiFetch(`${API}/fees/structures/${encodeURIComponent(structureId)}/charges/preview`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const body = await responseJson(response, 'Unable to preview charges');
      setPreview(body.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function generateCharges() {
    if (!preview || !window.confirm(`Generate ${preview.charge_count || 0} fee charges? Existing charge keys will be skipped.`)) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const response = await apiFetch(`${API}/fees/structures/${encodeURIComponent(structureId)}/charges/generate`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const body = await responseJson(response, 'Unable to generate charges');
      setNotice(`Generated ${body.data?.created_count || 0} charges; skipped ${body.data?.skipped_count || 0} existing charges.`);
      setPreview(null);
      if (onChargesGenerated) await onChargesGenerated();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section style={panelStyle} aria-label="Fee structures and installments">
      <div className="fee-schedule-header">
        <div>
          <h2 style={titleStyle}><CalendarDays size={17} />Fee structures and installments</h2>
          <p style={hintStyle}>Version schedules, preview charges, then generate them idempotently.</p>
        </div>
        <button type="button" onClick={loadStructures} disabled={loading} style={iconButton} aria-label="Refresh fee structures">
          <RefreshCw size={15} />
        </button>
      </div>

      {error && <div role="alert" style={messageStyle('#f87171')}>{error}</div>}
      {notice && <div role="status" style={messageStyle('#34d399')}>{notice}</div>}

      <label style={labelStyle} htmlFor="fee-structure-select">Fee structure</label>
      <SearchableSelect id="fee-structure-select" value={structureId} onChange={event => setStructureId(event.target.value)} style={inputStyle}>
        <option value="">Select structure</option>
        {structures.map(item => (
          <option key={item.id} value={item.id} label={`${item.name || item.class_id} (v${item.version || 1})`} />
        ))}
      </SearchableSelect>

      {structureId && installments.map((item, installmentIndex) => (
        <div key={`${installmentIndex}-${item.code}`} style={installmentStyle}>
          <div className="fee-schedule-grid">
            <input aria-label={`Installment ${installmentIndex + 1} code`} value={item.code} onChange={event => updateInstallment(installmentIndex, 'code', event.target.value)} placeholder="Code, e.g. TERM-1" style={inputStyle} />
            <input aria-label={`Installment ${installmentIndex + 1} label`} value={item.label} onChange={event => updateInstallment(installmentIndex, 'label', event.target.value)} placeholder="Label" style={inputStyle} />
            <input aria-label={`Installment ${installmentIndex + 1} due date`} value={item.due_date} onChange={event => updateInstallment(installmentIndex, 'due_date', event.target.value)} type="date" style={inputStyle} />
          </div>
          {item.fee_heads.map((head, headIndex) => (
            <div key={headIndex} className="fee-head-grid">
              <input aria-label={`Installment ${installmentIndex + 1} fee head ${headIndex + 1}`} value={head.name} onChange={event => updateHead(installmentIndex, headIndex, 'name', event.target.value)} placeholder="Fee head" style={inputStyle} />
              <input aria-label={`Installment ${installmentIndex + 1} amount ${headIndex + 1}`} value={head.amount} onChange={event => updateHead(installmentIndex, headIndex, 'amount', event.target.value)} placeholder="Amount" min="0.01" step="0.01" type="number" style={inputStyle} />
              <button type="button" onClick={() => removeHead(installmentIndex, headIndex)} disabled={item.fee_heads.length === 1} style={iconButton} aria-label={`Remove fee head ${headIndex + 1}`}><Trash2 size={14} /></button>
            </div>
          ))}
          <div style={actionRow}>
            <button type="button" onClick={() => addHead(installmentIndex)} style={secondaryButton}><Plus size={14} />Add fee head</button>
            <button type="button" onClick={() => setInstallments(current => current.filter((_, index) => index !== installmentIndex))} disabled={installments.length === 1} style={secondaryButton}><Trash2 size={14} />Remove installment</button>
          </div>
        </div>
      ))}

      {structureId && (
        <div style={actionRow}>
          <button type="button" onClick={() => setInstallments(current => [...current, emptyInstallment()])} style={secondaryButton}><Plus size={14} />Add installment</button>
          <button type="button" onClick={saveSchedule} disabled={saving} style={primaryButton}><Save size={14} />Save schedule</button>
          <button type="button" onClick={previewCharges} disabled={saving} style={secondaryButton}>Preview charges</button>
        </div>
      )}

      {preview && (
        <div style={previewStyle}>
          <strong>{preview.charge_count || 0} charges</strong>
          <span>{preview.student_count || 0} students</span>
          <span>Rs {Number(preview.total_amount || 0).toLocaleString('en-IN')}</span>
          <button type="button" onClick={generateCharges} disabled={saving || !preview.charge_count} style={primaryButton}>Generate charges</button>
        </div>
      )}

      <style>{`
        .fee-schedule-header { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
        .fee-schedule-grid { display:grid; grid-template-columns:1fr 1.4fr minmax(145px, .8fr); gap:8px; }
        .fee-head-grid { display:grid; grid-template-columns:minmax(140px, 1fr) minmax(110px, .5fr) 38px; gap:8px; align-items:center; margin-top:8px; }
        @media (max-width: 640px) {
          .fee-schedule-grid { grid-template-columns:1fr; }
          .fee-head-grid { grid-template-columns:minmax(0, 1fr) minmax(90px, .6fr) 38px; }
        }
      `}</style>
    </section>
  );
}

const panelStyle = { background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 16, marginBottom: 18 };
const titleStyle = { display: 'flex', gap: 8, alignItems: 'center', color: 'var(--color-text-primary)', fontSize: 15, margin: 0 };
const hintStyle = { color: 'var(--color-text-muted)', fontSize: 11, margin: '5px 0 14px' };
const labelStyle = { display: 'block', color: 'var(--color-text-secondary)', fontSize: 11, marginBottom: 5 };
const inputStyle = { width: '100%', boxSizing: 'border-box', background: 'var(--color-bg-primary)', border: '1px solid var(--color-border)', borderRadius: 7, color: 'var(--color-text-primary)', padding: '9px 10px', marginBottom: 8 };
const installmentStyle = { border: '1px solid var(--color-border)', borderRadius: 9, padding: 12, marginTop: 12 };
const actionRow = { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginTop: 8 };
const iconButton = { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 36, height: 36, borderRadius: 7, border: '1px solid var(--color-border)', background: 'var(--color-bg-primary)', color: 'var(--color-text-secondary)', cursor: 'pointer' };
const secondaryButton = { display: 'inline-flex', alignItems: 'center', gap: 6, border: '1px solid var(--color-border)', borderRadius: 7, padding: '8px 11px', background: 'var(--color-bg-primary)', color: 'var(--color-text-secondary)', cursor: 'pointer' };
const primaryButton = { display: 'inline-flex', alignItems: 'center', gap: 6, border: 0, borderRadius: 7, padding: '9px 12px', background: 'var(--tool-hex-4f8ff7)', color: '#fff', cursor: 'pointer', fontWeight: 650 };
const previewStyle = { display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'center', marginTop: 14, borderTop: '1px solid var(--color-border)', paddingTop: 12, color: 'var(--color-text-secondary)', fontSize: 12 };
const messageStyle = color => ({ color, background: `${color}16`, border: `1px solid ${color}55`, borderRadius: 7, padding: '8px 10px', margin: '8px 0', fontSize: 12 });
