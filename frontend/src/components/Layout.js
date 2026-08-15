import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import Sidebar from './Sidebar';
import Header from './Header';
import ChatInterface from './ChatInterface';
import ErrorBoundary from './ErrorBoundary';
import { createConversation, getConversations } from '../lib/api';
import ProfileModal from './ProfileModal';
import SettingsModal from './SettingsModal';
import CommandPalette from './CommandPalette';
import { resolveToolId } from '../lib/toolAliases';
import { MANAGEMENT_HUB_IDS } from '../lib/managementHubs';

const loadTool = async (rawToolId) => {
  const toolId = resolveToolId(rawToolId);
  if (MANAGEMENT_HUB_IDS.includes(toolId)) {
    const ManagementHub = (await import('./tools/ManagementHub')).default;
    return () => <ManagementHub hubId={toolId} />;
  }
  if (toolId === 'commercial-operations') return (await import('./tools/CommercialOperations')).default;
  // Phase 3 dedicated tool panels - loaded directly
  if (toolId === 'facility-requests') return (await import('./tools/MaintenanceTools')).MaintenanceFacilityTracker;
  if (toolId === 'tech-issues') return (await import('./tools/MaintenanceTools')).ITTechIssueTracker;
  if (toolId === 'all-issues') return (await import('./tools/MaintenanceTools')).AllIssuesView;
  if (toolId === 'maintenance-schedule') return (await import('./tools/MaintenanceTools')).MaintenanceSchedule;
  if (toolId === 'vendor-log') return (await import('./tools/MaintenanceTools')).VendorLog;
  if (toolId === 'raise-maintenance') return (await import('./tools/MaintenanceTools')).RaiseMaintenanceRequest;
  if (toolId === 'incident-tracker') return (await import('./tools/IncidentTracker')).default;
  if (toolId === 'timetable-builder') return (await import('./tools/TimetableBuilder')).default;
  if (toolId === 'audit-log') return (await import('./tools/AuditLog')).default;
  if (toolId === 'school-settings') return (await import('./tools/SchoolSettings')).default;
  if (toolId === 'academic-structure') return (await import('./tools/AcademicStructure')).default;
  if (toolId === 'principal-daily') return (await import('./tools/PrincipalDailyOps')).default;
  if (toolId === 'exam-manager') return (await import('./tools/ExamManager')).default;
  if (toolId === 'what-ive-learned') return (await import('./tools/LearningTools')).default;
  if (toolId === 'conversation-trace') return (await import('./tools/ConversationTrace')).default;
  // Epic 6. Reached from the bell panel's footer and the sidebar's Recent Chats
  // header rather than from a per-role nav list - both of those live in the
  // shell, so the pages are reachable from every screen (FR81) without editing
  // eight navigation configs.
  if (toolId === 'all-notifications') return (await import('./tools/AllNotifications')).default;
  // Approvals workflow, 2026-08-15. Reached from the bell's Approvals tab and from
  // the notifications screen, exactly like all-notifications above, rather than from a
  // per-profile nav list: every profile has the same approvals screen (decision 25) and
  // what differs is what is on it, which the server decides.
  if (toolId === 'approvals') return (await import('./tools/ApprovalsQueue')).default;
  if (toolId === 'all-chats') return (await import('./tools/AllChats')).default;
  if (toolId === 'platform-messaging') return (await import('./MessagingScreen')).default;

  // Existing dedicated tools
  if (toolId === 'query-section') return (await import('./tools/QuerySection')).QuerySection;
  if (toolId === 'staff-tracker') return (await import('./tools/StaffTracker')).default;
  if (toolId === 'attendance-recorder') return (await import('./tools/AttendanceRecorder')).default;
  if (toolId === 'fee-collection') return (await import('./tools/FeeCollection')).default;
  if (toolId === 'fee-sync') return (await import('./tools/FeeSync')).default;
  if (toolId === 'student-database') return (await import('./tools/StudentDatabase')).default;
  // Epic 7 - the School Directory (Owner + Principal only, via their tool sets).
  // Reads the existing students/staff endpoints; adds no new server surface.
  if (toolId === 'school-activities') return (await import('./tools/SchoolActivities')).default;
  if (toolId === 'transport-optimisation') return (await import('./tools/TransportOptimisation')).default;
  if (toolId === 'student-leave-manager') return (await import('./tools/StudentLeaveManager')).default;
  if (toolId === 'student-leave-request') return (await import('./tools/StudentLeaveRequest')).default;
  if (['resource-calendar', 'asset-custody', 'procurement-inventory', 'library-circulation'].includes(toolId)) {
    const campus = await import('./tools/EnterpriseCampusTools');
    const names = { 'resource-calendar': 'ResourceCalendar', 'asset-custody': 'AssetCustody', 'procurement-inventory': 'ProcurementInventory', 'library-circulation': 'LibraryCirculation' };
    return campus[names[toolId]];
  }
  if (['accounting-periods', 'payroll-manager', 'my-payslips'].includes(toolId)) {
    const finance = await import('./tools/FinanceControlTools');
    const names = { 'accounting-periods': 'AccountingPeriods', 'payroll-manager': 'PayrollManager', 'my-payslips': 'MyPayslips' };
    return finance[names[toolId]];
  }
  if (toolId === 'quiz-manager' || toolId === 'practice-test') {
    const quizzes = await import('./tools/QuizTools');
    return quizzes[toolId === 'quiz-manager' ? 'QuizManager' : 'PracticeTest'];
  }

  // A4: the merged Admissions screen. It pulls panels from three different files, so
  // it gets its own entry rather than being routed by which role list it sits in.
  if (toolId === 'admissions') return (await import('./tools/AdmissionsScreen')).Admissions;

  const OWNERS = ['school-pulse','fee-collection','fee-sync','student-strength','data-import','attendance-overview','staff-tracker','staff-attendance-tracker','financial-reports','accounting-periods','payroll-manager','announcement-broadcaster','staff-leave-manager','student-leave-manager','resource-calendar','asset-custody','procurement-inventory','library-circulation','quiz-manager','staff-performance','ai-health-report','smart-alerts','expense-tracker','custom-report-builder','board-report','smart-fee-defaulter','attendance-alerts','reports-trends','platform-health-dashboard'];
  const ADMINS = ['fee-tracker','certificate-generator','circular-sender','document-scanner','smart-fee-defaulter','admission-pipeline','parent-message','student-transfer','id-card-generator','asset-tracker','asset-custody','resource-calendar','procurement-inventory','library-circulation','accounting-periods','payroll-manager','quiz-manager','transport-manager','automated-report','custom-form-builder','report-card-builder','student-performance-viewer','student-leave-manager','attendance-alerts','reports-trends','timetable-builder'];
  const TEACHERS = ['class-attendance-marker','assignment-generator','question-paper-creator','report-card-builder','student-performance-viewer','leave-application','lesson-plan-generator','worksheet-creator','class-performance-analytics','substitution-viewer','ptm-notes','curriculum-tracker','resource-calendar','library-circulation','quiz-manager','my-payslips','form-submissions'];
  const STUDENTS = ['ai-tutor','doubt-solver','homework-viewer','attendance-self-check','result-viewer','practice-test','study-planner','career-guidance','fee-status-viewer','student-leave-request','library-circulation','ptm-summary-viewer','form-submissions'];
  const PARENTS = ['guardian-portal'];

  const toComp = (id) => id.split('-').map(w => w[0].toUpperCase() + w.slice(1)).join('');
  if (OWNERS.includes(toolId)) return (await import('./tools/OwnerTools'))[toComp(toolId)];
  if (ADMINS.includes(toolId)) return (await import('./tools/AdminTools'))[toComp(toolId)];
  if (TEACHERS.includes(toolId)) return (await import('./tools/TeacherTools'))[toComp(toolId)];
  if (STUDENTS.includes(toolId)) return (await import('./tools/StudentTools'))[toComp(toolId)];
  if (PARENTS.includes(toolId)) return (await import('./tools/ParentTools'))[toComp(toolId)];
  return null;
};

