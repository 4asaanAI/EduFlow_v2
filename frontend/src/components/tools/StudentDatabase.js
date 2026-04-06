import React, { useState, useEffect } from 'react';
import { useUser } from '../../contexts/UserContext';
import { getStudents, createStudent, getAllClasses } from '../../lib/api';
import { Search, Plus, X, RefreshCw } from 'lucide-react';

function AddStudentModal({ classes, onClose, onSuccess }) {
  const { currentUser } = useUser();
  const [form, setForm] = useState({ name: '', class_id: '', admission_number: '', dob: '', gender: '', guardian_name: '', guardian_phone: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.class_id) { setError('Name and class are required'); return; }
    setSaving(true);
    try {
      const res = await createStudent(currentUser, form);
      if (res.success) { onSuccess(); onClose(); }
      else setError(res.error?.message || 'Failed to create student');
    } catch { setError('Network error'); }
    setSaving(false);
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
      <div style={{ background: '#1C1C28', border: '1px solid #222230', borderRadius: 14, padding: 28, width: 480, maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 16, fontWeight: 600, color: '#fff' }}>Add New Student</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#64748B', cursor: 'pointer' }}><X size={16} /></button>
        </div>
        <form onSubmit={handleSubmit}>
          {[
            { key: 'name', label: 'Full Name *', placeholder: 'Student full name', type: 'text' },
            { key: 'admission_number', label: 'Admission Number', placeholder: 'Auto-generated if empty', type: 'text' },
            { key: 'dob', label: 'Date of Birth', placeholder: '', type: 'date' },
            { key: 'guardian_name', label: 'Guardian Name', placeholder: "Parent/Guardian's name", type: 'text' },
            { key: 'guardian_phone', label: 'Guardian Phone', placeholder: '10-digit mobile number', type: 'tel' },
          ].map(f => (
            <div key={f.key} style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 11, color: '#64748B', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{f.label}</label>
              <input type={f.type} placeholder={f.placeholder} value={form[f.key]}
                onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                style={{ width: '100%', background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '9px 12px', color: '#E2E8F0', fontSize: 13, outline: 'none' }}
              />
            </div>
          ))}
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', fontSize: 11, color: '#64748B', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Class *</label>
            <select value={form.class_id} onChange={e => setForm(p => ({ ...p, class_id: e.target.value }))}
              style={{ width: '100%', background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '9px 12px', color: '#E2E8F0', fontSize: 13, outline: 'none' }}>
              <option value="">Select class...</option>
              {classes.map(c => (<option key={c.id} value={c.id}>{c.name}-{c.section}</option>))}
            </select>
          </div>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', fontSize: 11, color: '#64748B', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Gender</label>
            <select value={form.gender} onChange={e => setForm(p => ({ ...p, gender: e.target.value }))}
              style={{ width: '100%', background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '9px 12px', color: '#E2E8F0', fontSize: 13, outline: 'none' }}>
              <option value="">Select...</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </div>
          {error && <div style={{ color: '#EF4444', fontSize: 12, marginBottom: 12 }}>{error}</div>}
          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <button type="button" onClick={onClose} style={{ flex: 1, background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '10px', color: '#94A3B8', fontSize: 13, cursor: 'pointer' }}>Cancel</button>
            <button type="submit" disabled={saving} data-testid="submit-student-btn" style={{ flex: 1, background: saving ? '#1E3A5F' : '#3B82F6', border: 'none', borderRadius: 8, padding: '10px', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
              {saving ? 'Saving...' : 'Add Student'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function StudentDatabase() {
  const { currentUser } = useUser();
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterClass, setFilterClass] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => { loadData(); }, [search, filterClass, page]);
  useEffect(() => { loadClasses(); }, []);

  const loadClasses = async () => {
    try {
      const res = await getAllClasses(currentUser);
      if (res.success) setClasses(res.data || []);
    } catch {}
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const params = { page };
      if (search) params.search = search;
      if (filterClass) params.class_id = filterClass;
      const res = await getStudents(currentUser, params);
      if (res.success) { setStudents(res.data || []); setTotal(res.meta?.total || 0); }
    } catch {}
    setLoading(false);
  };

  return (
    <div data-testid="student-database-tool" style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 22, fontWeight: 600, color: '#fff' }}>Student database</h1>
          <div style={{ color: '#64748B', fontSize: 12, marginTop: 2 }}>{total} students enrolled</div>
        </div>
        {currentUser.role !== 'teacher' && (
          <button data-testid="add-student-btn" onClick={() => setShowAdd(true)} style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#3B82F6', border: 'none', borderRadius: 8, padding: '9px 16px', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
            <Plus size={14} />Add Student
          </button>
        )}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 18, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 300 }}>
          <Search size={13} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#64748B' }} />
          <input type="text" placeholder="Search by name or admission no..." value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            data-testid="student-search"
            style={{ width: '100%', background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '9px 12px 9px 32px', color: '#E2E8F0', fontSize: 13, outline: 'none' }}
          />
        </div>
        <select value={filterClass} onChange={e => { setFilterClass(e.target.value); setPage(1); }}
          data-testid="class-filter"
          style={{ background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '9px 14px', color: '#E2E8F0', fontSize: 13, outline: 'none' }}>
          <option value="">All classes</option>
          {classes.map(c => (<option key={c.id} value={c.id}>{c.name}-{c.section}</option>))}
        </select>
      </div>

      {/* Table */}
      <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 12, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#64748B', fontSize: 13 }}>Loading...</div>
        ) : students.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#64748B', fontSize: 13 }}>No students found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Name', 'Class', 'Adm. No.', 'Gender', 'Status'].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.06em', background: '#0F0F1A', borderBottom: '1px solid #222230' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {students.map((s, i) => (
                <tr key={s.id || i} style={{ borderBottom: i < students.length - 1 ? '1px solid #1A1A24' : 'none' }}>
                  <td style={{ padding: '10px 16px', fontSize: 13, color: '#E2E8F0', fontWeight: 500 }}>{s.name}</td>
                  <td style={{ padding: '10px 16px', fontSize: 12, color: '#94A3B8' }}>
                    {s.class_info ? `${s.class_info.name}-${s.class_info.section}` : 'N/A'}
                  </td>
                  <td style={{ padding: '10px 16px', fontSize: 12, color: '#94A3B8', fontFamily: 'JetBrains Mono, monospace' }}>{s.admission_number || 'N/A'}</td>
                  <td style={{ padding: '10px 16px', fontSize: 12, color: '#94A3B8', textTransform: 'capitalize' }}>{s.gender || 'N/A'}</td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 5, background: s.status === 'active' ? 'rgba(16,185,129,0.1)' : 'rgba(100,116,139,0.1)', color: s.status === 'active' ? '#10B981' : '#64748B' }}>
                      {s.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 14 }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} style={{ background: '#161622', border: '1px solid #222230', borderRadius: 7, padding: '6px 14px', color: '#94A3B8', fontSize: 12, cursor: 'pointer' }}>
            Prev
          </button>
          <span style={{ color: '#64748B', fontSize: 12, alignSelf: 'center' }}>Page {page} · {total} total</span>
          <button onClick={() => setPage(p => p + 1)} disabled={students.length < 20} style={{ background: '#161622', border: '1px solid #222230', borderRadius: 7, padding: '6px 14px', color: '#94A3B8', fontSize: 12, cursor: 'pointer' }}>
            Next
          </button>
        </div>
      )}

      {showAdd && <AddStudentModal classes={classes} onClose={() => setShowAdd(false)} onSuccess={() => { setShowAdd(false); loadData(); }} />}
    </div>
  );
}
