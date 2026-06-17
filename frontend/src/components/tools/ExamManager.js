import React, { useState, useEffect, useCallback } from 'react';
import { useUser } from '../../contexts/UserContext';
import { useTheme } from '../../contexts/ThemeContext';
import {
  Plus, ChevronRight, ChevronLeft, Edit2, Trash2, BookOpen,
  Users, BarChart2, Calendar, CheckCircle, X, ClipboardList, AlertTriangle, Save, Eye,
} from 'lucide-react';
import {
  listExams, createExam, updateExam, deleteExam, getAllClasses, getSubjects,
  getExamSheet, saveExamSchedule, bulkEnterResults,
} from '../../lib/api';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function _authHeaders(user) {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const EXAM_TYPES = [
  { value: 'unit_test', label: 'Unit Test' },
  { value: 'mid_term', label: 'Mid Term' },
  { value: 'final_term', label: 'Final Term' },
  { value: 'mock_test', label: 'Mock Test' },
  { value: 'practical', label: 'Practical' },
];

const EMPTY_FORM = { name: '', exam_type: 'unit_test', class_id: '', subject_id: '', start_date: '', end_date: '' };

function Pill({ label, color }) {
  const { isDark } = useTheme();
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600,
      background: isDark ? `${color}22` : `${color}18`, color, border: `1px solid ${color}44`,
    }}>{label}</span>
  );
}

function ExamTypeLabel({ type }) {
  const map = { unit_test: '#fb923c', mid_term: '#4f8ff7', final_term: '#f472b6', mock_test: '#a78bfa', practical: '#34d399' };
  const found = EXAM_TYPES.find(t => t.value === type);
  return <Pill label={found?.label || type} color={map[type] || '#737373'} />;
}

function Card({ children, onClick, style = {} }) {
  const { isDark } = useTheme();
  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: '14px 16px', cursor: onClick ? 'pointer' : 'default',
        transition: 'box-shadow 0.15s, border-color 0.15s',
        ...style,
      }}
      onMouseEnter={e => { if (onClick) { e.currentTarget.style.borderColor = '#4f8ff7'; e.currentTarget.style.boxShadow = '0 2px 12px rgba(79,143,247,0.12)'; } }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = ''; e.currentTarget.style.boxShadow = ''; }}
    >
      {children}
    </div>
  );
}

function FormField({ label, value, onChange, type = 'text', options, required, placeholder }) {
  const { isDark } = useTheme();
  const inputStyle = {
    width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 8,
    border: '1px solid var(--color-border)', background: isDark ? '#1a1a1a' : '#fafafa',
    color: 'var(--color-text-primary)', fontSize: 13, outline: 'none',
  };
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}{required && <span style={{ color: '#f87171' }}> *</span>}
      </label>
      {type === 'select' ? (
        <select value={value} onChange={e => onChange(e.target.value)} style={inputStyle}>
          {!required && <option value="">— Select —</option>}
          {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ) : (
        <input
          type={type} value={value} onChange={e => onChange(e.target.value)}
          placeholder={placeholder} style={inputStyle}
        />
      )}
    </div>
  );
}

function Btn({ label, onClick, variant = 'primary', icon, disabled, size = 'md' }) {
  const pad = size === 'sm' ? '5px 10px' : '8px 14px';
  const fs = size === 'sm' ? 12 : 13;
  const colors = {
    primary: { bg: '#4f8ff7', color: '#fff', border: '#4f8ff7' },
    danger: { bg: '#f87171', color: '#fff', border: '#f87171' },
    ghost: { bg: 'transparent', color: 'var(--color-text-secondary)', border: 'var(--color-border)' },
  };
  const c = colors[variant] || colors.primary;
  return (
    <button
      onClick={onClick} disabled={disabled}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5, padding: pad, borderRadius: 8,
        border: `1px solid ${c.border}`, background: c.bg, color: c.color, cursor: disabled ? 'not-allowed' : 'pointer',
        fontSize: fs, fontWeight: 600, opacity: disabled ? 0.6 : 1, transition: 'opacity 0.15s',
      }}
    >{icon}{label}</button>
  );
}

