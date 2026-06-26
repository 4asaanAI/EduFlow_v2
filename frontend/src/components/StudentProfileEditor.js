import React, { useState, useEffect, useCallback } from 'react';
import { User, Heart, Users, Save, Check, AlertCircle } from 'lucide-react';
import { getMyStudentProfile, updateMyStudentProfile, updateMyGuardian } from '../lib/api';

const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'];
const GENDERS = ['Male', 'Female', 'Other'];
const TABS = [
  { id: 'personal', label: 'Personal', icon: User },
  { id: 'medical', label: 'Medical', icon: Heart },
  { id: 'parents', label: 'Parents', icon: Users },
];

function Field({ label, children, style }) {
  return (
    <div style={{ marginBottom: 14, ...style }}>
      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--color-muted)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </label>
      {children}
    </div>
  );
}

function Input({ value, onChange, placeholder, type = 'text', readOnly }) {
  return (
    <input
      type={type}
      value={value || ''}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      readOnly={readOnly}
      style={{
        width: '100%', boxSizing: 'border-box',
        background: readOnly ? 'var(--color-surface-2)' : 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 8, padding: '8px 12px',
        fontSize: 13, color: readOnly ? 'var(--color-muted)' : 'var(--color-text)',
        outline: 'none', cursor: readOnly ? 'default' : 'text',
        transition: 'border-color 0.15s',
      }}
      onFocus={e => { if (!readOnly) e.target.style.borderColor = '#4f8ff7'; }}
      onBlur={e => { e.target.style.borderColor = 'var(--color-border)'; }}
    />
  );
}

