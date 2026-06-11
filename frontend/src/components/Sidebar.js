import React, { useState, useEffect, useRef } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { getConversations, updateConversation, deleteConversation } from '../lib/api';
import {
  Activity, IndianRupee, Users, BarChart2, Bell, FileText, HeartPulse, Megaphone,
  CalendarDays, UserPlus, MessageSquare, Pin, Star, Trash2, Plus, BookOpen,
  ClipboardList, Brain, PenTool, BarChart, UserCheck, Award, Truck,
  Package, Printer, FilePlus, HelpCircle, Target, Compass, FileCheck,
  Edit2, X, ChevronDown, ChevronRight, MessageCircle, Settings, User, LogOut, Sun, Moon,
  LifeBuoy, Database, RefreshCw, Wrench, Monitor, AlertTriangle, ScrollText, Trophy,
} from 'lucide-react';

const TOOLS_BY_ROLE = {
  owner: [
    { id: 'school-pulse', name: 'School Pulse', subtitle: "Today's overview", icon: Activity, color: '#fb923c' },
    { id: 'fee-collection', name: 'Fee Collection', subtitle: 'Revenue & defaulters', icon: IndianRupee, color: '#4f8ff7' },
    { id: 'fee-sync', name: 'Fee Sync', subtitle: 'External API conflicts', icon: RefreshCw, color: '#6366f1' },
    { id: 'student-database', name: 'Student Database', subtitle: 'Strength, manage & search', icon: Users, color: '#4f8ff7' },
    { id: 'data-import', name: 'Data Import', subtitle: 'Validate & seed students', icon: Database, color: '#22d3ee' },
    { id: 'attendance-overview', name: 'Attendance Overview', subtitle: 'Trends & patterns', icon: ClipboardList, color: '#a78bfa' },
    { id: 'staff-tracker', name: 'Staff Tracker', subtitle: 'Profiles & roles', icon: UserCheck, color: '#4f8ff7' },
    { id: 'staff-attendance-tracker', name: 'Staff Attendance', subtitle: 'Attendance & leaves', icon: UserCheck, color: '#22d3ee' },
    { id: 'financial-reports', name: 'Financial Reports', subtitle: 'Revenue & expenses', icon: FileText, color: '#22d3ee' },
    { id: 'announcement-broadcaster', name: 'Announcements', subtitle: 'Broadcast messages', icon: Megaphone, color: '#fbbf24' },
    { id: 'admission-funnel', name: 'Admission Funnel', subtitle: 'Enquiries & conversions', icon: UserPlus, color: '#4f8ff7' },
    { id: 'staff-leave-manager', name: 'Leave Manager', subtitle: 'Approve / reject', icon: CalendarDays, color: '#34d399' },
    { id: 'staff-performance', name: 'Staff Performance', subtitle: 'Overview & analytics', icon: BarChart2, color: '#fb923c' },
    { id: 'ai-health-report', name: 'AI Health Report', subtitle: 'Weekly auto-summary', icon: HeartPulse, color: '#f472b6' },
    { id: 'smart-alerts', name: 'Smart Alerts', subtitle: 'Exceptions & flags', icon: Bell, color: '#f87171' },
    { id: 'expense-tracker', name: 'Expense Tracker', subtitle: 'Track & approve', icon: IndianRupee, color: '#fbbf24' },
    { id: 'custom-report-builder', name: 'Custom Reports', subtitle: 'Build any report', icon: FilePlus, color: '#737373' },
    { id: 'board-report', name: 'Board Report', subtitle: 'Trust meeting data', icon: FileText, color: '#737373' },
    { id: 'smart-fee-defaulter', name: 'Fee Defaulters', subtitle: 'Reminders via SMS', icon: Bell, color: '#f87171' },
    { id: 'attendance-alerts', name: 'Attendance Alerts', subtitle: 'SMS below threshold', icon: MessageSquare, color: '#a78bfa' },
    { id: 'facility-requests', name: 'Facility Requests', subtitle: 'Maintenance queue', icon: Wrench, color: '#fb923c' },
    { id: 'maintenance-schedule', name: 'Maintenance Schedule', subtitle: 'Preventive calendar', icon: CalendarDays, color: '#fbbf24' },
    { id: 'vendor-log', name: 'Vendor Log', subtitle: 'Contractors & vendors', icon: Users, color: '#22d3ee' },
    { id: 'incident-tracker', name: 'Incidents & Visitors', subtitle: 'Log & track', icon: AlertTriangle, color: '#f87171' },
    { id: 'school-activities', name: 'School Activities', subtitle: 'Houses, sports, awards', icon: Trophy, color: '#f59e0b' },
    { id: 'audit-log', name: 'Audit Log', subtitle: 'Who did what', icon: ScrollText, color: '#737373' },
    { id: 'fee-receipts', name: 'Fee Receipts', subtitle: 'PDF & export', icon: FileText, color: '#34d399' },
    { id: 'query-section', name: 'Query & Support', subtitle: 'Tickets & issues', icon: LifeBuoy, color: '#22d3ee' },
  ],
  admin: [
    { id: 'student-database', name: 'Student Database', subtitle: 'Manage & search', icon: Users, color: '#4f8ff7' },
    { id: 'fee-tracker', name: 'Fee Tracker', subtitle: 'Reminders & dues', icon: IndianRupee, color: '#34d399' },
    { id: 'fee-receipts', name: 'Fee Receipts', subtitle: 'PDF & export', icon: FileText, color: '#34d399' },
    { id: 'attendance-recorder', name: 'Attendance', subtitle: 'Mark & track', icon: ClipboardList, color: '#fb923c' },
    { id: 'principal-daily', name: 'Principal Daily', subtitle: 'Absences & substitutes', icon: CalendarDays, color: '#fbbf24' },
    { id: 'certificate-generator', name: 'Certificates', subtitle: 'TC, Bonafide, etc.', icon: Award, color: '#fbbf24' },
    { id: 'circular-sender', name: 'Circulars', subtitle: 'Notices & messages', icon: Megaphone, color: '#22d3ee' },
    { id: 'enquiry-register', name: 'Enquiry Register', subtitle: 'Admission leads', icon: UserPlus, color: '#a78bfa' },
    { id: 'document-scanner', name: 'Doc Scanner', subtitle: 'Extract & file', icon: FileCheck, color: '#737373' },
    { id: 'smart-fee-defaulter', name: 'Fee Defaulters', subtitle: 'Smart reminders', icon: Bell, color: '#f87171' },
    { id: 'admission-pipeline', name: 'Admission Pipeline', subtitle: 'Track conversions', icon: Target, color: '#4f8ff7' },
    { id: 'parent-message', name: 'Parent Messages', subtitle: 'Compose & send', icon: MessageSquare, color: '#34d399' },
    { id: 'student-transfer', name: 'Student Transfer', subtitle: 'Withdrawal & TC', icon: UserPlus, color: '#fb923c' },
    { id: 'id-card-generator', name: 'ID Cards', subtitle: 'Generate & print', icon: Printer, color: '#a78bfa' },
    { id: 'timetable-builder', name: 'Timetable', subtitle: 'Build & manage', icon: CalendarDays, color: '#f472b6' },
    { id: 'asset-tracker', name: 'Asset Tracker', subtitle: 'Inventory & items', icon: Package, color: '#22d3ee' },
    { id: 'transport-manager', name: 'Transport', subtitle: 'Routes & buses', icon: Truck, color: '#fb923c' },
    { id: 'transport-optimisation', name: 'Route Optimisation', subtitle: 'Geocode & cluster analysis', icon: Truck, color: '#22d3ee' },
    { id: 'facility-requests', name: 'Facility Requests', subtitle: 'Maintenance queue', icon: Wrench, color: '#fb923c' },
    { id: 'maintenance-schedule', name: 'Maintenance Schedule', subtitle: 'Preventive calendar', icon: CalendarDays, color: '#fbbf24' },
    { id: 'vendor-log', name: 'Vendor Log', subtitle: 'Contractors & vendors', icon: Users, color: '#22d3ee' },
    { id: 'raise-maintenance', name: 'Report an Issue', subtitle: 'Raise maintenance request', icon: Wrench, color: '#fb923c' },
    { id: 'tech-issues', name: 'Tech Issues', subtitle: 'IT request tracker', icon: Monitor, color: '#818cf8' },
    { id: 'incident-tracker', name: 'Incidents & Visitors', subtitle: 'Log & track', icon: AlertTriangle, color: '#f87171' },
    { id: 'school-activities', name: 'School Activities', subtitle: 'Houses, sports, awards', icon: Trophy, color: '#f59e0b' },
    { id: 'audit-log', name: 'Audit Log', subtitle: 'Who did what', icon: ScrollText, color: '#737373' },
    { id: 'automated-report', name: 'Auto Reports', subtitle: 'Scheduled reports', icon: FileText, color: '#737373' },
    { id: 'custom-form-builder', name: 'Form Builder', subtitle: 'Dynamic forms', icon: FilePlus, color: '#737373' },
    { id: 'attendance-alerts', name: 'Attendance Alerts', subtitle: 'SMS below threshold', icon: MessageSquare, color: '#a78bfa' },
    { id: 'attendance-overview', name: 'Attendance Overview', subtitle: 'Trends & patterns', icon: ClipboardList, color: '#a78bfa' },
    { id: 'staff-tracker', name: 'Staff Tracker', subtitle: 'Profiles & roles', icon: UserCheck, color: '#4f8ff7' },
    { id: 'staff-performance', name: 'Staff Performance', subtitle: 'Overview & analytics', icon: BarChart2, color: '#fb923c' },
    { id: 'staff-leave-manager', name: 'Leave Manager', subtitle: 'Approve / reject', icon: CalendarDays, color: '#34d399' },
    { id: 'smart-alerts', name: 'Smart Alerts', subtitle: 'Exceptions & flags', icon: Bell, color: '#f87171' },
    { id: 'query-section', name: 'Query & Support', subtitle: 'Tickets & issues', icon: LifeBuoy, color: '#22d3ee' },
  ],
  teacher: [
    { id: 'class-attendance-marker', name: 'Attendance', subtitle: 'Mark my class', icon: ClipboardList, color: '#fb923c' },
    { id: 'assignment-generator', name: 'Assignments', subtitle: 'Create & manage', icon: BookOpen, color: '#4f8ff7' },
    { id: 'question-paper-creator', name: 'Question Papers', subtitle: 'Create & export', icon: PenTool, color: '#34d399' },
    { id: 'report-card-builder', name: 'Report Cards', subtitle: 'Enter & generate', icon: FileText, color: '#a78bfa' },
    { id: 'student-performance-viewer', name: 'Student Performance', subtitle: 'Marks & trends', icon: BarChart2, color: '#22d3ee' },
    { id: 'leave-application', name: 'Leave Application', subtitle: 'Apply for leave', icon: CalendarDays, color: '#fbbf24' },
    { id: 'lesson-plan-generator', name: 'Lesson Plans', subtitle: 'Plan chapters', icon: BookOpen, color: '#f472b6' },
    { id: 'worksheet-creator', name: 'Worksheets', subtitle: 'Practice sheets', icon: FilePlus, color: '#fb923c' },
    { id: 'class-performance-analytics', name: 'Class Analytics', subtitle: 'Trends & insights', icon: BarChart, color: '#a78bfa' },
    { id: 'substitution-viewer', name: 'Substitutions', subtitle: 'My schedule changes', icon: CalendarDays, color: '#737373' },
    { id: 'ptm-notes', name: 'PTM Notes', subtitle: 'Parent meet notes', icon: MessageSquare, color: '#34d399' },
    { id: 'curriculum-tracker', name: 'Curriculum', subtitle: 'Progress tracking', icon: Target, color: '#4f8ff7' },
    { id: 'form-submissions', name: 'Forms', subtitle: 'Surveys & forms', icon: FileText, color: '#22d3ee' },
    { id: 'raise-maintenance', name: 'Report an Issue', subtitle: 'Raise maintenance request', icon: Wrench, color: '#fb923c' },
  ],
  student: [
    { id: 'ai-tutor', name: 'AI Tutor', subtitle: 'Study help', icon: Brain, color: '#a78bfa' },
    { id: 'doubt-solver', name: 'Doubt Solver', subtitle: 'Ask any doubt', icon: HelpCircle, color: '#4f8ff7' },
    { id: 'homework-viewer', name: 'Homework', subtitle: 'My assignments', icon: BookOpen, color: '#fb923c' },
    { id: 'attendance-self-check', name: 'My Attendance', subtitle: 'View records', icon: ClipboardList, color: '#34d399' },
    { id: 'result-viewer', name: 'My Results', subtitle: 'Exam marks', icon: BarChart2, color: '#f472b6' },
    { id: 'practice-test', name: 'Practice Tests', subtitle: 'Self-assessment', icon: PenTool, color: '#fbbf24' },
    { id: 'study-planner', name: 'Study Planner', subtitle: 'Plan your week', icon: Target, color: '#22d3ee' },
    { id: 'career-guidance', name: 'Career Guidance', subtitle: 'Future planning', icon: Compass, color: '#a78bfa' },
    { id: 'fee-status-viewer', name: 'My Fees', subtitle: 'Payment status', icon: IndianRupee, color: '#4f8ff7' },
    { id: 'ptm-summary-viewer', name: 'PTM Summary', subtitle: 'Teacher notes', icon: MessageSquare, color: '#34d399' },
    { id: 'form-submissions', name: 'Forms', subtitle: 'Surveys & forms', icon: FileText, color: '#22d3ee' },
    { id: 'raise-maintenance', name: 'Report an Issue', subtitle: 'Raise maintenance request', icon: Wrench, color: '#fb923c' },
  ],
};

