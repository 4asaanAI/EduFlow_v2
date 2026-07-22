import React, { useState, useEffect } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { X, Mail, Phone, Zap, User, Shield, Lock, Building2, Clock, Send } from 'lucide-react';
import {
  getMyTokenUsage, getMyStaffProfile,
  requestMyProfileChange, getMyProfileChangeRequests,
} from '../lib/api';
import StudentProfileEditor from './StudentProfileEditor';

// The school's city. Single literal, so correcting it is a one-line change
// rather than a hunt — it was wrong ("Lucknow") in four separate places.
const SCHOOL_CITY = 'Joya, Amroha';

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


function TokenCard({ isDark, currentUser }) {
  const [tokenUsage, setTokenUsage] = useState(null);
  const border  = 'var(--color-border)';
  const text    = 'var(--color-text-primary)';
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
        <div style={{ background: 'var(--color-border)', borderRadius: 6, height: 6, overflow: 'hidden', marginBottom: 8 }}>
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

// Story 1.3 as revised by the owner, 2026-07-22 — your own details are shown
// but NOT editable here. Changing your own name or phone is itself a way to
// misuse an account, so a correction has to be approved by an administrator.
// The request-and-approve flow is planned (Epic 8); until it exists, the honest
// thing is to show the details, say plainly who can change them, and offer no
// control that does nothing.
function OwnProfile({ currentUser }) {
  const [profile, setProfile] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getMyStaffProfile()
      .then((res) => { if (!cancelled) { if (res.success) setProfile(res.data); setLoaded(true); } })
      .catch(() => { if (!cancelled) setLoaded(true); });
    return () => { cancelled = true; };
  }, [currentUser.id]);

  // Fall back to the signed-in session when there is no staff record behind the
  // account (the Owner's account, for instance, need not be a staff member).
  const value = (key, fallback) => {
    if (!loaded) return '…';
    return (profile && profile[key]) || fallback || 'Not recorded';
  };

  const rows = [
    { key: 'name', label: 'Name', icon: User, value: value('name', currentUser.name) },
    { key: 'phone', label: 'Phone', icon: Phone, value: value('phone', currentUser.phone) },
    { key: 'email', label: 'Email', icon: Mail, value: value('email', null) },
    { key: 'role', label: 'Role', icon: Shield, value: ROLE_LABELS[currentUser.role] || currentUser.role },
    ...(currentUser.sub_category ? [{
      key: 'job', label: 'Job', icon: Shield,
      value: SUB_CATEGORY_LABELS[currentUser.sub_category] || currentUser.sub_category,
    }] : []),
    { key: 'school', label: 'School', icon: Building2, value: `The Aaryans, ${SCHOOL_CITY}` },
  ];

  return (
    <div data-testid="profile-own-details">
      <div style={{
        background: 'var(--c-bg)', border: '1px solid var(--c-border)',
        borderRadius: 10, padding: '4px 14px', marginBottom: 14,
      }}>
        {rows.map((row, index) => (
          <div
            key={row.key}
            data-testid={`profile-${row.key}`}
            style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '11px 0',
              borderBottom: index === rows.length - 1 ? 'none' : '1px solid var(--c-border)',
            }}
          >
            <row.icon size={13} style={{ color: 'var(--c-faint)', flexShrink: 0 }} />
            <span style={{ fontSize: 12, color: 'var(--c-faint)', minWidth: 52 }}>{row.label}</span>
            <span style={{ fontSize: 14, color: 'var(--c-text)', fontWeight: 500, wordBreak: 'break-word' }}>
              {row.value}
            </span>
          </div>
        ))}
      </div>

      <RequestACorrection
        currentValues={{
          name: (profile && profile.name) || currentUser.name || '',
          phone: (profile && profile.phone) || '',
          email: (profile && profile.email) || '',
        }}
        hasStaffRecord={Boolean(profile)}
      />
    </div>
  );
}

