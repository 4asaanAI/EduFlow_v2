import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useUser } from '../../contexts/UserContext';
import { compareClassLabels } from '../../lib/classOrder';
import {
  createStudent,
  deactivateStudent,
  eraseStudent,
  getAllClasses,
  getStudent,
  getStudentStrengthStats,
  getStudents,
  updateStudent,
  uploadGuardianPhoto,
  uploadStudentPhoto,
  upsertGuardians,
} from '../../lib/api';
import { Camera, CheckCircle2, ChevronLeft, ChevronRight, Edit3, MinusCircle, Plus, RefreshCw, Search, Trash2, User, X } from 'lucide-react';
import DataTable, { cellValue } from '../ui/DataTable';
import { Pill } from '../ui/primitives';
import { useTablePageSize } from '../../hooks/useTablePrefs';

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

function Btn({ children, onClick, disabled, variant = 'primary', type = 'button', title, style: extra }) {
  const secondary = variant === 'secondary';
  const danger = variant === 'danger';
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      style={{
        minHeight: 36,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        background: danger ? '#7f1d1d' : secondary ? 'var(--c-bg)' : '#4f8ff7',
        border: secondary ? '1px solid var(--c-border)' : 'none',
        borderRadius: 8,
        padding: '7px 13px',
        color: danger || !secondary ? '#fff' : 'var(--c-muted)',
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
          status: personal.status,
          blood_group: medical.blood_group,
          height_cm: medical.height_cm ? parseFloat(medical.height_cm) : undefined,
          weight_kg: medical.weight_kg ? parseFloat(medical.weight_kg) : undefined,
          medical_notes: medical.medical_notes,
          emergency_contact: medical.emergency_contact,
        });
        if (!res.success) { setError(res.detail || 'Unable to save'); setSaving(false); return; }
        studentId = initialStudent.id;
      } else {
        const res = await createStudent(null, payload);
        if (!res.success) { setError(res.detail || 'Unable to save'); setSaving(false); return; }
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
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div style={{ gridColumn: '1 / -1' }}>
                <Field label="Full Name *">
                  <input value={personal.name} onChange={setP('name')} style={inputStyle} placeholder="Student's full name" />
                </Field>
              </div>
              <Field label="Class *">
                <select value={personal.class_id} onChange={setP('class_id')} style={inputStyle}>
                  <option value="">Select class</option>
                  {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
                </select>
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
              {editing && (
                <Field label="Status">
                  <select value={personal.status} onChange={setP('status')} style={inputStyle}>
                    <option value="active">Active</option>
                    <option value="withdrawn">Withdrawn</option>
                    <option value="transferred">Transferred</option>
                    <option value="graduated">Graduated</option>
                  </select>
                </Field>
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
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
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
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
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
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
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
                  <input value={medical.emergency_contact} onChange={setM('emergency_contact')} style={inputStyle} placeholder="Name: Phone — e.g. Uncle Ramesh: 9876543210" />
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

function DetailPanel({ studentId, onClose, onEdit, canManage }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getStudent(studentId).then(res => {
      if (res.success) setData(res.data);
      setLoading(false);
    });
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
      <div style={{ width: 420, maxWidth: '95vw', background: 'var(--c-input)', borderLeft: '1px solid var(--c-border)', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
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
              <InfoRow label="Admission No." value={data.admission_number || '—'} mono />
              <InfoRow label="Date of Birth" value={data.dob ? `${data.dob}${age ? ` (${age}y)` : ''}` : '—'} />
              <InfoRow label="Gender" value={data.gender ? data.gender.charAt(0).toUpperCase() + data.gender.slice(1) : '—'} />
              <InfoRow label="Admission Date" value={data.admission_date || '—'} />
            </Section>

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
                <InfoRow label="Bus Route" value={data.bus_route || '—'} />
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
  const [includeInactive, setIncludeInactive] = useState(false);
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [editing, setEditing] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [detailId, setDetailId] = useState(null);
  const [eraseTarget, setEraseTarget] = useState(null);
  const [eraseReason, setEraseReason] = useState('');

  const canManage = ['owner', 'admin'].includes(currentUser.role);
  const canErase = currentUser.role === 'owner';

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
      key: 'status', label: 'Status',
      render: (s) => (
        <Pill tone={s.is_active ? 'green' : 'neutral'} icon={s.is_active ? CheckCircle2 : MinusCircle}>
          {s.status || (s.is_active ? 'active' : 'inactive')}
        </Pill>
      ),
    },
    {
      key: 'actions', label: 'Actions',
      render: (student) => (
        <div style={{ display: 'flex', gap: 5, alignItems: 'center' }} onClick={e => e.stopPropagation()}>
          <Btn variant="secondary" onClick={() => setDetailId(student.id)} title="View profile"><User size={12} /></Btn>
          {canManage && <Btn variant="secondary" onClick={() => openEdit(student)} title="Edit student"><Edit3 size={12} /></Btn>}
          {canManage && student.is_active && <Btn variant="secondary" onClick={() => deactivate(student)} title="Deactivate">Deactivate</Btn>}
          {canErase && <Btn variant="danger" onClick={() => setEraseTarget(student)} title="Erase student"><Trash2 size={12} /></Btn>}
        </div>
      ),
    },
  ], [canManage, canErase]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Server-side aggregated stats for the Class Strength tab (accurate across all pages)
  const [strengthStats, setStrengthStats] = useState([]);
  const [strengthLoading, setStrengthLoading] = useState(false);

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

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      // UX-DR10: the size goes to the API so the SERVER paginates. Fetching
      // everything and slicing on the client would defeat the point entirely
      // on a 1,802-row table.
      const params = { page, sort, limit: pageSize };
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
  }, [search, filterClass, includeInactive, sort, page, pageSize, currentUser]);

  useEffect(() => { loadClasses(); }, [loadClasses]);
  useEffect(() => { loadData(); }, [loadData]);

  const deactivate = async (student) => {
    if (!window.confirm(`Deactivate ${student.name}?`)) return;
    const res = await deactivateStudent(student.id);
    if (res.success) loadData();
    else setError(res.detail || 'Unable to deactivate student');
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

  const openEdit = (student) => {
    setDetailId(null);
    setEditing(student);
  };

  return (
    <div data-testid="student-database-tool" style={{ padding: 24, overflowY: 'auto', height: '100%', boxSizing: 'border-box' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--c-text)', margin: 0 }}>Student Database</h1>
          <div style={{ color: 'var(--c-faint)', fontSize: 12, marginTop: 3 }}>{total} records</div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Btn variant="secondary" onClick={loadData}><RefreshCw size={13} />Refresh</Btn>
          {canManage && <Btn onClick={() => setShowAdd(true)}><Plus size={13} />Add Student</Btn>}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 18, borderBottom: '1px solid var(--c-border)' }}>
        {[{ id: 'database', label: 'Database' }, { id: 'strength', label: 'Class Strength' }].map(t => (
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

      {/* ── Class Strength Tab ── */}
      {tab === 'strength' && (
        <div>
          {strengthLoading ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>Loading strength data…</div>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12, marginBottom: 24 }}>
                {[
                  { label: 'Total Students', value: strengthStats.reduce((a, r) => a + r.total, 0), color: '#4f8ff7' },
                  { label: 'Classes', value: strengthStats.length, color: '#34d399' },
                  { label: 'Boys', value: strengthStats.reduce((a, r) => a + r.boys, 0), color: '#60a5fa' },
                  { label: 'Girls', value: strengthStats.reduce((a, r) => a + r.girls, 0), color: '#f472b6' },
                ].map(stat => (
                  <div key={stat.label} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: '16px 18px' }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: stat.color }}>{stat.value}</div>
                    <div style={{ fontSize: 12, color: 'var(--c-muted)', marginTop: 4 }}>{stat.label}</div>
                  </div>
                ))}
              </div>
              {strengthStats.length === 0 ? (
                <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>No student data available</div>
              ) : (
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
                      {strengthStats.map((row, i) => (
                        <tr key={row.class_id || i} style={{ borderBottom: i < strengthStats.length - 1 ? '1px solid var(--c-border)' : 'none' }}>
                          <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--c-text)', fontSize: 13 }}>{row.class_label}</td>
                          <td style={{ padding: '10px 14px', color: '#60a5fa', fontSize: 13 }}>{row.boys}</td>
                          <td style={{ padding: '10px 14px', color: '#f472b6', fontSize: 13 }}>{row.girls}</td>
                          <td style={{ padding: '10px 14px', color: 'var(--c-muted)', fontSize: 13 }}>{row.other}</td>
                          <td style={{ padding: '10px 14px', fontWeight: 700, color: 'var(--c-text)', fontSize: 13 }}>{row.total}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
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
            <select value={filterClass} onChange={e => { setFilterClass(e.target.value); setPage(1); }}
              data-testid="class-filter" style={{ ...inputStyle, width: 160 }}>
              <option value="">All classes</option>
              {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
            </select>
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
            {currentUser.role === 'owner' && (
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--c-muted)', fontSize: 12, minHeight: 36, cursor: 'pointer' }}>
                <input type="checkbox" checked={includeInactive} onChange={e => { setIncludeInactive(e.target.checked); setPage(1); }} />
                Include inactive
              </label>
            )}
          </div>

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
              emptyTitle="No students match these filters"
              emptyMessage="Try clearing the search or choosing a different class."
            />
          )}
        </>
      )}

      {/* Modals */}
      {showAdd && <StudentProfileModal classes={classes} onClose={() => setShowAdd(false)} onSaved={loadData} />}
      {editing && <StudentProfileModal classes={classes} initialStudent={editing} onClose={() => setEditing(null)} onSaved={loadData} />}
      {detailId && <DetailPanel studentId={detailId} onClose={() => setDetailId(null)} onEdit={openEdit} canManage={canManage} />}

      {eraseTarget && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 210, padding: 16 }}>
          <div style={{ background: 'var(--c-input)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 22, width: 480, maxWidth: '100%' }}>
            <h3 style={{ color: 'var(--c-text)', fontSize: 16, margin: '0 0 6px' }}>Erase {eraseTarget.name}</h3>
            <p style={{ color: 'var(--c-faint)', fontSize: 12, lineHeight: 1.6, margin: '0 0 12px' }}>This permanently removes student PII and pseudonymizes attendance records. Enter a detailed reason.</p>
            <textarea value={eraseReason} onChange={e => setEraseReason(e.target.value)} rows={4} style={{ ...inputStyle, resize: 'vertical' }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 14 }}>
              <Btn variant="secondary" onClick={() => { setEraseTarget(null); setEraseReason(''); }}>Cancel</Btn>
              <Btn variant="danger" disabled={eraseReason.trim().length < 10} onClick={confirmErase}>Erase Student</Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
