import React, { useEffect, useState, useCallback } from 'react';
import { BookOpen, Plus, Edit3, Trash2, X, GraduationCap, User } from 'lucide-react';
import { ToolPage, FormField, ActionBtn, ErrorCard, LoadingCard } from './ToolPage';
import {
  getAllClasses, createClass, updateClass, deleteClass,
  getSubjects, createSubject, updateSubject, deleteSubject,
  getStaff, getAcademicYear,
} from '@/lib/api';

const card = {
  background: 'var(--color-surface)', border: '1px solid var(--color-border)',
  borderRadius: 14, padding: 16,
};

function Modal({ title, onClose, children }) {
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ ...card, width: '100%', maxWidth: 440, maxHeight: '88vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)' }}>{title}</div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function IconBtn({ icon, onClick, title, danger }) {
  return (
    <button onClick={onClick} title={title} style={{
      background: danger ? 'color-mix(in srgb, var(--color-danger) 12%, transparent)' : 'var(--color-surface-raised)',
      border: `1px solid ${danger ? 'color-mix(in srgb, var(--color-danger) 30%, transparent)' : 'var(--color-border)'}`,
      borderRadius: 7, padding: '5px 7px', cursor: 'pointer',
      color: danger ? 'var(--color-danger)' : 'var(--color-text-secondary)',
      display: 'flex', alignItems: 'center',
    }}>{icon}</button>
  );
}

