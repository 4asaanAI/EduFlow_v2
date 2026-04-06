import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, AtSign, Slash } from 'lucide-react';
import { useUser } from '../contexts/UserContext';

const TOOLS_BY_ROLE = {
  owner: [
    { id: 'school-pulse', label: 'school-pulse', desc: "Today's school overview" },
    { id: 'fee-collection', label: 'fee-collection', desc: 'Fee summary & defaulters' },
    { id: 'student-strength', label: 'student-strength', desc: 'Class-wise enrollment' },
    { id: 'attendance-overview', label: 'attendance-overview', desc: 'Attendance trends' },
    { id: 'staff-attendance-tracker', label: 'staff-tracker', desc: 'Staff attendance & leaves' },
    { id: 'financial-reports', label: 'financial-reports', desc: 'Revenue & expenses' },
    { id: 'smart-alerts', label: 'smart-alerts', desc: 'Active alerts & flags' },
    { id: 'ai-health-report', label: 'ai-health-report', desc: 'Weekly school health summary' },
    { id: 'staff-leave-manager', label: 'leave-manager', desc: 'Approve / reject leaves' },
    { id: 'admission-funnel', label: 'admission-funnel', desc: 'Enquiries & conversions' },
    { id: 'expense-tracker', label: 'expense-tracker', desc: 'Track school expenses' },
    { id: 'complaint-tracker', label: 'complaint-tracker', desc: 'Grievance management' },
  ],
  admin: [
    { id: 'student-database', label: 'student-database', desc: 'Search & manage students' },
    { id: 'fee-tracker', label: 'fee-tracker', desc: 'Fee payments & dues' },
    { id: 'attendance-recorder', label: 'attendance', desc: 'Mark & track attendance' },
    { id: 'certificate-generator', label: 'certificates', desc: 'TC, Bonafide, Character' },
    { id: 'enquiry-register', label: 'enquiry-register', desc: 'Admission leads' },
    { id: 'smart-fee-defaulter', label: 'fee-defaulters', desc: 'Smart reminders' },
    { id: 'timetable-builder', label: 'timetable', desc: 'Build & manage timetable' },
    { id: 'asset-tracker', label: 'assets', desc: 'Inventory & items' },
    { id: 'visitor-log', label: 'visitor-log', desc: 'Entry & exit' },
    { id: 'transport-manager', label: 'transport', desc: 'Routes & buses' },
  ],
  teacher: [
    { id: 'class-attendance-marker', label: 'attendance', desc: 'Mark my class attendance' },
    { id: 'assignment-generator', label: 'assignments', desc: 'Create & manage assignments' },
    { id: 'report-card-builder', label: 'report-cards', desc: 'Enter marks & generate cards' },
    { id: 'student-performance-viewer', label: 'student-performance', desc: 'View marks & trends' },
    { id: 'leave-application', label: 'leave-application', desc: 'Apply for leave' },
    { id: 'lesson-plan-generator', label: 'lesson-plans', desc: 'Plan chapters' },
    { id: 'ptm-notes', label: 'ptm-notes', desc: 'Parent meet notes' },
    { id: 'curriculum-tracker', label: 'curriculum', desc: 'Track syllabus coverage' },
  ],
  student: [
    { id: 'ai-tutor', label: 'ai-tutor', desc: 'Get study help' },
    { id: 'doubt-solver', label: 'doubt-solver', desc: 'Ask any doubt' },
    { id: 'homework-viewer', label: 'homework', desc: 'My assignments' },
    { id: 'attendance-self-check', label: 'my-attendance', desc: 'View attendance record' },
    { id: 'result-viewer', label: 'my-results', desc: 'View exam marks' },
    { id: 'fee-status-viewer', label: 'my-fees', desc: 'Payment status' },
  ],
};

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function getHeaders(user) {
  return { 'X-User-Role': user?.role || 'owner', 'X-User-Id': user?.id || 'user-owner-001', 'X-User-Name': user?.name || 'Aman' };
}

