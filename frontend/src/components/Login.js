import React, { useState } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const ROLES = [
  { key: 'owner',   label: 'Owner',   color: '#F97316', icon: '👑', free: true,  hint: 'Click to enter' },
  { key: 'admin',   label: 'Admin',   color: '#3B82F6', icon: '🛡️', free: true,  hint: 'Click to enter' },
  { key: 'teacher', label: 'Teacher', color: '#10B981', icon: '📚', free: false, hint: 'Enter name & password' },
  { key: 'student', label: 'Student', color: '#8B5CF6', icon: '🎓', free: false, hint: 'Enter admission no & password' },
];

export default function Login() {
  const { login } = useUser();
  const { isDark } = useTheme();
  const [activeRole, setActiveRole] = useState('owner');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const role = ROLES.find(r => r.key === activeRole);

  const handleRoleChange = (key) => {
    setActiveRole(key);
    setUsername('');
    setPassword('');
    setError('');
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: activeRole, username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Login failed');
      } else {
        login(data.user);
      }
    } catch {
      setError('Cannot connect to server. Is the backend running?');
    }
    setLoading(false);
  };

  const bg = isDark ? '#0A0A0F' : '#F8F9FC';
  const card = isDark ? '#111118' : '#FFFFFF';
  const border = isDark ? '#1E1E2E' : '#E2E8F0';
  const text = isDark ? '#E2E8F0' : '#0F172A';
  const muted = isDark ? '#64748B' : '#94A3B8';
  const inputBg = isDark ? '#161622' : '#F8F9FC';
  const inputBorder = isDark ? '#2A2A3E' : '#E2E8F0';

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: bg, fontFamily: 'Outfit, sans-serif', padding: 20,
    }}>
      <div style={{ width: '100%', maxWidth: 440 }}>
        {/* Logo / Branding */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14, background: 'linear-gradient(135deg, #3B82F6, #8B5CF6)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 26, marginBottom: 12, boxShadow: '0 8px 24px rgba(59,130,246,0.3)',
          }}>📚</div>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: text, margin: 0 }}>EduFlow</h1>
          <p style={{ fontSize: 13, color: muted, marginTop: 4 }}>The Aaryans CBSE School</p>
        </div>

        {/* Card */}
        <div style={{ background: card, border: `1px solid ${border}`, borderRadius: 16, overflow: 'hidden', boxShadow: isDark ? '0 8px 32px rgba(0,0,0,0.4)' : '0 4px 24px rgba(0,0,0,0.08)' }}>
          {/* Role Tabs */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', borderBottom: `1px solid ${border}` }}>
            {ROLES.map(r => (
              <button
                key={r.key}
                onClick={() => handleRoleChange(r.key)}
                style={{
                  padding: '12px 4px', border: 'none', background: activeRole === r.key
                    ? isDark ? '#1A1A2E' : '#F0F6FF'
                    : 'transparent',
                  borderBottom: activeRole === r.key ? `2px solid ${r.color}` : '2px solid transparent',
                  color: activeRole === r.key ? r.color : muted,
                  fontSize: 11, fontWeight: 600, cursor: 'pointer',
                  transition: 'all 0.15s', textAlign: 'center',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                }}
              >
                <span style={{ fontSize: 16 }}>{r.icon}</span>
                {r.label}
              </button>
            ))}
          </div>

          {/* Form */}
          <div style={{ padding: 28 }}>
            <p style={{ fontSize: 12, color: muted, marginBottom: 20, textAlign: 'center' }}>{role.hint}</p>

            <form onSubmit={handleLogin}>
              {!role.free && (
                <>
                  <div style={{ marginBottom: 14 }}>
                    <label style={{ display: 'block', fontSize: 10, color: muted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                      {activeRole === 'student' ? 'Admission Number' : 'Full Name'}
                    </label>
                    <input
                      type="text"
                      value={username}
                      onChange={e => setUsername(e.target.value)}
                      placeholder={activeRole === 'student' ? 'e.g. ADM20250001' : 'e.g. Rajesh Kumar'}
                      required
                      style={{
                        width: '100%', padding: '10px 14px', background: inputBg,
                        border: `1px solid ${inputBorder}`, borderRadius: 8, color: text,
                        fontSize: 13, outline: 'none', boxSizing: 'border-box',
                      }}
                    />
                  </div>
                  <div style={{ marginBottom: 20 }}>
                    <label style={{ display: 'block', fontSize: 10, color: muted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                      Password
                    </label>
                    <input
                      type="password"
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      placeholder={activeRole === 'student' ? 'Same as admission number' : 'Enter password'}
                      required
                      style={{
                        width: '100%', padding: '10px 14px', background: inputBg,
                        border: `1px solid ${inputBorder}`, borderRadius: 8, color: text,
                        fontSize: 13, outline: 'none', boxSizing: 'border-box',
                      }}
                    />
                  </div>
                </>
              )}

              {role.free && (
                <div style={{ textAlign: 'center', padding: '16px 0 20px' }}>
                  <div style={{ fontSize: 36, marginBottom: 8 }}>{role.icon}</div>
                  <p style={{ fontSize: 13, color: text, fontWeight: 600 }}>
                    {role.label} — No password required
                  </p>
                  <p style={{ fontSize: 11, color: muted, marginTop: 4 }}>
                    Direct access granted
                  </p>
                </div>
              )}

              {error && (
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 8, padding: '10px 14px', marginBottom: 16 }}>
                  <p style={{ fontSize: 12, color: '#EF4444', margin: 0 }}>{error}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                style={{
                  width: '100%', padding: '11px', borderRadius: 9, border: 'none',
                  background: loading ? muted : role.color,
                  color: '#fff', fontSize: 14, fontWeight: 600,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  transition: 'opacity 0.15s', opacity: loading ? 0.7 : 1,
                }}
              >
                {loading ? 'Signing in...' : `Sign in as ${role.label}`}
              </button>
            </form>
          </div>
        </div>

        {/* Quick credentials hint */}
        <div style={{ marginTop: 20, background: isDark ? '#0E0E1A' : '#F1F5F9', border: `1px solid ${border}`, borderRadius: 10, padding: '14px 16px' }}>
          <p style={{ fontSize: 10, color: muted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Demo Credentials</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {[
              { label: 'Teacher 1', user: 'Rajesh Kumar', pass: 'teacher@123', color: '#10B981' },
              { label: 'Teacher 2', user: 'Sunita Devi', pass: 'teacher@123', color: '#10B981' },
              { label: 'Student 1', user: 'ADM20250001', pass: 'ADM20250001', color: '#8B5CF6' },
              { label: 'Student 2', user: 'ADM20250002', pass: 'ADM20250002', color: '#8B5CF6' },
            ].map(c => (
              <div key={c.label} style={{ background: isDark ? '#161622' : '#fff', border: `1px solid ${border}`, borderRadius: 7, padding: '8px 10px' }}>
                <p style={{ fontSize: 9, color: c.color, fontWeight: 700, margin: '0 0 3px', textTransform: 'uppercase' }}>{c.label}</p>
                <p style={{ fontSize: 10, color: text, margin: '0 0 1px', fontFamily: 'monospace' }}>{c.user}</p>
                <p style={{ fontSize: 9, color: muted, margin: 0, fontFamily: 'monospace' }}>{c.pass}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
