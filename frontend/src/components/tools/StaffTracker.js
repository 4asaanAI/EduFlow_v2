import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createStaff, deactivateStaff, getPendingLeaves, getStaff, subscribeSSE, updateLeave, updateStaff } from '../../lib/api';
import { CheckCircle, Edit3, Plus, RefreshCw, X, XCircle } from 'lucide-react';
import { useUser } from '../../contexts/UserContext';

const blankForm = {
  name: '',
  staff_type: 'teacher',
  employee_id: '',
  phone: '',
  email: '',
  department: '',
  qualification: '',
  specialization: '',
  role: 'teacher',
  sub_category: '',
  casual_leave_balance: 12,
  medical_leave_balance: 10,
  earned_leave_balance: 15,
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

function lastUpdatedLabel(value) {
  if (!value) return 'Waiting for attendance stream';
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 5) return 'Attendance updated just now';
  if (seconds < 60) return `Attendance updated ${seconds}s ago`;
  return `Attendance updated ${Math.floor(seconds / 60)}m ago`;
}

function ActionButton({ children, onClick, disabled, variant = 'primary', type = 'button' }) {
  const secondary = variant === 'secondary';
  const danger = variant === 'danger';
  return (
    <button
      type={type}
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
        fontWeight: 650,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.65 : 1,
      }}
    >
      {children}
    </button>
  );
}

