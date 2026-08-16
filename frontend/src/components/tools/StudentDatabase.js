import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import { compareClassLabels } from '../../lib/classOrder';
import {
  createStudent,
  deactivateStudent,
  eraseStudent,
  setStudentEnrolment,
  getAllClasses,
  getStudent,
  getStudentFeeStatus,
  explainStudentFee,
  setStudentConcession,
  recordAdmissionConcession,
  setRightToEducation,
  getStudentEnrolmentSummary,
  getStudentStrengthStats,
  getStudents,
  updateStudent,
  uploadGuardianPhoto,
  uploadStudentPhoto,
  upsertGuardians,
} from '../../lib/api';
import { Camera, ChevronLeft, ChevronRight, Edit3, MinusCircle, Plus, RefreshCw, RotateCcw, Search, Trash2, User, X } from 'lucide-react';
import DataTable, { cellValue } from '../ui/DataTable';
import { Pill } from '../ui/primitives';
import {
  EnrolmentBadge,
  EnrolmentStateModal,
  EraseConfirmModal,
  ViewPicker,
} from '../ui/EnrolmentControls';
import { ON_ROLL_VIEW, OFF_ROLL_VIEW, readState } from '../../lib/enrolmentStates';
import ProfileNotes from '../ui/ProfileNotes';
import ProfileDocuments from '../ui/ProfileDocuments';
import { ALL_ROWS, useTablePageSize } from '../../hooks/useTablePrefs';
import { fetchAllRows } from '../../lib/fetchAllRows';
import { collectAllRows } from '../../lib/exportTable';
// The staff finder from the retired School Directory screen (D-44 cluster D).
import { StaffTab } from './SchoolDirectory';
import SearchableSelect from '../ui/SearchableSelect';

/**
 * The most rows `GET /api/students` will return in one request (`per_page` is
 * clamped to 500 in backend/routes/students.py). "All" walks the pages in chunks
 * this size. If the server's cap ever moves, this number moves with it.
 */
const SERVER_MAX_LIMIT = 500;

// Class Strength columns. "Not recorded" is its own column because it is a
// different fact from "Other": one is a student recorded as another gender, the
// other is a student whose gender was never captured. Merging them is what made
// "Other" and "Total" show the same number for every class (owner, 2026-07-22).
const STRENGTH_COLUMNS = [
  { key: 'class_label', label: 'Class', sortKey: 'class_label',
    render: (r) => <span style={{ fontWeight: 600 }}>{r.class_label}</span> },
  { key: 'boys', label: 'Boys', sortKey: 'boys', align: 'right',
    render: (r) => <span style={{ color: '#60a5fa' }}>{r.boys}</span> },
  { key: 'girls', label: 'Girls', sortKey: 'girls', align: 'right',
    render: (r) => <span style={{ color: '#f472b6' }}>{r.girls}</span> },
  { key: 'other', label: 'Other', sortKey: 'other', align: 'right',
    render: (r) => <span style={{ color: 'var(--color-text-muted)' }}>{r.other ?? 0}</span> },
  { key: 'not_recorded', label: 'Not recorded', sortKey: 'not_recorded', align: 'right',
    render: (r) => (
      <span style={{ color: 'var(--color-text-muted)', fontStyle: (r.not_recorded ?? 0) > 0 ? 'italic' : 'normal' }}>
        {r.not_recorded ?? 0}
      </span>
    ) },
  { key: 'total', label: 'Total', sortKey: 'total', align: 'right',
    render: (r) => <span style={{ fontWeight: 700 }}>{r.total}</span> },
];

// ─── Shared styles ────────────────────────────────────────────────────────────

const inputStyle = {
  width: '100%',
  background: 'var(--c-bg)',
  border: '1px solid var(--c-border)',
  borderRadius: 8,
  padding: '9px 12px',
  color: 'var(--c-text)',
  fontSize: 13,
  outline: 'none',
  boxSizing: 'border-box',
};

function Btn({ children, onClick, disabled, variant = 'primary', type = 'button', title, style: extra, 'aria-label': ariaLabel }) {
  const secondary = variant === 'secondary';
  const danger = variant === 'danger';
  return (
    <button
      type={type}
      title={title}
      aria-label={ariaLabel}
      onClick={onClick}
      disabled={disabled}
      style={{
        // 40px, the platform's thumb floor. Phone and tablet are the primary
        // devices; the phone sweep in Release 3 item E found this one short.
        minHeight: 40,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        background: danger ? '#7f1d1d' : secondary ? 'var(--c-bg)' : '#4f8ff7',
        border: secondary ? '1px solid var(--c-border)' : 'none',
        borderRadius: 8,
        padding: '7px 13px',
        // --c-text, not --c-muted. A secondary button's label and its icon both take
        // this colour, and the muted grey sat close enough to the button's own fill
        // that a 12px icon in it disappeared (owner request 9, 2026-08-06).
        color: danger || !secondary ? '#fff' : 'var(--c-text)',
        fontSize: 12,
        fontWeight: 600,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
        ...extra,
      }}
    >
      {children}
    </button>
  );
}

function Field({ label, children }) {
  return (
    <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>
      {label}
      <div style={{ marginTop: 5 }}>{children}</div>
    </label>
  );
}

function PhotoUploader({ src, onFile, size = 72, label = 'Upload' }) {
  const inputRef = useRef();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
      <div
        onClick={() => inputRef.current.click()}
        style={{
          width: size, height: size, borderRadius: size < 80 ? 8 : '50%',
          background: src ? `url(${src}) center/cover no-repeat` : 'var(--c-input)',
          border: '2px dashed var(--c-border)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', flexShrink: 0,
        }}
      >
        {!src && <Camera size={size > 80 ? 22 : 16} color="var(--c-faint)" />}
      </div>
      <span style={{ fontSize: 10, color: 'var(--c-faint)' }}>{label}</span>
      <input ref={inputRef} type="file" accept="image/*,.heic" style={{ display: 'none' }}
        onChange={e => onFile && onFile(e.target.files?.[0])} />
    </div>
  );
}

// ─── Tabbed Profile Modal ─────────────────────────────────────────────────────

const ALL_MODAL_TABS = [
  { id: 'personal', label: 'Personal' },
  { id: 'parents', label: 'Parents' },
  { id: 'medical', label: 'Medical' },
];

const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];
const HOUSES = ['Atulya', 'Agrim', 'Agamya', 'Aprajit'];
const HOUSE_COLORS = {
  Atulya:  { bg: 'rgba(239,68,68,0.12)',   color: '#ef4444' },
  Agrim:   { bg: 'rgba(59,130,246,0.12)',  color: '#3b82f6' },
  Agamya:  { bg: 'rgba(34,197,94,0.12)',   color: '#22c55e' },
  Aprajit: { bg: 'rgba(234,179,8,0.12)',   color: '#eab308' },
};

function blankGuardian(relation) {
  return { relation, name: '', phone: '', occupation: '', email: '', photo_url: null, _tmpPhotoFile: null };
}

