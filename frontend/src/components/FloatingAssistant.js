import React, { useState, useRef, useEffect } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { MessageCircle, X, Send, Bot, ChevronDown, RotateCcw } from 'lucide-react';
import { getAuthHeaders } from '../lib/authSession';

const API = process.env.REACT_APP_BACKEND_URL + '/api/assistant';

function getH() {
  return getAuthHeaders();
}

function TypingDots({ isDark }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '10px 14px' }}>
      {[0, 1, 2].map(i => (
        <span key={i} style={{
          width: 6, height: 6, borderRadius: '50%',
          background: isDark ? '#555' : '#ccc',
          display: 'inline-block',
          animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
    </div>
  );
}

const SUGGESTED = [
  'What tools does an admin have?',
  'How do I mark attendance?',
  'How to generate a TC?',
  'What is the Query & Support tool?',
];

export default function FloatingAssistant() {
  const { isDark } = useTheme();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hi! I'm your EduFlow guide. Ask me anything about the dashboard — tools, workflows, navigation, or features." }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [unread, setUnread] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setUnread(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const send = async (text) => {
    const msg = (text || input).trim();
    if (!msg || loading) return;
    setInput('');

    const updated = [...messages, { role: 'user', content: msg }];
    setMessages(updated);
    setLoading(true);

    try {
      const res = await fetch(API, {
        method: 'POST',
        headers: getH(),
        body: JSON.stringify({ messages: updated }),
      }).then(r => r.json());

      const reply = res.reply || "Sorry, I couldn't get a response. Please try again.";
      setMessages(prev => [...prev, { role: 'assistant', content: reply }]);
      if (!open) setUnread(true);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: "Connection error. Please check your network and try again." }]);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setMessages([{ role: 'assistant', content: "Hi! I'm your EduFlow guide. Ask me anything about the dashboard — tools, workflows, navigation, or features." }]);
    setInput('');
  };

  const bg = isDark ? '#1a1a1a' : '#ffffff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const tp = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#666' : '#a3a3a3';
  const inputBg = isDark ? '#111' : '#f9f9f9';
  const userBubble = '#4f8ff7';
  const aiBubbleBg = isDark ? '#252525' : '#f3f4f6';
  const aiBubbleText = isDark ? '#e5e5e5' : '#1f2937';

  return (
    <>
      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-6px); }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(16px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        .assistant-panel { animation: slideUp 0.22s cubic-bezier(0.34, 1.56, 0.64, 1) forwards; }
        .assistant-msg { animation: slideUp 0.18s ease forwards; }
      `}</style>

      {/* Floating button */}
      <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 1000 }}>
        {!open && (
          <button
            onClick={() => setOpen(true)}
            title="EduFlow Assistant"
            style={{
              width: 52, height: 52, borderRadius: '50%',
              background: 'linear-gradient(135deg, #4f8ff7, #a78bfa)',
              border: 'none', cursor: 'pointer', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 20px rgba(79,143,247,0.45)',
              transition: 'transform 0.2s ease, box-shadow 0.2s ease',
              position: 'relative',
            }}
            onMouseEnter={e => { e.currentTarget.style.transform = 'scale(1.08)'; e.currentTarget.style.boxShadow = '0 6px 24px rgba(79,143,247,0.6)'; }}
            onMouseLeave={e => { e.currentTarget.style.transform = 'scale(1)'; e.currentTarget.style.boxShadow = '0 4px 20px rgba(79,143,247,0.45)'; }}
          >
            <MessageCircle size={22} color="#fff" strokeWidth={2} />
            {unread && (
              <span style={{
                position: 'absolute', top: 4, right: 4,
                width: 10, height: 10, borderRadius: '50%',
                background: '#f87171', border: '2px solid #1a1a1a',
              }} />
            )}
          </button>
        )}

        {/* Chat panel */}
        {open && (
          <div className="assistant-panel" style={{
            width: 360, height: 520,
            background: bg, border: `1px solid ${border}`,
            borderRadius: 18, boxShadow: '0 8px 40px rgba(0,0,0,0.18)',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            {/* Header */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '14px 16px', borderBottom: `1px solid ${border}`,
              background: isDark ? '#141414' : '#fafafa',
              flexShrink: 0,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: 10,
                  background: 'linear-gradient(135deg, #4f8ff7, #a78bfa)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Bot size={16} color="#fff" />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: tp, lineHeight: 1.2 }}>EduFlow Assistant</div>
                  <div style={{ fontSize: 11, color: '#34d399', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#34d399', display: 'inline-block' }} />
                    Dashboard guide
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                <button onClick={reset} title="Clear chat"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: muted, padding: 6, borderRadius: 8, transition: 'all 0.15s' }}
                  onMouseEnter={e => e.currentTarget.style.background = isDark ? '#252525' : '#f0f0f0'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <RotateCcw size={14} />
                </button>
                <button onClick={() => setOpen(false)} title="Minimise"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: muted, padding: 6, borderRadius: 8, transition: 'all 0.15s' }}
                  onMouseEnter={e => e.currentTarget.style.background = isDark ? '#252525' : '#f0f0f0'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <ChevronDown size={16} />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '14px 14px 8px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {messages.map((msg, i) => (
                <div key={i} className="assistant-msg" style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  {msg.role === 'assistant' && (
                    <div style={{ width: 24, height: 24, borderRadius: 7, background: 'linear-gradient(135deg, #4f8ff7, #a78bfa)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginRight: 8, marginTop: 2 }}>
                      <Bot size={12} color="#fff" />
                    </div>
                  )}
                  <div style={{
                    maxWidth: '78%',
                    padding: '9px 13px',
                    borderRadius: msg.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                    background: msg.role === 'user' ? userBubble : aiBubbleBg,
                    color: msg.role === 'user' ? '#fff' : aiBubbleText,
                    fontSize: 13, lineHeight: 1.55, fontWeight: 400,
                    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  }}>
                    {msg.content}
                  </div>
                </div>
              ))}

              {loading && (
                <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                  <div style={{ width: 24, height: 24, borderRadius: 7, background: 'linear-gradient(135deg, #4f8ff7, #a78bfa)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: 8, marginTop: 2 }}>
                    <Bot size={12} color="#fff" />
                  </div>
                  <div style={{ background: aiBubbleBg, borderRadius: '14px 14px 14px 4px' }}>
                    <TypingDots isDark={isDark} />
                  </div>
                </div>
              )}

              {/* Suggestions — shown only on first message */}
              {messages.length === 1 && !loading && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                  {SUGGESTED.map(s => (
                    <button key={s} onClick={() => send(s)}
                      style={{
                        fontSize: 11, padding: '5px 10px', borderRadius: 20,
                        border: `1px solid ${border}`, background: 'transparent',
                        color: isDark ? '#aaa' : '#555', cursor: 'pointer',
                        transition: 'all 0.15s',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.background = isDark ? '#252525' : '#f0f0f0'; e.currentTarget.style.color = tp; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = isDark ? '#aaa' : '#555'; }}>
                      {s}
                    </button>
                  ))}
                </div>
              )}

              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div style={{ padding: '10px 12px 14px', borderTop: `1px solid ${border}`, flexShrink: 0 }}>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, background: inputBg, border: `1px solid ${border}`, borderRadius: 12, padding: '8px 10px 8px 14px' }}>
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={e => { setInput(e.target.value); e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px'; }}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
                  placeholder="Ask about any tool or feature…"
                  rows={1}
                  style={{
                    flex: 1, resize: 'none', border: 'none', outline: 'none',
                    background: 'transparent', color: tp, fontSize: 13, lineHeight: 1.5,
                    fontFamily: 'Inter, sans-serif', maxHeight: 100, overflowY: 'auto',
                  }}
                />
                <button
                  onClick={() => send()}
                  disabled={!input.trim() || loading}
                  style={{
                    width: 32, height: 32, borderRadius: 9, border: 'none', cursor: input.trim() && !loading ? 'pointer' : 'default',
                    background: input.trim() && !loading ? 'linear-gradient(135deg, #4f8ff7, #a78bfa)' : (isDark ? '#2a2a2a' : '#e5e5e5'),
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0, transition: 'all 0.15s',
                  }}>
                  <Send size={14} color={input.trim() && !loading ? '#fff' : muted} />
                </button>
              </div>
              <div style={{ fontSize: 10, color: muted, marginTop: 6, textAlign: 'center' }}>
                EduFlow guide only · Enter to send · Shift+Enter for new line
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
