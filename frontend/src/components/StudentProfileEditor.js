import React, { useState, useEffect, useCallback } from 'react';
import {
  X, Phone, Mail, MapPin, User, Calendar, Heart, Users,
  Droplets, Ruler, Weight, FileText, Briefcase, MessageSquare,
  CheckCircle2, AlertCircle, Pencil, Lock, GraduationCap,
} from 'lucide-react';
import { getMyStudentProfile, updateMyStudentProfile, updateMyGuardian } from '../lib/api';

const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'];
const GENDERS = ['Male', 'Female', 'Other'];
const ACCENT = '#a78bfa';

/* ─── tiny primitives ──────────────────────────────────────────────────────── */

function useThemeVars(isDark) {
  return {
    bg: isDark ? '#181818' : '#ffffff',
    bgCard: isDark ? '#212121' : '#f8f8f8',
    bgInput: isDark ? '#272727' : '#ffffff',
    bgInputFocus: isDark ? '#2c2c2c' : '#fafafa',
    border: isDark ? '#303030' : '#e4e4e4',
    borderFocus: ACCENT,
    text: isDark ? '#f0f0f0' : '#181818',
    textSub: isDark ? '#a0a0a0' : '#6b7280',
    textMuted: isDark ? '#666666' : '#9ca3af',
    heroBg: isDark
      ? 'linear-gradient(155deg,rgba(167,139,250,0.22) 0%,rgba(24,24,24,0.0) 70%)'
      : 'linear-gradient(155deg,rgba(167,139,250,0.14) 0%,rgba(255,255,255,0.0) 70%)',
    shadow: isDark ? '0 0 0 3px rgba(167,139,250,0.18)' : '0 0 0 3px rgba(167,139,250,0.14)',
  };
}

function FormInput({ v, label, placeholder, type = 'text', icon: Icon, onChange, readOnly, isDark }) {
  const t = useThemeVars(isDark);
  const [focused, setFocused] = useState(false);
  return (
    <div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10.5, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: t.textMuted, marginBottom: 6 }}>
        {Icon && <Icon size={10} />}{label}
        {readOnly && <Lock size={9} style={{ marginLeft: 2, opacity: 0.5 }} />}
      </label>
      <div style={{ position: 'relative' }}>
        {Icon && (
          <Icon size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: focused ? ACCENT : t.textMuted, transition: 'color 0.15s', pointerEvents: 'none' }} />
        )}
        <input
          type={type}
          value={v || ''}
          onChange={e => onChange && onChange(e.target.value)}
          placeholder={placeholder}
          readOnly={readOnly}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{
            width: '100%', boxSizing: 'border-box',
            background: readOnly ? t.bgCard : (focused ? t.bgInputFocus : t.bgInput),
            border: `1.5px solid ${focused ? t.borderFocus : t.border}`,
            borderRadius: 10,
            padding: Icon ? '10px 12px 10px 34px' : '10px 12px',
            fontSize: 13, color: readOnly ? t.textSub : t.text,
            outline: 'none', cursor: readOnly ? 'default' : 'text',
            boxShadow: focused ? t.shadow : 'none',
            transition: 'border-color 0.15s, box-shadow 0.15s, background 0.15s',
            fontFamily: 'inherit',
          }}
        />
      </div>
    </div>
  );
}

function FormSelect({ v, label, options, icon: Icon, onChange, isDark }) {
  const t = useThemeVars(isDark);
  const [focused, setFocused] = useState(false);
  return (
    <div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10.5, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: t.textMuted, marginBottom: 6 }}>
        {Icon && <Icon size={10} />}{label}
      </label>
      <select
        value={v || ''}
        onChange={e => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          width: '100%', boxSizing: 'border-box',
          background: focused ? t.bgInputFocus : t.bgInput,
          border: `1.5px solid ${focused ? t.borderFocus : t.border}`,
          borderRadius: 10, padding: '10px 12px',
          fontSize: 13, color: v ? t.text : t.textMuted,
          outline: 'none', fontFamily: 'inherit',
          boxShadow: focused ? t.shadow : 'none',
          transition: 'border-color 0.15s, box-shadow 0.15s',
          cursor: 'pointer',
        }}
      >
        <option value="">— Select —</option>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}

