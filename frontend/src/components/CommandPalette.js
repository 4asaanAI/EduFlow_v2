import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useUser } from '../contexts/UserContext';
import {
  Activity, AlertTriangle, Award, BarChart2, Bell, BookOpen, CalendarDays,
  ClipboardList, Command, Database, FileCheck, FilePlus, FileText, IndianRupee,
  LifeBuoy, Megaphone, MessageSquare, Monitor, Package, PenTool, Printer, RefreshCw,
  ScrollText, Settings, Shield, Target, Trash2, Truck, Trophy, Users, UserCheck, UserPlus,
  Wrench, X,
} from 'lucide-react';

const ALL_TOOLS = [
  { id: 'school-pulse',           name: 'School Pulse',          subtitle: "Today's overview",         icon: Activity,      roles: ['owner'] },
  { id: 'student-database',       name: 'Student Database',      subtitle: 'Manage & search students', icon: Users,         roles: ['owner','admin'] },
  { id: 'fee-collection',         name: 'Fee Collection',        subtitle: 'Revenue & defaulters',     icon: IndianRupee,   roles: ['owner'] },
  { id: 'fee-tracker',            name: 'Fee Tracker',           subtitle: 'Dues & reminders',         icon: IndianRupee,   roles: ['admin'] },
  { id: 'attendance-recorder',    name: 'Attendance',            subtitle: 'Mark & track daily',       icon: ClipboardList, roles: ['owner','admin'] },
  { id: 'attendance-overview',    name: 'Attendance Overview',   subtitle: 'Trends & patterns',        icon: ClipboardList, roles: ['owner'] },
  { id: 'timetable-builder',      name: 'Timetable',             subtitle: 'Build & manage schedules', icon: CalendarDays,  roles: ['owner','admin'] },
  { id: 'staff-tracker',          name: 'Staff Tracker',         subtitle: 'Profiles & roles',         icon: UserCheck,     roles: ['owner','admin'] },
  { id: 'staff-attendance-tracker', name: 'Staff Attendance',    subtitle: 'Attendance & leaves',      icon: UserCheck,     roles: ['owner'] },
  { id: 'announcement-broadcaster', name: 'Announcements',       subtitle: 'Broadcast messages',       icon: Megaphone,     roles: ['owner'] },
  { id: 'smart-fee-defaulter',    name: 'Fee Defaulters',        subtitle: 'Smart reminders via SMS',  icon: Bell,          roles: ['owner','admin'] },
  { id: 'admission-pipeline',     name: 'Admission Pipeline',    subtitle: 'Track conversions',        icon: Target,        roles: ['owner','admin'] },
  { id: 'enquiry-register',       name: 'Enquiry Register',      subtitle: 'Admission leads',          icon: UserPlus,      roles: ['owner','admin'] },
  { id: 'incident-tracker',       name: 'Incidents & Visitors',  subtitle: 'Log & track incidents',    icon: AlertTriangle, roles: ['owner','admin'] },
  { id: 'transport-manager',      name: 'Transport',             subtitle: 'Routes & buses',           icon: Truck,         roles: ['owner','admin'] },
  { id: 'facility-requests',      name: 'Facility Requests',     subtitle: 'Maintenance queue',        icon: Wrench,        roles: ['owner','admin'] },
  { id: 'tech-issues',            name: 'Tech Issues',           subtitle: 'IT request tracker',       icon: Monitor,       roles: ['admin'] },
  { id: 'audit-log',              name: 'Audit Log',             subtitle: 'Who did what',             icon: ScrollText,    roles: ['owner','admin'] },
  { id: 'academic-structure',     name: 'Academic Structure',    subtitle: 'Classes, subjects & teachers', icon: BookOpen,  roles: ['admin'] },
  { id: 'school-settings',        name: 'School Settings',       subtitle: 'Identity & profile',       icon: Settings,      roles: ['owner'] },
  { id: 'school-activities',      name: 'School Activities',     subtitle: 'Houses, sports, awards',   icon: Trophy,        roles: ['owner','admin'] },
  { id: 'fee-receipts',           name: 'Fee Receipts',          subtitle: 'PDF & export',             icon: FileText,      roles: ['owner','admin'] },
  { id: 'certificate-generator',  name: 'Certificates',          subtitle: 'TC, Bonafide, etc.',       icon: Award,         roles: ['owner','admin'] },
  { id: 'principal-daily',        name: 'Principal Daily',       subtitle: 'Absences & subs',          icon: CalendarDays,  roles: ['admin'] },
  { id: 'asset-tracker',          name: 'Asset Tracker',         subtitle: 'Inventory & items',        icon: Package,       roles: ['owner','admin'] },
  { id: 'document-scanner',       name: 'Doc Scanner',           subtitle: 'Extract & file',           icon: FileCheck,     roles: ['admin'] },
  { id: 'custom-form-builder',    name: 'Form Builder',          subtitle: 'Dynamic forms',            icon: FilePlus,      roles: ['owner','admin'] },
  { id: 'query-section',          name: 'Query & Support',       subtitle: 'Tickets & issues',         icon: LifeBuoy,      roles: ['owner','admin','teacher'] },
  { id: 'data-import',            name: 'Data Import',           subtitle: 'Validate & seed',          icon: Database,      roles: ['owner'] },
  { id: 'fee-sync',               name: 'Fee Sync',              subtitle: 'External API conflicts',   icon: RefreshCw,     roles: ['owner'] },
  { id: 'parent-message',         name: 'Parent Messages',       subtitle: 'Compose & send',           icon: MessageSquare, roles: ['owner','admin'] },
  { id: 'circular-sender',        name: 'Circulars',             subtitle: 'Notices & messages',       icon: Megaphone,     roles: ['admin'] },
  { id: 'id-card-generator',      name: 'ID Cards',              subtitle: 'Generate & print',         icon: Printer,       roles: ['admin'] },
  { id: 'financial-reports',      name: 'Financial Reports',     subtitle: 'Revenue & expenses',       icon: FileText,      roles: ['owner'] },
  { id: 'staff-leave-manager',    name: 'Leave Manager',         subtitle: 'Approve & reject',         icon: CalendarDays,  roles: ['owner','admin'] },
  { id: 'staff-performance',      name: 'Staff Performance',     subtitle: 'Overview & analytics',     icon: BarChart2,     roles: ['owner','admin'] },
  { id: 'smart-alerts',           name: 'Smart Alerts',          subtitle: 'Exceptions & flags',       icon: Bell,          roles: ['owner','admin'] },

  // Teacher tools
  { id: 'class-attendance-marker',     name: 'Attendance',           subtitle: 'Mark my class',            icon: ClipboardList, roles: ['teacher'] },
  { id: 'assignment-generator',        name: 'Assignments',          subtitle: 'Create & manage',          icon: BookOpen,      roles: ['teacher'] },
  { id: 'question-paper-creator',      name: 'Question Papers',      subtitle: 'Create & export',          icon: PenTool,       roles: ['teacher'] },
  { id: 'report-card-builder',         name: 'Report Cards',         subtitle: 'Enter & generate',         icon: FileText,      roles: ['teacher'] },
  { id: 'student-performance-viewer',  name: 'Student Performance',  subtitle: 'Marks & trends',           icon: BarChart2,     roles: ['teacher'] },
  { id: 'leave-application',           name: 'Leave Application',    subtitle: 'Apply for leave',          icon: CalendarDays,  roles: ['teacher'] },
  { id: 'lesson-plan-generator',       name: 'Lesson Plans',         subtitle: 'Plan chapters',            icon: BookOpen,      roles: ['teacher'] },
  { id: 'worksheet-creator',           name: 'Worksheets',           subtitle: 'Practice sheets',          icon: FilePlus,      roles: ['teacher'] },
  { id: 'class-performance-analytics', name: 'Class Analytics',      subtitle: 'Trends & insights',        icon: BarChart2,     roles: ['teacher'] },
  { id: 'substitution-viewer',         name: 'Substitutions',        subtitle: 'My schedule changes',      icon: CalendarDays,  roles: ['teacher'] },
  { id: 'ptm-notes',                   name: 'PTM Notes',            subtitle: 'Parent meet notes',        icon: MessageSquare, roles: ['teacher'] },
  { id: 'curriculum-tracker',          name: 'Curriculum',           subtitle: 'Progress tracking',        icon: Target,        roles: ['teacher'] },
  { id: 'raise-maintenance',           name: 'Report an Issue',      subtitle: 'Raise maintenance request', icon: Wrench,       roles: ['teacher','student'] },
  { id: 'form-submissions',            name: 'Forms',                subtitle: 'Surveys & forms',          icon: FileText,      roles: ['teacher','student'] },

  // Student tools
  { id: 'ai-tutor',            name: 'AI Tutor',          subtitle: 'Study help & tutoring',     icon: MessageSquare,  roles: ['student'] },
  { id: 'doubt-solver',        name: 'Doubt Solver',      subtitle: 'Ask any doubt',             icon: MessageSquare,  roles: ['student'] },
  { id: 'homework-viewer',     name: 'Homework',          subtitle: 'My assignments',            icon: BookOpen,       roles: ['student'] },
  { id: 'attendance-self-check', name: 'My Attendance',  subtitle: 'View attendance records',   icon: ClipboardList,  roles: ['student'] },
  { id: 'result-viewer',       name: 'My Results',        subtitle: 'Exam marks & grades',       icon: BarChart2,      roles: ['student'] },
  { id: 'practice-test',       name: 'Practice Tests',    subtitle: 'Self-assessment quizzes',   icon: PenTool,        roles: ['student'] },
  { id: 'study-planner',       name: 'Study Planner',     subtitle: 'Plan your week',            icon: Target,         roles: ['student'] },
  { id: 'career-guidance',     name: 'Career Guidance',   subtitle: 'Future planning',           icon: Target,         roles: ['student'] },
  { id: 'fee-status-viewer',   name: 'My Fees',           subtitle: 'Payment status',            icon: IndianRupee,    roles: ['student'] },
  { id: 'ptm-summary-viewer',  name: 'PTM Summary',       subtitle: 'Teacher notes',             icon: MessageSquare,  roles: ['student'] },
];