function ToolView({ toolId }) {
  const [Comp, setComp] = useState(null);
  const { isDark } = useTheme();
  useEffect(() => {
    setComp(null);
    loadTool(toolId).then(C => setComp(() => C || null));
  }, [toolId]);
  if (!Comp) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 16 }}>
      <div className="spinner" style={{ width: 20, height: 20 }} />
      <span style={{ color: 'var(--text-muted)', fontSize: 13, fontWeight: 500 }}>Loading tool...</span>
    </div>
  );
  return (
    <div style={{ height: '100%' }}>
      <ErrorBoundary name={toolId}>
        <Comp />
      </ErrorBoundary>
    </div>
  );
}

const TOOL_DASHBOARD_ROLES = ['admin', 'teacher', 'owner', 'student'];
const MOBILE_BREAKPOINT = 768;

export default function Layout() {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [searchParams, setSearchParams] = useSearchParams();
  // Resolved here, not deeper in, so a retired id (see TOOL_ALIASES) also lights up
  // the right sidebar row and puts the right name in the header - not just the right
  // screen in the middle.
  const activeTool = resolveToolId(searchParams.get('tool'));
  const [activeConvId, setActiveConvId] = useState(null);
  const [activeConvTitle, setActiveConvTitle] = useState('');
  const [convRefresh, setConvRefresh] = useState(0);
  const [showProfile, setShowProfile] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showCmdPalette, setShowCmdPalette] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > MOBILE_BREAKPOINT);
  const previousUserIdRef = useRef(currentUser.id);

  const isToolDashboardRole = TOOL_DASHBOARD_ROLES.includes(currentUser.role);

  // Keep the shell adaptive when a tablet rotates or a desktop window is narrowed.
  // A phone starts with the drawer closed; desktop keeps the persistent sidebar.
  useEffect(() => {
    let wasMobile = window.innerWidth <= MOBILE_BREAKPOINT;
    const syncSidebarToViewport = () => {
      const isMobile = window.innerWidth <= MOBILE_BREAKPOINT;
      if (isMobile !== wasMobile) {
        setSidebarOpen(!isMobile);
        wasMobile = isMobile;
      }
    };
    window.addEventListener('resize', syncSidebarToViewport);
    return () => window.removeEventListener('resize', syncSidebarToViewport);
  }, []);

  const setActiveToolParam = useCallback((toolId, options = {}) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (toolId) next.set('tool', toolId);
      else next.delete('tool');
      return next;
    }, { replace: !!options.replace });
  }, [setSearchParams]);

  /**
   * Where Back goes (owner request 19, 2026-08-06).
   *
   * Back used to clear `?tool=` outright, which dropped you into the chat from
   * wherever you were. That is wrong the moment a screen is reached THROUGH another
   * screen - which is now the normal case, because the nine management hubs exist
   * to be opened and then drilled into. Open School Database, open Students &
   * Guardians, press Back, and you were in the chat rather than back at School
   * Database, with no way to the hub except starting again from the menu.
   *
   * The trail is kept here rather than read from browser history because the shell
   * cannot see how many of the browser's entries belong to this app (a person may
   * have arrived from anywhere), and `history.back()` past the first one would
   * leave the site entirely.
   *
   * Rules:
   *   - opening a screen pushes the one you were on;
   *   - Back pops, so it walks the trail one step at a time;
   *   - an empty trail means Back goes to the chat, which is the old behaviour and
   *     the right answer for a screen opened straight from the menu;
   *   - re-opening a screen already on the trail truncates back to it rather than
   *     stacking a second copy, so hub → tool → hub → tool cannot grow forever.
   */
  const [toolTrail, setToolTrail] = useState([]);

  const pushTool = useCallback((toolId) => {
    setToolTrail((trail) => {
      if (!activeTool || activeTool === toolId) return trail;
      const seenAt = trail.indexOf(toolId);
      if (seenAt !== -1) return trail.slice(0, seenAt);
      return [...trail, activeTool];
    });
  }, [activeTool]);

  // Deliberately NOT navigating from inside a state updater: React may invoke an
  // updater twice, and a double navigation would skip a step of the trail.
  const handleBack = useCallback(() => {
    if (toolTrail.length === 0) {
      setActiveToolParam(null);
      return;
    }
    setActiveToolParam(toolTrail[toolTrail.length - 1]);
    setToolTrail(toolTrail.slice(0, -1));
  }, [toolTrail, setActiveToolParam]);

  /**
   * Close the drawer when the user picks something that NAVIGATES.
   *
   * On phones the sidebar is an overlay sitting on top of the thing you just
   * asked for, so leaving it open means tapping the backdrop to see your own
   * choice. On desktop it sits beside the content, so it stays.
   *
   * The rule, set by Abhimanyu 2026-07-22: close on anything that takes you
   * somewhere - New Chat, a tool, a conversation, Profile, Settings. Do NOT
   * close on anything that merely EXPANDS in place: a tool group opening its
   * children, or Help & Support opening its submenu. Closing there would shut
   * the drawer at the exact moment the user was drilling into it.
   *
   * 768px matches the `@media (max-width: 768px)` breakpoint the drawer CSS
   * uses in index.css. The two must agree, or the drawer closes at a width
   * where it is not a drawer.
   */
  const closeDrawerOnNavigate = useCallback(() => {
    if (window.innerWidth <= MOBILE_BREAKPOINT) setSidebarOpen(false);
  }, []);

  const handleNewChat = async () => {
    setActiveToolParam(null);
    setToolTrail([]);
    closeDrawerOnNavigate();
    // D-64: takes no arguments (see the note on getConversations below).
    const res = await createConversation();
    if (res.success) {
      setActiveConvId(res.data.id);
      setActiveConvTitle('');
      setConvRefresh(n => n + 1);
    }
  };

  const handleSelectTool = (toolId) => {
    // Picking a screen from the MENU starts a fresh trail: the menu is a top-level
    // jump, not a step deeper into where you already were. Drilling in from a hub
    // goes through the `open-tool` handler below, which does push.
    setToolTrail([]);
    setActiveToolParam(toolId);
    closeDrawerOnNavigate();
    if (isToolDashboardRole) {
      const key = `eduflow_activity_${currentUser.id}`;
      const prev = JSON.parse(localStorage.getItem(key) || '[]').filter(a => a.id !== toolId);
      prev.unshift({ id: toolId, at: new Date().toISOString() });
      localStorage.setItem(key, JSON.stringify(prev.slice(0, 30)));
    }
  };

  const handleSelectConv = async (convId) => {
    setActiveToolParam(null);
    setToolTrail([]);
    setActiveConvId(convId);
    closeDrawerOnNavigate();
    try {
      // D-64: NEVER pass the signed-in person here. This helper turns its argument
      // into the query string, so handing it the user object wrote that person's id,
      // name, email and role into the request URL - and from there into the server
      // and CloudFront access logs - on every single chat load. The screen looked
      // correct throughout, which is why it survived. The caller is already
      // authenticated by the bearer token; the server knows who is asking.
      // Guarded by lib/__tests__/apiDeadArgs.test.js, whose exemption list is empty.
      const res = await getConversations();
      const conv = res.data?.find(c => c.id === convId);
      setActiveConvTitle(conv?.title || '');
    } catch {}
  };

  const handleConvCreated = (convId) => {
    setActiveConvId(convId);
    setConvRefresh(n => n + 1);
  };

  // `open-tool` is how a screen opens another screen: a hub card, a search result,
  // the notification panel. That IS a step deeper, so it pushes onto the trail and
  // Back returns to the screen that sent you.
  useEffect(() => {
    const handler = (e) => {
      if (!e.detail) return;
      pushTool(resolveToolId(e.detail));
      setActiveToolParam(e.detail);
    };
    window.addEventListener('open-tool', handler);
    return () => window.removeEventListener('open-tool', handler);
  }, [setActiveToolParam, pushTool]);

  /**
   * Epic 6: the All Chats page opening a conversation, and telling the shell that
   * conversations were deleted.
   *
   * `ToolView` renders tool components with no props, so a page cannot call
   * `handleSelectConv` directly. This mirrors the `open-tool` event above rather
   * than restructuring `ToolView` to thread props through - reshaping the shell
   * inside a UI-defect epic is the scope creep D-25 warns about.
   */
  useEffect(() => {
    const openConv = (e) => { if (e.detail) handleSelectConv(e.detail); };
    const changed = (e) => {
      const deleted = e.detail?.deletedIds || [];
      // Never leave the chat view pointing at a conversation that is gone.
      if (deleted.length && activeConvId && deleted.includes(activeConvId)) {
        setActiveConvId(null);
        setActiveConvTitle('');
      }
      // The sidebar is on screen at the same time and would keep offering rows
      // that no longer exist.
      setConvRefresh(n => n + 1);
    };
    window.addEventListener('open-conversation', openConv);
    window.addEventListener('conversations-changed', changed);
    return () => {
      window.removeEventListener('open-conversation', openConv);
      window.removeEventListener('conversations-changed', changed);
    };
  }, [activeConvId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowCmdPalette(v => !v);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  /**
   * Someone else signed in on this computer - drop the previous person's open tool.
   *
   * D-59 (owner decision 2026-08-04, decision 3): a link that points straight at a
   * screen must work when it is opened in a fresh browser tab. The old version of
   * this check cleared `?tool=` whenever the tab held no record of the current user,
   * and a brand new tab NEVER holds one - so a pasted deep link always landed on the
   * chat screen instead of the tool it named.
   *
   * The distinction that was missing:
   *   - no record at all  = FIRST visit in this tab. Nobody else's session can be on
   *                         screen, because nothing has been on screen yet. Record
   *                         who this is and leave the URL exactly as it arrived.
   *   - a DIFFERENT record = someone else used this tab. Clear the tool and the
   *                         conversation, which is the safety behaviour this check
   *                         was written for.
   *
   * Signing out and signing in as someone else on the same machine still clears,
   * because nothing removes this key on logout: the tab keeps the previous person's
   * id, the next person's id does not match it, and the else-branch fires. The ref
   * covers the same swap happening without this component unmounting.
   */
  useEffect(() => {
    const SESSION_KEY = 'eduflow_session_user';
    const lastUserId = sessionStorage.getItem(SESSION_KEY);
    const isFirstVisitInThisTab = lastUserId === null;
    const isDifferentUser = !isFirstVisitInThisTab && lastUserId !== currentUser.id;
    const switchedWhileMounted = previousUserIdRef.current !== currentUser.id;

    previousUserIdRef.current = currentUser.id;
    sessionStorage.setItem(SESSION_KEY, currentUser.id);

    if (isDifferentUser || switchedWhileMounted) {
      setActiveToolParam(null, { replace: true });
      setActiveConvId(null);
      setActiveConvTitle('');
    }
  }, [currentUser.id, setActiveToolParam]);

  // Tapping outside the open drawer closes it. Same 768px breakpoint as
  // closeDrawerOnNavigate and as the drawer's own CSS - all three must agree.
  useEffect(() => {
    const handleClick = (e) => {
      if (window.innerWidth <= MOBILE_BREAKPOINT && sidebarOpen) {
        if (e.target.closest?.('[aria-label="Open menu"]')) return;
        const sidebar = document.querySelector('.sidebar-wrapper');
        if (sidebar && !sidebar.contains(e.target)) {
          setSidebarOpen(false);
        }
      }
    };
    if (window.innerWidth <= MOBILE_BREAKPOINT) {
      document.addEventListener('mousedown', handleClick);
    }
    return () => document.removeEventListener('mousedown', handleClick);
  }, [sidebarOpen]);

  // Epic 9: this used to be `isDark ? '#111111' : '#f5f5f5'` - a pair of
  // literals computed in JS, which meant the app shell painted its own
  // background and was the one surface the design tokens could not reach.
  // Switching themes recoloured the text and left this white. Read the token
  // instead, so there is exactly one place that decides what the page is.
  return (
    <div data-testid="app-layout" style={{ display: 'flex', height: '100vh', background: 'var(--color-page)', overflow: 'hidden' }}>
      {sidebarOpen && (
        <div onClick={() => setSidebarOpen(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 39, display: 'none', backdropFilter: 'blur(2px)' }} className="mobile-overlay" />
      )}

      <Sidebar
        onSelectTool={handleSelectTool}
        onSelectConv={handleSelectConv}
        onNewChat={handleNewChat}
        activeTool={activeTool}
        activeConvId={activeConvId}
        convRefresh={convRefresh}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
      />

      <div className="app-main-content" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <Header
          activeTool={activeTool}
          activeConvTitle={activeConvTitle}
          onBack={handleBack}
          canGoBack={toolTrail.length > 0}
          onOpenProfile={() => setShowProfile(true)}
          onOpenSettings={() => setShowSettings(true)}
          onToggleSidebar={() => setSidebarOpen(v => !v)}
        />
        <div style={{ flex: 1, overflow: 'hidden' }}>
          {activeTool ? (
            <ToolView toolId={activeTool} />
          ) : (
            <ChatInterface
              activeConvId={activeConvId}
              activeConvTitle={activeConvTitle}
              onConvCreated={handleConvCreated}
            />
          )}
        </div>
      </div>

      {showProfile && <ProfileModal onClose={() => setShowProfile(false)} />}
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      {showCmdPalette && <CommandPalette onSelectTool={handleSelectTool} onClose={() => setShowCmdPalette(false)} />}
    </div>
  );
}
