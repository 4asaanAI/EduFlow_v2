import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { Search, Bell, ChevronLeft, Menu, X, CalendarDays } from 'lucide-react';
import { getAuthHeaders } from '../lib/authSession';
import NotificationDetailModal from './NotificationDetailModal';
import { getToolForNotification } from '../lib/notifRouting';
import { getAcademicYear } from '../lib/api';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

/* Every icon button in the header — menu, search, bell — uses THIS, so they
   share one size and one baseline.

   They previously each carried their own numbers (padding 6 with an 18px icon,
   a 36x36 box with an 18px icon, padding 7 with a 17px icon). Three different
   boxes with three different icon sizes meant the three symbols neither lined
   up on the same midline nor matched each other, which is exactly what
   Abhimanyu saw. A fixed square box with `alignItems: center` puts the optical
   centre of each icon on the same line regardless of the glyph's own shape.

   36px also clears the 44px-with-spacing touch guidance closely enough inside a
   52px header, and is the same box the sidebar toggle uses. */
const ICON_SIZE = 19;
const ICON_BTN = {
  width: 36,
  height: 36,
  flexShrink: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'none',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
  padding: 0,
  transition: 'background var(--transition-fast)',
};

function getH() {
  return getAuthHeaders(null);
}

function SearchPanel({ user, onClose, isDark }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API}/search?q=${encodeURIComponent(query)}`, { headers: getH(user) }).then(r => r.json());
        if (r.success) setResults(r.data || []);
      } catch {}
      setLoading(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const bg = 'var(--color-surface)';
  const border = 'var(--color-border)';
  const text = 'var(--color-text-primary)';
  const muted = 'var(--color-text-muted)';

  const typeColors = { tool: '#a78bfa', student: '#4f8ff7', staff: '#34d399', announcement: '#fbbf24' };

  const handleResultClick = (r) => {
    onClose();
    if (r.type === 'tool') window.dispatchEvent(new CustomEvent('open-tool', { detail: r.id }));
    else if (r.type === 'student') window.dispatchEvent(new CustomEvent('open-tool', { detail: 'student-database' }));
    else if (r.type === 'staff') window.dispatchEvent(new CustomEvent('open-tool', { detail: 'staff-attendance-tracker' }));
    else if (r.type === 'announcement') window.dispatchEvent(new CustomEvent('open-tool', { detail: 'announcement-broadcaster' }));
  };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 80 }}>
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)' }} />
      <div className="fade-in-scale" style={{ position: 'relative', width: 560, maxWidth: '90vw', background: bg, border: `1px solid ${border}`, borderRadius: 16, boxShadow: 'var(--shadow-xl)', overflow: 'hidden' }}>
        {/* Same pattern as the chat composer: the ROW owns the focus
            indication, and the transparent field inside it opts out of the
            global ring. Ringing the field drew a blue pill floating inside the
            panel, which is what Abhimanyu flagged here and in the composer. */}
        <div className="search-row" style={{ display: 'flex', alignItems: 'center', padding: '14px 18px', gap: 12, borderBottom: `1px solid ${border}` }}>
          <Search size={16} color={muted} />
          <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)} placeholder="Search tools, students, staff..."
            aria-label="Search tools, students and staff"
            data-focus-ring="none"
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: text, fontFamily: 'var(--font-body)', fontSize: 16, fontWeight: 400 }} />
          {loading && <div className="spinner" style={{ width: 14, height: 14 }} />}
          {/* Another key cap — same treatment as the Ctrl/ hint. */}
          <button onClick={onClose} aria-label="Close search" style={{
            background: 'var(--color-page)', border: '1px solid var(--color-border)',
            color: 'var(--color-text-secondary)', cursor: 'pointer',
            borderRadius: 'var(--radius-sm)', padding: '2px 8px',
            fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', fontWeight: 600,
          }}>ESC</button>
        </div>
        {results.length > 0 && (
          <div style={{ maxHeight: 400, overflowY: 'auto', padding: 6 }}>
            {results.map((r, i) => (
              <div key={i} onClick={() => handleResultClick(r)} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderRadius: 10, cursor: 'pointer', transition: 'var(--transition-fast)' }}
                onMouseEnter={e => e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: `${typeColors[r.type] || '#666'}15`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: typeColors[r.type] || '#666', fontWeight: 700 }}>
                  {r.type?.[0]?.toUpperCase()}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 500, color: text }}>{r.name || r.title}</div>
                  <div style={{ fontSize: 12, color: muted }}>{r.subtitle || r.type}</div>
                </div>
                <span style={{ fontSize: 11, color: muted, background: 'var(--color-surface-raised)', padding: '3px 8px', borderRadius: 6, fontWeight: 500 }}>{r.type}</span>
              </div>
            ))}
          </div>
        )}
        {query && results.length === 0 && !loading && (
          <div style={{ padding: 32, textAlign: 'center', color: muted, fontSize: 14 }}>No results for "{query}"</div>
        )}
        {!query && (
          <div style={{ padding: '20px' }}>
            <div style={{ fontSize: 12, color: muted }}>Search for students, staff, tools, or announcements.</div>
          </div>
        )}
      </div>
    </div>
  );
}

const TYPE_CONFIG = {
  info:    { bg: '#4f8ff7', icon: 'ℹ', light: '#4f8ff715', border: '#4f8ff730' },
  warning: { bg: '#f59e0b', icon: '⚠', light: '#f59e0b15', border: '#f59e0b30' },
  success: { bg: '#10b981', icon: '✓', light: '#10b98115', border: '#10b98130' },
  error:   { bg: '#ef4444', icon: '!', light: '#ef444415', border: '#ef444430' },
};

function NotificationsPanel({ user, onClose, isDark, onOpenDetail, onNavigateToTool }) {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(false);
  const [readIds, setReadIds] = useState(new Set());
  const [markingAll, setMarkingAll] = useState(false);

  const load = () => {
    setLoading(true);
    setFetchError(false);
    fetch(`${API}/notifications`, { headers: getH(user) })
      .then(r => r.json())
      .then(r => {
        if (r.success) {
          const data = r.data || [];
          setNotifications(data);
          setReadIds(new Set(data.filter(n => n.read || n.is_digest).map(n => n.id).filter(Boolean)));
        } else {
          setFetchError(true);
        }
      })
      .catch(() => setFetchError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [user.id, user.role]); // eslint-disable-line

  const bg = isDark ? '#161616' : '#ffffff';
  const surface = isDark ? '#1e1e1e' : '#f8f9fa';
  const border = isDark ? '#2a2a2a' : '#e8eaed';
  const text = isDark ? '#f0f0f0' : '#111827';
  const muted = isDark ? '#777' : '#6b7280';
  const subtext = isDark ? '#555' : '#9ca3af';

  const markRead = (n) => {
    if (!n.id || n.is_digest || readIds.has(n.id)) return;
    setReadIds(prev => new Set([...prev, n.id]));
    fetch(`${API}/notifications/${n.id}/read`, { method: 'PATCH', headers: getH(user) }).catch(() => {});
  };

  const handleMarkAllRead = async () => {
    if (markingAll) return;
    setMarkingAll(true);
    setReadIds(new Set(notifications.map(n => n.id).filter(Boolean)));
    try { await fetch(`${API}/notifications/mark-all-read`, { method: 'PATCH', headers: getH(user) }); } catch {}
    setMarkingAll(false);
  };

  const handleNotifClick = (n) => {
    markRead(n);
    const toolId = getToolForNotification(n, user.role);
    if (toolId) {
      onClose();
      onNavigateToTool(toolId);
    } else {
      onOpenDetail(n);
    }
  };

  const unreadCount = notifications.filter(n => n.id && !n.is_digest && !readIds.has(n.id)).length;

  return (
    <div className="fade-in-scale" style={{
      position: 'absolute', top: 'calc(100% + 10px)', right: -4, width: 380,
      background: bg, border: `1px solid ${border}`,
      borderRadius: 18, zIndex: 100, overflow: 'hidden',
      boxShadow: isDark
        ? '0 20px 60px rgba(0,0,0,0.6), 0 4px 16px rgba(0,0,0,0.4)'
        : '0 20px 60px rgba(0,0,0,0.12), 0 4px 16px rgba(0,0,0,0.06)',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 18px 14px',
        background: 'var(--color-surface)',
        borderBottom: `1px solid ${border}`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 10,
            background: isDark ? '#252525' : '#f0f4ff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Bell size={15} color={isDark ? '#818cf8' : '#4f8ff7'} />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: text, letterSpacing: '-0.01em' }}>Notifications</div>
            {!loading && !fetchError && (
              <div style={{ fontSize: 11, color: muted, marginTop: 1 }}>
                {unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'}
              </div>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              disabled={markingAll}
              style={{
                background: isDark ? '#252525' : '#f0f4ff', border: 'none',
                color: isDark ? '#818cf8' : '#4f8ff7',
                cursor: markingAll ? 'wait' : 'pointer', padding: '4px 10px', borderRadius: 8,
                fontSize: 11, fontWeight: 600, opacity: markingAll ? 0.6 : 1,
              }}>
              Mark all read
            </button>
          )}
          <button onClick={onClose} style={{
            background: isDark ? '#252525' : '#f3f4f6', border: 'none',
            color: muted, cursor: 'pointer', padding: 6, borderRadius: 8,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <X size={13} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div style={{ maxHeight: 420, overflowY: 'auto' }}>
        {loading ? (
          <div style={{ padding: '40px 20px', textAlign: 'center' }}>
            <div className="spinner" style={{ margin: '0 auto 12px', width: 20, height: 20 }} />
            <span style={{ color: muted, fontSize: 13 }}>Loading notifications...</span>
          </div>
        ) : fetchError ? (
          <div style={{ padding: '40px 20px', textAlign: 'center' }}>
            <div style={{ fontSize: 28, marginBottom: 10 }}>⚡</div>
            <div style={{ color: '#ef4444', fontSize: 13, fontWeight: 500 }}>Could not load notifications</div>
            <div style={{ color: subtext, fontSize: 12, marginTop: 4 }}>Check your connection and try again</div>
          </div>
        ) : notifications.length === 0 ? (
          <div style={{ padding: '48px 20px', textAlign: 'center' }}>
            <Bell size={28} color={subtext} style={{ display: 'block', margin: '0 auto 12px' }} />
            <div style={{ color: text, fontSize: 13, fontWeight: 600, marginBottom: 4 }}>You're all caught up!</div>
            <div style={{ color: subtext, fontSize: 12 }}>No new notifications right now</div>
          </div>
        ) : (
          <div style={{ padding: '8px 0' }}>
            {notifications.map((n, i) => {
              const cfg = TYPE_CONFIG[n.type] || TYPE_CONFIG.info;
              const isRead = n.is_digest || readIds.has(n.id);
              return (
                <div key={n.id || i}
                  onClick={() => handleNotifClick(n)}
                  style={{
                    padding: '12px 18px',
                    display: 'flex', gap: 12, alignItems: 'flex-start',
                    cursor: 'pointer',
                    background: isRead ? 'transparent' : (isDark ? 'rgba(79,143,247,0.04)' : 'rgba(79,143,247,0.03)'),
                    borderBottom: i < notifications.length - 1 ? `1px solid ${border}` : 'none',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = isRead ? 'transparent' : (isDark ? 'rgba(79,143,247,0.04)' : 'rgba(79,143,247,0.03)'); }}
                >
                  <div style={{
                    width: 34, height: 34, borderRadius: 10, flexShrink: 0,
                    background: cfg.light, border: `1px solid ${cfg.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 14, color: cfg.bg, fontWeight: 700,
                  }}>
                    {cfg.icon}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                      <span style={{ fontSize: 13, color: text, fontWeight: isRead ? 500 : 600, lineHeight: 1.3, flex: 1 }}>{n.title}</span>
                      {!isRead && (
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: cfg.bg, flexShrink: 0, display: 'inline-block' }} />
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: muted, lineHeight: 1.45 }}>{n.message}</div>
                    <div style={{ fontSize: 11, color: subtext, marginTop: 5 }}>
                      {n.created_at ? new Date(n.created_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : (n.time || '')}
                    </div>
                  </div>
                  <div style={{ color: subtext, fontSize: 16, flexShrink: 0, alignSelf: 'center', opacity: 0.5 }}>›</div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      {!loading && !fetchError && notifications.length > 0 && (
        <div style={{
          padding: '10px 18px', borderTop: `1px solid ${border}`,
          background: isDark ? '#1a1a1a' : '#fafafa',
          display: 'flex', justifyContent: 'center',
        }}>
          <span style={{ fontSize: 11, color: subtext }}>{notifications.length} notification{notifications.length !== 1 ? 's' : ''} total</span>
        </div>
      )}
    </div>
  );
}

