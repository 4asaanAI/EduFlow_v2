/**
 * Story 17: Timetable Management — weekly grid with CRUD
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useUser } from '../../contexts/UserContext';
import { useTheme } from '../../contexts/ThemeContext';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, ActionBtn, FormField } from './ToolPage';
import { Plus, Trash2, Edit2, Save, X } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function h() { return getAuthHeaders(); }

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const PERIODS = [1, 2, 3, 4, 5, 6, 7, 8];

export default function TimetableBuilder() {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [staff, setStaff] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [editSlot, setEditSlot] = useState(null); // { day, period }
  const [editForm, setEditForm] = useState({ subject_id: '', teacher_id: '', start_time: '', end_time: '', room: '' });
  const [saving, setSaving] = useState(false);

  const canEdit = currentUser.role === 'owner' || currentUser.role === 'admin';

  const bg = isDark ? 'var(--tool-hex-1a1a1a)' : 'var(--tool-hex-f5f5f5)';
  const card = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-fff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-888)' : 'var(--tool-hex-737373)';
  const accent = 'var(--tool-hex-4f8ff7)';

  useEffect(() => {
    Promise.all([
      fetch(`${API}/settings/classes`, { headers: h() }).then(r => r.json()),
      fetch(`${API}/staff?limit=100`, { headers: h() }).then(r => r.json()),
    ]).then(([clsRes, staffRes]) => {
      if (clsRes.success) setClasses(clsRes.data || []);
      if (staffRes.success) setStaff((staffRes.data || []).filter(s => s.staff_type === 'teacher' || s.sub_category === 'teacher'));
    }).catch(() => {});
  }, []);

  const loadTimetable = useCallback(async (classId) => {
    if (!classId) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API}/academics/timetable/${classId}`, { headers: h() });
      const data = await res.json();
      if (data.success) setSlots(data.data || []);
      else setError(data.detail || 'Failed to load timetable');
    } catch { setError('Network error'); }
    setLoading(false);
  }, []);

  useEffect(() => { loadTimetable(selectedClass); }, [selectedClass, loadTimetable]);

  const getSlot = (day, period) => slots.find(s => s.day_of_week === day && s.period_number === period);

  const openEdit = (day, period) => {
    if (!canEdit) return;
    const existing = getSlot(day, period);
    setEditSlot({ day, period, id: existing?.id });
    setEditForm({
      subject_id: existing?.subject_id || '',
      teacher_id: existing?.teacher_id || '',
      start_time: existing?.start_time || '',
      end_time: existing?.end_time || '',
      room: existing?.room || '',
    });
  };

  const saveSlot = async () => {
    if (!selectedClass || !editSlot) return;
    setSaving(true);
    setError('');
    try {
      const payload = {
        class_id: selectedClass,
        day_of_week: editSlot.day,
        period_number: editSlot.period,
        ...editForm,
      };
      if (editSlot.id) {
        await fetch(`${API}/academics/timetable/${editSlot.id}`, {
          method: 'PATCH',
          headers: { ...h(), 'Content-Type': 'application/json' },
          body: JSON.stringify(editForm),
        });
      } else {
        await fetch(`${API}/academics/timetable`, {
          method: 'POST',
          headers: { ...h(), 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }
      setEditSlot(null);
      loadTimetable(selectedClass);
    } catch { setError('Failed to save'); }
    setSaving(false);
  };

  const deleteSlot = async (slotId) => {
    if (!slotId) return;
    await fetch(`${API}/academics/timetable/${slotId}`, { method: 'DELETE', headers: h() });
    loadTimetable(selectedClass);
  };

  const subjectName = (id) => {
    const s = subjects.find(s => s.id === id);
    if (s) return s.name;
    // Try to get from slots
    const slot = slots.find(sl => sl.subject_id === id);
    return slot?.subject_name || id?.slice(0, 8) || '—';
  };

  const teacherName = (id) => {
    const t = staff.find(s => s.id === id);
    return t ? t.name : (id?.slice(0, 8) || '—');
  };

  return (
    <ToolPage title="Timetable" subtitle={selectedClass ? `Viewing ${classes.find(c => c.id === selectedClass)?.name || ''}-${classes.find(c => c.id === selectedClass)?.section || ''}` : 'Select a class'} onRefresh={() => loadTimetable(selectedClass)} loading={loading}>
      {error && <div style={{ color: 'var(--tool-hex-f87171)', fontSize: 13, marginBottom: 12 }}>{error}</div>}

      {/* Class selector */}
      <div style={{ marginBottom: 20 }}>
        <select
          value={selectedClass}
          onChange={e => setSelectedClass(e.target.value)}
          style={{ background: card, border: `1px solid ${border}`, borderRadius: 9, padding: '9px 14px', color: text, fontSize: 13, outline: 'none', minWidth: 200 }}
        >
          <option value="">Select class...</option>
          {classes.map(c => (
            <option key={c.id} value={c.id}>{c.name}-{c.section}</option>
          ))}
        </select>
      </div>

      {!selectedClass ? (
        <div style={{ color: muted, textAlign: 'center', padding: 40 }}>Select a class to view and edit its timetable.</div>
      ) : (
        <>
          {/* Weekly grid */}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{ padding: '8px 12px', textAlign: 'left', color: muted, fontWeight: 600, fontSize: 11, width: 90, background: isDark ? 'var(--tool-hex-161616)' : 'var(--tool-hex-f9f9f9)', border: `1px solid ${border}` }}>Period</th>
                  {DAYS.map(day => (
                    <th key={day} style={{ padding: '8px 12px', textAlign: 'center', color: muted, fontWeight: 600, fontSize: 11, background: isDark ? 'var(--tool-hex-161616)' : 'var(--tool-hex-f9f9f9)', border: `1px solid ${border}` }}>
                      {day.slice(0, 3)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {PERIODS.map(period => (
                  <tr key={period}>
                    <td style={{ padding: '8px 12px', color: muted, fontWeight: 500, background: isDark ? 'var(--tool-hex-161616)' : 'var(--tool-hex-f9f9f9)', border: `1px solid ${border}`, fontSize: 11 }}>P{period}</td>
                    {DAYS.map((day, dayIdx) => {
                      const slot = getSlot(dayIdx, period);
                      return (
                        <td
                          key={day}
                          onClick={() => openEdit(dayIdx, period)}
                          style={{
                            padding: '6px 8px', border: `1px solid ${border}`, cursor: canEdit ? 'pointer' : 'default',
                            background: slot ? (isDark ? 'var(--tool-hex-1e2433)' : 'var(--tool-hex-eff6ff)') : card,
                            verticalAlign: 'top', minWidth: 90,
                            transition: 'background 0.12s',
                          }}
                          onMouseEnter={e => canEdit && !slot && (e.currentTarget.style.background = isDark ? 'var(--tool-hex-222)' : 'var(--tool-hex-f9f9f9)')}
                          onMouseLeave={e => canEdit && !slot && (e.currentTarget.style.background = card)}
                        >
                          {slot ? (
                            <div>
                              <div style={{ fontWeight: 600, color: accent, fontSize: 12, marginBottom: 2 }}>
                                {slot.subject_name || subjectName(slot.subject_id)}
                              </div>
                              <div style={{ color: muted, fontSize: 10 }}>{teacherName(slot.teacher_id)}</div>
                              {slot.start_time && <div style={{ color: muted, fontSize: 10 }}>{slot.start_time}–{slot.end_time}</div>}
                              {canEdit && (
                                <button
                                  onClick={e => { e.stopPropagation(); deleteSlot(slot.id); }}
                                  style={{ marginTop: 4, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--tool-hex-f87171)', padding: 0 }}
                                  title="Remove slot"
                                >
                                  <Trash2 size={10} />
                                </button>
                              )}
                            </div>
                          ) : (
                            canEdit ? <div style={{ color: isDark ? 'var(--tool-hex-333)' : 'var(--tool-hex-d4d4d4)', fontSize: 11, textAlign: 'center' }}>+</div> : null
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Edit modal */}
          {editSlot && (
            <div style={{
              position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
              background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <div style={{ background: card, borderRadius: 14, padding: 24, width: 380, maxWidth: '90vw', border: `1px solid ${border}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                  <h3 style={{ fontSize: 15, fontWeight: 700, color: text, margin: 0 }}>
                    {DAYS[editSlot.day]} — Period {editSlot.period}
                  </h3>
                  <button onClick={() => setEditSlot(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: muted }}><X size={16} /></button>
                </div>
                <FormField
                  label="Subject"
                  value={editForm.subject_id}
                  onChange={v => setEditForm(p => ({ ...p, subject_id: v }))}
                  placeholder="Subject name or ID"
                />
                <FormField
                  label="Teacher"
                  type="select"
                  value={editForm.teacher_id}
                  onChange={v => setEditForm(p => ({ ...p, teacher_id: v }))}
                  options={[{ value: '', label: 'Select teacher...' }, ...staff.map(s => ({ value: s.id, label: s.name }))]}
                />
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <FormField label="Start Time" type="time" value={editForm.start_time} onChange={v => setEditForm(p => ({ ...p, start_time: v }))} />
                  <FormField label="End Time" type="time" value={editForm.end_time} onChange={v => setEditForm(p => ({ ...p, end_time: v }))} />
                </div>
                <FormField label="Room" value={editForm.room} onChange={v => setEditForm(p => ({ ...p, room: v }))} placeholder="Room number" />
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <ActionBtn label={saving ? 'Saving...' : 'Save'} icon={<Save size={11} />} onClick={saveSlot} disabled={saving} />
                  <ActionBtn label="Cancel" variant="secondary" onClick={() => setEditSlot(null)} />
                </div>
              </div>
            </div>
          )}

          {canEdit && (
            <p style={{ fontSize: 11, color: muted, marginTop: 12 }}>
              Click any cell to add or edit. Click the trash icon to remove a slot.
            </p>
          )}
        </>
      )}
    </ToolPage>
  );
}