function FormTextarea({ v, label, placeholder, icon: Icon, onChange, isDark }) {
  const t = useThemeVars(isDark);
  const [focused, setFocused] = useState(false);
  return (
    <div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10.5, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: t.textMuted, marginBottom: 6 }}>
        {Icon && <Icon size={10} />}{label}
      </label>
      <textarea
        value={v || ''}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        rows={3}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          width: '100%', boxSizing: 'border-box',
          background: focused ? t.bgInputFocus : t.bgInput,
          border: `1.5px solid ${focused ? t.borderFocus : t.border}`,
          borderRadius: 10, padding: '10px 12px',
          fontSize: 13, color: t.text, outline: 'none',
          resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.55,
          boxShadow: focused ? t.shadow : 'none',
          transition: 'border-color 0.15s, box-shadow 0.15s',
          minHeight: 80,
        }}
      />
    </div>
  );
}

function SectionHeading({ label, isDark }) {
  const t = useThemeVars(isDark);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '22px 0 14px' }}>
      <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: t.textMuted }}>{label}</span>
      <div style={{ flex: 1, height: 1, background: `linear-gradient(90deg,${t.border},transparent)` }} />
    </div>
  );
}

function SaveButton({ onSave, saving, saved, error, isDark }) {
  const t = useThemeVars(isDark);
  return (
    <div style={{ marginTop: 24 }}>
      <button
        onClick={onSave}
        disabled={saving || saved}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          padding: '12px 20px', border: 'none', borderRadius: 12,
          fontSize: 14, fontWeight: 600, cursor: (saving || saved) ? 'default' : 'pointer',
          background: saved ? '#1a3a2a' : `linear-gradient(135deg, #a78bfa 0%, #818cf8 100%)`,
          color: saved ? '#34d399' : '#fff',
          boxShadow: saved ? 'none' : '0 4px 16px rgba(167,139,250,0.35)',
          transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
          transform: saving ? 'scale(0.99)' : 'scale(1)',
          opacity: saving ? 0.85 : 1,
        }}
      >
        {saving ? (
          <><span style={{ width: 16, height: 16, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', display: 'inline-block', animation: 'spe-spin 0.7s linear infinite' }} />Saving changes…</>
        ) : saved ? (
          <><CheckCircle2 size={16} />Changes saved</>
        ) : (
          'Save Changes'
        )}
      </button>
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, padding: '9px 12px', background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.2)', borderRadius: 8 }}>
          <AlertCircle size={14} color="#f87171" />
          <span style={{ fontSize: 12, color: '#f87171' }}>{error}</span>
        </div>
      )}
    </div>
  );
}

/* ─── tab panels ────────────────────────────────────────────────────────────── */

function PersonalTab({ profile, onSave, isDark }) {
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
  const set = k => v => setForm(f => ({ ...f, [k]: v }));

  async function save() {
    setSaving(true); setSaved(false); setError('');
    try {
      const r = await onSave({ ...form, gender: form.gender ? form.gender.toLowerCase() : undefined });
      if (r.success) { setSaved(true); setTimeout(() => setSaved(false), 3000); }
      else setError(r.detail || 'Could not save. Please try again.');
    } catch { setError('Network error. Check your connection.'); }
    setSaving(false);
  }

  return (
    <div>
      <SectionHeading label="Contact" isDark={isDark} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <FormInput v={form.phone} label="Phone" placeholder="Mobile number" icon={Phone} onChange={set('phone')} isDark={isDark} />
        <FormInput v={form.email} label="Email" placeholder="Personal email" icon={Mail} type="email" onChange={set('email')} isDark={isDark} />
      </div>

      <SectionHeading label="Personal Details" isDark={isDark} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
        <FormInput v={form.dob} label="Date of Birth" icon={Calendar} type="date" onChange={set('dob')} isDark={isDark} />
        <FormSelect v={form.gender} label="Gender" icon={User} options={GENDERS} onChange={set('gender')} isDark={isDark} />
      </div>
      <FormInput v={form.preferred_name} label="Preferred Name" placeholder="Nickname or display name" icon={User} onChange={set('preferred_name')} isDark={isDark} />

      <SectionHeading label="Address & Emergency" isDark={isDark} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <FormTextarea v={form.address} label="Home Address" placeholder="Full residential address" icon={MapPin} onChange={set('address')} isDark={isDark} />
        <FormInput v={form.emergency_contact} label="Emergency Contact" placeholder="e.g. Father – 9876543210" icon={Phone} onChange={set('emergency_contact')} isDark={isDark} />
      </div>
      <SaveButton onSave={save} saving={saving} saved={saved} error={error} isDark={isDark} />
    </div>
  );
}