function StaffModal({ initialStaff, canEditLeaveBalances, onClose, onSaved }) {
  const editing = Boolean(initialStaff);
  const [form, setForm] = useState(() => initialStaff ? { ...blankForm, ...initialStaff } : blankForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const setField = (key) => (event) => {
    setForm((current) => ({ ...current, [key]: event.target.value }));
    setError('');
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.name || !form.staff_type) {
      setError('Name and staff type are required');
      return;
    }
    setSaving(true);
    const payload = {
      ...form,
      casual_leave_balance: Number(form.casual_leave_balance || 0),
      medical_leave_balance: Number(form.medical_leave_balance || 0),
      earned_leave_balance: Number(form.earned_leave_balance || 0),
    };
    try {
      const res = editing ? await updateStaff(initialStaff.id, payload) : await createStaff(payload);
      if (res.success) {
        onSaved(res.data);
        onClose();
      } else {
        setError(res.detail || 'Unable to save staff profile');
      }
    } catch (err) {
      setError(err.message || 'Network error');
    }
    setSaving(false);
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 220, padding: 16 }}>
      <div style={{ background: 'var(--c-input)', border: '1px solid var(--c-border)', borderRadius: 8, padding: 24, width: 620, maxWidth: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <h3 style={{ margin: 0, color: 'var(--c-text)', fontSize: 16 }}>{editing ? 'Edit Staff Profile' : 'Add Staff Profile'}</h3>
          <button aria-label="Close" onClick={onClose} style={{ width: 36, height: 36, border: 0, background: 'transparent', color: 'var(--c-faint)', cursor: 'pointer' }}><X size={18} /></button>
        </div>
        <form onSubmit={submit}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Name
              <input value={form.name} onChange={setField('name')} style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Staff Type
              <select value={form.staff_type} onChange={setField('staff_type')} style={{ ...inputStyle, marginTop: 5 }}>
                <option value="teacher">Teacher</option>
                <option value="admin">Admin</option>
                <option value="support">Support</option>
                <option value="transport">Transport</option>
              </select>
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Role
              <select value={form.role} onChange={setField('role')} style={{ ...inputStyle, marginTop: 5 }}>
                <option value="teacher">Teacher</option>
                <option value="admin">Admin</option>
                <option value="owner">Owner</option>
              </select>
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Sub Category
              <input value={form.sub_category || ''} onChange={setField('sub_category')} placeholder="principal, accountant, class_teacher" style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Employee ID
              <input value={form.employee_id || ''} onChange={setField('employee_id')} style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Department
              <input value={form.department || ''} onChange={setField('department')} style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Phone
              <input value={form.phone || ''} onChange={setField('phone')} style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Email
              <input value={form.email || ''} onChange={setField('email')} style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Qualification
              <input value={form.qualification || ''} onChange={setField('qualification')} style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Specialization
              <input value={form.specialization || ''} onChange={setField('specialization')} style={{ ...inputStyle, marginTop: 5 }} />
            </label>
            {canEditLeaveBalances && ['casual_leave_balance', 'medical_leave_balance', 'earned_leave_balance'].map((field) => (
              <label key={field} style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>{field.replaceAll('_', ' ')}
                <input type="number" min="0" value={form[field]} onChange={setField(field)} style={{ ...inputStyle, marginTop: 5 }} />
              </label>
            ))}
          </div>
          {error && <div style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginTop: 12 }}>{error}</div>}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
            <ActionButton variant="secondary" onClick={onClose}>Cancel</ActionButton>
            <ActionButton type="submit" disabled={saving}>{saving ? 'Saving...' : 'Save Staff'}</ActionButton>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function StaffTracker() {
  const { currentUser } = useUser();
  const [staff, setStaff] = useState([]);
  const [pendingLeaves, setPendingLeaves] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('profiles');
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [editing, setEditing] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [attendanceStreamUpdatedAt, setAttendanceStreamUpdatedAt] = useState(null);
  const [, setClockTick] = useState(0);
  const canEditLeaveBalances = currentUser.role === 'owner' || currentUser.sub_category === 'principal';
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / 20)), [total]);
  const attendanceLiveLabel = lastUpdatedLabel(attendanceStreamUpdatedAt);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [staffRes, leavesRes] = await Promise.all([
        getStaff({ page, sort }),
        getPendingLeaves().catch(() => ({ data: [] })),
      ]);
      if (staffRes.success) {
        setStaff(staffRes.data || []);
        setTotal(staffRes.meta?.total || 0);
      } else {
        setError(staffRes.detail || 'Unable to load staff profiles');
      }
      if (leavesRes.success) setPendingLeaves(leavesRes.data || []);
    } catch (err) {
      setError(err.message || 'Unable to load staff profiles');
    }
    setLoading(false);
  }, [page, sort]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    const interval = setInterval(() => setClockTick(t => t + 1), 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => subscribeSSE('/attendance/stream', (event) => {
    if (event.type === 'snapshot' || event.type === 'staff_attendance_updated') {
      setAttendanceStreamUpdatedAt(event.last_updated || event.updated_at || new Date().toISOString());
      if (event.type !== 'snapshot') loadData();
    }
  }, { onReconnect: loadData }), [loadData]);

  const handleLeave = async (leaveId, status) => {
    const reason = window.prompt(`Reason for ${status} decision`);
    if (!reason || !reason.trim()) {
      setError('Leave decision reason is required');
      return;
    }
    const res = await updateLeave(leaveId, status, reason.trim());
    if (!res.success) setError(res.detail || 'Unable to update leave request');
    loadData();
  };

  const deactivate = async (profile) => {
    if (!window.confirm(`Deactivate ${profile.name}? Their login sessions will be revoked.`)) return;
    const res = await deactivateStaff(profile.id);
    if (res.success) loadData();
    else setError(res.detail || 'Unable to deactivate staff profile');
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--c-faint)' }}>
        <RefreshCw size={20} style={{ animation: 'spin 0.8s linear infinite' }} />
        <span style={{ marginLeft: 10 }}>Loading staff records...</span>
      </div>
    );
  }

  return (
    <div data-testid="staff-tracker-tool" style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 650, color: 'var(--c-text)', margin: 0 }}>Staff Tracker</h1>
          <div style={{ color: 'var(--c-faint)', fontSize: 12, marginTop: 3 }}>{total} staff profiles</div>
          <div style={{ color: 'var(--c-muted)', fontSize: 11, marginTop: 3 }}>{attendanceLiveLabel}</div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <ActionButton variant="secondary" onClick={loadData}><RefreshCw size={13} />Refresh</ActionButton>
          <ActionButton onClick={() => setShowAdd(true)}><Plus size={13} />Add Staff</ActionButton>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid var(--c-border)' }}>
        {[
          ['profiles', 'Profiles'],
          ['leaves', `Pending Leaves (${pendingLeaves.length})`],
        ].map(([id, label]) => (
          <button key={id} onClick={() => setActiveTab(id)} style={{ background: 'none', border: 'none', borderBottom: activeTab === id ? '2px solid var(--tool-hex-4f8ff7)' : '2px solid transparent', color: activeTab === id ? 'var(--c-text)' : 'var(--c-faint)', padding: '9px 16px', fontSize: 13, cursor: 'pointer' }}>{label}</button>
        ))}
      </div>

      {error && <div style={{ color: 'var(--tool-hex-f87171)', background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.18)', borderRadius: 8, padding: 10, marginBottom: 12, fontSize: 12 }}>{error}</div>}

      {activeTab === 'profiles' && (
        <>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
            <select value={sort} onChange={(event) => { setSort(event.target.value); setPage(1); }} style={{ ...inputStyle, width: 180 }}>
              <option value="name">Sort by name</option>
              <option value="staff_type">Sort by type</option>
              <option value="department">Sort by department</option>
              <option value="created_at">Newest first</option>
            </select>
          </div>
          <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, overflowX: 'auto' }}>
            {staff.length === 0 ? (
              <div style={{ padding: 30, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>No staff records found</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 820 }}>
                <thead>
                  <tr>
                    {['Name', 'Type', 'Role', 'Department', 'Leave Balance', 'Actions'].map((header) => (
                      <th key={header} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 750, color: 'var(--c-faint)', textTransform: 'uppercase', background: 'var(--c-deep)', borderBottom: '1px solid var(--c-border)' }}>{header}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {staff.map((profile, index) => (
                    <tr key={profile.id} style={{ borderBottom: index < staff.length - 1 ? '1px solid var(--c-border)' : 'none' }}>
                      <td style={{ padding: '10px 14px', color: 'var(--c-text)', fontSize: 13, fontWeight: 650 }}>{profile.name}<div style={{ color: 'var(--c-faint)', fontSize: 11 }}>{profile.employee_id || 'No employee ID'}</div></td>
                      <td style={{ padding: '10px 14px', color: 'var(--c-muted)', fontSize: 12 }}>{profile.staff_type}</td>
                      <td style={{ padding: '10px 14px', color: 'var(--c-muted)', fontSize: 12 }}>{profile.role || 'teacher'}{profile.sub_category ? ` / ${profile.sub_category}` : ''}</td>
                      <td style={{ padding: '10px 14px', color: 'var(--c-muted)', fontSize: 12 }}>{profile.department || 'N/A'}</td>
                      <td style={{ padding: '10px 14px', color: 'var(--c-muted)', fontSize: 12 }}>CL {profile.casual_leave_balance ?? 0} · ML {profile.medical_leave_balance ?? 0} · EL {profile.earned_leave_balance ?? 0}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          <ActionButton variant="secondary" onClick={() => setEditing(profile)}><Edit3 size={13} /></ActionButton>
                          {profile.is_active !== false && <ActionButton variant="danger" onClick={() => deactivate(profile)}>Deactivate</ActionButton>}
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
        </>
      )}

      {activeTab === 'leaves' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 840 }}>
          {pendingLeaves.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13, background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8 }}>No pending leave requests</div>
          ) : pendingLeaves.map((leave) => (
            <div key={leave.id} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <div>
                  <div style={{ fontWeight: 650, color: 'var(--c-text)', fontSize: 14 }}>{leave.staff?.name || leave.staff_name || 'Staff member'}</div>
                  <div style={{ color: 'var(--c-faint)', fontSize: 12, marginTop: 2 }}>{leave.leave_type} - {leave.start_date || leave.date_range?.start} to {leave.end_date || leave.date_range?.end}</div>
                  <div style={{ color: 'var(--c-muted)', fontSize: 12, marginTop: 4 }}>{leave.reason}</div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <ActionButton variant="secondary" onClick={() => handleLeave(leave.id, 'approved')}><CheckCircle size={13} />Approve</ActionButton>
                  <ActionButton variant="danger" onClick={() => handleLeave(leave.id, 'rejected')}><XCircle size={13} />Reject</ActionButton>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showAdd && <StaffModal canEditLeaveBalances={canEditLeaveBalances} onClose={() => setShowAdd(false)} onSaved={loadData} />}
      {editing && <StaffModal initialStaff={editing} canEditLeaveBalances={canEditLeaveBalances} onClose={() => setEditing(null)} onSaved={loadData} />}
    </div>
  );
}