function StudentProfileModal({ classes, initialStudent, onClose, onSaved }) {
  const editing = Boolean(initialStudent);
  const [activeTab, setActiveTab] = useState('personal');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [photoFile, setPhotoFile] = useState(null);
  const [photoPreview, setPhotoPreview] = useState(initialStudent?.photo_url || null);

  const [personal, setPersonal] = useState({
    name: initialStudent?.name || '',
    class_id: initialStudent?.class_id || '',
    admission_number: initialStudent?.admission_number || '',
    roll_number: initialStudent?.roll_number || '',
    dob: initialStudent?.dob || '',
    gender: initialStudent?.gender || '',
    house: initialStudent?.house || '',
    status: initialStudent?.status || 'active',
    // Owner request 11 (2026-08-06): where the child lives. One free-text box on
    // purpose - Indian addresses do not fit tidily into line1/line2/postcode, and a
    // form that fights the address is a form nobody fills in.
    address: initialStudent?.address || '',
  });

  const getGuardianByRelation = (relation) => {
    // First try exact match, then fall back to 'Parent' (created by bulk import)
    const g = initialStudent?.guardians?.find(g => g.relation?.toLowerCase() === relation.toLowerCase())
      || (relation.toLowerCase() === 'father' ? initialStudent?.guardians?.find(g => g.relation?.toLowerCase() === 'parent') : null);
    return g ? { relation: relation, name: g.name || '', phone: g.phone || '', occupation: g.occupation || '', email: g.email || '', photo_url: g.photo_url || null, id: g.id, _tmpPhotoFile: null } : blankGuardian(relation);
  };

  const [father, setFather] = useState(() => getGuardianByRelation('Father'));
  const [mother, setMother] = useState(() => getGuardianByRelation('Mother'));

  const [medical, setMedical] = useState({
    blood_group: initialStudent?.blood_group || '',
    height_cm: initialStudent?.height_cm || '',
    weight_kg: initialStudent?.weight_kg || '',
    medical_notes: initialStudent?.medical_notes || '',
    emergency_contact: initialStudent?.emergency_contact || '',
  });

  const handlePhotoSelect = (file) => {
    if (!file) return;
    setPhotoFile(file);
    setPhotoPreview(URL.createObjectURL(file));
  };

  const handleFatherPhoto = (file) => {
    if (!file) return;
    setFather(prev => ({ ...prev, _tmpPhotoFile: file, photo_url: URL.createObjectURL(file) }));
  };

  const handleMotherPhoto = (file) => {
    if (!file) return;
    setMother(prev => ({ ...prev, _tmpPhotoFile: file, photo_url: URL.createObjectURL(file) }));
  };

  const validate = () => {
    if (!personal.name.trim()) return 'Student name is required';
    if (!personal.class_id) return 'Class is required';
    return null;
  };

  const submit = async (e) => {
    e.preventDefault();
    const err = validate();
    if (err) { setError(err); return; }
    setSaving(true);
    setError('');
    try {
      const payload = {
        ...personal,
        ...medical,
        height_cm: medical.height_cm ? parseFloat(medical.height_cm) : null,
        weight_kg: medical.weight_kg ? parseFloat(medical.weight_kg) : null,
        father_name: father.name,
        father_phone: father.phone,
        father_occupation: father.occupation,
        mother_name: mother.name,
        mother_phone: mother.phone,
        mother_occupation: mother.occupation,
      };

      let studentId;
      if (editing) {
        const res = await updateStudent(initialStudent.id, {
          name: personal.name,
          class_id: personal.class_id,
          admission_number: personal.admission_number,
          roll_number: personal.roll_number,
          dob: personal.dob,
          gender: personal.gender,
          house: personal.house,
          address: personal.address,
          blood_group: medical.blood_group,
          height_cm: medical.height_cm ? parseFloat(medical.height_cm) : undefined,
          weight_kg: medical.weight_kg ? parseFloat(medical.weight_kg) : undefined,
          medical_notes: medical.medical_notes,
          emergency_contact: medical.emergency_contact,
        });
        if (!res.success) { setError(res.detail || "Couldn't save"); setSaving(false); return; }
        studentId = initialStudent.id;
      } else {
        const res = await createStudent(payload);
        if (!res.success) { setError(res.detail || "Couldn't save"); setSaving(false); return; }
        studentId = res.data?.id;
      }

      const guardiansToSave = [];
      if (father.name && father.phone) guardiansToSave.push({ ...father, relation: 'Father', is_primary: true });
      if (mother.name && mother.phone) guardiansToSave.push({ ...mother, relation: 'Mother', is_primary: !father.name });
      if (guardiansToSave.length > 0 && studentId) {
        const gRes = await upsertGuardians(studentId, guardiansToSave);
        if (gRes.success && gRes.data) {
          for (const saved of gRes.data) {
            const local = saved.relation?.toLowerCase() === 'father' ? father : mother;
            if (local?._tmpPhotoFile) {
              await uploadGuardianPhoto(studentId, saved.id, local._tmpPhotoFile);
            }
          }
        }
      }

      if (photoFile && studentId) await uploadStudentPhoto(studentId, photoFile);

      onSaved();
      onClose();
    } catch (err) {
      setError(err.message || 'Network error');
    }
    setSaving(false);
  };

  const setP = (key) => (e) => { setPersonal(p => ({ ...p, [key]: e.target.value })); setError(''); };
  const setM = (key) => (e) => { setMedical(m => ({ ...m, [key]: e.target.value })); };
  const setF = (key) => (e) => { setFather(f => ({ ...f, [key]: e.target.value })); };
  const setMo = (key) => (e) => { setMother(m => ({ ...m, [key]: e.target.value })); };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 16 }}>
      <div style={{ background: 'var(--c-input)', border: '1px solid var(--c-border)', borderRadius: 12, width: 620, maxWidth: '100%', maxHeight: '92vh', display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 22px 0', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <PhotoUploader src={photoPreview} onFile={handlePhotoSelect} size={52} label="Photo" />
            <div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--c-text)', margin: 0 }}>
                {editing ? 'Edit Student' : 'Add Student'}
              </h3>
              {editing && <div style={{ fontSize: 11, color: 'var(--c-faint)', marginTop: 2 }}>{initialStudent.admission_number}</div>}
            </div>
          </div>
          <button onClick={onClose} style={{ width: 32, height: 32, border: 'none', background: 'transparent', color: 'var(--c-faint)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 6 }}><X size={17} /></button>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 2, padding: '12px 22px 0', borderBottom: '1px solid var(--c-border)', flexShrink: 0 }}>
          {ALL_MODAL_TABS.map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
              padding: '7px 16px', fontSize: 12, fontWeight: activeTab === t.id ? 700 : 500,
              color: activeTab === t.id ? '#4f8ff7' : 'var(--c-muted)',
              background: 'transparent', border: 'none',
              borderBottom: activeTab === t.id ? '2px solid #4f8ff7' : '2px solid transparent',
              cursor: 'pointer', marginBottom: -1,
            }}>{t.label}</button>
          ))}
        </div>

        {/* Body */}
        <form onSubmit={submit} style={{ flex: 1, overflowY: 'auto', padding: '18px 22px' }}>

          {/* ── Personal Tab ── */}
          {activeTab === 'personal' && (
            <div className="responsive-form-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div style={{ gridColumn: '1 / -1' }}>
                <Field label="Full Name *">
                  <input value={personal.name} onChange={setP('name')} style={inputStyle} placeholder="Student's full name" />
                </Field>
              </div>
              <Field label="Class *">
                <SearchableSelect value={personal.class_id} onChange={setP('class_id')} style={inputStyle}>
                  <option value="">Select class</option>
                  {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
                </SearchableSelect>
              </Field>
              <Field label="Gender">
                <select value={personal.gender} onChange={setP('gender')} style={inputStyle}>
                  <option value="">Select</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </Field>
              <Field label="Admission Number">
                <input value={personal.admission_number} onChange={setP('admission_number')} style={inputStyle} placeholder="Auto-generated if blank" />
              </Field>
              <Field label="Roll Number">
                <input value={personal.roll_number} onChange={setP('roll_number')} style={inputStyle} />
              </Field>
              <Field label="Date of Birth">
                <input type="date" value={personal.dob} onChange={setP('dob')} style={inputStyle} />
              </Field>
              <Field label="House">
                <select value={personal.house} onChange={setP('house')} style={inputStyle}>
                  <option value="">No house</option>
                  {HOUSES.map(h => <option key={h} value={h}>{h}</option>)}
                </select>
              </Field>
              <div style={{ gridColumn: '1 / -1' }}>
                <Field label="Address">
                  <textarea
                    value={personal.address}
                    onChange={setP('address')}
                    rows={2}
                    data-testid="student-address"
                    style={{ ...inputStyle, resize: 'vertical' }}
                    placeholder="House, street, locality, town and district"
                  />
                </Field>
              </div>
              {editing && (
                /* Owner request 10 (2026-08-06): the free Status list that used to sit
                   here wrote the `status` word on its own and left `is_active` behind,
                   which is precisely the bug that made a student unrecoverable. Where a
                   student stands is now set in one place, by the Status button on the
                   row, which always writes both. */
                <div style={{ gridColumn: '1 / -1', fontSize: 12, color: 'var(--c-faint)', lineHeight: 1.55 }}>
                  To move this student between the roll, the NSO list and having left,
                  close this form and use the <strong>Status</strong> button on their row.
                </div>
              )}
            </div>
          )}

          {/* ── Parents Tab ── */}
          {activeTab === 'parents' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              {/* Father */}
              <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
                  <PhotoUploader src={father.photo_url} onFile={handleFatherPhoto} size={56} label="Father photo" />
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--c-text)' }}>Father's Details</div>
                </div>
                <div className="responsive-form-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <Field label="Full Name">
                    <input value={father.name} onChange={setF('name')} style={inputStyle} placeholder="Father's name" />
                  </Field>
                  <Field label="Phone">
                    <input value={father.phone} onChange={setF('phone')} style={inputStyle} placeholder="+91 XXXXX XXXXX" />
                  </Field>
                  <Field label="Occupation">
                    <input value={father.occupation} onChange={setF('occupation')} style={inputStyle} placeholder="e.g. Teacher, Engineer" />
                  </Field>
                  <Field label="Email">
                    <input type="email" value={father.email} onChange={setF('email')} style={inputStyle} />
                  </Field>
                </div>
              </div>

              {/* Mother */}
              <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
                  <PhotoUploader src={mother.photo_url} onFile={handleMotherPhoto} size={56} label="Mother photo" />
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--c-text)' }}>Mother's Details</div>
                </div>
                <div className="responsive-form-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <Field label="Full Name">
                    <input value={mother.name} onChange={setMo('name')} style={inputStyle} placeholder="Mother's name" />
                  </Field>
                  <Field label="Phone">
                    <input value={mother.phone} onChange={setMo('phone')} style={inputStyle} placeholder="+91 XXXXX XXXXX" />
                  </Field>
                  <Field label="Occupation">
                    <input value={mother.occupation} onChange={setMo('occupation')} style={inputStyle} placeholder="e.g. Homemaker, Doctor" />
                  </Field>
                  <Field label="Email">
                    <input type="email" value={mother.email} onChange={setMo('email')} style={inputStyle} />
                  </Field>
                </div>
              </div>
            </div>
          )}

          {/* ── Medical Tab ── */}
          {activeTab === 'medical' && (
            <div className="responsive-form-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <Field label="Blood Group">
                <select value={medical.blood_group} onChange={setM('blood_group')} style={inputStyle}>
                  <option value="">Unknown</option>
                  {BLOOD_GROUPS.map(bg => <option key={bg} value={bg}>{bg}</option>)}
                </select>
              </Field>
              <div /> {/* spacer */}
              <Field label="Height (cm)">
                <input type="number" value={medical.height_cm} onChange={setM('height_cm')} style={inputStyle} placeholder="e.g. 142" min={50} max={250} />
              </Field>
              <Field label="Weight (kg)">
                <input type="number" value={medical.weight_kg} onChange={setM('weight_kg')} style={inputStyle} placeholder="e.g. 38" min={5} max={200} />
              </Field>
              <div style={{ gridColumn: '1 / -1' }}>
                <Field label="Medical Notes / Allergies">
                  <textarea value={medical.medical_notes} onChange={setM('medical_notes')} rows={3}
                    style={{ ...inputStyle, resize: 'vertical' }} placeholder="Known allergies, conditions, medications..." />
                </Field>
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <Field label="Emergency Contact (outside parents)">
                  <input value={medical.emergency_contact} onChange={setM('emergency_contact')} style={inputStyle} placeholder="Name: Phone - e.g. Uncle Ramesh: 9876543210" />
                </Field>
              </div>
            </div>
          )}

          {error && <div style={{ color: '#f87171', fontSize: 12, marginTop: 14 }}>{error}</div>}

          {/* Footer */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--c-border)' }}>
            <div />
            <div style={{ display: 'flex', gap: 8 }}>
              <Btn variant="secondary" onClick={onClose}>Cancel</Btn>
              <Btn type="submit" disabled={saving}>{saving ? 'Saving…' : editing ? 'Save Changes' : 'Add Student'}</Btn>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Student Detail Side Panel ────────────────────────────────────────────────