const ROLE_COLORS = { owner: '#fb923c', admin: '#4f8ff7', teacher: '#34d399', student: '#a78bfa' };
const ROLE_LABELS = { owner: 'Owner', admin: 'Admin', teacher: 'Teacher', student: 'Student' };

const ADMIN_SUBCATEGORY_TOOLS = {
  accountant: ['student-database', 'fee-tracker', 'smart-fee-defaulter', 'fee-receipts', 'custom-form-builder', 'raise-maintenance'],
  transport_head: ['student-database', 'transport-manager', 'transport-optimisation', 'asset-tracker', 'custom-form-builder', 'raise-maintenance'],
  principal: [
    'student-database', 'attendance-recorder', 'attendance-overview', 'principal-daily',
    'timetable-builder', 'certificate-generator', 'circular-sender', 'parent-message',
    'enquiry-register', 'admission-pipeline', 'smart-fee-defaulter', 'staff-tracker',
    'staff-performance', 'staff-leave-manager', 'incident-tracker', 'smart-alerts',
    'transport-manager', 'school-activities', 'document-scanner', 'audit-log',
    'facility-requests', 'raise-maintenance', 'custom-form-builder', 'query-section',
  ],
  receptionist: ['student-database', 'enquiry-register', 'admission-pipeline', 'parent-message', 'student-transfer', 'id-card-generator', 'asset-tracker', 'incident-tracker', 'raise-maintenance', 'custom-form-builder'],
  it_tech: ['tech-issues', 'raise-maintenance', 'custom-form-builder', 'query-section'],
  maintenance: ['maintenance-schedule', 'vendor-log', 'raise-maintenance'],
};