export default function AcademicStructure() {
  const [classes, setClasses] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [academicYear, setAcademicYear] = useState(null);
  const [selectedClassId, setSelectedClassId] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [subjectsLoading, setSubjectsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [classModal, setClassModal] = useState(null);   // { mode, form }
  const [subjectModal, setSubjectModal] = useState(null);
  const [confirm, setConfirm] = useState(null);          // { kind, id, label }
  const [busy, setBusy] = useState(false);

  const teacherMap = Object.fromEntries(teachers.map((t) => [t.user_id, t.name]));
  const teacherOptions = teachers.map((t) => ({ value: t.user_id, label: t.name }));

  const loadTeachers = useCallback(async () => {
    const collected = [];
    let page = 1;
    for (let guard = 0; guard < 50; guard += 1) {
      const res = await getStaff({ page, limit: 20, sort: 'name' });
      if (!res.success) break;
      collected.push(...(res.data || []));
      const total = res.meta?.total ?? collected.length;
      if (collected.length >= total || (res.data || []).length === 0) break;
      page += 1;
    }
    setTeachers(collected.filter((s) => s.staff_type === 'teacher' && s.user_id));
  }, []);

  const loadClasses = useCallback(async () => {
    const res = await getAllClasses();
    if (res.success) {
      const list = res.data || [];
      setClasses(list);
      return list;
    }
    setError(res.detail || 'Unable to load classes');
    return [];
  }, []);

  const loadSubjects = useCallback(async (classId) => {
    if (!classId) { setSubjects([]); return; }
    setSubjectsLoading(true);
    try {
      const res = await getSubjects(classId);
      setSubjects(res.success ? (res.data || []) : []);
    } catch {
      setSubjects([]);
    } finally {
      setSubjectsLoading(false);
    }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list] = await Promise.all([loadClasses(), loadTeachers(), getAcademicYear().then((r) => setAcademicYear(r.data)).catch(() => {})]);
      setSelectedClassId((prev) => {
        const next = prev && list.some((c) => c.id === prev) ? prev : (list[0]?.id || null);
        loadSubjects(next);
        return next;
      });
    } catch {
      setError('Network error — please try again');
    } finally {
      setLoading(false);
    }
  }, [loadClasses, loadTeachers, loadSubjects]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const selectClass = (id) => { setSelectedClassId(id); loadSubjects(id); };

  // ── Class save / delete ────────────────────────────────────────────────
  const saveClass = async () => {
    const f = classModal.form;
    if (!f.name.trim()) { setError('Class name is required'); return; }
    setBusy(true);
    setError(null);
    try {
      const payload = {
        name: f.name.trim(), section: f.section.trim(),
        room_number: f.room_number.trim(), class_teacher_id: f.class_teacher_id || null,
      };
      const res = classModal.mode === 'edit'
        ? await updateClass(classModal.id, payload)
        : await createClass(payload);
      if (res.success) {
        const list = await loadClasses();
        if (classModal.mode === 'create' && res.data?.id) selectClass(res.data.id);
        else if (!list.some((c) => c.id === selectedClassId)) selectClass(list[0]?.id || null);
        setClassModal(null);
      } else {
        setError(res.detail || 'Failed to save class');
      }
    } catch {
      setError('Network error — please try again');
    } finally {
      setBusy(false);
    }
  };

  const saveSubject = async () => {
    const f = subjectModal.form;
    if (!f.name.trim()) { setError('Subject name is required'); return; }
    setBusy(true);
    setError(null);
    try {
      const payload = {
        name: f.name.trim(), class_id: selectedClassId,
        teacher_id: f.teacher_id || null,
        max_marks: f.max_marks === '' ? 100 : Number(f.max_marks),
        pass_marks: f.pass_marks === '' ? 33 : Number(f.pass_marks),
      };
      const res = subjectModal.mode === 'edit'
        ? await updateSubject(subjectModal.id, payload)
        : await createSubject(payload);
      if (res.success) {
        await loadSubjects(selectedClassId);
        setSubjectModal(null);
      } else {
        setError(res.detail || 'Failed to save subject');
      }
    } catch {
      setError('Network error — please try again');
    } finally {
      setBusy(false);
    }
  };

  const doDelete = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = confirm.kind === 'class' ? await deleteClass(confirm.id) : await deleteSubject(confirm.id);
      if (res.success) {
        if (confirm.kind === 'class') {
          const list = await loadClasses();
          if (selectedClassId === confirm.id) selectClass(list[0]?.id || null);
        } else {
          await loadSubjects(selectedClassId);
        }
        setConfirm(null);
      } else {
        setError(res.detail || 'Delete failed');
        setConfirm(null);
      }
    } catch {
      setError('Network error — please try again');
      setConfirm(null);
    } finally {
      setBusy(false);
    }
  };

  const selectedClass = classes.find((c) => c.id === selectedClassId);
  const z = (v) => (v === '' || v == null ? '' : String(v));

  const actions = <ActionBtn label="Add Class" icon={<Plus size={13} />} onClick={() => setClassModal({ mode: 'create', form: { name: '', section: '', room_number: '', class_teacher_id: '' } })} />;

  return (
    <ToolPage
      title="Academic Structure"
      subtitle={academicYear?.name ? `Classes & subjects — ${academicYear.name}` : 'Manage classes, subjects & teacher links'}
      onRefresh={loadAll}
      loading={loading}
      actions={actions}
    >
      {error && <ErrorCard message={error} onRetry={() => setError(null)} />}
      {loading ? <LoadingCard message="Loading academic structure…" /> : (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(240px, 320px) 1fr', gap: 16, alignItems: 'start' }}>
          {/* Classes column */}
          <div style={card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 12, fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary)' }}>
              <GraduationCap size={15} /> Classes ({classes.length})
            </div>
            {classes.length === 0 && <div style={{ fontSize: 13, color: 'var(--color-text-muted)', padding: '12px 0' }}>No classes yet. Click “Add Class”.</div>}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {classes.map((c) => {
                const active = c.id === selectedClassId;
                return (
                  <div key={c.id} onClick={() => selectClass(c.id)} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
                    padding: '9px 11px', borderRadius: 10, cursor: 'pointer',
                    background: active ? 'color-mix(in srgb, var(--color-accent-blue) 12%, transparent)' : 'var(--color-surface-raised)',
                    border: `1px solid ${active ? 'color-mix(in srgb, var(--color-accent-blue) 35%, transparent)' : 'var(--color-border)'}`,
                  }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>
                        {c.name}{c.section ? ` — ${c.section}` : ''}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {c.room_number ? `Room ${c.room_number} · ` : ''}{c.class_teacher_id ? (teacherMap[c.class_teacher_id] || 'Teacher assigned') : 'No class teacher'}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
                      <IconBtn icon={<Edit3 size={13} />} title="Edit class" onClick={(e) => { e.stopPropagation(); setClassModal({ mode: 'edit', id: c.id, form: { name: c.name || '', section: c.section || '', room_number: c.room_number || '', class_teacher_id: c.class_teacher_id || '' } }); }} />
                      <IconBtn icon={<Trash2 size={13} />} title="Delete class" danger onClick={(e) => { e.stopPropagation(); setConfirm({ kind: 'class', id: c.id, label: `${c.name}${c.section ? ' — ' + c.section : ''}` }); }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Subjects column */}
          <div style={card}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary)' }}>
                <BookOpen size={15} /> Subjects{selectedClass ? ` — ${selectedClass.name}${selectedClass.section ? ' ' + selectedClass.section : ''}` : ''}
              </div>
              {selectedClass && (
                <ActionBtn label="Add Subject" icon={<Plus size={12} />} onClick={() => setSubjectModal({ mode: 'create', form: { name: '', teacher_id: '', max_marks: '100', pass_marks: '33' } })} />
              )}
            </div>
            {!selectedClass ? (
              <div style={{ fontSize: 13, color: 'var(--color-text-muted)', padding: '12px 0' }}>Select a class to manage its subjects.</div>
            ) : subjectsLoading ? (
              <LoadingCard message="Loading subjects…" />
            ) : subjects.length === 0 ? (
              <div style={{ fontSize: 13, color: 'var(--color-text-muted)', padding: '12px 0' }}>No subjects for this class yet.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {subjects.map((s) => (
                  <div key={s.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '9px 11px', borderRadius: 10, background: 'var(--color-surface-raised)', border: '1px solid var(--color-border)' }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>{s.name}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>
                        <User size={11} />{s.teacher_id ? (teacherMap[s.teacher_id] || 'Teacher assigned') : 'Unassigned'} · {s.pass_marks ?? 33}/{s.max_marks ?? 100} marks
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
                      <IconBtn icon={<Edit3 size={13} />} title="Edit subject" onClick={() => setSubjectModal({ mode: 'edit', id: s.id, form: { name: s.name || '', teacher_id: s.teacher_id || '', max_marks: z(s.max_marks), pass_marks: z(s.pass_marks) } })} />
                      <IconBtn icon={<Trash2 size={13} />} title="Delete subject" danger onClick={() => setConfirm({ kind: 'subject', id: s.id, label: s.name })} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Class modal */}
      {classModal && (
        <Modal title={classModal.mode === 'edit' ? 'Edit Class' : 'Add Class'} onClose={() => setClassModal(null)}>
          <FormField label="Class Name" value={classModal.form.name} onChange={(v) => setClassModal((m) => ({ ...m, form: { ...m.form, name: v } }))} placeholder="Class 9" required />
          <FormField label="Section" value={classModal.form.section} onChange={(v) => setClassModal((m) => ({ ...m, form: { ...m.form, section: v } }))} placeholder="A" />
          <FormField label="Room Number" value={classModal.form.room_number} onChange={(v) => setClassModal((m) => ({ ...m, form: { ...m.form, room_number: v } }))} placeholder="R-101" />
          <FormField label="Class Teacher" type="select" value={classModal.form.class_teacher_id} onChange={(v) => setClassModal((m) => ({ ...m, form: { ...m.form, class_teacher_id: v } }))} options={teacherOptions} />
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <ActionBtn label="Cancel" variant="secondary" onClick={() => setClassModal(null)} />
            <ActionBtn label={busy ? 'Saving…' : 'Save'} onClick={saveClass} disabled={busy} />
          </div>
        </Modal>
      )}

      {/* Subject modal */}
      {subjectModal && (
        <Modal title={subjectModal.mode === 'edit' ? 'Edit Subject' : 'Add Subject'} onClose={() => setSubjectModal(null)}>
          <FormField label="Subject Name" value={subjectModal.form.name} onChange={(v) => setSubjectModal((m) => ({ ...m, form: { ...m.form, name: v } }))} placeholder="Mathematics" required />
          <FormField label="Teacher" type="select" value={subjectModal.form.teacher_id} onChange={(v) => setSubjectModal((m) => ({ ...m, form: { ...m.form, teacher_id: v } }))} options={teacherOptions} />
          <FormField label="Max Marks" type="number" value={subjectModal.form.max_marks} onChange={(v) => setSubjectModal((m) => ({ ...m, form: { ...m.form, max_marks: v } }))} placeholder="100" />
          <FormField label="Pass Marks" type="number" value={subjectModal.form.pass_marks} onChange={(v) => setSubjectModal((m) => ({ ...m, form: { ...m.form, pass_marks: v } }))} placeholder="33" />
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <ActionBtn label="Cancel" variant="secondary" onClick={() => setSubjectModal(null)} />
            <ActionBtn label={busy ? 'Saving…' : 'Save'} onClick={saveSubject} disabled={busy} />
          </div>
        </Modal>
      )}

      {/* Delete confirm */}
      {confirm && (
        <Modal title={`Delete ${confirm.kind}`} onClose={() => setConfirm(null)}>
          <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginBottom: 16 }}>
            Permanently delete <strong>{confirm.label}</strong>? This cannot be undone.
            {confirm.kind === 'class' && ' A class with active students cannot be deleted.'}
            {confirm.kind === 'subject' && ' A subject with recorded exam results cannot be deleted.'}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <ActionBtn label="Cancel" variant="secondary" onClick={() => setConfirm(null)} />
            <ActionBtn label={busy ? 'Deleting…' : 'Delete'} variant="danger" onClick={doDelete} disabled={busy} />
          </div>
        </Modal>
      )}
    </ToolPage>
  );
}
