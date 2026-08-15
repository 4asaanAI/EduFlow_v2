/**
 * The account button and its menu - now in the top bar, not the sidebar.
 *
 * Moved out of Sidebar.js on 2026-08-06 at the owner's request (items 5, 6 and 15).
 * Three things were asked for and they are all one job:
 *
 *   15. Put it in the header, right of the search and bell icons. On a phone the
 *       drawer was so full of fixed furniture - logo, school card, New Chat, the
 *       token bar, this block - that Tools and Recent Chats had about two rows each
 *       to share. Moving this out gives that height back to the two lists people
 *       actually navigate with.
 *   5.  The AI token bar moves in here as a row called "Usage". It was a permanent
 *       fixture of the sidebar for a number that changes slowly and is read rarely.
 *   6.  Help & Support opens onto something again. See lib/helpMenu.js for why it
 *       was empty.
 *
 * There is no photograph on a user record in this product, so the button shows the
 * person's initials on their role colour - the same mark the sidebar used.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, CheckSquare, ChevronDown, LogOut, Moon, Settings, Sun, User, LifeBuoy, Gauge, Flag } from 'lucide-react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { getMyTokenUsage } from '../lib/api';
import { helpToolsForUser } from '../lib/helpMenu';
import TokenUpgradeModal from './TokenUpgradeModal';
import ReportProblemModal from './ReportProblemModal';
import { userInitials } from '../lib/initials';

const ROLE_COLORS = { owner: '#fb923c', admin: '#4f8ff7', teacher: '#34d399', student: '#a78bfa', parent: '#22d3ee' };
const ROLE_LABELS = { owner: 'Owner', admin: 'Admin', teacher: 'Teacher', student: 'Student', parent: 'Guardian' };

function fmtTokens(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return `${n}`;
}

const rowStyle = {
  display: 'flex', alignItems: 'center', gap: 10, width: '100%',
  padding: '9px 10px', background: 'transparent', border: 'none',
  borderRadius: 8, cursor: 'pointer', color: 'var(--color-text-secondary)',
  fontSize: 13, fontWeight: 500, transition: 'var(--transition-fast)',
  textAlign: 'left',
};

export default function AccountMenu({ onOpenProfile, onOpenSettings, onSelectTool, activeTool }) {
  const { currentUser, logout } = useUser();
  const { isDark, toggleTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [showUsage, setShowUsage] = useState(false);
  const [showUpgrade, setShowUpgrade] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [usage, setUsage] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    const h = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false); setShowHelp(false); setShowUsage(false);
      }
    };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  // Escape closes the menu. A menu that can only be dismissed by clicking away is a
  // trap for anyone driving the page from the keyboard.
  useEffect(() => {
    if (!open) return undefined;
    const h = (e) => { if (e.key === 'Escape') { setOpen(false); setShowHelp(false); setShowUsage(false); } };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, [open]);

  useEffect(() => {
    getMyTokenUsage()
      .then(r => { if (r.success) setUsage(r.data); })
      .catch(() => {});
  }, [currentUser?.id]);

  const hover = 'var(--bg-hover)';
  const border = 'var(--color-border)';
  const muted = 'var(--color-text-muted)';
  const roleColor = ROLE_COLORS[currentUser?.role] || '#4f8ff7';

  const openTool = useCallback((toolId) => {
    setOpen(false); setShowHelp(false); setShowUsage(false);
    if (onSelectTool) onSelectTool(toolId);
    else window.dispatchEvent(new CustomEvent('open-tool', { detail: toolId }));
  }, [onSelectTool]);

  const helpTools = helpToolsForUser(currentUser);

  const isUnlimited = usage ? (usage.unlimited === true || usage.role_limit == null) : false;
  const limit = isUnlimited ? 0 : (usage?.role_limit || 0);
  const used = usage?.total_used || 0;
  const pct = (!isUnlimited && limit > 0) ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const barColor = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981';

  if (!currentUser) return null;

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        data-testid="account-menu-btn"
        aria-label={`Account menu for ${currentUser.name}`}
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen(v => !v)}
        style={{
          width: 36, height: 36, flexShrink: 0, padding: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'none', border: 'none', borderRadius: 'var(--radius-full)',
          cursor: 'pointer', transition: 'background var(--transition-fast)',
        }}
        onMouseEnter={e => e.currentTarget.style.background = hover}
        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
      >
        <span style={{
          width: 30, height: 30, borderRadius: '50%',
          background: `linear-gradient(135deg, ${roleColor}, ${roleColor}aa)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700, color: '#fff',
          boxShadow: `0 2px 6px ${roleColor}44`,
        }}>
          {userInitials(currentUser)}
        </span>
      </button>

      {open && (
        <div
          className="fade-in-scale"
          data-testid="account-menu"
          role="menu"
          style={{
            position: 'absolute', top: 'calc(100% + 8px)', right: 0,
            width: 248, maxWidth: 'calc(100vw - 24px)',
            background: 'var(--color-surface-raised)', border: `1px solid ${border}`,
            borderRadius: 12, padding: 6, boxShadow: 'var(--shadow-lg)', zIndex: 120,
          }}
        >
          {/* Who is signed in. In the sidebar this was the button itself; in a 36px
              round button there is nowhere to put a name, so it becomes the menu's
              first line rather than disappearing. */}
          <div style={{ padding: '8px 10px 10px', borderBottom: `1px solid ${border}`, marginBottom: 4 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)', lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {currentUser.name}
            </div>
            <div style={{ fontSize: 10, color: roleColor, fontWeight: 600, marginTop: 2 }}>
              {ROLE_LABELS[currentUser.role] || currentUser.role}
            </div>
          </div>

          <button role="menuitem" style={rowStyle}
            onClick={() => { setOpen(false); onOpenProfile(); }}
            onMouseEnter={e => e.currentTarget.style.background = hover}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
            <User size={14} /><span>Profile</span>
          </button>

          {/* Approvals and Notifications, 2026-08-15 (Abhimanyu).
              Both of these screens existed and could only be reached from inside the
              bell panel: the notifications window through its footer, and the approvals
              screen only when the bell happened to be showing its approvals half, which
              it only does when something is sitting there unread. So once a person had
              read their notifications there was NO WAY BACK to either screen. A screen
              you can only reach while it has something on it is indistinguishable from
              a screen that does not exist.

              They are here rather than in the sidebar because they belong to the person
              rather than to their job: every profile has the same two, and what is on
              them is decided by the server. */}
          <button role="menuitem" style={rowStyle} data-testid="account-approvals"
            onClick={() => openTool('approvals')}
            onMouseEnter={e => e.currentTarget.style.background = hover}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
            <CheckSquare size={14} /><span>Approvals</span>
          </button>

          <button role="menuitem" style={rowStyle} data-testid="account-notifications"
            onClick={() => openTool('all-notifications')}
            onMouseEnter={e => e.currentTarget.style.background = hover}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
            <Bell size={14} /><span>Notifications</span>
          </button>

          {/* Usage - owner request 5. Expands in place rather than navigating, so the
              number is readable without leaving whatever screen you were on. */}
          {usage && (
            <>
              <button role="menuitem" data-testid="account-usage-btn"
                aria-expanded={showUsage}
                onClick={() => setShowUsage(v => !v)}
                style={{ ...rowStyle, background: showUsage ? hover : 'transparent' }}
                onMouseEnter={e => e.currentTarget.style.background = hover}
                onMouseLeave={e => { if (!showUsage) e.currentTarget.style.background = 'transparent'; }}>
                <Gauge size={14} />
                <span style={{ flex: 1 }}>Usage</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: isUnlimited ? '#10b981' : barColor }}>
                  {isUnlimited ? 'Unlimited' : `${pct}%`}
                </span>
              </button>
              {showUsage && (
                <div style={{ padding: '4px 12px 10px' }}>
                  {!isUnlimited && (
                    <div style={{ height: 4, borderRadius: 3, background: 'var(--color-border)', overflow: 'hidden', marginBottom: 6 }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: barColor, borderRadius: 3 }} />
                    </div>
                  )}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>
                      {isUnlimited ? `${fmtTokens(used)} AI words used` : `${fmtTokens(used)} of ${fmtTokens(limit)} AI words`}
                    </span>
                    <button type="button" data-testid="account-usage-manage"
                      onClick={() => { setOpen(false); setShowUsage(false); setShowUpgrade(true); }}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 600, color: '#4f8ff7', padding: 0 }}>
                      Manage
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          <button role="menuitem" style={rowStyle}
            onClick={toggleTheme}
            onMouseEnter={e => e.currentTarget.style.background = hover}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
            {isDark ? <Sun size={14} /> : <Moon size={14} />}
            <span>{isDark ? 'Light Mode' : 'Dark Mode'}</span>
          </button>

          {/* R4-5: report a problem to Layaa AI. Deliberately NOT inside "Help &
              Support", which is hidden entirely for roles with nothing under it. This
              must be there for everybody, owner down to student, because anybody who
              can hit a fault has to be able to report one. */}
          <button role="menuitem" data-testid="account-report-problem"
            style={rowStyle}
            onClick={() => { setOpen(false); setShowReport(true); }}
            onMouseEnter={e => e.currentTarget.style.background = hover}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
            <Flag size={14} /><span>Report a problem</span>
          </button>

          <button role="menuitem" style={rowStyle}
            onClick={() => { setOpen(false); onOpenSettings(); }}
            onMouseEnter={e => e.currentTarget.style.background = hover}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
            <Settings size={14} /><span>Settings</span>
          </button>

          {/* Owner request 6: this opened onto nothing. It is hidden entirely when a
              role has nothing under it, rather than offered and then found empty. */}
          {helpTools.length > 0 && (
            <>
              <button role="menuitem" data-testid="account-help-btn"
                aria-expanded={showHelp}
                onClick={() => setShowHelp(v => !v)}
                style={{ ...rowStyle, background: showHelp ? hover : 'transparent' }}
                onMouseEnter={e => e.currentTarget.style.background = hover}
                onMouseLeave={e => { if (!showHelp) e.currentTarget.style.background = 'transparent'; }}>
                <LifeBuoy size={14} />
                <span style={{ flex: 1 }}>Help & Support</span>
                <ChevronDown size={12} color={muted} style={{ transform: showHelp ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.2s ease' }} />
              </button>
              {showHelp && (
                <div style={{ paddingLeft: 8, paddingBottom: 2 }}>
                  {helpTools.map(tool => {
                    const Icon = tool.icon;
                    const isActive = activeTool === tool.id;
                    return (
                      <button key={tool.id} role="menuitem" data-testid={`account-help-${tool.id}`}
                        onClick={() => openTool(tool.id)}
                        style={{
                          ...rowStyle, padding: '7px 10px', fontSize: 12,
                          background: isActive ? `${tool.color}12` : 'transparent',
                          color: isActive ? tool.color : 'var(--color-text-secondary)',
                          fontWeight: isActive ? 600 : 500,
                        }}
                        onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = hover; }}
                        onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}>
                        <Icon size={13} color={isActive ? tool.color : muted} />
                        <span>{tool.name}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </>
          )}

          <div style={{ borderTop: `1px solid ${border}`, margin: '4px 0' }} />

          <button role="menuitem" data-testid="account-sign-out"
            onClick={() => { setOpen(false); logout(); }}
            style={{ ...rowStyle, color: '#f87171' }}
            onMouseEnter={e => e.currentTarget.style.background = hover}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
            <LogOut size={14} /><span>Sign Out</span>
          </button>
        </div>
      )}

      {showUpgrade && (
        <TokenUpgradeModal
          onClose={() => setShowUpgrade(false)}
          currentUsage={usage?.total_used || 0}
          roleLimit={usage?.role_limit || 0}
          canPurchase={currentUser.role !== 'student'}
        />
      )}

      {/* No `canReport` prop and no role check. Every profile may report a problem,
          which is R4-5's decision and not an omission here. */}
      {showReport && <ReportProblemModal onClose={() => setShowReport(false)} />}
    </div>
  );
}