export default function Header({ activeTool, onBackToChat, onOpenProfile, onOpenSettings, onToggleSidebar, activeConvTitle }) {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [showSearch, setShowSearch] = useState(false);
  const [showNotif, setShowNotif] = useState(false);
  const [detailNotif, setDetailNotif] = useState(null);
  const notifRef = useRef(null);
  const [isMobile, setIsMobile] = useState(false);
  const [academicYear, setAcademicYear] = useState('');
  // The red dot used to be painted unconditionally, so the bell always looked as
  // though something needed attention even when everything was read. Count the
  // unread ones and only show it when there really is something.
  const [unreadCount, setUnreadCount] = useState(0);

  const refreshUnread = useCallback(() => {
    fetch(`${API}/notifications`, { headers: getH() })
      .then(r => (r.ok ? r.json() : null))
      .then(res => {
        const list = Array.isArray(res) ? res : (res?.data || []);
        setUnreadCount(list.filter(n => n && !n.is_digest && !n.is_read).length);
      })
      .catch(() => {});
  }, []);

  useEffect(() => { refreshUnread(); }, [refreshUnread]);
  // Re-count when the panel closes, since reading items in it changes the answer.
  useEffect(() => { if (!showNotif) refreshUnread(); }, [showNotif, refreshUnread]);

  useEffect(() => {
    const load = () => {
      getAcademicYear()
        .then(r => { if (r.success && r.data) setAcademicYear(r.data.name || r.data.year || ''); })
        .catch(() => {});
    };
    load();
    window.addEventListener('academic-year-updated', load);
    return () => window.removeEventListener('academic-year-updated', load);
  }, [currentUser?.id]);

  useEffect(() => {
    const h = (e) => { if (notifRef.current && !notifRef.current.contains(e.target)) setShowNotif(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  useEffect(() => {
    const checkScreen = () => setIsMobile(window.innerWidth <= 768);
    checkScreen();
    window.addEventListener('resize', checkScreen);
    return () => window.removeEventListener('resize', checkScreen);
  }, []);

  // ⌘K is handled by Layout (opens CommandPalette); ⌘/ opens database search here
  useEffect(() => {
    const h = (e) => { if ((e.metaKey || e.ctrlKey) && e.key === '/') { e.preventDefault(); setShowSearch(true); } };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, []);

  const title = activeTool
    ? activeTool?.split('-').map(w => w[0].toUpperCase() + w.slice(1)).join(' ')
    : '';

  const bg = 'var(--color-surface)';
  const border = 'var(--color-border)';
  const tp = 'var(--color-text-primary)';
  const muted = 'var(--color-text-muted)';
  const secondary = 'var(--color-text-secondary)';

  return (
    <>
      <header data-testid="main-header" style={{
        height: 52, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', borderBottom: `1px solid ${border}`, background: bg,
        position: 'sticky', top: 0, zIndex: 50, gap: 12, flexShrink: 0,
      }}>
        {/* Left */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: '0 0 auto' }}>
          <button aria-label="Open menu" onClick={onToggleSidebar} style={{
            ...ICON_BTN,
            color: muted,
            display: isMobile ? 'flex' : 'none',
          }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
            <Menu size={ICON_SIZE} />
          </button>
          {/* Back is desktop-only. On a phone the hamburger sits right beside it and
              already gets you out of a tool, so Back is redundant and it crowds the
              header enough to push the search box and bell off screen. */}
          {activeTool && !isMobile ? (
            <button data-testid="back-to-chat-btn" onClick={onBackToChat} style={{
              background: 'var(--color-surface-raised)', border: 'none', color: secondary,
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 13, fontWeight: 500, padding: '5px 10px', borderRadius: 8,
              transition: 'var(--transition-fast)',
            }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
              onMouseLeave={e => e.currentTarget.style.background = 'var(--color-surface-raised)'}>
              <ChevronLeft size={14} /> Back
            </button>
          ) : null}
          {/* The EduFlow wordmark, never the tool's name.
              Every tool page prints its own name as an <h1>, together with its
              record count and its action buttons. Repeating it here showed the
              title TWICE, one line apart, on every tool and in every role.

              A first attempt kept the header title on phones — which missed the
              point entirely, because a phone is where Abhimanyu was looking, so
              the duplicate survived everywhere he could see it. The name is now
              gone from the header at every width and for every role, and the
              brand takes the space. One <h1> per screen, which is also what the
              heading-order rule wants.

              MOBILE ONLY, deliberately. The rule is one EduFlow logo in view at
              a time:
                - desktop: the sidebar is always visible and carries the logo,
                  so a second one in the header is a duplicate;
                - mobile: the sidebar is a drawer and its logo is hidden until
                  you open the menu, so without this the brand would be absent
                  from the entire phone experience.
              Sized larger here than the sidebar's, because it is the only one
              on screen and has a 52px bar to fill. */}
          {isMobile ? (
            <img
              src="/eduflow-logo.png"
              alt="EduFlow"
              data-testid="header-logo"
              style={{ height: 34, width: 'auto', objectFit: 'contain', display: 'block', flexShrink: 0 }}
            />
          ) : null}
        </div>

        {/* Center: search.
            On phones this collapses to a single icon. The full-width version wrapped
            its label onto three lines inside a 52px-tall header, which spilled the box
            out over the page and squeezed the notification bell off screen entirely.
            The keyboard hint is desktop-only too \u2014 there is no Ctrl key on a phone. */}
        {isMobile ? (
          <div style={{ flex: 1, display: 'flex', justifyContent: 'flex-end', minWidth: 0 }}>
            <button aria-label="Search students and staff" onClick={() => setShowSearch(true)}
              style={{ ...ICON_BTN, color: muted }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              <Search size={ICON_SIZE} />
            </button>
          </div>
        ) : (
          <div style={{ flex: 1, maxWidth: 420, minWidth: 0, display: 'flex', justifyContent: 'center' }}>
            <button onClick={() => setShowSearch(true)} style={{
              width: '100%', display: 'flex', alignItems: 'center', gap: 10,
              background: 'var(--color-surface-raised)', border: `1px solid ${border}`,
              borderRadius: 10, padding: '7px 14px', cursor: 'pointer', color: muted, fontSize: 13,
              transition: 'var(--transition-fast)', overflow: 'hidden',
            }}
              onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--color-text-muted)'}
              onMouseLeave={e => e.currentTarget.style.borderColor = border}>
              <Search size={14} style={{ flexShrink: 0 }} />
              <span style={{ flex: 1, textAlign: 'left', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                Search students, staff {academicYear || ''}
              </span>
              {/* The keyboard hint. It filled with --color-border-strong, a
                  BORDER token raised to a slate blue for 3:1 outlines \u2014 as a
                  fill it read as a muddy blue smudge with unreadable text on
                  it. A key cap wants a recessed surface and a real outline. */}
              <kbd style={{
                flexShrink: 0, fontSize: 'var(--text-xs)', lineHeight: 1.6,
                color: 'var(--color-text-secondary)',
                background: 'var(--color-page)',
                border: '1px solid var(--color-border)',
                padding: '0 6px', borderRadius: 'var(--radius-sm)',
                fontFamily: 'var(--font-mono)', fontWeight: 500,
              }}>
                {navigator.platform.includes('Mac') ? '\u2318' : 'Ctrl'}/
              </kbd>
            </button>
          </div>
        )}

        {/* Right */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0 }}>

          {/* Academic year chip */}
          {academicYear && !isMobile && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6, marginRight: 6,
              padding: '4px 10px', borderRadius: 8,
              background: isDark ? 'rgba(79,143,247,0.08)' : 'rgba(79,143,247,0.06)',
              border: `1px solid ${isDark ? 'rgba(79,143,247,0.2)' : 'rgba(79,143,247,0.18)'}`,
            }}>
              <CalendarDays size={11} color={'var(--color-accent-blue)'} />
              <span style={{ fontSize: 11, color: isDark ? '#8baee8' : '#3b5fc0', fontWeight: 600, letterSpacing: '0.01em' }}>
                Academic Year {academicYear}
              </span>
            </div>
          )}

          <div ref={notifRef} style={{ position: 'relative' }}>
            <button aria-label="Notifications" data-testid="notifications-btn" onClick={() => setShowNotif(v => !v)}
              style={{ ...ICON_BTN, color: muted, position: 'relative' }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              <Bell size={ICON_SIZE} />
              {unreadCount > 0 && (
                <span aria-label={`${unreadCount} unread notifications`} style={{ position: 'absolute', top: 6, right: 6, width: 7, height: 7, background: 'var(--color-danger)', borderRadius: '50%', border: `2px solid ${bg}` }} />
              )}
            </button>
            {showNotif && (
              <NotificationsPanel
                user={currentUser}
                onClose={() => setShowNotif(false)}
                isDark={isDark}
                onOpenDetail={n => { setShowNotif(false); setDetailNotif(n); }}
                onNavigateToTool={toolId => {
                  setShowNotif(false);
                  window.dispatchEvent(new CustomEvent('eduflow-navigate', { detail: { toolId } }));
                }}
              />
            )}
          </div>
        </div>
      </header>

      {showSearch && <SearchPanel user={currentUser} onClose={() => setShowSearch(false)} isDark={isDark} />}
      {detailNotif && <NotificationDetailModal notification={detailNotif} onClose={() => setDetailNotif(null)} />}
    </>
  );
}