function DetailPanel({ studentId, onClose, onEdit, canManage, canKeepNotes }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // R2-2 / decision 1, 2026-08-10. The management head chases families about fees and
  // until now his student screens could not tell him who was behind at all. This is
  // the flag he was promised: paid or not, and never an amount. The route returns
  // `{student_id, status}` and nothing else, for every caller, so there is no figure
  // here to leak.
  const [feeStatus, setFeeStatus] = useState(null);
  // R2 audit, 2026-08-12. The concessions, the Right to Education mark and the fee band
  // existed on the platform and Flo could explain them, while the screens showed none of
  // it. A rule nobody can see on the record is a rule the office cannot check. The three
  // finance desks get this row; every other profile is refused the route and simply does
  // not see it, exactly like the fee status row above.
  const [feeExplain, setFeeExplain] = useState(null);
  // R2 audit finding 6, 2026-08-12. Flo could grant a concession and no screen could,
  // which is backwards for this platform: the screen is where the office works. These
  // three controls call the same service Flo's tools call, so the two doors cannot give
  // different answers. Only the three finance desks are allowed the routes; for anyone
  // else `feeExplain` is null and none of this renders.
  const [busy, setBusy] = useState('');
  const [problem, setProblem] = useState('');
  const [oneTime, setOneTime] = useState({ open: false, amount: '', authorised_by: '' });

  const reloadFees = useCallback(() => {
    explainStudentFee(studentId)
      .then(res => { if (res?.success) setFeeExplain(res.data || null); })
      .catch(() => {});
  }, [studentId]);

  async function runFeeChange(label, call) {
    setBusy(label);
    setProblem('');
    try {
      const res = await call();
      if (res?.success) reloadFees();
      else setProblem(res?.detail || res?.message || 'That did not go through.');
    } catch {
      setProblem('That did not go through.');
    }
    setBusy('');
  }

  useEffect(() => {
    setLoading(true);
    setFeeStatus(null);
    setFeeExplain(null);
    setProblem('');
    setOneTime({ open: false, amount: '', authorised_by: '' });
    getStudent(studentId).then(res => {
      if (res.success) setData(res.data);
      setLoading(false);
    });
    // Deliberately does not block the panel: a profile that is refused this route
    // (a teacher, say) still gets the whole record, just without the row.
    getStudentFeeStatus(studentId)
      .then(res => { if (res?.success) setFeeStatus(res.data?.status || null); })
      .catch(() => {});
    explainStudentFee(studentId)
      .then(res => { if (res?.success) setFeeExplain(res.data || null); })
      .catch(() => {});
  }, [studentId]);

  if (!studentId) return null;

  const father = data?.guardians?.find(g => g.relation?.toLowerCase() === 'father');
  const mother = data?.guardians?.find(g => g.relation?.toLowerCase() === 'mother');
  const otherGuardians = data?.guardians?.filter(g => !['father', 'mother'].includes(g.relation?.toLowerCase())) || [];

  const age = data?.dob ? Math.floor((Date.now() - new Date(data.dob)) / (365.25 * 24 * 3600 * 1000)) : null;

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 190, display: 'flex' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={{ flex: 1, background: 'rgba(0,0,0,0.45)' }} onClick={onClose} />
      <div style={{ width: 420, maxWidth: '95vw', background: 'var(--c-input)', borderLeft: '1px solid var(--c-border)', display: 'flex', flexDirection: 'column', overflowY: 'auto', height: '100vh' }}>
        {/* Header */}
        <div style={{ padding: '20px 20px 16px', borderBottom: '1px solid var(--c-border)', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          {loading ? (
            <div style={{ color: 'var(--c-faint)', fontSize: 13 }}>Loading…</div>
          ) : data ? (
            <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
              <div style={{ width: 64, height: 64, borderRadius: 12, background: data.photo_url ? `url(${data.photo_url}) center/cover` : 'var(--c-bg)', border: '1px solid var(--c-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, color: 'var(--c-faint)', flexShrink: 0 }}>
                {!data.photo_url && (data.name?.[0] || <User size={22} />)}
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--c-text)' }}>{data.name}</div>
                <div style={{ fontSize: 12, color: 'var(--c-muted)', marginTop: 2 }}>
                  {data.class_info ? `${data.class_info.name}-${data.class_info.section}` : ''} · Roll {data.roll_number || 'N/A'}
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: data.is_active ? 'rgba(52,211,153,0.12)' : 'rgba(100,116,139,0.12)', color: data.is_active ? '#34d399' : 'var(--c-faint)' }}>{data.status || 'active'}</span>
                  {data.house && (() => { const hc = HOUSE_COLORS[data.house] || { bg: 'rgba(79,143,247,0.12)', color: '#4f8ff7' }; return <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: hc.bg, color: hc.color }}>{data.house} House</span>; })()}
                  {data.blood_group && <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: 'rgba(251,113,133,0.12)', color: '#fb7185' }}>{data.blood_group}</span>}
                </div>
              </div>
            </div>
          ) : null}
          <button onClick={onClose} style={{ border: 'none', background: 'transparent', color: 'var(--c-faint)', cursor: 'pointer', padding: 4 }}><X size={17} /></button>
        </div>

        {!loading && data && (
          <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 18 }}>
            {/* Actions */}
            {canManage && (
              <div style={{ display: 'flex', gap: 8 }}>
                <Btn variant="secondary" onClick={() => onEdit(data)} style={{ flex: 1, justifyContent: 'center' }}><Edit3 size={12} />Edit Profile</Btn>
              </div>
            )}

            {/* Personal Info */}
            <Section title="Personal">
              <InfoRow label="Admission No." value={data.admission_number || '-'} mono />
              <InfoRow label="Date of Birth" value={data.dob ? `${data.dob}${age ? ` (${age}y)` : ''}` : '-'} />
              <InfoRow label="Gender" value={data.gender ? data.gender.charAt(0).toUpperCase() + data.gender.slice(1) : '-'} />
              <InfoRow label="Admission Date" value={data.admission_date || '-'} />
              {/* Owner request 11 (2026-08-06) */}
              <InfoRow label="Address" value={data.address || '-'} />
              {feeStatus && (
                <InfoRow
                  label="Fees"
                  value={feeStatus === 'paid' ? 'Paid' : feeStatus === 'overdue' ? 'Overdue' : 'Unpaid'}
                />
              )}
              {/* R2 step 6, Sonu's request: the brothers and sisters in this school, by
                  admission number, so the office can see at a glance who is owed the
                  sibling concession. The links are the school's own, from its payment
                  remarks; nothing here is inferred from surnames or phone numbers. */}
              {data.siblings?.length > 0 && (
                <InfoRow label="Brothers / sisters here" value={data.siblings.join(', ')} mono />
              )}
            </Section>

            {/* What this family is actually charged, and why. Only the three finance
                desks are allowed the route behind this, so for everybody else the whole
                section is simply absent rather than showing a refusal. */}
            {feeExplain && (
              <Section title="Fees, and why">
                {feeExplain.right_to_education ? (
                  <InfoRow
                    label="School fee"
                    value="None. This child holds a government-paid Right to Education place."
                  />
                ) : (
                  <>
                    <InfoRow
                      label="Class fee"
                      value={feeExplain.band?.quarterly_amount
                        ? `₹${feeExplain.band.quarterly_amount.toLocaleString('en-IN')} a quarter (₹${feeExplain.band.annual_amount.toLocaleString('en-IN')} a year)`
                        : 'No fee structure is loaded for this class yet'}
                    />
                    {feeExplain.concessions?.lines?.length > 0 ? (
                      feeExplain.concessions.lines.map((line, i) => (
                        <InfoRow
                          key={i}
                          label={line.label}
                          value={line.amount
                            ? `-₹${line.amount.toLocaleString('en-IN')} · ${line.why}`
                            : line.why}
                        />
                      ))
                    ) : (
                      <InfoRow label="Concessions" value="None" />
                    )}
                    {feeExplain.concessions?.total > 0 && (
                      <InfoRow
                        label="Payable"
                        value={`₹${feeExplain.concessions.net.toLocaleString('en-IN')} a quarter`}
                      />
                    )}
                  </>
                )}
                {feeExplain.transport?.uses_the_bus && (
                  <InfoRow
                    label="School bus"
                    value={`${feeExplain.transport.route || 'route not recorded'}${
                      feeExplain.transport.monthly_fare
                        ? ` · ₹${feeExplain.transport.monthly_fare.toLocaleString('en-IN')} a month, 11 months (no June)`
                        : ''}`}
                  />
                )}
                <InfoRow
                  label="Paid so far"
                  value={`₹${(feeExplain.total_paid || 0).toLocaleString('en-IN')}`}
                />
                {/* R2 audit finding, 2026-08-12. The late fine was worked out only when
                    somebody asked Flo for it, so in practice nobody saw one. It is the
                    school's own rule: 10 a day from the 16th until the quarter ends,
                    then 1,000 at each following quarter end, and only one daily fine
                    ever runs. */}
                {feeExplain.late_fines?.total > 0 && (
                  <InfoRow
                    label="Late fine today"
                    value={`₹${feeExplain.late_fines.total.toLocaleString('en-IN')}${
                      feeExplain.late_fines.daily_running
                        ? ` · ${feeExplain.late_fines.daily_running.toUpperCase()} is still adding ₹10 a day`
                        : ' · no daily fine is running'}`}
                  />
                )}

                {/* The four concessions the school gives, and nothing else. Each button
                    calls the same service Flo calls. The wording says what the school
                    says: the youngest child pays full, and the employee one wins. */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                  {[
                    ['employee_child', "Employee's child (50%)"],
                    ['sibling', 'Sibling concession'],
                  ].map(([key, label]) => {
                    const on = feeExplain.concessions?.lines?.some(
                      l => l.rule === key && l.amount > 0
                    );
                    return (
                      <Btn
                        key={key}
                        variant="secondary"
                        disabled={!!busy || feeExplain.right_to_education}
                        title={feeExplain.right_to_education
                          ? 'This child owes no school fee, so there is nothing to reduce'
                          : `${on ? 'Remove' : 'Give'} the ${label.toLowerCase()}`}
                        onClick={() => runFeeChange(key, () => setStudentConcession({
                          student_id: data.id, concession: key, granted: !on,
                        }))}
                      >
                        {on ? `Remove ${label}` : `Give ${label}`}
                      </Btn>
                    );
                  })}
                  <Btn
                    variant="secondary"
                    disabled={!!busy}
                    title="A government-paid place. Not a discount: no school fee applies at all."
                    onClick={() => {
                      const reason = window.prompt(
                        feeExplain.right_to_education
                          ? 'Why is this child no longer on a Right to Education place? They will be billed school fees from the next bill raised.'
                          : 'Why does this child hold a Right to Education place? (for the record)'
                      );
                      if (!reason) return;
                      runFeeChange('rte', () => setRightToEducation({
                        student_id: data.id,
                        holds_place: !feeExplain.right_to_education,
                        reason,
                      }));
                    }}
                  >
                    {feeExplain.right_to_education
                      ? 'Remove Right to Education place'
                      : 'Mark Right to Education place'}
                  </Btn>
                  {!feeExplain.concessions?.lines?.some(l => l.rule === 'admission_one_time') && (
                    <Btn
                      variant="secondary"
                      disabled={!!busy || feeExplain.right_to_education}
                      onClick={() => setOneTime(o => ({ ...o, open: !o.open }))}
                    >
                      One-time amount agreed at admission
                    </Btn>
                  )}
                </div>

                {oneTime.open && (
                  <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ fontSize: 11, color: 'var(--c-muted)' }}>
                      The school&apos;s owner or the Principal decide this amount and the
                      accountant head applies it. It is used by one instalment and never
                      repeats, so record who agreed to it.
                    </div>
                    <input
                      type="number"
                      placeholder="Amount in rupees"
                      value={oneTime.amount}
                      onChange={e => setOneTime(o => ({ ...o, amount: e.target.value }))}
                      style={{ padding: '7px 10px', borderRadius: 6, border: '1px solid var(--c-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12 }}
                    />
                    <input
                      placeholder="Who agreed it, by name"
                      value={oneTime.authorised_by}
                      onChange={e => setOneTime(o => ({ ...o, authorised_by: e.target.value }))}
                      style={{ padding: '7px 10px', borderRadius: 6, border: '1px solid var(--c-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12 }}
                    />
                    <Btn
                      disabled={!!busy || !oneTime.amount || !oneTime.authorised_by.trim()}
                      onClick={() => runFeeChange('one-time', async () => {
                        const res = await recordAdmissionConcession({
                          student_id: data.id,
                          amount: Number(oneTime.amount),
                          authorised_by: oneTime.authorised_by.trim(),
                        });
                        if (res?.success) setOneTime({ open: false, amount: '', authorised_by: '' });
                        return res;
                      })}
                    >
                      Record it
                    </Btn>
                  </div>
                )}

                {problem && (
                  <div style={{ marginTop: 8, fontSize: 12, color: 'var(--tool-hex-f87171)' }}>
                    {problem}
                  </div>
                )}
              </Section>
            )}

            {/* Medical */}
            {(data.blood_group || data.height_cm || data.weight_kg || data.medical_notes || data.emergency_contact) && (
              <Section title="Medical">
                {data.blood_group && <InfoRow label="Blood Group" value={data.blood_group} />}
                {data.height_cm && <InfoRow label="Height" value={`${data.height_cm} cm`} />}
                {data.weight_kg && <InfoRow label="Weight" value={`${data.weight_kg} kg`} />}
                {data.medical_notes && <InfoRow label="Notes" value={data.medical_notes} />}
                {data.emergency_contact && <InfoRow label="Emergency" value={data.emergency_contact} />}
              </Section>
            )}

            {/* Father */}
            {father && (
              <Section title="Father">
                <GuardianCard guardian={father} />
              </Section>
            )}

            {/* Mother */}
            {mother && (
              <Section title="Mother">
                <GuardianCard guardian={mother} />
              </Section>
            )}

            {/* Other guardians */}
            {otherGuardians.map(g => (
              <Section key={g.id} title={g.relation || 'Guardian'}>
                <GuardianCard guardian={g} />
              </Section>
            ))}

            {/* Transport */}
            {data.uses_transport && (
              <Section title="Transport">
                <InfoRow label="Bus Route" value={data.bus_route || '-'} />
              </Section>
            )}

            {/* Owner request 11 (2026-08-06): Aadhaar, birth certificate and the rest.
                A school record, so the owner and the principal both reach it. */}
            {canKeepNotes && (
              <Section title="Documents">
                <div style={{ padding: '12px 14px' }}>
                  <ProfileDocuments subjectId={data.id} canManage={canManage} />
                </div>
              </Section>
            )}

            {/* Owner request 4 (2026-08-06). PRIVATE TO EACH AUTHOR, unlike the
                documents above: the owner and the principal each see only their own. */}
            {canKeepNotes && (
              <Section title="My notes">
                <div style={{ padding: '12px 14px' }}>
                  <ProfileNotes subjectType="student" subjectId={data.id} subjectName={data.name} />
                </div>
              </Section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontWeight: 800, color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>{title}</div>
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, overflow: 'hidden' }}>
        {children}
      </div>
    </div>
  );
}

function InfoRow({ label, value, mono }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', padding: '9px 14px', borderBottom: '1px solid var(--c-border)', gap: 12 }}>
      <span style={{ fontSize: 12, color: 'var(--c-faint)', whiteSpace: 'nowrap', flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 12, color: 'var(--c-text)', fontFamily: mono ? 'monospace' : undefined, textAlign: 'right', wordBreak: 'break-word' }}>{value}</span>
    </div>
  );
}

