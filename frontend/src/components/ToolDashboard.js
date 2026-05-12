import React from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import {
  IndianRupee, Users, BarChart2, Bell, FileText, Megaphone,
  CalendarDays, UserPlus, MessageSquare, BookOpen, ClipboardList,
  PenTool, BarChart, Award, Truck, Package, Printer, FilePlus,
  Target, FileCheck, LifeBuoy, Wrench, Monitor, AlertTriangle,
  ScrollText, Shield,
} from 'lucide-react';

// ─── All tool definitions ──────────────────────────────────────────────────────
const T = {
  'student-database':      { id: 'student-database',      name: 'Student Database',    subtitle: 'Manage & search',       icon: Users,         color: '#4f8ff7' },
  'fee-tracker':           { id: 'fee-tracker',           name: 'Fee Tracker',         subtitle: 'Reminders & dues',      icon: IndianRupee,   color: '#34d399' },
  'attendance-recorder':   { id: 'attendance-recorder',   name: 'Attendance',          subtitle: 'Mark & track',          icon: ClipboardList, color: '#fb923c' },
  'certificate-generator': { id: 'certificate-generator', name: 'Certificates',        subtitle: 'TC, Bonafide, etc.',    icon: Award,         color: '#fbbf24' },
  'circular-sender':       { id: 'circular-sender',       name: 'Circulars',           subtitle: 'Notices & messages',    icon: Megaphone,     color: '#22d3ee' },
  'enquiry-register':      { id: 'enquiry-register',      name: 'Enquiry Register',    subtitle: 'Admission leads',       icon: UserPlus,      color: '#a78bfa' },
  'document-scanner':      { id: 'document-scanner',      name: 'Doc Scanner',         subtitle: 'Extract & file',        icon: FileCheck,     color: '#737373' },
  'smart-fee-defaulter':   { id: 'smart-fee-defaulter',   name: 'Fee Defaulters',      subtitle: 'Smart reminders',       icon: Bell,          color: '#f87171' },
  'admission-pipeline':    { id: 'admission-pipeline',    name: 'Admission Pipeline',  subtitle: 'Track conversions',     icon: Target,        color: '#4f8ff7' },
  'parent-message':        { id: 'parent-message',        name: 'Parent Messages',     subtitle: 'Compose & send',        icon: MessageSquare, color: '#34d399' },
  'student-transfer':      { id: 'student-transfer',      name: 'Student Transfer',    subtitle: 'Withdrawal & TC',       icon: UserPlus,      color: '#fb923c' },
  'id-card-generator':     { id: 'id-card-generator',     name: 'ID Cards',            subtitle: 'Generate & print',      icon: Printer,       color: '#a78bfa' },
  'timetable-builder':     { id: 'timetable-builder',     name: 'Timetable',           subtitle: 'Build & manage',        icon: CalendarDays,  color: '#f472b6' },
  'asset-tracker':         { id: 'asset-tracker',         name: 'Asset Tracker',       subtitle: 'Inventory & items',     icon: Package,       color: '#22d3ee' },
  'transport-manager':     { id: 'transport-manager',     name: 'Transport',           subtitle: 'Routes & buses',        icon: Truck,         color: '#fb923c' },
  'automated-report':      { id: 'automated-report',      name: 'Auto Reports',        subtitle: 'Scheduled reports',     icon: FileText,      color: '#737373' },
  'custom-form-builder':   { id: 'custom-form-builder',   name: 'Form Builder',        subtitle: 'Dynamic forms',         icon: FilePlus,      color: '#737373' },
  'attendance-alerts':     { id: 'attendance-alerts',     name: 'Attendance Alerts',   subtitle: 'SMS below threshold',   icon: MessageSquare, color: '#a78bfa' },
  'query-section':         { id: 'query-section',         name: 'Query & Support',     subtitle: 'Tickets & issues',      icon: LifeBuoy,      color: '#22d3ee' },
  // Phase 3 — new tool panels
  'facility-requests':     { id: 'facility-requests',     name: 'Facility Requests',   subtitle: 'Maintenance queue',     icon: Wrench,        color: '#fb923c' },
  'tech-issues':           { id: 'tech-issues',           name: 'Tech Issues',         subtitle: 'IT request tracker',    icon: Monitor,       color: '#818cf8' },
  'incident-tracker':      { id: 'incident-tracker',      name: 'Incidents & Visitors',subtitle: 'Log & track',           icon: AlertTriangle, color: '#f87171' },
  'audit-log':             { id: 'audit-log',             name: 'Audit Log',           subtitle: 'Who did what',          icon: ScrollText,    color: '#737373' },
  'fee-receipts':          { id: 'fee-receipts',          name: 'Fee Receipts',        subtitle: 'PDF & export',          icon: FileText,      color: '#34d399' },

  // Teacher-only tools
  'class-attendance-marker':     { id: 'class-attendance-marker',     name: 'Attendance',           subtitle: 'Mark my class',        icon: ClipboardList, color: '#fb923c' },
  'assignment-generator':        { id: 'assignment-generator',        name: 'Assignments',          subtitle: 'Create & manage',      icon: BookOpen,      color: '#4f8ff7' },
  'question-paper-creator':      { id: 'question-paper-creator',      name: 'Question Papers',      subtitle: 'Create & export',      icon: PenTool,       color: '#34d399' },
  'report-card-builder':         { id: 'report-card-builder',         name: 'Report Cards',         subtitle: 'Enter & generate',     icon: FileText,      color: '#a78bfa' },
  'student-performance-viewer':  { id: 'student-performance-viewer',  name: 'Student Performance',  subtitle: 'Marks & trends',       icon: BarChart2,     color: '#22d3ee' },
  'leave-application':           { id: 'leave-application',           name: 'Leave Application',    subtitle: 'Apply for leave',      icon: CalendarDays,  color: '#fbbf24' },
  'lesson-plan-generator':       { id: 'lesson-plan-generator',       name: 'Lesson Plans',         subtitle: 'Plan chapters',        icon: BookOpen,      color: '#f472b6' },
  'worksheet-creator':           { id: 'worksheet-creator',           name: 'Worksheets',           subtitle: 'Practice sheets',      icon: FilePlus,      color: '#fb923c' },
  'class-performance-analytics': { id: 'class-performance-analytics', name: 'Class Analytics',      subtitle: 'Trends & insights',    icon: BarChart,      color: '#a78bfa' },
  'substitution-viewer':         { id: 'substitution-viewer',         name: 'Substitutions',        subtitle: 'My schedule changes',  icon: CalendarDays,  color: '#737373' },
  'ptm-notes':                   { id: 'ptm-notes',                   name: 'PTM Notes',            subtitle: 'Parent meet notes',    icon: MessageSquare, color: '#34d399' },
  'curriculum-tracker':          { id: 'curriculum-tracker',          name: 'Curriculum',           subtitle: 'Progress tracking',    icon: Target,        color: '#4f8ff7' },
  'form-submissions':            { id: 'form-submissions',            name: 'Forms',                subtitle: 'Surveys & forms',      icon: FileText,      color: '#22d3ee' },
};

