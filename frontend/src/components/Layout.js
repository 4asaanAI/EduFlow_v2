import React, { useState, useEffect } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import Sidebar from './Sidebar';
import Header from './Header';
import ChatInterface from './ChatInterface';
import { createConversation, getConversations } from '../lib/api';
import ProfileModal from './ProfileModal';
import SettingsModal from './SettingsModal';

const loadTool = async (toolId) => {
  const OWNERS = ['school-pulse','fee-collection','student-strength','attendance-overview','staff-attendance-tracker','financial-reports','announcement-broadcaster','admission-funnel','staff-leave-manager','staff-performance','ai-health-report','smart-alerts','expense-tracker','complaint-tracker','custom-report-builder','board-report'];
  const ADMINS = ['student-database','fee-tracker','attendance-recorder','certificate-generator','circular-sender','enquiry-register','document-scanner','smart-fee-defaulter','admission-pipeline','parent-message','student-transfer','id-card-generator','timetable-builder','asset-tracker','transport-manager','automated-report','custom-form-builder','report-card-builder','student-performance-viewer'];
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
  useEffect(() => {
    loadTool(toolId).then(C => setComp(() => C || null));
  }, [toolId]);
  if (!Comp) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748B', flexDirection: 'column', gap: 12 }}>
      <div className="spinner" />
      <span>Loading tool...</span>
    </div>
  );
  return <Comp />;
}

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

  const handleNewChat = async () => {
    setActiveTool(null);
    const res = await createConversation(currentUser);
    if (res.success) {
      setActiveConvId(res.data.id);
      setActiveConvTitle('');
      setConvRefresh(n => n + 1);
    }
  };

  const handleSelectTool = (toolId) => setActiveTool(toolId);

  const handleSelectConv = async (convId) => {
    setActiveTool(null);
    setActiveConvId(convId);
    // Find conv title
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

  // Listen for tool open events from Quick Actions
  useEffect(() => {
    const handler = (e) => { if (e.detail) { setActiveTool(e.detail); } };
    window.addEventListener('open-tool', handler);
    return () => window.removeEventListener('open-tool', handler);
  }, []);

  // Reset on role switch
  useEffect(() => {
    setActiveTool(null);
    setActiveConvId(null);
    setActiveConvTitle('');
  }, [currentUser.id]);

  // Mobile: close sidebar when clicking outside (only on mobile)
  useEffect(() => {
    const handleClick = (e) => {
      if (window.innerWidth <= 768 && sidebarOpen) {
        const sidebar = document.querySelector('.sidebar-wrapper');
        const menuBtn = document.querySelector('[data-testid="main-header"] button');
        if (sidebar && !sidebar.contains(e.target)) {
          setSidebarOpen(false);
        }
      }
    };
    // Only add listener, don't auto-close on desktop
    if (window.innerWidth <= 768) {
      document.addEventListener('mousedown', handleClick);
    }
    return () => document.removeEventListener('mousedown', handleClick);
  }, [sidebarOpen]);

  const bg = isDark ? '#0A0A0F' : '#F8F9FC';

  return (
    <div style={{ display: 'flex', height: '100vh', background: bg, overflow: 'hidden' }}>
      {/* Mobile overlay — only on mobile */}
      {sidebarOpen && (
        <div onClick={() => setSidebarOpen(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 39, display: 'none' }} className="mobile-overlay" />
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
    </div>
  );
}
