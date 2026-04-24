import React, { useState } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { Sparkles, KeyRound, Loader2, ChevronDown, ChevronUp } from 'lucide-react';

// All seeded accounts — grouped by role (with sub-roles)
const CREDENTIAL_GROUPS = [
  {
    role: 'Owner',
    color: '#fb923c',
    accounts: [
      { label: 'Aman Sharma', username: 'owner', password: 'owner@123', note: 'Full access · All data' },
    ],
  },
  {
    role: 'Admin',
    color: '#4f8ff7',
    accounts: [
      { label: 'Priya Sharma',  username: 'admin',       password: 'admin@123',       note: 'Principal · Full ops' },
      { label: 'Meena Gupta',   username: 'accountant',  password: 'accountant@123',  note: 'Accountant · Fees only' },
      { label: 'Suresh Yadav',  username: 'transport',   password: 'transport@123',   note: 'Transport Head' },
      { label: 'Kavita Singh',  username: 'reception',   password: 'reception@123',   note: 'Receptionist · Enquiries' },
      { label: 'Rahul Tech',    username: 'ittech',      password: 'ittech@123',      note: 'IT & Tech · Support' },
    ],
  },
  {
    role: 'Teacher',
    color: '#34d399',
    accounts: [
      { label: 'Vikash Singh',  username: 'Vikash Singh',  password: 'hod@123',      note: 'HOD · Mathematics' },
      { label: 'Deepa Verma',   username: 'Deepa Verma',   password: 'teacher@123',  note: 'Coordinator · Class 9-12' },
      { label: 'Rajesh Kumar',  username: 'Rajesh Kumar',  password: 'teacher@123',  note: 'Class Teacher · 9A' },
      { label: 'Sunita Devi',   username: 'Sunita Devi',   password: 'teacher@123',  note: 'Class Teacher · 9B' },
      { label: 'Manoj Tiwari',  username: 'Manoj Tiwari',  password: 'teacher@123',  note: 'Subject Teacher · Science' },
      { label: 'Ankit Sharma',  username: 'Ankit Sharma',  password: 'teacher@123',  note: 'Subject Teacher · SST' },
      { label: 'Nisha Verma',   username: 'Nisha Verma',   password: 'kg@123',       note: 'KG In-charge · Nursery' },
    ],
  },
  {
    role: 'Student',
    color: '#a78bfa',
    accounts: [
      { label: 'Rahul Singh',   username: 'ADM20250001', password: 'student@123', note: 'Class 9A · Roll 1' },
      { label: 'Sneha Kumari',  username: 'ADM20250002', password: 'student@123', note: 'Class 9A · Roll 2' },
      { label: 'Sohail Khan',   username: 'ADM20250011', password: 'student@123', note: 'Class 9B · Roll 1' },
    ],
  },
];

