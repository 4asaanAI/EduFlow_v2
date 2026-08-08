import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { adminResetPassword, createStaff, deactivateStaff, decideProfileChangeRequest, eraseStaff, getPendingLeaves, getProfileChangeRequests, getStaff, getStaffEnrolmentSummary, getStaffMember, setStaffEnrolment, subscribeSSE, updateLeave, updateStaff } from '../../lib/api';
import {
  EnrolmentBadge,
  EnrolmentStateModal,
  EraseConfirmModal,
  ViewPicker,
} from '../ui/EnrolmentControls';
import { ON_ROLL_VIEW, OFF_ROLL_VIEW, readState } from '../../lib/enrolmentStates';
import ProfileNotes from '../ui/ProfileNotes';
import ProfileDocuments from '../ui/ProfileDocuments';
import { ArrowRight, CheckCircle, Edit3, KeyRound, Plus, RefreshCw, RotateCcw, Search, Trash2, X, XCircle } from 'lucide-react';
import { Pill } from '../ui/primitives';
import { useUser } from '../../contexts/UserContext';
import { useTheme } from '../../contexts/ThemeContext';
import DataTable, { cellValue } from '../ui/DataTable';
import { useTablePageSize } from '../../hooks/useTablePrefs';

const blankForm = {
  name: '',
  staff_type: 'teacher',
  employee_id: '',
  phone: '',
  email: '',
  department: '',
  // Owner request 11 (2026-08-06) - where this person lives.
  address: '',
  qualification: '',
  specialization: '',
  role: 'teacher',
  sub_category: '',
  casual_leave_balance: 12,
  medical_leave_balance: 10,
  earned_leave_balance: 15,
};

// The canonical sub_category list, mirroring backend middleware/auth.py
// VALID_SUB_CATEGORIES. The backend GATES ACCESS on these exact strings —
// require_access(..., sub_category="accountant") and the AI tool registry both
// match them literally. A typo here silently grants nothing, which is why this
// is a fixed list and not the free-text box it used to be.
// "owner" and "student" are intentionally absent: neither is assignable from
// the staff screen.
const SUB_CATEGORIES = {
  admin: [
    { value: 'principal', label: 'Principal' },
    { value: 'management', label: 'Management' },
    { value: 'accountant', label: 'Accountant' },
    { value: 'receptionist', label: 'Receptionist' },
    { value: 'transport_head', label: 'Transport Head' },
    { value: 'it_tech', label: 'IT / Tech' },
    { value: 'maintenance', label: 'Maintenance' },
    { value: 'support_staff', label: 'Support Staff' },
  ],
  teacher: [
    { value: 'class_teacher', label: 'Class Teacher' },
    { value: 'subject_teacher', label: 'Subject Teacher' },
    { value: 'hod', label: 'Head of Department' },
    { value: 'coordinator', label: 'Coordinator' },
    { value: 'kg_incharge', label: 'KG In-charge' },
  ],
};

