/**
 * All 19 Admin Tools
 */
import React, { useState, useEffect, useRef } from 'react';
import { useUser } from '../../contexts/UserContext';
import { getStudents, createStudent, getAllClasses, getTodayAttendance, bulkMarkAttendance, getFeeTransactions, recordFeePayment, getPendingLeaves, updateLeave } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, StatCard, DataTable, Badge, ComingSoon, FormField, ActionBtn } from './ToolPage';
import { Search, Plus, CheckCircle, XCircle, Save, RefreshCw, X, FileDown } from 'lucide-react';
import FullStudentDatabase from './StudentDatabase';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function h() { return getAuthHeaders(); }

// 1. Student Database Manager
export function StudentDatabase() {
  return <FullStudentDatabase />;

  const { currentUser } = useUser();
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterClass, setFilterClass] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: '', class_id: '', admission_number: '', dob: '', gender: '', guardian_name: '', guardian_phone: '', roll_number: '' });
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  useEffect(() => { getAllClasses(currentUser).then(r => { if (r.success) setClasses(r.data || []); }); }, []);
  useEffect(() => { load(); }, [search, filterClass, page]);

  const load = async () => {
    setLoading(true);
    const params = { page };
    if (search) params.search = search;
    if (filterClass) params.class_id = filterClass;
    try { const r = await getStudents(currentUser, params); if (r.success) { setStudents(r.data || []); setTotal(r.meta?.total || 0); } } catch {}
    setLoading(false);
  };

  const [addError, setAddError] = useState('');
  const [saving, setSaving] = useState(false);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!form.name || !form.class_id) { setAddError('Name and class are required'); return; }
    setSaving(true);
    setAddError('');
    try {
      const res = await createStudent(currentUser, form);
      if (res.success) {
        setShowAdd(false);
        setForm({ name: '', class_id: '', admission_number: '', dob: '', gender: '', guardian_name: '', guardian_phone: '', roll_number: '' });
        load();
      } else {
        setAddError(res.detail || res.message || 'Failed to add student');
      }
    } catch (err) {
      console.error('Create student error:', err);
      setAddError('Network error: ' + err.message);
    }
    setSaving(false);
  };

  return (
    <ToolPage title="Student Database" subtitle={`${total} students enrolled`} onRefresh={load} loading={loading}
      actions={<ActionBtn label="Add Student" onClick={() => setShowAdd(true)} icon={<Plus size={11} />} />}>
      {showAdd && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Add New Student</h3>
          <form onSubmit={handleAdd}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Full Name" value={form.name} onChange={f('name')} placeholder="Student full name" required />
              <FormField label="Class" type="select" value={form.class_id} onChange={f('class_id')} options={classes.map(c => ({ value: c.id, label: `${c.name}-${c.section}` }))} required />
              <FormField label="Admission No." value={form.admission_number} onChange={f('admission_number')} placeholder="Auto-generated if empty" />
              <FormField label="Roll Number" value={form.roll_number} onChange={f('roll_number')} placeholder="Enter roll number" />
              <FormField label="Date of Birth" type="date" value={form.dob} onChange={f('dob')} />
              <FormField label="Guardian Name" value={form.guardian_name} onChange={f('guardian_name')} placeholder="Parent/guardian name" />
              <FormField label="Guardian Phone" type="tel" value={form.guardian_phone} onChange={f('guardian_phone')} placeholder="10-digit mobile" />
            </div>
            <FormField label="Gender" type="select" value={form.gender} onChange={f('gender')} options={[{ value: 'male', label: 'Male' }, { value: 'female', label: 'Female' }, { value: 'other', label: 'Other' }]} />
            {addError && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 8 }}>{addError}</div>}
            <div style={{ display: 'flex', gap: 8 }}><ActionBtn label={saving ? 'Saving...' : 'Add Student'} type="submit" disabled={saving} /><ActionBtn label="Cancel" variant="secondary" onClick={() => { setShowAdd(false); setAddError(''); }} /></div>
          </form>
        </div>
      )}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 280 }}>
          <Search size={12} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--c-faint)' }} />
          <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} data-testid="student-search" placeholder="Search by name or admission no..." style={{ width: '100%', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 10px 8px 28px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }} />
        </div>
        <select value={filterClass} onChange={e => { setFilterClass(e.target.value); setPage(1); }} data-testid="class-filter" style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }}>
          <option value="">All classes</option>
          {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
        </select>
      </div>
      <DataTable headers={['Name', 'Class', 'Adm. No.', 'Gender', 'Status']}
        rows={students.map(s => [
          s.name,
          s.class_info ? `${s.class_info.name}-${s.class_info.section}` : 'N/A',
          <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>{s.admission_number || 'N/A'}</span>,
          s.gender || 'N/A',
          <Badge text={s.status} color={s.status === 'active' ? 'green' : 'gray'} />,
        ])}
        emptyMsg={loading ? 'Loading...' : 'No students found'}
      />
      {total > 20 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 12 }}>
          <ActionBtn label="Prev" variant="secondary" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} />
          <span style={{ color: 'var(--c-faint)', fontSize: 12, alignSelf: 'center' }}>Page {page} of {Math.ceil(total / 20)}</span>
          <ActionBtn label="Next" variant="secondary" onClick={() => setPage(p => p + 1)} disabled={students.length < 20} />
        </div>
      )}
    </ToolPage>
  );
}