export default function InputBar({ onSend, disabled, isDark = true }) {
  const { currentUser } = useUser();
  const [text, setText] = useState('');
  const [showSlash, setShowSlash] = useState(false);
  const [showAt, setShowAt] = useState(false);
  const [slashQuery, setSlashQuery] = useState('');
  const [atQuery, setAtQuery] = useState('');
  const [slashFiltered, setSlashFiltered] = useState([]);
  const [atResults, setAtResults] = useState([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [highlights, setHighlights] = useState([]); // [{text, type}]
  const textareaRef = useRef(null);
  const slashPosRef = useRef(-1);
  const atPosRef = useRef(-1);

  const allTools = TOOLS_BY_ROLE[currentUser.role] || [];

  // Detect / and @ anywhere in the text
  const handleChange = (e) => {
    const val = e.target.value;
    setText(val);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';

    const cursor = e.target.selectionStart;
    // Find the last / before cursor without space
    const beforeCursor = val.slice(0, cursor);
    const slashMatch = beforeCursor.match(/\/([a-zA-Z0-9-]*)$/);
    const atMatch = beforeCursor.match(/@([a-zA-Z0-9 ]*)$/);

    if (slashMatch) {
      const query = slashMatch[1].toLowerCase();
      const pos = cursor - slashMatch[0].length;
      slashPosRef.current = pos;
      setSlashQuery(query);
      const filtered = allTools.filter(t => t.label.includes(query) || t.desc.toLowerCase().includes(query));
      setSlashFiltered(filtered);
      setShowSlash(true);
      setShowAt(false);
      setSelectedIdx(0);
    } else if (atMatch) {
      const query = atMatch[1];
      const pos = cursor - atMatch[0].length;
      atPosRef.current = pos;
      setAtQuery(query);
      setShowSlash(false);
      setShowAt(true);
      setSelectedIdx(0);
      // Fetch persons from DB
      if (query.length >= 1) {
        fetch(`${API}/search?q=${encodeURIComponent(query)}&type=persons`, { headers: getHeaders(currentUser) })
          .then(r => r.json())
          .then(r => { if (r.success) setAtResults(r.data || []); })
          .catch(() => setAtResults([]));
      }
    } else {
      setShowSlash(false);
      setShowAt(false);
    }
  };

  const insertSlashTool = (tool) => {
    const cursor = textareaRef.current?.selectionStart || text.length;
    const beforeSlash = text.slice(0, slashPosRef.current);
    const afterCursor = text.slice(cursor);
    const insertion = `/${tool.label} `;
    const newText = beforeSlash + insertion + afterCursor;
    setText(newText);
    setShowSlash(false);
    textareaRef.current?.focus();
    // Position cursor after insertion
    setTimeout(() => {
      const newPos = beforeSlash.length + insertion.length;
      textareaRef.current?.setSelectionRange(newPos, newPos);
    }, 0);
  };

  const insertAtMention = (person) => {
    const cursor = textareaRef.current?.selectionStart || text.length;
    const beforeAt = text.slice(0, atPosRef.current);
    const afterCursor = text.slice(cursor);
    const insertion = `@${person.name} `;
    setText(beforeAt + insertion + afterCursor);
    setShowAt(false);
    textareaRef.current?.focus();
    setTimeout(() => {
      const newPos = beforeAt.length + insertion.length;
      textareaRef.current?.setSelectionRange(newPos, newPos);
    }, 0);
  };

  const handleKeyDown = (e) => {
    const list = showSlash ? slashFiltered : showAt ? atResults : [];
    if (showSlash || showAt) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIdx(i => Math.min(i + 1, list.length - 1)); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIdx(i => Math.max(i - 1, 0)); return; }
      if (e.key === 'Enter' && !e.shiftKey && list[selectedIdx]) {
        e.preventDefault();
        if (showSlash) insertSlashTool(list[selectedIdx]);
        else insertAtMention(list[selectedIdx]);
        return;
      }
      if (e.key === 'Escape') { setShowSlash(false); setShowAt(false); return; }
    }
    if (e.key === 'Enter' && !e.shiftKey && !showSlash && !showAt) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
    setShowSlash(false);
    setShowAt(false);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  // Render text with highlights
  const renderHighlighted = () => {
    const parts = [];
    let i = 0;
    const regex = /(\/[a-zA-Z0-9-]+|@[a-zA-Z0-9 ]+)/g;
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > i) parts.push(<span key={i}>{text.slice(i, match.index)}</span>);
      const isSlash = match[0].startsWith('/');
      parts.push(
        <span key={match.index} style={{ background: isSlash ? 'rgba(99,102,241,0.25)' : 'rgba(16,185,129,0.25)', color: isSlash ? '#818CF8' : '#6EE7B7', borderRadius: 3, padding: '0 2px' }}>
          {match[0]}
        </span>
      );
      i = match.index + match[0].length;
    }
    if (i < text.length) parts.push(<span key={i}>{text.slice(i)}</span>);
    return parts;
  };

  const inputBg = isDark ? '#1C1C28' : '#FFFFFF';
  const inputBorder = isDark ? '#222230' : '#E2E8F0';
  const inputColor = isDark ? '#E2E8F0' : '#0F172A';
  const inputPlaceholder = isDark ? '#475569' : '#94A3B8';
  const dropdownBg = isDark ? '#1C1C28' : '#FFFFFF';
  const dropdownBorder = isDark ? '#222230' : '#E2E8F0';
  const gradBg = isDark ? '#0A0A0F' : '#F8F9FC';
  const footerColor = isDark ? '#374151' : '#94A3B8';

  const showList = showSlash ? slashFiltered : showAt ? atResults : [];

  return (
    <div data-testid="input-bar" style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: `linear-gradient(to top, ${gradBg} 70%, transparent)`, padding: '28px 24px 20px', zIndex: 40 }}>
      <div style={{ maxWidth: 820, margin: '0 auto', position: 'relative' }}>
        {showList.length > 0 && (
          <div style={{ position: 'absolute', bottom: '100%', left: 0, right: 0, background: dropdownBg, border: `1px solid ${dropdownBorder}`, borderRadius: 10, marginBottom: 6, maxHeight: 280, overflowY: 'auto', boxShadow: '0 -8px 32px rgba(0,0,0,0.3)' }}>
            {showSlash && <div style={{ padding: '6px 14px 4px', fontSize: 9, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.08em', borderBottom: `1px solid ${dropdownBorder}` }}>Tools for {currentUser.role}</div>}
            {showAt && <div style={{ padding: '6px 14px 4px', fontSize: 9, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.08em', borderBottom: `1px solid ${dropdownBorder}` }}>Mention a person</div>}
            {showList.map((item, i) => (
              <button key={item.id || item.name || i} data-testid={`suggestion-${item.id || i}`}
                onMouseDown={e => { e.preventDefault(); if (showSlash) insertSlashTool(item); else insertAtMention(item); }}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', background: i === selectedIdx ? (isDark ? 'rgba(99,102,241,0.15)' : 'rgba(99,102,241,0.08)') : 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left' }}
                onMouseEnter={() => setSelectedIdx(i)}>
                {showSlash ? (
                  <>
                    <code style={{ fontSize: 12, color: '#818CF8', fontFamily: 'JetBrains Mono, monospace', minWidth: 120 }}>/{item.label}</code>
                    <span style={{ fontSize: 11, color: '#64748B' }}>{item.desc}</span>
                  </>
                ) : (
                  <>
                    <div style={{ width: 22, height: 22, borderRadius: '50%', background: '#3B82F620', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: '#60A5FA' }}>{(item.name || '?')[0]}</div>
                    <span style={{ fontSize: 12, color: inputColor, fontWeight: 500 }}>{item.name}</span>
                    <span style={{ fontSize: 10, color: '#64748B' }}>{item.sub_role || item.role}</span>
                    <span style={{ fontSize: 10, color: '#64748B', marginLeft: 'auto' }}>{item.role}</span>
                  </>
                )}
              </button>
            ))}
          </div>
        )}

        <div style={{ background: inputBg, border: `1px solid ${disabled ? (isDark ? '#1A1A24' : '#F1F5F9') : inputBorder}`, borderRadius: 14, display: 'flex', alignItems: 'flex-end', padding: '10px 12px', gap: 8 }}>
          <textarea ref={textareaRef} data-testid="chat-input" value={text} onChange={handleChange} onKeyDown={handleKeyDown}
            placeholder={disabled ? 'EduFlow AI is thinking...' : 'Describe what you need, type / for tools or @ to mention...'}
            disabled={disabled} rows={1}
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: disabled ? '#475569' : inputColor, fontSize: 13, resize: 'none', lineHeight: 1.5, padding: 0, fontFamily: 'Manrope, sans-serif', maxHeight: 160, overflowY: 'auto' }}
          />
          <button data-testid="send-btn" onClick={handleSend} disabled={disabled || !text.trim()}
            style={{ width: 32, height: 32, borderRadius: 8, background: disabled || !text.trim() ? (isDark ? '#1A1A24' : '#E2E8F0') : '#3B82F6', border: 'none', cursor: disabled || !text.trim() ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'background 0.15s' }}>
            <Send size={13} color={disabled || !text.trim() ? '#64748B' : '#fff'} />
          </button>
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 14, marginTop: 6, color: footerColor, fontSize: 10 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}><Slash size={8} color={footerColor} /> tool search</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}><AtSign size={8} color={footerColor} /> mentions</span>
          <span>EduFlow AI can make mistakes. Please double-check responses</span>
        </div>
      </div>
    </div>
  );
}
