import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import Sidebar from './Sidebar';
import Header from './Header';
import ChatInterface from './ChatInterface';
import ErrorBoundary from './ErrorBoundary';
import FloatingAssistant from './FloatingAssistant';
import { createConversation, getConversations } from '../lib/api';
import ProfileModal from './ProfileModal';
import SettingsModal from './SettingsModal';
import CommandPalette from './CommandPalette';

const loadTool = async (toolId) => {
  // Phase 3 dedicated tool panels — loaded directly
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
  if (toolId === 'fee-receipts') return (await import('./tools/FeeCollection')).default;
  if (toolId === 'principal-daily') return (await import('./tools/PrincipalDailyOps')).default;
  if (toolId === 'exam-manager') return (await import('./tools/ExamManager')).default;
  if (toolId === 'what-ive-learned') return (await import('./tools/LearningTools')).default;
  if (toolId === 'conversation-trace') return (await import('./tools/ConversationTrace')).default;

  // Existing dedicated tools
  if (toolId === 'query-section') return (await import('./tools/QuerySection')).QuerySection;
  if (toolId === 'staff-tracker') return (await import('./tools/StaffTracker')).default;
  if (toolId === 'attendance-recorder') return (await import('./tools/AttendanceRecorder')).default;
  if (toolId === 'fee-collection') return (await import('./tools/FeeCollection')).default;
  if (toolId === 'fee-sync') return (await import('./tools/FeeSync')).default;
  if (toolId === 'student-database') return (await import('./tools/StudentDatabase')).default;
  if (toolId === 'school-activities') return (await import('./tools/SchoolActivities')).default;
  if (toolId === 'transport-optimisation') return (await import('./tools/TransportOptimisation')).default;

  const OWNERS = ['school-pulse','fee-collection','fee-sync','student-strength','data-import','attendance-overview','staff-tracker','staff-attendance-tracker','financial-reports','announcement-broadcaster','admission-funnel','staff-leave-manager','staff-performance','ai-health-report','smart-alerts','expense-tracker','custom-report-builder','board-report','smart-fee-defaulter','attendance-alerts','reports-trends','platform-health-dashboard'];
  const ADMINS = ['fee-tracker','certificate-generator','circular-sender','enquiry-register','document-scanner','smart-fee-defaulter','admission-pipeline','parent-message','student-transfer','id-card-generator','asset-tracker','transport-manager','automated-report','custom-form-builder','report-card-builder','student-performance-viewer','attendance-alerts','reports-trends','timetable-builder'];
  const TEACHERS = ['class-attendance-marker','assignment-generator','question-paper-creator','report-card-builder','student-performance-viewer','leave-application','lesson-plan-generator','worksheet-creator','class-performance-analytics','substitution-viewer','ptm-notes','curriculum-tracker','form-submissions'];
  const STUDENTS = ['ai-tutor','doubt-solver','homework-viewer','attendance-self-check','result-viewer','practice-test','study-planner','career-guidance','fee-status-viewer','ptm-summary-viewer','form-submissions'];

  const toComp = (id) => id.split('-').map(w => w[0].toUpperCase() + w.slice(1)).join('');
  if (OWNERS.includes(toolId)) return (await import('./tools/OwnerTools'))[toComp(toolId)];
  if (ADMINS.includes(toolId)) return (await import('./tools/AdminTools'))[toComp(toolId)];
  if (TEACHERS.includes(toolId)) return (await import('./tools/TeacherTools'))[toComp(toolId)];
  if (STUDENTS.includes(toolId)) return (await import('./tools/StudentTools'))[toComp(toolId)];
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

export default function Layout() {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTool = searchParams.get('tool');
  const [activeConvId, setActiveConvId] = useState(null);
  const [activeConvTitle, setActiveConvTitle] = useState('');
  const [convRefresh, setConvRefresh] = useState(0);
  const [showProfile, setShowProfile] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showCmdPalette, setShowCmdPalette] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const previousUserIdRef = useRef(currentUser.id);

  const isToolDashboardRole = TOOL_DASHBOARD_ROLES.includes(currentUser.role);

  const setActiveToolParam = useCallback((toolId, options = {}) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (toolId) next.set('tool', toolId);
      else next.delete('tool');
      return next;
    }, { replace: !!options.replace });
  }, [setSearchParams]);

  const handleNewChat = async () => {
    setActiveToolParam(null);
    const res = await createConversation(currentUser);
    if (res.success) {
      setActiveConvId(res.data.id);
      setActiveConvTitle('');
      setConvRefresh(n => n + 1);
    }
  };

  const handleSelectTool = (toolId) => {
    setActiveToolParam(toolId);
    if (isToolDashboardRole) {
      const key = `eduflow_activity_${currentUser.id}`;
      const prev = JSON.parse(localStorage.getItem(key) || '[]').filter(a => a.id !== toolId);
      prev.unshift({ id: toolId, at: new Date().toISOString() });
      localStorage.setItem(key, JSON.stringify(prev.slice(0, 30)));
    }
  };

  const handleSelectConv = async (convId) => {
    setActiveToolParam(null);
    setActiveConvId(convId);
    try {
      const res = await getConversations(currentUser);
      const conv = res.data?.find(c => c.id === convId);
      setActiveConvTitle(conv?.title || '');
    } catch {}
  };

  const handleConvCreated = (convId) => {
    setActiveConvId(convId);
    setConvRefresh(n => n + 1);
  };

  useEffect(() => {
    const handler = (e) => { if (e.detail) { setActiveToolParam(e.detail); } };
    window.addEventListener('open-tool', handler);
    return () => window.removeEventListener('open-tool', handler);
  }, [setActiveToolParam]);

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

  useEffect(() => {
    const SESSION_KEY = 'eduflow_session_user';
    const lastUserId = sessionStorage.getItem(SESSION_KEY);
    const isNewUser = previousUserIdRef.current !== currentUser.id || lastUserId !== currentUser.id;
    if (isNewUser) {
      previousUserIdRef.current = currentUser.id;
      sessionStorage.setItem(SESSION_KEY, currentUser.id);
      setActiveToolParam(null, { replace: true });
      setActiveConvId(null);
      setActiveConvTitle('');
    }
  }, [currentUser.id, setActiveToolParam]);

  useEffect(() => {
    const handleClick = (e) => {
      if (window.innerWidth <= 768 && sidebarOpen) {
        const sidebar = document.querySelector('.sidebar-wrapper');
        if (sidebar && !sidebar.contains(e.target)) {
          setSidebarOpen(false);
        }
      }
    };
    if (window.innerWidth <= 768) {
      document.addEventListener('mousedown', handleClick);
    }
    return () => document.removeEventListener('mousedown', handleClick);
  }, [sidebarOpen]);

  const bg = isDark ? '#111111' : '#f5f5f5';

  return (
    <div data-testid="app-layout" style={{ display: 'flex', height: '100vh', background: bg, overflow: 'hidden' }}>
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
        onOpenProfile={() => setShowProfile(true)}
        onOpenSettings={() => setShowSettings(true)}
        isToolDashboardRole={isToolDashboardRole}
      />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <Header
          activeTool={activeTool}
          activeConvTitle={activeConvTitle}
          onBackToChat={() => setActiveToolParam(null)}
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
      {isToolDashboardRole && <FloatingAssistant />}
    </div>
  );
}