// ─── Grouped navigation config per role ──────────────────────────────────────
const TOOL_GROUPS = {
  owner: {
    top: ['school-pulse'],
    groups: [
      { id: 'fee', name: 'Fee Summary', icon: IndianRupee, color: '#4f8ff7',
        tools: ['fee-collection', 'fee-sync', 'financial-reports', 'expense-tracker', 'smart-fee-defaulter'] },
      { id: 'database', name: 'Database', icon: Database, color: '#22d3ee',
        tools: ['student-database', 'data-import', 'staff-tracker'] },
      { id: 'attendance', name: 'Attendance', icon: ClipboardList, color: '#a78bfa',
        tools: ['attendance-overview', 'staff-attendance-tracker', 'staff-performance', 'attendance-alerts'] },
      { id: 'internals', name: 'School Internals', icon: Megaphone, color: '#fbbf24',
        tools: ['announcement-broadcaster', 'staff-leave-manager', 'custom-report-builder', 'board-report', 'school-activities'] },
      { id: 'ai', name: 'Smart AI', icon: Brain, color: '#f472b6',
        tools: ['ai-health-report', 'smart-alerts'] },
      { id: 'queries', name: 'Queries', icon: Wrench, color: '#fb923c',
        tools: ['vendor-log', 'facility-requests', 'maintenance-schedule'] },
    ],
    bottom: ['audit-log', 'query-section'],
  },
  principal: {
    top: ['principal-daily'],
    groups: [
      { id: 'students', name: 'Students', icon: Users, color: '#4f8ff7',
        tools: ['student-database', 'certificate-generator', 'admission-pipeline', 'enquiry-register', 'document-scanner', 'id-card-generator'] },
      { id: 'attendance', name: 'Attendance', icon: ClipboardList, color: '#a78bfa',
        tools: ['attendance-recorder', 'attendance-overview'] },
      { id: 'staff', name: 'Staff', icon: UserCheck, color: '#34d399',
        tools: ['staff-tracker', 'staff-performance', 'staff-leave-manager'] },
      { id: 'communication', name: 'Communication', icon: MessageSquare, color: '#fbbf24',
        tools: ['circular-sender', 'parent-message'] },
      { id: 'operations', name: 'Operations', icon: CalendarDays, color: '#f472b6',
        tools: ['timetable-builder', 'transport-manager', 'school-activities', 'incident-tracker', 'smart-alerts'] },
      { id: 'facilities', name: 'Facilities', icon: Wrench, color: '#fb923c',
        tools: ['facility-requests', 'raise-maintenance', 'smart-fee-defaulter'] },
    ],
    bottom: ['audit-log', 'query-section'],
  },
  teacher: {
    top: [],
    groups: [
      { id: 'classroom', name: 'Classroom', icon: BookOpen, color: '#fb923c',
        tools: ['class-attendance-marker', 'assignment-generator', 'worksheet-creator', 'question-paper-creator'] },
      { id: 'academics', name: 'Academics', icon: BarChart2, color: '#4f8ff7',
        tools: ['report-card-builder', 'student-performance-viewer', 'curriculum-tracker', 'class-performance-analytics'] },
      { id: 'planning', name: 'Planning', icon: CalendarDays, color: '#a78bfa',
        tools: ['lesson-plan-generator', 'substitution-viewer', 'ptm-notes'] },
      { id: 'personal', name: 'Personal', icon: User, color: '#34d399',
        tools: ['leave-application'] },
    ],
    bottom: ['form-submissions', 'raise-maintenance'],
  },
  student: {
    top: [],
    groups: [
      { id: 'learning', name: 'Learning', icon: Brain, color: '#a78bfa',
        tools: ['ai-tutor', 'doubt-solver', 'homework-viewer', 'practice-test'] },
      { id: 'records', name: 'My Records', icon: FileText, color: '#4f8ff7',
        tools: ['attendance-self-check', 'result-viewer', 'ptm-summary-viewer', 'fee-status-viewer'] },
      { id: 'planning', name: 'Planning', icon: Target, color: '#22d3ee',
        tools: ['study-planner', 'career-guidance'] },
    ],
    bottom: ['form-submissions', 'raise-maintenance'],
  },
};