function scoreMatch(tool, query) {
  const q = query.toLowerCase();
  const name = tool.name.toLowerCase();
  const sub = tool.subtitle.toLowerCase();
  if (name === q) return 100;
  if (name.startsWith(q)) return 80;
  if (name.includes(q)) return 60;
  if (sub.includes(q)) return 40;
  return 0;
}

export default function CommandPalette({ onSelectTool, onClose }) {
  const { currentUser } = useUser();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const inputRef = useRef();
  const listRef = useRef();

  const filtered = ALL_TOOLS
    .filter(t => t.roles.includes(currentUser.role))
    .map(t => ({ ...t, score: query ? scoreMatch(t, query) : 50 }))
    .filter(t => !query || t.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 8);

  useEffect(() => { setSelected(0); }, [query]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const pick = useCallback((toolId) => {
    onSelectTool(toolId);
    onClose();
  }, [onSelectTool, onClose]);

  const handleKey = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelected(s => Math.min(s + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelected(s => Math.max(s - 1, 0));
    } else if (e.key === 'Enter') {
      if (filtered[selected]) pick(filtered[selected].id);
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  const isDark = document.documentElement.getAttribute('data-theme') !== 'light';

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9000,
        background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
        paddingTop: '12vh',
      }}
      onClick={onClose}
    >
      <div
        className="cmd-palette"
        onClick={e => e.stopPropagation()}
        style={{
          width: 540, maxWidth: '95vw',
          background: 'var(--color-surface)',
          border: `1px solid ${'var(--color-border-strong)'}`,
          borderRadius: 14,
          boxShadow: '0 24px 80px rgba(0,0,0,0.5)',
          overflow: 'hidden',
        }}
      >
        {/* Search bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px', borderBottom: `1px solid ${'var(--color-border)'}` }}>
          <Command size={16} color={'var(--color-text-muted)'} />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Search tools…"
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              fontSize: 15, color: 'var(--color-text-primary)', fontFamily: 'Inter, sans-serif',
            }}
          />
          {query && (
            <button onClick={() => setQuery('')} style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', display: 'flex' }}>
              <X size={14} />
            </button>
          )}
          <kbd style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: isDark ? '#2e2e2e' : '#f5f5f5', color: 'var(--color-text-muted)', border: `1px solid ${isDark ? '#444' : '#e5e5e5'}`, fontFamily: 'inherit' }}>esc</kbd>
        </div>

        {/* Results */}
        <div ref={listRef} style={{ maxHeight: 360, overflowY: 'auto' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13 }}>
              No tools found for "{query}"
            </div>
          ) : (
            filtered.map((tool, i) => {
              const Icon = tool.icon;
              const isActive = i === selected;
              return (
                <button
                  key={tool.id}
                  onClick={() => pick(tool.id)}
                  onMouseEnter={() => setSelected(i)}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', gap: 12,
                    padding: '10px 16px', border: 'none', cursor: 'pointer',
                    background: isActive ? (isDark ? '#2a2a2a' : '#f5f5f5') : 'transparent',
                    textAlign: 'left',
                  }}
                >
                  <div style={{
                    width: 34, height: 34, borderRadius: 8, flexShrink: 0,
                    background: 'var(--color-surface-raised)',
                    border: `1px solid ${'var(--color-border-strong)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Icon size={15} color={isDark ? '#a0a0a0' : '#737373'} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>{tool.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 1 }}>{tool.subtitle}</div>
                  </div>
                  {isActive && <div style={{ fontSize: 10, color: isDark ? '#555' : '#ccc' }}>↵</div>}
                </button>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '8px 16px', borderTop: `1px solid ${'var(--color-border)'}`, display: 'flex', gap: 12, alignItems: 'center' }}>
          {[['↑↓', 'navigate'], ['↵', 'open'], ['esc', 'close']].map(([key, label]) => (
            <span key={key} style={{ fontSize: 10, color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <kbd style={{ padding: '1px 5px', borderRadius: 3, background: isDark ? '#2e2e2e' : '#f5f5f5', border: `1px solid ${isDark ? '#444' : '#e5e5e5'}`, fontFamily: 'inherit', fontSize: 10 }}>{key}</kbd>
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