export default function Login() {
  const { loginPassword } = useUser();
  const { isDark } = useTheme();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedGroup, setExpandedGroup] = useState(null);

  const bg = isDark ? '#111111' : '#f5f5f5';
  const card = isDark ? '#1a1a1a' : '#ffffff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#666' : '#a3a3a3';
  const secondary = isDark ? '#a0a0a0' : '#525252';
  const inputBg = isDark ? '#252525' : '#fafafa';
  const inputBorder = isDark ? '#333' : '#e5e5e5';
  const rowHover = isDark ? '#252525' : '#f9fafb';
  const accent = '#4f8ff7';

  const inputStyle = {
    width: '100%', padding: '12px 14px', background: inputBg,
    border: `1px solid ${inputBorder}`, borderRadius: 10, color: text,
    fontSize: 15, outline: 'none', boxSizing: 'border-box',
    transition: 'border-color 0.2s ease',
  };

  const buttonStyle = (disabled) => ({
    width: '100%', padding: '13px', borderRadius: 12, border: 'none',
    background: disabled ? muted : (isDark ? '#f5f5f5' : '#171717'),
    color: disabled ? '#fff' : (isDark ? '#171717' : '#fff'),
    fontSize: 14, fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 0.2s ease', opacity: disabled ? 0.7 : 1,
    letterSpacing: '-0.01em',
    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
  });

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Enter username and password');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await loginPassword(username.trim(), password.trim());
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const fillCredentials = (account) => {
    setUsername(account.username);
    setPassword(account.password);
    setError('');
  };

  const toggleGroup = (role) => {
    setExpandedGroup(prev => prev === role ? null : role);
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: bg, padding: 20,
    }}>
      <div style={{ width: '100%', maxWidth: 440 }}>
        {/* Logo */}
        <div className="fade-in" style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 16,
            background: 'linear-gradient(135deg, #4f8ff7, #a78bfa)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 16, boxShadow: '0 8px 24px rgba(79,143,247,0.25)',
          }}>
            <Sparkles size={24} color="#fff" />
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 700, color: text, margin: 0, letterSpacing: '-0.03em' }}>EduFlow</h1>
          <p style={{ fontSize: 14, color: muted, marginTop: 6 }}>The Aaryans CBSE School</p>
        </div>

        {/* Login Card */}
        <div className="fade-in" style={{
          background: card, border: `1px solid ${border}`, borderRadius: 20,
          overflow: 'hidden', boxShadow: isDark ? 'var(--shadow-lg)' : 'var(--shadow-md)',
        }}>
          <div style={{ padding: 32 }}>
            <div style={{ textAlign: 'center', marginBottom: 28 }}>
              <div style={{
                width: 48, height: 48, borderRadius: 14, margin: '0 auto 14px',
                background: `${accent}12`, display: 'flex', alignItems: 'center',
                justifyContent: 'center', border: `1px solid ${accent}20`,
              }}>
                <KeyRound size={22} color={accent} />
              </div>
              <h2 style={{ fontSize: 18, fontWeight: 600, color: text, margin: '0 0 4px' }}>
                Sign In
              </h2>
              <p style={{ fontSize: 13, color: muted, margin: 0 }}>
                Enter your credentials to continue
              </p>
            </div>

            <form onSubmit={handleLogin}>
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', fontSize: 12, color: secondary, fontWeight: 600, marginBottom: 8 }}>
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={e => { setUsername(e.target.value); setError(''); }}
                  placeholder="Username, name, or admission number"
                  required
                  autoFocus
                  autoComplete="username"
                  style={inputStyle}
                  onFocus={e => e.target.style.borderColor = accent}
                  onBlur={e => e.target.style.borderColor = inputBorder}
                />
              </div>
              <div style={{ marginBottom: 24 }}>
                <label style={{ display: 'block', fontSize: 12, color: secondary, fontWeight: 600, marginBottom: 8 }}>
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={e => { setPassword(e.target.value); setError(''); }}
                  placeholder="Enter password"
                  required
                  autoComplete="current-password"
                  style={inputStyle}
                  onFocus={e => e.target.style.borderColor = accent}
                  onBlur={e => e.target.style.borderColor = inputBorder}
                />
              </div>

              {error && (
                <div style={{
                  background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)',
                  borderRadius: 10, padding: '10px 14px', marginBottom: 16,
                }}>
                  <p style={{ fontSize: 13, color: '#f87171', margin: 0 }}>{error}</p>
                </div>
              )}

              <button type="submit" disabled={loading} style={buttonStyle(loading)}>
                {loading && <Loader2 size={16} className="spin" />}
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>
          </div>
        </div>

        {/* Demo Credentials — grouped by role */}
        <div className="fade-in" style={{
          marginTop: 20, background: card, border: `1px solid ${border}`,
          borderRadius: 16, overflow: 'hidden',
        }}>
          <div style={{ padding: '14px 18px 10px', borderBottom: `1px solid ${border}` }}>
            <p style={{ fontSize: 11, fontWeight: 700, color: muted, margin: 0, letterSpacing: '0.06em' }}>
              DEMO CREDENTIALS — CLICK TO FILL
            </p>
          </div>

          {CREDENTIAL_GROUPS.map((group, gi) => {
            const isExpanded = expandedGroup === group.role;
            const isLast = gi === CREDENTIAL_GROUPS.length - 1;

            return (
              <div key={group.role} style={{ borderBottom: isLast ? 'none' : `1px solid ${border}` }}>
                {/* Role header — clickable to expand/collapse */}
                <button
                  onClick={() => toggleGroup(group.role)}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '12px 18px', background: 'transparent', border: 'none',
                    cursor: 'pointer', transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = rowHover}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                      width: 8, height: 8, borderRadius: '50%', background: group.color, flexShrink: 0,
                    }} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: group.color }}>{group.role}</span>
                    <span style={{ fontSize: 11, color: muted }}>
                      {group.accounts.length} account{group.accounts.length > 1 ? 's' : ''}
                    </span>
                    {/* Quick-fill for single-account roles */}
                    {group.accounts.length === 1 && (
                      <span
                        style={{ fontSize: 11, color: secondary, fontFamily: 'monospace' }}
                        onClick={e => { e.stopPropagation(); fillCredentials(group.accounts[0]); }}
                      >
                        {group.accounts[0].username}
                      </span>
                    )}
                  </div>
                  {group.accounts.length > 1
                    ? (isExpanded ? <ChevronUp size={14} color={muted} /> : <ChevronDown size={14} color={muted} />)
                    : null}
                </button>

                {/* Expanded account list */}
                {(isExpanded || group.accounts.length === 1) && (
                  <div style={{ paddingBottom: 6 }}>
                    {group.accounts.map((account, ai) => (
                      <div
                        key={ai}
                        onClick={() => fillCredentials(account)}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          padding: '8px 18px 8px 36px', cursor: 'pointer',
                          transition: 'background 0.15s ease',
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = rowHover}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      >
                        <div>
                          <p style={{ fontSize: 12, color: text, fontWeight: 500, margin: '0 0 2px' }}>
                            {account.label}
                          </p>
                          <p style={{ fontSize: 11, color: muted, margin: 0 }}>{account.note}</p>
                        </div>
                        <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 12 }}>
                          <p style={{ fontSize: 11, color: secondary, margin: '0 0 2px', fontFamily: 'monospace' }}>
                            {account.username}
                          </p>
                          <p style={{ fontSize: 10, color: muted, margin: 0, fontFamily: 'monospace' }}>
                            {account.password}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        .spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}
