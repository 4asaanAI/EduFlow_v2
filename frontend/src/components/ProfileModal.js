import React, { useState, useEffect } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { X, User, Mail, Phone, Shield, Zap, TrendingUp } from 'lucide-react';

const ROLE_COLORS = { owner: '#F97316', admin: '#3B82F6', teacher: '#10B981', student: '#8B5CF6' };
const ROLE_LABELS = { owner: 'Owner / Principal', admin: 'Admin Staff', teacher: 'Teacher', student: 'Student' };
const API = process.env.REACT_APP_BACKEND_URL + '/api';

export default function ProfileModal({ onClose }) {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [tokenUsage, setTokenUsage] = useState({ used: 0, limit: 50000, sessions: 0 });

  useEffect(() => {
    // Load token usage from localStorage (tracked locally per session)
    const stored = localStorage.getItem(`token-usage-${currentUser.id}`);
    if (stored) {
      try { setTokenUsage(JSON.parse(stored)); } catch {}
    }
  }, [currentUser.id]);

  const bg = isDark ? '#161622' : '#fff';
  const border = isDark ? '#222230' : '#E2E8F0';
  const text = isDark ? '#E2E8F0' : '#0F172A';
  const muted = isDark ? '#64748B' : '#94A3B8';
  const cardBg = isDark ? '#0F0F1A' : '#F8F9FC';

  const usagePct = Math.min(100, Math.round((tokenUsage.used / tokenUsage.limit) * 100));
  const usageColor = usagePct > 80 ? '#EF4444' : usagePct > 60 ? '#F59E0B' : '#10B981';

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 300 }}>
      <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 16, padding: 28, width: 400, boxShadow: '0 24px 64px rgba(0,0,0,0.4)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 18, fontWeight: 700, color: text }}>Profile</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: muted, cursor: 'pointer' }}><X size={18} /></button>
        </div>

        {/* Avatar */}
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ width: 68, height: 68, borderRadius: '50%', background: ROLE_COLORS[currentUser.role], display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26, fontWeight: 700, color: '#fff', margin: '0 auto 10px', fontFamily: 'Outfit, sans-serif' }}>
            {currentUser.initials}
          </div>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 18, fontWeight: 600, color: text, marginBottom: 4 }}>{currentUser.name}</h3>
          <span style={{ fontSize: 11, fontWeight: 700, color: ROLE_COLORS[currentUser.role], background: `${ROLE_COLORS[currentUser.role]}20`, padding: '3px 10px', borderRadius: 20 }}>
            {ROLE_LABELS[currentUser.role]}
          </span>
        </div>

        {/* Info */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0, marginBottom: 16 }}>
          {[
            { icon: Shield, label: 'Role', value: ROLE_LABELS[currentUser.role] },
            { icon: Mail, label: 'Email', value: `${currentUser.name.toLowerCase().replace(' ', '.')}@theararyans.edu.in` },
            { icon: Phone, label: 'School', value: 'The Aaryans, Lucknow, CBSE' },
          ].map((item, i) => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: `1px solid ${border}` }}>
              <item.icon size={13} color={muted} style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 11, color: muted, minWidth: 50 }}>{item.label}</span>
              <span style={{ fontSize: 12, color: text, fontWeight: 500 }}>{item.value}</span>
            </div>
          ))}
        </div>

        {/* Token Usage */}
        <div style={{ background: cardBg, borderRadius: 10, border: `1px solid ${border}`, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Zap size={14} color={usageColor} />
            <span style={{ fontSize: 12, fontWeight: 600, color: text }}>AI Token Usage</span>
            <span style={{ marginLeft: 'auto', fontSize: 11, color: muted }}>{tokenUsage.sessions} sessions</span>
          </div>
          <div style={{ background: isDark ? '#222230' : '#E2E8F0', borderRadius: 6, height: 6, overflow: 'hidden', marginBottom: 6 }}>
            <div style={{ height: '100%', width: `${usagePct}%`, background: usageColor, borderRadius: 6, transition: 'width 0.5s' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: muted }}>
            <span>{tokenUsage.used.toLocaleString()} tokens used</span>
            <span>{tokenUsage.limit.toLocaleString()} monthly limit</span>
          </div>
          {usagePct > 80 && (
            <p style={{ fontSize: 10, color: '#EF4444', marginTop: 6 }}>
              High usage. Go to Profile → Universal Key → Add Balance or enable auto top-up.
            </p>
          )}
        </div>

        <div style={{ marginTop: 14, padding: '10px', background: cardBg, borderRadius: 8, border: `1px solid ${border}` }}>
          <p style={{ fontSize: 10, color: muted, textAlign: 'center' }}>
            Auth disabled in dev mode. Role switching available via header dropdown.
          </p>
        </div>
      </div>
    </div>
  );
}
