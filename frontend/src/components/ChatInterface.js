import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { createConversation, getMessages, sendMessageStream } from '../lib/api';
import MessageRenderer from './MessageRenderer';
import InputBar from './InputBar';
import { executeTool } from '../lib/api';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function getHeaders(user) {
  return { 'Content-Type': 'application/json', 'X-User-Role': user?.role || 'owner', 'X-User-Id': user?.id || 'user-owner-001', 'X-User-Name': user?.name || 'Aman' };
}

async function executeAction(convId, action, params, label, user) {
  const res = await fetch(`${API}/chat/conversations/${convId}/action`, {
    method: 'POST', headers: getHeaders(user),
    body: JSON.stringify({ action, params, label }),
  });
  return res.json();
}

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', gap: 12, padding: '8px 0', alignItems: 'flex-start' }}>
      <div style={{ width: 30, height: 30, borderRadius: 8, background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Outfit, sans-serif', fontWeight: 700, fontSize: 13, color: '#818CF8', flexShrink: 0 }}>AI</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, paddingTop: 6 }}>
        <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
      </div>
    </div>
  );
}

function ToolCallBadge({ tool, status }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.25)', borderRadius: 6, padding: '3px 8px', fontSize: 11, color: '#93C5FD', marginBottom: 8 }}>
      {status === 'running' ? <div className="spinner" style={{ width: 10, height: 10 }} /> : <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#10B981' }} />}
      <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{tool}</span>
      <span style={{ color: '#64748B' }}>{status === 'running' ? '...' : 'done'}</span>
    </div>
  );
}

