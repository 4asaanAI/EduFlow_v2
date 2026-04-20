import React from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import {
  IndianRupee, Users, BarChart2, Bell, FileText, Megaphone,
  CalendarDays, UserPlus, MessageSquare, BookOpen, ClipboardList,
  PenTool, BarChart, Award, Truck, Package, Printer, FilePlus,
  Target, FileCheck, LifeBuoy,
} from 'lucide-react';

const TOOLS_BY_ROLE = {
  admin: [
    { id: 'student-database',     name: 'Student Database',   subtitle: 'Manage & search',      icon: Users,         color: '#4f8ff7' },
    { id: 'fee-tracker',          name: 'Fee Tracker',        subtitle: 'Reminders & dues',     icon: IndianRupee,   color: '#34d399' },
    { id: 'attendance-recorder',  name: 'Attendance',         subtitle: 'Mark & track',         icon: ClipboardList, color: '#fb923c' },
    { id: 'certificate-generator',name: 'Certificates',       subtitle: 'TC, Bonafide, etc.',   icon: Award,         color: '#fbbf24' },
    { id: 'circular-sender',      name: 'Circulars',          subtitle: 'Notices & messages',   icon: Megaphone,     color: '#22d3ee' },
    { id: 'enquiry-register',     name: 'Enquiry Register',   subtitle: 'Admission leads',      icon: UserPlus,      color: '#a78bfa' },
    { id: 'document-scanner',     name: 'Doc Scanner',        subtitle: 'Extract & file',       icon: FileCheck,     color: '#737373' },
    { id: 'smart-fee-defaulter',  name: 'Fee Defaulters',     subtitle: 'Smart reminders',      icon: Bell,          color: '#f87171' },
    { id: 'admission-pipeline',   name: 'Admission Pipeline', subtitle: 'Track conversions',    icon: Target,        color: '#4f8ff7' },
    { id: 'parent-message',       name: 'Parent Messages',    subtitle: 'Compose & send',       icon: MessageSquare, color: '#34d399' },
    { id: 'student-transfer',     name: 'Student Transfer',   subtitle: 'Withdrawal & TC',      icon: UserPlus,      color: '#fb923c' },
    { id: 'id-card-generator',    name: 'ID Cards',           subtitle: 'Generate & print',     icon: Printer,       color: '#a78bfa' },
    { id: 'timetable-builder',    name: 'Timetable',          subtitle: 'Build & manage',       icon: CalendarDays,  color: '#f472b6' },
    { id: 'asset-tracker',        name: 'Asset Tracker',      subtitle: 'Inventory & items',    icon: Package,       color: '#22d3ee' },
    { id: 'transport-manager',    name: 'Transport',          subtitle: 'Routes & buses',       icon: Truck,         color: '#fb923c' },
    { id: 'automated-report',     name: 'Auto Reports',       subtitle: 'Scheduled reports',    icon: FileText,      color: '#737373' },
    { id: 'custom-form-builder',  name: 'Form Builder',       subtitle: 'Dynamic forms',        icon: FilePlus,      color: '#737373' },
    { id: 'attendance-alerts',    name: 'Attendance Alerts',  subtitle: 'SMS below threshold',  icon: MessageSquare, color: '#a78bfa' },
    { id: 'query-section',        name: 'Query & Support',    subtitle: 'Tickets & issues',     icon: LifeBuoy,      color: '#22d3ee' },
  ],
  teacher: [
    { id: 'class-attendance-marker',    name: 'Attendance',          subtitle: 'Mark my class',       icon: ClipboardList, color: '#fb923c' },
    { id: 'assignment-generator',       name: 'Assignments',         subtitle: 'Create & manage',     icon: BookOpen,      color: '#4f8ff7' },
    { id: 'question-paper-creator',     name: 'Question Papers',     subtitle: 'Create & export',     icon: PenTool,       color: '#34d399' },
    { id: 'report-card-builder',        name: 'Report Cards',        subtitle: 'Enter & generate',    icon: FileText,      color: '#a78bfa' },
    { id: 'student-performance-viewer', name: 'Student Performance', subtitle: 'Marks & trends',      icon: BarChart2,     color: '#22d3ee' },
    { id: 'leave-application',          name: 'Leave Application',   subtitle: 'Apply for leave',     icon: CalendarDays,  color: '#fbbf24' },
    { id: 'lesson-plan-generator',      name: 'Lesson Plans',        subtitle: 'Plan chapters',       icon: BookOpen,      color: '#f472b6' },
    { id: 'worksheet-creator',          name: 'Worksheets',          subtitle: 'Practice sheets',     icon: FilePlus,      color: '#fb923c' },
    { id: 'class-performance-analytics',name: 'Class Analytics',     subtitle: 'Trends & insights',   icon: BarChart,      color: '#a78bfa' },
    { id: 'substitution-viewer',        name: 'Substitutions',       subtitle: 'My schedule changes', icon: CalendarDays,  color: '#737373' },
    { id: 'ptm-notes',                  name: 'PTM Notes',           subtitle: 'Parent meet notes',   icon: MessageSquare, color: '#34d399' },
    { id: 'curriculum-tracker',         name: 'Curriculum',          subtitle: 'Progress tracking',   icon: Target,        color: '#4f8ff7' },
    { id: 'form-submissions',           name: 'Forms',               subtitle: 'Surveys & forms',     icon: FileText,      color: '#22d3ee' },
    { id: 'query-section',              name: 'Query & Support',     subtitle: 'Tickets & issues',    icon: LifeBuoy,      color: '#22d3ee' },
  ],
};

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
  const tools = TOOLS_BY_ROLE[currentUser.role] || [];
  const roleColor = { admin: '#4f8ff7', teacher: '#34d399' }[currentUser.role] || '#4f8ff7';
  const bg = isDark ? '#141414' : '#f5f5f5';
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#555' : '#a3a3a3';

  return (
    <div style={{ flex: 1, overflowY: 'auto', background: bg, padding: '32px 32px 48px' }}>

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
          {currentUser.role?.charAt(0).toUpperCase() + currentUser.role?.slice(1)} Dashboard · {tools.length} tools
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
