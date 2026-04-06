import React, { useState, useEffect } from 'react';
import { useUser } from '../../contexts/UserContext';
import { getAllClasses, getTodayAttendance, bulkMarkAttendance } from '../../lib/api';
import { CheckCircle, XCircle, Clock, RefreshCw, Save } from 'lucide-react';

const STATUS_OPTIONS = [
  { value: 'present', label: 'Present', color: '#10B981' },
  { value: 'absent', label: 'Absent', color: '#EF4444' },
  { value: 'late', label: 'Late', color: '#F59E0B' },
  { value: 'holiday', label: 'Holiday', color: '#64748B' },
];

export default function AttendanceRecorder() {
  const { currentUser } = useUser();
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [attendanceData, setAttendanceData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));

  useEffect(() => { loadClasses(); }, []);
  useEffect(() => { if (selectedClass) loadAttendance(); }, [selectedClass, date]);

  const loadClasses = async () => {
    try {
      const res = await getAllClasses(currentUser);
      if (res.success && res.data.length > 0) {
        setClasses(res.data);
        setSelectedClass(res.data[0].id);
      }
    } catch {}
  };

  const loadAttendance = async () => {
    if (!selectedClass) return;
    setLoading(true);
    try {
      const res = await getTodayAttendance(selectedClass, currentUser);
      if (res.success) setAttendanceData(res.data || []);
    } catch {}
    setLoading(false);
  };

  const markAll = (status) => {
    setAttendanceData(prev => prev.map(s => ({ ...s, status })));
  };

  const toggleStatus = (studentId) => {
    setAttendanceData(prev =>
      prev.map(s => {
        if (s.student_id !== studentId) return s;
        const idx = STATUS_OPTIONS.findIndex(o => o.value === s.status);
        const next = STATUS_OPTIONS[(idx + 1) % STATUS_OPTIONS.length].value;
        return { ...s, status: next };
      })
    );
  };

  const handleSave = async () => {
    if (!selectedClass) return;
    setSaving(true);
    try {
      const records = attendanceData.map(s => ({ student_id: s.student_id, status: s.status }));
      const res = await bulkMarkAttendance({ class_id: selectedClass, date, records }, currentUser);
      if (res.success) { setSaved(true); setTimeout(() => setSaved(false), 3000); }
    } catch {}
    setSaving(false);
  };

  const presentCount = attendanceData.filter(s => s.status === 'present').length;
  const absentCount = attendanceData.filter(s => s.status === 'absent').length;
  const lateCount = attendanceData.filter(s => s.status === 'late').length;

  return (
    <div data-testid="attendance-recorder-tool" style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 22, fontWeight: 600, color: '#fff' }}>Attendance recorder</h1>
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={selectedClass} onChange={e => setSelectedClass(e.target.value)}
          data-testid="class-select"
          style={{ background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '9px 14px', color: '#E2E8F0', fontSize: 13, outline: 'none' }}>
          {classes.map(c => (<option key={c.id} value={c.id}>{c.name}-{c.section}</option>))}
        </select>
        <input type="date" value={date} onChange={e => setDate(e.target.value)}
          data-testid="date-picker"
          style={{ background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '9px 14px', color: '#E2E8F0', fontSize: 13, outline: 'none' }}
        />
        {/* Quick mark buttons */}
        <button onClick={() => markAll('present')} data-testid="mark-all-present" style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 8, padding: '9px 14px', color: '#10B981', fontSize: 12, cursor: 'pointer', fontWeight: 600 }}>
          All Present
        </button>
        <button onClick={() => markAll('absent')} data-testid="mark-all-absent" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '9px 14px', color: '#EF4444', fontSize: 12, cursor: 'pointer', fontWeight: 600 }}>
          All Absent
        </button>
      </div>

      {/* Summary bar */}
      {attendanceData.length > 0 && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          {[
            { count: presentCount, label: 'Present', color: '#10B981' },
            { count: absentCount, label: 'Absent', color: '#EF4444' },
            { count: lateCount, label: 'Late', color: '#F59E0B' },
            { count: attendanceData.length, label: 'Total', color: '#94A3B8' },
          ].map(s => (
            <div key={s.label} style={{ background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '10px 14px', textAlign: 'center', minWidth: 80 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: s.color, fontFamily: 'Outfit, sans-serif' }}>{s.count}</div>
              <div style={{ fontSize: 10, color: '#64748B', fontWeight: 600, textTransform: 'uppercase' }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Student list */}
      <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 12, overflow: 'hidden', marginBottom: 16 }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#64748B' }}>Loading students...</div>
        ) : attendanceData.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#64748B' }}>No students in this class or class not selected</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Roll No.', 'Student Name', 'Status', 'Action'].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.06em', background: '#0F0F1A', borderBottom: '1px solid #222230' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {attendanceData.map((s, i) => {
                const statusOpt = STATUS_OPTIONS.find(o => o.value === s.status) || STATUS_OPTIONS[0];
                return (
                  <tr key={s.student_id || i} style={{ borderBottom: i < attendanceData.length - 1 ? '1px solid #1A1A24' : 'none' }}>
                    <td style={{ padding: '9px 16px', fontSize: 12, color: '#64748B', fontFamily: 'JetBrains Mono, monospace' }}>{s.roll_number || '-'}</td>
                    <td style={{ padding: '9px 16px', fontSize: 13, color: '#E2E8F0', fontWeight: 500 }}>{s.name}</td>
                    <td style={{ padding: '9px 16px' }}>
                      <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 5, background: `${statusOpt.color}15`, color: statusOpt.color }}>
                        {statusOpt.label}
                      </span>
                    </td>
                    <td style={{ padding: '9px 16px' }}>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {STATUS_OPTIONS.slice(0, 3).map(opt => (
                          <button key={opt.value} onClick={() => setAttendanceData(prev => prev.map(st => st.student_id === s.student_id ? { ...st, status: opt.value } : st))}
                            data-testid={`mark-${s.student_id}-${opt.value}`}
                            style={{
                              background: s.status === opt.value ? `${opt.color}20` : 'transparent',
                              border: `1px solid ${s.status === opt.value ? opt.color + '50' : '#222230'}`,
                              borderRadius: 5, padding: '4px 8px', color: s.status === opt.value ? opt.color : '#64748B',
                              fontSize: 10, cursor: 'pointer', fontWeight: 600, transition: 'all 0.1s',
                            }}>
                            {opt.label[0]}
                          </button>
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Save button */}
      {attendanceData.length > 0 && (
        <button data-testid="save-attendance-btn" onClick={handleSave} disabled={saving}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: saved ? '#10B981' : saving ? '#1E3A5F' : '#3B82F6',
            border: 'none', borderRadius: 8, padding: '11px 24px',
            color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'background 0.2s',
          }}>
          {saved ? <CheckCircle size={14} /> : <Save size={14} />}
          {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Attendance'}
        </button>
      )}
    </div>
  );
}
