import React, { useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { X, Sun, Moon, Bell, Lock, Save, Check } from 'lucide-react';

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

  const handleSaveNotif = () => {
    localStorage.setItem('eduflow-notif-settings', JSON.stringify(notifSettings));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const bg = isDark ? '#161622' : '#fff';
  const border = isDark ? '#222230' : '#E2E8F0';
  const text = isDark ? '#E2E8F0' : '#0F172A';
  const muted = isDark ? '#64748B' : '#94A3B8';
  const sectionBg = isDark ? '#0F0F1A' : '#F8F9FC';

  const Section = ({ title, children, action }) => (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{title}</div>
        {action}
      </div>
      <div style={{ background: sectionBg, borderRadius: 10, border: `1px solid ${border}`, overflow: 'hidden' }}>
        {children}
      </div>
    </div>
  );

  const Row = ({ icon: Icon, label, subtitle, control, noBorder }) => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 14px', borderBottom: noBorder ? 'none' : `1px solid ${border}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {Icon && <Icon size={14} color={muted} />}
        <div>
          <div style={{ fontSize: 13, fontWeight: 500, color: text }}>{label}</div>
          {subtitle && <div style={{ fontSize: 11, color: muted, marginTop: 1 }}>{subtitle}</div>}
        </div>
      </div>
      {control}
    </div>
  );

  const Toggle = ({ active, onToggle }) => (
    <button onClick={onToggle} style={{ width: 40, height: 22, borderRadius: 11, background: active ? '#3B82F6' : (isDark ? '#222230' : '#CBD5E1'), border: 'none', cursor: 'pointer', position: 'relative', transition: 'background 0.2s', flexShrink: 0 }}>
      <div style={{ width: 16, height: 16, borderRadius: '50%', background: '#fff', position: 'absolute', top: 3, left: active ? 21 : 3, transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)' }} />
    </button>
  );

  const toggle = (key) => setNotifSettings(p => {
    const next = { ...p, [key]: !p[key] };
    localStorage.setItem('eduflow-notif-settings', JSON.stringify(next));
    return next;
  });

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 300 }}>
      <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 16, padding: 28, width: 440, maxHeight: '88vh', overflowY: 'auto', boxShadow: '0 24px 64px rgba(0,0,0,0.4)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 18, fontWeight: 700, color: text }}>Settings</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: muted, cursor: 'pointer' }}><X size={18} /></button>
        </div>

        <Section title="Appearance">
          <Row icon={isDark ? Moon : Sun} label="Theme" subtitle={`Currently: ${theme === 'dark' ? 'Dark mode' : 'Light mode'}`}
            control={<Toggle active={isDark} onToggle={toggleTheme} />}
            noBorder
          />
        </Section>

        <Section title="Notifications"
          action={
            <button onClick={handleSaveNotif} style={{ display: 'flex', alignItems: 'center', gap: 5, background: saved ? '#10B981' : '#3B82F6', border: 'none', borderRadius: 6, padding: '4px 10px', color: '#fff', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
              {saved ? <Check size={11} /> : <Save size={11} />}
              {saved ? 'Saved' : 'Save'}
            </button>
          }>
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
            control={<span style={{ fontSize: 11, color: '#10B981', fontWeight: 600 }}>Active</span>}
          />
          <Row label="Session timeout" subtitle="Auto-logout after inactivity" noBorder
            control={<select style={{ background: isDark ? '#222230' : '#F1F5F9', border: `1px solid ${border}`, borderRadius: 6, padding: '4px 8px', color: text, fontSize: 12, outline: 'none' }}>
              <option>30 min</option><option>1 hour</option><option>2 hours</option>
            </select>}
          />
        </Section>

        <Section title="About">
          <Row label="EduFlow Version" control={<span style={{ fontSize: 11, color: muted }}>v1.1.0</span>} />
          <Row label="School" control={<span style={{ fontSize: 11, color: muted }}>The Aaryans, CBSE</span>} />
          <Row label="Academic Year" control={<span style={{ fontSize: 11, color: muted }}>2025-26</span>} noBorder />
        </Section>
      </div>
    </div>
  );
}