const sectionLabelStyle = {
  fontSize: 10, fontWeight: 800, color: 'var(--c-faint)',
  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8,
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

// A person's job title as a human would say it.
//
// Every staff record already carries a readable `designation` — "Class Teacher",
// "Teacher", "Principal" — populated for all 89 records. The table used to print
// `role / sub_category` instead ("teacher / subject_teacher"), which reads as
// machine output and duplicates the Type column beside it. Prefer the real
// designation; fall back to a tidied sub_category, then role.
function designationOf(profile) {
  if (profile.designation) return profile.designation;
  const raw = profile.sub_category || profile.role || profile.staff_type;
  if (!raw) return '—';
  return String(raw).split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

function lastUpdatedLabel(value) {
  if (!value) return 'Waiting for attendance stream';
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 5) return 'Attendance updated just now';
  if (seconds < 60) return `Attendance updated ${seconds}s ago`;
  return `Attendance updated ${Math.floor(seconds / 60)}m ago`;
}

function ActionButton({ children, onClick, disabled, variant = 'primary', type = 'button' }) {
  const { isDark } = useTheme();
  const secondary = variant === 'secondary';
  const danger = variant === 'danger';
  // Use a bright accessible red in light mode; deep red in dark mode
  const dangerBg = isDark ? '#991b1b' : '#dc2626';
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
        background: danger ? dangerBg : secondary ? 'var(--c-bg)' : 'var(--tool-hex-4f8ff7)',
        border: secondary ? '1px solid var(--c-border)' : danger ? `1px solid ${isDark ? '#7f1d1d' : '#b91c1c'}` : 'none',
        borderRadius: 8,
        padding: '8px 13px',
        color: danger || !secondary ? '#fff' : 'var(--c-muted)',
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
    const value = event.target.value;
    setForm((current) => {
      const next = { ...current, [key]: value };
      // Sub-categories are role-specific. Switching role must clear a now-invalid
      // one, otherwise an admin could be saved carrying "class_teacher" — which
      // matches no permission rule and silently grants nothing.
      if (key === 'role') {
        const allowed = (SUB_CATEGORIES[value] || []).map((s) => s.value);
        if (!allowed.includes(next.sub_category)) next.sub_category = '';
      }
      return next;
    });
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
            {/* Owner is deliberately NOT offered. It is the highest privilege in
                the platform and must never be grantable from the staff screen —
                anyone who can add a staff member could otherwise mint a full
                owner account. Owner is assigned out of band. */}
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Role
              <select value={form.role} onChange={setField('role')} style={{ ...inputStyle, marginTop: 5 }}>
                <option value="teacher">Teacher</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Sub Category
              <select value={form.sub_category || ''} onChange={setField('sub_category')} style={{ ...inputStyle, marginTop: 5 }}>
                <option value="">Select…</option>
                {(SUB_CATEGORIES[form.role] || []).map(s => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
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
            <label style={{ gridColumn: '1 / -1', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Address
              <textarea
                value={form.address || ''}
                onChange={setField('address')}
                rows={2}
                data-testid="staff-address"
                placeholder="House, street, locality, town and district"
                style={{ ...inputStyle, marginTop: 5, resize: 'vertical' }}
              />
            </label>
          </div>

          {/* Only on a record that already exists - a note or a document has to hang
              off something, and there is no id until the record is saved. */}
          {initialStaff?.id && (
            <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 18 }}>
              <div>
                <div style={sectionLabelStyle}>Documents</div>
                <ProfileDocuments subjectId={initialStaff.id} />
              </div>
              <div>
                <div style={sectionLabelStyle}>My notes</div>
                <ProfileNotes subjectType="staff" subjectId={initialStaff.id} subjectName={initialStaff.name} />
              </div>
            </div>
          )}
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

function ResetPasswordModal({ profile, onClose }) {
  const [newPassword, setNewPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    if (newPassword.length < 8) { setError('Password must be at least 8 characters'); return; }
    setSaving(true);
    setError('');
    const res = await adminResetPassword(profile.user_id || profile.id, newPassword);
    setSaving(false);
    if (res.success) {
      setSuccess('Password changed. Existing sessions have been signed out.');
    } else {
      setError(res.detail || 'Failed to reset password');
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 220, padding: 16 }}>
      <div style={{ background: 'var(--c-input)', border: '1px solid var(--c-border)', borderRadius: 8, padding: 24, width: 420, maxWidth: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <h3 style={{ margin: 0, color: 'var(--c-text)', fontSize: 16 }}>Reset Password — {profile.name}</h3>
          <button aria-label="Close" onClick={onClose} style={{ width: 36, height: 36, border: 0, background: 'transparent', color: 'var(--c-faint)', cursor: 'pointer' }}><X size={18} /></button>
        </div>
        {success ? (
          <div style={{ color: 'var(--tool-hex-34d399)', fontSize: 13, marginBottom: 16 }}>{success}</div>
        ) : (
          <form onSubmit={submit}>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, display: 'block', marginBottom: 5 }}>New Password
              <input
                type="text"
                value={newPassword}
                onChange={e => { setNewPassword(e.target.value); setError(''); }}
                placeholder="Enter new password..."
                style={{ ...inputStyle, marginTop: 5 }}
                autoFocus
              />
            </label>
            {error && <div style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginTop: 8 }}>{error}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
              <ActionButton variant="secondary" onClick={onClose}>Cancel</ActionButton>
              <ActionButton type="submit" disabled={saving}>{saving ? 'Resetting...' : 'Reset Password'}</ActionButton>
            </div>
          </form>
        )}
        {success && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
            <ActionButton onClick={onClose}>Close</ActionButton>
          </div>
        )}
      </div>
    </div>
  );
}

export default function StaffTracker() {
  const { currentUser } = useUser();
  const [staff, setStaff] = useState([]);
  const [pendingLeaves, setPendingLeaves] = useState([]);
  // Epic 8 — corrections people have asked for. Only the Owner and the
  // Principal may see or decide these, so nobody else even fetches them.
  const [changeRequests, setChangeRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [leavesLoading, setLeavesLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('profiles');
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [editing, setEditing] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [resetTarget, setResetTarget] = useState(null);
  // Owner request 10 decision 2 (2026-08-06): staff and teachers get the same three
  // states as students, the same recycle bin, and the same compulsory reason before
  // anything is destroyed. The controls are shared with the student screen for that
  // reason — two copies of these words is how the two would drift apart.
  const [enrolmentView, setEnrolmentView] = useState(ON_ROLL_VIEW);
  const [enrolmentCounts, setEnrolmentCounts] = useState(null);
  const [stateTarget, setStateTarget] = useState(null);
  const [eraseTarget, setEraseTarget] = useState(null);
  const [savingState, setSavingState] = useState(false);
  // Owner note, 2026-08-07: several lists had no way to search at all, so finding one
  // person among 89 meant paging through them.
  const [search, setSearch] = useState('');
  const canResetPassword = currentUser.role === 'owner' || (currentUser.role === 'admin' && currentUser.sub_category === 'principal');
  const [attendanceStreamUpdatedAt, setAttendanceStreamUpdatedAt] = useState(null);
  const [, setClockTick] = useState(0);
  const canEditLeaveBalances = currentUser.role === 'owner' || currentUser.sub_category === 'principal';
  // Mirrors the server's require_owner_or_principal gate. A convenience only —
  // the server refuses regardless of what this says.
  const canReviewChanges = currentUser.role === 'owner'
    || (currentUser.role === 'admin' && currentUser.sub_category === 'principal');
  // Mirrors require_owner_or_principal on POST /api/staff/{id}/enrolment, and
  // require_owner on the erase route. Offering either to anyone else would only
  // produce a refusal when they pressed it, which is the D-49 mistake.
  const canChangeEnrolment = canReviewChanges;
  const canErase = currentUser.role === 'owner';
  const attendanceLiveLabel = lastUpdatedLabel(attendanceStreamUpdatedAt);

  // D-44 — deep link from the School Directory. A staff row there opens
  // `?tool=staff-tracker&focus=<id>`. This opens the SAME editor the row's own Edit
  // button opens; it is not a second way to edit a profile, which is the fork D-44
  // was written to avoid. The record is fetched by id because this list is paginated
  // on the server, so the person may not be on the page that happens to be loaded.
  // Applied once via the ref, then the parameter is stripped so closing the editor
  // (or reloading) does not reopen it.
  const [searchParams, setSearchParams] = useSearchParams();
  const appliedFocusRef = useRef(false);
  const [focusError, setFocusError] = useState('');
  useEffect(() => {
    if (appliedFocusRef.current) return;
    const focus = searchParams.get('focus');
    if (!focus) return;
    appliedFocusRef.current = true;

    // The parameter is stripped AFTER the record is fetched, not before. Stripping
    // first re-runs this effect, and a cleanup that cancelled the in-flight request
    // would throw away the answer it was waiting for — the deep link then silently
    // did nothing, which is exactly the failure mode D-63 was about.
    (async () => {
      try {
        const res = await getStaffMember(focus);
        if (res && res.success && res.data) setEditing(res.data);
        // The server refuses this for anyone who may not manage staff. Say so
        // plainly and leave the list usable rather than failing silently.
        else setFocusError('That staff member could not be opened. They may have been removed, or you may not have permission to view the record.');
      } catch {
        setFocusError('That staff member could not be opened just now.');
      } finally {
        setSearchParams((prev) => {
          const next = new URLSearchParams(prev);
          next.delete('focus');
          return next;
        }, { replace: true });
      }
    })();
  }, [searchParams, setSearchParams]);

  // UX-DR10: page size, remembered per table. Keyed 'staff', so sizing this
  // list does not resize the student list.
  const [pageSize, setPageSize] = useTablePageSize('staff');
  // Both reset to page 1 — changing either can shrink the number of pages, and
  // being left on a page that no longer exists shows an empty list.
  const changePageSize = useCallback((n) => { setPageSize(n); setPage(1); }, [setPageSize]);
  const changeSort = useCallback((next) => { setSort(next); setPage(1); }, []);

  const staffColumns = useMemo(() => [
    {
      key: 'name', label: 'Name', sortKey: 'name',
      render: (profile) => (
        <div>
          <div style={{ color: 'var(--c-text)', fontFamily: 'var(--font-display)', fontWeight: 700 }}>{profile.name}</div>
          <div style={{ color: 'var(--c-faint)', fontSize: 'var(--text-xs)' }}>{profile.employee_id || 'No employee ID'}</div>
        </div>
      ),
    },
    // `designation` is the readable label the school actually uses and is
    // populated for all 89 records. The old column showed `role /
    // sub_category` ("teacher / subject_teacher"), which is the one the owner
    // objected to on 2026-07-22.
    { key: 'designation', label: 'Designation', sortKey: 'designation', render: (p) => designationOf(p) },
    { key: 'department', label: 'Department', sortKey: 'department', render: (p) => cellValue(p.department) },
    {
      key: 'leave', label: 'Leave Balance',
      render: (p) => `CL ${p.casual_leave_balance ?? 0} · ML ${p.medical_leave_balance ?? 0} · EL ${p.earned_leave_balance ?? 0}`,
    },
    {
      key: 'status', label: 'Status',
      render: (profile) => <EnrolmentBadge state={readState(profile)} data-testid={`staff-state-${profile.id}`} />,
    },
    {
      key: 'actions', label: 'Actions',
      render: (profile) => (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <ActionButton variant="secondary" onClick={() => setEditing(profile)} aria-label={`Edit ${profile.name}`}><Edit3 size={13} />Edit</ActionButton>
          {canResetPassword && <ActionButton variant="secondary" onClick={() => setResetTarget(profile)} aria-label={`Reset password for ${profile.name}`}><KeyRound size={13} />Password</ActionButton>}
          {/* Owner or principal: one button for all three states, in either
              direction. This is also the only way back — before it, deactivating a
              colleague was a one-way door. */}
          {canChangeEnrolment && (
            <ActionButton variant="secondary" onClick={() => setStateTarget(profile)} aria-label={`Change status for ${profile.name}`}>
              <RefreshCw size={13} />Status
            </ActionButton>
          )}
          {canChangeEnrolment && readState(profile) !== 'active' && (
            <ActionButton variant="secondary" onClick={() => restore(profile)} aria-label={`Restore ${profile.name} to the roll`}>
              <RotateCcw size={13} />Restore
            </ActionButton>
          )}
          {/* The wider admin set keeps the plain deactivate it always had. */}
          {!canChangeEnrolment && profile.is_active !== false && (
            <ActionButton variant="danger" onClick={() => deactivate(profile)}>Deactivate</ActionButton>
          )}
          {canErase && (
            <ActionButton variant="danger" onClick={() => setEraseTarget(profile)} aria-label={`Erase ${profile.name} permanently`}>
              <Trash2 size={13} />Erase
            </ActionButton>
          )}
        </div>
      ),
    },
  ], [canResetPassword, canChangeEnrolment, canErase]);  // eslint-disable-line react-hooks/exhaustive-deps

  const loadData = useCallback(async () => {
    setLoading(true);
    setLeavesLoading(true);
    setError('');
    try {
      const [staffRes, leavesRes, requestsRes] = await Promise.all([
        // The page size goes to the API so the SERVER paginates (UX-DR10). The view
        // and the search term go the same way, so the answer is the whole school's
        // worth of matches rather than whatever happened to be on this page.
        getStaff({
          page,
          sort,
          limit: pageSize,
          enrolment_state: enrolmentView,
          ...(search ? { search } : {}),
        }),
        getPendingLeaves().catch(() => ({ data: [] })),
        canReviewChanges ? getProfileChangeRequests('pending').catch(() => ({ data: [] }))
                         : Promise.resolve({ data: [] }),
      ]);
      if (staffRes.success) {
        setStaff(staffRes.data || []);
        setTotal(staffRes.meta?.total || 0);
      } else {
        setError(staffRes.detail || 'Unable to load staff profiles');
      }
      if (leavesRes.success) setPendingLeaves(leavesRes.data || []);
      if (requestsRes.success) setChangeRequests(requestsRes.data || []);
    } catch (err) {
      setError(err.message || 'Unable to load staff profiles');
    }
    setLoading(false);
    setLeavesLoading(false);
  }, [page, sort, pageSize, canReviewChanges, enrolmentView, search]);

  useEffect(() => { loadData(); }, [loadData]);

  const loadCounts = useCallback(async () => {
    const res = await getStaffEnrolmentSummary();
    if (res.success) setEnrolmentCounts(res.data);
  }, []);
  useEffect(() => { loadCounts(); }, [loadCounts]);

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

  const handleChangeRequest = async (requestId, status) => {
    let reason = '';
    if (status === 'rejected') {
      // Optional, unlike a leave decision — a correction may simply be wrong,
      // and forcing a sentence would make people type "no" to get past it.
      reason = window.prompt('Why is this not being approved? (optional)') || '';
    }
    const res = await decideProfileChangeRequest(requestId, status, reason.trim());
    if (!res.success) setError(res.detail || 'Unable to decide that request');
    loadData();
  };

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
    if (res.success) { loadData(); loadCounts(); }
    else setError(res.detail || 'Unable to deactivate staff profile');
  };

  /** Put someone back on the staff roll. Their login comes back with them. */
  const restore = async (profile) => {
    if (!window.confirm(`Put ${profile.name} back on the staff roll? Their login will work again.`)) return;
    const res = await setStaffEnrolment(profile.id, 'active');
    if (res.success) { loadData(); loadCounts(); }
    else setError(res.detail || 'Unable to restore this staff profile');
  };

  const changeState = async (state, reason) => {
    if (!stateTarget) return;
    setSavingState(true);
    const res = await setStaffEnrolment(stateTarget.id, state, reason);
    setSavingState(false);
    if (res.success) {
      setStateTarget(null);
      loadData();
      loadCounts();
    } else {
      setError(res.detail || 'Unable to change this status');
    }
  };

  const confirmErase = async (reason) => {
    if (!eraseTarget) return;
    const res = await eraseStaff(eraseTarget.id, reason);
    if (res.success) {
      setEraseTarget(null);
      loadData();
      loadCounts();
    } else {
      setError(res.detail || 'Unable to erase this staff record');
    }
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
          <div style={{ color: 'var(--c-muted)', fontSize: 11, marginTop: 3, display: 'flex', alignItems: 'center', gap: 5 }}>
            {loading && <RefreshCw size={10} style={{ animation: 'spin 0.8s linear infinite' }} />}
            {attendanceLiveLabel}
          </div>
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
          ...(canReviewChanges ? [['changes', `Corrections (${changeRequests.length})`]] : []),
        ].map(([id, label]) => (
          <button key={id} onClick={() => setActiveTab(id)} style={{ background: 'none', border: 'none', borderBottom: activeTab === id ? '2px solid var(--tool-hex-4f8ff7)' : '2px solid transparent', color: activeTab === id ? 'var(--c-text)' : 'var(--c-faint)', padding: '9px 16px', fontSize: 13, cursor: 'pointer' }}>{label}</button>
        ))}
      </div>

      {error && <div style={{ color: 'var(--tool-hex-f87171)', background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.18)', borderRadius: 8, padding: 10, marginBottom: 12, fontSize: 12 }}>{error}</div>}

      {/* D-44: a deep link that could not be opened says so, and the list still works. */}
      {focusError && (
        <div data-testid="staff-focus-error" style={{ color: 'var(--tool-hex-f87171)', background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.18)', borderRadius: 8, padding: 10, marginBottom: 12, fontSize: 12 }}>{focusError}</div>
      )}

      {activeTab === 'profiles' && (
        <>
          <div style={{ display: 'flex', gap: 10, marginBottom: 10, flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <div style={{ position: 'relative', flex: '1 1 240px', maxWidth: 320 }}>
              <Search size={13} style={{ position: 'absolute', left: 12, top: 20, transform: 'translateY(-50%)', color: 'var(--c-faint)' }} />
              <input
                value={search}
                onChange={(event) => { setSearch(event.target.value); setPage(1); }}
                data-testid="staff-search"
                aria-label="Search staff by name, employee ID, designation or department"
                placeholder="Name, employee ID, designation…"
                style={{ ...inputStyle, paddingLeft: 32, width: '100%' }}
              />
            </div>
            <ViewPicker
              value={enrolmentView}
              canSeeOffRoll={canChangeEnrolment}
              onChange={(next) => { setEnrolmentView(next); setPage(1); }}
              data-testid="staff-view-picker"
            />
            <select value={sort} onChange={(event) => { setSort(event.target.value); setPage(1); }} aria-label="Sort staff by" style={{ ...inputStyle, width: 180 }}>
              <option value="name">Sort by name</option>
              <option value="staff_type">Sort by type</option>
              <option value="department">Sort by department</option>
              <option value="created_at">Newest first</option>
            </select>
          </div>

          {enrolmentCounts && (
            <div data-testid="staff-enrolment-counts" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
              <Pill tone="green">{enrolmentCounts.on_roll} on the roll</Pill>
              <Pill tone="orange">{enrolmentCounts.nso} on the NSO list</Pill>
              <Pill tone="neutral">{enrolmentCounts.tc_issued} have left</Pill>
            </div>
          )}

          <DataTable
            tableId="staff"
            caption="Staff, sortable by column"
            columns={staffColumns}
            rows={staff}
            rowKey={(profile) => profile.id}
            sort={sort}
            onSortChange={changeSort}
            page={page}
            total={total}
            pageSize={pageSize}
            onPageChange={setPage}
            onPageSizeChange={changePageSize}
            emptyTitle={enrolmentView === OFF_ROLL_VIEW ? 'The recycle bin is empty' : 'No staff records found'}
            emptyMessage={enrolmentView === OFF_ROLL_VIEW
              ? 'Nobody has been taken off the staff roll. Anyone moved to NSO or marked as having left will appear here, and can be put back.'
              : 'Try clearing the search, or add a member of staff.'}
          />
        </>
      )}

      {activeTab === 'leaves' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 840 }}>
          {leavesLoading ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>
              <RefreshCw size={18} style={{ animation: 'spin 0.8s linear infinite', marginBottom: 8 }} />
              <div>Loading leave requests…</div>
            </div>
          ) : pendingLeaves.length === 0 ? (
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

      {activeTab === 'changes' && canReviewChanges && (
        <div data-testid="staff-change-requests" style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 840 }}>
          {changeRequests.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13, background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8 }}>
              Nobody has asked for a correction
            </div>
          ) : changeRequests.map((req) => (
            <div key={req.id} data-testid={`change-request-${req.id}`} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <div style={{ minWidth: 240 }}>
                  <div style={{ fontWeight: 650, color: 'var(--c-text)', fontSize: 14 }}>
                    {req.requested_by_name || 'A member of staff'}
                  </div>
                  {/* Old beside new — a reviewer should never have to go and
                      look up what the current value was. */}
                  {Object.entries(req.requested || {}).map(([field, value]) => (
                    <div key={field} style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 5, fontSize: 12, flexWrap: 'wrap' }}>
                      <span style={{ color: 'var(--c-faint)', minWidth: 46 }}>{field}</span>
                      <span style={{ color: 'var(--c-muted)', textDecoration: 'line-through' }}>
                        {(req.current || {})[field] || 'not recorded'}
                      </span>
                      <ArrowRight size={11} style={{ color: 'var(--c-faint)' }} />
                      <span style={{ color: 'var(--c-text)', fontWeight: 600 }}>{value}</span>
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <ActionButton variant="secondary" onClick={() => handleChangeRequest(req.id, 'approved')}><CheckCircle size={13} />Approve</ActionButton>
                  <ActionButton variant="danger" onClick={() => handleChangeRequest(req.id, 'rejected')}><XCircle size={13} />Reject</ActionButton>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showAdd && <StaffModal canEditLeaveBalances={canEditLeaveBalances} onClose={() => setShowAdd(false)} onSaved={loadData} />}
      {editing && <StaffModal initialStaff={editing} canEditLeaveBalances={canEditLeaveBalances} onClose={() => setEditing(null)} onSaved={loadData} />}
      {resetTarget && <ResetPasswordModal profile={resetTarget} onClose={() => setResetTarget(null)} />}

      {stateTarget && (
        <EnrolmentStateModal
          person={stateTarget}
          currentState={readState(stateTarget)}
          kind="staff"
          busy={savingState}
          onCancel={() => setStateTarget(null)}
          onConfirm={changeState}
        />
      )}

      {eraseTarget && (
        <EraseConfirmModal
          person={eraseTarget}
          kind="staff"
          onCancel={() => setEraseTarget(null)}
          onConfirm={confirmErase}
        />
      )}
    </div>
  );
}
