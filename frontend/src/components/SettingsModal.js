import React, { useState, useRef } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { useUser } from '../contexts/UserContext';
import { X, Sun, Moon, Bell, Lock, Check, KeyRound, Eye, EyeOff } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

function Toggle({ active, onToggle, isDark }) {
  return (
    <button onClick={onToggle} style={{
      width: 42, height: 24, borderRadius: 12,
      background: active ? '#4f8ff7' : (isDark ? '#333' : '#d4d4d4'),
      border: 'none', cursor: 'pointer', position: 'relative',
      transition: 'background 0.2s ease', flexShrink: 0,
    }}>
      <div style={{
        width: 18, height: 18, borderRadius: '50%', background: '#fff',
        position: 'absolute', top: 3, left: active ? 21 : 3,
        transition: 'left 0.2s ease', boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
      }} />
    </button>
  );
}

function Section({ title, children, styles }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: styles.muted, letterSpacing: '0.03em', marginBottom: 10 }}>{title}</div>
      <div style={{ background: styles.sectionBg, borderRadius: 14, border: `1px solid ${styles.border}`, overflow: 'hidden' }}>
        {children}
      </div>
    </div>
  );
}

function Row({ icon: Icon, label, subtitle, control, noBorder, styles }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', borderBottom: noBorder ? 'none' : `1px solid ${styles.border}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {Icon && <Icon size={16} color={styles.muted} />}
        <div>
          <div style={{ fontSize: 14, fontWeight: 500, color: styles.text }}>{label}</div>
          {subtitle && <div style={{ fontSize: 12, color: styles.muted, marginTop: 2 }}>{subtitle}</div>}
        </div>
      </div>
      {control}
    </div>
  );
}

