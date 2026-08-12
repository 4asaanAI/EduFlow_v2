/**
 * Story 17: Timetable Management - weekly grid with CRUD
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useUser } from '../../contexts/UserContext';
import { useTheme } from '../../contexts/ThemeContext';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, ActionBtn, FormField } from './ToolPage';
import { Plus, Trash2, Edit2, Save, X, Wand2 } from 'lucide-react';
import ExportButton from '../ui/ExportButton';
import { API, apiFetch } from '../../lib/api';

function h() { return getAuthHeaders(); }

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const PERIODS = [1, 2, 3, 4, 5, 6, 7, 8];

/** The timetable keeps its grid shape in a file: a column per day. */
const TIMETABLE_EXPORT_COLUMNS = [
  { key: 'period', label: 'Period' },
  ...DAYS.map((day) => ({ key: day, label: day })),
];

/**
 * Work the week out, instead of typing it in.
 *
 * Ported from the standalone timetable builder Abhimanyu supplied on 2026-08-12. The
 * search runs on the SERVER, where it can see what every other class has already
 * booked - see `services/timetable_solver.py`. Doing it here would mean shipping the
 * whole school's timetables to the browser and would still get teacher clashes wrong.
 *
 * THE RULE ON THIS PANEL: generating shows you a week. It does not save one. The
 * saved timetable is what the substitution plan reads when a teacher is away, so the
 * person looks at the proposal, sees its marks out of 100, and then decides. Nothing
 * reaches the school's records without that second, deliberate tap.
 */
