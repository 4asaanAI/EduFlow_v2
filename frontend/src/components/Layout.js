import React, { useState, useEffect } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import Sidebar from './Sidebar';
import Header from './Header';
import ChatInterface from './ChatInterface';
import ToolDashboard from './ToolDashboard';
import FloatingAssistant from './FloatingAssistant';
import { createConversation, getConversations } from '../lib/api';
import ProfileModal from './ProfileModal';
import SettingsModal from './SettingsModal';

const loadTool = async (toolId) => {
  if (toolId === 'query-section') return (await import('./tools/QuerySection')).QuerySection;

  const OWNERS = ['school-pulse','fee-collection','student-strength','student-database','data-import','attendance-overview','staff-attendance-tracker','financial-reports','announcement-broadcaster','admission-funnel','staff-leave-manager','staff-performance','ai-health-report','smart-alerts','expense-tracker','complaint-tracker','custom-report-builder','board-report','smart-fee-defaulter','attendance-alerts'];
  const ADMINS = ['student-database','fee-tracker','attendance-recorder','certificate-generator','circular-sender','enquiry-register','document-scanner','smart-fee-defaulter','admission-pipeline','parent-message','student-transfer','id-card-generator','timetable-builder','asset-tracker','transport-manager','automated-report','custom-form-builder','report-card-builder','student-performance-viewer','attendance-alerts'];
  const TEACHERS = ['class-attendance-marker','assignment-generator','question-paper-creator','leave-application','lesson-plan-generator','worksheet-creator','class-performance-analytics','substitution-viewer','ptm-notes','curriculum-tracker','form-submissions'];
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
  return <Comp />;
}

const TOOL_DASHBOARD_ROLES = ['admin', 'teacher'];

export default function Layout() {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [activeTool, setActiveTool] = useState(null);
  const [activeConvId, setActiveConvId] = useState(null);
  const [activeConvTitle, setActiveConvTitle] = useState('');
  const [convRefresh, setConvRefresh] = useState(0);
  const [showProfile, setShowProfile] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const isToolDashboardRole = TOOL_DASHBOARD_ROLES.includes(currentUser.role);

  const handleNewChat = async () => {
    setActiveTool(null);
    const res = await createConversation(currentUser);
    if (res.success) {
      setActiveConvId(res.data.id);
      setActiveConvTitle('');
      setConvRefresh(n => n + 1);
    }
  };

  const handleSelectTool = (toolId) => {
    setActiveTool(toolId);
    if (isToolDashboardRole) {
      const key = `eduflow_activity_${currentUser.id}`;
      const prev = JSON.parse(localStorage.getItem(key) || '[]').filter(a => a.id !== toolId);
      prev.unshift({ id: toolId, at: new Date().toISOString() });
      localStorage.setItem(key, JSON.stringify(prev.slice(0, 30)));
    }
  };

  const handleSelectConv = async (convId) => {
    setActiveTool(null);
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
    const handler = (e) => { if (e.detail) { setActiveTool(e.detail); } };
    window.addEventListener('open-tool', handler);
    return () => window.removeEventListener('open-tool', handler);
  }, []);

  useEffect(() => {
    setActiveTool(null);
    setActiveConvId(null);
    setActiveConvTitle('');
  }, [currentUser.id]);

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
          onBackToChat={() => setActiveTool(null)}
          onOpenProfile={() => setShowProfile(true)}
          onOpenSettings={() => setShowSettings(true)}
          onToggleSidebar={() => setSidebarOpen(v => !v)}
        />
        <div style={{ flex: 1, overflow: 'hidden' }}>
          {activeTool ? (
            <ToolView toolId={activeTool} />
          ) : isToolDashboardRole ? (
            <ToolDashboard onSelectTool={handleSelectTool} />
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
      {isToolDashboardRole && <FloatingAssistant />}
    </div>
  );
}
