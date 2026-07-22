import React, { useState, useEffect } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { X, Mail, Phone, Zap, User, Check, Lock } from 'lucide-react';
import { getMyTokenUsage, getMyStaffProfile, updateMyStaffProfile } from '../lib/api';
import StudentProfileEditor from './StudentProfileEditor';

const ROLE_COLORS = { owner: '#fb923c', admin: '#4f8ff7', teacher: '#34d399', student: '#a78bfa' };
const ROLE_LABELS = { owner: 'Owner', admin: 'Admin Staff', teacher: 'Teacher', student: 'Student' };

// Story 1.2's canonical sub-categories, as a person would say them.
const SUB_CATEGORY_LABELS = {
  owner: 'Owner', principal: 'Principal', management: 'Management',
  accountant: 'Accountant', receptionist: 'Receptionist', transport_head: 'Transport Head',
  it_tech: 'IT / Tech', maintenance: 'Maintenance', support_staff: 'Support Staff',
  class_teacher: 'Class Teacher', subject_teacher: 'Subject Teacher',
  hod: 'Head of Department', coordinator: 'Coordinator', kg_incharge: 'KG In-charge',
};

// The three fields a person may correct on their own record. The server holds
// the same allow-list — this one only decides what gets a text box.
const SELF_SERVICE_FIELDS = [
  { key: 'name', label: 'Name', icon: User, type: 'text', placeholder: 'Your full name' },
  { key: 'phone', label: 'Phone', icon: Phone, type: 'tel', placeholder: 'Mobile number' },
  { key: 'email', label: 'Email', icon: Mail, type: 'email', placeholder: 'you@example.com' },
];

const fieldStyle = {
  width: '100%',
  marginTop: 5,
  background: 'var(--c-bg)',
  border: '1px solid var(--c-border)',
  borderRadius: 8,
  padding: '10px 12px',
  color: 'var(--c-text)',
  fontSize: 14,          // UX-DR7: at/above the 16px-adjacent comfortable range and
  outline: 'none',       // well clear of the 12–13px the platform used to render
};

