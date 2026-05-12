import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  Download,
  History,
  RefreshCw,
  Save,
  ShieldAlert,
} from 'lucide-react';
import {
  bulkMarkAttendance,
  correctAttendance,
  createManualAttendance,
  getAllClasses,
  getAttendanceHistory,
  getTodayAttendance,
} from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const STATUS_OPTIONS = [
  { value: 'present', label: 'Present', color: '#34d399' },
  { value: 'absent', label: 'Absent', color: '#f87171' },
  { value: 'late', label: 'Late', color: '#fbbf24' },
  { value: 'holiday', label: 'Holiday', color: 'var(--c-faint)' },
];

const blankManual = { student_id: '', status: 'present', reason: '' };

function badge(status) {
  return STATUS_OPTIONS.find(o => o.value === status) || { label: status || 'Not marked', color: 'var(--c-faint)' };
}

export default function AttendanceRecorder() {
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [records, setRecords] = useState([]);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [correctionId, setCorrectionId] = useState('');
  const [correctionReason, setCorrectionReason] = useState('');
  const [manual, setManual] = useState(blankManual);
  const [history, setHistory] = useState(null);

  useEffect(() => {
    let active = true;
    async function loadClasses() {
      setLoading(true);
      setError('');
      try {
        const res = await getAllClasses();
        if (!active) return;
        if (!res.success) throw new Error(res.detail || 'Unable to load classes');
        setClasses(res.data || []);
        setSelectedClass(res.data?.[0]?.id || '');
      } catch (err) {
        if (active) setError(err.message || 'Unable to load classes');
      } finally {
        if (active) setLoading(false);
      }
    }
    loadClasses();
    return () => { active = false; };
  }, []);

  const selectedClassLabel = useMemo(() => {
    const item = classes.find(c => c.id === selectedClass);
    return item ? `${item.name}-${item.section}` : '';
  }, [classes, selectedClass]);

  const loadAttendance = useCallback(async () => {
    setLoading(true);
    setError('');
    setHistory(null);
    try {
      const res = await getTodayAttendance(selectedClass, date);
      if (!res.success) throw new Error(res.detail || 'Unable to load attendance');
      setRecords((res.data || []).map(row => ({ ...row, original_status: row.status })));
    } catch (err) {
      setError(err.message || 'Unable to load attendance');
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }, [selectedClass, date]);

  useEffect(() => {
    if (selectedClass) loadAttendance();
  }, [selectedClass, date, loadAttendance]);

  function updateStatus(studentId, status) {
    setRecords(prev => prev.map(row => row.student_id === studentId ? { ...row, status } : row));
  }

  function markAll(status) {
    setRecords(prev => prev.map(row => ({ ...row, status })));
  }

  async function saveBulk() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const changedExisting = records.filter(row => row.attendance_id && row.status !== row.original_status);
      if (changedExisting.length && !correctionReason.trim()) {
        throw new Error('Correction reason is required before changing saved attendance records.');
      }

      const newRecords = records.filter(row => !row.attendance_id);
      if (newRecords.length) {
        const res = await bulkMarkAttendance({
          class_id: selectedClass,
          date,
          records: newRecords.map(row => ({ student_id: row.student_id, status: row.status })),
        });
        if (!res.success) throw new Error(res.detail || 'Unable to save attendance');
      }

      for (const row of changedExisting) {
        const res = await correctAttendance(row.attendance_id, {
          status: row.status,
          correction_type: row.status,
          reason: correctionReason.trim(),
        });
        if (!res.success) throw new Error(res.detail || `Unable to correct ${row.name}`);
      }

      setNotice('Attendance saved.');
      setCorrectionReason('');
      await loadAttendance();
    } catch (err) {
      setError(err.message || 'Unable to save attendance');
    } finally {
      setSaving(false);
    }
  }

  async function saveManual() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      if (!manual.student_id || !manual.reason.trim()) {
        throw new Error('Manual entry requires a student and reason.');
      }
      const res = await createManualAttendance({
        class_id: selectedClass,
        date,
        student_id: manual.student_id,
        status: manual.status,
        reason: manual.reason.trim(),
      });
      if (!res.success) throw new Error(res.detail || 'Manual attendance could not be saved');
      setManual(blankManual);
      setNotice('Manual attendance entry saved.');
      await loadAttendance();
    } catch (err) {
      setError(err.message || 'Manual attendance could not be saved');
    } finally {
      setSaving(false);
    }
  }

  async function loadHistory(attendanceId) {
    setCorrectionId(attendanceId);
    setHistory(null);
    setError('');
    try {
      const res = await getAttendanceHistory(attendanceId);
      if (!res.success) throw new Error(res.detail || 'Unable to load correction history');
      setHistory(res.data);
    } catch (err) {
      setError(err.message || 'Unable to load correction history');
    }
  }

  async function exportAttendanceCSV() {
    if (!selectedClass || !date) return;
    setError('');
    try {
      const month = date.slice(0, 7);
      const res = await fetch(`${API}/attendance/export?class_id=${selectedClass}&month=${month}&format=csv`, { headers: getAuthHeaders() });
      if (!res.ok) throw new Error('Attendance export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `attendance-${selectedClassLabel || selectedClass}-${month}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || 'Attendance export failed');
    }
  }

  const counts = STATUS_OPTIONS.reduce((acc, opt) => {
    acc[opt.value] = records.filter(row => row.status === opt.value).length;
    return acc;
  }, {});

  return (
    <div data-testid="attendance-recorder-tool" style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontFamily: 'Inter, sans-serif', fontSize: 22, fontWeight: 650, color: 'var(--c-text)', margin: 0 }}>Attendance recorder</h1>
          <p style={{ margin: '6px 0 0', color: 'var(--c-faint)', fontSize: 12 }}>{selectedClassLabel || 'Select a class'} - {date}</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={exportAttendanceCSV} disabled={!selectedClass} title="Export month attendance as CSV"
            style={{ minHeight: 44, minWidth: 44, display: 'grid', placeItems: 'center', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, color: 'var(--c-text)', cursor: 'pointer' }}>
            <Download size={16} />
          </button>
          <button onClick={loadAttendance} disabled={!selectedClass || loading} title="Refresh attendance"
            style={{ minHeight: 44, minWidth: 44, display: 'grid', placeItems: 'center', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, color: 'var(--c-text)', cursor: 'pointer' }}>
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {error && <div role="alert" style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 14, padding: 12, border: '1px solid rgba(248,113,113,.35)', borderRadius: 8, color: '#f87171', background: 'rgba(248,113,113,.08)', fontSize: 13 }}><AlertCircle size={16} />{error}</div>}
      {notice && <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 14, padding: 12, border: '1px solid rgba(52,211,153,.35)', borderRadius: 8, color: '#34d399', background: 'rgba(52,211,153,.08)', fontSize: 13 }}><CheckCircle size={16} />{notice}</div>}

      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={selectedClass} onChange={e => setSelectedClass(e.target.value)} data-testid="class-select"
          style={{ minHeight: 44, background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: '9px 14px', color: 'var(--c-text)', fontSize: 13, outline: 'none' }}>
          {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
        </select>
        <input type="date" value={date} onChange={e => setDate(e.target.value)} data-testid="date-picker"
          style={{ minHeight: 44, background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: '9px 14px', color: 'var(--c-text)', fontSize: 13, outline: 'none' }}
        />
        <button onClick={() => markAll('present')} data-testid="mark-all-present" style={quickButton('#34d399')}>All Present</button>
        <button onClick={() => markAll('absent')} data-testid="mark-all-absent" style={quickButton('#f87171')}>All Absent</button>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        {STATUS_OPTIONS.slice(0, 3).map(opt => (
          <div key={opt.value} style={{ minWidth: 92, background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: '10px 14px' }}>
            <div style={{ color: opt.color, fontSize: 18, fontWeight: 750 }}>{counts[opt.value] || 0}</div>
            <div style={{ color: 'var(--c-faint)', fontSize: 10, fontWeight: 700, textTransform: 'uppercase' }}>{opt.label}</div>
          </div>
        ))}
      </div>

      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, overflow: 'hidden', marginBottom: 16 }}>
        {loading ? (
          <div style={{ padding: 36, color: 'var(--c-faint)', textAlign: 'center', fontSize: 13 }}>Loading attendance...</div>
        ) : records.length === 0 ? (
          <div style={{ padding: 36, color: 'var(--c-faint)', textAlign: 'center', fontSize: 13 }}>No students found for this class and date.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Roll', 'Student', 'Current', 'Mark', 'Audit'].map(head => (
                  <th key={head} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase', background: 'var(--c-deep)', borderBottom: '1px solid var(--c-border)' }}>{head}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((row, i) => {
                const current = badge(row.status);
                const dirty = row.attendance_id && row.status !== row.original_status;
                return (
                  <tr key={row.student_id} style={{ borderBottom: i < records.length - 1 ? '1px solid var(--c-border)' : 'none' }}>
                    <td style={cellStyle('mono')}>{row.roll_number || '-'}</td>
                    <td style={cellStyle()}>{row.name}</td>
                    <td style={cellStyle()}><span style={{ fontSize: 11, fontWeight: 700, padding: '3px 9px', borderRadius: 5, background: `${current.color}18`, color: current.color }}>{current.label}{dirty ? ' *' : ''}</span></td>
                    <td style={cellStyle()}>
                      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                        {STATUS_OPTIONS.slice(0, 3).map(opt => (
                          <button key={opt.value} onClick={() => updateStatus(row.student_id, opt.value)}
                            data-testid={`mark-${row.student_id}-${opt.value}`}
                            style={{ minWidth: 34, minHeight: 34, background: row.status === opt.value ? `${opt.color}20` : 'transparent', border: `1px solid ${row.status === opt.value ? opt.color + '60' : 'var(--c-border)'}`, borderRadius: 6, color: row.status === opt.value ? opt.color : 'var(--c-faint)', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>
                            {opt.label[0]}
                          </button>
                        ))}
                      </div>
                    </td>
                    <td style={cellStyle()}>
                      {row.attendance_id ? (
                        <button onClick={() => loadHistory(row.attendance_id)} title="View correction history" style={iconButton(correctionId === row.attendance_id)}>
                          <History size={15} />
                        </button>
                      ) : <span style={{ color: 'var(--c-faint)', fontSize: 11 }}>New</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14, marginBottom: 16 }}>
        <section style={panelStyle}>
          <h2 style={panelTitle}><ShieldAlert size={16} />Correction reason</h2>
          <textarea value={correctionReason} onChange={e => setCorrectionReason(e.target.value)} data-testid="attendance-correction-reason"
            placeholder="Required when changing a saved attendance record"
            style={textareaStyle}
          />
        </section>

        <section style={panelStyle}>
          <h2 style={panelTitle}>Manual fallback</h2>
          <div style={{ display: 'grid', gap: 8 }}>
            <select value={manual.student_id} onChange={e => setManual(prev => ({ ...prev, student_id: e.target.value }))} style={inputStyle}>
              <option value="">Select student</option>
              {records.map(row => <option key={row.student_id} value={row.student_id}>{row.name}</option>)}
            </select>
            <select value={manual.status} onChange={e => setManual(prev => ({ ...prev, status: e.target.value }))} style={inputStyle}>
              {STATUS_OPTIONS.slice(0, 3).map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
            <textarea value={manual.reason} onChange={e => setManual(prev => ({ ...prev, reason: e.target.value }))} placeholder="Reason required" style={textareaStyle} />
            <button onClick={saveManual} disabled={saving || !selectedClass} style={primaryButton('#6366f1')}>Save manual entry</button>
          </div>
        </section>
      </div>

      {history && (
        <section style={{ ...panelStyle, marginBottom: 16 }}>
          <h2 style={panelTitle}>Correction history</h2>
          <div style={{ color: 'var(--c-faint)', fontSize: 12, marginBottom: 8 }}>Original status: {history.original?.status || '-'}</div>
          {(history.corrections || []).length === 0 ? (
            <div style={{ color: 'var(--c-faint)', fontSize: 12 }}>No corrections recorded.</div>
          ) : history.corrections.map(item => (
            <div key={item.id} style={{ padding: '8px 0', borderTop: '1px solid var(--c-border)', color: 'var(--c-text)', fontSize: 12 }}>
              {item.previous_status} to {item.new_status} - {item.reason}
            </div>
          ))}
        </section>
      )}

      {records.length > 0 && (
        <button data-testid="save-attendance-btn" onClick={saveBulk} disabled={saving}
          style={primaryButton(saving ? '#1e3a5f' : '#4f8ff7')}>
          <Save size={15} />
          {saving ? 'Saving...' : 'Save Attendance'}
        </button>
      )}
    </div>
  );
}

const cellStyle = mode => ({
  padding: '10px 14px',
  fontSize: 13,
  color: mode === 'mono' ? 'var(--c-faint)' : 'var(--c-text)',
  fontFamily: mode === 'mono' ? 'JetBrains Mono, monospace' : 'Inter, sans-serif',
  verticalAlign: 'middle',
});

const quickButton = color => ({
  minHeight: 44,
  background: `${color}18`,
  border: `1px solid ${color}55`,
  borderRadius: 8,
  padding: '9px 14px',
  color,
  fontSize: 12,
  cursor: 'pointer',
  fontWeight: 700,
});

const panelStyle = {
  background: 'var(--c-bg)',
  border: '1px solid var(--c-border)',
  borderRadius: 8,
  padding: 14,
};

const panelTitle = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  margin: '0 0 10px',
  color: 'var(--c-text)',
  fontSize: 13,
  fontWeight: 700,
};

const inputStyle = {
  minHeight: 40,
  background: 'var(--c-deep)',
  border: '1px solid var(--c-border)',
  borderRadius: 7,
  padding: '8px 10px',
  color: 'var(--c-text)',
  fontSize: 13,
  outline: 'none',
};

const textareaStyle = {
  width: '100%',
  minHeight: 82,
  resize: 'vertical',
  background: 'var(--c-deep)',
  border: '1px solid var(--c-border)',
  borderRadius: 7,
  padding: 10,
  color: 'var(--c-text)',
  fontSize: 13,
  outline: 'none',
  boxSizing: 'border-box',
};

const primaryButton = background => ({
  minHeight: 44,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 8,
  background,
  border: 'none',
  borderRadius: 8,
  padding: '11px 20px',
  color: '#fff',
  fontSize: 13,
  fontWeight: 700,
  cursor: 'pointer',
});

const iconButton = active => ({
  minWidth: 36,
  minHeight: 36,
  display: 'grid',
  placeItems: 'center',
  background: active ? 'rgba(79,143,247,.16)' : 'transparent',
  border: `1px solid ${active ? 'rgba(79,143,247,.45)' : 'var(--c-border)'}`,
  borderRadius: 7,
  color: active ? '#4f8ff7' : 'var(--c-faint)',
  cursor: 'pointer',
});
