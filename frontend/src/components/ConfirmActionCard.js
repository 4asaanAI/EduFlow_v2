import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getAuthHeaders } from '../lib/authSession';

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

// Status: 'pending' | 'loading' | 'confirmed' | 'cancelled' | 'error' | 'rate_limited'

// I.2: map the backend 409/502/500 failure taxonomy to a specific, human message
// and whether re-confirming the SAME token can help. The backend nests the code
// under `detail` (FastAPI HTTPException), e.g. {"detail": {"code, message}}; a
// 500 detail is an opaque string with a correlation id.
function classifyConfirmError(httpStatus, body) {
  const detail = body && typeof body === 'object' ? body.detail : null;
  const code = detail && typeof detail === 'object'
    ? detail.code
    : (body && typeof body === 'object' ? body.code : null);
  const serverMsg = detail && typeof detail === 'object' ? detail.message : null;
  // A correlation id may arrive as a top-level field, nested in the detail
  // object, OR embedded in an opaque 500 detail string like
  // "An internal error occurred (id=abc-123)". Extract it without surfacing the
  // rest of the (internal) string.
  let correlationId = null;
  if (body && typeof body === 'object') {
    correlationId = body.correlation_id
      || (detail && typeof detail === 'object' ? detail.correlation_id : null)
      || null;
    if (!correlationId && typeof detail === 'string') {
      const m = detail.match(/id=([\w-]+)/i);
      if (m) correlationId = m[1];
    }
  }

  switch (code) {
    case 'plan_tampered':
      return {
        kind: code,
        message: serverMsg
          || 'The approved plan could not be verified. Please ask me to prepare it again, then confirm.',
        // The token is spent/invalid — re-posting it can't help. Re-ask instead.
        retryable: false,
      };
    case 'plan_stale':
      return {
        kind: code,
        message: serverMsg
          || 'The data changed since you reviewed this plan. Please ask me to re-plan it.',
        retryable: false,
      };
    case 'plan_expired':
      return {
        kind: code,
        message: serverMsg
          || 'This plan expired before it was confirmed. Just ask again and I\'ll rebuild it.',
        retryable: false,
      };
    case 'needs_manual_reconciliation':
      return {
        kind: code,
        message: serverMsg
          || 'Part of this could not be completed safely. Nothing was applied — this needs manual attention in the relevant panel.',
        retryable: false,
      };
    case 'side_effect_failed':
      return {
        kind: code,
        message: serverMsg
          || 'The records were updated but a follow-up step (e.g. a notification) failed. Please check the panel before retrying.',
        retryable: false,
      };
    default:
      // Opaque / unexpected failure: surface NO internal detail beyond a
      // correlation id the user can quote to support.
      return {
        kind: 'opaque',
        message: correlationId
          ? `Nothing was applied because something went wrong. Reference: ${correlationId}`
          : 'Nothing was applied because something went wrong. Please try again in a moment.',
        // A transient/opaque failure can be re-attempted; the token may still be live.
        retryable: httpStatus >= 500,
        correlationId,
      };
  }
}

function formatParamKey(key) {
  return String(key || '')
    .replace(/^_+/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, char => char.toUpperCase());
}

function formatParamValue(value) {
  if (value == null || value === '') return 'Not provided';
  if (Array.isArray(value)) return `${value.length} item${value.length === 1 ? '' : 's'}`;
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function DestructiveBadge({ isDark }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      marginLeft: 6,
      padding: '1px 6px',
      borderRadius: 6,
      fontSize: 10,
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.03em',
      color: isDark ? '#fca5a5' : '#b91c1c',
      background: isDark ? 'rgba(239,68,68,0.12)' : 'rgba(239,68,68,0.08)',
      border: `1px solid ${isDark ? '#3a1a1a' : '#fecaca'}`,
    }}>
      Destructive
    </span>
  );
}

