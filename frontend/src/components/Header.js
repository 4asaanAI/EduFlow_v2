import React, { useState, useRef, useEffect } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { Search, Bell, ChevronLeft, Menu, X } from 'lucide-react';
import { getAuthHeaders } from '../lib/authSession';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

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

  const bg = isDark ? '#1e1e1e' : '#fff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#525252';

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
        <div style={{ display: 'flex', alignItems: 'center', padding: '14px 18px', gap: 12, borderBottom: `1px solid ${border}` }}>
          <Search size={16} color={muted} />
          <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)} placeholder="Search tools, students, staff..."
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: text, fontSize: 15, fontWeight: 400 }} />
          {loading && <div className="spinner" style={{ width: 14, height: 14 }} />}
          <button onClick={onClose} style={{ background: isDark ? '#333' : '#e5e5e5', border: 'none', color: muted, cursor: 'pointer', borderRadius: 6, padding: '3px 8px', fontSize: 11, fontWeight: 600 }}>ESC</button>
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
                <span style={{ fontSize: 11, color: muted, background: isDark ? '#252525' : '#f5f5f5', padding: '3px 8px', borderRadius: 6, fontWeight: 500 }}>{r.type}</span>
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

function NotificationsPanel({ user, onClose, isDark }) {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(false);
  const [read, setRead] = useState(new Set());

  useEffect(() => {
    setLoading(true);
    setFetchError(false);
    fetch(`${API}/notifications`, { headers: getH(user) })
      .then(r => r.json())
      .then(r => {
        if (r.success) setNotifications(r.data || []);
        else setFetchError(true);
      })
      .catch(() => setFetchError(true))
      .finally(() => setLoading(false));
  }, [user.id, user.role]);

  const bg = isDark ? '#161616' : '#ffffff';
  const surface = isDark ? '#1e1e1e' : '#f8f9fa';
  const border = isDark ? '#2a2a2a' : '#e8eaed';
  const text = isDark ? '#f0f0f0' : '#111827';
  const muted = isDark ? '#777' : '#6b7280';
  const subtext = isDark ? '#555' : '#9ca3af';

  const adminRouteMap = { 'Pending Leave Requests': 'staff-leave-manager', 'Fee Overdue': 'fee-collection', 'Announcement': 'announcement-broadcaster' };
  const teacherRouteMap = { 'Leave Status': 'leave-application' };
  const studentRouteMap = { 'Low Attendance': 'attendance-self-check', 'Fee Due': 'fee-status-viewer', 'Announcement': 'announcement-broadcaster' };

  const handleNotifClick = (n, i) => {
    setRead(prev => new Set([...prev, i]));
    let tool = null;
    if (user.role === 'owner' || user.role === 'admin') tool = adminRouteMap[n.title];
    else if (user.role === 'teacher') tool = teacherRouteMap[n.title];
    else if (user.role === 'student') tool = studentRouteMap[n.title];
    if (tool) { onClose(); window.dispatchEvent(new CustomEvent('open-tool', { detail: tool })); }
  };

  const unreadCount = notifications.filter((_, i) => !read.has(i)).length;

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
        background: isDark ? '#1a1a1a' : '#ffffff',
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
              onClick={() => setRead(new Set(notifications.map((_, i) => i)))}
              style={{
                background: isDark ? '#252525' : '#f0f4ff', border: 'none',
                color: isDark ? '#818cf8' : '#4f8ff7',
                cursor: 'pointer', padding: '4px 10px', borderRadius: 8,
                fontSize: 11, fontWeight: 600,
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
            <div style={{ fontSize: 32, marginBottom: 12 }}>🔔</div>
            <div style={{ color: text, fontSize: 13, fontWeight: 600, marginBottom: 4 }}>You're all caught up!</div>
            <div style={{ color: subtext, fontSize: 12 }}>No new notifications right now</div>
          </div>
        ) : (
          <div style={{ padding: '8px 0' }}>
            {notifications.map((n, i) => {
              const cfg = TYPE_CONFIG[n.type] || TYPE_CONFIG.info;
              const isRead = read.has(i);
              const isClickable = (() => {
                if (user.role === 'owner' || user.role === 'admin') return !!adminRouteMap[n.title];
                if (user.role === 'teacher') return !!teacherRouteMap[n.title];
                if (user.role === 'student') return !!studentRouteMap[n.title];
                return false;
              })();
              return (
                <div key={i}
                  onClick={() => handleNotifClick(n, i)}
                  style={{
                    padding: '12px 18px',
                    display: 'flex', gap: 12, alignItems: 'flex-start',
                    cursor: isClickable ? 'pointer' : 'default',
                    background: isRead ? 'transparent' : (isDark ? 'rgba(79,143,247,0.04)' : 'rgba(79,143,247,0.03)'),
                    borderBottom: i < notifications.length - 1 ? `1px solid ${border}` : 'none',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={e => { if (isClickable) e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = isRead ? 'transparent' : (isDark ? 'rgba(79,143,247,0.04)' : 'rgba(79,143,247,0.03)'); }}
                >
                  {/* Type icon */}
                  <div style={{
                    width: 34, height: 34, borderRadius: 10, flexShrink: 0,
                    background: cfg.light, border: `1px solid ${cfg.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 14, color: cfg.bg, fontWeight: 700,
                  }}>
                    {cfg.icon}
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                      <span style={{ fontSize: 13, color: text, fontWeight: isRead ? 500 : 600, lineHeight: 1.3, flex: 1 }}>{n.title}</span>
                      {!isRead && (
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: cfg.bg, flexShrink: 0, display: 'inline-block' }} />
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: muted, lineHeight: 1.45 }}>{n.message}</div>
                    <div style={{ fontSize: 11, color: subtext, marginTop: 5 }}>{n.time}</div>
                  </div>

                  {/* Arrow if clickable */}
                  {isClickable && (
                    <div style={{ color: subtext, fontSize: 16, flexShrink: 0, alignSelf: 'center', opacity: 0.6 }}>›</div>
                  )}
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
  const notifRef = useRef(null);
  const [isMobile, setIsMobile] = useState(false);

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

  const bg = isDark ? '#1a1a1a' : '#ffffff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const tp = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#525252';
  const secondary = isDark ? '#a0a0a0' : '#525252';

  return (
    <>
      <header data-testid="main-header" style={{
        height: 52, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', borderBottom: `1px solid ${border}`, background: bg,
        position: 'sticky', top: 0, zIndex: 50, gap: 12, flexShrink: 0,
      }}>
        {/* Left */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: '0 0 auto' }}>
          <button onClick={onToggleSidebar} style={{
            background: 'none', border: 'none', color: muted, cursor: 'pointer', padding: 6, borderRadius: 8,
            display: isMobile ? 'flex' : 'none', transition: 'var(--transition-fast)',
          }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
            <Menu size={18} />
          </button>
          {activeTool ? (
            <button data-testid="back-to-chat-btn" onClick={onBackToChat} style={{
              background: isDark ? '#252525' : '#f5f5f5', border: 'none', color: secondary,
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 13, fontWeight: 500, padding: '5px 10px', borderRadius: 8,
              transition: 'var(--transition-fast)',
            }}
              onMouseEnter={e => e.currentTarget.style.background = isDark ? '#333' : '#e5e5e5'}
              onMouseLeave={e => e.currentTarget.style.background = isDark ? '#252525' : '#f5f5f5'}>
              <ChevronLeft size={14} /> Back
            </button>
          ) : null}
          <span style={{ fontWeight: 600, fontSize: 15, color: tp, whiteSpace: 'nowrap', letterSpacing: '-0.01em' }}>
            {title}
          </span>
        </div>

        {/* Center: search */}
        <div style={{ flex: 1, maxWidth: 420, display: 'flex', justifyContent: 'center' }}>
          <button onClick={() => setShowSearch(true)} style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 10,
            background: isDark ? '#252525' : '#f5f5f5', border: `1px solid ${border}`,
            borderRadius: 10, padding: '7px 14px', cursor: 'pointer', color: muted, fontSize: 13,
            transition: 'var(--transition-fast)',
          }}
            onMouseEnter={e => e.currentTarget.style.borderColor = isDark ? '#444' : '#ccc'}
            onMouseLeave={e => e.currentTarget.style.borderColor = border}>
            <Search size={14} />
            <span style={{ flex: 1, textAlign: 'left' }}>Search students, staff\u2026</span>
            <div style={{ display: 'flex', gap: 4 }}>
              <kbd style={{ fontSize: 10, color: muted, background: isDark ? '#333' : '#e5e5e5', padding: '1px 5px', borderRadius: 4, fontFamily: 'Inter, sans-serif' }}>
                {navigator.platform.includes('Mac') ? '\u2318' : 'Ctrl'}/
              </kbd>
            </div>
          </button>
        </div>

        {/* Right */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0 }}>
          <div ref={notifRef} style={{ position: 'relative' }}>
            <button data-testid="notifications-btn" onClick={() => setShowNotif(v => !v)} style={{
              background: 'none', border: 'none', cursor: 'pointer', color: muted,
              padding: 7, borderRadius: 8, position: 'relative', transition: 'var(--transition-fast)',
            }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              <Bell size={17} />
              <span style={{ position: 'absolute', top: 5, right: 5, width: 6, height: 6, background: '#f87171', borderRadius: '50%', border: `2px solid ${bg}` }} />
            </button>
            {showNotif && <NotificationsPanel user={currentUser} onClose={() => setShowNotif(false)} isDark={isDark} />}
          </div>
        </div>
      </header>

      {showSearch && <SearchPanel user={currentUser} onClose={() => setShowSearch(false)} isDark={isDark} />}
    </>
  );
}
