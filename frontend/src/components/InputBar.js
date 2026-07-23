import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Slash, AtSign, Paperclip, X, Loader, Mic } from 'lucide-react';
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

function getSpeechRecognitionCtor() {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function getVoiceErrorMessage(error) {
  switch (error) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Microphone access was blocked. Allow mic access and try again.';
    case 'audio-capture':
      return 'No microphone was detected on this device.';
    case 'network':
      return 'Voice capture lost connection. Please check your network and try again.';
    case 'no-speech':
      return 'No speech was detected. Try again and speak a little closer to the mic.';
    default:
      return 'Voice capture could not start. Please try again.';
  }
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
  const [voiceError, setVoiceError] = useState('');
  const [isListening, setIsListening] = useState(false);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const slashPosRef = useRef(-1);
  const atPosRef = useRef(-1);
  const recognitionRef = useRef(null);
  const listeningRef = useRef(false);
  const speechBaseRef = useRef('');
  const finalTranscriptRef = useRef('');
  const voiceSessionRef = useRef(0);
  const userStoppedVoiceRef = useRef(false);

  const allTools = TOOLS_BY_ROLE[currentUser.role] || [];
  const voiceSupported = Boolean(getSpeechRecognitionCtor());

  const resizeTextarea = (el = textareaRef.current) => {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  };

  const syncComposerState = (val, cursor = val.length, textareaEl = textareaRef.current) => {
    setText(val);
    resizeTextarea(textareaEl);

    const beforeCursor = val.slice(0, cursor);
    const slashMatch = beforeCursor.match(/\/([a-zA-Z0-9-]*)$/);
    const atMatch = beforeCursor.match(/@([a-zA-Z0-9 ]*)$/);

    if (slashMatch) {
      const query = slashMatch[1].toLowerCase();
      const pos = cursor - slashMatch[0].length;
      slashPosRef.current = pos;
      setSlashQuery(query);
      setSlashFiltered(allTools.filter(t => t.label.includes(query) || t.desc.toLowerCase().includes(query)));
      setShowSlash(true);
      setShowAt(false);
      setSelectedIdx(0);
      return;
    }

    if (atMatch) {
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
      } else {
        setAtResults([]);
      }
      return;
    }

    setShowSlash(false);
    setShowAt(false);
    setAtResults([]);
  };

  const stopVoiceCapture = ({ discardTranscript = false } = {}) => {
    const recognition = recognitionRef.current;
    userStoppedVoiceRef.current = true;
    listeningRef.current = false;
    setIsListening(false);
    if (discardTranscript) {
      voiceSessionRef.current += 1;
      recognitionRef.current = null;
    }
    if (!recognition) return;
    try {
      if (discardTranscript) recognition.abort();
      else recognition.stop();
    } catch {
      recognitionRef.current = null;
    }
  };

  const handleChange = (e) => {
    if (listeningRef.current) stopVoiceCapture({ discardTranscript: true });
    setVoiceError('');
    syncComposerState(e.target.value, e.target.selectionStart, e.target);
  };

  const insertSlashTool = (tool) => {
    if (listeningRef.current) stopVoiceCapture({ discardTranscript: true });
    const cursor = textareaRef.current?.selectionStart || text.length;
    const beforeSlash = text.slice(0, slashPosRef.current);
    const afterCursor = text.slice(cursor);
    const insertion = `/${tool.label} `;
    const newText = beforeSlash + insertion + afterCursor;
    syncComposerState(newText, beforeSlash.length + insertion.length);
    setShowSlash(false);
    textareaRef.current?.focus();
    setTimeout(() => {
      const newPos = beforeSlash.length + insertion.length;
      textareaRef.current?.setSelectionRange(newPos, newPos);
    }, 0);
  };

  const insertAtMention = (person) => {
    if (listeningRef.current) stopVoiceCapture({ discardTranscript: true });
    const cursor = textareaRef.current?.selectionStart || text.length;
    const beforeAt = text.slice(0, atPosRef.current);
    const afterCursor = text.slice(cursor);
    const insertion = `@${person.name} `;
    syncComposerState(beforeAt + insertion + afterCursor, beforeAt.length + insertion.length);
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

  const handleVoiceToggle = () => {
    if (disabled || uploadingFile) return;
    if (isListening) {
      stopVoiceCapture();
      return;
    }

    const SpeechRecognition = getSpeechRecognitionCtor();
    if (!SpeechRecognition) {
      setVoiceError('Voice input is not supported in this browser.');
      return;
    }

    const recognition = new SpeechRecognition();
    const sessionId = voiceSessionRef.current + 1;
    voiceSessionRef.current = sessionId;
    userStoppedVoiceRef.current = false;
    speechBaseRef.current = text.trimEnd();
    finalTranscriptRef.current = '';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    const preferredLanguage = typeof navigator !== 'undefined'
      ? (navigator.languages?.[0] || navigator.language)
      : null;
    recognition.lang = preferredLanguage || 'en-IN';

    recognition.onresult = (event) => {
      if (voiceSessionRef.current !== sessionId) return;
      let committed = finalTranscriptRef.current;
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const chunk = (event.results[i]?.[0]?.transcript || '').trim();
        if (!chunk) continue;
        if (event.results[i].isFinal) {
          committed = committed ? `${committed} ${chunk}` : chunk;
        } else {
          interim = interim ? `${interim} ${chunk}` : chunk;
        }
      }
      finalTranscriptRef.current = committed.replace(/\s+/g, ' ').trim();
      const nextText = [speechBaseRef.current, finalTranscriptRef.current, interim]
        .filter(Boolean)
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim();
      syncComposerState(nextText, nextText.length);
    };

    recognition.onerror = (event) => {
      if (voiceSessionRef.current !== sessionId) return;
      if (userStoppedVoiceRef.current && event.error === 'aborted') return;
      setVoiceError(getVoiceErrorMessage(event.error));
    };

    recognition.onend = () => {
      if (voiceSessionRef.current !== sessionId) return;
      recognitionRef.current = null;
      listeningRef.current = false;
      setIsListening(false);
      userStoppedVoiceRef.current = false;
      setTimeout(() => {
        textareaRef.current?.focus();
        const end = textareaRef.current?.value?.length || 0;
        textareaRef.current?.setSelectionRange(end, end);
      }, 0);
    };

    recognitionRef.current = recognition;
    listeningRef.current = true;
    setIsListening(true);
    setVoiceError('');

    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      listeningRef.current = false;
      setIsListening(false);
      setVoiceError('Voice capture could not start. Please try again.');
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
    } catch (err) {
      // uploadChatFile throws with a specific reason (too large / blocked at the
      // edge / HTTP status); only a plain network drop falls back to the generic line.
      setUploadError(err?.message && err.name !== 'AbortError' ? err.message : 'Upload failed. Please try again.');
    }
    setUploadingFile(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeAttachment = () => {
    setAttachedFile(null);
    setUploadError('');
  };

  const handleSend = () => {
    if (listeningRef.current) stopVoiceCapture({ discardTranscript: true });
    const trimmed = text.trim();
    if ((!trimmed && !attachedFile) || disabled || uploadingFile) return;
    let finalText = trimmed;
    if (attachedFile) {
      const fileContext = `[File attached: ${attachedFile.filename}]\n\n${attachedFile.extractedText}`;
      finalText = trimmed ? `${trimmed}\n\n---\n${fileContext}` : fileContext;
    }
    // Snapshot the raw input so we can put it back if the turn can't even start.
    const snapshotText = text;
    const snapshotFile = attachedFile;
    const result = onSend(finalText, attachedFile?.imageData || null);
    // Optimistic clear.
    setText('');
    setAttachedFile(null);
    setUploadError('');
    setVoiceError('');
    setShowSlash(false);
    setShowAt(false);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    // FH2 (R8.1 AC2): if handleSend reports it couldn't start (e.g. the
    // conversation failed to create), restore what the user typed so it isn't
    // silently lost. A normal send resolves undefined and nothing is restored.
    Promise.resolve(result).then((ok) => {
      if (ok === false) {
        syncComposerState(snapshotText, snapshotText.length);
        setAttachedFile(snapshotFile);
      }
    }).catch(() => {});
  };

  useEffect(() => (
    () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {}
      }
    }
  ), []);

  const inputBg = 'var(--color-surface-raised)';
  const inputBorder = 'var(--color-border-strong)';
  const inputColor = 'var(--color-text-primary)';
  const dropdownBg = 'var(--color-surface-raised)';
  const dropdownBorder = 'var(--color-border-strong)';
  const gradBg = 'var(--color-page)';
  const footerColor = isDark ? '#666' : '#525252';
  const muted = 'var(--color-text-muted)';
  const voiceButtonTitle = !voiceSupported
    ? 'Voice input is available in supported browsers with microphone access'
    : isListening
      ? 'Stop voice input'
      : 'Start voice input';

  const showList = showSlash ? slashFiltered : showAt ? atResults : [];

  return (
    <div data-testid="input-bar" style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      background: `linear-gradient(to top, ${gradBg} 75%, transparent)`,
      padding: '32px 24px 20px', zIndex: 40,
    }}>
      <div style={{ width: '100%', margin: '0 auto', position: 'relative' }}>
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
                  background: i === selectedIdx ? 'var(--bg-active)' : 'transparent',
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

        {(uploadError || voiceError) && (
          <div style={{ fontSize: 11, color: uploadError ? '#f87171' : '#fbbf24', marginBottom: 6 }}>
            {uploadError || voiceError}
          </div>
        )}

        <input ref={fileInputRef} type="file" onChange={handleFileSelect} style={{ display: 'none' }} data-testid="file-input"
          accept=".txt,.md,.html,.htm,.csv,.json,.xml,.pdf,.doc,.docx,.xlsx,.xls,.pptx,.png,.jpg,.jpeg,.heic,.webp,.gif,.zip,.py,.js,.ts,.sql,.log"
        />

        {/* .composer-shell owns the focus indication for the whole pill —
            see index.css. The textarea inside opts out of the global ring. */}
        <div className="composer-shell" style={{
          background: inputBg,
          border: `1px solid ${disabled ? 'var(--color-border-subtle, var(--color-border))' : inputBorder}`,
          borderRadius: 'var(--radius-xl)', display: 'flex', alignItems: 'center',
          padding: '10px 12px', gap: 8,
          boxShadow: 'var(--shadow-md)',
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

          <button
            data-testid="voice-input-btn"
            onClick={handleVoiceToggle}
            disabled={disabled || uploadingFile || !voiceSupported}
            aria-pressed={isListening}
            title={voiceButtonTitle}
            style={{
              width: 32, height: 32, borderRadius: 10, flexShrink: 0,
              background: isListening ? '#4f8ff715' : 'transparent',
              border: 'none',
              cursor: disabled || uploadingFile || !voiceSupported ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: isListening ? '#4f8ff7' : muted,
              opacity: voiceSupported ? 1 : 0.45,
              transition: 'background var(--transition-fast), color var(--transition-fast)',
            }}
          >
            <Mic size={15} />
          </button>

          <textarea ref={textareaRef} data-testid="chat-input" value={text} onChange={handleChange} onKeyDown={handleKeyDown}
            placeholder={disabled ? 'EduFlow is thinking...' : 'Message EduFlow...'}
            disabled={disabled} rows={1}
            // The composer pill carries the focus indication (.composer-shell
            // :focus-within). Ringing this transparent, edge-to-edge field as
            // well drew a second blue pill inside the first one.
            data-focus-ring="none"
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: disabled ? muted : inputColor, fontSize: 'var(--text-base)', resize: 'none',
              lineHeight: 1.5, padding: 0, fontFamily: 'var(--font-body)',
              maxHeight: 160, overflowY: 'auto',
            }}
          />
          {/* Send.
              It used to fill with --color-border-strong when idle and near-black
              when ready. --color-border-strong is a BORDER token, raised to a
              slate blue so a secondary button's outline can clear 3:1; used as a
              fill it made the button look like a washed-out grey-blue tile.
              Now: brand blue with a chunky press when there is something to
              send, a plain recessed surface when there is not. */}
          {(() => {
            const inert = disabled || uploadingFile || (!text.trim() && !attachedFile);
            return (
              <button data-testid="chat-send" onClick={handleSend} disabled={inert}
                aria-label="Send message"
                style={{
                  width: 34, height: 34, borderRadius: 'var(--radius-md)',
                  background: inert ? 'var(--color-surface-raised)' : 'var(--brand-blue-fill)',
                  border: inert ? '1px solid var(--color-border)' : 'none',
                  boxShadow: inert ? 'none' : '0 3px 0 0 var(--brand-blue-press)',
                  cursor: inert ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  transition: 'background var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast)',
                }}
                // transform only, so pressing send never nudges the composer.
                onMouseDown={e => { if (!inert) e.currentTarget.style.transform = 'translateY(2px)'; }}
                onMouseUp={e => { e.currentTarget.style.transform = 'translateY(0)'; }}
                onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; }}
              >
                <ArrowUp
                  size={16}
                  color={inert ? 'var(--color-text-muted)' : 'var(--on-brand-blue)'}
                  strokeWidth={2.6}
                />
              </button>
            );
          })()}
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 8, color: footerColor, fontSize: 11, fontWeight: 400 }}>
          {isListening && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#4f8ff7' }}>
              <Mic size={10} /> listening
            </span>
          )}
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Slash size={10} /> tools</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><AtSign size={10} /> mention</span>
          <span>Flo can make mistakes</span>
        </div>
      </div>
    </div>
  );
}
