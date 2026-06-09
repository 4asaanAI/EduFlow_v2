import React, { useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { X, Sun, Moon, Bell, Lock, Check } from 'lucide-react';

export default function SettingsModal({ onClose }) {
  const { isDark, toggleTheme, theme } = useTheme();
  const [notifSettings, setNotifSettings] = useState(() => {
    try {
      const stored = localStorage.getItem('eduflow-notif-settings');
      return stored ? JSON.parse(stored) : { push: true, leave: true, fee: true, attendance: true, announcements: true };
    } catch {
      return { push: true, leave: true, fee: true, attendance: true, announcements: true };
    }
  });
  const [saved, setSaved] = useState(false);

  const bg = isDark ? '#1e1e1e' : '#fff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#525252';
  const secondary = isDark ? '#a0a0a0' : '#525252';
  const sectionBg = isDark ? '#141414' : '#fafafa';

  const Toggle = ({ active, onToggle }) => (
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

  const toggle = (key) => setNotifSettings(p => {
    const next = { ...p, [key]: !p[key] };
    localStorage.setItem('eduflow-notif-settings', JSON.stringify(next));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    return next;
  });

  const Section = ({ title, children }) => (
    <div style={{ marginBottom: 24 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: muted, letterSpacing: '0.03em', marginBottom: 10 }}>{title}</div>
      <div style={{ background: sectionBg, borderRadius: 14, border: `1px solid ${border}`, overflow: 'hidden' }}>
        {children}
      </div>
    </div>
  );

  const Row = ({ icon: Icon, label, subtitle, control, noBorder }) => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', borderBottom: noBorder ? 'none' : `1px solid ${border}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {Icon && <Icon size={16} color={muted} />}
        <div>
          <div style={{ fontSize: 14, fontWeight: 500, color: text }}>{label}</div>
          {subtitle && <div style={{ fontSize: 12, color: muted, marginTop: 2 }}>{subtitle}</div>}
        </div>
      </div>
      {control}
    </div>
  );

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 300 }}>
      <div className="fade-in-scale" style={{ background: bg, border: `1px solid ${border}`, borderRadius: 20, padding: 32, width: 460, maxWidth: '90vw', maxHeight: '88vh', overflowY: 'auto', boxShadow: 'var(--shadow-xl)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: text, letterSpacing: '-0.02em' }}>Settings</h2>
          <button onClick={onClose} style={{ background: isDark ? '#252525' : '#f5f5f5', border: 'none', color: muted, cursor: 'pointer', borderRadius: 8, padding: 6, transition: 'var(--transition-fast)' }}
            onMouseEnter={e => e.currentTarget.style.background = isDark ? '#333' : '#e5e5e5'}
            onMouseLeave={e => e.currentTarget.style.background = isDark ? '#252525' : '#f5f5f5'}>
            <X size={16} />
          </button>
        </div>

        <Section title="Appearance">
          <Row icon={isDark ? Moon : Sun} label="Theme" subtitle={`Currently: ${theme === 'dark' ? 'Dark' : 'Light'} mode`}
            control={<Toggle active={isDark} onToggle={toggleTheme} />}
            noBorder
          />
        </Section>

        <Section title="Notifications">
          {[
            { key: 'push', icon: Bell, label: 'Push Notifications', sub: 'School alerts & reminders' },
            { key: 'leave', label: 'Leave approvals', sub: 'Notify when approved/rejected' },
            { key: 'fee', label: 'Fee reminders', sub: 'Alert when payment due' },
            { key: 'attendance', label: 'Attendance alerts', sub: 'When student is absent' },
            { key: 'announcements', label: 'New announcements', sub: 'School broadcasts' },
          ].map(({ key, icon, label, sub }, i, arr) => (
            <Row key={key} icon={icon} label={label} subtitle={sub}
              control={<Toggle active={notifSettings[key]} onToggle={() => toggle(key)} />}
              noBorder={i === arr.length - 1}
            />
          ))}
        </Section>

        <Section title="Privacy & Security">
          <Row icon={Lock} label="Data Privacy" subtitle="DPDP Act compliant data handling"
            control={<span style={{ fontSize: 12, color: '#34d399', fontWeight: 600 }}>Active</span>}
          />
          <Row label="Session timeout" subtitle="Auto-logout after inactivity" noBorder
            control={<select style={{ background: isDark ? '#252525' : '#f5f5f5', border: `1px solid ${border}`, borderRadius: 8, padding: '5px 10px', color: text, fontSize: 13, outline: 'none', cursor: 'pointer' }}>
              <option>30 min</option><option>1 hour</option><option>2 hours</option>
            </select>}
          />
        </Section>

        <Section title="About">
          <Row label="EduFlow Version" control={<span style={{ fontSize: 12, color: muted, fontWeight: 500 }}>v1.1.0</span>} />
          <Row label="School" control={<span style={{ fontSize: 12, color: muted, fontWeight: 500 }}>The Aaryans, CBSE</span>} />
          <Row label="Academic Year" control={<span style={{ fontSize: 12, color: muted, fontWeight: 500 }}>2025-26</span>} noBorder />
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
