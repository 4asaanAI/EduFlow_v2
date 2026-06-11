import React, { useState, useEffect } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { X, Info, AlertTriangle, CheckCircle, AlertCircle, Clock, User, Tag, ArrowRight } from 'lucide-react';
import { getAuthHeaders } from '../lib/authSession';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const TYPE_META = {
  info:    { color: '#4f8ff7', Icon: Info },
  warning: { color: '#f59e0b', Icon: AlertTriangle },
  success: { color: '#10b981', Icon: CheckCircle },
  error:   { color: '#ef4444', Icon: AlertCircle },
  leave_decision: { color: '#a78bfa', Icon: CheckCircle },
};

const STATUS_COLORS = {
  pending:     { color: '#f59e0b', bg: 'color-mix(in srgb, #f59e0b 12%, transparent)', border: 'color-mix(in srgb, #f59e0b 30%, transparent)' },
  open:        { color: '#f59e0b', bg: 'color-mix(in srgb, #f59e0b 12%, transparent)', border: 'color-mix(in srgb, #f59e0b 30%, transparent)' },
  active:      { color: '#4f8ff7', bg: 'color-mix(in srgb, #4f8ff7 12%, transparent)', border: 'color-mix(in srgb, #4f8ff7 30%, transparent)' },
  in_progress: { color: '#4f8ff7', bg: 'color-mix(in srgb, #4f8ff7 12%, transparent)', border: 'color-mix(in srgb, #4f8ff7 30%, transparent)' },
  approved:    { color: '#10b981', bg: 'color-mix(in srgb, #10b981 12%, transparent)', border: 'color-mix(in srgb, #10b981 30%, transparent)' },
  resolved:    { color: '#10b981', bg: 'color-mix(in srgb, #10b981 12%, transparent)', border: 'color-mix(in srgb, #10b981 30%, transparent)' },
  closed:      { color: '#10b981', bg: 'color-mix(in srgb, #10b981 12%, transparent)', border: 'color-mix(in srgb, #10b981 30%, transparent)' },
  paid:        { color: '#10b981', bg: 'color-mix(in srgb, #10b981 12%, transparent)', border: 'color-mix(in srgb, #10b981 30%, transparent)' },
  completed:   { color: '#10b981', bg: 'color-mix(in srgb, #10b981 12%, transparent)', border: 'color-mix(in srgb, #10b981 30%, transparent)' },
  rejected:    { color: '#ef4444', bg: 'color-mix(in srgb, #ef4444 12%, transparent)', border: 'color-mix(in srgb, #ef4444 30%, transparent)' },
  overdue:     { color: '#ef4444', bg: 'color-mix(in srgb, #ef4444 12%, transparent)', border: 'color-mix(in srgb, #ef4444 30%, transparent)' },
};

const EVENT_COLORS = {
  created:       '#737373',
  leave_approved:  '#10b981',
  leave_rejected:  '#ef4444',
  leave_created:   '#4f8ff7',
  facility_resolved: '#10b981',
  facility_created:  '#4f8ff7',
  incident_resolved: '#10b981',
  incident_created:  '#f59e0b',
  cert_approved:   '#10b981',
  cert_rejected:   '#ef4444',
  cert_created:    '#4f8ff7',
  substitution_assigned: '#a78bfa',
  fee_paid:        '#10b981',
  fee_overdue:     '#ef4444',
  approval_approved: '#10b981',
  approval_rejected: '#ef4444',
  status_change:   '#4f8ff7',
};

function fmtTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso.slice(0, 16).replace('T', ' ');
  }
}

function fmtDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch {
    return iso.slice(0, 10);
  }
}

function relativeTime(iso) {
  if (!iso) return '';
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    if (d < 7) return `${d}d ago`;
    return fmtDate(iso);
  } catch {
    return '';
  }
}