// ─── Tool sets per role / admin sub-role ───────────────────────────────────────
const TOOL_SETS = {
  // Admin sub-roles
  admin_principal: [
    'student-database','fee-tracker','attendance-recorder','certificate-generator',
    'circular-sender','enquiry-register','document-scanner','smart-fee-defaulter',
    'admission-pipeline','parent-message','student-transfer','id-card-generator',
    'timetable-builder','asset-tracker','transport-manager','incident-tracker',
    'automated-report','custom-form-builder','attendance-alerts','query-section',
    'audit-log',
  ],
  admin_accountant: [
    'student-database','fee-tracker','smart-fee-defaulter','fee-receipts',
    'custom-form-builder','query-section',
  ],
  admin_transport_head: [
    'student-database','transport-manager','asset-tracker','custom-form-builder','query-section',
  ],
  admin_receptionist: [
    'student-database','enquiry-register','admission-pipeline','parent-message',
    'student-transfer','id-card-generator','asset-tracker','incident-tracker',
    'custom-form-builder','query-section',
  ],
  admin_it_tech: [
    'tech-issues','query-section','custom-form-builder',
  ],
  admin_maintenance: [
    'facility-requests','query-section',
  ],

  // Teacher (unchanged)
  teacher: [
    'class-attendance-marker','assignment-generator','question-paper-creator',
    'report-card-builder','student-performance-viewer','leave-application',
    'lesson-plan-generator','worksheet-creator','class-performance-analytics',
    'substitution-viewer','ptm-notes','curriculum-tracker','form-submissions','query-section',
  ],
};

// Sub-role display labels
const SUB_ROLE_LABELS = {
  principal:      'Principal',
  accountant:     'Accounts',
  transport_head: 'Transport Head',
  receptionist:   'Receptionist',
  it_tech:        'IT & Tech',
  maintenance:    'Maintenance',
  hod:            'HOD',
  coordinator:    'Coordinator',
  class_teacher:  'Class Teacher',
  subject_teacher:'Subject Teacher',
  kg_incharge:    'KG In-charge',
};