function Select({ value, onChange, options }) {
  return (
    <select
      value={value || ''}
      onChange={e => onChange(e.target.value)}
      style={{
        width: '100%', boxSizing: 'border-box',
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 8, padding: '8px 12px',
        fontSize: 13, color: 'var(--color-text)', outline: 'none',
      }}
    >
      <option value="">— Select —</option>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

function Textarea({ value, onChange, placeholder }) {
  return (
    <textarea
      value={value || ''}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      rows={3}
      style={{
        width: '100%', boxSizing: 'border-box',
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 8, padding: '8px 12px',
        fontSize: 13, color: 'var(--color-text)', outline: 'none', resize: 'vertical',
        fontFamily: 'inherit',
      }}
      onFocus={e => { e.target.style.borderColor = '#4f8ff7'; }}
      onBlur={e => { e.target.style.borderColor = 'var(--color-border)'; }}
    />
  );
}

function SaveBar({ onSave, saving, saved, error }) {
  return (
    <div style={{ marginTop: 18, display: 'flex', alignItems: 'center', gap: 10 }}>
      <button
        onClick={onSave}
        disabled={saving}
        style={{
          display: 'flex', alignItems: 'center', gap: 7,
          background: '#4f8ff7', color: '#fff', border: 'none',
          borderRadius: 8, padding: '9px 18px', fontSize: 13, fontWeight: 600,
          cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1,
          transition: 'opacity 0.15s',
        }}
      >
        {saving ? <><span style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.4)', borderTopColor: '#fff', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />Saving…</> : <><Save size={14} />Save</>}
      </button>
      {saved && !saving && (
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#34d399', fontWeight: 600 }}>
          <Check size={14} /> Saved
        </span>
      )}
      {error && (
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#f87171' }}>
          <AlertCircle size={13} /> {error}
        </span>
      )}
    </div>
  );
}

function PersonalTab({ profile, onSave }) {
  const [form, setForm] = useState({
    phone: profile.phone || '',
    email: profile.email || '',
    address: profile.address || '',
    dob: profile.dob || '',
    gender: profile.gender ? (profile.gender.charAt(0).toUpperCase() + profile.gender.slice(1)) : '',
    preferred_name: profile.preferred_name || '',
    emergency_contact: profile.emergency_contact || '',
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  const set = (key) => (val) => setForm(f => ({ ...f, [key]: val }));

  async function save() {
    setSaving(true); setSaved(false); setError('');
    try {
      const payload = { ...form, gender: form.gender ? form.gender.toLowerCase() : undefined };
      const r = await onSave(payload);
      if (r.success) { setSaved(true); setTimeout(() => setSaved(false), 3000); }
      else setError(r.detail || 'Save failed');
    } catch { setError('Network error'); }
    setSaving(false);
  }

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
        <Field label="Phone"><Input value={form.phone} onChange={set('phone')} placeholder="Mobile number" /></Field>
        <Field label="Email"><Input value={form.email} onChange={set('email')} placeholder="Personal email" type="email" /></Field>
        <Field label="Date of Birth"><Input value={form.dob} onChange={set('dob')} type="date" /></Field>
        <Field label="Gender"><Select value={form.gender} onChange={set('gender')} options={GENDERS} /></Field>
      </div>
      <Field label="Preferred Name"><Input value={form.preferred_name} onChange={set('preferred_name')} placeholder="Nickname / display name" /></Field>
      <Field label="Address"><Textarea value={form.address} onChange={set('address')} placeholder="Home address" /></Field>
      <Field label="Emergency Contact"><Input value={form.emergency_contact} onChange={set('emergency_contact')} placeholder="Name & phone (e.g. Parent: 9876543210)" /></Field>
      <SaveBar onSave={save} saving={saving} saved={saved} error={error} />
    </div>
  );
}

function MedicalTab({ profile, onSave }) {
  const [form, setForm] = useState({
    blood_group: profile.blood_group || '',
    height_cm: profile.height_cm || '',
    weight_kg: profile.weight_kg || '',
    medical_notes: profile.medical_notes || '',
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  const set = (key) => (val) => setForm(f => ({ ...f, [key]: val }));

  async function save() {
    setSaving(true); setSaved(false); setError('');
    try {
      const payload = {
        blood_group: form.blood_group || undefined,
        height_cm: form.height_cm ? Number(form.height_cm) : undefined,
        weight_kg: form.weight_kg ? Number(form.weight_kg) : undefined,
        medical_notes: form.medical_notes || undefined,
      };
      const r = await onSave(payload);
      if (r.success) { setSaved(true); setTimeout(() => setSaved(false), 3000); }
      else setError(r.detail || 'Save failed');
    } catch { setError('Network error'); }
    setSaving(false);
  }

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
        <Field label="Blood Group">
          <Select value={form.blood_group} onChange={set('blood_group')} options={BLOOD_GROUPS} />
        </Field>
        <Field label="Height (cm)">
          <Input value={form.height_cm} onChange={set('height_cm')} placeholder="e.g. 165" type="number" />
        </Field>
        <Field label="Weight (kg)">
          <Input value={form.weight_kg} onChange={set('weight_kg')} placeholder="e.g. 55" type="number" />
        </Field>
      </div>
      <Field label="Medical Notes / Allergies / Conditions">
        <Textarea value={form.medical_notes} onChange={set('medical_notes')} placeholder="Any known allergies, conditions, or medications..." />
      </Field>
      <SaveBar onSave={save} saving={saving} saved={saved} error={error} />
    </div>
  );
}

function GuardianCard({ guardian, onSave }) {
  const [form, setForm] = useState({
    name: guardian.name || '',
    phone: guardian.phone || '',
    whatsapp_phone: guardian.whatsapp_phone || '',
    email: guardian.email || '',
    occupation: guardian.occupation || '',
  });
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  const set = (key) => (val) => setForm(f => ({ ...f, [key]: val }));

  async function save() {
    setSaving(true); setSaved(false); setError('');
    try {
      const r = await onSave(guardian.id, form);
      if (r.success) { setSaved(true); setTimeout(() => setSaved(false), 3000); }
      else setError(r.detail || 'Save failed');
    } catch { setError('Network error'); }
    setSaving(false);
  }

  const rel = guardian.relation || 'Guardian';

  return (
    <div style={{ border: '1px solid var(--color-border)', borderRadius: 10, marginBottom: 12, overflow: 'hidden' }}>
      <div
        onClick={() => setOpen(o => !o)}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 14px', cursor: 'pointer', background: 'var(--color-surface-2)' }}
      >
        <div>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>{form.name || '—'}</span>
          <span style={{ fontSize: 11, color: 'var(--color-muted)', marginLeft: 8 }}>{rel}</span>
        </div>
        <span style={{ fontSize: 11, color: 'var(--color-muted)', transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>▶</span>
      </div>
      {open && (
        <div style={{ padding: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
            <Field label="Name"><Input value={form.name} onChange={set('name')} placeholder="Full name" /></Field>
            <Field label="Occupation"><Input value={form.occupation} onChange={set('occupation')} placeholder="e.g. Business" /></Field>
            <Field label="Phone"><Input value={form.phone} onChange={set('phone')} placeholder="Contact number" /></Field>
            <Field label="WhatsApp"><Input value={form.whatsapp_phone} onChange={set('whatsapp_phone')} placeholder="WhatsApp number" /></Field>
          </div>
          <Field label="Email"><Input value={form.email} onChange={set('email')} placeholder="Email address" type="email" /></Field>
          <SaveBar onSave={save} saving={saving} saved={saved} error={error} />
        </div>
      )}
    </div>
  );
}

function ParentsTab({ guardians, onSaveGuardian }) {
  if (!guardians || guardians.length === 0) {
    return <p style={{ fontSize: 13, color: 'var(--color-muted)', textAlign: 'center', padding: '24px 0' }}>No guardian records found.</p>;
  }
  return (
    <div>
      {guardians.map(g => (
        <GuardianCard key={g.id} guardian={g} onSave={onSaveGuardian} />
      ))}
    </div>
  );
}

export default function StudentProfileEditor({ isDark }) {
  const [profile, setProfile] = useState(null);
  const [activeTab, setActiveTab] = useState('personal');
  const [loading, setLoading] = useState(true);

  const vars = {
    '--color-text': isDark ? '#f5f5f5' : '#171717',
    '--color-muted': isDark ? '#888' : '#525252',
    '--color-border': isDark ? '#2e2e2e' : '#e5e5e5',
    '--color-surface': isDark ? '#1e1e1e' : '#fff',
    '--color-surface-2': isDark ? '#141414' : '#fafafa',
  };

  useEffect(() => {
    getMyStudentProfile().then(r => {
      if (r.success) setProfile(r.data);
    }).finally(() => setLoading(false));
  }, []);

  const saveProfile = useCallback((data) => updateMyStudentProfile(data), []);
  const saveGuardian = useCallback((gid, data) => updateMyGuardian(gid, data), []);

  if (loading) {
    return <p style={{ fontSize: 13, color: 'var(--color-muted)', textAlign: 'center', padding: '24px 0' }}>Loading profile…</p>;
  }
  if (!profile) {
    return <p style={{ fontSize: 13, color: '#f87171', textAlign: 'center', padding: '24px 0' }}>Could not load profile.</p>;
  }

  const cls = profile.class_info;
  const classLabel = cls ? `${cls.name}${cls.section ? ' – ' + cls.section : ''}` : '—';

  return (
    <div style={vars}>
      {/* Read-only summary row */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
        {[
          { label: 'Admission No', value: profile.admission_number },
          { label: 'Roll No', value: profile.roll_number },
          { label: 'Class', value: classLabel },
          { label: 'Status', value: profile.status || 'Active' },
        ].map(item => (
          <div key={item.label} style={{ flex: '1 1 100px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 8, padding: '8px 12px' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>{item.label}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>{item.value || '—'}</div>
          </div>
        ))}
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 18, borderBottom: '1px solid var(--color-border)', paddingBottom: 0 }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 14px', border: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: activeTab === tab.id ? 600 : 400,
              color: activeTab === tab.id ? '#4f8ff7' : 'var(--color-muted)',
              background: 'transparent',
              borderBottom: activeTab === tab.id ? '2px solid #4f8ff7' : '2px solid transparent',
              marginBottom: -1, transition: 'color 0.15s',
            }}
          >
            <tab.icon size={14} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'personal' && <PersonalTab profile={profile} onSave={saveProfile} />}
      {activeTab === 'medical' && <MedicalTab profile={profile} onSave={saveProfile} />}
      {activeTab === 'parents' && <ParentsTab guardians={profile.guardians} onSaveGuardian={saveGuardian} />}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
