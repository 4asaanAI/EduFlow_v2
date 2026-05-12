import React, { useEffect, useMemo, useState } from 'react';
import { useUser } from '../../contexts/UserContext';
import {
  createStudent,
  deactivateStudent,
  eraseStudent,
  getAllClasses,
  getStudents,
  updateStudent,
  uploadStudentPhoto,
} from '../../lib/api';
import { Camera, Edit3, Plus, RefreshCw, Search, Trash2, X } from 'lucide-react';

const blankForm = {
  name: '',
  class_id: '',
  admission_number: '',
  roll_number: '',
  dob: '',
  gender: '',
  guardian_name: '',
  guardian_phone: '',
};

const inputStyle = {
  width: '100%',
  background: 'var(--c-bg)',
  border: '1px solid var(--c-border)',
  borderRadius: 8,
  padding: '9px 12px',
  color: 'var(--c-text)',
  fontSize: 13,
  outline: 'none',
};

function ActionButton({ children, onClick, disabled, variant = 'primary', type = 'button', title }) {
  const secondary = variant === 'secondary';
  const danger = variant === 'danger';
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      style={{
        minHeight: 38,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 7,
        background: danger ? 'var(--tool-hex-7f1d1d)' : secondary ? 'var(--c-bg)' : 'var(--tool-hex-4f8ff7)',
        border: secondary ? '1px solid var(--c-border)' : 'none',
        borderRadius: 8,
        padding: '8px 13px',
        color: danger || !secondary ? 'var(--tool-hex-fff)' : 'var(--c-muted)',
        fontSize: 12,
        fontWeight: 600,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.65 : 1,
      }}
    >
      {children}
    </button>
  );
}