function TimetableGenerator({ classId, className, subjects, days, periods, onApplied, styles }) {
  const { card, border, text, muted, accent } = styles;
  const [periodsPerDay, setPeriodsPerDay] = React.useState(8);
  const [perWeek, setPerWeek] = React.useState({});
  const [morning, setMorning] = React.useState({});
  const [proposal, setProposal] = React.useState(null);
  const [problems, setProblems] = React.useState([]);
  const [busy, setBusy] = React.useState('');
  const [note, setNote] = React.useState('');
  const [error, setError] = React.useState('');

  // A new class means the previous class's proposal is meaningless. Leaving it on
  // screen is how somebody applies 5A's week to 6B.
  React.useEffect(() => {
    setProposal(null);
    setProblems([]);
    setNote('');
    setError('');
    setPerWeek({});
    setMorning({});
  }, [classId]);

  const asked = Object.values(perWeek).reduce((sum, n) => sum + (Number(n) || 0), 0);
  const available = days.length * periodsPerDay;

  async function generate() {
    setBusy('generate');
    setError('');
    setNote('');
    setProblems([]);
    try {
      const res = await apiFetch(`${API}/academics/timetable/generate`, {
        method: 'POST',
        headers: { ...h(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          class_id: classId,
          days,
          periods_per_day: periodsPerDay,
          periods_per_week: perWeek,
          prefer_morning: Object.keys(morning).filter((id) => morning[id]),
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'The timetable could not be worked out.');
      if (body.data.solved) {
        setProposal(body.data);
      } else {
        setProposal(null);
        // The server's own wording says what to change. Replacing it with "failed"
        // would throw away the only useful part of the answer.
        setProblems(body.data.problems || []);
      }
    } catch (err) {
      setError(err.message || 'The timetable could not be worked out.');
    }
    setBusy('');
  }

  async function apply() {
    if (!proposal) return;
    setBusy('apply');
    setError('');
    try {
      const res = await apiFetch(`${API}/academics/timetable/apply`, {
        method: 'POST',
        headers: { ...h(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ class_id: classId, slots: proposal.slots }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'The timetable could not be saved.');
      setNote(
        `Saved. ${className} now has ${body.meta.count} periods`
        + (body.meta.replaced ? `, replacing ${body.meta.replaced}.` : '.'),
      );
      setProposal(null);
      onApplied();
    } catch (err) {
      setError(err.message || 'The timetable could not be saved.');
    }
    setBusy('');
  }

  const cell = {
    background: card, border: `1px solid ${border}`, borderRadius: 7,
    padding: '6px 9px', color: text, fontSize: 12, width: 70,
  };

  return (
    <div
      data-testid="timetable-generator"
      style={{ background: card, border: `1px solid ${border}`, borderRadius: 12, padding: 16, marginBottom: 20 }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
        <div>
          <span style={{ fontWeight: 700, fontSize: 14, color: text, display: 'flex', alignItems: 'center', gap: 7 }}>
            <Wand2 size={15} color={accent} /> Work out a timetable
          </span>
          <div style={{ color: muted, fontSize: 12, marginTop: 4 }}>
            Say how many periods a week each subject needs. Nothing is saved until you
            look at the result and choose to keep it.
          </div>
        </div>
        <label style={{ color: muted, fontSize: 12, display: 'flex', alignItems: 'center', gap: 7 }}>
          Periods a day
          <input
            type="number" min="1" max="12" value={periodsPerDay}
            data-testid="generator-periods-per-day"
            onChange={(e) => setPeriodsPerDay(Math.max(1, Math.min(12, Number(e.target.value) || 1)))}
            style={cell}
          />
        </label>
      </div>

      {subjects.length === 0 ? (
        <div style={{ color: muted, fontSize: 12 }}>
          This class has no subjects set up yet, so there is nothing to place. Add its
          subjects first, each with the teacher who takes it.
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 12 }}>
            {subjects.map((sub) => (
              <div
                key={sub.id}
                style={{ border: `1px solid ${border}`, borderRadius: 9, padding: '8px 10px', minWidth: 170 }}
              >
                <div style={{ color: text, fontSize: 12, fontWeight: 600, marginBottom: 6 }}>{sub.name}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input
                    type="number" min="0" max="40" placeholder="0"
                    data-testid={`generator-count-${sub.id}`}
                    value={perWeek[sub.id] ?? ''}
                    onChange={(e) => setPerWeek((p) => ({ ...p, [sub.id]: e.target.value }))}
                    style={cell}
                  />
                  <label style={{ color: muted, fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <input
                      type="checkbox"
                      checked={!!morning[sub.id]}
                      onChange={(e) => setMorning((m) => ({ ...m, [sub.id]: e.target.checked }))}
                    />
                    Morning
                  </label>
                </div>
              </div>
            ))}
          </div>

          {/* The two numbers side by side, because "asked for more than the week
              holds" is the commonest reason this cannot be done, and seeing it before
              pressing the button saves the person a round trip. */}
          <div style={{ color: asked > available ? 'var(--tool-hex-f87171)' : muted, fontSize: 12, marginBottom: 12 }}>
            {asked} period{asked === 1 ? '' : 's'} asked for, {available} available in the week.
            {asked > available ? ' That is more than the week holds.' : ''}
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <ActionBtn
              label={busy === 'generate' ? 'Working it out...' : 'Work it out'}
              icon={<Wand2 size={13} />}
              onClick={generate}
              disabled={!!busy || asked === 0}
              data-testid="generator-run"
            />
            {proposal && (
              <ActionBtn
                label={busy === 'apply' ? 'Saving...' : 'Use this timetable'}
                icon={<Save size={13} />}
                onClick={apply}
                disabled={!!busy}
                data-testid="generator-apply"
              />
            )}
          </div>
        </>
      )}

      {error && (
        <div role="alert" data-testid="generator-error" style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginTop: 10 }}>
          {error}
        </div>
      )}

      {problems.length > 0 && (
        <div data-testid="generator-problems" style={{ marginTop: 12 }}>
          <div style={{ color: 'var(--tool-hex-fbbf24)', fontSize: 12, fontWeight: 600, marginBottom: 5 }}>
            No timetable fits all of this at once:
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, color: muted, fontSize: 12, lineHeight: 1.6 }}>
            {problems.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </div>
      )}

      {note && (
        <div role="status" data-testid="generator-note" style={{ color: 'var(--tool-hex-34d399)', fontSize: 12, marginTop: 10 }}>
          {note}
        </div>
      )}

      {proposal && (
        <div data-testid="generator-proposal" style={{ marginTop: 14, borderTop: `1px solid ${border}`, paddingTop: 12 }}>
          <div style={{ color: text, fontSize: 12, fontWeight: 600, marginBottom: 8 }}>
            {proposal.slots.length} periods worked out. Nothing is saved yet.
          </div>
          {/* The four marks, in words rather than only a number, so a person can see
              WHICH part is weak and change that one thing rather than guessing. */}
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 11, color: muted, marginBottom: 10 }}>
            <span style={{ color: text, fontWeight: 700 }}>Overall {proposal.score.total}/100</span>
            <span>Spread across the week {proposal.score.distribution}</span>
            <span>Teachers&apos; preferred periods {proposal.score.teacher_preference}</span>
            <span>Morning subjects in the morning {proposal.score.morning_preference}</span>
            <span>No subject twice running {proposal.score.consecutive_avoidance}</span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr>
                  <th style={{ padding: '6px 8px', textAlign: 'left', color: muted, border: `1px solid ${border}` }}>Period</th>
                  {days.map((d) => (
                    <th key={d} style={{ padding: '6px 8px', color: muted, border: `1px solid ${border}` }}>{d.slice(0, 3)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: periodsPerDay }, (_, i) => i + 1).map((period) => (
                  <tr key={period}>
                    <td style={{ padding: '6px 8px', color: muted, border: `1px solid ${border}` }}>P{period}</td>
                    {days.map((day, dayIdx) => {
                      const found = proposal.slots.find(
                        (s) => s.day_of_week === dayIdx && s.period_number === period,
                      );
                      return (
                        <td key={day} style={{ padding: '6px 8px', border: `1px solid ${border}`, color: text }}>
                          {found ? (
                            <>
                              <div style={{ fontWeight: 600 }}>{found.subject_name}</div>
                              <div style={{ color: muted, fontSize: 10 }}>{found.teacher_name}</div>
                            </>
                          ) : (
                            <span style={{ color: muted }}>-</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

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
  // Working a whole week out is Adesh's tool - he writes the school's timetables
  // himself (Abhimanyu, 2026-08-12) - and Aman's, because the owner is never shut out
  // of his own school. The server gate is the one that decides; this only avoids
  // showing somebody a button that would refuse them. Lalit keeps the screen and can
  // still hand-edit a period, exactly as he does today.
  const canGenerate = currentUser.role === 'owner'
    || (currentUser.role === 'admin' && currentUser.sub_category === 'principal');

  // Use --c-* semantic variables that work correctly for both themes
  const bg = 'var(--c-deep)';
  const card = 'var(--c-bg)';
  const border = 'var(--c-border)';
  const text = 'var(--c-text)';
  const muted = 'var(--c-muted)';
  const accent = 'var(--tool-hex-4f8ff7)';

  useEffect(() => {
    // Use allSettled so a failing staff fetch doesn't block class list from loading
    Promise.allSettled([
      apiFetch(`${API}/settings/classes`, { headers: h() }).then(r => r.json()),
      apiFetch(`${API}/staff/?limit=100`, { headers: h() }).then(r => r.json()),
    ]).then(([clsResult, staffResult]) => {
      if (clsResult.status === 'fulfilled' && clsResult.value?.success) setClasses(clsResult.value.data || []);
      if (staffResult.status === 'fulfilled' && staffResult.value?.success) {
        setStaff((staffResult.value.data || []).filter(s => s.staff_type === 'teacher' || s.sub_category === 'teacher'));
      }
    });
  }, []);

  const loadTimetable = useCallback(async (classId) => {
    if (!classId) return;
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch(`${API}/academics/timetable/${classId}`, { headers: h() });
      const data = await res.json();
      if (data.success) setSlots(data.data || []);
      else setError(data.detail || 'Failed to load timetable');
    } catch { setError('Network error'); }
    setLoading(false);
  }, []);

  useEffect(() => { loadTimetable(selectedClass); }, [selectedClass, loadTimetable]);

  useEffect(() => {
    if (!selectedClass) {
      setSubjects([]);
      return;
    }
    apiFetch(`${API}/academics/subjects?class_id=${encodeURIComponent(selectedClass)}`, { headers: h() })
      .then(r => r.json())
      .then(data => setSubjects(data.success ? (data.data || []) : []))
      .catch(() => setSubjects([]));
  }, [selectedClass]);

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
      let response;
      if (editSlot.id) {
        response = await apiFetch(`${API}/academics/timetable/${editSlot.id}`, {
          method: 'PATCH',
          headers: { ...h(), 'Content-Type': 'application/json' },
          body: JSON.stringify(editForm),
        });
      } else {
        response = await apiFetch(`${API}/academics/timetable`, {
          method: 'POST',
          headers: { ...h(), 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }
      const result = await response.json();
      if (!response.ok || !result.success) {
        setError(result.detail || 'Failed to save timetable slot');
        setSaving(false);
        return;
      }
      setEditSlot(null);
      loadTimetable(selectedClass);
    } catch { setError('Failed to save'); }
    setSaving(false);
  };

  const deleteSlot = async (slotId) => {
    if (!slotId) return;
    await apiFetch(`${API}/academics/timetable/${slotId}`, { method: 'DELETE', headers: h() });
    loadTimetable(selectedClass);
  };

  const subjectName = (id) => {
    const s = subjects.find(s => s.id === id);
    if (s) return s.name;
    // Try to get from slots
    const slot = slots.find(sl => sl.subject_id === id);
    return slot?.subject_name || id?.slice(0, 8) || '-';
  };

  const teacherName = (id) => {
    const t = staff.find(s => s.id === id);
    return t ? t.name : (id?.slice(0, 8) || '-');
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
          {/* Weekly grid.

              D-24 (deliberate exception): this table is NOT sortable and must not become
              sortable. Its rows are periods 1..N and its columns are the days of the
              week - the order IS the information. A timetable re-ordered by "Subject"
              would still be a grid of the right cells and would be read as the school's
              actual schedule, which is the worst possible outcome. The same rule is
              written on `DataTable`'s `sortable={false}` option in ToolPage.js. */}
          {canGenerate && (
            <TimetableGenerator
              classId={selectedClass}
              className={(() => {
                const cls = classes.find(x => x.id === selectedClass);
                return `${cls?.name || ''}-${cls?.section || ''}`;
              })()}
              subjects={subjects}
              days={DAYS}
              periods={PERIODS}
              onApplied={() => loadTimetable(selectedClass)}
              styles={{ card, border, text, muted, accent }}
            />
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
            {/* A timetable is a GRID, not a list, so the file keeps the grid: one row
                per period, one column per day. Flattening it into a list of slots
                would be a different document from the one on the wall, and the point
                of downloading a timetable is to print the one on the wall. */}
            <ExportButton
              title={(() => {
                const cls = classes.find(c => c.id === selectedClass);
                return `Timetable ${cls?.name || ''} ${cls?.section || ''}`.replace(/\s+/g, ' ').trim();
              })()}
              testId="timetable-export"
              columns={TIMETABLE_EXPORT_COLUMNS}
              getRows={async () => PERIODS.map((period) => {
                const row = { period: `P${period}` };
                DAYS.forEach((day, dayIdx) => {
                  const slot = getSlot(dayIdx, period);
                  row[day] = slot
                    ? [
                        slot.subject_name || subjectName(slot.subject_id),
                        teacherName(slot.teacher_id),
                        slot.start_time ? `${slot.start_time}-${slot.end_time}` : '',
                      ].filter(Boolean).join(' / ')
                    : '';
                });
                return row;
              })}
            />
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{ padding: '8px 12px', textAlign: 'left', color: muted, fontWeight: 600, fontSize: 11, width: 90, background: 'var(--c-deep)', border: `1px solid ${border}` }}>Period</th>
                  {DAYS.map(day => (
                    <th key={day} style={{ padding: '8px 12px', textAlign: 'center', color: muted, fontWeight: 600, fontSize: 11, background: 'var(--c-deep)', border: `1px solid ${border}` }}>
                      {day.slice(0, 3)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {PERIODS.map(period => (
                  <tr key={period}>
                    <td style={{ padding: '8px 12px', color: muted, fontWeight: 500, background: 'var(--c-deep)', border: `1px solid ${border}`, fontSize: 11 }}>P{period}</td>
                    {DAYS.map((day, dayIdx) => {
                      const slot = getSlot(dayIdx, period);
                      return (
                        <td
                          key={day}
                          onClick={() => openEdit(dayIdx, period)}
                          style={{
                            padding: '6px 8px', border: `1px solid ${border}`, cursor: canEdit ? 'pointer' : 'default',
                            background: slot ? 'var(--tool-hex-eff6ff)' : card,
                            verticalAlign: 'top', minWidth: 90,
                            transition: 'background 0.12s',
                          }}
                          onMouseEnter={e => canEdit && !slot && (e.currentTarget.style.background = 'var(--c-deep)')}
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
                            canEdit ? <div style={{ color: 'var(--c-border)', fontSize: 11, textAlign: 'center' }}>+</div> : null
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
              <div style={{ background: 'var(--c-bg)', borderRadius: 14, padding: 24, width: 380, maxWidth: '90vw', border: '1px solid var(--c-border)', boxShadow: 'var(--shadow-lg)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                  <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--c-text)', margin: 0 }}>
                    {DAYS[editSlot.day]} - Period {editSlot.period}
                  </h3>
                  <button onClick={() => setEditSlot(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: muted }}><X size={16} /></button>
                </div>
                <FormField
                  label="Subject"
                  type="select"
                  value={editForm.subject_id}
                  onChange={v => setEditForm(p => ({ ...p, subject_id: v }))}
                  options={[{ value: '', label: 'Select subject...' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]}
                />
                <FormField
                  label="Teacher"
                  type="select"
                  value={editForm.teacher_id}
                  onChange={v => setEditForm(p => ({ ...p, teacher_id: v }))}
                  options={[{ value: '', label: 'Select teacher...' }, ...staff.map(s => ({ value: s.id, label: s.name }))]}
                />
                <div className="responsive-form-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
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
