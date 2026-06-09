import React, { useState } from 'react';
import { KeyRound, Loader2, Eye, EyeOff } from 'lucide-react';
import { changePassword } from '../lib/api';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';

export default function ChangePassword() {
  const { clearMustChangePassword } = useUser();
  const { isDark } = useTheme();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const bg = isDark ? '#111111' : '#f5f5f5';
  const card = isDark ? '#1a1a1a' : '#ffffff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#525252';
  const inputBg = isDark ? '#252525' : '#fafafa';
  const inputBorder = isDark ? '#333' : '#e5e5e5';
  const accent = '#4f8ff7';

  const inputWrapStyle = { position: 'relative' };
  const inputStyle = {
    width: '100%', padding: '12px 42px 12px 14px', background: inputBg,
    border: `1px solid ${inputBorder}`, borderRadius: 10, color: text,
    fontSize: 15, outline: 'none', boxSizing: 'border-box',
    transition: 'border-color 0.2s ease',
  };
  const toggleBtnStyle = {
    position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
    background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: muted,
    display: 'flex', alignItems: 'center',
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      const data = await changePassword(currentPassword, newPassword);
      if (!data.success) {
        setError(data.detail || 'Password change failed');
        return;
      }
      clearMustChangePassword();
      window.location.replace('/');
    } catch (err) {
      setError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: bg,
    }}>
      <div style={{
        width: '100%', maxWidth: 420, background: card,
        borderRadius: 20, border: `1px solid ${border}`,
        padding: '40px 36px', boxShadow: isDark ? '0 8px 32px rgba(0,0,0,0.4)' : '0 8px 32px rgba(0,0,0,0.08)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 16,
            background: `${accent}22`, display: 'flex',
            alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px',
          }}>
            <KeyRound size={24} color={accent} />
          </div>
          <h1 style={{ color: text, fontSize: 22, fontWeight: 700, margin: 0 }}>
            Set Your Password
          </h1>
          <p style={{ color: muted, fontSize: 14, marginTop: 8 }}>
            Choose a secure password to continue
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', color: muted, fontSize: 13, marginBottom: 6 }}>
              Current Password
            </label>
            <div style={inputWrapStyle}>
              <input
                type={showCurrent ? 'text' : 'password'}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Your current password"
                style={inputStyle}
                required
              />
              <button type="button" onClick={() => setShowCurrent(!showCurrent)} style={toggleBtnStyle}>
                {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', color: muted, fontSize: 13, marginBottom: 6 }}>
              New Password
            </label>
            <div style={inputWrapStyle}>
              <input
                type={showNew ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Min. 8 characters"
                style={inputStyle}
                required
              />
              <button type="button" onClick={() => setShowNew(!showNew)} style={toggleBtnStyle}>
                {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', color: muted, fontSize: 13, marginBottom: 6 }}>
              Confirm New Password
            </label>
            <div style={inputWrapStyle}>
              <input
                type={showConfirm ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter new password"
                style={inputStyle}
                required
              />
              <button type="button" onClick={() => setShowConfirm(!showConfirm)} style={toggleBtnStyle}>
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {error && (
            <div style={{
              padding: '10px 14px', background: '#ef444420', border: '1px solid #ef4444',
              borderRadius: 8, color: '#ef4444', fontSize: 14,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '13px', borderRadius: 12, border: 'none',
              background: loading ? '#333' : accent, color: '#fff',
              fontSize: 15, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s ease', display: 'flex', alignItems: 'center',
              justifyContent: 'center', gap: 8, marginTop: 4,
            }}
          >
            {loading && <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />}
            {loading ? 'Saving...' : 'Set Password & Continue'}
          </button>
        </form>
      </div>
    </div>
  );
}