function HealthScoreWidget({ user }) {
  const [score, setScore] = useState(null);
  useEffect(() => {
    if (user.role !== 'owner' && user.role !== 'admin') return;
    executeTool('get_school_pulse', {}, user).then(r => {
      if (!r.success) return;
      const d = r.data?.summary || {};
      const att = parseFloat(d.attendance_rate) || 0;
      const fees = r.data?.fee_stats?.paid ? 75 : 50;
      const alerts = r.data?.active_alerts || 0;
      const s = Math.max(0, Math.min(100, Math.round((att * 0.4) + (fees * 0.4) - (alerts * 5) + 20)));
      setScore(s);
    }).catch(() => {});
  }, [user.id]);

  if (score === null || (user.role !== 'owner' && user.role !== 'admin')) return null;
  const color = score >= 80 ? '#10B981' : score >= 60 ? '#F59E0B' : '#EF4444';

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, background: '#161622', border: `1px solid ${color}30`, borderRadius: 10, padding: '10px 16px', marginBottom: 20 }}>
      <div style={{ width: 48, height: 48, borderRadius: '50%', border: `3px solid ${color}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: 16, fontWeight: 800, color, fontFamily: 'Outfit, sans-serif' }}>{score}</span>
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#E2E8F0' }}>School Health Score</div>
        <div style={{ fontSize: 11, color: '#64748B' }}>Based on attendance, fees & alerts</div>
      </div>
    </div>
  );
}

export default function ChatInterface({ activeConvId, activeConvTitle, onConvCreated }) {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [convId, setConvId] = useState(activeConvId);
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [currentStreamMsg, setCurrentStreamMsg] = useState(null);
  const messagesEndRef = useRef(null);

  // Refs to prevent React Strict Mode double-fire issues
  const justCreatedRef = useRef(false);
  const pendingFinalMsgRef = useRef(null);
  const processedMessageIds = useRef(new Set());

  // Sync external convId
  useEffect(() => {
    if (activeConvId && activeConvId !== convId) {
      setConvId(activeConvId);
    }
  }, [activeConvId]);

  // Load messages when conversation changes (but skip on new creation)
  useEffect(() => {
    if (convId) {
      if (justCreatedRef.current) {
        justCreatedRef.current = false;
        return;
      }
      processedMessageIds.current.clear();
      setMessages([]);
      loadMessages(convId);
    } else {
      setMessages([]);
      processedMessageIds.current.clear();
    }
  }, [convId, currentUser.id]);

  // Add final message when streaming stops (avoids nested setState anti-pattern)
  useEffect(() => {
    if (!streaming && pendingFinalMsgRef.current) {
      const finalMsg = pendingFinalMsgRef.current;
      pendingFinalMsgRef.current = null;
      setMessages(m => {
        if (m.some(msg => msg.id === finalMsg.id)) return m;
        return [...m, finalMsg];
      });
    }
  }, [streaming]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentStreamMsg]);

  const loadMessages = async (id) => {
    try {
      const res = await getMessages(id, currentUser);
      if (res.success) {
        const msgs = res.data || [];
        msgs.forEach(m => processedMessageIds.current.add(m.id));
        setMessages(msgs);
      }
    } catch {}
  };

  const handleSend = async (text) => {
    if (!text.trim() || streaming) return;

    let cid = convId;

    if (!cid) {
      const res = await createConversation(currentUser);
      if (!res.success) return;
      cid = res.data.id;
      justCreatedRef.current = true;
      setConvId(cid);
      onConvCreated(cid);
    }

    const tempId = `tmp-${Date.now()}`;
    const userMsg = { id: tempId, role: 'user', content: text, created_at: new Date().toISOString() };
    processedMessageIds.current.add(tempId);
    setMessages(prev => [...prev, userMsg]);
    setStreaming(true);
    setCurrentStreamMsg({ id: 'streaming', role: 'assistant', content: '', toolCall: null, richBlocks: [], actionButtons: [] });

    try {
      await sendMessageStream(cid, text, currentUser, (event) => {
        if (event.type === 'text_delta') {
          setCurrentStreamMsg(prev => prev ? ({ ...prev, content: (prev.content || '') + event.delta }) : prev);
        } else if (event.type === 'tool_call') {
          setCurrentStreamMsg(prev => prev ? ({ ...prev, toolCall: { tool: event.tool, status: event.status } }) : prev);
        } else if (event.type === 'rich_blocks') {
          setCurrentStreamMsg(prev => prev ? ({ ...prev, richBlocks: event.blocks || [], actionButtons: event.action_buttons || [] }) : prev);
        } else if (event.type === 'done') {
          const messageId = event.message_id || `ai-${Date.now()}`;
          // Track token usage in localStorage
          if (event.tokens_used) {
            const key = `token-usage-${currentUser.id}`;
            let usage = { used: 0, limit: 50000, sessions: 0 };
            try { usage = JSON.parse(localStorage.getItem(key) || '{}') || usage; } catch {}
            usage.used = (usage.used || 0) + event.tokens_used;
            usage.sessions = (usage.sessions || 0) + 1;
            usage.limit = usage.limit || 50000;
            localStorage.setItem(key, JSON.stringify(usage));
          }
          // Save final message to ref, clear streaming state
          setCurrentStreamMsg(prev => {
            if (prev && !processedMessageIds.current.has(messageId)) {
              processedMessageIds.current.add(messageId);
              pendingFinalMsgRef.current = { ...prev, id: messageId, role: 'assistant' };
            }
            return null;
          });
          setStreaming(false);
        }
      });
    } catch {
      setStreaming(false);
      setCurrentStreamMsg(null);
      setMessages(prev => [...prev, { id: `err-${Date.now()}`, role: 'assistant', content: 'Something went wrong. Please try again.', created_at: new Date().toISOString() }]);
    }
  };

  const handleActionButton = async (action, params, label) => {
    if (!convId) return;
    const actionId = `act-${Date.now()}`;
    setMessages(prev => [...prev, { id: actionId, role: 'user', content: `▶ ${label || action}`, isAction: true, created_at: new Date().toISOString() }]);
    try {
      const res = await executeAction(convId, action, params, label, currentUser);
      if (res.success) {
        const resultId = `res-${Date.now()}`;
        setMessages(prev => [...prev, { id: resultId, role: 'assistant', content: res.data?.message || 'Done.', created_at: new Date().toISOString() }]);
      }
    } catch {}
  };

  const isNewChat = !convId || messages.length === 0;
  const chatBg = isDark ? '#0A0A0F' : '#F8F9FC';
  const titleBorder = isDark ? '#1A1A24' : '#F1F5F9';
  const titleColor = isDark ? '#64748B' : '#94A3B8';
  const greetColor = isDark ? '#fff' : '#0F172A';
  const greetSub = isDark ? '#64748B' : '#94A3B8';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative', background: chatBg }}>
      {activeConvTitle && !isNewChat && (
        <div style={{ padding: '7px 24px', borderBottom: `1px solid ${titleBorder}`, fontSize: 11, color: titleColor, fontWeight: 500, background: chatBg, flexShrink: 0 }}>
          {activeConvTitle}
        </div>
      )}

      <div data-testid="messages-area" style={{ flex: 1, overflowY: 'auto', padding: '20px 0 200px' }}>
        <div style={{ maxWidth: 820, margin: '0 auto', padding: '0 24px' }}>
          {isNewChat && (
            <div className="fade-in" style={{ textAlign: 'center', padding: '48px 0 32px' }}>
              <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 22, fontWeight: 600, color: greetColor, marginBottom: 8 }}>
                Hello {currentUser.name}!
              </h2>
              <p style={{ color: greetSub, fontSize: 13, marginBottom: 24 }}>
                What can I assist you with today?
              </p>
              <HealthScoreWidget user={currentUser} />
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={msg.id || idx} className="fade-in">
              <MessageRenderer message={msg} onActionButton={handleActionButton} />
            </div>
          ))}

          {streaming && currentStreamMsg && (
            <div className="fade-in">
              {currentStreamMsg.toolCall && (
                <div style={{ paddingLeft: 42, marginBottom: 4 }}>
                  <ToolCallBadge tool={currentStreamMsg.toolCall.tool} status={currentStreamMsg.toolCall.status} />
                </div>
              )}
              {currentStreamMsg.content ? (
                <MessageRenderer message={{ ...currentStreamMsg, role: 'assistant' }} isStreaming onActionButton={handleActionButton} />
              ) : (
                <TypingIndicator isDark={isDark} />
              )}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>
      <InputBar onSend={handleSend} disabled={streaming} isDark={isDark} />
    </div>
  );
}
