import React, { useState, useEffect } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { X, Mail, Phone, Shield, Zap, BookOpen } from 'lucide-react';
import { getMyTokenUsage } from '../lib/api';
import StudentProfileEditor from './StudentProfileEditor';

const ROLE_COLORS = { owner: '#fb923c', admin: '#4f8ff7', teacher: '#34d399', student: '#a78bfa' };
const ROLE_LABELS = { owner: 'Owner / Principal', admin: 'Admin Staff', teacher: 'Teacher', student: 'Student' };
const API = process.env.REACT_APP_BACKEND_URL + '/api';

function TokenCard({ isDark, currentUser }) {
  const [tokenUsage, setTokenUsage] = useState(null);

  useEffect(() => {
    getMyTokenUsage()
      .then(r => { if (r.success) setTokenUsage(r.data); })
      .catch(() => {});
  }, [currentUser.id]);

  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#525252';
  const cardBg = isDark ? '#141414' : '#fafafa';

  const isUnlimited = tokenUsage?.unlimited === true || tokenUsage?.role_limit == null;
  const limit = isUnlimited ? 0 : (tokenUsage?.role_limit || 0);
  const used = tokenUsage?.total_used || 0;
  const usagePct = (!isUnlimited && limit > 0) ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const usageColor = usagePct >= 90 ? '#ef4444' : usagePct >= 70 ? '#f59e0b' : '#10b981';

  function fmtTokens(n) {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
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
        <span>{isUnlimited ? `${fmtTokens(used)} used` : `${fmtTokens(used)} / ${fmtTokens(limit)}`}</span>
        {!isUnlimited && usagePct >= 80 && <span style={{ color: '#4f8ff7', fontWeight: 600 }}>⚡ Top up</span>}
      </div>
      {tokenUsage == null && <p style={{ fontSize: 11, color: muted, marginTop: 4 }}>Loading usage…</p>}
    </div>
  );
}

export default function ProfileModal({ onClose }) {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const isStudent = currentUser.role === 'student';

  const bg = isDark ? '#1e1e1e' : '#fff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#525252';
  const secondary = isDark ? '#a0a0a0' : '#525252';

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 300 }}>
      <div
        className="fade-in-scale"
        style={{
          background: bg, border: `1px solid ${border}`, borderRadius: 20,
          padding: 32, width: isStudent ? 520 : 420, maxWidth: '94vw',
          maxHeight: '90vh', overflowY: 'auto',
          boxShadow: 'var(--shadow-xl)',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: text, letterSpacing: '-0.02em' }}>
            {isStudent ? 'My Profile' : 'Profile'}
          </h2>
          <button onClick={onClose} style={{ background: isDark ? '#252525' : '#f5f5f5', border: 'none', color: muted, cursor: 'pointer', borderRadius: 8, padding: 6 }}
            onMouseEnter={e => e.currentTarget.style.background = isDark ? '#333' : '#e5e5e5'}
            onMouseLeave={e => e.currentTarget.style.background = isDark ? '#252525' : '#f5f5f5'}>
            <X size={16} />
          </button>
        </div>

        {/* Avatar */}
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ width: 64, height: 64, borderRadius: 16, background: ROLE_COLORS[currentUser.role], display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, fontWeight: 700, color: '#fff', margin: '0 auto 12px' }}>
            {currentUser.initials}
          </div>
          <h3 style={{ fontSize: 18, fontWeight: 600, color: text, marginBottom: 6, letterSpacing: '-0.02em' }}>{currentUser.name}</h3>
          <span style={{ fontSize: 11, fontWeight: 600, color: ROLE_COLORS[currentUser.role], background: `${ROLE_COLORS[currentUser.role]}18`, padding: '3px 12px', borderRadius: 20 }}>
            {ROLE_LABELS[currentUser.role]}
          </span>
        </div>

        {/* Student: tabbed editor */}
        {isStudent ? (
          <StudentProfileEditor isDark={isDark} />
        ) : (
          <>
            {/* Staff: read-only info rows */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0, marginBottom: 20 }}>
              {[
                { icon: Shield, label: 'Role', value: ROLE_LABELS[currentUser.role] },
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
            <TokenCard isDark={isDark} currentUser={currentUser} />
          </>
        )}
      </div>
    </div>
  );
}