// I.1: renders the ordered steps of a multi-step plan under one confirm/cancel.
function PlanSteps({ steps, isDark, muted }) {
  const ordered = (steps || []).filter(Boolean);
  if (ordered.length === 0) return null;
  return (
    <ol
      data-testid="confirm-plan-steps"
      style={{
        listStyle: 'none',
        margin: '4px 0 12px',
        padding: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        opacity: muted ? 0.7 : 1,
      }}
    >
      {ordered.map((step, i) => (
        <li
          key={step.idx != null ? step.idx : i}
          data-testid={`confirm-plan-step-${i}`}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 8,
            background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.55)',
            border: `1px solid ${isDark ? '#2e2e2e' : '#f3e8b5'}`,
            borderRadius: 8,
            padding: '7px 10px',
          }}
        >
          <span style={{
            flexShrink: 0,
            width: 18,
            height: 18,
            borderRadius: '50%',
            background: isDark ? '#3a3520' : '#fde68a',
            color: isDark ? '#fbbf24' : '#92400e',
            fontSize: 11,
            fontWeight: 700,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginTop: 1,
          }}>
            {i + 1}
          </span>
          <span style={{
            flex: 1,
            minWidth: 0,
            color: isDark ? '#d4d4d4' : '#292524',
            fontSize: 12,
            lineHeight: 1.45,
          }}>
            {step.display || step.tool}
            {step.destructive && <DestructiveBadge isDark={isDark} />}
          </span>
        </li>
      ))}
    </ol>
  );
}