function StatusBadge({ status, isDark }) {
  if (!status) return null;
  const cfg = STATUS_COLORS[status] || { color: '#737373', bg: 'color-mix(in srgb, #737373 12%, transparent)', border: 'color-mix(in srgb, #737373 30%, transparent)' };
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, letterSpacing: '0.06em',
      padding: '3px 9px', borderRadius: 20,
      color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}`,
      textTransform: 'uppercase',
    }}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}

function TimelineEvent({ event, isLast, isDark }) {
  const color = EVENT_COLORS[event.event_type] || (event.is_current ? '#10b981' : '#737373');
  const dotBg = event.is_current ? color : 'var(--c-bg)';
  const dotBorder = color;

  return (
    <div style={{ display: 'flex', gap: 0, position: 'relative' }}>
      {/* Connector column */}
      <div style={{ width: 32, flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{
          width: 12, height: 12, borderRadius: '50%',
          background: dotBg, border: `2px solid ${dotBorder}`,
          flexShrink: 0, marginTop: 2, zIndex: 1,
          boxShadow: event.is_current ? `0 0 0 3px ${color}20` : 'none',
          transition: 'all 0.2s',
        }} />
        {!isLast && (
          <div style={{
            width: 2, flex: 1, minHeight: 24,
            background: `linear-gradient(to bottom, ${dotBorder}40, var(--c-border))`,
            marginTop: 3,
          }} />
        )}
      </div>

      {/* Content */}
      <div style={{ flex: 1, paddingBottom: isLast ? 0 : 20, paddingLeft: 12 }}>
        <div style={{
          background: event.is_current
            ? `color-mix(in srgb, ${color} 6%, var(--c-bg))`
            : 'var(--c-bg)',
          border: `1px solid ${event.is_current ? `color-mix(in srgb, ${color} 25%, transparent)` : 'var(--c-border)'}`,
          borderRadius: 10, padding: '10px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: event.is_current ? color : 'var(--c-text)', lineHeight: 1.3, marginBottom: event.detail || event.actor ? 5 : 0 }}>
                {event.label}
              </div>
              {event.detail && (
                <div style={{ fontSize: 12, color: 'var(--c-muted)', lineHeight: 1.5, marginBottom: event.actor ? 5 : 0 }}>
                  {event.detail}
                </div>
              )}
              {event.actor && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <User size={10} color="var(--c-faint)" />
                  <span style={{ fontSize: 11, color: 'var(--c-faint)' }}>
                    {event.actor}{event.actor_role ? ` · ${event.actor_role.replace(/_/g, ' ')}` : ''}
                  </span>
                </div>
              )}
            </div>
            <div style={{ flexShrink: 0, textAlign: 'right' }}>
              {event.timestamp && (
                <div style={{ fontSize: 10, color: 'var(--c-faint)', whiteSpace: 'nowrap' }}>
                  {relativeTime(event.timestamp)}
                </div>
              )}
              {event.timestamp && (
                <div style={{ fontSize: 9, color: 'var(--c-faint)', marginTop: 2, opacity: 0.7, whiteSpace: 'nowrap' }}>
                  {fmtTime(event.timestamp)}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SourceCard({ source, isDark }) {
  if (!source) return null;
  const status = source.status || '';
  const typeLabel = source.source_type?.replace(/_/g, ' ') || '';

  return (
    <div style={{
      background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 12,
      padding: '14px 16px', marginBottom: 20,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: source.subtitle || source.detail ? 10 : 0 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.07em',
              padding: '2px 7px', borderRadius: 4,
              color: '#737373', background: 'color-mix(in srgb, #737373 10%, transparent)',
              border: '1px solid color-mix(in srgb, #737373 20%, transparent)',
              textTransform: 'uppercase',
            }}>{typeLabel}</span>
            <StatusBadge status={status} isDark={isDark} />
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--c-text)', lineHeight: 1.3 }}>
            {source.title}
          </div>
        </div>
      </div>
      {source.subtitle && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 5 }}>
          <Tag size={10} color="var(--c-faint)" />
          <span style={{ fontSize: 12, color: 'var(--c-muted)' }}>{source.subtitle}</span>
        </div>
      )}
      {source.detail && source.detail.length > 0 && (
        <div style={{
          marginTop: 8, fontSize: 12, color: 'var(--c-muted)', lineHeight: 1.5,
          padding: '8px 12px', borderRadius: 7,
          background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.025)',
          border: '1px solid var(--c-border)',
          display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>
          {source.detail}
        </div>
      )}
    </div>
  );
}

export default function NotificationDetailModal({ notification, onClose }) {
  const { isDark } = useTheme();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isDigest = !notification?.id || notification?.is_digest;
  const typeMeta = TYPE_META[notification?.type] || TYPE_META.info;
  const TypeIcon = typeMeta.Icon;
  const typeColor = typeMeta.color;

  useEffect(() => {
    if (isDigest) return;
    setLoading(true);
    setError('');
    fetch(`${API}/notifications/${notification.id}/detail`, { headers: getAuthHeaders(null) })
      .then(r => r.json())
      .then(r => {
        if (r.success) setDetail(r.data);
        else setError('Could not load details.');
      })
      .catch(() => setError('Network error.'))
      .finally(() => setLoading(false));
  }, [notification?.id, isDigest]);

  const notif = detail?.notification || notification;
  const source = detail?.source || null;
  const timeline = detail?.timeline || [];

  const bg = isDark ? '#111' : '#f8f9fb';
  const surface = isDark ? '#161616' : '#ffffff';
  const border = isDark ? '#222' : '#e5e7eb';

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 600,
        background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '16px',
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <style>{`
        @media (max-width: 560px) {
          .notif-detail-modal {
            border-radius: 20px !important;
            max-height: 95vh !important;
          }
        }
      `}</style>
      <div
        className="fade-in-scale notif-detail-modal"
        style={{
          background: bg, border: `1px solid ${border}`,
          borderRadius: 24, width: '100%', maxWidth: 520,
          maxHeight: '88vh', display: 'flex', flexDirection: 'column',
          boxShadow: isDark
            ? '0 32px 100px rgba(0,0,0,0.75), 0 4px 20px rgba(0,0,0,0.5)'
            : '0 32px 100px rgba(0,0,0,0.12), 0 4px 20px rgba(0,0,0,0.06)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '20px 22px 16px',
          background: surface,
          borderBottom: `1px solid ${border}`,
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
            <div style={{
              width: 42, height: 42, borderRadius: 13, flexShrink: 0,
              background: `color-mix(in srgb, ${typeColor} 12%, transparent)`,
              border: `1.5px solid color-mix(in srgb, ${typeColor} 35%, transparent)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <TypeIcon size={19} color={typeColor} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--c-text)', lineHeight: 1.3, letterSpacing: '-0.01em' }}>
                {notif?.title || 'Notification'}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 5, flexWrap: 'wrap' }}>
                {notif?.created_at && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Clock size={10} color="var(--c-faint)" />
                    <span style={{ fontSize: 11, color: 'var(--c-faint)' }}>{fmtTime(notif.created_at)}</span>
                  </div>
                )}
                {notif?.time && !notif?.created_at && (
                  <span style={{ fontSize: 11, color: 'var(--c-faint)' }}>{notif.time}</span>
                )}
                {notif?.read_at && (
                  <span style={{
                    fontSize: 10, fontWeight: 600, color: '#10b981',
                    background: 'color-mix(in srgb, #10b981 10%, transparent)',
                    border: '1px solid color-mix(in srgb, #10b981 25%, transparent)',
                    padding: '1px 7px', borderRadius: 20,
                  }}>Read</span>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              style={{
                background: isDark ? '#222' : '#f3f4f6', border: 'none', color: 'var(--c-muted)',
                cursor: 'pointer', padding: 7, borderRadius: 9, flexShrink: 0,
                display: 'flex', alignItems: 'center',
              }}
            >
              <X size={14} />
            </button>
          </div>

          {/* Message */}
          {notif?.message && notif.message !== notif.title && (
            <div style={{
              marginTop: 12, padding: '10px 14px', borderRadius: 10,
              background: `color-mix(in srgb, ${typeColor} 6%, transparent)`,
              border: `1px solid color-mix(in srgb, ${typeColor} 20%, transparent)`,
              fontSize: 13, color: 'var(--c-text)', lineHeight: 1.55,
            }}>
              {notif.message}
            </div>
          )}
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 22px 24px' }}>
          {loading ? (
            <div style={{ padding: '32px 0', textAlign: 'center' }}>
              <div className="spinner" style={{ width: 20, height: 20, margin: '0 auto 10px' }} />
              <div style={{ fontSize: 13, color: 'var(--c-muted)' }}>Loading history…</div>
            </div>
          ) : error ? (
            <div style={{ padding: '24px 0', textAlign: 'center', color: '#ef4444', fontSize: 13 }}>{error}</div>
          ) : (
            <>
              {/* Source record card */}
              {source && <SourceCard source={source} isDark={isDark} />}

              {/* Timeline */}
              {timeline.length > 0 ? (
                <div>
                  <div style={{
                    fontSize: 11, fontWeight: 700, letterSpacing: '0.07em',
                    color: 'var(--c-faint)', textTransform: 'uppercase', marginBottom: 14,
                  }}>
                    Activity Timeline
                  </div>
                  {timeline.map((ev, idx) => (
                    <TimelineEvent
                      key={idx}
                      event={ev}
                      isLast={idx === timeline.length - 1}
                      isDark={isDark}
                    />
                  ))}
                </div>
              ) : isDigest ? (
                <div style={{
                  padding: '20px', borderRadius: 12,
                  background: `color-mix(in srgb, ${typeColor} 6%, var(--c-bg))`,
                  border: `1px solid color-mix(in srgb, ${typeColor} 20%, transparent)`,
                  fontSize: 13, color: 'var(--c-muted)', lineHeight: 1.6,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
                    <ArrowRight size={13} color={typeColor} />
                    <span style={{ fontWeight: 600, color: 'var(--c-text)', fontSize: 13 }}>Live summary alert</span>
                  </div>
                  This is a real-time digest item generated from current school data. Click the notification to navigate to the relevant section for full details.
                </div>
              ) : (
                <div style={{ padding: '20px 0', textAlign: 'center', color: 'var(--c-muted)', fontSize: 13 }}>
                  No activity history available for this notification.
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {notif?.id && (
          <div style={{
            padding: '10px 22px 14px',
            borderTop: `1px solid ${border}`,
            background: surface,
            flexShrink: 0,
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: notif?.read ? '#10b981' : typeColor,
              flexShrink: 0,
            }} />
            <span style={{ fontSize: 11, color: 'var(--c-faint)' }}>
              {notif?.read ? `Read ${notif.read_at ? relativeTime(notif.read_at) : ''}` : 'Unread'}
              {notif?.source_record_type ? ` · ${notif.source_record_type.replace(/_/g, ' ')}` : ''}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
