import React, { useState, useRef, useEffect } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { Search, Bell, ChevronDown, ChevronLeft, User, Settings, Menu, X, Zap, LogOut } from 'lucide-react';

const ROLE_COLORS = { owner: '#F97316', admin: '#3B82F6', teacher: '#10B981', student: '#8B5CF6' };
const ROLE_LABELS = { owner: 'Owner', admin: 'Admin', teacher: 'Teacher', student: 'Student' };
const API = process.env.REACT_APP_BACKEND_URL + '/api';

function getH(user) {
  return { 'X-User-Role': user?.role || 'owner', 'X-User-Id': user?.id || 'user-owner-001', 'X-User-Name': user?.name || 'Aman' };
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

 

  const bg = isDark ? '#1C1C28' : '#fff';
  const border = isDark ? '#222230' : '#E2E8F0';
  const text = isDark ? '#E2E8F0' : '#0F172A';
  const muted = isDark ? '#64748B' : '#94A3B8';

  const typeColors = { tool: '#8B5CF6', student: '#3B82F6', staff: '#10B981', announcement: '#EAB308' };

  const handleResultClick = (r) => {
    onClose();
    if (r.type === 'tool') window.dispatchEvent(new CustomEvent('open-tool', { detail: r.id }));
    else if (r.type === 'student') window.dispatchEvent(new CustomEvent('open-tool', { detail: 'student-database' }));
    else if (r.type === 'staff') window.dispatchEvent(new CustomEvent('open-tool', { detail: 'staff-attendance-tracker' }));
    else if (r.type === 'announcement') window.dispatchEvent(new CustomEvent('open-tool', { detail: 'announcement-broadcaster' }));
  };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 70 }}>
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)' }} />
      <div style={{ position: 'relative', width: 560, background: bg, border: `1px solid ${border}`, borderRadius: 14, boxShadow: '0 24px 64px rgba(0,0,0,0.4)', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', padding: '12px 16px', gap: 10, borderBottom: `1px solid ${border}` }}>
          <Search size={14} color={muted} />
          <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)} placeholder="Search tools, students, staff, announcements..."
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: text, fontSize: 14 }} />
          {loading && <div className="spinner" style={{ width: 14, height: 14 }} />}
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: muted, cursor: 'pointer' }}><X size={14} /></button>
        </div>
        {results.length > 0 && (
          <div style={{ maxHeight: 400, overflowY: 'auto', padding: 8 }}>
            {results.map((r, i) => (
              <div key={i} onClick={() => handleResultClick(r)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', borderRadius: 8, cursor: 'pointer' }}
                onMouseEnter={e => e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                <div style={{ width: 28, height: 28, borderRadius: 7, background: `${typeColors[r.type] || '#64748B'}20`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: typeColors[r.type] || '#64748B', fontWeight: 700 }}>
                  {r.type?.[0]?.toUpperCase()}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: text }}>{r.name || r.title}</div>
                  <div style={{ fontSize: 11, color: muted }}>{r.subtitle || r.type}</div>
                </div>
                <span style={{ fontSize: 10, color: muted, background: `${typeColors[r.type] || '#64748B'}15`, padding: '2px 6px', borderRadius: 4 }}>{r.type}</span>
              </div>
            ))}
          </div>
        )}
        {query && results.length === 0 && !loading && (
          <div style={{ padding: 24, textAlign: 'center', color: muted, fontSize: 13 }}>No results for "{query}"</div>
        )}
        {!query && (
          <div style={{ padding: '16px' }}>
            <div style={{ fontSize: 10, color: muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Quick Tips</div>
            <div style={{ fontSize: 12, color: muted }}>Search for students, staff, tools, or announcements. Results are scoped to your role.</div>
          </div>
        )}
      </div>
    </div>
  );
}

