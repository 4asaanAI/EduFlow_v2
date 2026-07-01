import React, { useState } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { KeyRound, Loader2 } from 'lucide-react';

export default function Login() {
  const { loginPassword } = useUser();
  const { isDark } = useTheme();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const bg = isDark ? '#111111' : '#f5f5f5';
  const card = isDark ? '#1a1a1a' : '#ffffff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#525252';
  const secondary = isDark ? '#a0a0a0' : '#525252';
  const inputBg = isDark ? '#252525' : '#fafafa';
  const inputBorder = isDark ? '#333' : '#e5e5e5';
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
      window.history.replaceState(null, '', '/dashboard');
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: bg, padding: 20,
    }}>
      <div style={{ width: '100%', maxWidth: 440 }}>
        {/* Logo */}
        <div className="fade-in" style={{ textAlign: 'center', marginBottom: 36 }}>
          {/* Logo image with glow halo */}
          <div style={{ display: 'inline-block', marginBottom: 8, position: 'relative' }}>
            <div style={{
              position: 'absolute', inset: -20, borderRadius: 32,
              background: 'radial-gradient(ellipse at center, rgba(232,89,12,0.18) 0%, transparent 70%)',
              pointerEvents: 'none',
            }} />
            <img
              src="/eduflow-logo.png"
              alt="EduFlow"
              style={{
                height: 80, width: 'auto', objectFit: 'contain', display: 'block',
                filter: isDark
                  ? 'brightness(1.15) drop-shadow(0 6px 20px rgba(232,89,12,0.5))'
                  : 'drop-shadow(0 6px 16px rgba(232,89,12,0.35))',
              }}
            />
          </div>

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

            <form onSubmit={handleLogin} data-testid="login-form">
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', fontSize: 12, color: secondary, fontWeight: 600, marginBottom: 8 }}>
                  Username
                </label>
                <input
                  data-testid="login-username"
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
                  data-testid="login-password"
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
                  <p data-testid="login-error" style={{ fontSize: 13, color: '#f87171', margin: 0 }}>{error}</p>
                </div>
              )}

              <button type="submit" data-testid="login-submit" disabled={loading} style={buttonStyle(loading)}>
                {loading && <Loader2 size={16} className="spin" />}
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>
          </div>
        </div>

      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        .spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}
