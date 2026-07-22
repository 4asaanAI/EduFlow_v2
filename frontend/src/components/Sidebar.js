import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { getConversations, updateConversation, deleteConversation, getMyTokenUsage, getSchoolSettings } from '../lib/api';
import TokenUpgradeModal from './TokenUpgradeModal';
import {
  Activity, IndianRupee, Users, BarChart2, Bell, FileText, HeartPulse, Megaphone,
  CalendarDays, UserPlus, MessageSquare, Pin, Star, Trash2, Plus, BookOpen,
  ClipboardList, Brain, PenTool, BarChart, UserCheck, Award, Truck,
  Package, Printer, FilePlus, HelpCircle, Target, Compass, FileCheck,
  Edit2, X, ChevronDown, ChevronRight, MessageCircle, Settings, User, LogOut, Sun, Moon,
  LifeBuoy, Database, RefreshCw, Wrench, Monitor, AlertTriangle, ScrollText, Trophy,
  Search,
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
    { id: 'exam-manager', name: 'Exams', subtitle: 'Schedule & results', icon: ClipboardList, color: '#a78bfa' },
    { id: 'school-settings', name: 'School Settings', subtitle: 'Identity & profile', icon: Settings, color: '#737373' },
  ],
  admin: [
    { id: 'academic-structure', name: 'Academic Structure', subtitle: 'Classes, subjects & teachers', icon: BookOpen, color: '#4f8ff7' },
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
    { id: 'exam-manager', name: 'Exams', subtitle: 'Schedule & results', icon: ClipboardList, color: '#a78bfa' },
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
    { id: 'exam-manager', name: 'Exams', subtitle: 'Schedule & results', icon: ClipboardList, color: '#a78bfa' },
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
    'academic-structure', 'student-database', 'attendance-recorder', 'attendance-overview', 'principal-daily',
    'timetable-builder', 'certificate-generator', 'circular-sender', 'parent-message',
    'enquiry-register', 'smart-fee-defaulter', 'staff-tracker',
    'staff-performance', 'staff-leave-manager', 'incident-tracker', 'smart-alerts',
    'transport-manager', 'school-activities', 'document-scanner', 'audit-log',
    'facility-requests', 'raise-maintenance', 'custom-form-builder', 'query-section', 'exam-manager',
  ],
  receptionist: ['student-database', 'enquiry-register', 'parent-message', 'student-transfer', 'id-card-generator', 'asset-tracker', 'incident-tracker', 'raise-maintenance', 'custom-form-builder'],
  it_tech: ['tech-issues', 'raise-maintenance', 'custom-form-builder', 'query-section'],
  maintenance: ['maintenance-schedule', 'vendor-log', 'raise-maintenance'],
  management: ['academic-structure', 'timetable-builder', 'exam-manager', 'raise-maintenance', 'audit-log', 'query-section'],
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
        tools: ['announcement-broadcaster', 'staff-leave-manager', 'custom-report-builder', 'board-report', 'school-activities', 'exam-manager', 'school-settings'] },
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
        tools: ['student-database', 'certificate-generator', 'enquiry-register', 'document-scanner', 'id-card-generator'] },
      { id: 'attendance', name: 'Attendance', icon: ClipboardList, color: '#a78bfa',
        tools: ['attendance-recorder', 'attendance-overview'] },
      { id: 'staff', name: 'Staff', icon: UserCheck, color: '#34d399',
        tools: ['staff-tracker', 'staff-performance', 'staff-leave-manager'] },
      { id: 'communication', name: 'Communication', icon: MessageSquare, color: '#fbbf24',
        tools: ['circular-sender', 'parent-message'] },
      { id: 'operations', name: 'Operations', icon: CalendarDays, color: '#f472b6',
        tools: ['academic-structure', 'timetable-builder', 'transport-manager', 'school-activities', 'exam-manager', 'incident-tracker', 'smart-alerts'] },
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
        tools: ['lesson-plan-generator', 'substitution-viewer', 'ptm-notes', 'exam-manager'] },
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
  const bg = 'var(--color-surface-raised)';
  const border = 'var(--color-border)';
  return (
    <div ref={ref} className="fade-in-scale" style={{ position: 'absolute', top: '100%', left: 4, right: 4, background: bg, border: `1px solid ${border}`, borderRadius: 'var(--radius-md)', padding: 4, zIndex: 200, boxShadow: 'var(--shadow-lg)' }}>
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
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [tokenUsage, setTokenUsage] = useState(null);
  const { isDark, toggleTheme } = useTheme();
  const [conversations, setConversations] = useState([]);
  const [menuConvId, setMenuConvId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [renameVal, setRenameVal] = useState('');
  const [toolsExpanded, setToolsExpanded] = useState(false);
  // (chatsExpanded removed with the "N more chats" expander — the zone now
  //  lists every conversation and scrolls on its own.)
  // Whether the Recent Chats section is open at all. Collapsing belongs on the
  // heading — that is where people reach for it — not on a link buried under the
  // list, which you had to scroll past the whole list to reach.
  const [chatsSectionOpen, setChatsSectionOpen] = useState(true);
  // Tools collapses exactly like Recent Chats — same control, same behaviour.
  const [toolsSectionOpen, setToolsSectionOpen] = useState(true);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [schoolName, setSchoolName] = useState('');
  const [schoolMeta, setSchoolMeta] = useState({ city: '', state: '', phone: '', email: '' });
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
    loadConversations();
  }, [currentUser.id, convRefresh]);

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
    const h = (e) => { if (userMenuRef.current && !userMenuRef.current.contains(e.target)) { setShowUserMenu(false); setShowHelp(false); } };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  useEffect(() => {
    getMyTokenUsage()
      .then(r => { if (r.success) setTokenUsage(r.data); })
      .catch(() => {});
  }, [currentUser.id]);

  // School identity — fetched for every role, refreshes when the owner saves settings
  useEffect(() => {
    const loadSchool = () => {
      getSchoolSettings()
        .then(r => {
          if (r.success && r.data) {
            if (r.data.school_name) setSchoolName(r.data.school_name);
            setSchoolMeta({
              city: r.data.city || '',
              state: r.data.state || '',
              phone: r.data.phone || '',
              email: r.data.email || '',
            });
          }
        })
        .catch(() => {});
    };
    loadSchool();
    window.addEventListener('school-settings-updated', loadSchool);
    return () => window.removeEventListener('school-settings-updated', loadSchool);
  }, [currentUser.id]);

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

  // Epic 9: these were `isDark ? '<hex>' : '<hex>'` pairs. Computing theme
  // colours in JS meant the sidebar painted itself from literals and was
  // invisible to the design tokens — switching themes recoloured the text and
  // left the surfaces behind. Reading tokens also means the browser handles
  // the switch, so no re-render is needed for the colours to change.
  const bg = 'var(--bg-sidebar)';
  const border = 'var(--color-border)';
  const tp = 'var(--color-text-primary)';
  const muted = 'var(--color-text-muted)';
  const secondary = 'var(--color-text-secondary)';
  const hover = 'var(--bg-hover)';
  const activeBg = 'var(--bg-active)';

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
          background: isActive ? `${tool.color}18` : 'var(--color-surface-raised)',
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
            background: isOpen || hasActive ? `${group.color}18` : 'var(--color-surface-raised)',
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {tools.map(t => renderToolItem(t))}
        </div>
      );
    }
    return (
      <div>
        {groupConfig.top.map(id => renderToolItem(tools.find(t => t.id === id)))}
        {groupConfig.top.length > 0 && <div style={{ height: 4 }} />}
        {groupConfig.groups.map(renderGroup)}
      </div>
    );
  };

  // Bottom pinned tools (audit log, query & support) — separate non-scrolling strip
  const bottomTools = isToolDashboardRole && groupConfig
    ? groupConfig.bottom.map(id => tools.find(t => t.id === id)).filter(Boolean)
    : [];

  // Section zone backgrounds — distinct but subtle.
  // Kept as explicit pairs rather than tokens: these two tints exist to tell
  // the tools zone and the chats zone apart, so they are deliberately NOT the
  // standard surface colour. Retuned onto the navy/paper palette in Epic 9.
  // Retuned to sit on the LIGHTER dark sidebar (#242424). The old values were
  // pitched against a #1A1A1A panel, so on the new surface they read as dark
  // holes rather than tinted zones, and their borders vanished entirely.
  const toolsZoneBg = isDark ? '#1D2432' : '#F1F6FF';          // cool blue tint
  const chatsZoneBg = isDark ? '#2A2118' : '#FFFAF2';          // warm amber tint
  const toolsZoneBorder = isDark ? '#3A4763' : '#E1EAFB';
  const chatsZoneBorder = isDark ? '#4A3A22' : '#FFEBD2';

  return (
    <>
      <style>{`
        @media (max-width: 768px) {
          .sidebar-wrapper {
            transform: ${sidebarOpen ? 'translateX(0)' : 'translateX(-100%)'};
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: fixed; left: 0; top: 0; z-index: 50; height: 100vh;
            width: 280px !important; min-width: 280px !important;
          }
          .mobile-close { display: flex !important; }
          .sidebar-overlay {
            display: ${sidebarOpen ? 'block' : 'none'};
            position: fixed; inset: 0; background: rgba(0,0,0,0.45);
            z-index: 49; backdrop-filter: blur(2px);
          }
        }
        @media (min-width: 769px) {
          .sidebar-wrapper { transform: translateX(0) !important; position: relative !important; }
          .sidebar-overlay { display: none !important; }
        }
        .hide-emergent-badge, [class*="emergent-badge"], .emergent-watermark { display: none !important; }
        .sidebar-scroll::-webkit-scrollbar { width: 4px; }
        .sidebar-scroll::-webkit-scrollbar-track { background: transparent; }
        .sidebar-scroll::-webkit-scrollbar-thumb { background: var(--color-border-strong); border-radius: 4px; }
        .sidebar-scroll::-webkit-scrollbar-thumb:hover { background: var(--color-text-muted); }
        .new-chat-btn {
          width: 100%; display: flex; align-items: center; justify-content: center; gap: 7px;
          padding: 10px 14px;
          /* Epic 9: the brand's blue-to-orange, and a chunky press rather than
             a flat gradient chip. White on this gradient stays above 4.5:1
             because the gradient never reaches the raw #2B8FF0. */
          background: linear-gradient(135deg, var(--brand-blue-fill) 0%, #3D63C9 55%, #7C5AD6 100%);
          border: none; border-radius: var(--radius-lg); color: #fff;
          font-family: var(--font-display);
          font-size: 14px; font-weight: 700; cursor: pointer;
          /* The chunky solid shadow of the brand, plus a soft glow. */
          box-shadow: 0 4px 0 0 var(--brand-blue-press), 0 6px 18px -8px rgba(43,143,240,0.5);
          transition: transform var(--transition-fast), box-shadow var(--transition-fast);
          letter-spacing: 0.01em;
        }
        .new-chat-btn:hover {
          box-shadow: 0 5px 0 0 var(--brand-blue-press), 0 10px 24px -8px rgba(43,143,240,0.6);
          transform: translateY(-1px);
        }
        /* Presses INTO its own shadow. transform only — never height or margin,
           or the whole sidebar below it would shift on every click. */
        .new-chat-btn:active {
          transform: translateY(3px);
          box-shadow: 0 1px 0 0 var(--brand-blue-press);
        }
        .zone-header {
          display: flex; align-items: center; gap: 6px;
          padding: 8px 10px 6px;
          font-size: 10px; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase;
        }
        .conv-btn-row { display: flex; flex-direction: column; align-items: flex-start; width: 100%; padding: 8px 10px; border: none; border-radius: 8px; cursor: pointer; transition: all 0.15s ease; text-align: left; gap: 2px; }
      `}</style>

      {/* Mobile overlay */}
      <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />

      <aside className="sidebar-wrapper" data-testid="sidebar" style={{
        width: 260, minWidth: 260, background: bg, borderRight: `1px solid ${border}`,
        display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', flexShrink: 0,
      }}>

        {/* ── Header: Logo + School Identity + New Chat ── */}
        <div style={{ padding: '12px 12px 10px', flexShrink: 0 }}>

          {/* Brand row */}
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <img
              src="/eduflow-logo.png"
              alt="EduFlow"
              style={{
                height: 52, width: 'auto', maxWidth: '100%', objectFit: 'contain',
                // The wordmark's "Edu" is a deep navy blue, which all but
                // disappeared against the dark sidebar. A brightness lift alone
                // was not enough; the saturation boost is what brings the blue
                // back, and the halo separates it from the panel behind.
                filter: isDark
                  ? 'brightness(1.45) saturate(1.25) drop-shadow(0 2px 10px rgba(232,89,12,0.5))'
                  : 'drop-shadow(0 2px 6px rgba(232,89,12,0.28))',
              }}
            />
            <button onClick={() => setSidebarOpen(false)} className="mobile-close"
              style={{ position: 'absolute', right: 0, background: 'var(--color-surface-raised)', border: 'none', cursor: 'pointer', color: muted, padding: '5px', borderRadius: 7, display: 'none', alignItems: 'center', justifyContent: 'center', transition: 'var(--transition-fast)' }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
              onMouseLeave={e => e.currentTarget.style.background = 'var(--color-surface-raised)'}>
              <X size={15} />
            </button>
          </div>

          {/* School identity card */}
          <div style={{
            background: 'var(--bg-active)',
            border: `1px solid ${'var(--color-accent-blue)'}`,
            borderRadius: 10, padding: '7px 10px', marginBottom: 10,
          }}>
            <div style={{
              fontSize: 12, fontWeight: 700, color: tp,
              letterSpacing: '-0.01em', lineHeight: 1.2,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }} title={schoolName || 'School Management'}>
              {schoolName || 'School Management'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 4 }}>
              <span style={{
                fontSize: 9, fontWeight: 700, color: '#fff',
                background: 'linear-gradient(135deg, #e8590c, #c94b07)',
                padding: '1.5px 6px', borderRadius: 4, letterSpacing: '0.05em', flexShrink: 0,
              }}>CBSE</span>
              {(schoolMeta.city || schoolMeta.state) && (
                <span style={{ fontSize: 9.5, color: muted, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {[schoolMeta.city, schoolMeta.state].filter(Boolean).join(', ')}
                </span>
              )}
            </div>
          </div>

          {/* New Chat CTA */}
          <button data-testid="new-chat-btn" onClick={onNewChat} className="new-chat-btn">
            <div style={{ width: 18, height: 18, borderRadius: 5, background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Plus size={11} strokeWidth={2.5} color="#fff" />
            </div>
            New Chat
          </button>
        </div>

        {/* ── Body ──
            NOT scrollable itself. The outer scrollbar is deliberately gone:
            with it, reaching the chat history meant scrolling the whole tool
            list past first, and you could end up with two scrollbars nested
            inside one another. This is a flex column instead, and each zone
            scrolls within its own share of the height — so both section
            headers stay put and visible at all times.
            `minHeight: 0` is what actually allows a flex child to shrink
            below its content and scroll; without it the zones would grow and
            push each other off the bottom. */}
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 8, overflow: 'hidden', padding: '0 8px 8px' }}>

          {/* Tools zone — cool blue tint */}
          <div style={{
            borderRadius: 12, background: toolsZoneBg, border: `1px solid ${toolsZoneBorder}`,
            overflow: 'hidden', display: 'flex', flexDirection: 'column',
            // `0 1 auto` — size to the CONTENT, never grow into spare space.
            // With `1 1 auto` the zone stretched to fill the sidebar even when
            // the tool list was short, leaving an empty gap between the last
            // tool and Recent Chats. It may still SHRINK (and then scroll)
            // when the list is long, which is what the 1 in the middle allows.
            flex: '0 1 auto', minHeight: 0,
          }}>
            {/* Collapsible, matching Recent Chats — same control, same place,
                same chevron, so the two sections behave identically. */}
            <button
              type="button"
              aria-expanded={toolsSectionOpen}
              data-testid="tools-section-toggle"
              onClick={() => setToolsSectionOpen(v => !v)}
              className="zone-header"
              style={{
                color: 'var(--color-accent-blue)',
                width: '100%', background: 'none', border: 'none',
                cursor: 'pointer', font: 'inherit', letterSpacing: '0.07em',
                fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                flexShrink: 0,
              }}
            >
              <Wrench size={11} />
              Tools
              <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
                {toolsSectionOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              </span>
            </button>
            {/* The tools list scrolls INSIDE its own zone. */}
            <div className="sidebar-scroll" style={{ padding: '0 6px 6px', display: toolsSectionOpen ? 'block' : 'none', flex: 1, minHeight: 0, overflowY: 'auto', overflowX: 'hidden' }}>
              {renderGroupedNav()}
            </div>
          </div>

          {/* Chat history zone — warm amber tint.
              Epic 6: this used to be hidden entirely when the list was empty
              (`conversations.length > 0`), which meant someone with no recent
              chats had NO route to the archive at all. A door that disappears
              when the room behind it looks empty is how a page ships and is
              never found. The zone now always renders; only the list inside it
              is conditional. */}
          {(
            <div style={{
              borderRadius: 12, background: chatsZoneBg, border: `1px solid ${chatsZoneBorder}`,
              overflow: 'hidden', display: 'flex', flexDirection: 'column',
              // Chats takes whatever height is left once Tools has taken what
              // it needs, so it begins immediately below the last tool and
              // then scrolls. Collapsed, it shrinks to just its header.
              flex: chatsSectionOpen ? '1 1 auto' : '0 0 auto', minHeight: 0,
            }}>
              <button
                type="button"
                aria-expanded={chatsSectionOpen}
                onClick={() => setChatsSectionOpen(v => !v)}
                className="zone-header"
                style={{
                  color: 'var(--accent-orange)',
                  width: '100%', background: 'none', border: 'none',
                  cursor: 'pointer', font: 'inherit', letterSpacing: '0.07em',
                  fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                  flexShrink: 0,
                }}
              >
                <MessageCircle size={11} />
                Recent Chats
                <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
                  {chatsSectionOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                </span>
              </button>
              {/* Every conversation is listed, and the zone scrolls on its own.
                  This replaces the "N more chats" expander that used to sit at
                  the bottom: the section already has a collapse control in its
                  own header, so a second toggle underneath was doing the same
                  job twice. Scrolling reaches the whole history in one gesture
                  rather than expand-then-scroll. */}
              {/* The way to every chat, not just the newest fifty the server
                  returns here. Outside the scrolling list on purpose: it must
                  not scroll out of reach, and it must be there when the list is
                  empty. */}
              {chatsSectionOpen && (
                <button
                  type="button"
                  data-testid="sidebar-all-chats"
                  onClick={() => { onSelectTool('all-chats'); }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    width: 'calc(100% - 12px)', margin: '0 6px 4px',
                    padding: '6px 8px', minHeight: 30,
                    background: 'transparent', border: 'none',
                    borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                    fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700,
                    color: 'var(--accent-orange)',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <Search size={11} aria-hidden="true" />
                  See all chats
                </button>
              )}
              <div className="sidebar-scroll" style={{ padding: '0 6px 6px', display: chatsSectionOpen ? 'block' : 'none', flex: 1, minHeight: 0, overflowY: 'auto', overflowX: 'hidden' }}>
                {conversations.map(conv => (
                  <div key={conv.id} style={{ position: 'relative' }}>
                    {renamingId === conv.id ? (
                      <div style={{ padding: '3px 4px' }}>
                        <input autoFocus value={renameVal} onChange={e => setRenameVal(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter') commitRename(conv.id); if (e.key === 'Escape') setRenamingId(null); }}
                          onBlur={() => commitRename(conv.id)}
                          style={{ width: '100%', background: 'var(--color-surface-raised)', border: `1px solid #4f8ff7`, borderRadius: 8, padding: '6px 10px', color: tp, fontSize: 12, outline: 'none' }}
                        />
                      </div>
                    ) : (
                      <button data-testid={`conv-btn-${conv.id}`}
                        onClick={() => onSelectConv(conv.id)}
                        onContextMenu={e => { e.preventDefault(); setMenuConvId(conv.id); }}
                        className="conv-btn-row"
                        style={{ background: activeConvId === conv.id ? 'var(--bg-active)' : 'transparent' }}
                        onMouseEnter={e => { if (activeConvId !== conv.id) e.currentTarget.style.background = 'var(--bg-hover)'; }}
                        onMouseLeave={e => { if (activeConvId !== conv.id) e.currentTarget.style.background = 'transparent'; }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
                          <div style={{ width: 22, height: 22, borderRadius: 6, flexShrink: 0, background: activeConvId === conv.id ? 'rgba(79,143,247,0.15)' : 'var(--bg-hover)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <MessageCircle size={11} color={activeConvId === conv.id ? '#4f8ff7' : muted} />
                          </div>
                          {conv.is_pinned && <Pin size={9} color="#fbbf24" />}
                          {conv.is_starred && <Star size={9} color="#fbbf24" />}
                          <span style={{ fontSize: 12, fontWeight: activeConvId === conv.id ? 600 : 500, color: activeConvId === conv.id ? tp : secondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                            {conv.title || 'New conversation'}
                          </span>
                        </div>
                        <span style={{ fontSize: 10, color: muted, paddingLeft: 28 }}>{timeAgo(conv.updated_at)}</span>
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
              </div>
            </div>
          )}
        </div>



        {/* ── Token usage badge ── */}
        <TokenUsageBadge
          usage={tokenUsage}
          role={currentUser.role}
          isDark={isDark}
          border={border}
          onClick={() => setShowUpgradeModal(true)}
        />

        {/* ── User section ── */}
        <div style={{ borderTop: `1px solid ${border}`, padding: '8px', flexShrink: 0 }} ref={userMenuRef}>
          {showUserMenu && (
            <div className="fade-in-scale" style={{
              position: 'absolute', bottom: 68, left: 8, right: 8,
              background: 'var(--color-surface-raised)', border: `1px solid ${border}`,
              borderRadius: 12, padding: 6, boxShadow: 'var(--shadow-lg)', zIndex: 100,
            }}>
              {/* Profile */}
              <button onClick={() => { onOpenProfile(); setShowUserMenu(false); }}
                style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px', background: 'transparent', border: 'none', borderRadius: 8, cursor: 'pointer', color: secondary, fontSize: 13, fontWeight: 500, transition: 'var(--transition-fast)' }}
                onMouseEnter={e => e.currentTarget.style.background = hover}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                <User size={14} />
                <span>Profile</span>
              </button>
              {/* Dark Mode */}
              <button onClick={toggleTheme}
                style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px', background: 'transparent', border: 'none', borderRadius: 8, cursor: 'pointer', color: secondary, fontSize: 13, fontWeight: 500, transition: 'var(--transition-fast)' }}
                onMouseEnter={e => e.currentTarget.style.background = hover}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                {isDark ? <Sun size={14} /> : <Moon size={14} />}
                <span>{isDark ? 'Light Mode' : 'Dark Mode'}</span>
              </button>
              {/* Settings */}
              <button onClick={() => { onOpenSettings(); setShowUserMenu(false); }}
                style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px', background: 'transparent', border: 'none', borderRadius: 8, cursor: 'pointer', color: secondary, fontSize: 13, fontWeight: 500, transition: 'var(--transition-fast)' }}
                onMouseEnter={e => e.currentTarget.style.background = hover}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                <Settings size={14} />
                <span>Settings</span>
              </button>
              {/* Help — expandable, contains bottomTools */}
              <button onClick={() => setShowHelp(v => !v)}
                style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px', background: showHelp ? hover : 'transparent', border: 'none', borderRadius: 8, cursor: 'pointer', color: secondary, fontSize: 13, fontWeight: 500, transition: 'var(--transition-fast)' }}
                onMouseEnter={e => e.currentTarget.style.background = hover}
                onMouseLeave={e => { if (!showHelp) e.currentTarget.style.background = 'transparent'; }}>
                <LifeBuoy size={14} />
                <span style={{ flex: 1, textAlign: 'left' }}>Help & Support</span>
                <ChevronDown size={12} color={muted} style={{ transform: showHelp ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.2s ease' }} />
              </button>
              {showHelp && bottomTools.length > 0 && (
                <div style={{ paddingLeft: 8, paddingBottom: 2 }}>
                  {bottomTools.map(t => {
                    const Icon = t.icon;
                    const isActive = activeTool === t.id;
                    return (
                      <button key={t.id} onClick={() => { onSelectTool(t.id); setShowUserMenu(false); setShowHelp(false); }}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '7px 10px', background: isActive ? `${t.color}12` : 'transparent', border: 'none', borderRadius: 7, cursor: 'pointer', color: isActive ? t.color : secondary, fontSize: 12, fontWeight: isActive ? 600 : 500, transition: 'var(--transition-fast)' }}
                        onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = hover; }}
                        onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}>
                        <Icon size={13} color={isActive ? t.color : muted} />
                        <span>{t.name}</span>
                      </button>
                    );
                  })}
                </div>
              )}
              <div style={{ borderTop: `1px solid ${border}`, margin: '4px 0' }} />
              {/* Sign Out */}
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
              display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '9px 10px',
              background: showUserMenu ? hover : 'transparent',
              border: 'none', borderRadius: 10, cursor: 'pointer', transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={e => e.currentTarget.style.background = hover}
            onMouseLeave={e => { if (!showUserMenu) e.currentTarget.style.background = 'transparent'; }}>
            <div style={{
              width: 32, height: 32, borderRadius: 9, background: `linear-gradient(135deg, ${ROLE_COLORS[currentUser.role]}, ${ROLE_COLORS[currentUser.role]}aa)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, fontWeight: 700, color: '#fff', flexShrink: 0,
              boxShadow: `0 2px 6px ${ROLE_COLORS[currentUser.role]}44`,
            }}>
              {currentUser.initials}
            </div>
            <div style={{ flex: 1, textAlign: 'left', minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: tp, lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{currentUser.name}</div>
              <div style={{ fontSize: 10, color: ROLE_COLORS[currentUser.role], fontWeight: 600, lineHeight: 1.2, marginTop: 2 }}>{ROLE_LABELS[currentUser.role]}</div>
            </div>
            <ChevronDown size={13} color={muted} style={{ transform: showUserMenu ? 'rotate(180deg)' : 'none', transition: 'var(--transition-fast)' }} />
          </button>
        </div>
      </aside>

      {showUpgradeModal && (
        <TokenUpgradeModal
          onClose={() => setShowUpgradeModal(false)}
          currentUsage={tokenUsage?.total_used || 0}
          roleLimit={tokenUsage?.role_limit || 0}
          canPurchase={currentUser.role !== 'student'}
        />
      )}
    </>
  );
}

function TokenUsageBadge({ usage, isDark, border, onClick }) {
  if (!usage) return null;

  const isUnlimited = usage.unlimited === true || usage.role_limit == null;
  const limit = isUnlimited ? 0 : (usage.role_limit || 0);
  const used = usage.total_used || 0;
  const pct = (!isUnlimited && limit > 0) ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const barColor = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981';
  const textColor = 'var(--color-text-secondary)';
  const bg = 'var(--color-surface-muted)';
  const hoverBg = 'var(--bg-hover)';

  function fmt(n) {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
    return `${n}`;
  }

  return (
    <div style={{ padding: '4px 8px', borderTop: `1px solid ${border}` }}>
      <button
        onClick={onClick}
        title={isUnlimited ? `${used.toLocaleString()} tokens used — Unlimited plan` : `${used.toLocaleString()} / ${limit.toLocaleString()} tokens used — Click to manage`}
        style={{
          width: '100%', border: 'none', cursor: 'pointer',
          background: bg, borderRadius: 10, padding: '8px 10px',
          display: 'flex', flexDirection: 'column', gap: 5,
          transition: 'background 0.15s',
        }}
        onMouseEnter={e => e.currentTarget.style.background = hoverBg}
        onMouseLeave={e => e.currentTarget.style.background = bg}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: textColor, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            AI Tokens
          </span>
          {isUnlimited
            ? <span style={{ fontSize: 10, fontWeight: 700, color: '#10b981' }}>∞ Unlimited</span>
            : <span style={{ fontSize: 10, fontWeight: 700, color: barColor }}>{pct}%</span>
          }
        </div>
        {!isUnlimited && (
          <div style={{ height: 4, borderRadius: 3, background: 'var(--color-border)', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${pct}%`, background: barColor, borderRadius: 3, transition: 'width 0.5s ease' }} />
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 10, color: textColor }}>
            {isUnlimited ? `${fmt(used)} used` : `${fmt(used)} / ${fmt(limit)}`}
          </span>
          <span style={{ fontSize: 10, color: '#4f8ff7', fontWeight: 600 }}>
            {!isUnlimited && pct >= 80 ? '⚡ Top up →' : 'Manage →'}
          </span>
        </div>
      </button>
    </div>
  );
}