// Epic 8 — ask for a correction. This form never changes anything on its own;
// it records the ask, and the Owner or Principal decides.
function RequestACorrection({ currentValues, hasStaffRecord }) {
  const [pending, setPending] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(currentValues);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { setForm(currentValues); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [currentValues.name, currentValues.phone, currentValues.email]);

  useEffect(() => {
    let cancelled = false;
    getMyProfileChangeRequests()
      .then((res) => {
        if (cancelled || !res.success) return;
        setPending((res.data || []).find((r) => r.status === 'pending') || null);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    // Send only what the person actually altered, so the reviewer sees one
    // clear change rather than three fields of which two are identical.
    const changed = {};
    ['name', 'phone', 'email'].forEach((field) => {
      const next = (form[field] || '').trim();
      if (next !== (currentValues[field] || '').trim()) changed[field] = next;
    });
    if (!Object.keys(changed).length) { setError('Nothing has been changed yet'); return; }
    setSending(true);
    try {
      const res = await requestMyProfileChange(changed);
      if (res.success) { setPending(res.data); setOpen(false); }
      else setError(res.detail || 'Could not send your request');
    } catch (err) {
      setError(err.message || 'Network error');
    }
    setSending(false);
  };

  if (!hasStaffRecord) {
    return (
      <p data-testid="profile-readonly-note" style={noteStyle}>
        <Lock size={12} style={{ flexShrink: 0, marginTop: 2 }} />
        These details are maintained by the Owner and the Principal.
      </p>
    );
  }

  if (pending) {
    return (
      <div data-testid="profile-request-pending" style={{
        display: 'flex', alignItems: 'flex-start', gap: 8,
        background: 'var(--c-bg)', border: '1px solid var(--c-border)',
        borderRadius: 10, padding: 12,
      }}>
        <Clock size={13} style={{ color: '#f59e0b', flexShrink: 0, marginTop: 2 }} />
        <div style={{ fontSize: 12, color: 'var(--c-faint)', lineHeight: 1.55 }}>
          Waiting for approval —{' '}
          <span style={{ color: 'var(--c-text)', fontWeight: 600 }}>
            {Object.entries(pending.requested || {})
              .map(([field, value]) => `${field}: ${value}`).join(', ')}
          </span>
          <br />
          The Owner or the Principal will approve it. You can ask again once it is settled.
        </div>
      </div>
    );
  }

  if (!open) {
    return (
      <>
        <p data-testid="profile-readonly-note" style={noteStyle}>
          <Lock size={12} style={{ flexShrink: 0, marginTop: 2 }} />
          You cannot change these yourself. Ask and the Owner or the Principal will approve it.
        </p>
        <button
          type="button"
          className="focus-ring"
          data-testid="profile-request-open"
          onClick={() => { setOpen(true); setError(''); }}
          style={{
            marginTop: 10, width: '100%', minHeight: 40, borderRadius: 10,
            border: '1px solid var(--c-border)', background: 'var(--c-bg)',
            color: 'var(--c-text)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}
        >
          Ask for a correction
        </button>
      </>
    );
  }

  return (
    <form onSubmit={submit} data-testid="profile-request-form">
      {[
        { key: 'name', label: 'Name', type: 'text' },
        { key: 'phone', label: 'Phone', type: 'tel' },
        { key: 'email', label: 'Email', type: 'email' },
      ].map((field) => (
        <label
          key={field.key}
          htmlFor={`request-${field.key}`}
          style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--c-faint)', marginBottom: 10 }}
        >
          {field.label}
          <input
            id={`request-${field.key}`}
            className="focus-ring"
            data-testid={`profile-request-${field.key}`}
            type={field.type}
            value={form[field.key] || ''}
            onChange={(e) => { setForm({ ...form, [field.key]: e.target.value }); setError(''); }}
            style={{
              width: '100%', marginTop: 5, background: 'var(--c-bg)',
              border: '1px solid var(--c-border)', borderRadius: 8, padding: '10px 12px',
              color: 'var(--c-text)', fontSize: 14, outline: 'none',
            }}
          />
        </label>
      ))}

      {error && (
        <div data-testid="profile-request-error" style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 10 }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          type="button"
          className="focus-ring"
          data-testid="profile-request-cancel"
          onClick={() => { setOpen(false); setForm(currentValues); setError(''); }}
          style={{
            flex: 1, minHeight: 40, borderRadius: 10, border: '1px solid var(--c-border)',
            background: 'var(--c-bg)', color: 'var(--c-muted)', fontSize: 13,
            fontWeight: 600, cursor: 'pointer',
          }}
        >
          Cancel
        </button>
        <button
          type="submit"
          className="focus-ring"
          data-testid="profile-request-send"
          disabled={sending}
          style={{
            flex: 2, minHeight: 40, borderRadius: 10, border: 'none',
            background: 'var(--tool-hex-4f8ff7)', color: '#fff', fontSize: 13,
            fontWeight: 650, cursor: sending ? 'not-allowed' : 'pointer',
            opacity: sending ? 0.65 : 1,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          }}
        >
          <Send size={13} /> {sending ? 'Sending…' : 'Send for approval'}
        </button>
      </div>
    </form>
  );
}

const noteStyle = {
  display: 'flex', alignItems: 'flex-start', gap: 7, margin: 0,
  fontSize: 12, lineHeight: 1.5, color: 'var(--c-faint)',
};

export default function ProfileModal({ onClose }) {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const isStudent = currentUser.role === 'student';

  const bg     = 'var(--color-surface)';
  const border = 'var(--color-border)';
  const text   = 'var(--color-text-primary)';
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
                style={{ background: 'var(--color-surface-raised)', border: 'none', color: muted, cursor: 'pointer', borderRadius: 8, padding: 6 }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                onMouseLeave={e => e.currentTarget.style.background = 'var(--color-surface-raised)'}
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

            <OwnProfile currentUser={currentUser} />

            <div style={{ marginTop: 20 }}>
              <TokenCard isDark={isDark} currentUser={currentUser} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