function ActionDetails({ params, isDark }) {
  const entries = Object.entries(params || {})
    .filter(([key]) => !key.startsWith('_'))
    .slice(0, 6);

  if (entries.length === 0) return null;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'minmax(92px, 0.45fr) minmax(0, 1fr)',
      gap: '6px 10px',
      background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.55)',
      border: `1px solid ${isDark ? '#2e2e2e' : '#f3e8b5'}`,
      borderRadius: 8,
      padding: '9px 10px',
      marginBottom: 12,
    }}>
      {entries.map(([key, value]) => (
        <React.Fragment key={key}>
          <span style={{ color: isDark ? '#737373' : '#78716c', fontSize: 11, fontWeight: 600 }}>
            {formatParamKey(key)}
          </span>
          <span style={{
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            color: isDark ? '#d4d4d4' : '#292524',
            fontSize: 12,
          }}>
            {formatParamValue(value)}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
}

export default function ConfirmActionCard({ action, conversationId, sessionId, onComplete }) {
  const isDark = useDarkMode();
  const isPlan = action.is_plan === true && Array.isArray(action.steps);
  const [status, setStatus] = useState('pending');
  const [clickedAction, setClickedAction] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [errorRetryable, setErrorRetryable] = useState(true);
  const [secondsLeft, setSecondsLeft] = useState(action.expires_in_seconds || null);
  const [rateLimitSecondsLeft, setRateLimitSecondsLeft] = useState(0);
  const [rateLimitInfo, setRateLimitInfo] = useState(null);
  const [showProgressLabel, setShowProgressLabel] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const styleInjected = useRef(false);

  useEffect(() => {
    if (styleInjected.current) return;
    styleInjected.current = true;
    const style = document.createElement('style');
    style.textContent = SPIN_KEYFRAMES;
    document.head.appendChild(style);
    return () => { document.head.removeChild(style); };
  }, []);

  useEffect(() => {
    setSecondsLeft(action.expires_in_seconds || null);
  }, [action.action_id, action.expires_in_seconds]);

  useEffect(() => {
    if (status !== 'pending' || secondsLeft == null) return undefined;
    if (secondsLeft <= 0) {
      setStatus('error');
      setErrorMsg('This confirmation expired. Please ask EduFlow to prepare the action again.');
      return undefined;
    }
    const timer = window.setTimeout(() => setSecondsLeft(prev => (prev == null ? prev : prev - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [secondsLeft, status]);

  // Rate-limit cooldown: tick down and re-arm the confirm button at zero.
  useEffect(() => {
    if (status !== 'rate_limited') return undefined;
    if (rateLimitSecondsLeft <= 0) {
      setStatus('pending');
      setRateLimitInfo(null);
      return undefined;
    }
    const timer = window.setTimeout(() => setRateLimitSecondsLeft(prev => Math.max(0, prev - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [status, rateLimitSecondsLeft]);

  useEffect(() => {
    if (status !== 'loading') {
      setShowProgressLabel(false);
      return undefined;
    }
    const timer = window.setTimeout(() => setShowProgressLabel(true), 2000);
    return () => window.clearTimeout(timer);
  }, [status]);

  const handleClick = useCallback(async (button) => {
    // During rate-limited cooldown the cancel button must still work; only
    // confirm is blocked. handleCancel paths through here with button.action
    // === 'cancel' which we accept.
    if (submittingRef.current) return;
    if (status === 'loading') return;
    if (status === 'rate_limited' && button.action === 'confirm') return;
    if (status !== 'pending' && status !== 'rate_limited') return;
    submittingRef.current = true;
    setIsSubmitting(true);
    setStatus('loading');
    setClickedAction(button.action);
    setErrorMsg('');

    try {
      const res = await fetch(`${API}/chat/conversations/${conversationId}/confirm`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_id: action.action_id,
          token: action.token || action.action_id,
          decision: button.action,
          confirmed: button.action === 'confirm',
          tool: action.tool,
          params: action.params,
          session_id: sessionId || conversationId,
        }),
      });

      if (res.status === 429) {
        // Rate-limited. Read Retry-After header (seconds) — fall back to body.
        const errData = await res.json().catch(() => null);
        const headerRetry = parseInt(res.headers.get('Retry-After') || '', 10);
        const bodyRetry = parseInt(errData?.retry_after_seconds, 10);
        const retrySecs = Number.isFinite(headerRetry) && headerRetry > 0
          ? headerRetry
          : (Number.isFinite(bodyRetry) && bodyRetry > 0 ? bodyRetry : 60);
        setRateLimitInfo({ limit: errData?.limit, window: errData?.window || 'hour' });
        setRateLimitSecondsLeft(retrySecs);
        setStatus('rate_limited');
        setClickedAction(null);
        return;
      }

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        const classified = classifyConfirmError(res.status, errData);
        setErrorMsg(classified.message);
        setErrorRetryable(classified.retryable);
        setStatus('error');
        setClickedAction(null);
        return;
      }

      const data = await res.json();
      const outcome = button.action === 'confirm' ? 'confirmed' : 'cancelled';
      setStatus(outcome);

      if (onComplete) {
        onComplete(data);
      }
    } catch (err) {
      // Network/transport failure (fetch rejected) — no server response to
      // classify. Safe to re-attempt with the same token.
      setErrorMsg(err.message || 'Something went wrong. Please try again.');
      setErrorRetryable(true);
      setStatus('error');
      setClickedAction(null);
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }, [status, conversationId, sessionId, action.action_id, action.token, action.tool, action.params, onComplete]);

  const handleRetry = useCallback(() => {
    setStatus('pending');
    setClickedAction(null);
    setErrorMsg('');
    setErrorRetryable(true);
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
  if (status === 'rate_limited') {
    cardStyle.borderLeftColor = '#f59e0b';
    cardStyle.border = `1px solid ${isDark ? '#3a3520' : '#fde68a'}`;
    cardStyle.borderLeft = '3px solid #f59e0b';
    cardStyle.background = isDark ? '#241f15' : '#fffbeb';
  } else if (status === 'confirmed') {
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
    // Confirm is locked during loading AND during rate-limit cooldown.
    // Cancel is locked only during loading (it stays live during rate-limit
    // so the user can dismiss the action).
    const isLocked = isConfirm
      ? (status === 'loading' || status === 'rate_limited' || isSubmitting)
      : (status === 'loading' || isSubmitting);
    const isThisLoading = status === 'loading' && clickedAction === button.action;

    if (isConfirm) {
      return {
        ...btnBase,
        background: isLocked ? (isDark ? '#1a3a2a' : '#bbf7d0') : (isDark ? '#166534' : '#16a34a'),
        color: isLocked ? (isDark ? '#4ade80' : '#166534') : '#ffffff',
        opacity: isLocked && !isThisLoading ? 0.5 : 1,
        cursor: isLocked ? 'not-allowed' : 'pointer',
      };
    }

    return {
      ...btnBase,
      background: isLocked ? (isDark ? '#252525' : '#f0f0f0') : (isDark ? '#2a2a2a' : '#e5e5e5'),
      color: isLocked ? (isDark ? '#737373' : '#a3a3a3') : (isDark ? '#d4d4d4' : '#525252'),
      opacity: isLocked && !isThisLoading ? 0.5 : 1,
      cursor: isLocked ? 'not-allowed' : 'pointer',
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
            {isPlan
              ? <PlanSteps steps={action.steps} isDark={isDark} muted={status === 'cancelled'} />
              : (action.params && <ActionDetails params={action.params} isDark={isDark} />)}
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
                  {errorRetryable && (
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
                  )}
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
    <div style={cardStyle} data-testid={`confirm-action-card-${status}`}>
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
      {isPlan
        ? <PlanSteps steps={action.steps} isDark={isDark} />
        : <ActionDetails params={action.params} isDark={isDark} />}
      {status === 'rate_limited' && (
        <div data-testid="confirm-rate-limit-notice" style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 10px',
          marginBottom: 12,
          borderRadius: 8,
          background: isDark ? 'rgba(251,191,36,0.08)' : 'rgba(251,191,36,0.12)',
          border: `1px solid ${isDark ? '#3a3520' : '#fde68a'}`,
          color: isDark ? '#fbbf24' : '#92400e',
          fontSize: 12,
          fontWeight: 500,
        }}>
          <WarningIcon />
          <span>
            Too many AI actions — please wait {Math.max(1, Math.ceil(rateLimitSecondsLeft / 60))} minute{Math.max(1, Math.ceil(rateLimitSecondsLeft / 60)) === 1 ? '' : 's'}
            {rateLimitInfo?.limit != null && (
              <span style={{ opacity: 0.7 }}> (limit: {rateLimitInfo.limit}/hour)</span>
            )}
          </span>
        </div>
      )}
      <div style={{ display: 'flex', gap: 8 }}>
        {(action.buttons || []).map((button, i) => (
          <button
            key={button.action || i}
            onClick={() => handleClick(button)}
            disabled={isSubmitting || status === 'loading' || (status === 'rate_limited' && button.action === 'confirm')}
            style={getButtonStyle(button)}
            onMouseEnter={(e) => {
              const buttonLocked = isSubmitting
                || status === 'loading'
                || (status === 'rate_limited' && button.action === 'confirm');
              if (!buttonLocked) {
                e.currentTarget.style.opacity = '0.85';
              }
            }}
            onMouseLeave={(e) => {
              const buttonLocked = isSubmitting
                || status === 'loading'
                || (status === 'rate_limited' && button.action === 'confirm');
              if (!buttonLocked) {
                e.currentTarget.style.opacity = '1';
              }
            }}
          >
            {status === 'loading' && clickedAction === button.action && <Spinner />}
            {button.label}
          </button>
        ))}
      </div>
      {showProgressLabel && status === 'loading' && (
        <div role="status" aria-live="polite" style={{
          marginTop: 10,
          fontSize: 12,
          color: isDark ? '#a0a0a0' : '#78716c',
        }}>
          Applying changes...
        </div>
      )}
      {secondsLeft != null && status === 'pending' && (
        <div style={{
          marginTop: 10,
          fontSize: 11,
          color: isDark ? '#737373' : '#a3a3a3',
        }}>
          Expires in {Math.max(0, secondsLeft)}s
        </div>
      )}
    </div>
  );
}