function TokenCard({ isDark, currentUser }) {
  const [tokenUsage, setTokenUsage] = useState(null);
  const border  = isDark ? '#2e2e2e' : '#e5e5e5';
  const text    = isDark ? '#f5f5f5' : '#171717';
  const muted   = isDark ? '#888'    : '#525252';
  const cardBg  = isDark ? '#141414' : '#fafafa';

  useEffect(() => {
    getMyTokenUsage().then(r => { if (r.success) setTokenUsage(r.data); }).catch(() => {});
  }, [currentUser.id]);

  const isUnlimited = tokenUsage?.unlimited === true || tokenUsage?.role_limit == null;
  const limit    = isUnlimited ? 0 : (tokenUsage?.role_limit || 0);
  const used     = tokenUsage?.total_used || 0;
  const usagePct = (!isUnlimited && limit > 0) ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const usageColor = usagePct >= 90 ? '#ef4444' : usagePct >= 70 ? '#f59e0b' : '#10b981';

  function fmt(n) {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`;
    return `${n}`;
  }

  return (
    <div style={{ background: cardBg, borderRadius: 14, border: `1px solid ${border}`, padding: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <Zap size={15} color={usageColor} />
        <span style={{ fontSize: 13, fontWeight: 600, color: text }}>AI Token Usage</span>
        {isUnlimited
          ? <span style={{ marginLeft: 'auto', fontSize: 12, fontWeight: 700, color: '#10b981' }}>∞ Unlimited</span>
          : <span style={{ marginLeft: 'auto', fontSize: 12, fontWeight: 700, color: usageColor }}>{usagePct}%</span>
        }
      </div>
      {!isUnlimited && (
        <div style={{ background: isDark ? '#2e2e2e' : '#e5e5e5', borderRadius: 6, height: 6, overflow: 'hidden', marginBottom: 8 }}>
          <div style={{ height: '100%', width: `${usagePct}%`, background: usageColor, borderRadius: 6, transition: 'width 0.5s ease' }} />
        </div>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: muted }}>
        <span>{isUnlimited ? `${fmt(used)} used` : `${fmt(used)} / ${fmt(limit)}`}</span>
        {!isUnlimited && usagePct >= 80 && <span style={{ color: '#4f8ff7', fontWeight: 600 }}>⚡ Top up</span>}
      </div>
      {tokenUsage == null && <p style={{ fontSize: 11, color: muted, marginTop: 4 }}>Loading usage…</p>}
    </div>
  );
}

// Story 1.3 — a person maintains their own contact details here. Authority
// (role, sub-category, school, token allowance) is shown but never editable:
// changing what someone may DO happens on the staff screen, in one place, where
// Stories 1.1 and 1.2 police it.
function SelfServiceProfile({ currentUser }) {
  const { applyProfileUpdate } = useUser();
  const [form, setForm] = useState({ name: currentUser.name || '', phone: currentUser.phone || '', email: '' });
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getMyStaffProfile()
      .then((res) => {
        if (cancelled) return;
        if (res.success && res.data) {
          setForm({
            name: res.data.name || currentUser.name || '',
            phone: res.data.phone || '',
            email: res.data.email || '',
          });
        }
        setLoaded(true);
      })
      .catch(() => { if (!cancelled) setLoaded(true); });
    return () => { cancelled = true; };
  }, [currentUser.id, currentUser.name]);

  const setField = (key) => (event) => {
    const { value } = event.target;
    setForm((current) => ({ ...current, [key]: value }));
    setError('');
    setSaved(false);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.name.trim()) { setError('Name cannot be empty'); return; }
    setSaving(true);
    try {
      const res = await updateMyStaffProfile({
        name: form.name.trim(), phone: form.phone.trim(), email: form.email.trim(),
      });
      if (res.success) {
        applyProfileUpdate(res.data);
        setSaved(true);
      } else {
        setError(res.detail || 'Could not save your details');
      }
    } catch (err) {
      setError(err.message || 'Network error');
    }
    setSaving(false);
  };

  const readOnlyRows = [
    { label: 'Role', value: ROLE_LABELS[currentUser.role] || currentUser.role },
    ...(currentUser.sub_category
      ? [{ label: 'Job', value: SUB_CATEGORY_LABELS[currentUser.sub_category] || currentUser.sub_category }]
      : []),
    { label: 'School', value: 'The Aaryans' },
  ];

  return (
    <form onSubmit={submit} data-testid="profile-self-service">
      {SELF_SERVICE_FIELDS.map((field) => (
        <label
          key={field.key}
          htmlFor={`profile-${field.key}`}
          style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--c-faint)', marginBottom: 14 }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <field.icon size={13} /> {field.label}
          </span>
          <input
            id={`profile-${field.key}`}
            className="focus-ring"
            data-testid={`profile-${field.key}-input`}
            type={field.type}
            value={form[field.key]}
            placeholder={field.placeholder}
            disabled={!loaded}
            onChange={setField(field.key)}
            style={fieldStyle}
          />
        </label>
      ))}

      {/* Shown, never editable — see the comment above this component. */}
      <div
        data-testid="profile-readonly"
        style={{
          background: 'var(--c-bg)', border: '1px solid var(--c-border)',
          borderRadius: 10, padding: '4px 14px', marginBottom: 16,
        }}
      >
        {readOnlyRows.map((row, index) => (
          <div
            key={row.label}
            style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0',
              borderBottom: index === readOnlyRows.length - 1 ? 'none' : '1px solid var(--c-border)',
            }}
          >
            <Lock size={12} style={{ color: 'var(--c-faint)', flexShrink: 0 }} />
            <span style={{ fontSize: 12, color: 'var(--c-faint)', minWidth: 58 }}>{row.label}</span>
            <span style={{ fontSize: 13, color: 'var(--c-text)', fontWeight: 500 }}>{row.value}</span>
          </div>
        ))}
      </div>

      {error && (
        <div data-testid="profile-error" style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 12 }}>
          {error}
        </div>
      )}
      {saved && !error && (
        <div data-testid="profile-saved" style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#10b981', fontSize: 12, marginBottom: 12 }}>
          <Check size={13} /> Your details are saved
        </div>
      )}

      <button
        type="submit"
        className="focus-ring"
        data-testid="profile-save"
        disabled={saving || !loaded}
        style={{
          width: '100%', minHeight: 42, border: 'none', borderRadius: 10,
          background: 'var(--tool-hex-4f8ff7)', color: '#fff',
          fontSize: 14, fontWeight: 650, cursor: saving || !loaded ? 'not-allowed' : 'pointer',
          opacity: saving || !loaded ? 0.65 : 1,
        }}
      >
        {saving ? 'Saving…' : 'Save my details'}
      </button>
    </form>
  );
}

export default function ProfileModal({ onClose }) {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const isStudent = currentUser.role === 'student';

  const bg     = isDark ? '#1e1e1e' : '#fff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text   = isDark ? '#f5f5f5' : '#171717';
  const muted  = isDark ? '#888'    : '#525252';

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 300 }}>
      <div
        className="fade-in-scale"
        style={{
          background: bg,
          border: `1px solid ${border}`,
          borderRadius: 20,
          width: isStudent ? 580 : 420,
          maxWidth: '95vw',
          maxHeight: '90vh',
          overflowY: 'auto',
          boxShadow: 'var(--shadow-xl)',
          /* no padding for students — hero owns the top */
          padding: isStudent ? 0 : 32,
        }}
      >
        {isStudent ? (
          /* Student full-featured profile editor */
          <StudentProfileEditor isDark={isDark} currentUser={currentUser} onClose={onClose} />
        ) : (
          /* Staff / teacher / owner: maintain your own contact details (Story 1.3) */
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
              <h2 style={{ fontSize: 20, fontWeight: 700, color: text, letterSpacing: '-0.02em' }}>Profile</h2>
              <button
                onClick={onClose}
                className="focus-ring"
                data-testid="profile-close"
                aria-label="Close profile"
                style={{ background: isDark ? '#252525' : '#f5f5f5', border: 'none', color: muted, cursor: 'pointer', borderRadius: 8, padding: 6 }}
                onMouseEnter={e => e.currentTarget.style.background = isDark ? '#333' : '#e5e5e5'}
                onMouseLeave={e => e.currentTarget.style.background = isDark ? '#252525' : '#f5f5f5'}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ textAlign: 'center', marginBottom: 28 }}>
              <div style={{ width: 72, height: 72, borderRadius: 18, background: ROLE_COLORS[currentUser.role], display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, fontWeight: 700, color: '#fff', margin: '0 auto 14px' }}>
                {currentUser.initials}
              </div>
              <h3 style={{ fontSize: 20, fontWeight: 600, color: text, marginBottom: 6, letterSpacing: '-0.02em' }}>{currentUser.name}</h3>
              <span style={{ fontSize: 12, fontWeight: 600, color: ROLE_COLORS[currentUser.role], background: `${ROLE_COLORS[currentUser.role]}12`, padding: '4px 14px', borderRadius: 20 }}>
                {ROLE_LABELS[currentUser.role]}
              </span>
            </div>

            <SelfServiceProfile currentUser={currentUser} />

            <div style={{ marginTop: 20 }}>
              <TokenCard isDark={isDark} currentUser={currentUser} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