function getGroupConfig(user) {
  if (user.role === 'owner') return TOOL_GROUPS.owner;
  if (user.role === 'admin' && user.sub_category === 'principal') return TOOL_GROUPS.principal;
  if (user.role === 'teacher') return TOOL_GROUPS.teacher;
  if (user.role === 'student') return TOOL_GROUPS.student;
  return null;
}

function getSidebarTools(user) {
  const tools = TOOLS_BY_ROLE[user.role] || [];
  if (user.role !== 'admin') return tools;
  const allowed = ADMIN_SUBCATEGORY_TOOLS[user.sub_category];
  if (!allowed) return tools;
  const ownerTools = user.sub_category === 'principal' ? (TOOLS_BY_ROLE.owner || []) : [];
  const allTools = [...new Map([...tools, ...ownerTools].filter(t => t?.id).map(t => [t.id, t])).values()];
  return allowed.map(id => allTools.find(tool => tool.id === id)).filter(Boolean);
}

function timeAgo(iso) {
  if (!iso) return '';
  // Append 'Z' to treat bare ISO strings as UTC (backend stores UTC without tz offset)
  const utcIso = (iso.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(iso)) ? iso : iso + 'Z';
  const diff = Date.now() - new Date(utcIso).getTime();
  if (diff < 0) return 'Just now';
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function ConvMenu({ conv, onClose, onRename, onPin, onStar, onDelete, isDark }) {
  const ref = useRef(null);
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);
  const bg = isDark ? '#252525' : '#ffffff';
  const border = isDark ? '#333' : '#e5e5e5';
  return (
    <div ref={ref} className="fade-in-scale" style={{ position: 'absolute', top: '100%', left: 4, right: 4, background: bg, border: `1px solid ${border}`, borderRadius: 10, padding: 4, zIndex: 200, boxShadow: 'var(--shadow-lg)' }}>
      {[
        { label: 'Rename', icon: Edit2, action: onRename },
        { label: conv.is_pinned ? 'Unpin' : 'Pin', icon: Pin, action: onPin },
        { label: conv.is_starred ? 'Unstar' : 'Star', icon: Star, action: onStar },
        { label: 'Delete', icon: Trash2, action: onDelete, danger: true },
      ].map(item => (
        <button key={item.label} onClick={() => { item.action(); onClose(); }}
          className="conv-menu-btn"
          style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '8px 10px', border: 'none', borderRadius: 7, cursor: 'pointer', color: item.danger ? '#f87171' : 'var(--text-secondary)', fontSize: 12, fontWeight: 500, transition: 'var(--transition-fast)' }}
        >
          <item.icon size={13} />{item.label}
        </button>
      ))}
    </div>
  );
}

