import React, { useState, useEffect, useCallback } from 'react';
import { useUser } from '../../contexts/UserContext';
import { useTheme } from '../../contexts/ThemeContext';
import {
  Plus, ChevronRight, ChevronLeft, Edit2, Trash2, BookOpen,
  Users, BarChart2, Calendar, CheckCircle, X, ClipboardList, AlertTriangle,
} from 'lucide-react';
import { listExams, createExam, updateExam, deleteExam, getExamResults, getAllClasses, getSubjects } from '../../lib/api';

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
  const canManage = isOwner || (currentUser.role === 'admin' && ['principal', 'management'].includes(currentUser.sub_category));
  const isTeacher = currentUser.role === 'teacher';

  const [view, setView] = useState('exams');
  const [exams, setExams] = useState([]);
  const [selectedExam, setSelectedExam] = useState(null);
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState(null);
  const [studentResults, setStudentResults] = useState([]);
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
    setStudentResults([]);
    setView('classes');
  };

  const handleSelectClass = async (cls) => {
    setSelectedClass(cls);
    setResultsLoading(true);
    setView('students');
    try {
      const res = await getExamResults({ exam_id: selectedExam.id, class_id: cls.id });
      if (res.success) setStudentResults(res.data || []);
    } catch {}
    setResultsLoading(false);
  };

  const groupByStudent = (results) => {
    const byStudent = {};
    for (const r of results) {
      if (!byStudent[r.student_id]) byStudent[r.student_id] = { student_name: r.student_name, subjects: [] };
      byStudent[r.student_id].subjects.push(r);
    }
    return Object.values(byStudent).sort((a, b) => a.student_name.localeCompare(b.student_name));
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
          {view === 'classes' && <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--color-text-secondary)' }}>Select a class to view student performance</p>}
          {view === 'students' && <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--color-text-secondary)' }}>Subject-wise marks for all students</p>}
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
                    <div style={{ fontSize: 11, color: '#4f8ff7', marginTop: 8, fontWeight: 600 }}>View Results →</div>
                  </Card>
                ))}
              </div>
            );
          })()}
        </>
      )}

      {/* Student subject-wise view */}
      {view === 'students' && (
        <>
          {resultsLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: 48, color: 'var(--color-text-secondary)', fontSize: 13 }}>
              <div className="spinner" style={{ width: 16, height: 16 }} /> Loading results…
            </div>
          ) : studentResults.length === 0 ? (
            <EmptyState icon={<BarChart2 size={40} />} message="No results recorded for this class yet." />
          ) : (() => {
            // Determine subject visibility for teachers:
            // - Class teachers of this class → see all subjects
            // - Subject-only teachers → see only their subjects for this class
            let allowedSubjectIds = null;
            if (isTeacher && teachingScope?.is_teacher && selectedClass) {
              const isClassTeacher = (teachingScope.class_teacher_class_ids || []).includes(selectedClass.id);
              if (!isClassTeacher) {
                // Subject teacher: only show their subjects that belong to this class
                const mySubjectsForClass = (teachingScope.subjects || [])
                  .filter(s => s.class_id === selectedClass.id)
                  .map(s => s.id);
                allowedSubjectIds = new Set(mySubjectsForClass);
              }
            }

            const grouped = groupByStudent(studentResults);
            let allSubjects = [...new Set(studentResults.map(r => r.subject_name))].sort();

            // Filter columns if subject teacher
            if (allowedSubjectIds !== null) {
              const allowedNames = new Set(
                studentResults
                  .filter(r => allowedSubjectIds.has(r.subject_id))
                  .map(r => r.subject_name)
              );
              allSubjects = allSubjects.filter(s => allowedNames.has(s));
            }

            const showTotal = allowedSubjectIds === null;

            return (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--color-border)' }}>
                      <th style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--color-text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>Student</th>
                      {allSubjects.map(s => (
                        <th key={s} style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--color-text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>{s}</th>
                      ))}
                      {showTotal && <th style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--color-text-secondary)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Total</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {grouped.map((g, idx) => {
                      const subjectMap = {};
                      for (const s of g.subjects) subjectMap[s.subject_name] = s;
                      const visibleSubjects = allowedSubjectIds !== null
                        ? g.subjects.filter(s => allowedSubjectIds.has(s.subject_id))
                        : g.subjects;
                      const totalObtained = visibleSubjects.reduce((acc, s) => acc + (s.marks_obtained || 0), 0);
                      const totalMax = visibleSubjects.reduce((acc, s) => acc + (s.max_marks || 100), 0);
                      return (
                        <tr key={g.student_name + idx} style={{ borderBottom: '1px solid var(--color-border)', background: idx % 2 === 0 ? 'transparent' : (isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)') }}>
                          <td style={{ padding: '9px 12px', fontWeight: 600, color: 'var(--color-text-primary)', whiteSpace: 'nowrap' }}>{g.student_name}</td>
                          {allSubjects.map(s => {
                            const r = subjectMap[s];
                            if (!r) return <td key={s} style={{ textAlign: 'center', padding: '9px 12px', color: 'var(--color-text-secondary)' }}>—</td>;
                            const pct = r.max_marks ? Math.round(r.marks_obtained / r.max_marks * 100) : null;
                            const color = pct === null ? '#737373' : pct >= 75 ? '#34d399' : pct >= 50 ? '#fbbf24' : '#f87171';
                            return (
                              <td key={s} style={{ textAlign: 'center', padding: '9px 12px' }}>
                                <span style={{ fontWeight: 700, color }}>{r.marks_obtained}</span>
                                <span style={{ color: 'var(--color-text-secondary)', fontSize: 11 }}>/{r.max_marks || 100}</span>
                              </td>
                            );
                          })}
                          {showTotal && (
                            <td style={{ textAlign: 'center', padding: '9px 12px', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                              {totalObtained}<span style={{ fontWeight: 400, color: 'var(--color-text-secondary)', fontSize: 11 }}>/{totalMax}</span>
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
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
