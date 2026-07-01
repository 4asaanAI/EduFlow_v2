import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Slash, AtSign, Paperclip, X, Loader } from 'lucide-react';
import { useUser } from '../contexts/UserContext';
import { getAuthHeaders } from '../lib/authSession';
import { uploadChatFile } from '../lib/api';

const TOOLS_BY_ROLE = {
  owner: [
    { id: 'school-pulse', label: 'school-pulse', desc: "Today's school overview" },
    { id: 'daily-brief', label: 'daily-brief', desc: 'Morning summary' },
    { id: 'fee-collection', label: 'fee-collection', desc: 'Fee summary & defaulters' },
    { id: 'fee-defaulters', label: 'fee-defaulters', desc: 'Overdue fee list' },
    { id: 'fee-structures', label: 'fee-structures', desc: 'Class-wise fee breakdown' },
    { id: 'student-database', label: 'student-database', desc: 'Search & filter students' },
    { id: 'student-profile', label: 'student-profile', desc: 'Full student details' },
    { id: 'attendance-overview', label: 'attendance-overview', desc: 'Attendance trends' },
    { id: 'class-attendance', label: 'class-attendance', desc: 'Class-wise attendance' },
    { id: 'staff-tracker', label: 'staff-tracker', desc: 'Staff attendance & leaves' },
    { id: 'staff-list', label: 'staff-list', desc: 'All staff directory' },
    { id: 'leave-requests', label: 'leave-requests', desc: 'Pending leave approvals' },
    { id: 'financial-reports', label: 'financial-reports', desc: 'Revenue & expenses' },
    { id: 'smart-alerts', label: 'smart-alerts', desc: 'Active alerts & flags' },
    { id: 'class-list', label: 'class-list', desc: 'All classes & teachers' },
    { id: 'house-standings', label: 'house-standings', desc: 'House points leaderboard' },
    { id: 'student-council', label: 'student-council', desc: 'Prefects & positions' },
    { id: 'library', label: 'library', desc: 'Books & overdue status' },
    { id: 'transport', label: 'transport', desc: 'Bus routes & status' },
    { id: 'inventory', label: 'inventory', desc: 'School inventory & stock' },
    { id: 'enquiries', label: 'enquiries', desc: 'Admission enquiries' },
    { id: 'branch-comparison', label: 'branch-comparison', desc: 'Cross-branch stats' },
    { id: 'record-fee', label: 'record-fee', desc: 'Record a fee payment' },
    { id: 'mark-attendance', label: 'mark-attendance', desc: 'Mark class attendance' },
    { id: 'award-points', label: 'award-points', desc: 'Award house points' },
  ],
  admin: [
    { id: 'school-pulse', label: 'school-pulse', desc: "Today's overview" },
    { id: 'student-database', label: 'student-database', desc: 'Search & manage students' },
    { id: 'student-profile', label: 'student-profile', desc: 'Full student details' },
    { id: 'fee-collection', label: 'fee-collection', desc: 'Fee payments & dues' },
    { id: 'fee-defaulters', label: 'fee-defaulters', desc: 'Overdue fee list' },
    { id: 'fee-structures', label: 'fee-structures', desc: 'Fee breakdown by class' },
    { id: 'attendance-overview', label: 'attendance-overview', desc: 'Attendance trends' },
    { id: 'class-attendance', label: 'class-attendance', desc: 'Per-class attendance' },
    { id: 'staff-tracker', label: 'staff-tracker', desc: 'Staff attendance & leaves' },
    { id: 'staff-list', label: 'staff-list', desc: 'Staff directory' },
    { id: 'leave-requests', label: 'leave-requests', desc: 'Approve / reject leaves' },
    { id: 'class-list', label: 'class-list', desc: 'Classes & teachers' },
    { id: 'enquiries', label: 'enquiries', desc: 'Admission leads' },
    { id: 'house-standings', label: 'house-standings', desc: 'House points' },
    { id: 'library', label: 'library', desc: 'Library status' },
    { id: 'transport', label: 'transport', desc: 'Routes & buses' },
    { id: 'inventory', label: 'inventory', desc: 'School assets' },
    { id: 'record-fee', label: 'record-fee', desc: 'Record a payment' },
    { id: 'mark-attendance', label: 'mark-attendance', desc: 'Mark attendance' },
  ],
  teacher: [
    { id: 'school-pulse', label: 'school-pulse', desc: "Today's overview" },
    { id: 'my-class-students', label: 'my-students', desc: 'My class roster' },
    { id: 'class-attendance', label: 'class-attendance', desc: 'My class attendance' },
    { id: 'mark-attendance', label: 'mark-attendance', desc: 'Mark today\'s attendance' },
    { id: 'assignments', label: 'assignments', desc: 'Create & manage' },
    { id: 'report-cards', label: 'report-cards', desc: 'Enter marks' },
    { id: 'house-standings', label: 'house-standings', desc: 'House points' },
    { id: 'award-points', label: 'award-points', desc: 'Award house points' },
    { id: 'library', label: 'library', desc: 'Class book status' },
    { id: 'leave-application', label: 'leave-application', desc: 'Apply for leave' },
    { id: 'lesson-plans', label: 'lesson-plans', desc: 'Plan chapters' },
    { id: 'curriculum', label: 'curriculum', desc: 'Syllabus coverage' },
  ],
  student: [
    { id: 'ai-tutor', label: 'ai-tutor', desc: 'Study help & doubt solving' },
    { id: 'my-attendance', label: 'my-attendance', desc: 'View attendance record' },
    { id: 'my-results', label: 'my-results', desc: 'View exam marks' },
    { id: 'my-fees', label: 'my-fees', desc: 'Payment status' },
    { id: 'homework', label: 'homework', desc: 'My assignments' },
    { id: 'house-standings', label: 'house-standings', desc: 'House points' },
    { id: 'library', label: 'library', desc: 'My issued books' },
    { id: 'announcements', label: 'announcements', desc: 'School notices' },
    { id: 'career-guide', label: 'career-guide', desc: 'Explore career options' },
  ],
};

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function getHeaders() {
  return getAuthHeaders(null);
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
  const [attachedFile, setAttachedFile] = useState(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const slashPosRef = useRef(-1);
  const atPosRef = useRef(-1);

  const allTools = TOOLS_BY_ROLE[currentUser.role] || [];

  const handleChange = (e) => {
    const val = e.target.value;
    setText(val);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';

    const cursor = e.target.selectionStart;
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

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError('');
    setUploadingFile(true);
    try {
      const res = await uploadChatFile(file);
      if (res.success) {
        setAttachedFile({ filename: res.filename, extractedText: res.extracted_text, sizeBytes: res.size_bytes, imageData: res.image_data || null });
      } else {
        setUploadError(res.detail || 'Upload failed');
      }
    } catch {
      setUploadError('Upload failed. Please try again.');
    }
    setUploadingFile(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeAttachment = () => {
    setAttachedFile(null);
    setUploadError('');
  };

  const handleSend = () => {
    const trimmed = text.trim();
    if ((!trimmed && !attachedFile) || disabled || uploadingFile) return;
    let finalText = trimmed;
    if (attachedFile) {
      const fileContext = `[File attached: ${attachedFile.filename}]\n\n${attachedFile.extractedText}`;
      finalText = trimmed ? `${trimmed}\n\n---\n${fileContext}` : fileContext;
    }
    onSend(finalText, attachedFile?.imageData || null);
    setText('');
    setAttachedFile(null);
    setUploadError('');
    setShowSlash(false);
    setShowAt(false);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const inputBg = isDark ? '#252525' : '#ffffff';
  const inputBorder = isDark ? '#333' : '#e5e5e5';
  const inputColor = isDark ? '#f5f5f5' : '#171717';
  const dropdownBg = isDark ? '#252525' : '#ffffff';
  const dropdownBorder = isDark ? '#333' : '#e5e5e5';
  const gradBg = isDark ? '#1a1a1a' : '#f5f5f5';
  const footerColor = isDark ? '#666' : '#525252';
  const muted = isDark ? '#888' : '#525252';

  const showList = showSlash ? slashFiltered : showAt ? atResults : [];

  return (
    <div data-testid="input-bar" style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      background: `linear-gradient(to top, ${gradBg} 75%, transparent)`,
      padding: '32px 24px 20px', zIndex: 40,
    }}>
      <div style={{ maxWidth: 760, margin: '0 auto', position: 'relative' }}>
        {showList.length > 0 && (
          <div className="fade-in-scale" style={{
            position: 'absolute', bottom: '100%', left: 0, right: 0,
            background: dropdownBg, border: `1px solid ${dropdownBorder}`,
            borderRadius: 14, marginBottom: 8, maxHeight: 300, overflowY: 'auto',
            boxShadow: 'var(--shadow-lg)',
          }}>
            {showSlash && <div style={{ padding: '8px 16px 6px', fontSize: 11, color: muted, fontWeight: 600, borderBottom: `1px solid ${dropdownBorder}` }}>Tools</div>}
            {showAt && <div style={{ padding: '8px 16px 6px', fontSize: 11, color: muted, fontWeight: 600, borderBottom: `1px solid ${dropdownBorder}` }}>Mention a person</div>}
            {showList.map((item, i) => (
              <button key={item.id || item.name || i} data-testid={`suggestion-${item.id || i}`}
                onMouseDown={e => { e.preventDefault(); if (showSlash) insertSlashTool(item); else insertAtMention(item); }}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px',
                  background: i === selectedIdx ? (isDark ? 'rgba(79,143,247,0.1)' : 'rgba(79,143,247,0.06)') : 'transparent',
                  border: 'none', cursor: 'pointer', textAlign: 'left', transition: 'var(--transition-fast)',
                }}
                onMouseEnter={() => setSelectedIdx(i)}>
                {showSlash ? (
                  <>
                    <code style={{ fontSize: 13, color: '#a78bfa', fontFamily: 'JetBrains Mono, monospace', minWidth: 130, fontWeight: 500 }}>/{item.label}</code>
                    <span style={{ fontSize: 12, color: muted }}>{item.desc}</span>
                  </>
                ) : (
                  <>
                    <div style={{ width: 26, height: 26, borderRadius: 7, background: '#4f8ff715', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: '#4f8ff7' }}>{(item.name || '?')[0]}</div>
                    <span style={{ fontSize: 13, color: inputColor, fontWeight: 500 }}>{item.name}</span>
                    <span style={{ fontSize: 11, color: muted }}>{item.sub_role || item.role}</span>
                    <span style={{ fontSize: 11, color: muted, marginLeft: 'auto' }}>{item.role}</span>
                  </>
                )}
              </button>
            ))}
          </div>
        )}

        {/* File attachment preview */}
        {attachedFile && (
          <div style={{
            background: isDark ? 'rgba(79,143,247,0.08)' : 'rgba(79,143,247,0.05)',
            border: `1px solid ${isDark ? 'rgba(79,143,247,0.25)' : 'rgba(79,143,247,0.2)'}`,
            borderRadius: 10, padding: '8px 12px', marginBottom: 8,
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <Paperclip size={13} color="#4f8ff7" />
            <span style={{ fontSize: 12, color: '#4f8ff7', fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {attachedFile.filename}
            </span>
            <span style={{ fontSize: 11, color: muted, flexShrink: 0 }}>
              {Math.round(attachedFile.sizeBytes / 1024)} KB · {attachedFile.extractedText.length.toLocaleString()} chars extracted
            </span>
            <button onClick={removeAttachment} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, color: muted, display: 'flex' }}>
              <X size={13} />
            </button>
          </div>
        )}

        {uploadError && (
          <div style={{ fontSize: 11, color: '#f87171', marginBottom: 6 }}>{uploadError}</div>
        )}

        <input ref={fileInputRef} type="file" onChange={handleFileSelect} style={{ display: 'none' }} data-testid="file-input"
          accept=".txt,.md,.html,.htm,.csv,.json,.xml,.pdf,.doc,.docx,.xlsx,.xls,.pptx,.png,.jpg,.jpeg,.heic,.webp,.gif,.zip,.py,.js,.ts,.sql,.log"
        />

        <div style={{
          background: inputBg,
          border: `1px solid ${disabled ? (isDark ? '#222' : '#eee') : inputBorder}`,
          borderRadius: 16, display: 'flex', alignItems: 'center',
          padding: '10px 12px', gap: 8,
          boxShadow: isDark ? '0 2px 12px rgba(0,0,0,0.3)' : '0 2px 12px rgba(0,0,0,0.06)',
          transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
        }}>
          {/* Attach file button */}
          <button
            data-testid="attach-file-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || uploadingFile}
            title="Attach a file (.pdf, .docx, .xlsx, .pptx, .txt, .png, .zip and more)"
            style={{
              width: 32, height: 32, borderRadius: 10, flexShrink: 0,
              background: 'transparent', border: 'none',
              cursor: disabled || uploadingFile ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: uploadingFile ? '#4f8ff7' : muted,
              transition: 'color var(--transition-fast)',
            }}
          >
            {uploadingFile ? <Loader size={15} style={{ animation: 'spin 1s linear infinite' }} /> : <Paperclip size={15} />}
          </button>

          <textarea ref={textareaRef} data-testid="chat-input" value={text} onChange={handleChange} onKeyDown={handleKeyDown}
            placeholder={disabled ? 'EduFlow is thinking...' : 'Message EduFlow...'}
            disabled={disabled} rows={1}
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: disabled ? muted : inputColor, fontSize: 14, resize: 'none',
              lineHeight: 1.5, padding: 0, fontFamily: 'Inter, -apple-system, sans-serif',
              maxHeight: 160, overflowY: 'auto',
            }}
          />
          <button data-testid="chat-send" onClick={handleSend}
            disabled={disabled || uploadingFile || (!text.trim() && !attachedFile)}
            style={{
              width: 32, height: 32, borderRadius: 10,
              background: (disabled || uploadingFile || (!text.trim() && !attachedFile)) ? (isDark ? '#333' : '#e5e5e5') : '#171717',
              border: 'none',
              cursor: (disabled || uploadingFile || (!text.trim() && !attachedFile)) ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              transition: 'all var(--transition-fast)',
            }}>
            <ArrowUp size={15} color={(disabled || !text.trim() && !attachedFile) ? '#666' : '#fff'} strokeWidth={2.5} />
          </button>
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 8, color: footerColor, fontSize: 11, fontWeight: 400 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Paperclip size={10} /> attach</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Slash size={10} /> tools</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><AtSign size={10} /> mention</span>
          <span>EduFlow AI can make mistakes</span>
        </div>
      </div>
    </div>
  );
}