const OWNER_TOOLS = [
  'student-database','fee-tracker','attendance-recorder','certificate-generator',
  'circular-sender','enquiry-register','smart-fee-defaulter','admission-pipeline',
  'parent-message','id-card-generator','timetable-builder','asset-tracker',
  'transport-manager','incident-tracker','facility-requests','tech-issues',
  'fee-receipts','audit-log','automated-report','custom-form-builder',
  'query-section',
];

function getTools(user) {
  if (user.role === 'owner') {
    return OWNER_TOOLS.map(id => T[id]).filter(Boolean);
  }
  if (user.role === 'admin') {
    const key = `admin_${user.sub_category || 'principal'}`;
    return (TOOL_SETS[key] || TOOL_SETS.admin_principal).map(id => T[id]).filter(Boolean);
  }
  return (TOOL_SETS[user.role] || []).map(id => T[id]).filter(Boolean);
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

function ToolCard({ tool, onClick, isDark }) {
  const [hov, setHov] = React.useState(false);
  const Icon = tool.icon;
  return (
    <button
      onClick={() => onClick(tool.id)}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
        padding: '16px 16px 14px', textAlign: 'left', outline: 'none', cursor: 'pointer',
        background: hov ? (isDark ? '#222' : '#fafafa') : (isDark ? '#1a1a1a' : '#ffffff'),
        border: `1px solid ${hov ? tool.color + '55' : (isDark ? '#2e2e2e' : '#e5e5e5')}`,
        borderRadius: 14, transition: 'all 0.15s ease',
        boxShadow: hov ? `0 4px 16px ${tool.color}15` : 'none',
      }}
    >
      <div style={{
        width: 36, height: 36, borderRadius: 10, marginBottom: 11,
        background: hov ? `${tool.color}18` : (isDark ? '#252525' : '#f5f5f5'),
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        transition: 'all 0.15s ease',
      }}>
        <Icon size={17} color={hov ? tool.color : (isDark ? '#666' : '#a3a3a3')} />
      </div>
      <span style={{ fontSize: 13, fontWeight: 600, color: isDark ? '#f5f5f5' : '#171717', letterSpacing: '-0.01em', lineHeight: 1.3, marginBottom: 3, display: 'block' }}>
        {tool.name}
      </span>
      <span style={{ fontSize: 11, color: isDark ? '#666' : '#a3a3a3', lineHeight: 1.4, display: 'block' }}>
        {tool.subtitle}
      </span>
    </button>
  );
}

export default function ToolDashboard({ onSelectTool }) {
  const { currentUser } = useUser();
  const { isDark } = useTheme();

  const tools = getTools(currentUser);

  const subLabel = SUB_ROLE_LABELS[currentUser.sub_category] || null;
  const roleLabel = currentUser.role === 'admin'
    ? (subLabel ? `Admin · ${subLabel}` : 'Admin')
    : currentUser.role?.charAt(0).toUpperCase() + currentUser.role?.slice(1);

  const roleColor = { admin: '#4f8ff7', teacher: '#34d399' }[currentUser.role] || '#4f8ff7';
  const bg   = isDark ? '#141414' : '#f5f5f5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#555' : '#a3a3a3';

  return (
    <div style={{ flex: 1, height: '100%', overflowY: 'auto', background: bg, padding: '32px 32px 48px' }}>

      {/* Greeting */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, color: text, margin: '0 0 4px', letterSpacing: '-0.03em' }}>
          {greeting()}, {currentUser.name?.split(' ')[0]}
        </h1>
        <p style={{ fontSize: 13, color: muted, margin: 0 }}>
          {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
        </p>
      </div>

      {/* Role badge */}
      <div style={{ marginBottom: 28 }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 12px',
          borderRadius: 8, background: `${roleColor}12`, color: roleColor,
          fontSize: 12, fontWeight: 600, border: `1px solid ${roleColor}25`,
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: roleColor, display: 'inline-block' }} />
          {roleLabel} · {tools.length} tools
        </span>
      </div>

      {/* Section label */}
      <p style={{ fontSize: 11, fontWeight: 600, color: muted, margin: '0 0 12px', letterSpacing: '0.06em' }}>
        TOOLS
      </p>

      {/* 4-col grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        {tools.map(tool => (
          <ToolCard key={tool.id} tool={tool} onClick={onSelectTool} isDark={isDark} />
        ))}
      </div>
    </div>
  );
}