function MedicalTab({ profile, onSave, isDark }) {
  const t = useThemeVars(isDark);
  const [form, setForm] = useState({
    blood_group: profile.blood_group || '',
    height_cm: profile.height_cm || '',
    weight_kg: profile.weight_kg || '',
    medical_notes: profile.medical_notes || '',
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const set = k => v => setForm(f => ({ ...f, [k]: v }));

  const bmi = form.height_cm && form.weight_kg
    ? (Number(form.weight_kg) / Math.pow(Number(form.height_cm) / 100, 2)).toFixed(1)
    : null;
  const bmiLabel = bmi ? (bmi < 18.5 ? 'Underweight' : bmi < 25 ? 'Normal' : bmi < 30 ? 'Overweight' : 'Obese') : null;
  const bmiColor = bmi ? (bmi < 18.5 ? '#fbbf24' : bmi < 25 ? '#34d399' : bmi < 30 ? '#fb923c' : '#f87171') : null;

  async function save() {
    setSaving(true); setSaved(false); setError('');
    try {
      const r = await onSave({
        blood_group: form.blood_group || undefined,
        height_cm: form.height_cm ? Number(form.height_cm) : undefined,
        weight_kg: form.weight_kg ? Number(form.weight_kg) : undefined,
        medical_notes: form.medical_notes || undefined,
      });
      if (r.success) { setSaved(true); setTimeout(() => setSaved(false), 3000); }
      else setError(r.detail || 'Could not save. Please try again.');
    } catch { setError('Network error.'); }
    setSaving(false);
  }

  return (
    <div>
      <SectionHeading label="Vitals" isDark={isDark} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        <FormSelect v={form.blood_group} label="Blood Group" icon={Droplets} options={BLOOD_GROUPS} onChange={set('blood_group')} isDark={isDark} />
        <FormInput v={form.height_cm} label="Height (cm)" placeholder="165" icon={Ruler} type="number" onChange={set('height_cm')} isDark={isDark} />
        <FormInput v={form.weight_kg} label="Weight (kg)" placeholder="55" icon={Weight} type="number" onChange={set('weight_kg')} isDark={isDark} />
      </div>

      {bmi && (
        <div style={{ marginTop: 12, padding: '10px 14px', background: `${bmiColor}14`, border: `1px solid ${bmiColor}30`, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: t.textSub, fontWeight: 500 }}>Body Mass Index (BMI)</span>
          <span style={{ fontSize: 14, fontWeight: 700, color: bmiColor }}>{bmi} <span style={{ fontSize: 11, fontWeight: 500 }}>— {bmiLabel}</span></span>
        </div>
      )}

      <SectionHeading label="Medical History" isDark={isDark} />
      <FormTextarea v={form.medical_notes} label="Conditions, Allergies & Medications" placeholder="Note any known conditions, allergies, or regular medications here…" icon={FileText} onChange={set('medical_notes')} isDark={isDark} />
      <SaveButton onSave={save} saving={saving} saved={saved} error={error} isDark={isDark} />
    </div>
  );
}

function GuardianCard({ guardian, onSave, isDark }) {
  const t = useThemeVars(isDark);
  const isMother = guardian.relation?.toLowerCase() === 'mother';
  const relColor = isMother ? '#f472b6' : '#60a5fa';
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    name: guardian.name || '',
    phone: guardian.phone || '',
    whatsapp_phone: guardian.whatsapp_phone || '',
    email: guardian.email || '',
    occupation: guardian.occupation || '',
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const set = k => v => setForm(f => ({ ...f, [k]: v }));

  async function save() {
    setSaving(true); setSaved(false); setError('');
    try {
      const r = await onSave(guardian.id, form);
      if (r.success) { setSaved(true); setTimeout(() => { setSaved(false); setEditing(false); }, 2000); }
      else setError(r.detail || 'Could not save.');
    } catch { setError('Network error.'); }
    setSaving(false);
  }

  return (
    <div style={{ background: t.bgCard, border: `1.5px solid ${t.border}`, borderRadius: 14, overflow: 'hidden', marginBottom: 12, transition: 'border-color 0.15s' }}>
      {/* Card header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 16px' }}>
        <div style={{ width: 44, height: 44, borderRadius: 12, background: `${relColor}20`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <User size={20} color={relColor} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: t.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {form.name || '—'}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: relColor, background: `${relColor}18`, padding: '2px 8px', borderRadius: 20 }}>
              {guardian.relation || 'Guardian'}
            </span>
            {form.phone && <span style={{ fontSize: 11, color: t.textMuted }}>{form.phone}</span>}
          </div>
        </div>
        <button
          onClick={() => { setEditing(e => !e); setError(''); }}
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '6px 12px', border: `1px solid ${editing ? ACCENT : t.border}`,
            borderRadius: 8, background: editing ? `${ACCENT}18` : 'transparent',
            color: editing ? ACCENT : t.textSub, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            transition: 'all 0.15s',
          }}
        >
          <Pencil size={12} />
          {editing ? 'Cancel' : 'Edit'}
        </button>
      </div>

      {/* Inline edit form */}
      {editing && (
        <div style={{ borderTop: `1px solid ${t.border}`, padding: '16px 16px 14px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <FormInput v={form.name} label="Full Name" placeholder="Guardian's name" icon={User} onChange={set('name')} isDark={isDark} />
            <FormInput v={form.occupation} label="Occupation" placeholder="e.g. Business" icon={Briefcase} onChange={set('occupation')} isDark={isDark} />
            <FormInput v={form.phone} label="Phone" placeholder="Contact number" icon={Phone} onChange={set('phone')} isDark={isDark} />
            <FormInput v={form.whatsapp_phone} label="WhatsApp" placeholder="WhatsApp number" icon={MessageSquare} onChange={set('whatsapp_phone')} isDark={isDark} />
          </div>
          <FormInput v={form.email} label="Email" placeholder="Email address" icon={Mail} type="email" onChange={set('email')} isDark={isDark} />
          <SaveButton onSave={save} saving={saving} saved={saved} error={error} isDark={isDark} />
        </div>
      )}
    </div>
  );
}

function ParentsTab({ guardians, onSaveGuardian, isDark }) {
  const t = useThemeVars(isDark);
  if (!guardians || guardians.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 20px' }}>
        <Users size={32} color={t.textMuted} style={{ margin: '0 auto 12px' }} />
        <p style={{ fontSize: 14, color: t.textMuted }}>No guardian records found.</p>
      </div>
    );
  }
  return (
    <div style={{ paddingTop: 4 }}>
      {guardians.map(g => (
        <GuardianCard key={g.id} guardian={g} onSave={onSaveGuardian} isDark={isDark} />
      ))}
    </div>
  );
}

/* ─── main export ───────────────────────────────────────────────────────────── */

const TABS = [
  { id: 'personal', label: 'Personal', icon: User },
  { id: 'medical',  label: 'Medical',  icon: Heart },
  { id: 'parents',  label: 'Parents',  icon: Users },
];

export default function StudentProfileEditor({ isDark, currentUser, onClose }) {
  const t = useThemeVars(isDark);
  const [profile, setProfile] = useState(null);
  const [activeTab, setActiveTab] = useState('personal');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMyStudentProfile().then(r => { if (r.success) setProfile(r.data); }).finally(() => setLoading(false));
  }, []);

  const saveProfile = useCallback(data => updateMyStudentProfile(data), []);
  const saveGuardian = useCallback((gid, data) => updateMyGuardian(gid, data), []);

  const cls = profile?.class_info;
  const classLabel = cls ? `${cls.name}${cls.section ? ' · ' + cls.section : ''}` : null;

  return (
    <>
      <style>{`
        @keyframes spe-spin { to { transform: rotate(360deg); } }
        @keyframes spe-fadein { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        .spe-tab-btn:hover { opacity: 1 !important; }
      `}</style>

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <div style={{ position: 'relative', background: t.heroBg, padding: '32px 28px 24px', borderRadius: '20px 20px 0 0', textAlign: 'center' }}>
        <button
          onClick={onClose}
          style={{ position: 'absolute', top: 16, right: 16, width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)', border: 'none', borderRadius: 8, color: t.textSub, cursor: 'pointer', transition: 'background 0.15s' }}
          onMouseEnter={e => e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'}
          onMouseLeave={e => e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}
        >
          <X size={15} />
        </button>

        {/* Avatar */}
        <div style={{ width: 76, height: 76, borderRadius: '50%', background: `linear-gradient(135deg,#a78bfa,#818cf8)`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, fontWeight: 800, color: '#fff', margin: '0 auto 14px', boxShadow: '0 0 0 4px rgba(167,139,250,0.2), 0 8px 24px rgba(167,139,250,0.3)', letterSpacing: '-0.02em' }}>
          {currentUser?.initials || '?'}
        </div>

        <h2 style={{ fontSize: 20, fontWeight: 700, color: t.text, marginBottom: 6, letterSpacing: '-0.02em' }}>
          {currentUser?.name || 'Student'}
        </h2>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: ACCENT, background: `${ACCENT}18`, padding: '3px 12px', borderRadius: 20 }}>
            Student
          </span>
          {classLabel && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 600, color: t.textSub, background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)', padding: '3px 10px', borderRadius: 20 }}>
              <GraduationCap size={11} /> {classLabel}
            </span>
          )}
        </div>
      </div>

      {/* ── Stat strip ─────────────────────────────────────────────────── */}
      <div style={{ padding: '0 20px', margin: '0', background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)', borderTop: `1px solid ${t.border}`, borderBottom: `1px solid ${t.border}` }}>
        {loading ? (
          <div style={{ padding: '14px 0', textAlign: 'center' }}>
            <span style={{ fontSize: 12, color: t.textMuted }}>Loading…</span>
          </div>
        ) : profile ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 0 }}>
            {[
              { label: 'Admission', value: profile.admission_number },
              { label: 'Roll No',   value: profile.roll_number },
              { label: 'Class',     value: classLabel },
              { label: 'Status',    value: profile.status ? profile.status.charAt(0).toUpperCase() + profile.status.slice(1) : 'Active' },
            ].map((item, i) => (
              <div key={item.label} style={{ padding: '12px 0', textAlign: 'center', borderRight: i < 3 ? `1px solid ${t.border}` : 'none' }}>
                <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: t.textMuted, marginBottom: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 3 }}>
                  <Lock size={8} />{item.label}
                </div>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: t.text }}>{item.value || '—'}</div>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {/* ── Tabs & content ─────────────────────────────────────────────── */}
      <div style={{ padding: '0 20px 24px' }}>
        {/* Tab bar */}
        <div style={{ display: 'flex', gap: 4, padding: '16px 0 0' }}>
          {TABS.map(tab => {
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                className="spe-tab-btn"
                onClick={() => setActiveTab(tab.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px',
                  border: 'none', borderRadius: 10, cursor: 'pointer', fontSize: 13, fontWeight: active ? 600 : 500,
                  background: active ? (isDark ? '#2c2c2c' : '#fff') : 'transparent',
                  color: active ? t.text : t.textMuted,
                  boxShadow: active ? (isDark ? '0 1px 6px rgba(0,0,0,0.4)' : '0 1px 6px rgba(0,0,0,0.08)') : 'none',
                  transition: 'all 0.15s cubic-bezier(0.4,0,0.2,1)',
                  opacity: active ? 1 : 0.7,
                }}
              >
                <tab.icon size={14} color={active ? ACCENT : 'currentColor'} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        {!profile && !loading && (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <AlertCircle size={28} color="#f87171" style={{ margin: '0 auto 10px' }} />
            <p style={{ fontSize: 13, color: '#f87171' }}>Could not load profile data.</p>
          </div>
        )}

        {profile && (
          <div key={activeTab} style={{ animation: 'spe-fadein 0.18s ease' }}>
            {activeTab === 'personal' && <PersonalTab profile={profile} onSave={saveProfile} isDark={isDark} />}
            {activeTab === 'medical'  && <MedicalTab  profile={profile} onSave={saveProfile} isDark={isDark} />}
            {activeTab === 'parents'  && <ParentsTab  guardians={profile.guardians} onSaveGuardian={saveGuardian} isDark={isDark} />}
          </div>
        )}
      </div>
    </>
  );
}