function StudentModal({ classes, initialStudent, onClose, onSaved }) {
  const editing = Boolean(initialStudent);
  const [form, setForm] = useState(() => initialStudent ? {
    name: initialStudent.name || '',
    class_id: initialStudent.class_id || '',
    admission_number: initialStudent.admission_number || '',
    roll_number: initialStudent.roll_number || '',
    dob: initialStudent.dob || '',
    gender: initialStudent.gender || '',
    guardian_name: initialStudent.guardians?.[0]?.name || '',
    guardian_phone: initialStudent.guardians?.[0]?.phone || '',
  } : blankForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const setField = (key) => (event) => {
    setForm((current) => ({ ...current, [key]: event.target.value }));
    setError('');
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.name || !form.class_id) {
      setError('Name and class are required');
      return;
    }
    setSaving(true);
    try {
      const res = editing
        ? await updateStudent(initialStudent.id, form)
        : await createStudent(null, form);
      if (res.success) {
        onSaved();
        onClose();
      } else {
        setError(res.detail || res.error?.message || 'Unable to save student');
      }
    } catch (err) {
      setError(err.message || 'Network error');
    }
    setSaving(false);
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 16 }}>
      <div style={{ background: 'var(--c-input)', border: '1px solid var(--c-border)', borderRadius: 8, padding: 24, width: 560, maxWidth: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <h3 style={{ fontSize: 16, fontWeight: 650, color: 'var(--c-text)', margin: 0 }}>{editing ? 'Edit Student' : 'Add Student'}</h3>
          <button onClick={onClose} aria-label="Close" style={{ width: 36, height: 36, border: 'none', background: 'transparent', color: 'var(--c-faint)', cursor: 'pointer' }}><X size={18} /></button>
        </div>
        <form onSubmit={submit}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 12 }}>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Full Name
              <input value={form.name} onChange={setField('name')} style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Class
              <select value={form.class_id} onChange={setField('class_id')} style={{ ...inputStyle, marginTop: 5 }}>
                <option value="">Select class</option>
                {classes.map((cls) => <option key={cls.id} value={cls.id}>{cls.name}-{cls.section}</option>)}
              </select>
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Admission No.
              <input value={form.admission_number} onChange={setField('admission_number')} style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Roll No.
              <input value={form.roll_number} onChange={setField('roll_number')} style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Date of Birth
              <input type="date" value={form.dob} onChange={setField('dob')} style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Gender
              <select value={form.gender} onChange={setField('gender')} style={{ ...inputStyle, marginTop: 5 }}>
                <option value="">Select</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </label>
            {!editing && (
              <>
                <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Guardian Name
                  <input value={form.guardian_name} onChange={setField('guardian_name')} style={{ ...inputStyle, marginTop: 5 }} />
                </label>
                <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Guardian Phone
                  <input value={form.guardian_phone} onChange={setField('guardian_phone')} style={{ ...inputStyle, marginTop: 5 }} />
                </label>
              </>
            )}
          </div>
          {error && <div style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginTop: 12 }}>{error}</div>}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
            <ActionButton variant="secondary" onClick={onClose}>Cancel</ActionButton>
            <ActionButton type="submit" disabled={saving}>{saving ? 'Saving...' : 'Save Student'}</ActionButton>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function StudentDatabase() {
  const { currentUser } = useUser();
  const [tab, setTab] = useState('database');
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [filterClass, setFilterClass] = useState('');
  const [includeInactive, setIncludeInactive] = useState(false);
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [editing, setEditing] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [eraseTarget, setEraseTarget] = useState(null);
  const [eraseReason, setEraseReason] = useState('');

  const canManage = ['owner', 'admin'].includes(currentUser.role);
  const canErase = currentUser.role === 'owner';
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / 20)), [total]);

  const strengthByClass = useMemo(() => {
    const map = {};
    students.forEach(s => {
      const key = s.class_info ? `${s.class_info.name}-${s.class_info.section}` : 'Unassigned';
      if (!map[key]) map[key] = { boys: 0, girls: 0, other: 0, total: 0 };
      const g = (s.gender || '').toLowerCase();
      if (g === 'male' || g === 'boy' || g === 'm') map[key].boys++;
      else if (g === 'female' || g === 'girl' || g === 'f') map[key].girls++;
      else map[key].other++;
      map[key].total++;
    });
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }));
  }, [students]);

  const loadClasses = async () => {
    const res = await getAllClasses();
    if (res.success) setClasses(res.data || []);
  };

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const params = { page, sort };
      if (search) params.search = search;
      if (filterClass) params.class_id = filterClass;
      if (includeInactive) params.include_inactive = true;
      const res = await getStudents(currentUser, params);
      if (res.success) {
        setStudents(res.data || []);
        setTotal(res.meta?.total || 0);
      } else {
        setError(res.detail || 'Unable to load students');
      }
    } catch (err) {
      setError(err.message || 'Unable to load students');
    }
    setLoading(false);
  };

  useEffect(() => { loadClasses().catch(() => {}); }, []);
  useEffect(() => { loadData(); }, [search, filterClass, includeInactive, sort, page]);

  const deactivate = async (student) => {
    if (!window.confirm(`Deactivate ${student.name}?`)) return;
    const res = await deactivateStudent(student.id);
    if (res.success) loadData();
    else setError(res.detail || 'Unable to deactivate student');
  };

  const uploadPhoto = async (student, file) => {
    if (!file) return;
    const res = await uploadStudentPhoto(student.id, file);
    if (res.success) loadData();
    else setError(res.detail || 'Unable to upload photo');
  };

  const confirmErase = async () => {
    if (!eraseTarget) return;
    const res = await eraseStudent(eraseTarget.id, eraseReason);
    if (res.success) {
      setEraseTarget(null);
      setEraseReason('');
      loadData();
    } else {
      setError(res.detail || 'Unable to erase student');
    }
  };

  return (
    <div data-testid="student-database-tool" style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 650, color: 'var(--c-text)', margin: 0 }}>Student Database</h1>
          <div style={{ color: 'var(--c-faint)', fontSize: 12, marginTop: 3 }}>{total} records</div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <ActionButton variant="secondary" onClick={loadData}><RefreshCw size={13} />Refresh</ActionButton>
          {canManage && <ActionButton onClick={() => setShowAdd(true)}><Plus size={13} />Add Student</ActionButton>}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 18, borderBottom: '1px solid var(--c-border)', paddingBottom: 0 }}>
        {[{ id: 'database', label: 'Database' }, { id: 'strength', label: 'Class Strength' }].map(t => (
          <button
            key={t.id}
            data-testid={`tab-${t.id}`}
            onClick={() => setTab(t.id)}
            style={{
              padding: '8px 16px',
              fontSize: 13,
              fontWeight: tab === t.id ? 650 : 500,
              color: tab === t.id ? '#4f8ff7' : 'var(--c-muted)',
              background: 'transparent',
              border: 'none',
              borderBottom: tab === t.id ? '2px solid #4f8ff7' : '2px solid transparent',
              cursor: 'pointer',
              marginBottom: -1,
              transition: 'color 0.15s',
            }}
          >{t.label}</button>
        ))}
      </div>

      {tab === 'strength' && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginBottom: 24 }}>
            {[
              { label: 'Total Students', value: total, color: '#4f8ff7' },
              { label: 'Classes', value: strengthByClass.length, color: '#34d399' },
              { label: 'Boys', value: strengthByClass.reduce((a, [, v]) => a + v.boys, 0), color: '#60a5fa' },
              { label: 'Girls', value: strengthByClass.reduce((a, [, v]) => a + v.girls, 0), color: '#f472b6' },
            ].map(stat => (
              <div key={stat.label} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: '16px 18px' }}>
                <div style={{ fontSize: 26, fontWeight: 700, color: stat.color }}>{stat.value}</div>
                <div style={{ fontSize: 12, color: 'var(--c-muted)', marginTop: 4 }}>{stat.label}</div>
              </div>
            ))}
          </div>

          <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Class', 'Boys', 'Girls', 'Other', 'Total'].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 750, color: 'var(--c-faint)', textTransform: 'uppercase', background: 'var(--c-deep)', borderBottom: '1px solid var(--c-border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {strengthByClass.map(([cls, counts], i) => (
                  <tr key={cls} style={{ borderBottom: i < strengthByClass.length - 1 ? '1px solid var(--c-border)' : 'none' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--c-text)', fontSize: 13 }}>{cls}</td>
                    <td style={{ padding: '10px 14px', color: '#60a5fa', fontSize: 13 }}>{counts.boys}</td>
                    <td style={{ padding: '10px 14px', color: '#f472b6', fontSize: 13 }}>{counts.girls}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--c-muted)', fontSize: 13 }}>{counts.other}</td>
                    <td style={{ padding: '10px 14px', fontWeight: 700, color: 'var(--c-text)', fontSize: 13 }}>{counts.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'database' && (<>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: '1 1 260px', maxWidth: 340 }}>
          <Search size={13} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--c-faint)' }} />
          <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} data-testid="student-search" placeholder="Search name or admission no." style={{ ...inputStyle, paddingLeft: 32 }} />
        </div>
        <select value={filterClass} onChange={(event) => { setFilterClass(event.target.value); setPage(1); }} data-testid="class-filter" style={{ ...inputStyle, width: 170 }}>
          <option value="">All classes</option>
          {classes.map((cls) => <option key={cls.id} value={cls.id}>{cls.name}-{cls.section}</option>)}
        </select>
        <select value={sort} onChange={(event) => { setSort(event.target.value); setPage(1); }} style={{ ...inputStyle, width: 150 }}>
          <option value="name">Sort by name</option>
          <option value="class">Sort by class</option>
          <option value="created_at">Newest first</option>
        </select>
        {currentUser.role === 'owner' && (
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--c-muted)', fontSize: 12, minHeight: 38 }}>
            <input type="checkbox" checked={includeInactive} onChange={(event) => { setIncludeInactive(event.target.checked); setPage(1); }} />
            Include inactive
          </label>
        )}
      </div>

      {error && <div style={{ color: 'var(--tool-hex-f87171)', background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.18)', borderRadius: 8, padding: 10, marginBottom: 12, fontSize: 12 }}>{error}</div>}

      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, overflowX: 'auto' }}>
        {loading ? (
          <div style={{ padding: 32, color: 'var(--c-faint)', fontSize: 13, textAlign: 'center' }}>Loading students...</div>
        ) : students.length === 0 ? (
          <div style={{ padding: 32, color: 'var(--c-faint)', fontSize: 13, textAlign: 'center' }}>No students match the current filters</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 760 }}>
            <thead>
              <tr>
                {['Student', 'Class', 'Admission', 'Gender', 'Status', 'Actions'].map((header) => (
                  <th key={header} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 750, color: 'var(--c-faint)', textTransform: 'uppercase', background: 'var(--c-deep)', borderBottom: '1px solid var(--c-border)' }}>{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {students.map((student, index) => (
                <tr key={student.id} style={{ borderBottom: index < students.length - 1 ? '1px solid var(--c-border)' : 'none' }}>
                  <td style={{ padding: '10px 14px', color: 'var(--c-text)', fontSize: 13, fontWeight: 600 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 34, height: 34, borderRadius: 8, background: student.photo_url ? `url(${student.photo_url}) center/cover` : 'var(--c-input)', border: '1px solid var(--c-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--c-faint)', fontSize: 11 }}>
                        {!student.photo_url && student.name?.slice(0, 1)}
                      </div>
                      <div>
                        <div>{student.name}</div>
                        <div style={{ color: 'var(--c-faint)', fontSize: 11 }}>Roll {student.roll_number || 'N/A'}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '10px 14px', color: 'var(--c-muted)', fontSize: 12 }}>{student.class_info ? `${student.class_info.name}-${student.class_info.section}` : 'N/A'}</td>
                  <td style={{ padding: '10px 14px', color: 'var(--c-muted)', fontSize: 12, fontFamily: 'JetBrains Mono, monospace' }}>{student.admission_number || 'N/A'}</td>
                  <td style={{ padding: '10px 14px', color: 'var(--c-muted)', fontSize: 12, textTransform: 'capitalize' }}>{student.gender || 'N/A'}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 8px', borderRadius: 5, background: student.is_active ? 'rgba(16,185,129,0.1)' : 'rgba(100,116,139,0.1)', color: student.is_active ? 'var(--tool-hex-34d399)' : 'var(--c-faint)' }}>{student.status || (student.is_active ? 'active' : 'inactive')}</span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                      {canManage && <ActionButton variant="secondary" onClick={() => setEditing(student)} title="Edit student"><Edit3 size={13} /></ActionButton>}
                      {canManage && (
                        <label title="Upload photo" style={{ minHeight: 38, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: '8px 11px', color: 'var(--c-muted)', cursor: 'pointer' }}>
                          <Camera size={13} />
                          <input type="file" accept="image/*" onChange={(event) => uploadPhoto(student, event.target.files?.[0])} style={{ display: 'none' }} />
                        </label>
                      )}
                      {canManage && student.is_active && <ActionButton variant="secondary" onClick={() => deactivate(student)}>Deactivate</ActionButton>}
                      {canErase && <ActionButton variant="danger" onClick={() => setEraseTarget(student)} title="Erase student"><Trash2 size={13} /></ActionButton>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {total > 20 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 14 }}>
          <ActionButton variant="secondary" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page === 1}>Prev</ActionButton>
          <span style={{ color: 'var(--c-faint)', fontSize: 12, alignSelf: 'center' }}>Page {page} of {totalPages}</span>
          <ActionButton variant="secondary" onClick={() => setPage((current) => current + 1)} disabled={page >= totalPages}>Next</ActionButton>
        </div>
      )}
      </>)}

      {showAdd && <StudentModal classes={classes} onClose={() => setShowAdd(false)} onSaved={loadData} />}
      {editing && <StudentModal classes={classes} initialStudent={editing} onClose={() => setEditing(null)} onSaved={loadData} />}
      {eraseTarget && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 210, padding: 16 }}>
          <div style={{ background: 'var(--c-input)', border: '1px solid var(--c-border)', borderRadius: 8, padding: 22, width: 480, maxWidth: '100%' }}>
            <h3 style={{ color: 'var(--c-text)', fontSize: 16, margin: 0 }}>Erase {eraseTarget.name}</h3>
            <p style={{ color: 'var(--c-faint)', fontSize: 12, lineHeight: 1.5 }}>This permanently removes student PII and pseudonymizes attendance records. Enter a detailed reason.</p>
            <textarea value={eraseReason} onChange={(event) => setEraseReason(event.target.value)} rows={4} style={{ ...inputStyle, resize: 'vertical' }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 14 }}>
              <ActionButton variant="secondary" onClick={() => { setEraseTarget(null); setEraseReason(''); }}>Cancel</ActionButton>
              <ActionButton variant="danger" disabled={eraseReason.trim().length < 10} onClick={confirmErase}>Erase Student</ActionButton>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