export default function SettingsModal({ onClose }) {
  const { isDark, toggleTheme, theme } = useTheme();
  const { currentUser, token } = useUser();
  const [notifSettings, setNotifSettings] = useState(() => {
    try {
      const stored = localStorage.getItem('eduflow-notif-settings');
      return stored ? JSON.parse(stored) : { push: true, leave: true, fee: true, attendance: true, announcements: true };
    } catch {
      return { push: true, leave: true, fee: true, attendance: true, announcements: true };
    }
  });
  const [saved, setSaved] = useState(false);
  const [pwForm, setPwForm] = useState({ new_password: '', confirm_password: '' });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwError, setPwError] = useState('');
  const [pwSuccess, setPwSuccess] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);
  const containerRef = useRef(null);

  const bg = isDark ? '#1e1e1e' : '#fff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#525252';
  const sectionBg = isDark ? '#141414' : '#fafafa';
  const styles = { bg, border, text, muted, sectionBg };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    setPwError('');
    setPwSuccess(false);
    if (pwForm.new_password.length < 6) {
      setPwError('Password must be at least 6 characters.');
      return;
    }
    if (pwForm.new_password !== pwForm.confirm_password) {
      setPwError('Passwords do not match.');
      return;
    }
    setPwSaving(true);
    try {
      const authToken = token || currentUser?.token || localStorage.getItem('token') || '';
      const res = await fetch(`${API}/auth/set-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({ new_password: pwForm.new_password }),
      });
      const data = await res.json();
      if (!res.ok) { setPwError(data.detail || 'Failed to change password.'); return; }
      setPwSuccess(true);
      setPwForm({ new_password: '', confirm_password: '' });
      setTimeout(() => setPwSuccess(false), 3000);
    } catch {
      setPwError('Network error. Please try again.');
    } finally {
      setPwSaving(false);
    }
  };

  const toggle = (key) => setNotifSettings(p => {
    const next = { ...p, [key]: !p[key] };
    localStorage.setItem('eduflow-notif-settings', JSON.stringify(next));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    return next;
  });

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 300 }}>
      <div ref={containerRef} className="fade-in-scale" style={{ background: bg, border: `1px solid ${border}`, borderRadius: 20, padding: 32, width: 460, maxWidth: '90vw', maxHeight: '88vh', overflowY: 'auto', boxShadow: 'var(--shadow-xl)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: text, letterSpacing: '-0.02em' }}>Settings</h2>
          <button onClick={onClose} style={{ background: isDark ? '#252525' : '#f5f5f5', border: 'none', color: muted, cursor: 'pointer', borderRadius: 8, padding: 6, transition: 'var(--transition-fast)' }}
            onMouseEnter={e => e.currentTarget.style.background = isDark ? '#333' : '#e5e5e5'}
            onMouseLeave={e => e.currentTarget.style.background = isDark ? '#252525' : '#f5f5f5'}>
            <X size={16} />
          </button>
        </div>

        <Section title="Appearance" styles={styles}>
          <Row icon={isDark ? Moon : Sun} label="Theme" subtitle={`Currently: ${theme === 'dark' ? 'Dark' : 'Light'} mode`}
            control={<Toggle active={isDark} onToggle={toggleTheme} isDark={isDark} />}
            noBorder styles={styles}
          />
        </Section>

        <Section title="Notifications" styles={styles}>
          {[
            { key: 'push', icon: Bell, label: 'Push Notifications', sub: 'School alerts & reminders' },
            { key: 'leave', label: 'Leave approvals', sub: 'Notify when approved/rejected' },
            { key: 'fee', label: 'Fee reminders', sub: 'Alert when payment due' },
            { key: 'attendance', label: 'Attendance alerts', sub: 'When student is absent' },
            { key: 'announcements', label: 'New announcements', sub: 'School broadcasts' },
          ].map(({ key, icon, label, sub }, i, arr) => (
            <Row key={key} icon={icon} label={label} subtitle={sub}
              control={<Toggle active={notifSettings[key]} onToggle={() => toggle(key)} isDark={isDark} />}
              noBorder={i === arr.length - 1} styles={styles}
            />
          ))}
        </Section>

        <Section title="Privacy & Security" styles={styles}>
          <Row icon={Lock} label="Data Privacy" subtitle="DPDP Act compliant data handling"
            control={<span style={{ fontSize: 12, color: '#34d399', fontWeight: 600 }}>Active</span>}
            styles={styles}
          />
          <Row label="Session timeout" subtitle="Auto-logout after inactivity" noBorder
            control={<select style={{ background: isDark ? '#252525' : '#f5f5f5', border: `1px solid ${border}`, borderRadius: 8, padding: '5px 10px', color: text, fontSize: 13, outline: 'none', cursor: 'pointer' }}>
              <option>30 min</option><option>1 hour</option><option>2 hours</option>
            </select>}
            styles={styles}
          />
        </Section>

        <Section title="Change Password" styles={styles}>
          <div style={{ padding: '14px 16px' }}>
            <form onSubmit={handlePasswordChange}>
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 11, color: muted, fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>New Password</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showNewPw ? 'text' : 'password'}
                    value={pwForm.new_password}
                    onChange={e => setPwForm(p => ({ ...p, new_password: e.target.value }))}
                    placeholder="Enter new password"
                    required
                    autoComplete="new-password"
                    style={{ width: '100%', background: isDark ? '#252525' : '#f5f5f5', border: `1px solid ${border}`, borderRadius: 8, padding: '9px 36px 9px 12px', color: text, fontSize: 13, outline: 'none', boxSizing: 'border-box' }}
                  />
                  <button type="button" onClick={() => setShowNewPw(v => !v)} style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: muted, padding: 2, display: 'flex', alignItems: 'center' }}>
                    {showNewPw ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>
              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: 11, color: muted, fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>Confirm Password</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showConfirmPw ? 'text' : 'password'}
                    value={pwForm.confirm_password}
                    onChange={e => setPwForm(p => ({ ...p, confirm_password: e.target.value }))}
                    placeholder="Confirm new password"
                    required
                    autoComplete="new-password"
                    style={{ width: '100%', background: isDark ? '#252525' : '#f5f5f5', border: `1px solid ${border}`, borderRadius: 8, padding: '9px 36px 9px 12px', color: text, fontSize: 13, outline: 'none', boxSizing: 'border-box' }}
                  />
                  <button type="button" onClick={() => setShowConfirmPw(v => !v)} style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: muted, padding: 2, display: 'flex', alignItems: 'center' }}>
                    {showConfirmPw ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>
              {pwError && (
                <div style={{ padding: '8px 12px', borderRadius: 8, marginBottom: 12, fontSize: 12, background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', color: '#f87171' }}>{pwError}</div>
              )}
              {pwSuccess && (
                <div style={{ padding: '8px 12px', borderRadius: 8, marginBottom: 12, fontSize: 12, background: 'rgba(52,211,153,0.1)', border: '1px solid rgba(52,211,153,0.3)', color: '#34d399', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Check size={13} /> Password changed successfully!
                </div>
              )}
              <button type="submit" disabled={pwSaving}
                style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 10, background: '#4f8ff7', border: 'none', color: '#fff', fontSize: 13, fontWeight: 600, cursor: pwSaving ? 'not-allowed' : 'pointer', opacity: pwSaving ? 0.7 : 1 }}>
                <KeyRound size={14} />
                {pwSaving ? 'Saving...' : 'Update Password'}
              </button>
            </form>
          </div>
        </Section>

        <Section title="About" styles={styles}>
          <Row label="EduFlow Version" control={<span style={{ fontSize: 12, color: muted, fontWeight: 500 }}>v1.1.0</span>} styles={styles} />
          <Row label="School" control={<span style={{ fontSize: 12, color: muted, fontWeight: 500 }}>The Aaryans, CBSE</span>} styles={styles} />
          <Row label="Academic Year" control={<span style={{ fontSize: 12, color: muted, fontWeight: 500 }}>2025-26</span>} noBorder styles={styles} />
        </Section>

        {saved && (
          <div className="fade-in" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '8px', background: 'rgba(52,211,153,0.1)', borderRadius: 10, color: '#34d399', fontSize: 13, fontWeight: 500 }}>
            <Check size={14} /> Settings saved
          </div>
        )}
      </div>
    </div>
  );
}
