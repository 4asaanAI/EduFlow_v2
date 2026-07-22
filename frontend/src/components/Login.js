import React, { useState } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { Loader2 } from 'lucide-react';
import BotMascot from './ui/BotMascot';

export default function Login() {
  const { loginPassword } = useUser();
  const { isDark } = useTheme();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Epic 9: these were hard-coded `isDark ? hex : hex` pairs, which made the
  // sign-in screen the one surface the design tokens never reached.
  const bg = 'var(--color-page)';
  const card = 'var(--color-surface)';
  const border = 'var(--color-border)';
  const text = 'var(--color-text-primary)';
  const muted = 'var(--color-text-muted)';
  const secondary = 'var(--color-text-secondary)';
  const inputBg = 'var(--color-surface-raised)';
  const inputBorder = 'var(--color-border)';
  const accent = 'var(--color-accent-blue)';

  const inputStyle = {
    width: '100%', padding: '12px 14px', background: inputBg,
    border: `1px solid ${inputBorder}`, borderRadius: 'var(--radius-md)', color: text,
    fontFamily: 'var(--font-body)',
    // 16px so iOS Safari does not zoom the page when the field takes focus.
    fontSize: 16, outline: 'none', boxSizing: 'border-box',
    transition: 'border-color var(--transition-fast)',
  };

  // The brand's pressable button: it sinks into its own shadow, using
  // `transform` only so the card never reflows on click.
  const buttonStyle = (disabled) => ({
    width: '100%', padding: '13px', borderRadius: 'var(--radius-lg)', border: 'none',
    background: disabled ? 'var(--color-border-strong)' : 'var(--brand-blue-fill)',
    color: disabled ? 'var(--color-text-primary)' : 'var(--on-brand-blue)',
    fontFamily: 'var(--font-display)',
    fontSize: 'var(--text-lg)', fontWeight: 700,
    boxShadow: disabled ? 'none' : '0 4px 0 0 var(--brand-blue-press)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'transform var(--transition-fast), box-shadow var(--transition-fast)',
    opacity: disabled ? 0.7 : 1,
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
        {/* Flo greets you at the door.
            The mascot takes the top slot the wordmark used to hold, and the
            wordmark moves down into the card in place of the key icon — so the
            first thing anyone sees signing in is the assistant, not a padlock.
            The sign-in screen is one of the three places Flo is allowed: here,
            empty states, and the chat greeting. Never on working screens. */}
        <div className="fade-in" style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ display: 'inline-block', position: 'relative' }}>
            <div style={{
              position: 'absolute', inset: -18, borderRadius: 40,
              background: 'radial-gradient(ellipse at center, rgba(43,143,240,0.20) 0%, transparent 70%)',
              pointerEvents: 'none',
            }} />
            <BotMascot size={104} wave data-testid="login-mascot" />
          </div>
        </div>

        {/* Login Card */}
        <div className="fade-in" style={{
          background: card, border: `1px solid ${border}`, borderRadius: 20,
          overflow: 'hidden', boxShadow: isDark ? 'var(--shadow-lg)' : 'var(--shadow-md)',
        }}>
          <div style={{ padding: 32 }}>
            <div style={{ textAlign: 'center', marginBottom: 28 }}>
              {/* The EduFlow wordmark, where the key icon used to be. A padlock
                  says "you are locked out"; the brand says "you are in the
                  right place". Same reason the mascot took the slot above. */}
              <img
                src="/eduflow-logo.png"
                alt="EduFlow"
                data-testid="login-wordmark"
                style={{
                  height: 72, width: 'auto', objectFit: 'contain',
                  display: 'block', margin: '0 auto 16px',
                  filter: isDark
                    ? 'brightness(1.15) drop-shadow(0 4px 14px rgba(232,89,12,0.45))'
                    : 'drop-shadow(0 4px 12px rgba(232,89,12,0.28))',
                }}
              />
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'var(--text-xl)', fontWeight: 700, color: text, margin: '0 0 4px' }}>
                Sign In
              </h2>
              <p style={{ fontSize: 'var(--text-sm)', color: muted, margin: 0 }}>
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
                  <p data-testid="login-error" role="alert" style={{ fontSize: 'var(--text-sm)', color: 'var(--color-danger)', margin: 0 }}>{error}</p>
                </div>
              )}

              <button
                type="submit"
                data-testid="login-submit"
                disabled={loading}
                className="login-submit-btn"
                style={buttonStyle(loading)}
              >
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
