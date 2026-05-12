import React, { useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export default function ForgotPassword() {
  const { isDark } = useTheme();
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    setStatus('');
    try {
      const res = await fetch(`${API}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Unable to send reset link');
      setStatus(data.message || 'If that email exists, a reset link has been sent.');
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const card = isDark ? '#1a1a1a' : '#fff';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#a0a0a0' : '#525252';

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: isDark ? '#111' : '#f5f5f5', padding: 20 }}>
      <form onSubmit={submit} style={{ width: '100%', maxWidth: 420, background: card, border: `1px solid ${isDark ? '#2e2e2e' : '#e5e5e5'}`, borderRadius: 16, padding: 28 }}>
        <h1 style={{ color: text, fontSize: 22, margin: 0 }}>Reset Password</h1>
        <p style={{ color: muted, fontSize: 13, marginTop: 8 }}>Enter your account email address.</p>
        <input value={email} onChange={e => setEmail(e.target.value)} type="email" required autoComplete="email" placeholder="you@example.com" style={{ width: '100%', boxSizing: 'border-box', marginTop: 18, padding: 12, borderRadius: 10, border: `1px solid ${isDark ? '#333' : '#ddd'}`, background: isDark ? '#252525' : '#fafafa', color: text }} />
        {status && <p style={{ color: '#34d399', fontSize: 13 }}>{status}</p>}
        {error && <p style={{ color: '#f87171', fontSize: 13 }}>{error}</p>}
        <button disabled={loading} style={{ width: '100%', marginTop: 18, padding: 12, border: 0, borderRadius: 10, background: isDark ? '#f5f5f5' : '#171717', color: isDark ? '#171717' : '#fff', fontWeight: 700 }}>{loading ? 'Sending...' : 'Send Reset Link'}</button>
        <button type="button" onClick={() => { window.location.href = '/'; }} style={{ width: '100%', marginTop: 10, padding: 10, border: 0, background: 'transparent', color: muted }}>Back to sign in</button>
      </form>
    </div>
  );
}