function GuardianCard({ guardian }) {
  return (
    <div style={{ padding: '12px 14px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      {guardian.photo_url ? (
        <img src={guardian.photo_url} alt={guardian.name} style={{ width: 44, height: 44, borderRadius: 8, objectFit: 'cover', flexShrink: 0 }} />
      ) : (
        <div style={{ width: 44, height: 44, borderRadius: 8, background: 'var(--c-input)', border: '1px solid var(--c-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <User size={18} color="var(--c-faint)" />
        </div>
      )}
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--c-text)' }}>{guardian.name}</div>
        <div style={{ fontSize: 12, color: 'var(--c-muted)', marginTop: 2 }}>{guardian.phone}</div>
        {guardian.occupation && <div style={{ fontSize: 11, color: 'var(--c-faint)', marginTop: 1 }}>{guardian.occupation}</div>}
        {guardian.email && <div style={{ fontSize: 11, color: 'var(--c-faint)', marginTop: 1 }}>{guardian.email}</div>}
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function StudentDatabase() {
  const { currentUser } = useUser();
  const [tab, setTab] = useState('database');
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [filterClass, setFilterClass] = useState('');
  // Owner request 10 (2026-08-06): this replaced an "Include inactive" tick box.
  // The tick was the only route to a student who had been switched off, it said
  // nothing about why, and it could not tell a child who stopped attending from one
  // who has formally left. Aman asked for a recycle bin, so this is a place you go.
  const [enrolmentView, setEnrolmentView] = useState(ON_ROLL_VIEW);
  const [enrolmentCounts, setEnrolmentCounts] = useState(null);
  const [stateTarget, setStateTarget] = useState(null);
  const [savingState, setSavingState] = useState(false);
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [editing, setEditing] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [detailId, setDetailId] = useState(null);
  const [eraseTarget, setEraseTarget] = useState(null);

  // Epic 7 - deep-link from the School Directory. A row there opens
  // `?tool=student-database&focus=<id>`; open that student's profile once, then
  // strip the param so closing it (or a reload) does not reopen, and the URL
  // stays tidy. Applied a single time via the ref - not on every param change.
  const [searchParams, setSearchParams] = useSearchParams();
  const appliedFocusRef = useRef(false);
  useEffect(() => {
    if (appliedFocusRef.current) return;
    const focus = searchParams.get('focus');
    if (!focus) return;
    appliedFocusRef.current = true;
    setDetailId(focus);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete('focus');
      return next;
    }, { replace: true });
  }, [searchParams, setSearchParams]);

  const canManage = ['owner', 'admin'].includes(currentUser.role);
  // Owner or principal only, matching require_owner_or_principal on the enrolment
  // endpoint. Offering the button to anyone else would only produce a refusal when
  // they pressed it, which is the D-49 mistake.
  const isHeadOfSchool = currentUser.role === 'owner'
    || (currentUser.role === 'admin' && currentUser.sub_category === 'principal');
  const canRestore = isHeadOfSchool;
  // Owner request 2026-08-07: the principal reported there was no way to delete a
  // student. Erase was owner-only, so the principal saw View / Edit / Status and
  // nothing else. It now matches require_owner_or_principal on the erase endpoint.
  const canErase = isHeadOfSchool;

  // UX-DR10: the user's chosen page size, remembered per table.
  const [pageSize, setPageSize] = useTablePageSize('students');

  // Changing the size while on page 40 of a 20-row listing would strand the
  // user on a page that no longer exists, so both handlers reset to page 1.
  const changePageSize = useCallback((n) => { setPageSize(n); setPage(1); }, [setPageSize]);
  const changeSort = useCallback((next) => { setSort(next); setPage(1); }, []);

  const studentColumns = useMemo(() => [
    {
      key: 'name', label: 'Student', sortKey: 'name',
      render: (student) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 'var(--radius-md)', background: student.photo_url ? `url(${student.photo_url}) center/cover` : 'var(--c-input)', border: '1px solid var(--c-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--c-faint)', fontSize: 13, fontWeight: 700, flexShrink: 0 }}>
            {!student.photo_url && student.name?.slice(0, 1)}
          </div>
          <div>
            {/* The real focusable way in. The row click is only a shortcut. */}
            <button
              data-testid={`student-open-${student.id}`}
              onClick={e => { e.stopPropagation(); setDetailId(student.id); }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--c-text)', fontWeight: 700, fontFamily: 'var(--font-display)', fontSize: 'var(--text-base)', textAlign: 'left' }}
            >
              {student.name}
            </button>
            <div style={{ color: 'var(--c-faint)', fontSize: 'var(--text-xs)', marginTop: 1 }}>Roll {student.roll_number || 'N/A'}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'class', label: 'Class', sortKey: 'class',
      // The class lives on a nested object, so a download needs telling where to
      // look. Without this the column would come out blank in the file while
      // reading correctly on screen - a difference nobody would think to check.
      exportValue: (s) => (s.class_info ? `${s.class_info.name}-${s.class_info.section}` : ''),
      render: (s) => (s.class_info ? `${s.class_info.name}-${s.class_info.section}` : cellValue(null)),
    },
    { key: 'primary_phone', label: 'Phone', render: (s) => cellValue(s.primary_phone) },
    { key: 'admission_number', label: 'Admission', sortKey: 'admission_number', render: (s) => cellValue(s.admission_number) },
    { key: 'gender', label: 'Gender', sortKey: 'gender', render: (s) => cellValue(s.gender) },
    {
      key: 'blood_group', label: 'Blood',
      render: (s) => (s.blood_group ? <Pill tone="red">{s.blood_group}</Pill> : cellValue(null)),
    },
    {
      // Owner request 12 (2026-08-06). House was already stored on every student,
      // already editable on the Add and Edit forms, and already shown on the profile
      // panel in its house colour - it was simply never a column, so the one place
      // you would look to see who is in which house did not say.
      key: 'house', label: 'House', sortKey: 'house',
      render: (s) => {
        if (!s.house) return cellValue(null);
        const hc = HOUSE_COLORS[s.house] || { bg: 'rgba(79,143,247,0.12)', color: '#4f8ff7' };
        return (
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
            background: hc.bg, color: hc.color, whiteSpace: 'nowrap',
          }}>
            {s.house}
          </span>
        );
      },
    },
    {
      // Owner request 10 (2026-08-06): the column used to print the raw stored word
      // ("withdrawn"), which is the platform's vocabulary rather than the school's,
      // and it could not tell an NSO child from one who has taken their TC.
      key: 'status', label: 'Status',
      // The same derived state the badge shows, in words. The raw stored field says
      // "withdrawn" for a child who has taken their TC and for one on NSO alike.
      exportValue: (s) => readState(s),
      render: (s) => <EnrolmentBadge state={readState(s)} data-testid={`student-state-${s.id}`} />,
    },
    {
      // Owner request 9 (2026-08-06): "the buttons at the end of each row don't have
      // any symbols to them". Two of the four were icon-only, drawn at 12px in the
      // muted grey - on a phone they read as empty boxes, and the third said
      // "Deactivate" in words beside them, so the row offered no clue that the blank
      // ones did anything at all.
      //
      // Every button now carries BOTH a word and a symbol, at a size you can see, and
      // an accessible name. Mixed icon-only and labelled buttons in one row is the
      // pattern that produced the complaint; do not go back to it.
      key: 'actions', label: 'Actions',
      // Buttons are not data. A column of empty cells in a downloaded file reads as
      // missing information rather than as a control that did not apply.
      exportSkip: true,
      render: (student) => (
        <div style={{ display: 'flex', gap: 5, alignItems: 'center' }} onClick={e => e.stopPropagation()}>
          <Btn variant="secondary" onClick={() => setDetailId(student.id)} title="View this student's profile" aria-label={`View ${student.name}`}>
            <User size={14} aria-hidden="true" />View
          </Btn>
          {canManage && (
            <Btn variant="secondary" onClick={() => openEdit(student)} title="Edit this student" aria-label={`Edit ${student.name}`}>
              <Edit3 size={14} aria-hidden="true" />Edit
            </Btn>
          )}
          {/* Owner or principal: one button for all three states, in either
              direction. Restore is simply "back on the roll", which is why it stays
              as its own button on an off-roll row - it is the one move somebody is
              looking for in a hurry when a name has vanished. */}
          {canRestore && (
            <Btn variant="secondary" onClick={() => setStateTarget(student)} title="Change where this student stands" aria-label={`Change status for ${student.name}`}>
              <RefreshCw size={14} aria-hidden="true" />Status
            </Btn>
          )}
          {canRestore && readState(student) !== 'active' && (
            <Btn variant="secondary" onClick={() => restore(student)} title="Put back on the school roll" aria-label={`Restore ${student.name} to the roll`}>
              <RotateCcw size={14} aria-hidden="true" />Restore
            </Btn>
          )}
          {/* The wider admin set can still take a student off the roll, exactly as
              before. Only the head of school decides where they land after that. */}
          {canManage && !canRestore && student.is_active && (
            <Btn variant="secondary" onClick={() => deactivate(student)} title="Mark as no longer attending" aria-label={`Deactivate ${student.name}`}>
              <MinusCircle size={14} aria-hidden="true" />Deactivate
            </Btn>
          )}
          {canErase && (
            <Btn variant="danger" onClick={() => setEraseTarget(student)} title="Erase permanently" aria-label={`Erase ${student.name} permanently`}>
              <Trash2 size={14} aria-hidden="true" />Erase
            </Btn>
          )}
        </div>
      ),
    },
  ], [canManage, canErase, canRestore]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Server-side aggregated stats for the Class Strength tab (accurate across all pages)
  const [strengthStats, setStrengthStats] = useState([]);
  const [strengthLoading, setStrengthLoading] = useState(false);
  const [strengthSort, setStrengthSort] = useState({ key: 'class_label', direction: 'ascending' });

  const onStrengthSort = useCallback((key) => {
    setStrengthSort(prev => (
      prev.key === key
        ? { key, direction: prev.direction === 'ascending' ? 'descending' : 'ascending' }
        : { key, direction: 'ascending' }
    ));
  }, []);

  const sortedStrengthRows = useMemo(() => {
    const rows = [...strengthStats];
    const { key, direction } = strengthSort;
    const factor = direction === 'descending' ? -1 : 1;
    rows.sort((a, b) => {
      // Class is ordered the way the school reads it - NUR, LKG, UKG, 1st … 12th -
      // never alphabetically, which would put 10th above 1st (owner item 5).
      if (key === 'class_label') {
        return factor * compareClassLabels(a.class_label, b.class_label);
      }
      return factor * ((a[key] ?? 0) - (b[key] ?? 0));
    });
    return rows;
  }, [strengthStats, strengthSort]);

  // Gender was never captured for any of the 1,802 students, so every one of them
  // lands in "not recorded". Boys 0 / Girls 0 are therefore NOT counts of zero
  // children - they are the absence of a record, and must not read as a figure.
  const genderEverRecorded = useMemo(
    () => strengthStats.some(r => (r.boys || 0) + (r.girls || 0) + (r.other || 0) > 0),
    [strengthStats],
  );

  useEffect(() => {
    if (tab !== 'strength') return;
    setStrengthLoading(true);
    getStudentStrengthStats()
      .then(res => {
        if (!res.success) return;
        // The aggregate comes back class-alphabetical, which puts 10th, 11th and
        // 12th above 1st and scatters NUR/LKG/UKG. Order it the way the school
        // reads it. Rows carry the class as one label ("10th-A").
        const rows = [...(res.data || [])].sort((a, b) =>
          compareClassLabels(a.class_name ?? a.class ?? a.label, b.class_name ?? b.class ?? b.label));
        setStrengthStats(rows);
      })
      .finally(() => setStrengthLoading(false));
  }, [tab]);

  const loadClasses = useCallback(async () => {
    const res = await getAllClasses();
    if (res.success) setClasses(res.data || []);
  }, []);

  /**
   * The filters in force right now.
   *
   * Pulled out of `loadData` so that the DOWNLOAD uses exactly the same ones. A
   * download of "class 5 A, searched for Sharma" that quietly comes back as the whole
   * roll is the same class of fault as a short file, in the other direction, and the
   * only way to be sure the two agree is for there to be one of them.
   */
  const currentFilters = useCallback(() => {
    const filters = {};
    if (search) filters.search = search;
    if (filterClass) filters.class_id = filterClass;
    // The server takes the view by name and answers with the derived state on each
    // row, so the screen never has to work out from `is_active` and `status` which
    // of the three a student is in.
    filters.enrolment_state = enrolmentView;
    return filters;
  }, [search, filterClass, enrolmentView]);

  /**
   * Every child matching those filters, for the download.
   *
   * This walks the person's OWN list endpoint rather than calling
   * `/api/export/students`. Two reasons, and the second is the important one:
   *   - the export route takes no filters, so it would hand back the whole roll
   *     whatever the screen was showing;
   *   - the list route is where the filtering, the branch scoping and the teacher
   *     narrowing already live. Restating any of that in a second place is how the
   *     screen and the file start disagreeing, which is the drift this release has
   *     spent most of its time undoing.
   * `fetchAllRows` throws rather than returning a short list, so a file is never
   * built from a partial walk.
   */
  const exportRows = useCallback(
    () => collectAllRows(
      ({ page: cursor, limit }) => getStudents({ ...currentFilters(), page: cursor, sort, limit }),
      { pageMax: SERVER_MAX_LIMIT, what: 'students' },
    ),
    [currentFilters, sort],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const filters = currentFilters();

      // "All" (owner request 13, 2026-08-06). The server refuses more than
      // SERVER_MAX_LIMIT in one request, so this walks the pages and joins them
      // rather than asking for 1,802 at once and getting 500. It stops as soon as
      // a page comes back short or the running count reaches the reported total,
      // so a wrong total on the server cannot spin this forever.
      if (pageSize === ALL_ROWS) {
        const all = await fetchAllRows(
          ({ page: cursor, limit }) => getStudents({ ...filters, page: cursor, sort, limit }),
          { pageMax: SERVER_MAX_LIMIT },
        );
        if (!all.success) {
          setError(all.detail || "Couldn't load students");
        } else {
          setStudents(all.data);
          setTotal(all.total);
        }
        setLoading(false);
        return;
      }

      // UX-DR10: the size goes to the API so the SERVER paginates. Fetching
      // everything and slicing on the client would defeat the point entirely
      // on a 1,802-row table.
      const res = await getStudents({ ...filters, page, sort, limit: pageSize });
      if (res.success) {
        setStudents(res.data || []);
        setTotal(res.meta?.total || 0);
      } else {
        setError(res.detail || "Couldn't load students");
      }
    } catch (err) {
      setError(err.message || "Couldn't load students");
    }
    setLoading(false);
  }, [currentFilters, sort, page, pageSize]);

  useEffect(() => { loadClasses(); }, [loadClasses]);
  useEffect(() => { loadData(); }, [loadData]);

  // The three numbers at the top of the screen. They are what stops anyone reading
  // "1,801 students" as the whole story when three more are on the NSO list and are
  // still marked every morning.
  const loadCounts = useCallback(async () => {
    const res = await getStudentEnrolmentSummary();
    if (res.success) setEnrolmentCounts(res.data);
  }, []);
  useEffect(() => { if (tab === 'database') loadCounts(); }, [tab, loadCounts]);

  const deactivate = async (student) => {
    if (!window.confirm(`Deactivate ${student.name}?`)) return;
    const res = await deactivateStudent(student.id);
    if (res.success) loadData();
    else setError(res.detail || "Couldn't deactivate student");
  };

  /**
   * Put a student back on the roll (owner request 9, 2026-08-06).
   *
   * The button this sits behind is the answer to "a student was deleted during a demo
   * and we cannot get them back". They were never deleted - deactivating only switches
   * a student off - but until the enrolment endpoint existed nothing in the product
   * could switch one back on, so a mistake was permanent in practice.
   *
   * Owner and principal only, which is why the button is gated on `canRestore` rather
   * than `canManage`: the wider admin set can deactivate, but deciding a child is back
   * on the roll is a head-of-school decision, and the server enforces the same rule.
   */
  const restore = async (student) => {
    if (!window.confirm(`Put ${student.name} back on the school roll?`)) return;
    const res = await setStudentEnrolment(student.id, 'active');
    if (res.success) { loadData(); loadCounts(); }
    else setError(res.detail || "Couldn't restore student");
  };

  /** Move one student between the three states, with the optional note. */
  const changeState = async (state, reason) => {
    if (!stateTarget) return;
    setSavingState(true);
    const res = await setStudentEnrolment(stateTarget.id, state, reason);
    setSavingState(false);
    if (res.success) {
      setStateTarget(null);
      loadData();
      loadCounts();
    } else {
      setError(res.detail || "Couldn’t change this student’s status");
    }
  };

  const confirmErase = async (reason) => {
    if (!eraseTarget) return;
    const res = await eraseStudent(eraseTarget.id, reason);
    if (res.success) {
      setEraseTarget(null);
      loadData();
      loadCounts();
    } else {
      setError(res.detail || "Couldn't erase student");
    }
  };

  const openEdit = async (student) => {
    setDetailId(null);
    if (!student.guardians) {
      const res = await getStudent(student.id);
      setEditing(res.success ? res.data : student);
    } else {
      setEditing(student);
    }
  };

  return (
    <div data-testid="student-database-tool" style={{ padding: 24, overflowY: 'auto', height: '100%', boxSizing: 'border-box' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          {/* Renamed on the owner's instruction, 2026-08-07. There used to be two
              screens listing every student - this one, and a read-only "School
              Directory" - and the owner reported them as "two views of the student
              database for some reason". They are one screen now, under the name that
              says what it is: everyone in the school, in one place. */}
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--c-text)', margin: 0 }}>School Directory</h1>
          <div style={{ color: 'var(--c-faint)', fontSize: 12, marginTop: 3 }}>
            {tab === 'staff' ? 'Everyone who works at the school' : `${total} students`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {tab !== 'staff' && <Btn variant="secondary" onClick={loadData}><RefreshCw size={13} />Refresh</Btn>}
          {canManage && tab !== 'staff' && <Btn onClick={() => setShowAdd(true)}><Plus size={13} />Add Student</Btn>}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 18, borderBottom: '1px solid var(--c-border)' }}>
        {[
          { id: 'database', label: 'Students' },
          // The staff list came from the School Directory, which was owner and
          // principal only. Merging the two screens must not hand the staff list to
          // the accountant, transport head or receptionist, who all have this screen
          // for students and never had the Directory. Same gate, new home.
          ...(isHeadOfSchool ? [{ id: 'staff', label: 'Staff' }] : []),
          { id: 'strength', label: 'Class Strength' },
        ].map(t => (
          <button key={t.id} data-testid={`tab-${t.id}`} onClick={() => setTab(t.id)} style={{
            padding: '8px 16px', fontSize: 13,
            fontWeight: tab === t.id ? 700 : 500,
            color: tab === t.id ? '#4f8ff7' : 'var(--c-muted)',
            background: 'transparent', border: 'none',
            borderBottom: tab === t.id ? '2px solid #4f8ff7' : '2px solid transparent',
            cursor: 'pointer', marginBottom: -1,
          }}>{t.label}</button>
        ))}
      </div>

      {/* ── Staff Tab (merged in from the retired School Directory, 2026-08-07) ──
          Opening a person still hands off to Staff Tracker, exactly as it did on the
          old screen, so nothing a person could do before has moved. */}
      {tab === 'staff' && isHeadOfSchool && (
        <StaffTab
          onOpen={(s) => setSearchParams({ tool: 'staff-tracker', focus: s.id })}
          onOpenFullScreen={() => setSearchParams({ tool: 'staff-tracker' })}
        />
      )}

      {/* ── Class Strength Tab ── */}
      {tab === 'strength' && (
        <div>
          {strengthLoading ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>Loading strength data…</div>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12, marginBottom: 24 }}>
                {[
                  { label: 'Total Students', value: strengthStats.reduce((a, r) => a + r.total, 0), color: '#4f8ff7', real: true },
                  { label: 'Classes', value: strengthStats.length, color: '#34d399', real: true },
                  // "Boys 0" when nobody's gender was ever captured is the same lie
                  // this epic exists to remove - it reads as "this school has no
                  // boys" rather than "we never wrote it down".
                  { label: 'Boys', value: strengthStats.reduce((a, r) => a + r.boys, 0), color: '#60a5fa', real: genderEverRecorded },
                  { label: 'Girls', value: strengthStats.reduce((a, r) => a + r.girls, 0), color: '#f472b6', real: genderEverRecorded },
                ].map(stat => (
                  <div key={stat.label} data-stat-state={stat.real ? 'ok' : 'not-recorded'} style={{
                    background: 'var(--c-bg)',
                    border: stat.real ? '1px solid var(--c-border)' : '1px dashed var(--c-border)',
                    borderRadius: 10, padding: '16px 18px',
                  }}>
                    <div style={{
                      fontSize: stat.real ? 28 : 15,
                      fontWeight: 700,
                      color: stat.real ? stat.color : 'var(--c-muted)',
                    }}>
                      {stat.real ? stat.value : 'Not recorded'}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--c-muted)', marginTop: 4 }}>{stat.label}</div>
                    {!stat.real && (
                      <div style={{ fontSize: 11, color: 'var(--c-muted)', marginTop: 3 }}>
                        Gender was never collected for these students
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {/* The shared sortable table (FR82/UX-DR5). Every one of the 48 rows
                  is already in memory here - this is an aggregate, not a page - so
                  ordering the whole array locally IS ordering the whole result set.
                  That is why sorting is done here and not asked of the server. */}
              <DataTable
                tableId="class-strength"
                caption="Students per class, by recorded gender"
                columns={STRENGTH_COLUMNS}
                rows={sortedStrengthRows}
                rowKey={(r, i) => r.class_id || i}
                sort={strengthSort.key}
                sortDirection={strengthSort.direction}
                onSortChange={onStrengthSort}
                page={1}
                total={sortedStrengthRows.length}
                pageSize={sortedStrengthRows.length || 1}
                // The whole summary is already in hand - one page, no server paging -
                // so the file is the table.
                exportTable={{ title: 'Class strength', getRows: async () => sortedStrengthRows }}
                emptyTitle="No student data available"
                emptyMessage="Class strength appears here once students are assigned to classes."
              />
            </>
          )}
        </div>
      )}

      {/* ── Database Tab ── */}
      {tab === 'database' && (
        <>
          {/* Filters */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ position: 'relative', flex: '1 1 240px', maxWidth: 320 }}>
              <Search size={13} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--c-faint)' }} />
              <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
                data-testid="student-search" placeholder="Name or admission no."
                style={{ ...inputStyle, paddingLeft: 32 }} />
            </div>
            <SearchableSelect value={filterClass} onChange={e => { setFilterClass(e.target.value); setPage(1); }}
              data-testid="class-filter" style={{ ...inputStyle, width: 160 }}>
              <option value="">All classes</option>
              {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
            </SearchableSelect>
            {/* Kept alongside the sortable column headings, and bound to the
                same `sort` state so the two can never disagree. Every value a
                heading can set has an option here, or the select would render
                blank once a heading was clicked. */}
            <select value={sort} onChange={e => changeSort(e.target.value)} aria-label="Sort students by" style={{ ...inputStyle, width: 150 }}>
              <option value="name">Name A–Z</option>
              <option value="class">By class</option>
              <option value="admission_number">Admission no.</option>
              <option value="gender">Gender</option>
              <option value="created_at">Newest first</option>
            </select>
            <ViewPicker
              value={enrolmentView}
              canSeeOffRoll={canRestore}
              onChange={(next) => { setEnrolmentView(next); setPage(1); }}
              data-testid="student-view-picker"
            />
          </div>

          {/* The honest headline. "1,801 students" on its own is not the whole
              answer when three more are on the NSO list and are marked every
              morning, and this is the one place the difference is visible. */}
          {enrolmentCounts && (
            <div data-testid="enrolment-counts" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
              <Pill tone="green">{enrolmentCounts.on_roll} on the roll</Pill>
              <Pill tone="orange">{enrolmentCounts.nso} on the NSO list</Pill>
              <Pill tone="neutral">{enrolmentCounts.tc_issued} left the school</Pill>
              <Pill tone="blue">{enrolmentCounts.on_register} marked every day</Pill>
            </div>
          )}

          {error && <div style={{ color: '#f87171', background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.18)', borderRadius: 8, padding: 10, marginBottom: 12, fontSize: 12 }}>{error}</div>}

          {loading ? (
            <div style={{ padding: 40, color: 'var(--c-faint)', fontSize: 13, textAlign: 'center' }}>Loading students…</div>
          ) : (
            <DataTable
              tableId="students"
              caption="Students, sortable by column"
              columns={studentColumns}
              rows={students}
              rowKey={(s) => s.id}
              onRowClick={(s) => setDetailId(prev => (prev === s.id ? null : s.id))}
              sort={sort}
              onSortChange={changeSort}
              page={page}
              total={total}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={changePageSize}
              exportTable={{ title: 'Students', getRows: exportRows }}
              emptyTitle={enrolmentView === OFF_ROLL_VIEW ? 'The recycle bin is empty' : 'No students match these filters'}
              emptyMessage={enrolmentView === OFF_ROLL_VIEW
                ? 'Nobody has been taken off the roll. Anyone moved to NSO or marked as having left will appear here, and can be put back.'
                : 'Try clearing the search or choosing a different class.'}
            />
          )}
        </>
      )}

      {/* Modals */}
      {showAdd && <StudentProfileModal classes={classes} onClose={() => setShowAdd(false)} onSaved={loadData} />}
      {editing && <StudentProfileModal classes={classes} initialStudent={editing} onClose={() => setEditing(null)} onSaved={loadData} />}
      {detailId && <DetailPanel studentId={detailId} onClose={() => setDetailId(null)} onEdit={openEdit} canManage={canManage} canKeepNotes={canRestore} />}

      {stateTarget && (
        <EnrolmentStateModal
          person={stateTarget}
          currentState={readState(stateTarget)}
          kind="student"
          busy={savingState}
          onCancel={() => setStateTarget(null)}
          onConfirm={changeState}
        />
      )}

      {eraseTarget && (
        <EraseConfirmModal
          person={eraseTarget}
          kind="student"
          onCancel={() => setEraseTarget(null)}
          onConfirm={confirmErase}
        />
      )}
    </div>
  );
}