function NotificationsPanel({ user, onClose, isDark }) {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/notifications`, { headers: getH(user) }).then(r => r.json())
      .then(r => { if (r.success) setNotifications(r.data || []); })
      .catch(() => {}).finally(() => setLoading(false));
  }, []);

  const bg = isDark ? '#1C1C28' : '#fff';
  const border = isDark ? '#222230' : '#E2E8F0';
  const text = isDark ? '#E2E8F0' : '#0F172A';
  const muted = isDark ? '#64748B' : '#94A3B8';
  const typeColors = { info: '#3B82F6', warning: '#F59E0B', success: '#10B981', error: '#EF4444' };

  const handleNotifClick = (n) => {
    onClose();
    const routeMap = {
      'Pending Leave Requests': 'staff-leave-manager',
      'Fee Overdue': 'fee-collection',
      'Leave Status': 'leave-application',
      'Low Attendance': 'attendance-self-check',
      'Fee Due': 'fee-status-viewer',
      'Announcement': 'announcement-broadcaster',
    };
    const tool = routeMap[n.title];
    if (tool) window.dispatchEvent(new CustomEvent('open-tool', { detail: tool }));
  };

  return (
    <div style={{ position: 'absolute', top: '110%', right: 0, width: 320, background: bg, border: `1px solid ${border}`, borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.3)', zIndex: 100, overflow: 'hidden' }}>
      <div style={{ padding: '12px 14px', borderBottom: `1px solid ${border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: text }}>Notifications</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: muted, cursor: 'pointer' }}><X size={13} /></button>
      </div>
      <div style={{ maxHeight: 340, overflowY: 'auto' }}>
        {loading ? (
          <div style={{ padding: 24, textAlign: 'center', color: muted, fontSize: 12 }}>Loading...</div>
        ) : notifications.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: muted, fontSize: 12 }}>No new notifications</div>
        ) : (
          notifications.map((n, i) => (
            <div key={i} onClick={() => handleNotifClick(n)} style={{ padding: '10px 14px', borderBottom: i < notifications.length - 1 ? `1px solid ${border}` : 'none', display: 'flex', gap: 10, alignItems: 'flex-start', cursor: 'pointer' }}
              onMouseEnter={e => e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: typeColors[n.type] || '#64748B', marginTop: 5, flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: 12, color: text, fontWeight: 500 }}>{n.title}</div>
                <div style={{ fontSize: 11, color: muted, marginTop: 2 }}>{n.message}</div>
                <div style={{ fontSize: 10, color: muted, marginTop: 3 }}>{n.time}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function Header({ activeTool, onBackToChat, onOpenProfile, onOpenSettings, onToggleSidebar, activeConvTitle }) {
  const { currentUser, switchRole, logout, MOCK_USERS } = useUser();
  const { isDark } = useTheme();
  const [showRoleMenu, setShowRoleMenu] = useState(false);
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
  const checkScreen = () => {
    setIsMobile(window.innerWidth <= 768);
  };

  checkScreen();

  window.addEventListener('resize', checkScreen);
  return () => window.removeEventListener('resize', checkScreen);
}, []);

  const title = activeTool
    ? activeTool?.split('-').map(w => w[0].toUpperCase() + w.slice(1)).join(' ')
    : '';

  const bg = isDark ? '#0A0A0F' : '#FFFFFF';
  const border = isDark ? '#222230' : '#E2E8F0';
  const tp = isDark ? '#fff' : '#0F172A';
  const muted = isDark ? '#64748B' : '#94A3B8';
  const cardBg = isDark ? '#161622' : '#F8F9FC';
  const cardBorder = isDark ? '#222230' : '#E2E8F0';

  return (
    <>
      <header data-testid="main-header" style={{ height: 50, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 14px', borderBottom: `1px solid ${border}`, background: bg, position: 'sticky', top: 0, zIndex: 50, gap: 10, flexShrink: 0 }}>
        {/* Left */}
       <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: '0 0 auto' }}>
          <button onClick={onToggleSidebar} style={{ background: 'none', border: 'none', color: muted, cursor: 'pointer', display: 'flex', padding: 4, display: isMobile ? 'flex' : 'none',}}>
            <Menu size={16} />
          </button>
          {activeTool ? (
            <button data-testid="back-to-chat-btn" onClick={onBackToChat} style={{ background: 'none', border: 'none', color: muted, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3, fontSize: 12 }}>
              <ChevronLeft size={13} />Chat
            </button>
          ) : null}
          <span style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 600, fontSize: 14, color: tp, whiteSpace: 'nowrap' }}>
            {title}
          </span>
        </div>

        {/* Center: search */}
        <div style={{ flex: 1, maxWidth: 400 }}>
          <button onClick={() => setShowSearch(true)} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, background: cardBg, border: `1px solid ${cardBorder}`, borderRadius: 20, padding: '6px 14px', cursor: 'pointer', color: muted, fontSize: 12 }}>
            <Search size={12} color={muted} />
            <span>Search tools, people, or anything...</span>
          </button>
        </div>

        {/* Right: compact */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
          {/* Notifications */}
          <div ref={notifRef} style={{ position: 'relative' }}>
            <button data-testid="notifications-btn" onClick={() => setShowNotif(v => !v)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: muted, padding: 5, position: 'relative' }}>
              <Bell size={15} />
              <span style={{ position: 'absolute', top: 3, right: 3, width: 5, height: 5, background: '#EF4444', borderRadius: '50%' }} />
            </button>
            {showNotif && <NotificationsPanel user={currentUser} onClose={() => setShowNotif(false)} isDark={isDark} />}
          </div>

          <button data-testid="profile-btn" onClick={onOpenProfile} style={{ background: 'none', border: 'none', cursor: 'pointer', color: muted, padding: 5 }}>
            <User size={15} />
          </button>
          <button data-testid="settings-btn" onClick={onOpenSettings} style={{ background: 'none', border: 'none', cursor: 'pointer', color: muted, padding: 5 }}>
            <Settings size={15} />
          </button>

          {/* Compact role + name */}
          <div style={{ position: 'relative' }}>
            <button data-testid="role-switcher-btn" onClick={() => setShowRoleMenu(v => !v)}
              style={{ display: 'flex', alignItems: 'center', gap: 6, background: cardBg, border: `1px solid ${cardBorder}`, borderRadius: 8, padding: '4px 8px 4px 6px', cursor: 'pointer' }}>
              <div style={{ width: 22, height: 22, borderRadius: '50%', background: ROLE_COLORS[currentUser.role], display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 700, color: '#fff' }}>
                {currentUser.initials}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: tp, lineHeight: 1 }}>{currentUser.name.split(' ')[0]}</span>
                <span style={{ fontSize: 9, color: ROLE_COLORS[currentUser.role], fontWeight: 700, lineHeight: 1, marginTop: 1 }}>{ROLE_LABELS[currentUser.role]}</span>
              </div>
              <ChevronDown size={9} color={muted} />
            </button>

            {showRoleMenu && (
              <div data-testid="role-menu" style={{ position: 'absolute', top: '110%', right: 0, background: isDark ? '#1C1C28' : '#fff', border: `1px solid ${cardBorder}`, borderRadius: 10, padding: 5, minWidth: 160, zIndex: 100, boxShadow: '0 8px 32px rgba(0,0,0,0.3)' }}>
                <div style={{ fontSize: 9, color: muted, padding: '3px 8px 6px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Switch Role (Dev)</div>
                {Object.entries(MOCK_USERS).map(([role, user]) => (
                  <button key={role} data-testid={`switch-role-${role}`}
                    onClick={() => { switchRole(role); setShowRoleMenu(false); }}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '6px 9px', background: currentUser.role === role ? (isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)') : 'transparent', border: 'none', borderRadius: 7, cursor: 'pointer', color: tp, fontSize: 11 }}>
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: ROLE_COLORS[role] }} />
                    <span style={{ fontWeight: 500 }}>{ROLE_LABELS[role]}</span>
                    <span style={{ color: muted, marginLeft: 'auto', fontSize: 10 }}>{user.name.split(' ')[0]}</span>
                  </button>
                ))}
                <div style={{ borderTop: `1px solid ${cardBorder}`, margin: '4px 0' }} />
                <button onClick={() => { logout(); setShowRoleMenu(false); }}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '6px 9px', background: 'transparent', border: 'none', borderRadius: 7, cursor: 'pointer', color: '#EF4444', fontSize: 11 }}>
                  <LogOut size={11} />
                  <span style={{ fontWeight: 500 }}>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {showSearch && <SearchPanel user={currentUser} onClose={() => setShowSearch(false)} isDark={isDark} />}
    </>
  );
}