function Modal({ title, onClose, children }) {
  const { isDark } = useTheme();
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ background: isDark ? '#1c1c1c' : '#fff', border: '1px solid var(--color-border)', borderRadius: 14, padding: 24, width: '100%', maxWidth: 480, maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)' }}>{title}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-secondary)' }}><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function EmptyState({ icon, message }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, padding: '48px 16px', color: 'var(--color-text-secondary)' }}>
      <div style={{ opacity: 0.3 }}>{icon}</div>
      <span style={{ fontSize: 13 }}>{message}</span>
    </div>
  );
}

export default function ExamManager() {
  const { currentUser } = useUser();
  const { isDark } = useTheme();

  const isOwner = currentUser.role === 'owner';
  // Owner is view-only. Only Principal/Management admins and teachers manage exams.
  const canManage = currentUser.role === 'admin' && ['principal', 'management'].includes(currentUser.sub_category);
  const isTeacher = currentUser.role === 'teacher';

  const [view, setView] = useState('exams');
  const [exams, setExams] = useState([]);
  const [selectedExam, setSelectedExam] = useState(null);
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState(null);
  const [sheet, setSheet] = useState(null);
  const [marksDraft, setMarksDraft] = useState({});
  const [scheduleDraft, setScheduleDraft] = useState({});
  const [savingMarks, setSavingMarks] = useState(false);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [resultsLoading, setResultsLoading] = useState(false);

  // Teaching scope — drives class/subject visibility for teachers
  const [teachingScope, setTeachingScope] = useState(null);

  useEffect(() => {
    if (!isTeacher) { setTeachingScope({ is_teacher: false }); return; }
    let alive = true;
    fetch(`${API}/academics/my-teaching-scope`, { headers: _authHeaders(currentUser) })
      .then(r => r.json())
      .then(r => { if (alive) setTeachingScope(r.success ? r.data : { is_teacher: false }); })
      .catch(() => { if (alive) setTeachingScope({ is_teacher: false }); });
    return () => { alive = false; };
  }, [isTeacher, currentUser]);

  const [showForm, setShowForm] = useState(false);
  const [editingExam, setEditingExam] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formSubjects, setFormSubjects] = useState([]);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');
  const [savedOk, setSavedOk] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadExams = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [examsRes, classesRes] = await Promise.all([listExams(), getAllClasses()]);
      if (examsRes.success) setExams(examsRes.data || []);
      if (classesRes.success) setClasses(classesRes.data || []);
    } catch {
      setError('Failed to load exams');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadExams(); }, [loadExams]);

  useEffect(() => {
    if (!form.class_id) { setFormSubjects([]); return; }
    getSubjects(form.class_id).then(r => { if (r.success) setFormSubjects(r.data || []); });
  }, [form.class_id]);

  const openCreate = () => {
    setEditingExam(null);
    setForm(EMPTY_FORM);
    setFormError('');
    setSavedOk(false);
    setShowForm(true);
  };

  const openEdit = (exam) => {
    setEditingExam(exam);
    setForm({
      name: exam.name || '',
      exam_type: exam.exam_type || 'unit_test',
      class_id: exam.class_id || '',
      subject_id: exam.subject_id || '',
      start_date: exam.start_date || '',
      end_date: exam.end_date || '',
    });
    setFormError('');
    setSavedOk(false);
    setShowForm(true);
  };

  const handleSaveExam = async () => {
    if (!form.name.trim()) { setFormError('Exam name is required'); return; }
    setSaving(true);
    setFormError('');
    try {
      const payload = { ...form };
      if (!payload.class_id) delete payload.class_id;
      if (!payload.subject_id) delete payload.subject_id;
      if (!payload.start_date) delete payload.start_date;
      if (!payload.end_date) delete payload.end_date;
      const res = editingExam
        ? await updateExam(editingExam.id, payload)
        : await createExam(payload);
      if (res.success) {
        setSavedOk(true);
        setTimeout(() => { setShowForm(false); setSavedOk(false); }, 900);
        await loadExams();
      } else {
        setFormError(res.detail || 'Save failed');
      }
    } catch {
      setFormError('Network error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      const res = await deleteExam(deleteTarget.id);
      if (res.success) {
        setDeleteTarget(null);
        await loadExams();
      }
    } catch {}
    setDeleting(false);
  };

  const handleSelectExam = (exam) => {
    setSelectedExam(exam);
    setSelectedClass(null);
    setSheet(null);
    setView('classes');
  };

  const initDrafts = (s) => {
    const md = {};
    for (const r of s.results || []) {
      if (r.marks_obtained !== null && r.marks_obtained !== undefined) {
        md[`${r.student_id}|${r.subject_id}`] = String(r.marks_obtained);
      }
    }
    setMarksDraft(md);
    const sd = {};
    for (const sub of s.subjects || []) {
      sd[sub.id] = { exam_date: sub.exam_date || '', max_marks: sub.max_marks ?? 100 };
    }
    setScheduleDraft(sd);
  };

  const loadSheet = useCallback(async (examId, classId) => {
    const res = await getExamSheet(examId, classId);
    if (res.success) {
      setSheet(res.data);
      initDrafts(res.data);
      return res.data;
    }
    setSheet(null);
    return null;
  }, []);

  const handleSelectClass = async (cls) => {
    setSelectedClass(cls);
    setResultsLoading(true);
    setSaveMsg('');
    setView('students');
    try {
      await loadSheet(selectedExam.id, cls.id);
    } catch {
      setSheet(null);
    }
    setResultsLoading(false);
  };

  const handleSaveSchedule = async () => {
    if (!sheet) return;
    setSavingSchedule(true);
    setSaveMsg('');
    const subjects = sheet.subjects.filter(s => s.can_edit).map(s => ({
      subject_id: s.id,
      exam_date: scheduleDraft[s.id]?.exam_date || null,
      max_marks: Number(scheduleDraft[s.id]?.max_marks) || 100,
    }));
    if (subjects.length === 0) { setSavingSchedule(false); return; }
    try {
      const res = await saveExamSchedule(sheet.exam.id, selectedClass.id, subjects);
      if (res.success) {
        setSaveMsg('Datesheet saved');
        await loadSheet(sheet.exam.id, selectedClass.id);
      } else {
        setSaveMsg(res.detail || 'Failed to save datesheet');
      }
    } catch {
      setSaveMsg('Network error');
    }
    setSavingSchedule(false);
  };

  const handleSaveMarks = async () => {
    if (!sheet) return;
    setSavingMarks(true);
    setSaveMsg('');
    const results = [];
    for (const sub of sheet.subjects) {
      if (!sub.can_edit) continue;
      const max = Number(scheduleDraft[sub.id]?.max_marks) || sub.max_marks || 100;
      for (const st of sheet.students) {
        const v = marksDraft[`${st.id}|${sub.id}`];
        if (v === undefined || v === '') continue;
        results.push({
          exam_id: sheet.exam.id, student_id: st.id, subject_id: sub.id,
          marks_obtained: Number(v), max_marks: max,
        });
      }
    }
    if (results.length === 0) { setSaveMsg('No marks entered yet'); setSavingMarks(false); return; }
    try {
      const res = await bulkEnterResults(results);
      if (res.success === true) setSaveMsg(`Saved marks for ${res.data?.saved ?? results.length} entries`);
      else if (res.success === 'partial') setSaveMsg(`Saved ${res.saved}; ${res.errors?.length || 0} skipped — check values don't exceed max marks`);
      else setSaveMsg(res.detail || "Save failed — marks may exceed max marks");
      await loadSheet(sheet.exam.id, selectedClass.id);
    } catch {
      setSaveMsg('Network error');
    }
    setSavingMarks(false);
  };

  const bg = isDark ? '#111' : '#f5f5f5';
  const surface = isDark ? '#1c1c1c' : '#fff';

  return (
    <div style={{ height: '100%', overflow: 'auto', background: bg, padding: '20px 20px 40px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 10 }}>
        <div>
          {/* Breadcrumb */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, fontSize: 12, color: 'var(--color-text-secondary)' }}>
            <span
              style={{ cursor: view !== 'exams' ? 'pointer' : 'default', color: view !== 'exams' ? '#4f8ff7' : 'inherit' }}
              onClick={() => { setView('exams'); setSelectedExam(null); setSelectedClass(null); }}
            >Exams</span>
            {selectedExam && (
              <>
                <ChevronRight size={12} />
                <span
                  style={{ cursor: view === 'students' ? 'pointer' : 'default', color: view === 'students' ? '#4f8ff7' : 'inherit' }}
                  onClick={() => { setView('classes'); setSelectedClass(null); }}
                >{selectedExam.name}</span>
              </>
            )}
            {selectedClass && (
              <>
                <ChevronRight size={12} />
                <span>{selectedClass.name}{selectedClass.section ? ` ${selectedClass.section}` : ''}</span>
              </>
            )}
          </div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <ClipboardList size={18} color="#a78bfa" />
            {view === 'exams' && 'Exams'}
            {view === 'classes' && selectedExam?.name}
            {view === 'students' && (selectedClass?.name + (selectedClass?.section ? ` ${selectedClass.section}` : ''))}
          </h2>
          {view === 'classes' && <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--color-text-secondary)' }}>{isOwner ? 'Select a class to view student performance' : 'Select a class to set dates and enter marks'}</p>}
          {view === 'students' && <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--color-text-secondary)' }}>{isOwner ? 'Subject-wise marks for all students' : 'Set exam dates and enter subject-wise marks'}</p>}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {view !== 'exams' && (
            <Btn label="Back" icon={<ChevronLeft size={13} />} variant="ghost" size="sm"
              onClick={() => {
                if (view === 'students') { setView('classes'); setSelectedClass(null); }
                else { setView('exams'); setSelectedExam(null); }
              }}
            />
          )}
          {(canManage || isTeacher) && view === 'exams' && (
            <Btn label="New Exam" icon={<Plus size={13} />} onClick={openCreate} />
          )}
          {view === 'exams' && (
            <Btn label="Refresh" icon={<ClipboardList size={13} />} variant="ghost" size="sm" onClick={loadExams} disabled={loading} />
          )}
        </div>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', marginBottom: 16, background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.25)', borderRadius: 10, color: '#f87171', fontSize: 13 }}>
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* Exam list view */}
      {view === 'exams' && (
        <>
          {loading || (isTeacher && teachingScope === null) ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: 48, color: 'var(--color-text-secondary)', fontSize: 13 }}>
              <div className="spinner" style={{ width: 16, height: 16 }} /> Loading exams…
            </div>
          ) : (() => {
            const scopeClassIds = isTeacher && teachingScope?.is_teacher
              ? new Set(teachingScope.all_class_ids || [])
              : null;
            const visibleExams = scopeClassIds
              ? exams.filter(e => !e.class_id || scopeClassIds.has(e.class_id))
              : exams;
            if (visibleExams.length === 0) {
              return <EmptyState icon={<ClipboardList size={40} />} message={isTeacher ? 'No exams for your assigned classes yet.' : 'No exams found.'} />;
            }
            return (
              <div style={{ display: 'grid', gap: 10 }}>
                {visibleExams.map(exam => {
                  const cls = classes.find(c => c.id === exam.class_id);
                  return (
                    <Card key={exam.id} onClick={() => handleSelectExam(exam)}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
                            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text-primary)' }}>{exam.name}</span>
                            <ExamTypeLabel type={exam.exam_type} />
                          </div>
                          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12, color: 'var(--color-text-secondary)' }}>
                            {cls && (
                              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                <Users size={11} /> {cls.name}{cls.section ? ` ${cls.section}` : ''}
                              </span>
                            )}
                            {exam.start_date && (
                              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                <Calendar size={11} /> {exam.start_date}{exam.end_date && exam.end_date !== exam.start_date ? ` → ${exam.end_date}` : ''}
                              </span>
                            )}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                          <Btn label="" icon={<BarChart2 size={13} />} variant="ghost" size="sm"
                            onClick={e => { e.stopPropagation(); handleSelectExam(exam); }}
                          />
                          {(canManage || (isTeacher && exam.created_by === currentUser.id)) && (
                            <Btn label="" icon={<Edit2 size={13} />} variant="ghost" size="sm"
                              onClick={e => { e.stopPropagation(); openEdit(exam); }}
                            />
                          )}
                          {canManage && (
                            <Btn label="" icon={<Trash2 size={13} />} variant="danger" size="sm"
                              onClick={e => { e.stopPropagation(); setDeleteTarget(exam); }}
                            />
                          )}
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            );
          })()}
        </>
      )}

      {/* Class performance view */}
      {view === 'classes' && (
        <>
          {(() => {
            const scopeClassIds = isTeacher && teachingScope?.is_teacher
              ? new Set(teachingScope.all_class_ids || [])
              : null;
            // If exam has a specific class, jump directly to that class for teacher
            const examClassId = selectedExam?.class_id;
            let visibleClasses = scopeClassIds
              ? classes.filter(c => scopeClassIds.has(c.id))
              : classes;
            if (examClassId) visibleClasses = visibleClasses.filter(c => c.id === examClassId);
            if (visibleClasses.length === 0) {
              return <EmptyState icon={<BookOpen size={40} />} message="No classes found." />;
            }
            return (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 10 }}>
                {visibleClasses.map(cls => (
                  <Card key={cls.id} onClick={() => handleSelectClass(cls)} style={{ textAlign: 'center', padding: '20px 14px' }}>
                    <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(79,143,247,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 10px' }}>
                      <BookOpen size={18} color="#4f8ff7" />
                    </div>
                    <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--color-text-primary)' }}>{cls.name}</div>
                    {cls.section && <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 2 }}>Section {cls.section}</div>}
                    <div style={{ fontSize: 11, color: '#4f8ff7', marginTop: 8, fontWeight: 600 }}>{isOwner ? 'View Results →' : 'Enter Marks →'}</div>
                  </Card>
                ))}
              </div>
            );
          })()}
        </>
      )}

      {/* Marks sheet view — subjects + students auto-fetched from Academic Structure */}
      {view === 'students' && (
        <>
          {resultsLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: 48, color: 'var(--color-text-secondary)', fontSize: 13 }}>
              <div className="spinner" style={{ width: 16, height: 16 }} /> Loading sheet…
            </div>
          ) : !sheet ? (
            <EmptyState icon={<AlertTriangle size={40} />} message="Couldn't load this class sheet." />
          ) : (() => {
            const canEdit = !!sheet.can_edit;
            const allSubjects = sheet.subjects || [];
            const students = sheet.students || [];
            const resultMap = {};
            for (const r of sheet.results || []) resultMap[`${r.student_id}|${r.subject_id}`] = r;

            // Privacy: a subject-only teacher (not the class teacher) sees and edits
            // only their own subjects — never a colleague's columns. Class teachers,
            // admins and the owner see every subject (owner read-only). The Total
            // column is shown only on the full-subject view.
            let restrictToOwn = false;
            if (isTeacher && teachingScope?.is_teacher && selectedClass) {
              restrictToOwn = !(teachingScope.class_teacher_class_ids || []).includes(selectedClass.id);
            }
            const subjects = restrictToOwn ? allSubjects.filter(s => s.can_edit) : allSubjects;
            const showTotal = !restrictToOwn;

            const updateMark = (sid, subId, val) => {
              if (val !== '' && !/^\d*\.?\d*$/.test(val)) return;
              setMarksDraft(d => ({ ...d, [`${sid}|${subId}`]: val }));
            };
            const updateSchedule = (subId, field, val) =>
              setScheduleDraft(d => ({ ...d, [subId]: { ...d[subId], [field]: val } }));

            const cellInput = {
              width: 56, textAlign: 'center', padding: '5px 4px', borderRadius: 6,
              border: '1px solid var(--color-border)', background: isDark ? '#1a1a1a' : '#fff',
              color: 'var(--color-text-primary)', fontSize: 13, outline: 'none',
            };

            if (subjects.length === 0) {
              return <EmptyState icon={<BookOpen size={40} />} message={
                allSubjects.length === 0
                  ? 'No subjects defined for this class in the Academic Structure.'
                  : 'You are not assigned any subjects in this class.'
              } />;
            }

            return (
              <div style={{ display: 'grid', gap: 18 }}>
                {/* View-only banner for owner / non-editors */}
                {!canEdit && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: isDark ? 'rgba(167,139,250,0.08)' : 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.3)', borderRadius: 10, color: '#a78bfa', fontSize: 12, fontWeight: 600 }}>
                    <Eye size={14} /> View only — marks and dates are managed by teachers and admins.
                  </div>
                )}

                {/* Datesheet */}
                <div style={{ background: surface, border: '1px solid var(--color-border)', borderRadius: 12, padding: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Calendar size={14} color="#4f8ff7" /> Datesheet & Max Marks
                    </span>
                    {canEdit && (
                      <Btn label={savingSchedule ? 'Saving…' : 'Save Datesheet'} icon={<Save size={13} />} size="sm" onClick={handleSaveSchedule} disabled={savingSchedule} />
                    )}
                  </div>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                          <th style={{ textAlign: 'left', padding: '6px 10px', color: 'var(--color-text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>Subject</th>
                          <th style={{ textAlign: 'left', padding: '6px 10px', color: 'var(--color-text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>Exam Date</th>
                          <th style={{ textAlign: 'left', padding: '6px 10px', color: 'var(--color-text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>Max Marks</th>
                        </tr>
                      </thead>
                      <tbody>
                        {subjects.map(sub => {
                          const editable = canEdit && sub.can_edit;
                          const draft = scheduleDraft[sub.id] || {};
                          return (
                            <tr key={sub.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                              <td style={{ padding: '8px 10px', fontWeight: 600, color: 'var(--color-text-primary)', whiteSpace: 'nowrap' }}>{sub.name}</td>
                              <td style={{ padding: '8px 10px' }}>
                                {editable ? (
                                  <input type="date" value={draft.exam_date || ''} onChange={e => updateSchedule(sub.id, 'exam_date', e.target.value)}
                                    style={{ ...cellInput, width: 150, textAlign: 'left' }} />
                                ) : (
                                  <span style={{ color: sub.exam_date ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}>{sub.exam_date || '—'}</span>
                                )}
                              </td>
                              <td style={{ padding: '8px 10px' }}>
                                {editable ? (
                                  <input type="number" min="1" value={draft.max_marks ?? ''} onChange={e => updateSchedule(sub.id, 'max_marks', e.target.value)}
                                    style={{ ...cellInput, width: 80, textAlign: 'left' }} />
                                ) : (
                                  <span style={{ color: 'var(--color-text-primary)' }}>{sub.max_marks ?? 100}</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Marks grid */}
                <div style={{ background: surface, border: '1px solid var(--color-border)', borderRadius: 12, padding: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <BarChart2 size={14} color="#34d399" /> Marks — {students.length} student{students.length === 1 ? '' : 's'}
                    </span>
                    {canEdit && (
                      <Btn label={savingMarks ? 'Saving…' : 'Save Marks'} icon={<Save size={13} />} size="sm" onClick={handleSaveMarks} disabled={savingMarks} />
                    )}
                  </div>
                  {saveMsg && (
                    <div style={{ marginBottom: 10, fontSize: 12, color: saveMsg.toLowerCase().includes('fail') || saveMsg.toLowerCase().includes('error') || saveMsg.toLowerCase().includes('skipped') ? '#f87171' : '#34d399', fontWeight: 600 }}>
                      {saveMsg}
                    </div>
                  )}
                  {students.length === 0 ? (
                    <EmptyState icon={<Users size={36} />} message="No students enrolled in this class yet." />
                  ) : (
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <thead>
                          <tr style={{ borderBottom: '2px solid var(--color-border)' }}>
                            <th style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--color-text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap', position: 'sticky', left: 0, background: surface }}>Student</th>
                            {subjects.map(sub => (
                              <th key={sub.id} style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--color-text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>
                                {sub.name}
                                <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--color-text-secondary)', textTransform: 'none' }}>/{scheduleDraft[sub.id]?.max_marks ?? sub.max_marks ?? 100}</div>
                              </th>
                            ))}
                            {showTotal && <th style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--color-text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Total</th>}
                          </tr>
                        </thead>
                        <tbody>
                          {students.map((st, idx) => {
                            let totalObtained = 0; let totalMax = 0; let hasAny = false;
                            const cells = subjects.map(sub => {
                              const max = Number(scheduleDraft[sub.id]?.max_marks) || sub.max_marks || 100;
                              const key = `${st.id}|${sub.id}`;
                              const draftVal = marksDraft[key];
                              const editable = canEdit && sub.can_edit;
                              const numeric = draftVal !== undefined && draftVal !== '' ? Number(draftVal) : null;
                              if (numeric !== null && !Number.isNaN(numeric)) { totalObtained += numeric; totalMax += max; hasAny = true; }
                              if (editable) {
                                const over = numeric !== null && numeric > max;
                                return (
                                  <td key={sub.id} style={{ textAlign: 'center', padding: '6px 8px' }}>
                                    <input
                                      value={draftVal ?? ''} onChange={e => updateMark(st.id, sub.id, e.target.value)}
                                      placeholder="—" inputMode="decimal"
                                      style={{ ...cellInput, borderColor: over ? '#f87171' : 'var(--color-border)' }}
                                    />
                                  </td>
                                );
                              }
                              const existing = resultMap[key];
                              if (!existing || existing.marks_obtained === null || existing.marks_obtained === undefined) {
                                return <td key={sub.id} style={{ textAlign: 'center', padding: '9px 12px', color: 'var(--color-text-secondary)' }}>—</td>;
                              }
                              const pct = max ? Math.round(existing.marks_obtained / max * 100) : null;
                              const color = pct === null ? '#737373' : pct >= 75 ? '#34d399' : pct >= 50 ? '#fbbf24' : '#f87171';
                              return (
                                <td key={sub.id} style={{ textAlign: 'center', padding: '9px 12px' }}>
                                  <span style={{ fontWeight: 700, color }}>{existing.marks_obtained}</span>
                                  <span style={{ color: 'var(--color-text-secondary)', fontSize: 11 }}>/{max}</span>
                                </td>
                              );
                            });
                            return (
                              <tr key={st.id} style={{ borderBottom: '1px solid var(--color-border)', background: idx % 2 === 0 ? 'transparent' : (isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)') }}>
                                <td style={{ padding: '9px 12px', fontWeight: 600, color: 'var(--color-text-primary)', whiteSpace: 'nowrap', position: 'sticky', left: 0, background: 'inherit' }}>
                                  {st.roll_number ? <span style={{ color: 'var(--color-text-secondary)', fontWeight: 500, marginRight: 6 }}>{st.roll_number}.</span> : null}
                                  {st.name}
                                </td>
                                {cells}
                                {showTotal && (
                                  <td style={{ textAlign: 'center', padding: '9px 12px', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                                    {hasAny ? <>{totalObtained}<span style={{ fontWeight: 400, color: 'var(--color-text-secondary)', fontSize: 11 }}>/{totalMax}</span></> : '—'}
                                  </td>
                                )}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
        </>
      )}

      {/* Create/Edit exam modal */}
      {showForm && (
        <Modal title={editingExam ? 'Edit Exam' : 'Schedule Exam'} onClose={() => setShowForm(false)}>
          <FormField label="Exam Name" value={form.name} onChange={v => setForm(f => ({ ...f, name: v }))} required placeholder="e.g. Unit Test 1 — Mathematics" />
          <FormField label="Type" type="select" value={form.exam_type} onChange={v => setForm(f => ({ ...f, exam_type: v }))} options={EXAM_TYPES} required />
          <FormField
            label="Class (optional)"
            type="select"
            value={form.class_id}
            onChange={v => setForm(f => ({ ...f, class_id: v, subject_id: '' }))}
            options={classes.map(c => ({ value: c.id, label: `${c.name}${c.section ? ' ' + c.section : ''}` }))}
          />
          {form.class_id && (
            <FormField
              label="Subject (optional)"
              type="select"
              value={form.subject_id}
              onChange={v => setForm(f => ({ ...f, subject_id: v }))}
              options={formSubjects.map(s => ({ value: s.id, label: s.name }))}
            />
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <FormField label="Start Date" type="date" value={form.start_date} onChange={v => setForm(f => ({ ...f, start_date: v }))} />
            <FormField label="End Date" type="date" value={form.end_date} onChange={v => setForm(f => ({ ...f, end_date: v }))} />
          </div>
          {formError && <p style={{ color: '#f87171', fontSize: 12, margin: '0 0 10px' }}>{formError}</p>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <Btn label="Cancel" variant="ghost" onClick={() => setShowForm(false)} />
            <Btn
              label={saving ? 'Saving…' : savedOk ? 'Saved!' : editingExam ? 'Update Exam' : 'Create Exam'}
              icon={savedOk ? <CheckCircle size={13} /> : undefined}
              onClick={handleSaveExam}
              disabled={saving}
            />
          </div>
        </Modal>
      )}

      {/* Delete confirm modal */}
      {deleteTarget && (
        <Modal title="Delete Exam?" onClose={() => setDeleteTarget(null)}>
          <p style={{ margin: '0 0 16px', color: 'var(--color-text-secondary)', fontSize: 13 }}>
            Are you sure you want to delete <strong style={{ color: 'var(--color-text-primary)' }}>{deleteTarget.name}</strong>? This cannot be undone.
          </p>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Btn label="Cancel" variant="ghost" onClick={() => setDeleteTarget(null)} />
            <Btn label={deleting ? 'Deleting…' : 'Delete'} variant="danger" onClick={handleDelete} disabled={deleting} />
          </div>
        </Modal>
      )}
    </div>
  );
}
