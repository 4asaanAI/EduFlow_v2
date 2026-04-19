import React, { useState, useEffect, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const SPIN_KEYFRAMES = `
@keyframes cac-spin {
  to { transform: rotate(360deg); }
}
`;

function useDarkMode() {
  const [isDark, setIsDark] = useState(() => {
    const el = document.documentElement;
    return el.getAttribute('data-theme') === 'dark' || el.classList.contains('dark');
  });

  useEffect(() => {
    const observer = new MutationObserver(() => {
      const el = document.documentElement;
      setIsDark(el.getAttribute('data-theme') === 'dark' || el.classList.contains('dark'));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
    return () => observer.disconnect();
  }, []);

  return isDark;
}

// Status: 'pending' | 'loading' | 'confirmed' | 'cancelled' | 'error'

export default function ConfirmActionCard({ action, conversationId, onComplete }) {
  const isDark = useDarkMode();
  const [status, setStatus] = useState('pending');
  const [clickedAction, setClickedAction] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const styleInjected = React.useRef(false);

  useEffect(() => {
    if (styleInjected.current) return;
    styleInjected.current = true;
    const style = document.createElement('style');
    style.textContent = SPIN_KEYFRAMES;
    document.head.appendChild(style);
    return () => { document.head.removeChild(style); };
  }, []);

  const handleClick = useCallback(async (button) => {
    if (status !== 'pending') return;
    setStatus('loading');
    setClickedAction(button.action);
    setErrorMsg('');

    try {
      const res = await fetch(`${API}/chat/conversations/${conversationId}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action_id: action.action_id, decision: button.action, tool: action.tool, params: action.params }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.message || errData?.error || `Request failed (${res.status})`);
      }

      const data = await res.json();
      const outcome = button.action === 'confirm' ? 'confirmed' : 'cancelled';
      setStatus(outcome);

      if (onComplete) {
        onComplete(data);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Something went wrong. Please try again.');
      setStatus('error');
      setClickedAction(null);
    }
  }, [status, conversationId, action.action_id, onComplete]);

  const handleRetry = useCallback(() => {
    setStatus('pending');
    setClickedAction(null);
    setErrorMsg('');
  }, []);

  // --- Outcome icons ---

  const WarningIcon = () => (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M10 2L1 18h18L10 2z" fill={isDark ? 'rgba(251,191,36,0.15)' : 'rgba(251,191,36,0.12)'} stroke="#f59e0b" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M10 8v4" stroke="#f59e0b" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="10" cy="14.5" r="0.75" fill="#f59e0b" />
    </svg>
  );

  const CheckIcon = () => (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="9" cy="9" r="8" fill={isDark ? 'rgba(52,211,153,0.15)' : 'rgba(52,211,153,0.1)'} stroke="#34d399" strokeWidth="1.5" />
      <path d="M5.5 9.5l2.5 2.5 4.5-5" stroke="#34d399" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );

  const CancelIcon = () => (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="9" cy="9" r="8" fill={isDark ? 'rgba(163,163,163,0.12)' : 'rgba(163,163,163,0.08)'} stroke={isDark ? '#737373' : '#a3a3a3'} strokeWidth="1.5" />
      <path d="M6.5 6.5l5 5M11.5 6.5l-5 5" stroke={isDark ? '#737373' : '#a3a3a3'} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );

  const ErrorIcon = () => (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="9" cy="9" r="8" fill={isDark ? 'rgba(239,68,68,0.12)' : 'rgba(239,68,68,0.08)'} stroke="#ef4444" strokeWidth="1.5" />
      <path d="M9 6v4" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="9" cy="13" r="0.75" fill="#ef4444" />
    </svg>
  );

  const Spinner = () => (
    <div style={{
      width: 14,
      height: 14,
      borderRadius: '50%',
      border: '2px solid transparent',
      borderTopColor: '#ffffff',
      borderRightColor: '#ffffff',
      animation: 'cac-spin 0.6s linear infinite',
      flexShrink: 0,
    }} />
  );

  // --- Card styles ---

  const cardStyle = {
    background: isDark ? '#1e1e1e' : '#fffdf7',
    border: `1px solid ${isDark ? '#3a3520' : '#fde68a'}`,
    borderLeft: `3px solid #f59e0b`,
    borderRadius: 12,
    padding: '14px 16px',
    maxWidth: 420,
    transition: 'all 0.2s ease',
  };

  // Completed states override the card style
  if (status === 'confirmed') {
    cardStyle.borderLeftColor = '#34d399';
    cardStyle.border = `1px solid ${isDark ? '#1a3a2a' : '#bbf7d0'}`;
    cardStyle.borderLeft = '3px solid #34d399';
    cardStyle.background = isDark ? '#1a2420' : '#f0fdf4';
  } else if (status === 'cancelled') {
    cardStyle.borderLeftColor = isDark ? '#525252' : '#a3a3a3';
    cardStyle.border = `1px solid ${isDark ? '#2e2e2e' : '#e5e5e5'}`;
    cardStyle.borderLeft = `3px solid ${isDark ? '#525252' : '#a3a3a3'}`;
    cardStyle.background = isDark ? '#1e1e1e' : '#fafafa';
  } else if (status === 'error') {
    cardStyle.borderLeftColor = '#ef4444';
    cardStyle.border = `1px solid ${isDark ? '#3a1a1a' : '#fecaca'}`;
    cardStyle.borderLeft = '3px solid #ef4444';
    cardStyle.background = isDark ? '#1e1a1a' : '#fef2f2';
  }

  const displayTextStyle = {
    fontSize: 13,
    lineHeight: 1.5,
    color: isDark ? '#e5e5e5' : '#1c1917',
    marginTop: 10,
    marginBottom: status === 'pending' || status === 'loading' ? 14 : 0,
    fontWeight: 500,
  };

  const btnBase = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    padding: '7px 16px',
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    border: 'none',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    minWidth: 90,
    lineHeight: 1,
  };

  const getButtonStyle = (button) => {
    const isConfirm = button.action === 'confirm';
    const isDisabled = status === 'loading';
    const isThisLoading = status === 'loading' && clickedAction === button.action;

    if (isConfirm) {
      return {
        ...btnBase,
        background: isDisabled ? (isDark ? '#1a3a2a' : '#bbf7d0') : (isDark ? '#166534' : '#16a34a'),
        color: isDisabled ? (isDark ? '#4ade80' : '#166534') : '#ffffff',
        opacity: isDisabled && !isThisLoading ? 0.5 : 1,
        cursor: isDisabled ? 'not-allowed' : 'pointer',
      };
    }

    return {
      ...btnBase,
      background: isDisabled ? (isDark ? '#252525' : '#f0f0f0') : (isDark ? '#2a2a2a' : '#e5e5e5'),
      color: isDisabled ? (isDark ? '#737373' : '#a3a3a3') : (isDark ? '#d4d4d4' : '#525252'),
      opacity: isDisabled && !isThisLoading ? 0.5 : 1,
      cursor: isDisabled ? 'not-allowed' : 'pointer',
    };
  };

  const outcomeStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginTop: 12,
    fontSize: 12,
    fontWeight: 500,
  };

  // --- Render ---

  // Completed / Error states
  if (status === 'confirmed' || status === 'cancelled' || status === 'error') {
    return (
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
          {status === 'confirmed' && <CheckIcon />}
          {status === 'cancelled' && <CancelIcon />}
          {status === 'error' && <ErrorIcon />}
          <div style={{ flex: 1 }}>
            <div style={{
              fontSize: 13,
              lineHeight: 1.5,
              color: isDark ? '#a0a0a0' : '#78716c',
              fontWeight: 400,
              textDecoration: status === 'cancelled' ? 'line-through' : 'none',
              opacity: status === 'cancelled' ? 0.7 : 1,
            }}>
              {action.display}
            </div>
            <div style={{
              ...outcomeStyle,
              color: status === 'confirmed'
                ? '#34d399'
                : status === 'error'
                  ? '#ef4444'
                  : (isDark ? '#737373' : '#a3a3a3'),
            }}>
              {status === 'confirmed' && 'Action confirmed and executed'}
              {status === 'cancelled' && 'Action cancelled'}
              {status === 'error' && (
                <span>
                  {errorMsg}
                  <button
                    onClick={handleRetry}
                    style={{
                      marginLeft: 8,
                      background: 'none',
                      border: 'none',
                      color: '#4f8ff7',
                      cursor: 'pointer',
                      fontSize: 12,
                      fontWeight: 600,
                      textDecoration: 'underline',
                      padding: 0,
                    }}
                  >
                    Retry
                  </button>
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Pending / Loading state
  return (
    <div style={cardStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <WarningIcon />
        <span style={{
          fontSize: 11,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          color: '#f59e0b',
        }}>
          Confirmation Required
        </span>
      </div>
      <div style={displayTextStyle}>
        {action.display}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        {(action.buttons || []).map((button, i) => (
          <button
            key={button.action || i}
            onClick={() => handleClick(button)}
            disabled={status === 'loading'}
            style={getButtonStyle(button)}
            onMouseEnter={(e) => {
              if (status !== 'loading') {
                e.currentTarget.style.opacity = '0.85';
              }
            }}
            onMouseLeave={(e) => {
              if (status !== 'loading') {
                e.currentTarget.style.opacity = '1';
              }
            }}
          >
            {status === 'loading' && clickedAction === button.action && <Spinner />}
            {button.label}
          </button>
        ))}
      </div>
    </div>
  );
}