// 2. Fee Tracker & Reminder
export function FeeTracker() {
  const { currentUser } = useUser();
  const [txns, setTxns] = useState([]);
  const [classSummary, setClassSummary] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [allStudents, setAllStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [form, setForm] = useState({ class_id: '', student_id: '', fee_type: 'tuition', amount: '', payment_mode: 'cash', status: 'paid', due_date: '' });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [classFilter, setClassFilter] = useState('');
  const [view, setView] = useState('transactions');

  const f = k => async v => {
    if (k === 'class_id') {
      setForm(p => ({ ...p, class_id: v, student_id: '' }));
      if (v) {
        setLoadingStudents(true);
        // Fetch all students for this specific class (no pagination limit)
        try {
          const res = await fetch(`${API}/students/?class_id=${v}&page=1`, { headers: h(currentUser) }).then(r => r.json());
          if (res.success) {
            // Fetch more pages if needed
            const total = res.meta?.total || 0;
            let all = res.data || [];
            if (total > 20) {
              const pages = Math.ceil(total / 20);
              const extra = await Promise.all(
                Array.from({ length: pages - 1 }, (_, i) =>
                  fetch(`${API}/students/?class_id=${v}&page=${i + 2}`, { headers: h(currentUser) }).then(r => r.json())
                )
              );
              extra.forEach(r => { if (r.success) all = [...all, ...(r.data || [])]; });
            }
            setAllStudents(all);
          }
        } catch { }
        setLoadingStudents(false);
      } else {
        setAllStudents([]);
      }
    } else {
      setForm(p => ({ ...p, [k]: v }));
    }
  };

  useEffect(() => {
    getAllClasses(currentUser).then(r => { if (r.success) setClasses(r.data || []); });
  }, []);

  useEffect(() => { load(); }, [statusFilter, classFilter]);

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (classFilter) params.class_id = classFilter;
      const [txnRes, summaryRes] = await Promise.all([
        getFeeTransactions(currentUser, params),
        fetch(`${API}/fees/class-summary`, { headers: h(currentUser) }).then(r => r.json()),
      ]);
      if (txnRes.success) setTxns(txnRes.data || []);
      if (summaryRes.success) setClassSummary(summaryRes.data || []);
    } catch {}
    setLoading(false);
  };

  const handleRecord = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.class_id) { setError('Select a class'); return; }
    if (!form.student_id) { setError('Select a student'); return; }
    if (!form.amount) { setError('Enter amount'); return; }
    setSaving(true);
    try {
      await recordFeePayment(currentUser, { ...form, amount: parseFloat(form.amount) });
      setShowForm(false);
      setForm({ class_id: '', student_id: '', fee_type: 'tuition', amount: '', payment_mode: 'cash', status: 'paid', due_date: '' });
      setError('');
      load();
    } catch (err) {
      setError(err.message || 'Failed to record payment');
    } finally {
      setSaving(false);
    }
  };

  const statusColors = { paid: 'green', pending: 'yellow', overdue: 'red', waived: 'gray', partial: 'blue' };
  const totalPaid = txns.filter(t => t.status === 'paid').reduce((s, t) => s + (t.amount || 0), 0);
  const totalPending = txns.filter(t => t.status !== 'paid').reduce((s, t) => s + (t.amount || 0), 0);

  const handleOpenForm = () => {
    setAllStudents([]);
    setForm({ class_id: '', student_id: '', fee_type: 'tuition', amount: '', payment_mode: 'cash', status: 'paid', due_date: '' });
    setError('');
    setShowForm(true);
  };

  return (
    <ToolPage title="Fee Tracker" subtitle="Payments, dues & class-wise tracking" onRefresh={load} loading={loading}
      actions={<ActionBtn label="Record Payment" onClick={handleOpenForm} icon={<Plus size={11} />} />}>

      {showForm && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Record Fee Payment</h3>
          <form onSubmit={handleRecord}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Class" type="select" value={form.class_id} onChange={f('class_id')} options={[{ value: '', label: '-- Select Class --' }, ...classes.map(c => ({ value: c.id, label: `${c.name}-${c.section}` }))]} required />
              <div>
                <FormField label="Student" type="select" value={form.student_id} onChange={f('student_id')}
                  options={[
                    { value: '', label: !form.class_id ? '-- Select class first --' : loadingStudents ? 'Loading...' : allStudents.length === 0 ? '-- No students --' : '-- Select Student --' },
                    ...allStudents.map(s => ({ value: s.id, label: s.name }))
                  ]}
                  disabled={!form.class_id || loadingStudents} required />
                {form.class_id && !loadingStudents && allStudents.length === 0 && (
                  <div style={{ fontSize: 11, color: '#fbbf24', marginTop: 4 }}>
                    ⚠️ No students in this class. Add students in Student Database first.
                  </div>
                )}
              </div>
              <FormField label="Fee Type" type="select" value={form.fee_type} onChange={f('fee_type')} options={['tuition', 'transport', 'exam', 'sports', 'other'].map(v => ({ value: v, label: v }))} />
              <FormField label="Amount (₹)" type="number" value={form.amount} onChange={f('amount')} placeholder="0.00" required />
              <FormField label="Payment Mode" type="select" value={form.payment_mode} onChange={f('payment_mode')} options={[{ value: 'cash', label: 'Cash' }, { value: 'upi', label: 'UPI' }, { value: 'cheque', label: 'Cheque' }, { value: 'online', label: 'Online' }]} />
              <FormField label="Status" type="select" value={form.status} onChange={f('status')} options={[{ value: 'paid', label: 'Paid' }, { value: 'pending', label: 'Pending' }, { value: 'overdue', label: 'Overdue' }, { value: 'waived', label: 'Waived' }, { value: 'partial', label: 'Partial' }]} />
              {(form.status === 'overdue' || form.status === 'pending') && (
                <FormField label="Due Date" type="date" value={form.due_date} onChange={f('due_date')} />
              )}
            </div>
            {error && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 12, marginTop: 8 }}>{error}</div>}
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button type="submit" disabled={saving} style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid #4f8ff7', background: '#4f8ff7', color: '#fff', fontSize: 12, cursor: saving ? 'not-allowed' : 'pointer', fontWeight: 500, opacity: saving ? 0.6 : 1 }}>
                {saving ? 'Recording...' : 'Record'}
              </button>
              <button type="button" onClick={() => { setShowForm(false); setError(''); }} style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid var(--c-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Summary stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
        <StatCard value={`₹${totalPaid.toLocaleString('en-IN')}`} label="COLLECTED" color="#34d399" />
        <StatCard value={`₹${totalPending.toLocaleString('en-IN')}`} label="PENDING" color="#f87171" />
        <StatCard value={txns.length} label="TRANSACTIONS" color="#4f8ff7" />
      </div>

      {/* View toggle */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 14, alignItems: 'center', flexWrap: 'wrap' }}>
        {['transactions', 'classwise'].map(v => (
          <button key={v} onClick={() => setView(v)} style={{ background: view === v ? '#4f8ff7' : 'var(--c-bg)', border: `1px solid ${view === v ? '#4f8ff7' : 'var(--c-border)'}`, borderRadius: 6, padding: '5px 14px', color: view === v ? '#fff' : 'var(--c-muted)', fontSize: 11, fontWeight: 600, cursor: 'pointer', textTransform: 'capitalize' }}>
            {v === 'classwise' ? 'Class-wise' : 'Transactions'}
          </button>
        ))}
        {view === 'transactions' && (
          <>
            <div style={{ width: 1, height: 20, background: 'var(--c-border)', margin: '0 4px' }} />
            {['', 'paid', 'pending', 'overdue'].map(s => (
              <button key={s} onClick={() => setStatusFilter(s)} style={{ background: statusFilter === s ? '#6366F1' : 'var(--c-bg)', border: `1px solid ${statusFilter === s ? '#6366F1' : 'var(--c-border)'}`, borderRadius: 6, padding: '5px 12px', color: statusFilter === s ? '#fff' : 'var(--c-muted)', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
                {s || 'All'}
              </button>
            ))}
            <div style={{ width: 1, height: 20, background: 'var(--c-border)', margin: '0 4px' }} />
            <select value={classFilter} onChange={e => setClassFilter(e.target.value)} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '5px 10px', color: 'var(--c-text)', fontSize: 11, outline: 'none' }}>
              <option value="">All classes</option>
              {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
            </select>
          </>
        )}
      </div>

      {view === 'transactions' ? (
        <DataTable headers={['Student', 'Class', 'Fee Type', 'Amount', 'Mode', 'Paid Date', 'Status']}
          rows={txns.map(t => [
            t.student_name || 'N/A',
            t.class_name || 'N/A',
            t.fee_type,
            `₹${(t.amount || 0).toLocaleString('en-IN')}`,
            t.payment_mode || '—',
            t.paid_date || '—',
            <Badge text={t.status} color={statusColors[t.status] || 'gray'} />,
          ])}
          emptyMsg="No transactions found"
        />
      ) : (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Class', 'Students', 'Collected', 'Pending', 'Total', 'Txns', 'Collection %'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', background: 'var(--c-deep)', borderBottom: '1px solid var(--c-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {classSummary.length === 0 ? (
                <tr><td colSpan={7} style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>No data available</td></tr>
              ) : classSummary.map((cls, i) => {
                const pct = cls.total > 0 ? Math.round((cls.paid / cls.total) * 100) : 0;
                const barColor = pct >= 75 ? '#34d399' : pct >= 40 ? '#fbbf24' : '#f87171';
                return (
                  <tr key={cls.class_id} style={{ borderBottom: i < classSummary.length - 1 ? '1px solid #242424' : 'none' }}>
                    <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--c-text)', fontWeight: 600 }}>{cls.class_name}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{cls.total_students}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: '#34d399', fontWeight: 600 }}>₹{(cls.paid || 0).toLocaleString('en-IN')}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: '#f87171' }}>₹{(cls.pending || 0).toLocaleString('en-IN')}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-text)' }}>₹{(cls.total || 0).toLocaleString('en-IN')}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{cls.transactions}</td>
                    <td style={{ padding: '10px 14px', minWidth: 120 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ flex: 1, height: 6, background: 'var(--c-border)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ width: `${pct}%`, height: '100%', background: barColor, borderRadius: 3, transition: 'width 0.4s' }} />
                        </div>
                        <span style={{ fontSize: 11, color: barColor, fontWeight: 700, minWidth: 32 }}>{pct}%</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </ToolPage>
  );
}

// 3. Attendance Recorder
export function AttendanceRecorder() {
  const { currentUser } = useUser();
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => { getAllClasses(currentUser).then(r => { if (r.success && r.data.length > 0) { setClasses(r.data); setSelectedClass(r.data[0].id); } }); }, []);
  useEffect(() => { if (selectedClass) loadStudents(); }, [selectedClass, date]);

  const loadStudents = async () => {
    setLoading(true);
    try { const r = await getTodayAttendance(selectedClass, currentUser); if (r.success) setRecords(r.data || []); } catch {}
    setLoading(false);
  };

  const markAll = status => setRecords(prev => prev.map(s => ({ ...s, status })));

  const handleSave = async () => {
    setSaving(true);
    try {
      await bulkMarkAttendance({ class_id: selectedClass, date, records: records.map(s => ({ student_id: s.student_id, status: s.status })) }, currentUser);
      setSaved(true); setTimeout(() => setSaved(false), 3000);
    } catch {}
    setSaving(false);
  };

  const statusOpts = ['present', 'absent', 'late', 'holiday'];
  const presentCount = records.filter(r => r.status === 'present').length;

  return (
    <ToolPage title="Attendance Recorder" subtitle="Mark class attendance">
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={selectedClass} onChange={e => setSelectedClass(e.target.value)} data-testid="class-select" style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }}>
          {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
        </select>
        <input type="date" value={date} onChange={e => setDate(e.target.value)} data-testid="date-picker" style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }} />
        <ActionBtn label="All Present" variant="success" onClick={() => markAll('present')} data-testid="mark-all-present" />
        <ActionBtn label="All Absent" variant="danger" onClick={() => markAll('absent')} data-testid="mark-all-absent" />
      </div>
      {records.length > 0 && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
          {[{ label: 'Present', val: presentCount, color: '#34d399' }, { label: 'Absent', val: records.filter(r => r.status === 'absent').length, color: '#f87171' }, { label: 'Late', val: records.filter(r => r.status === 'late').length, color: '#fbbf24' }, { label: 'Total', val: records.length, color: 'var(--c-text)' }].map(s => (
            <StatCard key={s.label} value={s.val} label={s.label} color={s.color} small />
          ))}
        </div>
      )}
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, overflow: 'hidden', marginBottom: 14 }}>
        {loading ? <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>Loading students...</div> : records.length === 0 ? <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>No students or no class selected</div> : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              {['Roll', 'Student Name', 'Status', 'Quick Mark'].map(h => <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontSize: 9.5, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', background: 'var(--c-deep)', borderBottom: '1px solid var(--c-border)' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {records.map((s, i) => {
                const statusOpt = { present: { color: '#34d399' }, absent: { color: '#f87171' }, late: { color: '#fbbf24' }, holiday: { color: 'var(--c-faint)' } };
                const sc = statusOpt[s.status] || { color: 'var(--c-faint)' };
                return (
                  <tr key={s.student_id || i} style={{ borderBottom: i < records.length - 1 ? '1px solid #242424' : 'none' }}>
                    <td style={{ padding: '8px 14px', fontSize: 11, color: 'var(--c-faint)', fontFamily: 'JetBrains Mono, monospace' }}>{s.roll_number || '-'}</td>
                    <td style={{ padding: '8px 14px', fontSize: 13, color: 'var(--c-text)', fontWeight: 500 }}>{s.name}</td>
                    <td style={{ padding: '8px 14px' }}><span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 5, background: `${sc.color}15`, color: sc.color }}>{s.status}</span></td>
                    <td style={{ padding: '8px 14px' }}>
                      <div style={{ display: 'flex', gap: 3 }}>
                        {['P', 'A', 'L'].map((lbl, li) => {
                          const vals = ['present', 'absent', 'late'];
                          const c = [{ color: '#34d399' }, { color: '#f87171' }, { color: '#fbbf24' }][li];
                          return <button key={lbl} onClick={() => setRecords(prev => prev.map(st => st.student_id === s.student_id ? { ...st, status: vals[li] } : st))}
                            style={{ background: s.status === vals[li] ? `${c.color}20` : 'transparent', border: `1px solid ${s.status === vals[li] ? c.color + '50' : 'var(--c-border)'}`, borderRadius: 4, padding: '3px 7px', color: s.status === vals[li] ? c.color : 'var(--c-faint)', fontSize: 10, cursor: 'pointer', fontWeight: 700 }}>{lbl}</button>;
                        })}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      {records.length > 0 && <button data-testid="save-attendance-btn" onClick={handleSave} disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: 7, background: saved ? '#34d399' : saving ? '#1e3a5f' : '#4f8ff7', border: 'none', borderRadius: 8, padding: '10px 20px', color: '#fff', fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>
        {saved ? <CheckCircle size={14} /> : <Save size={14} />}
        {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Attendance'}
      </button>}
    </ToolPage>
  );
}

// 4. Certificate Generator
const CERT_LABELS = { transfer: 'Transfer Certificate', bonafide: 'Bonafide Certificate', character: 'Character Certificate', sports: 'Sports Certificate', participation: 'Participation Certificate', migration: 'Migration Certificate' };

async function downloadBlobAsPdf(url, body, filename, onStart, onDone, onError) {
  onStart();
  try {
    const res = await fetch(url, { method: 'POST', headers: h(), body: JSON.stringify(body) });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (e) {
    onError && onError(e);
  } finally {
    onDone();
  }
}

export function CertificateGenerator() {
  const { currentUser } = useUser();
  const [students, setStudents] = useState([]);
  const [certs, setCerts] = useState([]);
  const [form, setForm] = useState({ student_id: '', cert_type: 'bonafide' });
  const f = k => v => setForm(p => ({ ...p, [k]: v }));
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(null);
  const [downloading, setDownloading] = useState(null);

  const loadCerts = async () => {
    const r = await fetch(`${API}/ops/certificates`, { headers: h(currentUser) }).then(r => r.json());
    if (r.success) setCerts(r.data || []);
  };

  useEffect(() => {
    Promise.all([
      getStudents(currentUser).then(r => { if (r.success) setStudents(r.data || []); }),
      loadCerts(),
    ]).finally(() => setLoading(false));
  }, []);

  const generate = async () => {
    if (!form.student_id) return;
    setGenerating(true);
    try {
      const student = students.find(s => s.id === form.student_id);
      const r = await fetch(`${API}/ops/certificates`, {
        method: 'POST', headers: h(currentUser),
        body: JSON.stringify({
          student_id: form.student_id,
          cert_type: form.cert_type,
          content_data: {
            student_name: student?.name || 'Student',
            class: student?.class_info ? `${student.class_info.name}-${student.class_info.section}` : 'N/A',
            issued_by: 'The Aaryans School',
            issued_date: new Date().toISOString().slice(0, 10),
            academic_year: '2025-26',
          },
        }),
      }).then(r => r.json());
      if (r.success) { setGenerated(r.data); await loadCerts(); }
    } catch {}
    setGenerating(false);
  };

  const downloadPdf = (cert) => {
    const key = cert.id || cert.serial_number;
    const d = cert.content_data || {};
    const label = CERT_LABELS[cert.cert_type] || cert.cert_type;
    const filename = `${label.replace(/\s+/g, '-')}-${(d.student_name || 'certificate').replace(/\s+/g, '-')}.pdf`;
    downloadBlobAsPdf(
      `${API}/image-gen/certificate`,
      {
        cert_type: cert.cert_type,
        student_name: d.student_name || '',
        class: d.class || '',
        school_name: d.issued_by || '',
        affiliation: 'Affiliated to CBSE · Lucknow, Uttar Pradesh',
        issued_date: d.issued_date || cert.issued_date || '',
        academic_year: d.academic_year || '',
        serial_number: cert.serial_number || '',
      },
      filename,
      () => setDownloading(key),
      () => setDownloading(null),
    );
  };

  return (
    <ToolPage title="Certificate Generator" subtitle="Generate & download TC, Bonafide, Character certificates" loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 20 }}>
        {/* Generator form */}
        <div>
          <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
            <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Generate Certificate</h3>
            <FormField label="Student" type="select" value={form.student_id} onChange={f('student_id')}
              options={students.map(s => ({ value: s.id, label: s.name }))} required />
            <FormField label="Certificate Type" type="select" value={form.cert_type} onChange={f('cert_type')}
              options={Object.entries(CERT_LABELS).map(([v, l]) => ({ value: v, label: l }))} />
            <ActionBtn label={generating ? 'Generating...' : 'Generate Certificate'} onClick={generate} disabled={generating || !form.student_id} />
          </div>

          {generated && (
            <div style={{ background: 'var(--c-bg)', border: '1px solid #34d39930', borderRadius: 11, padding: 16 }}>
              <div style={{ fontSize: 11, color: '#34d399', fontWeight: 700, marginBottom: 10 }}>Certificate Generated!</div>
              <div style={{ fontSize: 12, color: 'var(--c-muted)', lineHeight: 1.8 }}>
                <div><b style={{ color: 'var(--c-text)' }}>Type:</b> {CERT_LABELS[generated.cert_type]}</div>
                <div><b style={{ color: 'var(--c-text)' }}>Serial:</b> <span style={{ fontFamily: 'monospace' }}>{generated.serial_number}</span></div>
                <div><b style={{ color: 'var(--c-text)' }}>Student:</b> {generated.content_data?.student_name}</div>
                <div><b style={{ color: 'var(--c-text)' }}>Date:</b> {generated.issued_date}</div>
              </div>
              <div style={{ marginTop: 12 }}>
                <ActionBtn label={downloading === generated.id ? 'Downloading...' : 'Download PDF'} icon={<FileDown size={11} />}
                  onClick={() => downloadPdf(generated)} disabled={downloading === generated.id} />
              </div>
            </div>
          )}
        </div>

        {/* History */}
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--c-border)', fontSize: 11, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase' }}>
            Generated Certificates ({certs.length})
          </div>
          {certs.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>No certificates generated yet</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Student', 'Type', 'Serial No.', 'Date', ''].map((hd, i) => (
                    <th key={i} style={{ padding: '9px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase', background: 'var(--c-deep)', borderBottom: '1px solid var(--c-border)' }}>{hd}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {certs.map((c, i) => (
                  <tr key={c.id || i} style={{ borderBottom: i < certs.length - 1 ? '1px solid #242424' : 'none' }}>
                    <td style={{ padding: '9px 14px', fontSize: 12, color: 'var(--c-text)' }}>{c.student_name || c.content_data?.student_name || 'N/A'}</td>
                    <td style={{ padding: '9px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{CERT_LABELS[c.cert_type] || c.cert_type}</td>
                    <td style={{ padding: '9px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: 'var(--c-muted)' }}>{c.serial_number}</td>
                    <td style={{ padding: '9px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{c.issued_date}</td>
                    <td style={{ padding: '9px 14px' }}>
                      <button onClick={() => downloadPdf(c)} disabled={downloading === (c.id || c.serial_number)}
                        style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 5, padding: '4px 9px', color: '#93c5fd', fontSize: 11, cursor: 'pointer', fontWeight: 600 }}>
                        <FileDown size={11} />
                        {downloading === (c.id || c.serial_number) ? '...' : 'PDF'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </ToolPage>
  );
}

// 5. Circular & Notice Sender
export function CircularSender() {
  const { currentUser } = useUser();
  const [announcements, setAnnouncements] = useState([]);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const BLANK = { title: '', content: '', audience_type: 'all', audience_classes: [], audience_roles: [] };
  const [form, setForm] = useState(BLANK);
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  const ROLES = ['owner', 'admin', 'teacher', 'student'];

  const toggleArr = (key, val) => setForm(p => ({
    ...p,
    [key]: p[key].includes(val) ? p[key].filter(x => x !== val) : [...p[key], val],
  }));

  const load = async () => {
    const r = await fetch(`${API}/ops/announcements`, { headers: h(currentUser) }).then(r => r.json());
    if (r.success) setAnnouncements(r.data || []);
  };

  useEffect(() => {
    Promise.all([
      load(),
      getAllClasses(currentUser).then(r => { if (r.success) setClasses(r.data || []); }),
    ]).finally(() => setLoading(false));
  }, []);

  const send = async (e) => {
    e.preventDefault();
    if (!form.title.trim() || !form.content.trim()) { setError('Title and content are required'); return; }
    if (form.audience_type === 'class' && form.audience_classes.length === 0) { setError('Select at least one class'); return; }
    if (form.audience_type === 'role' && form.audience_roles.length === 0) { setError('Select at least one role'); return; }
    setSending(true); setError('');
    try {
      const res = await fetch(`${API}/ops/announcements`, {
        method: 'POST', headers: h(currentUser),
        body: JSON.stringify({ ...form, is_draft: false }),
      }).then(r => r.json());
      if (res.success) {
        setForm(BLANK);
        setSent(true);
        setTimeout(() => setSent(false), 2500);
        await load();
      } else {
        setError(res.detail || res.message || 'Failed to send');
      }
    } catch { setError('Network error'); }
    setSending(false);
  };

  const audienceLabel = (a) => {
    if (a.audience_type === 'class') return `Class: ${(a.audience_classes || []).join(', ') || 'N/A'}`;
    if (a.audience_type === 'role') return `Role: ${(a.audience_roles || []).join(', ') || 'N/A'}`;
    return 'All';
  };

  const chipStyle = (active) => ({
    display: 'inline-flex', alignItems: 'center', padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer',
    background: active ? 'rgba(59,130,246,0.2)' : 'var(--c-deep)',
    border: `1px solid ${active ? '#4f8ff7' : 'var(--c-border)'}`,
    color: active ? '#93c5fd' : 'var(--c-faint)',
    userSelect: 'none',
  });

  return (
    <ToolPage title="Circular & Notice Sender" subtitle="Send notices to all, by class, or by role" loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'start' }}>
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>New Circular</h3>
          <form onSubmit={send}>
            <FormField label="Title" value={form.title} onChange={f('title')} placeholder="Circular title" required />
            <FormField label="Content" type="textarea" value={form.content} onChange={f('content')} placeholder="Write the circular..." required />

            {/* Audience type */}
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Send To</label>
              <div style={{ display: 'flex', gap: 6 }}>
                {[['all', 'Everyone'], ['class', 'By Class'], ['role', 'By Role']].map(([val, lbl]) => (
                  <span key={val} style={chipStyle(form.audience_type === val)} onClick={() => f('audience_type')(val)}>{lbl}</span>
                ))}
              </div>
            </div>

            {/* Class multi-select */}
            {form.audience_type === 'class' && (
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Select Classes</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {classes.map(c => {
                    const label = `${c.name}-${c.section}`;
                    const active = form.audience_classes.includes(label);
                    return <span key={c.id} style={chipStyle(active)} onClick={() => toggleArr('audience_classes', label)}>{label}</span>;
                  })}
                  {classes.length === 0 && <span style={{ fontSize: 11, color: 'var(--c-faint)' }}>No classes found</span>}
                </div>
              </div>
            )}

            {/* Role multi-select */}
            {form.audience_type === 'role' && (
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Select Roles</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  {ROLES.map(role => (
                    <span key={role} style={chipStyle(form.audience_roles.includes(role))} onClick={() => toggleArr('audience_roles', role)}
                    >{role.charAt(0).toUpperCase() + role.slice(1)}</span>
                  ))}
                </div>
              </div>
            )}

            {error && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 10 }}>{error}</div>}
            <ActionBtn
              type="submit"
              label={sending ? 'Sending...' : sent ? '✓ Sent!' : 'Send Circular'}
              disabled={sending}
              variant={sent ? 'success' : 'primary'}
            />
          </form>
        </div>

        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--c-border)', fontSize: 11, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase' }}>
            Recent Circulars ({announcements.length})
          </div>
          {announcements.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>No circulars sent yet</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Title', 'Sent To', 'Date'].map(hd => (
                    <th key={hd} style={{ padding: '9px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase', background: 'var(--c-deep)', borderBottom: '1px solid var(--c-border)' }}>{hd}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {announcements.map((a, i) => (
                  <tr key={a.id || i} style={{ borderBottom: i < announcements.length - 1 ? '1px solid #242424' : 'none' }}>
                    <td style={{ padding: '9px 14px', fontSize: 12, color: 'var(--c-text)', fontWeight: 500 }}>{a.title}</td>
                    <td style={{ padding: '9px 14px', fontSize: 11, color: 'var(--c-muted)' }}>{audienceLabel(a)}</td>
                    <td style={{ padding: '9px 14px', fontSize: 11, color: 'var(--c-faint)' }}>{a.created_at?.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </ToolPage>
  );
}

// 6. Enquiry Register
export function EnquiryRegister() {
  const { currentUser } = useUser();
  const [enquiries, setEnquiries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [selectedEnquiry, setSelectedEnquiry] = useState(null);
  const [form, setForm] = useState({ student_name: '', parent_name: '', phone: '', class_applying: '', source: 'walk_in' });
  const [error, setError] = useState('');
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  const stages = ['new', 'contacted', 'visit_scheduled', 'visited', 'documents_submitted', 'fee_paid', 'enrolled', 'lost'];
  const stageLabels = { new: 'New', contacted: 'Contacted', visit_scheduled: 'Visit Scheduled', visited: 'Visited', documents_submitted: 'Documents', fee_paid: 'Fee Paid', enrolled: 'Enrolled ✓', lost: 'Lost ✗' };
  const statusColors = { new: 'blue', contacted: 'yellow', visit_scheduled: 'purple', visited: 'purple', documents_submitted: 'yellow', fee_paid: 'green', enrolled: 'green', lost: 'red' };

  useEffect(() => { load(); }, []);
  const load = async () => { setLoading(true); try { const r = await fetch(`${API}/ops/enquiries`, { headers: h(currentUser) }).then(r => r.json()); if (r.success) setEnquiries(r.data || []); } catch {} setLoading(false); };

  const handleAdd = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.student_name || !form.parent_name || !form.phone) { setError('Name, parent, and phone are required'); return; }
    try {
      const res = await fetch(`${API}/ops/enquiries`, { method: 'POST', headers: h(currentUser), body: JSON.stringify(form) }).then(r => r.json());
      if (res.success) {
        setShowForm(false);
        setForm({ student_name: '', parent_name: '', phone: '', class_applying: '', source: 'walk_in' });
        load();
      } else {
        setError('Failed to add enquiry');
      }
    } catch { setError('Network error'); }
  };

  const updateStatus = async (id, newStatus) => {
    try {
      const res = await fetch(`${API}/ops/enquiries/${id}`, { method: 'PATCH', headers: h(currentUser), body: JSON.stringify({ status: newStatus }) }).then(r => r.json());
      if (res.success) {
        load();
        setSelectedEnquiry(null);
      }
    } catch { }
  };

  return (
    <ToolPage title="Enquiry Register" subtitle="Track admission leads through pipeline" onRefresh={load} loading={loading}
      actions={<ActionBtn label="New Enquiry" onClick={() => setShowForm(true)} icon={<Plus size={11} />} />}>
      {showForm && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Add New Enquiry</h3>
          <form onSubmit={handleAdd}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Student Name" value={form.student_name} onChange={f('student_name')} placeholder="Prospective student" required />
              <FormField label="Parent Name" value={form.parent_name} onChange={f('parent_name')} placeholder="Parent/guardian" required />
              <FormField label="Phone" type="tel" value={form.phone} onChange={f('phone')} placeholder="10-digit mobile" required />
              <FormField label="Class Applying" value={form.class_applying} onChange={f('class_applying')} placeholder="e.g. Class 9" />
              <FormField label="Source" type="select" value={form.source} onChange={f('source')} options={[
                { value: 'walk_in', label: 'Walk In' },
                { value: 'phone', label: 'Phone Call' },
                { value: 'referral', label: 'Referral' },
                { value: 'online', label: 'Online' },
                { value: 'ad', label: 'Advertisement' }
              ]} />
            </div>
            {error && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 8, marginTop: 8 }}>{error}</div>}
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button type="submit" style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid #4f8ff7', background: '#4f8ff7', color: '#fff', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>Add Enquiry</button>
              <button type="button" onClick={() => { setShowForm(false); setError(''); }} style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid var(--c-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {selectedEnquiry && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 16, marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}>
            <h4 style={{ color: 'var(--c-text)', fontSize: 13, fontWeight: 600 }}>{selectedEnquiry.student_name} - Move to Stage</h4>
            <button onClick={() => setSelectedEnquiry(null)} style={{ background: 'transparent', border: 'none', color: 'var(--c-faint)', cursor: 'pointer', fontSize: 14 }}>✕</button>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {stages.map(s => (
              <button key={s} onClick={() => updateStatus(selectedEnquiry.id, s)} disabled={selectedEnquiry.status === s}
                style={{ padding: '6px 10px', borderRadius: 6, border: `1px solid ${selectedEnquiry.status === s ? 'var(--c-faint)' : '#4f8ff7'}`, background: selectedEnquiry.status === s ? 'var(--c-deep)' : '#4f8ff7', color: selectedEnquiry.status === s ? 'var(--c-faint)' : '#fff', fontSize: 11, cursor: selectedEnquiry.status === s ? 'default' : 'pointer', fontWeight: 500, opacity: selectedEnquiry.status === s ? 0.5 : 1 }}>
                {stageLabels[s]}
              </button>
            ))}
          </div>
        </div>
      )}

      <DataTable headers={['Student', 'Parent', 'Phone', 'Class', 'Status', 'Source', 'Date', 'Action']}
        rows={enquiries.map(e => [
          e.student_name,
          e.parent_name,
          e.phone,
          e.class_applying || 'N/A',
          <Badge text={stageLabels[e.status] || e.status} color={statusColors[e.status] || 'blue'} />,
          e.source?.replace('_', ' '),
          e.created_at?.slice(0, 10),
          <button onClick={() => setSelectedEnquiry(e)} style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 5, padding: '3px 8px', color: '#4f8ff7', fontSize: 10, cursor: 'pointer', fontWeight: 500 }}>Move Stage</button>
        ])}
        emptyMsg="No enquiries yet"
      />
    </ToolPage>
  );
}

