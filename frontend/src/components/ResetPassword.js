import React, { useMemo, useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export default function ResetPassword() {
  const { isDark } = useTheme();
  const token = useMemo(() => new URLSearchParams(window.location.search).get('token') || '', []);
  const [password, setPassword] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState(token ? '' : 'Reset token is missing.');
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    setStatus('');
    try {
      const res = await fetch(`${API}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Reset link is invalid or expired');
      setStatus('Password updated. You can sign in now.');
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
        <h1 style={{ color: text, fontSize: 22, margin: 0 }}>Create New Password</h1>
        <p style={{ color: muted, fontSize: 13, marginTop: 8 }}>Use at least 8 characters.</p>
        <input value={password} onChange={e => setPassword(e.target.value)} type="password" required minLength={8} autoComplete="new-password" placeholder="New password" style={{ width: '100%', boxSizing: 'border-box', marginTop: 18, padding: 12, borderRadius: 10, border: `1px solid ${isDark ? '#333' : '#ddd'}`, background: isDark ? '#252525' : '#fafafa', color: text }} />
        {status && <p style={{ color: '#34d399', fontSize: 13 }}>{status}</p>}
        {error && <p style={{ color: '#f87171', fontSize: 13 }}>{error}</p>}
        <button disabled={loading || !token} style={{ width: '100%', marginTop: 18, padding: 12, border: 0, borderRadius: 10, background: isDark ? '#f5f5f5' : '#171717', color: isDark ? '#171717' : '#fff', fontWeight: 700 }}>{loading ? 'Updating...' : 'Update Password'}</button>
        <button type="button" onClick={() => { window.location.href = '/'; }} style={{ width: '100%', marginTop: 10, padding: 10, border: 0, background: 'transparent', color: muted }}>Back to sign in</button>
      </form>
    </div>
  );
}