export default function Sidebar({ onSelectTool, onSelectConv, onNewChat, activeTool, activeConvId, convRefresh, sidebarOpen, setSidebarOpen, onOpenProfile, onOpenSettings, isToolDashboardRole }) {
  const { currentUser, logout } = useUser();
  const { isDark, toggleTheme } = useTheme();
  const [conversations, setConversations] = useState([]);
  const [menuConvId, setMenuConvId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [renameVal, setRenameVal] = useState('');
  const [toolsExpanded, setToolsExpanded] = useState(false);
  const [chatsExpanded, setChatsExpanded] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [openGroups, setOpenGroups] = useState(() => {
    const cfg = getGroupConfig(currentUser);
    if (!cfg) return new Set();
    const active = cfg.groups.find(g => g.tools.includes(activeTool));
    return active ? new Set([active.id]) : new Set();
  });
  const userMenuRef = useRef(null);

  const tools = getSidebarTools(currentUser);
  const groupConfig = getGroupConfig(currentUser);

  useEffect(() => {
    if (!isToolDashboardRole) loadConversations();
  }, [currentUser.id, convRefresh, isToolDashboardRole]);

  // Auto-open the group that contains the currently active tool
  useEffect(() => {
    if (!groupConfig) return;
    const active = groupConfig.groups.find(g => g.tools.includes(activeTool));
    if (active) setOpenGroups(prev => new Set([...prev, active.id]));
  }, [activeTool]);

  useEffect(() => {
    const handleNavigate = (e) => {
      const toolId = e.detail?.toolId;
      if (toolId && onSelectTool) onSelectTool(toolId);
    };
    window.addEventListener('eduflow-navigate', handleNavigate);
    return () => window.removeEventListener('eduflow-navigate', handleNavigate);
  }, [onSelectTool]);

  useEffect(() => {
    const h = (e) => { if (userMenuRef.current && !userMenuRef.current.contains(e.target)) setShowUserMenu(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const loadConversations = async () => {
    try { const r = await getConversations(); if (r.success) setConversations(r.data || []); } catch {}
  };

  const commitRename = async (id) => {
    if (!renameVal.trim()) return;
    await updateConversation(id, { title: renameVal.trim() });
    setRenamingId(null); loadConversations();
  };

  const handlePin = async (conv) => { await updateConversation(conv.id, { is_pinned: !conv.is_pinned }); loadConversations(); };
  const handleStar = async (conv) => { await updateConversation(conv.id, { is_starred: !conv.is_starred }); loadConversations(); };
  const handleDelete = async (id) => { await deleteConversation(id); loadConversations(); };

  const toggleGroup = (id) => {
    setOpenGroups(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const bg = isDark ? '#141414' : '#ffffff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const tp = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#525252';
  const secondary = isDark ? '#a0a0a0' : '#525252';
  const hover = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)';
  const activeBg = isDark ? 'rgba(79,143,247,0.1)' : 'rgba(79,143,247,0.06)';

  const renderToolItem = (tool, indent = false) => {
    if (!tool) return null;
    const Icon = tool.icon;
    const isActive = activeTool === tool.id;
    return (
      <button key={tool.id} data-testid={`tool-btn-${tool.id}`} onClick={() => onSelectTool(tool.id)} title={tool.name}
        style={{
          display: 'flex', alignItems: 'center', gap: 9, width: '100%',
          padding: indent ? '5px 10px 5px 14px' : '6px 10px',
          background: isActive ? activeBg : 'transparent', border: 'none', borderRadius: 8,
          cursor: 'pointer', transition: 'all var(--transition-fast)', textAlign: 'left',
        }}
        onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = hover; }}
        onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
      >
        <div style={{
          width: 24, height: 24, borderRadius: 6, flexShrink: 0,
          background: isActive ? `${tool.color}18` : (isDark ? '#252525' : '#f5f5f5'),
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={12} color={isActive ? tool.color : muted} />
        </div>
        <span style={{ fontSize: 12, fontWeight: isActive ? 600 : 500, color: isActive ? tp : secondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
          {tool.name}
        </span>
      </button>
    );
  };

  const renderGroup = (group) => {
    const groupTools = group.tools.map(id => tools.find(t => t.id === id)).filter(Boolean);
    if (groupTools.length === 0) return null;
    const isOpen = openGroups.has(group.id);
    const hasActive = groupTools.some(t => t.id === activeTool);
    const GIcon = group.icon;
    return (
      <div key={group.id} style={{ marginBottom: 1 }}>
        <button onClick={() => toggleGroup(group.id)}
          style={{
            display: 'flex', alignItems: 'center', gap: 9, width: '100%', padding: '7px 10px',
            background: hasActive && !isOpen ? `${group.color}0f` : 'transparent',
            border: 'none', borderRadius: 8, cursor: 'pointer', transition: 'all var(--transition-fast)',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = hover; }}
          onMouseLeave={e => { e.currentTarget.style.background = hasActive && !isOpen ? `${group.color}0f` : 'transparent'; }}
        >
          <div style={{
            width: 26, height: 26, borderRadius: 7, flexShrink: 0,
            background: isOpen || hasActive ? `${group.color}18` : (isDark ? '#252525' : '#f5f5f5'),
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <GIcon size={13} color={isOpen || hasActive ? group.color : muted} />
          </div>
          <span style={{ fontSize: 12, fontWeight: 600, color: isOpen || hasActive ? tp : secondary, flex: 1, textAlign: 'left' }}>
            {group.name}
          </span>
          <ChevronDown size={12} color={muted} style={{ transform: isOpen ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.2s ease', flexShrink: 0 }} />
        </button>
        {isOpen && (
          <div className="fade-in" style={{ paddingLeft: 8 }}>
            {groupTools.map(t => renderToolItem(t, true))}
          </div>
        )}
      </div>
    );
  };

  const renderGroupedNav = () => {
    if (!groupConfig) {
      return (
        <div style={{ paddingTop: 4, display: 'flex', flexDirection: 'column', gap: 1 }}>
          {tools.map(t => renderToolItem(t))}
        </div>
      );
    }
    return (
      <div style={{ paddingTop: 4 }}>
        {groupConfig.top.map(id => renderToolItem(tools.find(t => t.id === id)))}
        {groupConfig.top.length > 0 && <div style={{ height: 6 }} />}
        {groupConfig.groups.map(renderGroup)}
      </div>
    );
  };

  // Bottom pinned tools (audit log, query & support) — separate non-scrolling strip
  const bottomTools = isToolDashboardRole && groupConfig
    ? groupConfig.bottom.map(id => tools.find(t => t.id === id)).filter(Boolean)
    : [];

  return (
    <>
      <style>{`
        @media (max-width: 768px) {
          .sidebar-wrapper { transform: ${sidebarOpen ? 'translateX(0)' : 'translateX(-100%)'}; transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1); position: fixed; left: 0; top: 0; z-index: 50; height: 100vh; }
        }
        @media (min-width: 769px) {
          .sidebar-wrapper { transform: translateX(0) !important; position: relative !important; }
        }
        .hide-emergent-badge, [class*="emergent-badge"], .emergent-watermark { display: none !important; }
      `}</style>
      <aside className="sidebar-wrapper" data-testid="sidebar" style={{
        width: 260, minWidth: 260, background: bg, borderRight: `1px solid ${border}`,
        display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', flexShrink: 0,
      }}>
        {/* Logo */}
        <div style={{ padding: '16px 16px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: isToolDashboardRole ? 4 : 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 30, height: 30, borderRadius: 8, background: 'linear-gradient(135deg, #4f8ff7, #a78bfa)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontSize: 14, fontWeight: 800, color: '#fff', fontFamily: 'Inter, sans-serif' }}>E</span>
              </div>
              <span style={{ fontWeight: 700, fontSize: 16, color: tp, letterSpacing: '-0.02em' }}>EduFlow</span>
            </div>
            <button onClick={() => setSidebarOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: muted, padding: 4, borderRadius: 6, display: 'none', transition: 'var(--transition-fast)' }} className="mobile-close"
              onMouseEnter={e => e.currentTarget.style.background = hover}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              <X size={16} />
            </button>
          </div>

          {!isToolDashboardRole && (
            <button data-testid="new-chat-btn" onClick={onNewChat} style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              padding: '10px', background: isDark ? '#252525' : '#f5f5f5',
              border: `1px solid ${border}`, borderRadius: 10, color: tp,
              fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'all var(--transition-fast)',
            }}
              onMouseEnter={e => { e.currentTarget.style.background = isDark ? '#2e2e2e' : '#ebebeb'; }}
              onMouseLeave={e => { e.currentTarget.style.background = isDark ? '#252525' : '#f5f5f5'; }}>
              <Plus size={15} strokeWidth={2.5} /> New Chat
            </button>
          )}
        </div>

        {/* Scrollable area */}
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '0 8px' }}>
          {isToolDashboardRole ? (
            renderGroupedNav()
          ) : (
            <>
              {/* Grouped Tools Section — shown ABOVE chat history */}
              <div style={{ marginBottom: 4 }}>
                <button
                  onClick={() => setToolsExpanded(v => !v)}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', padding: '8px 8px', background: 'transparent', border: 'none', cursor: 'pointer', color: muted, borderRadius: 6, transition: 'var(--transition-fast)' }}
                  onMouseEnter={e => e.currentTarget.style.background = hover}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.03em' }}>Tools ({tools.length})</span>
                  {toolsExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                </button>
                {toolsExpanded && (
                  <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {groupConfig ? (
                      <>
                        {groupConfig.top.map(id => renderToolItem(tools.find(t => t.id === id)))}
                        {groupConfig.top.length > 0 && <div style={{ height: 4 }} />}
                        {groupConfig.groups.map(renderGroup)}
                        {groupConfig.bottom.length > 0 && <div style={{ borderTop: `1px solid ${border}`, margin: '4px 0' }} />}
                        {groupConfig.bottom.map(id => renderToolItem(tools.find(t => t.id === id)))}
                      </>
                    ) : (
                      tools.map(t => renderToolItem(t))
                    )}
                  </div>
                )}
              </div>

              {/* Chat History — below tools, capped at 5 with expand */}
              {conversations.length > 0 && (
                <div style={{ borderTop: `1px solid ${border}`, marginTop: 4, paddingTop: 4 }}>
                  <div style={{ padding: '8px 8px 6px', fontSize: 11, fontWeight: 600, color: muted, letterSpacing: '0.03em' }}>
                    Chats
                  </div>
                  {(chatsExpanded ? conversations : conversations.slice(0, 5)).map(conv => (
                    <div key={conv.id} style={{ position: 'relative' }}>
                      {renamingId === conv.id ? (
                        <div style={{ padding: '3px 4px' }}>
                          <input autoFocus value={renameVal} onChange={e => setRenameVal(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') commitRename(conv.id); if (e.key === 'Escape') setRenamingId(null); }}
                            onBlur={() => commitRename(conv.id)}
                            style={{ width: '100%', background: isDark ? '#252525' : '#fafafa', border: `1px solid ${isDark ? '#4f8ff7' : '#4f8ff7'}`, borderRadius: 8, padding: '6px 10px', color: tp, fontSize: 12, outline: 'none' }}
                          />
                        </div>
                      ) : (
                        <button data-testid={`conv-btn-${conv.id}`}
                          onClick={() => onSelectConv(conv.id)}
                          onContextMenu={e => { e.preventDefault(); setMenuConvId(conv.id); }}
                          style={{
                            display: 'flex', flexDirection: 'column', alignItems: 'flex-start', width: '100%',
                            padding: '8px 10px', background: activeConvId === conv.id ? activeBg : 'transparent',
                            border: 'none', borderRadius: 8, cursor: 'pointer',
                            transition: 'all var(--transition-fast)', textAlign: 'left', gap: 2,
                          }}
                          onMouseEnter={e => { if (activeConvId !== conv.id) e.currentTarget.style.background = hover; }}
                          onMouseLeave={e => { if (activeConvId !== conv.id) e.currentTarget.style.background = 'transparent'; }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 5, width: '100%' }}>
                            <MessageCircle size={12} color={activeConvId === conv.id ? '#4f8ff7' : muted} style={{ flexShrink: 0 }} />
                            {conv.is_pinned && <Pin size={9} color="#fbbf24" />}
                            {conv.is_starred && <Star size={9} color="#fbbf24" />}
                            <span style={{ fontSize: 13, fontWeight: 500, color: activeConvId === conv.id ? tp : secondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                              {conv.title || 'New conversation'}
                            </span>
                          </div>
                          <span style={{ fontSize: 11, color: muted, paddingLeft: 17 }}>{timeAgo(conv.updated_at)}</span>
                        </button>
                      )}
                      {menuConvId === conv.id && (
                        <ConvMenu conv={conv} onClose={() => setMenuConvId(null)} isDark={isDark}
                          onRename={() => { setRenamingId(conv.id); setRenameVal(conv.title || ''); setMenuConvId(null); }}
                          onPin={() => handlePin(conv)} onStar={() => handleStar(conv)}
                          onDelete={() => handleDelete(conv.id)}
                        />
                      )}
                    </div>
                  ))}
                  {conversations.length > 5 && (
                    <button
                      onClick={() => setChatsExpanded(v => !v)}
                      style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%', padding: '6px 10px', background: 'transparent', border: 'none', borderRadius: 8, cursor: 'pointer', color: muted, fontSize: 11, fontWeight: 600, transition: 'var(--transition-fast)' }}
                      onMouseEnter={e => e.currentTarget.style.background = hover}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      {chatsExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                      {chatsExpanded ? 'Show less' : `${conversations.length - 5} more chats`}
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Pinned bottom tools: Audit Log + Query & Support */}
        {bottomTools.length > 0 && (
          <div style={{ borderTop: `1px solid ${border}`, padding: '4px 8px 2px' }}>
            {bottomTools.map(t => renderToolItem(t))}
          </div>
        )}

        {/* Bottom user section */}
        <div style={{ borderTop: `1px solid ${border}`, padding: '8px' }} ref={userMenuRef}>
          {showUserMenu && (
            <div className="fade-in-scale" style={{
              position: 'absolute', bottom: 64, left: 8, right: 8,
              background: isDark ? '#252525' : '#ffffff', border: `1px solid ${border}`,
              borderRadius: 12, padding: 6, boxShadow: 'var(--shadow-lg)', zIndex: 100,
            }}>
              <button onClick={toggleTheme}
                style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px', background: 'transparent', border: 'none', borderRadius: 8, cursor: 'pointer', color: secondary, fontSize: 13, fontWeight: 500, transition: 'var(--transition-fast)' }}
                onMouseEnter={e => e.currentTarget.style.background = hover}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                {isDark ? <Sun size={14} /> : <Moon size={14} />}
                <span>{isDark ? 'Light Mode' : 'Dark Mode'}</span>
              </button>
              <button onClick={onOpenSettings}
                style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px', background: 'transparent', border: 'none', borderRadius: 8, cursor: 'pointer', color: secondary, fontSize: 13, fontWeight: 500, transition: 'var(--transition-fast)' }}
                onMouseEnter={e => e.currentTarget.style.background = hover}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                <Settings size={14} />
                <span>Settings</span>
              </button>
              <div style={{ borderTop: `1px solid ${border}`, margin: '4px 0' }} />
              <button onClick={() => { logout(); setShowUserMenu(false); }}
                style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px', background: 'transparent', border: 'none', borderRadius: 8, cursor: 'pointer', color: '#f87171', fontSize: 13, fontWeight: 500, transition: 'var(--transition-fast)' }}
                onMouseEnter={e => e.currentTarget.style.background = hover}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                <LogOut size={14} />
                <span>Sign Out</span>
              </button>
            </div>
          )}

          <button onClick={() => setShowUserMenu(v => !v)} data-testid="role-switcher-btn"
            style={{
              display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '10px',
              background: showUserMenu ? hover : 'transparent',
              border: 'none', borderRadius: 10, cursor: 'pointer', transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={e => e.currentTarget.style.background = hover}
            onMouseLeave={e => { if (!showUserMenu) e.currentTarget.style.background = 'transparent'; }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8, background: ROLE_COLORS[currentUser.role],
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, fontWeight: 700, color: '#fff', flexShrink: 0,
            }}>
              {currentUser.initials}
            </div>
            <div style={{ flex: 1, textAlign: 'left', minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: tp, lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{currentUser.name}</div>
              <div style={{ fontSize: 11, color: ROLE_COLORS[currentUser.role], fontWeight: 600, lineHeight: 1.2, marginTop: 1 }}>{ROLE_LABELS[currentUser.role]}</div>
            </div>
            <ChevronDown size={14} color={muted} style={{ transform: showUserMenu ? 'rotate(180deg)' : 'none', transition: 'var(--transition-fast)' }} />
          </button>
        </div>
      </aside>
    </>
  );
}