// 7-19: Remaining Admin Tools (some skeleton, some functional)
export function DocumentScanner() {
  const { currentUser } = useUser();
  const [files, setFiles] = useState([]);
  const [classes, setClasses] = useState([]);
  const [allStudents, setAllStudents] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [studentId, setStudentId] = useState('');
  const [docType, setDocType] = useState('aadhar');
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const inputRef = React.useRef(null);

  useEffect(() => {
    Promise.all([
      getAllClasses(currentUser).then(r => { if (r.success) setClasses(r.data || []); }),
      fetch(`${API}/students/`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setAllStudents(r.data || []); }),
    ]).finally(() => setLoading(false));
  }, []);

  // Reset student selection when class changes
  const handleClassChange = (cls) => { setSelectedClass(cls); setStudentId(''); };

  const studentsInClass = selectedClass
    ? allStudents.filter(s => s.class_id === selectedClass)
    : allStudents;

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!studentId) return;
    setUploading(true);
    setResult(null);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('entity_type', 'students');
    formData.append('entity_id', studentId);
    try {
      const res = await fetch(`${API}/uploads`, {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders(null),
        body: formData,
      }).then(r => r.json());
      if (res.success) {
        setResult({ ...res.data, doc_type: docType });
        setFiles(prev => [...prev, { ...res.data, doc_type: docType, student_name: allStudents.find(s => s.id === studentId)?.name || 'Unknown' }]);
        await fetch(`${API}/students/${studentId}`, { method: 'PATCH', headers: h(currentUser), body: JSON.stringify({ [`documents.${docType}`]: res.data.file_url }) });
      } else {
        setResult({ error: res.detail || 'Upload failed' });
      }
    } catch { setResult({ error: 'Network error' }); }
    setUploading(false);
    e.target.value = '';
  };

  const selStyle = { width: '100%', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: '9px 12px', color: 'var(--c-text)', fontSize: 13, outline: 'none', marginBottom: 12 };
  const lbl = (t) => <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>{t}</label>;

  return (
    <ToolPage title="Document Scanner & Extractor" subtitle="Upload and file student documents by class" loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, maxWidth: 900 }}>
        <div>
          <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 14, fontWeight: 600, color: 'var(--c-text)', marginBottom: 14 }}>Upload Document</h3>

          {/* Class dropdown */}
          <div style={{ marginBottom: 12 }}>
            {lbl('Class / Section')}
            <select value={selectedClass} onChange={e => handleClassChange(e.target.value)} style={selStyle}>
              <option value="">All Classes</option>
              {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
            </select>
          </div>

          {/* Student dropdown — filtered by class */}
          <div style={{ marginBottom: 12 }}>
            {lbl('Student *')}
            <select value={studentId} onChange={e => setStudentId(e.target.value)} style={selStyle}>
              <option value="">Select student...</option>
              {studentsInClass.map(s => <option key={s.id} value={s.id}>{s.name} {s.admission_number ? `(${s.admission_number})` : ''}</option>)}
            </select>
          </div>

          {/* Document type */}
          <div style={{ marginBottom: 16 }}>
            {lbl('Document Type')}
            <select value={docType} onChange={e => setDocType(e.target.value)} style={selStyle}>
              {[['aadhar', 'Aadhar Card'], ['birth_cert', 'Birth Certificate'], ['tc', 'Transfer Certificate'], ['photo', 'Student Photo'], ['mark_sheet', 'Mark Sheet'], ['other', 'Other']].map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>

          <input type="file" ref={inputRef} style={{ display: 'none' }} accept=".pdf,.jpg,.jpeg,.png,.heic" onChange={handleUpload} />
          <ActionBtn label={uploading ? 'Uploading...' : 'Choose & Upload File'} onClick={() => { if (!studentId) { setResult({ error: 'Please select a student first' }); return; } inputRef.current?.click(); }} disabled={uploading} />

          {result && (
            <div style={{ marginTop: 12, padding: 12, background: result.error ? 'rgba(239,68,68,0.08)' : 'rgba(16,185,129,0.08)', border: `1px solid ${result.error ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}`, borderRadius: 8, fontSize: 12, color: result.error ? '#f87171' : '#34d399' }}>
              {result.error ? result.error : `✓ Uploaded: ${result.file_name}`}
            </div>
          )}
        </div>

        <div>
          <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 14, fontWeight: 600, color: 'var(--c-text)', marginBottom: 14 }}>Session Uploads ({files.length})</h3>
          {files.length === 0 ? (
            <p style={{ color: 'var(--c-faint)', fontSize: 12 }}>No documents uploaded yet in this session.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {files.map((f, i) => (
                <div key={i} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: '10px 14px' }}>
                  <div style={{ fontSize: 12, color: 'var(--c-text)', fontWeight: 500 }}>{f.file_name}</div>
                  <div style={{ fontSize: 11, color: 'var(--c-faint)', marginTop: 3 }}>{f.student_name} · {f.doc_type} {f.file_size_kb ? `· ${f.file_size_kb}KB` : ''}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </ToolPage>
  );
}
export function SmartFeeDefaulter() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [twilioConfigured, setTwilioConfigured] = useState(false);
  const [selectedDefaulter, setSelectedDefaulter] = useState(null);
  const [smsForm, setSmsForm] = useState({ phone: '', message: '' });
  const [sending, setSending] = useState(false);
  const [smsResult, setSmsResult] = useState(null);
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkTemplate, setBulkTemplate] = useState('Dear {name}, your school fee of ₹{amount} is overdue. Please pay immediately to avoid penalty. Contact: school office.');
  const [bulkSending, setBulkSending] = useState(false);
  const [bulkResult, setBulkResult] = useState(null);
  const [selectedRows, setSelectedRows] = useState([]);
  const [smsLogs, setSmsLogs] = useState([]);
  const [viewMode, setViewMode] = useState('defaulters');

  const defaulters = data?.defaulters || [];

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/tools/get_fee_summary/execute`, {
        method: 'POST',
        headers: h(currentUser),
        body: JSON.stringify({ params: {} }),
      });
      if (!res.ok) {
        console.error('fee summary: server error', res.status);
        return;
      }
      const r = await res.json();
      if (r.success) setData(r.data);
    } catch (e) {
      console.error('fee summary:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let alive = true;
    loadData();
    fetch(`${API}/sms/config-status`, { headers: h(currentUser) })
      .then(r => r.json())
      .then(r => { if (alive && r.success) setTwilioConfigured(r.data.configured); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  const loadLogs = async () => {
    const r = await fetch(`${API}/sms/logs`, { headers: h(currentUser) }).then(r => r.json());
    if (r.success) setSmsLogs(r.data || []);
  };

  const openSmsForm = (d) => {
    setSelectedDefaulter(d);
    setSmsResult(null);
    setSmsForm({
      phone: d.phone || d.guardian_phone || '',
      message: `Dear ${d.student_name}, your school fee of ₹${d.amount_overdue || d.amount_overdue_fmt} is overdue for ${d.days_overdue} days. Please pay immediately. Contact school office.`
    });
  };

  const handleSendSingle = async (e) => {
    e.preventDefault();
    if (!smsForm.phone) { setSmsResult({ error: 'Phone number is required' }); return; }
    setSending(true);
    setSmsResult(null);
    try {
      const res = await fetch(`${API}/sms/send-reminder`, {
        method: 'POST',
        headers: h(currentUser),
        body: JSON.stringify({
          student_id: selectedDefaulter.student_id,
          student_name: selectedDefaulter.student_name,
          phone: smsForm.phone,
          message: smsForm.message,
          amount: selectedDefaulter.amount_overdue || selectedDefaulter.amount_overdue_fmt
        })
      }).then(r => r.json());
      if (res.success) {
        setSmsResult({ success: true, status: res.data.status });
      } else {
        setSmsResult({ error: res.detail || 'Failed to send' });
      }
    } catch (err) {
      setSmsResult({ error: err.message });
    } finally {
      setSending(false);
    }
  };

  const handleSendBulk = async () => {
    const targets = selectedRows.length > 0
      ? defaulters.filter(d => selectedRows.includes(d.student_id))
      : defaulters;
    if (!targets.length) return;
    setBulkSending(true);
    setBulkResult(null);
    try {
      const res = await fetch(`${API}/sms/send-bulk`, {
        method: 'POST',
        headers: h(currentUser),
        body: JSON.stringify({
          message_template: bulkTemplate,
          recipients: targets.map(d => ({
            student_id: d.student_id,
            student_name: d.student_name,
            phone: d.phone || d.guardian_phone || '',
            amount: d.amount_overdue || d.amount_overdue_fmt
          }))
        })
      }).then(r => r.json());
      if (res.success) setBulkResult(res.data);
    } catch (err) {
      setBulkResult({ error: err.message });
    } finally {
      setBulkSending(false);
    }
  };

  const toggleRow = (id) => setSelectedRows(p => p.includes(id) ? p.filter(r => r !== id) : [...p, id]);
  const toggleAll = () => setSelectedRows(p => p.length === defaulters.length ? [] : defaulters.map(d => d.student_id));

  return (
    <ToolPage title="Smart Fee Defaulter Manager" subtitle="Overdue fees with SMS reminders" loading={loading} onRefresh={loadData}>

      {/* Config Warning */}
      {!twilioConfigured && (
        <div style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontSize: 12, color: '#fbbf24' }}>
          ⚠️ Twilio not configured. Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER to your .env file to enable SMS sending.
        </div>
      )}

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16, maxWidth: 600 }}>
        <StatCard value={data?.stats?.total_overdue || '₹0'} label="TOTAL OVERDUE" color="#f87171" />
        <StatCard value={data?.stats?.students_with_dues || 0} label="STUDENTS" color="#fbbf24" />
        <StatCard value={data?.stats?.collection_rate || '0%'} label="COLLECTION RATE" color="#34d399" />
      </div>

      {/* View Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, borderBottom: '1px solid var(--c-border)', paddingBottom: 12 }}>
        {['defaulters', 'bulk', 'logs'].map(v => (
          <button key={v} onClick={() => { setViewMode(v); if (v === 'logs') loadLogs(); }}
            style={{ padding: '6px 12px', borderRadius: 6, border: viewMode === v ? '1px solid #4f8ff7' : '1px solid var(--c-border)', background: viewMode === v ? 'rgba(59,130,246,0.1)' : 'var(--c-bg)', color: viewMode === v ? '#4f8ff7' : 'var(--c-muted)', fontSize: 12, cursor: 'pointer', textTransform: 'capitalize' }}>
            {v === 'defaulters' ? 'Defaulters' : v === 'bulk' ? 'Bulk Reminder' : 'SMS Logs'}
          </button>
        ))}
      </div>

      {/* Defaulters List */}
      {viewMode === 'defaulters' && (
        <>
          {/* Single SMS Panel */}
          {selectedDefaulter && (
            <div style={{ background: 'var(--c-bg)', border: '1px solid #4f8ff7', borderRadius: 11, padding: 18, marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h4 style={{ color: 'var(--c-text)', fontSize: 13, fontWeight: 600 }}>Send SMS — {selectedDefaulter.student_name}</h4>
                <button onClick={() => { setSelectedDefaulter(null); setSmsResult(null); }} style={{ background: 'transparent', border: 'none', color: 'var(--c-faint)', cursor: 'pointer', fontSize: 16 }}>✕</button>
              </div>
              <form onSubmit={handleSendSingle}>
                <div style={{ marginBottom: 10 }}>
                  <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>PHONE NUMBER</label>
                  <input value={smsForm.phone} onChange={e => setSmsForm(p => ({ ...p, phone: e.target.value }))}
                    placeholder="e.g. 9876543210" required
                    style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box' }} />
                </div>
                <div style={{ marginBottom: 10 }}>
                  <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>MESSAGE ({smsForm.message.length}/160)</label>
                  <textarea value={smsForm.message} onChange={e => setSmsForm(p => ({ ...p, message: e.target.value }))}
                    maxLength={320} required rows={3}
                    style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', resize: 'vertical' }} />
                </div>
                {smsResult && (
                  <div style={{ padding: '8px 12px', borderRadius: 6, marginBottom: 10, fontSize: 12,
                    background: smsResult.success ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                    border: `1px solid ${smsResult.success ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
                    color: smsResult.success ? '#34d399' : '#f87171' }}>
                    {smsResult.success ? `✓ SMS ${smsResult.status === 'not_configured' ? 'logged (Twilio not configured)' : 'sent successfully!'}` : `✗ ${smsResult.error}`}
                  </div>
                )}
                <button type="submit" disabled={sending}
                  style={{ padding: '8px 16px', borderRadius: 6, background: '#4f8ff7', border: '1px solid #4f8ff7', color: '#fff', fontSize: 12, cursor: sending ? 'not-allowed' : 'pointer', fontWeight: 600, opacity: sending ? 0.6 : 1 }}>
                  {sending ? 'Sending...' : '📱 Send SMS'}
                </button>
              </form>
            </div>
          )}

          <DataTable headers={['Student', 'Class', 'Amount Due', 'Days Overdue', 'Action']}
            rows={defaulters.map(d => [
              d.student_name,
              d.class,
              <span style={{ color: '#f87171', fontWeight: 600 }}>{d.amount_overdue_fmt}</span>,
              <span style={{ color: d.days_overdue > 30 ? '#f87171' : '#fbbf24' }}>{d.days_overdue} days</span>,
              <button onClick={() => openSmsForm(d)}
                style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 5, padding: '4px 10px', color: '#4f8ff7', fontSize: 11, cursor: 'pointer', fontWeight: 500 }}>
                📱 Remind
              </button>
            ])}
            emptyMsg="No fee defaulters found"
          />
        </>
      )}

      {/* Bulk Reminder */}
      {viewMode === 'bulk' && (
        <div style={{ maxWidth: 600 }}>
          <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 18, marginBottom: 14 }}>
            <h4 style={{ color: 'var(--c-text)', fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Bulk SMS Reminder</h4>
            <p style={{ color: 'var(--c-faint)', fontSize: 12, marginBottom: 12 }}>
              Use <code style={{ background: 'var(--c-deep)', padding: '1px 4px', borderRadius: 3, color: 'var(--c-muted)' }}>{'{name}'}</code> and <code style={{ background: 'var(--c-deep)', padding: '1px 4px', borderRadius: 3, color: 'var(--c-muted)' }}>{'{amount}'}</code> as placeholders.
            </p>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>MESSAGE TEMPLATE ({bulkTemplate.length}/160)</label>
              <textarea value={bulkTemplate} onChange={e => setBulkTemplate(e.target.value)} rows={4} maxLength={320}
                style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', resize: 'vertical' }} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 8 }}>RECIPIENTS</label>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button onClick={toggleAll}
                  style={{ padding: '5px 10px', borderRadius: 5, border: '1px solid var(--c-border)', background: 'var(--c-deep)', color: 'var(--c-muted)', fontSize: 11, cursor: 'pointer' }}>
                  {selectedRows.length === defaulters.length ? 'Deselect All' : 'Select All'}
                </button>
                <span style={{ color: 'var(--c-faint)', fontSize: 12, alignSelf: 'center' }}>
                  {selectedRows.length > 0 ? `${selectedRows.length} selected` : `All ${defaulters.length} defaulters`}
                </span>
              </div>
            </div>
            {bulkResult && (
              <div style={{ padding: '10px 12px', borderRadius: 6, marginBottom: 12, fontSize: 12, background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', color: 'var(--c-text)' }}>
                {bulkResult.error ? (
                  <span style={{ color: '#f87171' }}>✗ {bulkResult.error}</span>
                ) : (
                  <>✓ Sent: <strong style={{ color: '#34d399' }}>{bulkResult.sent}</strong> &nbsp; Failed: <strong style={{ color: '#f87171' }}>{bulkResult.failed}</strong></>
                )}
              </div>
            )}
            <button onClick={handleSendBulk} disabled={bulkSending || defaulters.length === 0}
              style={{ padding: '9px 18px', borderRadius: 6, background: '#4f8ff7', border: '1px solid #4f8ff7', color: '#fff', fontSize: 12, cursor: bulkSending ? 'not-allowed' : 'pointer', fontWeight: 600, opacity: bulkSending ? 0.6 : 1 }}>
              {bulkSending ? 'Sending...' : `📱 Send to ${selectedRows.length > 0 ? selectedRows.length : defaulters.length} Students`}
            </button>
          </div>
        </div>
      )}

      {/* SMS Logs */}
      {viewMode === 'logs' && (
        <DataTable headers={['Student', 'Phone', 'Status', 'Sent At', 'By']}
          rows={smsLogs.map(l => [
            l.student_name,
            l.phone,
            <Badge text={l.status} color={l.status === 'sent' ? 'green' : l.status === 'not_configured' ? 'yellow' : 'red'} />,
            l.sent_at?.slice(0, 16).replace('T', ' '),
            l.sent_by_name || 'Admin'
          ])}
          emptyMsg="No SMS logs yet"
        />
      )}
    </ToolPage>
  );
}
export function AdmissionPipeline() { return <AdmissionFunnelAdmin />; }
function AdmissionFunnelAdmin() {
  const { currentUser } = useUser();
  const [enquiries, setEnquiries] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { fetch(`${API}/ops/enquiries`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setEnquiries(r.data || []); }).finally(() => setLoading(false)); }, []);
  const stages = ['new', 'contacted', 'visit_scheduled', 'visited', 'documents_submitted', 'fee_paid', 'enrolled', 'lost'];
  const counts = stages.reduce((acc, s) => { acc[s] = enquiries.filter(e => e.status === s).length; return acc; }, {});
  return (
    <ToolPage title="Admission Pipeline" subtitle="Track conversion funnel" loading={loading}>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 18 }}>
        {stages.map(s => <div key={s} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: '8px 12px', textAlign: 'center', minWidth: 85 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: s === 'enrolled' ? '#34d399' : s === 'lost' ? '#f87171' : 'var(--c-text)', fontFamily: 'Inter, sans-serif' }}>{counts[s] || 0}</div>
          <div style={{ fontSize: 9, color: 'var(--c-faint)', textTransform: 'capitalize', fontWeight: 600 }}>{s.replace('_', ' ')}</div>
        </div>)}
      </div>
    </ToolPage>
  );
}
export function ParentMessage() {
  const { currentUser } = useUser();
  const [classes, setClasses] = useState([]);
  const [allStudents, setAllStudents] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [selectedStudents, setSelectedStudents] = useState(new Set());
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [log, setLog] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/settings/classes`, { headers: h(currentUser) }).then(r => r.json()),
      fetch(`${API}/students/`, { headers: h(currentUser) }).then(r => r.json()),
    ]).then(([cls, stu]) => {
      if (cls.success) setClasses(cls.data || []);
      if (stu.success) setAllStudents(stu.data || []);
    }).finally(() => setLoading(false));
  }, []);

  const studentsInClass = selectedClass
    ? allStudents.filter(s => s.class_id === selectedClass)
    : allStudents;


  const allInClassSelected = studentsInClass.length > 0 && studentsInClass.every(s => selectedStudents.has(s.id));

  const toggleStudent = (id) => {
    setSelectedStudents(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAllInClass = () => {
    setSelectedStudents(prev => {
      const next = new Set(prev);
      if (allInClassSelected) {
        studentsInClass.forEach(s => next.delete(s.id));
      } else {
        studentsInClass.forEach(s => next.add(s.id));
      }
      return next;
    });
  };

  const handleSend = async () => {
    if (!message.trim() || selectedStudents.size === 0) return;
    setSending(true);
    setResult(null);
    try {
      const res = await fetch(`${API}/sms/send-parent-message`, {
        method: 'POST',
        headers: h(currentUser),
        body: JSON.stringify({ student_ids: [...selectedStudents], message }),
      }).then(r => r.json());
      if (res.success) {
        const d = res.data;
        setResult(d);
        setLog(prev => [{
          message,
          count: selectedStudents.size,
          sent: d.sent,
          failed: d.failed,
          no_phone: d.no_phone,
          not_configured: d.not_configured,
          time: new Date().toLocaleTimeString(),
        }, ...prev]);
        setMessage('');
        setSelectedStudents(new Set());
      }
    } catch { setResult({ error: 'Network error. Please try again.' }); }
    setSending(false);
  };

  const inp = { width: '100%', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none' };

  return (
    <ToolPage title="Parent Message Composer" subtitle="Send SMS to parents via Twilio" loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, maxWidth: 980 }}>

        {/* Left — recipient selector */}
        <div>
          <div style={{ marginBottom: 12 }}>
            <label style={{ fontSize: 10, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 6 }}>1. Select Class</label>
            <select value={selectedClass} onChange={e => { setSelectedClass(e.target.value); setSelectedStudents(new Set()); }} style={inp}>
              <option value="">— All Classes —</option>
              {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
            </select>
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <label style={{ fontSize: 10, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                2. Select Students ({selectedStudents.size} selected)
              </label>
              {studentsInClass.length > 0 && (
                <button onClick={toggleAllInClass} style={{ fontSize: 10, fontWeight: 700, color: '#4f8ff7', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                  {allInClassSelected ? 'Deselect All' : 'Select All'}
                </button>
              )}
            </div>
            <div style={{ border: '1px solid var(--c-border)', borderRadius: 8, maxHeight: 320, overflowY: 'auto' }}>
              {studentsInClass.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>No students found</div>
              ) : studentsInClass.map((s, i) => (
                <label key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderBottom: i < studentsInClass.length - 1 ? '1px solid var(--c-border)' : 'none', cursor: 'pointer', background: selectedStudents.has(s.id) ? 'rgba(59,130,246,0.06)' : 'transparent' }}>
                  <input type="checkbox" checked={selectedStudents.has(s.id)} onChange={() => toggleStudent(s.id)} style={{ accentColor: '#4f8ff7' }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--c-text)' }}>{s.name}</div>
                    <div style={{ fontSize: 10, color: 'var(--c-faint)' }}>Roll {s.roll_number || 'N/A'} · {classes.find(c => c.id === s.class_id) ? `${classes.find(c => c.id === s.class_id).name}-${classes.find(c => c.id === s.class_id).section}` : ''}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Right — compose & send */}
        <div>
          <div style={{ marginBottom: 12 }}>
            <label style={{ fontSize: 10, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 6 }}>3. Compose SMS</label>
            <textarea value={message} onChange={e => setMessage(e.target.value)} rows={6} placeholder="Type your message to parents... e.g. PTM is scheduled for Friday 10 AM. Please attend."
              style={{ ...inp, resize: 'vertical' }} />
            <div style={{ fontSize: 10, color: 'var(--c-faint)', marginTop: 4 }}>{message.length}/160 characters{message.length > 160 ? ' (will be split into multiple SMS)' : ''}</div>
          </div>

          <div style={{ background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontSize: 11, color: '#4f8ff7' }}>
            SMS sent via Twilio to guardian/parent phone numbers on record.
          </div>

          <ActionBtn
            label={sending ? 'Sending...' : `Send SMS to ${selectedStudents.size} Parent${selectedStudents.size !== 1 ? 's' : ''}`}
            onClick={handleSend}
            disabled={sending || !message.trim() || selectedStudents.size === 0}
          />

          {result && (
            <div style={{ marginTop: 12, background: result.error ? 'rgba(239,68,68,0.06)' : 'rgba(16,185,129,0.06)', border: `1px solid ${result.error ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}`, borderRadius: 8, padding: '12px 14px', fontSize: 12 }}>
              {result.error ? (
                <span style={{ color: '#f87171' }}>{result.error}</span>
              ) : (
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                  {result.sent > 0 && <span style={{ color: '#34d399' }}>✓ {result.sent} sent</span>}
                  {result.failed > 0 && <span style={{ color: '#f87171' }}>✗ {result.failed} failed</span>}
                  {result.no_phone > 0 && <span style={{ color: '#fbbf24' }}>⚠ {result.no_phone} no phone</span>}
                  {result.not_configured > 0 && <span style={{ color: 'var(--c-faint)' }}>Twilio not configured — {result.not_configured} logged</span>}
                </div>
              )}
            </div>
          )}

          {log.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h4 style={{ fontFamily: 'Inter, sans-serif', fontSize: 12, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Send History</h4>
              {log.map((l, i) => (
                <div key={i} style={{ fontSize: 11, color: 'var(--c-faint)', padding: '6px 0', borderBottom: '1px solid var(--c-border)' }}>
                  <span style={{ color: 'var(--c-text)', fontWeight: 600 }}>{l.time}</span> — {l.count} students selected · {l.sent ?? 0} sent · {l.failed ?? 0} failed
                  <div style={{ color: 'var(--c-faint)', fontSize: 10, marginTop: 2, fontStyle: 'italic' }}>{l.message.slice(0, 60)}{l.message.length > 60 ? '…' : ''}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </ToolPage>
  );
}

export function StudentTransfer() {
  const { currentUser } = useUser();
  const [classes, setClasses] = useState([]);
  const [allStudents, setAllStudents] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [search, setSearch] = useState('');
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [transferType, setTransferType] = useState('transfer'); // 'transfer' | 'withdrawal' | 'class_change'
  const [reason, setReason] = useState('');
  const [destinationClass, setDestinationClass] = useState('');
  const [destinationSchool, setDestinationSchool] = useState('');
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [done, setDone] = useState(null); // holds result
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      getAllClasses(currentUser).then(r => { if (r.success) setClasses(r.data || []); }),
      fetch(`${API}/students/`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setAllStudents(r.data || []); }),
    ]).finally(() => setLoading(false));
  }, []);

  const filteredStudents = allStudents.filter(s => {
    const matchClass = !selectedClass || s.class_id === selectedClass;
    const matchSearch = !search.trim() || s.name.toLowerCase().includes(search.toLowerCase()) || (s.admission_number || '').toLowerCase().includes(search.toLowerCase());
    return matchClass && matchSearch;
  });

  const handleProcess = async () => {
    if (!selectedStudent) return;
    if (!reason.trim()) { setError('Reason is required'); return; }
    if (transferType === 'class_change' && !destinationClass) { setError('Select destination class'); return; }
    setProcessing(true); setError('');
    try {
      const today = new Date().toISOString().slice(0, 10);
      if (transferType === 'class_change') {
        // Just update class_id
        const res = await fetch(`${API}/students/${selectedStudent.id}`, {
          method: 'PATCH', headers: h(currentUser),
          body: JSON.stringify({ class_id: destinationClass, updated_at: new Date().toISOString() }),
        }).then(r => r.json());
        if (!res.success) throw new Error(res.detail || 'Failed');
        setDone({ type: 'class_change', student: selectedStudent.name, msg: 'Student moved to new class successfully.' });
      } else {
        // Transfer or withdrawal — deactivate student
        const status = transferType === 'transfer' ? 'transferred' : 'withdrawn';
        const patchRes = await fetch(`${API}/students/${selectedStudent.id}`, {
          method: 'PATCH', headers: h(currentUser),
          body: JSON.stringify({ status, is_active: false, withdrawal_reason: reason, withdrawal_date: today }),
        }).then(r => r.json());
        if (!patchRes.success) throw new Error(patchRes.detail || 'Failed to update student');

        // Auto-generate Transfer Certificate
        const cls = selectedStudent.class_info;
        const certRes = await fetch(`${API}/ops/certificates`, {
          method: 'POST', headers: h(currentUser),
          body: JSON.stringify({
            student_id: selectedStudent.id,
            cert_type: 'transfer',
            content_data: {
              student_name: selectedStudent.name,
              class: cls ? `${cls.name}-${cls.section}` : 'N/A',
              issued_by: 'The Aaryans School',
              issued_date: today,
              academic_year: '2025-26',
              reason,
              destination_school: destinationSchool || 'N/A',
            },
          }),
        }).then(r => r.json());
        setDone({
          type: transferType,
          student: selectedStudent.name,
          serial: certRes.data?.serial_number,
          msg: transferType === 'transfer'
            ? `Student transferred. TC generated (Serial: ${certRes.data?.serial_number || 'N/A'}).`
            : 'Student withdrawn. TC generated and saved in Certificates section.',
        });
      }
    } catch (e) { setError(e.message || 'Something went wrong'); }
    setProcessing(false);
  };

  const reset = () => { setDone(null); setSelectedStudent(null); setReason(''); setDestinationClass(''); setDestinationSchool(''); setSearch(''); setError(''); };

  const inpStyle = { flex: 1, background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none' };
  const chipStyle = (active) => ({ padding: '5px 14px', borderRadius: 6, border: `1px solid ${active ? '#6366F1' : 'var(--c-border)'}`, background: active ? 'rgba(99,102,241,0.15)' : 'var(--c-bg)', color: active ? '#A5B4FC' : 'var(--c-muted)', fontSize: 11, fontWeight: 600, cursor: 'pointer' });

  if (done) {
    return (
      <ToolPage title="Student Transfer / Withdrawal" subtitle="Process student transfers and generate TC">
        <div style={{ maxWidth: 520, padding: 32, textAlign: 'center', background: 'var(--c-bg)', border: '1px solid #34d39930', borderRadius: 12 }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>✅</div>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: '#34d399', fontSize: 16, marginBottom: 8 }}>
            {done.type === 'class_change' ? 'Class Changed' : done.type === 'transfer' ? 'Transfer Processed' : 'Withdrawal Processed'}
          </h3>
          <p style={{ color: 'var(--c-muted)', fontSize: 13, lineHeight: 1.6 }}>{done.msg}</p>
          <div style={{ marginTop: 20 }}>
            <ActionBtn label="Process Another" variant="secondary" onClick={reset} />
          </div>
        </div>
      </ToolPage>
    );
  }

  return (
    <ToolPage title="Student Transfer / Withdrawal" subtitle="Transfer, withdraw, or move students between classes" loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, maxWidth: 960 }}>

        {/* Left: find student */}
        <div>
          <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 13, fontWeight: 600, color: 'var(--c-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>1. Find Student</h3>
          <div style={{ marginBottom: 10 }}>
            <select value={selectedClass} onChange={e => { setSelectedClass(e.target.value); setSelectedStudent(null); }} style={{ ...inpStyle, width: '100%', marginBottom: 8 }}>
              <option value="">All Classes</option>
              {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
            </select>
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by name or admission no..." style={{ ...inpStyle, width: '100%' }} />
          </div>
          <div style={{ maxHeight: 340, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {filteredStudents.length === 0 ? (
              <p style={{ fontSize: 12, color: 'var(--c-faint)', padding: '8px 0' }}>No students found</p>
            ) : filteredStudents.map(s => (
              <div key={s.id} onClick={() => { setSelectedStudent(s); setError(''); }}
                style={{ padding: '10px 14px', background: selectedStudent?.id === s.id ? 'rgba(99,102,241,0.12)' : 'var(--c-bg)', border: `1px solid ${selectedStudent?.id === s.id ? '#6366F1' : 'var(--c-border)'}`, borderRadius: 8, cursor: 'pointer' }}>
                <div style={{ fontWeight: 600, color: 'var(--c-text)', fontSize: 13 }}>{s.name}</div>
                <div style={{ fontSize: 11, color: 'var(--c-faint)', marginTop: 2 }}>
                  {s.class_info ? `${s.class_info.name}-${s.class_info.section}` : 'N/A'} · {s.admission_number || 'No Adm. No.'}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: action */}
        <div>
          <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 13, fontWeight: 600, color: 'var(--c-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>2. Action</h3>

          {!selectedStudent ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--c-faint)', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, fontSize: 12 }}>Select a student from the left</div>
          ) : (
            <>
              {/* Selected student card */}
              <div style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.25)', borderRadius: 10, padding: '12px 16px', marginBottom: 16 }}>
                <div style={{ fontWeight: 700, color: 'var(--c-text)', fontSize: 14 }}>{selectedStudent.name}</div>
                <div style={{ fontSize: 11, color: 'var(--c-muted)', marginTop: 3 }}>
                  {selectedStudent.class_info ? `Class ${selectedStudent.class_info.name}-${selectedStudent.class_info.section}` : 'N/A'} · {selectedStudent.admission_number || 'No Adm. No.'}
                </div>
              </div>

              {/* Transfer type */}
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Action Type</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[['transfer', 'Transfer Out'], ['withdrawal', 'Withdraw'], ['class_change', 'Change Class']].map(([val, lbl]) => (
                    <span key={val} style={chipStyle(transferType === val)} onClick={() => { setTransferType(val); setError(''); }}>{lbl}</span>
                  ))}
                </div>
              </div>

              {/* Destination class (class change only) */}
              {transferType === 'class_change' && (
                <div style={{ marginBottom: 12 }}>
                  <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Destination Class *</label>
                  <select value={destinationClass} onChange={e => setDestinationClass(e.target.value)}
                    style={{ width: '100%', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }}>
                    <option value="">Select new class...</option>
                    {classes.filter(c => c.id !== selectedStudent.class_id).map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
                  </select>
                </div>
              )}

              {/* Destination school (transfer only) */}
              {transferType === 'transfer' && (
                <div style={{ marginBottom: 12 }}>
                  <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Destination School (optional)</label>
                  <input value={destinationSchool} onChange={e => setDestinationSchool(e.target.value)} placeholder="e.g. DPS Lucknow"
                    style={{ width: '100%', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }} />
                </div>
              )}

              {/* Reason */}
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Reason *</label>
                <textarea value={reason} onChange={e => setReason(e.target.value)} rows={3}
                  placeholder={transferType === 'class_change' ? 'e.g. Section rearrangement' : 'e.g. Family relocation to Delhi'}
                  style={{ width: '100%', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none', resize: 'vertical' }} />
              </div>

              {transferType !== 'class_change' && (
                <div style={{ background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontSize: 12, color: '#fca5a5' }}>
                  This will deactivate the student and auto-generate a Transfer Certificate.
                </div>
              )}

              {error && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 10 }}>{error}</div>}

              <ActionBtn
                label={processing ? 'Processing...' : transferType === 'class_change' ? 'Move to New Class' : `Process ${transferType === 'transfer' ? 'Transfer' : 'Withdrawal'} & Generate TC`}
                variant={transferType === 'class_change' ? 'primary' : 'danger'}
                onClick={handleProcess}
                disabled={processing || !reason.trim()}
              />
            </>
          )}
        </div>
      </div>
    </ToolPage>
  );
}

export function IdCardGenerator() {
  const { currentUser } = useUser();
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [filterClass, setFilterClass] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState([]);
  const [printing, setPrinting] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/students/`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setStudents(r.data || []); }),
      fetch(`${API}/settings/classes`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setClasses(r.data || []); })
    ]).finally(() => setLoading(false));
  }, []);

  const toggleAll = () => {
    const filtered = filterClass ? students.filter(s => s.class_id === filterClass) : students;
    if (selectedIds.length === filtered.length) setSelectedIds([]);
    else setSelectedIds(filtered.map(s => s.id));
  };

  const printCards = () => {
    const selected = students
      .filter(s => selectedIds.includes(s.id))
      .map(s => ({
        name: s.name,
        class: s.class_info ? `${s.class_info.name}-${s.class_info.section}` : 'N/A',
        admission_number: s.admission_number || 'N/A',
        roll_number: s.roll_number || 'N/A',
      }));
    const filename = `ID-Cards-${new Date().toISOString().slice(0, 10)}.pdf`;
    downloadBlobAsPdf(
      `${API}/image-gen/id-cards`,
      { students: selected, school_name: 'The Aaryans School', academic_year: '2025-26' },
      filename,
      () => setPrinting(true),
      () => setPrinting(false),
    );
  };

  const filtered = filterClass ? students.filter(s => s.class_id === filterClass) : students;

  return (
    <ToolPage title="ID Card Generator" subtitle="Generate printable student ID cards" loading={loading}>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, alignItems: 'center', flexWrap: 'wrap' }}>
        <select value={filterClass} onChange={e => setFilterClass(e.target.value)} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }}>
          <option value="">All Classes</option>
          {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
        </select>
        <ActionBtn label={selectedIds.length === filtered.length ? 'Deselect All' : 'Select All'} variant="secondary" onClick={toggleAll} />
        <ActionBtn label={printing ? 'Generating PDF...' : `Download ${selectedIds.length} ID Cards PDF`} onClick={printCards} disabled={selectedIds.length === 0 || printing} />
      </div>
      <DataTable headers={['', 'Name', 'Class', 'Adm No.', 'Roll']}
        rows={filtered.map(s => [
          <input type="checkbox" checked={selectedIds.includes(s.id)} onChange={() => setSelectedIds(p => p.includes(s.id) ? p.filter(x => x !== s.id) : [...p, s.id])} />,
          s.name,
          s.class_info ? `${s.class_info.name}-${s.class_info.section}` : 'N/A',
          s.admission_number || 'N/A',
          s.roll_number || 'N/A'
        ])}
        emptyMsg="No students found"
      />
    </ToolPage>
  );
}
export function TimetableBuilder() {
  const { currentUser } = useUser();
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [staff, setStaff] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingSlot, setEditingSlot] = useState(null);
  const [form, setForm] = useState({ day_of_week: 1, period_number: 1, subject_id: '', teacher_id: '', start_time: '09:00', end_time: '09:45', room: '' });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const dayOptions = days.map((d, i) => ({ value: i + 1, label: d }));

  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  useEffect(() => {
    Promise.all([
      getAllClasses(currentUser),
      fetch(`${API}/academics/subjects`, { headers: h(currentUser) }).then(r => r.json()),
      fetch(`${API}/staff/`, { headers: h(currentUser) }).then(r => r.json())
    ]).then(([classRes, subjRes, staffRes]) => {
      if (classRes.success && classRes.data.length > 0) {
        setClasses(classRes.data);
        setSelectedClass(classRes.data[0].id);
      }
      if (subjRes.success) setSubjects(subjRes.data || []);
      if (staffRes.success) setStaff(staffRes.data || []);
    }).finally(() => setLoading(false));
  }, []);

  const loadSlots = async (classId) => {
    if (!classId) return;
    try {
      const r = await fetch(`${API}/academics/timetable/${classId}`, { headers: h(currentUser) }).then(r => r.json());
      if (r.success) setSlots(r.data || []);
    } catch { }
  };

  useEffect(() => { loadSlots(selectedClass); }, [selectedClass]);

  const handleSave = async (e) => {
    e.preventDefault();
    setError('');

    if (!selectedClass) { setError('Select a class'); return; }
    if (!form.subject_id) { setError('Select a subject'); return; }
    if (!form.day_of_week) { setError('Select a day'); return; }

    setSaving(true);
    try {
      const payload = {
        class_id: selectedClass,
        day_of_week: parseInt(form.day_of_week),
        period_number: parseInt(form.period_number),
        subject_id: form.subject_id,
        teacher_id: form.teacher_id || null,
        start_time: form.start_time,
        end_time: form.end_time,
        room: form.room
      };

      const url = editingSlot ? `${API}/academics/timetable/${editingSlot.id}` : `${API}/academics/timetable`;
      const method = editingSlot ? 'PATCH' : 'POST';

      const res = await fetch(url, {
        method,
        headers: h(currentUser),
        body: JSON.stringify(payload)
      }).then(r => r.json());

      if (res.success) {
        setShowForm(false);
        setEditingSlot(null);
        setForm({ day_of_week: 1, period_number: 1, subject_id: '', teacher_id: '', start_time: '09:00', end_time: '09:45', room: '' });
        loadSlots(selectedClass);
      } else {
        setError(res.detail || 'Failed to save slot');
      }
    } catch (err) {
      setError('Network error');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (slot) => {
    setEditingSlot(slot);
    setForm({
      day_of_week: slot.day_of_week,
      period_number: slot.period_number,
      subject_id: slot.subject_id,
      teacher_id: slot.teacher_id || '',
      start_time: slot.start_time,
      end_time: slot.end_time,
      room: slot.room || ''
    });
    setShowForm(true);
  };

  const handleDelete = async (slotId) => {
    if (!window.confirm('Delete this slot?')) return;
    try {
      const res = await fetch(`${API}/academics/timetable/${slotId}`, {
        method: 'DELETE',
        headers: h(currentUser)
      }).then(r => r.json());
      if (res.success) loadSlots(selectedClass);
    } catch { }
  };

  const getSubjectName = (id) => subjects.find(s => s.id === id)?.name || 'N/A';
  const getTeacherName = (id) => staff.find(s => s.id === id)?.name || 'N/A';

  return (
    <ToolPage title="Timetable Builder" subtitle="Create and manage class timetables" loading={loading}
      actions={selectedClass && <ActionBtn label="Add Period" onClick={() => { setEditingSlot(null); setShowForm(true); }} icon={<Plus size={11} />} />}>

      <div style={{ marginBottom: 16 }}>
        <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>Select Class</label>
        <select value={selectedClass} onChange={e => setSelectedClass(e.target.value)} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none', width: '100%', maxWidth: 300 }}>
          <option value="">-- Select --</option>
          {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
        </select>
      </div>

      {showForm && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>{editingSlot ? 'Edit Period' : 'Add New Period'}</h3>
          <form onSubmit={handleSave}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
              <FormField label="Day" type="select" value={form.day_of_week} onChange={f('day_of_week')} options={dayOptions} required />
              <FormField label="Period" type="number" value={form.period_number} onChange={f('period_number')} min="1" required />
              <FormField label="Subject" type="select" value={form.subject_id} onChange={f('subject_id')} options={subjects.map(s => ({ value: s.id, label: s.name }))} required />
              <FormField label="Teacher (Optional)" type="select" value={form.teacher_id} onChange={f('teacher_id')} options={[{ value: '', label: 'None' }, ...staff.map(s => ({ value: s.id, label: s.name }))]} />
              <FormField label="Start Time" type="time" value={form.start_time} onChange={f('start_time')} required />
              <FormField label="End Time" type="time" value={form.end_time} onChange={f('end_time')} required />
              <FormField label="Room (Optional)" value={form.room} onChange={f('room')} placeholder="e.g. Room 12" />
            </div>
            {error && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 12 }}>{error}</div>}
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="submit" disabled={saving} style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid #4f8ff7', background: '#4f8ff7', color: '#fff', fontSize: 12, cursor: saving ? 'not-allowed' : 'pointer', fontWeight: 500, opacity: saving ? 0.6 : 1 }}>
                {saving ? 'Saving...' : editingSlot ? 'Update' : 'Add'}
              </button>
              <button type="button" onClick={() => { setShowForm(false); setEditingSlot(null); setError(''); }} style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid var(--c-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <DataTable headers={['Day', 'Period', 'Subject', 'Teacher', 'Time', 'Room', 'Actions']}
        rows={slots.sort((a, b) => a.day_of_week - b.day_of_week || a.period_number - b.period_number).map(s => [
          days[s.day_of_week - 1] || 'N/A',
          s.period_number,
          getSubjectName(s.subject_id),
          s.teacher_id ? getTeacherName(s.teacher_id) : 'N/A',
          `${s.start_time} – ${s.end_time}`,
          s.room || 'N/A',
          <div style={{ display: 'flex', gap: 4 }}>
            <button onClick={() => handleEdit(s)} style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 5, padding: '3px 8px', color: '#4f8ff7', fontSize: 10, cursor: 'pointer' }}>Edit</button>
            <button onClick={() => handleDelete(s.id)} style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 5, padding: '3px 8px', color: '#f87171', fontSize: 10, cursor: 'pointer' }}>Delete</button>
          </div>
        ])}
        emptyMsg={selectedClass ? "No periods added yet" : "Select a class to view timetable"}
      />
    </ToolPage>
  );
}
export function AssetTracker() {
  const { currentUser } = useUser();
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: '', category: '', quantity: 1, location: '', status: 'good' });
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/ops/assets`, { headers: h(currentUser) }).then(r => r.json());
      if (r.success) setAssets(r.data || []);
    } catch {}
    setLoading(false);
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    setError('');

    if (!form.name.trim()) { setError('Asset name is required'); return; }
    if (!form.category) { setError('Category is required'); return; }
    if (form.quantity < 1) { setError('Quantity must be at least 1'); return; }

    setSaving(true);
    try {
      const res = await fetch(`${API}/ops/assets`, {
        method: 'POST',
        headers: h(currentUser),
        body: JSON.stringify({
          name: form.name.trim(),
          category: form.category,
          quantity: form.quantity,
          location: form.location.trim(),
          status: form.status
        })
      }).then(r => r.json());

      if (res.success) {
        setShowForm(false);
        setForm({ name: '', category: '', quantity: 1, location: '', status: 'good' });
        setError('');
        load();
      } else {
        setError(res.detail || 'Failed to add asset');
      }
    } catch (err) {
      console.error('Asset save error:', err);
      setError('Network error - ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <ToolPage title="Asset Tracker" subtitle="Track school inventory & assets" onRefresh={load} loading={loading}
      actions={<ActionBtn label="Add Asset" onClick={() => setShowForm(true)} icon={<Plus size={11} />} />}>
      {showForm && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Add New Asset</h3>
          <form onSubmit={handleAdd}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Asset Name" value={form.name} onChange={f('name')} placeholder="e.g. Computer, Desk, Projector" required />
              <FormField label="Category" type="select" value={form.category} onChange={f('category')} options={[
                { value: 'furniture', label: 'Furniture' },
                { value: 'electronics', label: 'Electronics' },
                { value: 'lab', label: 'Lab Equipment' },
                { value: 'sports', label: 'Sports' },
                { value: 'library', label: 'Library' },
                { value: 'other', label: 'Other' }
              ]} required />
              <FormField label="Quantity" type="number" value={form.quantity} onChange={f('quantity')} min="1" />
              <FormField label="Location" value={form.location} onChange={f('location')} placeholder="e.g. Room 12, Lab A" />
              <FormField label="Status" type="select" value={form.status} onChange={f('status')} options={[
                { value: 'good', label: 'Good' },
                { value: 'needs_repair', label: 'Needs Repair' },
                { value: 'damaged', label: 'Damaged' }
              ]} />
            </div>
            {error && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 12, marginTop: 8 }}>{error}</div>}
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button type="submit" disabled={saving} style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid #4f8ff7', background: '#4f8ff7', color: '#fff', fontSize: 12, cursor: saving ? 'not-allowed' : 'pointer', fontWeight: 500, opacity: saving ? 0.6 : 1 }}>
                {saving ? 'Adding...' : 'Add Asset'}
              </button>
              <button type="button" onClick={() => { setShowForm(false); setError(''); }} style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid var(--c-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>Cancel</button>
            </div>
          </form>
        </div>
      )}
      <DataTable headers={['Name', 'Category', 'Quantity', 'Location', 'Status']}
        rows={assets.map(a => [
          a.name,
          <span style={{ textTransform: 'capitalize' }}>{a.category?.replace('_', ' ') || 'N/A'}</span>,
          a.quantity || 0,
          a.location || 'N/A',
          <Badge text={a.status === 'good' ? 'Good' : a.status === 'needs_repair' ? 'Needs Repair' : 'Damaged'} color={a.status === 'good' ? 'green' : a.status === 'needs_repair' ? 'yellow' : 'red'} />
        ])}
        emptyMsg="No assets logged"
      />
    </ToolPage>
  );
}
export function TransportManager() {
  const { currentUser } = useUser();
  const [routes, setRoutes] = useState([]);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('routes');
  const [selectedRoute, setSelectedRoute] = useState(null);
  const [form, setForm] = useState({ route_name: '', start_point: '', end_point: '', driver_name: '', driver_phone: '', vehicle_no: '', capacity: '', fare: '' });
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [assignForm, setAssignForm] = useState({ student_id: '', bus_route: '' });
  const [showAssign, setShowAssign] = useState(false);
  const [assignError, setAssignError] = useState('');
  const f = k => v => setForm(p => ({ ...p, [k]: v }));
  const fa = k => v => setAssignForm(p => ({ ...p, [k]: v }));

  const load = async () => {
    setLoading(true);
    try {
      const [routesRes, studentsRes] = await Promise.all([
        fetch(`${API}/ops/transport`, { headers: h(currentUser) }).then(r => r.json()),
        getStudents(currentUser, {})
      ]);
      if (routesRes.success) setRoutes(routesRes.data || []);
      if (studentsRes.success) setStudents(studentsRes.data || []);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.route_name || !form.start_point || !form.end_point) {
      alert('Route name, start point, and end point are required');
      return;
    }
    const method = editingId ? 'PATCH' : 'POST';
    const url = editingId ? `${API}/ops/transport/${editingId}` : `${API}/ops/transport`;
    try {
      const res = await fetch(url, { method, headers: h(currentUser), body: JSON.stringify(form) }).then(r => r.json());
      if (res.success) {
        setShowForm(false);
        setEditingId(null);
        setForm({ route_name: '', start_point: '', end_point: '', driver_name: '', driver_phone: '', vehicle_no: '', capacity: '', fare: '' });
        load();
      }
    } catch {}
  };

  const handleEdit = (route) => {
    setForm(route);
    setEditingId(route.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this route?')) return;
    try {
      const res = await fetch(`${API}/ops/transport/${id}`, { method: 'DELETE', headers: h(currentUser) }).then(r => r.json());
      if (res.success) load();
    } catch {}
  };

  const handleAssign = async (e) => {
    e.preventDefault();
    setAssignError('');
    if (!assignForm.student_id || !assignForm.bus_route) {
      setAssignError('Select both student and route');
      return;
    }
    try {
      const res = await fetch(`${API}/students/${assignForm.student_id}`, {
        method: 'PATCH',
        headers: h(currentUser),
        body: JSON.stringify({ bus_route: assignForm.bus_route, uses_transport: true })
      }).then(r => r.json());
      if (res.success) {
        setShowAssign(false);
        setAssignForm({ student_id: '', bus_route: '' });
        setAssignError('');
        load();
      } else {
        setAssignError(res.detail || 'Failed to assign student');
      }
    } catch (err) {
      setAssignError('Network error');
    }
  };

  const routeStudents = selectedRoute ? students.filter(s => s.bus_route === selectedRoute.id) : [];

  return (
    <ToolPage title="Transport Manager" subtitle="Routes, vehicles & student assignments" loading={loading}
      actions={viewMode === 'routes' && <ActionBtn label="Add Route" onClick={() => { setShowForm(true); setEditingId(null); setForm({ route_name: '', start_point: '', end_point: '', driver_name: '', driver_phone: '', vehicle_no: '', capacity: '', fare: '' }); }} icon={<Plus size={11} />} />}>

      <div style={{ display: 'flex', gap: 10, marginBottom: 14, borderBottom: '1px solid var(--c-border)', paddingBottom: 12 }}>
        <button onClick={() => { setViewMode('routes'); setSelectedRoute(null); }} style={{ padding: '6px 12px', borderRadius: 6, border: viewMode === 'routes' ? '1px solid #4f8ff7' : '1px solid var(--c-border)', background: viewMode === 'routes' ? 'rgba(59,130,246,0.1)' : 'var(--c-bg)', color: viewMode === 'routes' ? '#4f8ff7' : 'var(--c-muted)', fontSize: 12, cursor: 'pointer' }}>Routes</button>
        <button onClick={() => { setViewMode('assignments'); setSelectedRoute(null); }} style={{ padding: '6px 12px', borderRadius: 6, border: viewMode === 'assignments' ? '1px solid #34d399' : '1px solid var(--c-border)', background: viewMode === 'assignments' ? 'rgba(16,185,129,0.1)' : 'var(--c-bg)', color: viewMode === 'assignments' ? '#34d399' : 'var(--c-muted)', fontSize: 12, cursor: 'pointer' }}>Student Assignments</button>
      </div>

      {showForm && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>{editingId ? 'Edit Route' : 'Add New Route'}</h3>
          <form onSubmit={handleSave}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Route Name" value={form.route_name} onChange={f('route_name')} placeholder="e.g. Route 1 - City Center" required />
              <FormField label="Start Point" value={form.start_point} onChange={f('start_point')} placeholder="e.g. Main Gate" required />
              <FormField label="End Point" value={form.end_point} onChange={f('end_point')} placeholder="e.g. Market Area" required />
              <FormField label="Driver Name" value={form.driver_name} onChange={f('driver_name')} placeholder="Full name" />
              <FormField label="Driver Phone" value={form.driver_phone} onChange={f('driver_phone')} placeholder="10-digit mobile" />
              <FormField label="Vehicle No." value={form.vehicle_no} onChange={f('vehicle_no')} placeholder="e.g. UP32 AB 1234" />
              <FormField label="Capacity" type="number" value={form.capacity} onChange={f('capacity')} placeholder="No. of seats" />
              <FormField label="Fare (₹)" type="number" value={form.fare} onChange={f('fare')} placeholder="Monthly fare" />
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <ActionBtn label={editingId ? 'Update Route' : 'Add Route'} type="submit" />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => { setShowForm(false); setEditingId(null); }} />
            </div>
          </form>
        </div>
      )}

      {showAssign && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Assign Student to Route</h3>
          <form onSubmit={handleAssign}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Route" type="select" value={assignForm.bus_route} onChange={fa('bus_route')} options={routes.map(r => ({ value: r.id, label: r.route_name }))} required />
              <FormField label="Student" type="select" value={assignForm.student_id} onChange={fa('student_id')} options={students.map(s => ({ value: s.id, label: s.name }))} required />
            </div>
            {assignError && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 8 }}>{assignError}</div>}
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <ActionBtn label="Assign" type="submit" />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => { setShowAssign(false); setAssignError(''); }} />
            </div>
          </form>
        </div>
      )}

      {viewMode === 'routes' && (
        <>
          <DataTable headers={['Route Name', 'Start → End', 'Driver', 'Vehicle', 'Capacity', 'Fare', 'Status', 'Action']}
            rows={routes.map(r => [
              r.route_name,
              `${r.start_point || 'N/A'} → ${r.end_point || 'N/A'}`,
              r.driver_name || 'N/A',
              r.vehicle_no || 'N/A',
              r.capacity || 'N/A',
              r.fare ? `₹${r.fare}` : 'N/A',
              <Badge text={r.is_active ? 'Active' : 'Inactive'} color={r.is_active ? 'green' : 'gray'} />,
              <div style={{ display: 'flex', gap: 4 }}>
                <button onClick={() => handleEdit(r)} style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 5, padding: '3px 8px', color: '#4f8ff7', fontSize: 10, cursor: 'pointer' }}>Edit</button>
                <button onClick={() => handleDelete(r.id)} style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 5, padding: '3px 8px', color: '#f87171', fontSize: 10, cursor: 'pointer' }}>Delete</button>
              </div>
            ])}
            emptyMsg="No transport routes configured"
          />
          <div style={{ marginTop: 12 }}>
            <ActionBtn label="Assign Students to Routes" onClick={() => setShowAssign(true)} />
          </div>
        </>
      )}

      {viewMode === 'assignments' && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16 }}>
            <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 12 }}>
              <h4 style={{ color: 'var(--c-muted)', fontSize: 11, fontWeight: 600, marginBottom: 10, textTransform: 'uppercase' }}>Routes</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {routes.map(r => (
                  <button key={r.id} onClick={() => setSelectedRoute(r)} style={{ padding: '8px 10px', borderRadius: 6, border: selectedRoute?.id === r.id ? '1px solid #4f8ff7' : '1px solid var(--c-border)', background: selectedRoute?.id === r.id ? 'rgba(59,130,246,0.1)' : 'var(--c-app)', color: 'var(--c-text)', fontSize: 12, textAlign: 'left', cursor: 'pointer' }}>
                    {r.route_name} <span style={{ color: 'var(--c-faint)', fontSize: 10 }}>({students.filter(s => s.bus_route === r.id).length})</span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              {selectedRoute ? (
                <div>
                  <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 14, marginBottom: 12 }}>
                    <h4 style={{ color: 'var(--c-text)', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>{selectedRoute.route_name}</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 11 }}>
                      <div><span style={{ color: 'var(--c-muted)' }}>Route:</span> {selectedRoute.start_point} → {selectedRoute.end_point}</div>
                      <div><span style={{ color: 'var(--c-muted)' }}>Driver:</span> {selectedRoute.driver_name || 'N/A'}</div>
                      <div><span style={{ color: 'var(--c-muted)' }}>Vehicle:</span> {selectedRoute.vehicle_no || 'N/A'}</div>
                      <div><span style={{ color: 'var(--c-muted)' }}>Fare:</span> ₹{selectedRoute.fare || 'N/A'}</div>
                    </div>
                  </div>
                  <DataTable headers={['Student Name', 'Class', 'Status']}
                    rows={routeStudents.map(s => [s.name, s.class_info ? `${s.class_info.name}-${s.class_info.section}` : 'N/A', <Badge text="Enrolled" color="green" />])}
                    emptyMsg="No students assigned to this route"
                  />
                </div>
              ) : (
                <div style={{ color: 'var(--c-faint)', textAlign: 'center', padding: '40px 20px' }}>Select a route to view assigned students</div>
              )}
            </div>
          </div>
        </>
      )}
    </ToolPage>
  );
}
export function AutomatedReport() {
  const { currentUser } = useUser();
  const [schedules, setSchedules] = useState([{ name: 'Weekly Attendance Report', frequency: 'weekly', day: 'Monday', time: '08:00', active: true }, { name: 'Monthly Fee Summary', frequency: 'monthly', day: '1', time: '09:00', active: true }]);
  return (
    <ToolPage title="Automated Reports" subtitle="Schedule recurring reports">
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16, maxWidth: 600 }}>
        <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Scheduled Reports</h3>
        {schedules.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid #242424' }}>
            <div>
              <div style={{ fontSize: 13, color: 'var(--c-text)', fontWeight: 500 }}>{s.name}</div>
              <div style={{ fontSize: 11, color: 'var(--c-faint)' }}>{s.frequency} · {s.day} at {s.time}</div>
            </div>
            <Badge text={s.active ? 'Active' : 'Paused'} color={s.active ? 'green' : 'gray'} />
          </div>
        ))}
        <div style={{ marginTop: 14 }}>
          <p style={{ fontSize: 11, color: 'var(--c-faint)' }}>Full scheduling system with email delivery coming in Phase 3. Reports are available via Export section.</p>
        </div>
      </div>
    </ToolPage>
  );
}

export function CustomFormBuilder() {
  const { currentUser } = useUser();
  const [forms, setForms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedForm, setSelectedForm] = useState(null);
  const [viewMode, setViewMode] = useState('list');
  const [formName, setFormName] = useState('');
  const [audience, setAudience] = useState('all');
  const [fields, setFields] = useState([{ label: '', type: 'text', options: '' }]);
  const [responses, setResponses] = useState([]);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/settings/forms`, { headers: h(currentUser) }).then(r => r.json());
      if (r.success) setForms(r.data || []);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const addField = () => setFields(p => [...p, { label: '', type: 'text', options: '' }]);
  const updateField = (i, key, val) => setFields(p => p.map((f, idx) => idx === i ? { ...f, [key]: val } : f));
  const removeField = (i) => setFields(p => p.filter((_, idx) => idx !== i));

  const save = async () => {
    setError('');
    if (!formName.trim()) { setError('Form title is required'); return; }
    const validFields = fields.filter(f => f.label.trim());
    if (validFields.length === 0) { setError('Add at least one field'); return; }
    try {
      const payload = {
        title: formName,
        audience,
        fields: validFields.map(f => ({
          label: f.label.trim(),
          type: f.type,
          options: (f.type === 'select' || f.type === 'radio') && f.options ? f.options.split(',').map(o => o.trim()).filter(o => o) : []
        }))
      };
      const headers = h(currentUser);
      const fetchRes = await fetch(`${API}/settings/forms`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });
      const res = await fetchRes.json();
      if (res.success) {
        setShowCreate(false);
        setFormName('');
        setAudience('all');
        setFields([{ label: '', type: 'text', options: '' }]);
        load();
      } else {
        setError(res.detail || res.message || JSON.stringify(res));
      }
    } catch (err) {
      console.error('Form save error:', err);
      setError('Error: ' + err.message);
    }
  };

  const loadResponses = async (formId) => {
    try {
      const r = await fetch(`${API}/settings/forms/${formId}/responses`, { headers: h(currentUser) }).then(r => r.json());
      if (r.success) setResponses(r.data || []);
    } catch {}
  };

  const handleViewResponses = (form) => {
    setSelectedForm(form);
    setViewMode('responses');
    loadResponses(form.id);
  };

  const handleDelete = async (formId) => {
    if (!window.confirm('Delete this form and all responses?')) return;
    try {
      const res = await fetch(`${API}/settings/forms/${formId}`, { method: 'DELETE', headers: h(currentUser) }).then(r => r.json());
      if (res.success) load();
    } catch {}
  };

  return (
    <ToolPage title="Custom Form Builder" subtitle="Create & manage data collection forms" loading={loading}
      actions={viewMode === 'list' && <ActionBtn label="Create Form" onClick={() => setShowCreate(true)} icon={<Plus size={11} />} />}>

      {viewMode === 'list' && (
        <>
          {showCreate && (
            <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
              <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Create New Form</h3>
              <FormField label="Form Title" value={formName} onChange={setFormName} placeholder="e.g. Student Health Survey" required />
              <FormField label="Audience" type="select" value={audience} onChange={setAudience} options={[
                { value: 'all', label: 'Everyone' },
                { value: 'students', label: 'Students Only' },
                { value: 'teachers', label: 'Teachers Only' },
                { value: 'parents', label: 'Parents Only' }
              ]} />
              <div style={{ marginBottom: 10 }}>
                <label style={{ fontSize: 10, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>FORM FIELDS</label>
                {fields.map((field, i) => (
                  <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 8, alignItems: 'flex-end' }}>
                    <input value={field.label} onChange={e => updateField(i, 'label', e.target.value)} placeholder="Field label" style={{ flex: 2, background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '6px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }} />
                    <select value={field.type} onChange={e => updateField(i, 'type', e.target.value)} style={{ flex: 1, background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '6px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }}>
                      <option value="text">Text</option>
                      <option value="number">Number</option>
                      <option value="email">Email</option>
                      <option value="date">Date</option>
                      <option value="select">Select</option>
                      <option value="radio">Radio</option>
                      <option value="textarea">Long Text</option>
                    </select>
                    {(field.type === 'select' || field.type === 'radio') && (
                      <input value={field.options} onChange={e => updateField(i, 'options', e.target.value)} placeholder="Option 1, Option 2" style={{ flex: 1.5, background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '6px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }} />
                    )}
                    <button onClick={() => removeField(i)} style={{ padding: '6px 10px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 6, color: '#f87171', fontSize: 11, cursor: 'pointer' }}>Remove</button>
                  </div>
                ))}
              </div>
              {error && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 12 }}>{error}</div>}
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={addField} style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid var(--c-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>+ Add Field</button>
                <button onClick={save} style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid #4f8ff7', background: '#4f8ff7', color: '#fff', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>Create Form</button>
                <button onClick={() => { setShowCreate(false); setError(''); }} style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid var(--c-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>Cancel</button>
              </div>
            </div>
          )}
          <DataTable headers={['Form Title', 'Audience', 'Fields', 'Responses', 'Created', 'Actions']}
            rows={forms.map(f => [
              f.title,
              <span style={{ textTransform: 'capitalize', fontSize: 11 }}>{f.audience}</span>,
              f.fields?.length || 0,
              <button onClick={() => handleViewResponses(f)} style={{ color: '#4f8ff7', fontSize: 11, background: 'transparent', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>View</button>,
              f.created_at?.slice(0, 10),
              <div style={{ display: 'flex', gap: 4 }}>
                <button onClick={() => handleViewResponses(f)} style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 5, padding: '3px 8px', color: '#4f8ff7', fontSize: 10, cursor: 'pointer' }}>Responses</button>
                <button onClick={() => handleDelete(f.id)} style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 5, padding: '3px 8px', color: '#f87171', fontSize: 10, cursor: 'pointer' }}>Delete</button>
              </div>
            ])}
            emptyMsg="No forms created yet"
          />
        </>
      )}

      {viewMode === 'responses' && selectedForm && (
        <>
          <div style={{ marginBottom: 14 }}>
            <button onClick={() => { setViewMode('list'); setSelectedForm(null); setResponses([]); }} style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--c-border)', background: 'var(--c-bg)', color: 'var(--c-muted)', fontSize: 12, cursor: 'pointer' }}>← Back to Forms</button>
          </div>
          <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 14, marginBottom: 14 }}>
            <h4 style={{ color: 'var(--c-text)', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{selectedForm.title}</h4>
            <p style={{ color: 'var(--c-faint)', fontSize: 11 }}>Responses: {responses.length} | Audience: <span style={{ textTransform: 'capitalize' }}>{selectedForm.audience}</span></p>
          </div>
          {responses.length === 0 ? (
            <div style={{ textAlign: 'center', color: 'var(--c-faint)', padding: '40px 20px' }}>No responses yet</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--c-border)' }}>
                    <th style={{ padding: '8px', textAlign: 'left', color: 'var(--c-muted)', fontWeight: 600 }}>Submitted By</th>
                    <th style={{ padding: '8px', textAlign: 'left', color: 'var(--c-muted)', fontWeight: 600 }}>Role</th>
                    {selectedForm.fields?.slice(0, 3).map(f => (
                      <th key={f.label} style={{ padding: '8px', textAlign: 'left', color: 'var(--c-muted)', fontWeight: 600 }}>{f.label}</th>
                    ))}
                    <th style={{ padding: '8px', textAlign: 'left', color: 'var(--c-muted)', fontWeight: 600 }}>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {responses.map(resp => (
                    <tr key={resp.id} style={{ borderBottom: '1px solid var(--c-border)' }}>
                      <td style={{ padding: '8px', color: 'var(--c-text)' }}>{resp.submitted_by_name}</td>
                      <td style={{ padding: '8px', color: 'var(--c-text)', textTransform: 'capitalize' }}>{resp.submitted_by_role}</td>
                      {selectedForm.fields?.slice(0, 3).map(f => (
                        <td key={f.label} style={{ padding: '8px', color: '#d4d4d4', fontSize: 11 }}>{String(resp.answers?.[f.label] || 'N/A').slice(0, 30)}</td>
                      ))}
                      <td style={{ padding: '8px', color: 'var(--c-faint)', fontSize: 10 }}>{resp.submitted_at?.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </ToolPage>
  );
}

// 20. Report Card Builder (Admin/Owner only)
export function ReportCardBuilder() {
  const { currentUser } = useUser();
  const [exams, setExams] = useState([]);
  const [selectedExam, setSelectedExam] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetch(`${API}/academics/exams`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setExams(r.data || []); }).finally(() => setLoading(false)); }, []);
  useEffect(() => { if (selectedExam) fetch(`${API}/academics/results?exam_id=${selectedExam}`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setResults(r.data || []); }); }, [selectedExam]);

  return (
    <ToolPage title="Report Card Builder" subtitle="Enter marks & generate report cards" loading={loading}>
      <div style={{ marginBottom: 14 }}>
        <select value={selectedExam} onChange={e => setSelectedExam(e.target.value)} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }}>
          <option value="">Select exam...</option>
          {exams.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </div>
      <DataTable headers={['Student', 'Subject', 'Marks', 'Max', 'Grade']}
        rows={results.map(r => [r.student_name, r.subject_name, r.marks_obtained, r.max_marks, <Badge text={r.grade || 'N/A'} color={r.grade?.startsWith('A') ? 'green' : r.grade?.startsWith('B') ? 'blue' : 'yellow'} />])}
        emptyMsg={selectedExam ? 'No results entered yet' : 'Select an exam to view results'}
      />
    </ToolPage>
  );
}

// 21. Student Performance Viewer (Admin/Owner only)
export function StudentPerformanceViewer() {
  const { currentUser } = useUser();
  const [students, setStudents] = useState([]);
  const [results, setResults] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [studentResults, setStudentResults] = useState([]);
  const [studentAtt, setStudentAtt] = useState(null);

  useEffect(() => {
    Promise.all([
      getStudents(currentUser).then(r => { if (r.success) setStudents(r.data || []); }),
      fetch(`${API}/academics/results`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setResults(r.data || []); }),
    ]).finally(() => setLoading(false));
  }, []);

  const viewStudent = async (student) => {
    setSelectedStudent(student);
    // Get results
    const r1 = await fetch(`${API}/academics/results?student_id=${student.id}`, { headers: h(currentUser) }).then(r => r.json());
    if (r1.success) setStudentResults(r1.data || []);
    // Get attendance summary
    const r2 = await fetch(`${API}/attendance/student?student_id=${student.id}`, { headers: h(currentUser) }).then(r => r.json());
    if (r2.success) {
      const records = r2.data || [];
      const present = records.filter(r => r.status === 'present').length;
      const total = records.length;
      setStudentAtt({ present, absent: total - present, total, rate: total > 0 ? Math.round(present / total * 100) + '%' : 'N/A' });
    }
  };

  // Aggregate: avg marks per student
  const studentStats = students.slice(0, 20).map(s => {
    const sResults = results.filter(r => r.student_id === s.id);
    const avg = sResults.length > 0 ? Math.round(sResults.reduce((sum, r) => sum + (r.marks_obtained || 0), 0) / sResults.length) : null;
    const grade = avg === null ? 'N/A' : avg >= 90 ? 'A1' : avg >= 80 ? 'A2' : avg >= 70 ? 'B1' : avg >= 60 ? 'B2' : 'C';
    return { ...s, avg, grade, exams: sResults.length };
  });

  const gradeColor = { A1: 'green', A2: 'green', B1: 'blue', B2: 'blue', C: 'yellow', D: 'red', N: 'gray' };

  return (
    <ToolPage title="Student Performance" subtitle="Marks, grades & attendance analytics" loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 18, maxWidth: 700 }}>
        <StatCard value={students.length} label="STUDENTS" color="#4f8ff7" />
        <StatCard value={results.length} label="EXAM ENTRIES" color="#a78bfa" />
        <StatCard value={studentStats.filter(s => s.avg && s.avg >= 80).length} label="ABOVE 80%" color="#34d399" />
        <StatCard value={studentStats.filter(s => s.avg && s.avg < 60).length} label="BELOW 60%" color="#f87171" />
      </div>

      {selectedStudent ? (
        <div>
          <div style={{ display: 'flex', gap: 10, marginBottom: 14, alignItems: 'center' }}>
            <ActionBtn label="← Back to All" variant="secondary" onClick={() => setSelectedStudent(null)} />
            <span style={{ fontFamily: 'Inter, sans-serif', fontSize: 15, fontWeight: 600, color: 'var(--c-text)' }}>{selectedStudent.name}</span>
          </div>
          {studentAtt && (
            <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
              {[['Attendance', studentAtt.rate, '#34d399'], ['Present', studentAtt.present, '#34d399'], ['Absent', studentAtt.absent, '#f87171'], ['Total Days', studentAtt.total, 'var(--c-text)']].map(([l, v, c]) => (
                <StatCard key={l} value={v} label={l} color={c} small />
              ))}
            </div>
          )}
          <DataTable title={`Exam Results for ${selectedStudent.name}`} headers={['Subject', 'Marks', 'Max', 'Grade']}
            rows={studentResults.map(r => [r.subject_name, r.marks_obtained, r.max_marks, <Badge text={r.grade || 'N/A'} color={gradeColor[r.grade?.[0]] || 'gray'} />])}
            emptyMsg="No exam results entered yet"
          />
        </div>
      ) : (
        <DataTable title="Student Performance Overview" headers={['Name', 'Class', 'Exams', 'Avg Marks', 'Grade', 'Action']}
          rows={studentStats.map(s => [
            s.name,
            s.class_info ? `${s.class_info.name}-${s.class_info.section}` : 'N/A',
            s.exams,
            s.avg !== null ? <span style={{ color: s.avg >= 80 ? '#34d399' : s.avg >= 60 ? '#fbbf24' : '#f87171', fontWeight: 600 }}>{s.avg}%</span> : 'No data',
            s.grade !== 'N/A' ? <Badge text={s.grade} color={gradeColor[s.grade[0]] || 'gray'} /> : <span style={{ color: 'var(--c-faint)' }}>N/A</span>,
            <button onClick={() => viewStudent(s)} style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 5, padding: '3px 8px', color: '#93c5fd', fontSize: 10, cursor: 'pointer' }}>View</button>
          ])}
          emptyMsg="No students found"
        />
      )}
    </ToolPage>
  );
}

// Re-export AttendanceAlerts from OwnerTools so admin can use it
export { AttendanceAlerts } from './OwnerTools';
