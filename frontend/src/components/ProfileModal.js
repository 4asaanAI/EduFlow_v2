import React, { useState, useEffect } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { X, Mail, Phone, Shield, Zap, BookOpen } from 'lucide-react';
import { getAuthHeaders } from '../lib/authSession';

const ROLE_COLORS = { owner: '#fb923c', admin: '#4f8ff7', teacher: '#34d399', student: '#a78bfa' };
const ROLE_LABELS = { owner: 'Owner / Principal', admin: 'Admin Staff', teacher: 'Teacher', student: 'Student' };
const API = process.env.REACT_APP_BACKEND_URL + '/api';

export default function ProfileModal({ onClose }) {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [tokenUsage, setTokenUsage] = useState({ used: 0, limit: 50000, sessions: 0 });
  const [studentClass, setStudentClass] = useState(null);

  useEffect(() => {
    const stored = localStorage.getItem(`token-usage-${currentUser.id}`);
    if (stored) {
      try { setTokenUsage(JSON.parse(stored)); } catch {}
    }
  }, [currentUser.id]);

  useEffect(() => {
    if (currentUser.role !== 'student') return;
    fetch(`${API}/students/me`, {
      headers: getAuthHeaders()
    }).then(r => r.json()).then(r => {
      if (r.success && r.data?.class_info) {
        const c = r.data.class_info;
        setStudentClass(`${c.name}${c.section ? '-' + c.section : ''}`);
      }
    }).catch(() => {});
  }, [currentUser.id, currentUser.role]);

  const bg = isDark ? '#1e1e1e' : '#fff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#666' : '#a3a3a3';
  const secondary = isDark ? '#a0a0a0' : '#525252';
  const cardBg = isDark ? '#141414' : '#fafafa';

  const usagePct = Math.min(100, Math.round((tokenUsage.used / tokenUsage.limit) * 100));
  const usageColor = usagePct > 80 ? '#f87171' : usagePct > 60 ? '#fbbf24' : '#34d399';

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 300 }}>
      <div className="fade-in-scale" style={{ background: bg, border: `1px solid ${border}`, borderRadius: 20, padding: 32, width: 420, maxWidth: '90vw', boxShadow: 'var(--shadow-xl)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: text, letterSpacing: '-0.02em' }}>Profile</h2>
          <button onClick={onClose} style={{ background: isDark ? '#252525' : '#f5f5f5', border: 'none', color: muted, cursor: 'pointer', borderRadius: 8, padding: 6, transition: 'var(--transition-fast)' }}
            onMouseEnter={e => e.currentTarget.style.background = isDark ? '#333' : '#e5e5e5'}
            onMouseLeave={e => e.currentTarget.style.background = isDark ? '#252525' : '#f5f5f5'}>
            <X size={16} />
          </button>
        </div>

        {/* Avatar */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ width: 72, height: 72, borderRadius: 18, background: ROLE_COLORS[currentUser.role], display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, fontWeight: 700, color: '#fff', margin: '0 auto 14px' }}>
            {currentUser.initials}
          </div>
          <h3 style={{ fontSize: 20, fontWeight: 600, color: text, marginBottom: 6, letterSpacing: '-0.02em' }}>{currentUser.name}</h3>
          <span style={{ fontSize: 12, fontWeight: 600, color: ROLE_COLORS[currentUser.role], background: `${ROLE_COLORS[currentUser.role]}12`, padding: '4px 14px', borderRadius: 20 }}>
            {ROLE_LABELS[currentUser.role]}
          </span>
        </div>

        {/* Info */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0, marginBottom: 20 }}>
          {[
            { icon: Shield, label: 'Role', value: ROLE_LABELS[currentUser.role] },
            ...(currentUser.role === 'student' && studentClass ? [{ icon: BookOpen, label: 'Class', value: studentClass }] : []),
            { icon: Mail, label: 'Email', value: `${currentUser.name.toLowerCase().replace(' ', '.')}@theararyans.edu.in` },
            { icon: Phone, label: 'School', value: 'The Aaryans, Lucknow, CBSE' },
          ].map((item) => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 0', borderBottom: `1px solid ${border}` }}>
              <item.icon size={15} color={muted} style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: muted, minWidth: 55, fontWeight: 500 }}>{item.label}</span>
              <span style={{ fontSize: 13, color: secondary, fontWeight: 500 }}>{item.value}</span>
            </div>
          ))}
        </div>

        {/* Token Usage */}
        <div style={{ background: cardBg, borderRadius: 14, border: `1px solid ${border}`, padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <Zap size={15} color={usageColor} />
            <span style={{ fontSize: 13, fontWeight: 600, color: text }}>AI Token Usage</span>
            <span style={{ marginLeft: 'auto', fontSize: 12, color: muted }}>{tokenUsage.sessions} sessions</span>
          </div>
          <div style={{ background: isDark ? '#2e2e2e' : '#e5e5e5', borderRadius: 6, height: 6, overflow: 'hidden', marginBottom: 8 }}>
            <div style={{ height: '100%', width: `${usagePct}%`, background: usageColor, borderRadius: 6, transition: 'width 0.5s ease' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: muted }}>
            <span>{tokenUsage.used.toLocaleString()} tokens used</span>
            <span>{tokenUsage.limit.toLocaleString()} limit</span>
          </div>
          {usagePct > 80 && (
            <p style={{ fontSize: 11, color: '#f87171', marginTop: 8 }}>
              High usage. Consider adding balance or enabling auto top-up.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
