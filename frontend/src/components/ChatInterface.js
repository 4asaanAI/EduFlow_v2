import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { apiFetch, createConversation, getBrowserSseSessionId, getMessages, sendMessageStream } from '../lib/api';
import MessageRenderer from './MessageRenderer';
import InputBar from './InputBar';
import TokenBudgetBar from './TokenBudgetBar';
import { executeTool } from '../lib/api';
import { getAuthHeaders } from '../lib/authSession';
import { Sparkles } from 'lucide-react';
import ThinkingProcess from './ThinkingProcess';
import ConfirmActionCard from './ConfirmActionCard';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function getHeaders() {
  return getAuthHeaders();
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
    <div style={{ display: 'flex', gap: 14, padding: '12px 0', alignItems: 'flex-start' }}>
      <div style={{
        width: 28, height: 28, borderRadius: 8,
        background: 'linear-gradient(135deg, rgba(79,143,247,0.15), rgba(167,139,250,0.15))',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <Sparkles size={13} color="#a78bfa" />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, paddingTop: 8 }}>
        <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
      </div>
    </div>
  );
}

function ToolCallBadge({ tool, status }) {
  const { isDark } = useTheme();
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 7,
      background: isDark ? 'rgba(79,143,247,0.08)' : 'rgba(79,143,247,0.06)',
      border: `1px solid ${isDark ? 'rgba(79,143,247,0.15)' : 'rgba(79,143,247,0.12)'}`,
      borderRadius: 8, padding: '4px 10px', fontSize: 12, color: '#4f8ff7', marginBottom: 10,
    }}>
      {status === 'running' ? <div className="spinner" style={{ width: 10, height: 10 }} /> : <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#34d399' }} />}
      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>{tool}</span>
      <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{status === 'running' ? 'running...' : 'completed'}</span>
    </div>
  );
}

function HealthScoreWidget({ user }) {
  const { isDark } = useTheme();
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
  const color = score >= 80 ? '#34d399' : score >= 60 ? '#fbbf24' : '#f87171';

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 14,
      background: isDark ? '#1e1e1e' : '#ffffff',
      border: `1px solid ${isDark ? '#2e2e2e' : '#e5e5e5'}`,
      borderRadius: 14, padding: '14px 20px', marginBottom: 24,
      boxShadow: 'var(--shadow-sm)',
    }}>
      <div style={{
        width: 52, height: 52, borderRadius: 14,
        border: `3px solid ${color}`, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: `${color}10`,
      }}>
        <span style={{ fontSize: 18, fontWeight: 800, color }}>{score}</span>
      </div>
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>School Health</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>Attendance, fees & alerts</div>
      </div>
    </div>
  );
}

function getQuickActionSuggestions(user) {
  const role = user?.role;
  const subRole = user?.sub_category;

  if (role === 'student') {
    return [
      'Explain my latest attendance trend',
      'Help me revise today\'s homework topic',
      'Show my exam results',
      'Guide me on career options after school',
    ];
  }

  if (role === 'teacher') {
    return [
      'Show my class attendance today',
      'List my class students',
      'Create a quick lesson plan for tomorrow',
      'Which students need attention this week?',
    ];
  }

  if (role === 'admin' && subRole === 'accounts') {
    return [
      'Show today\'s fee collection summary',
      'List overdue fee defaulters',
      'Show fee structure for Class 5',
      'Find payment history for a student',
    ];
  }

  if (role === 'admin' && subRole === 'transport_head') {
    return [
      'Show transport status',
      'List active bus routes',
      'Which drivers are present today?',
      'Show route issues needing attention',
    ];
  }

  if (role === 'admin' && subRole === 'principal') {
    return [
      'Give me the principal morning brief',
      'Show pending leave requests',
      'List open parent complaints',
      'Show today\'s attendance overview',
    ];
  }

  return [
    'Show today\'s school pulse',
    'Generate a school health report',
    'How many fee defaulters are there?',
    'List pending leave requests',
  ];
}

// Quick action suggestions for the greeting screen
function QuickActions({ onSend, isDark, user }) {
  const suggestions = getQuickActionSuggestions(user);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, maxWidth: 500, margin: '0 auto' }}>
      {suggestions.map((s, i) => (
        <button key={i} onClick={() => onSend(s)} style={{
          background: isDark ? '#1e1e1e' : '#ffffff',
          border: `1px solid ${isDark ? '#2e2e2e' : '#e5e5e5'}`,
          borderRadius: 12, padding: '12px 14px', textAlign: 'left',
          color: 'var(--text-secondary)', fontSize: 13, cursor: 'pointer',
          transition: 'all var(--transition-fast)', lineHeight: 1.4,
        }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = isDark ? '#444' : '#ccc'; e.currentTarget.style.background = isDark ? '#252525' : '#fafafa'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = isDark ? '#2e2e2e' : '#e5e5e5'; e.currentTarget.style.background = isDark ? '#1e1e1e' : '#ffffff'; }}>
          {s}
        </button>
      ))}
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
  const [aiUnavailable, setAiUnavailable] = useState(false);
  const [aiUnavailableMessage, setAiUnavailableMessage] = useState('');
  const messagesEndRef = useRef(null);
  const chatSessionIdRef = useRef(getBrowserSseSessionId());

  const justCreatedRef = useRef(false);
  const pendingFinalMsgRef = useRef(null);
  const processedMessageIds = useRef(new Set());

  // New state variables for thinking, confirm action
  const [thinkingSteps, setThinkingSteps] = useState([]);
  const [thinkingCollapsed, setThinkingCollapsed] = useState(false);
  const [thinkingStartTime, setThinkingStartTime] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null); // {action_id, tool, params, display, buttons}

  // Token budget state
  const [tokenUsed, setTokenUsed] = useState(0);
  const [tokenLimit, setTokenLimit] = useState(-1); // -1 = unlimited
  const [tokenCanRecharge, setTokenCanRecharge] = useState(false);
  const [tokenSelfRechargeEnabled, setTokenSelfRechargeEnabled] = useState(true);
  const [tokenExhausted, setTokenExhausted] = useState(false);

  // Ref to track thinkingStartTime inside SSE callback without stale closure
  const thinkingStartTimeRef = useRef(null);
  // Ref to track thinkingCollapsed and thinkingSteps inside SSE callback
  const thinkingCollapsedRef = useRef(false);
  const thinkingStepsRef = useRef([]);

  // Keep refs in sync with state
  useEffect(() => {
    thinkingStartTimeRef.current = thinkingStartTime;
  }, [thinkingStartTime]);
  useEffect(() => {
    thinkingCollapsedRef.current = thinkingCollapsed;
  }, [thinkingCollapsed]);
  useEffect(() => {
    thinkingStepsRef.current = thinkingSteps;
  }, [thinkingSteps]);

  useEffect(() => {
    if (activeConvId && activeConvId !== convId) {
      setConvId(activeConvId);
    }
  }, [activeConvId]);

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

  // Fetch token usage on mount and when user changes
  const fetchTokenUsage = useCallback(async () => {
    try {
      const res = await fetch(`${API}/tokens/usage/me`, { headers: getHeaders(currentUser) });
      const data = await res.json();
      if (data.success && data.data) {
        const d = data.data;
        setTokenUsed(d.total_used || 0);
        setTokenLimit(d.role_limit != null ? d.role_limit : -1);
        setTokenSelfRechargeEnabled(d.self_recharge_enabled !== false);
        const isExhausted = d.role_limit > 0 && d.total_used >= d.role_limit && (d.personal_topup_balance || 0) <= 0;
        setTokenExhausted(isExhausted);
        setTokenCanRecharge(isExhausted && d.self_recharge_enabled !== false);
      }
    } catch {
      // Non-fatal — token bar just won't show
    }
  }, [currentUser]);

  useEffect(() => {
    fetchTokenUsage();
  }, [fetchTokenUsage]);

  // Detect return from Stripe checkout and refresh token balance
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const rechargeParam = params.get('recharge');
    if (rechargeParam) {
      window.history.replaceState({}, '', window.location.pathname);
      if (rechargeParam === 'success') {
        fetchTokenUsage();
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRecharge = async (packId) => {
    try {
      const res = await apiFetch(`${API}/tokens/create-checkout-session`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pack_id: packId,
          success_url: `${window.location.origin}?recharge=success`,
          cancel_url: `${window.location.origin}?recharge=cancel`,
        }),
      });
      const data = await res.json();
      if (data.success && data.data && data.data.checkout_url) {
        window.location.href = data.data.checkout_url;
      }
    } catch {
      // Payment initiation error — silently ignore (token bar stays visible)
    }
  };

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

    // Reset thinking state before starting SSE
    setThinkingSteps([]);
    setThinkingCollapsed(false);
    setThinkingStartTime(null);
    setConfirmAction(null);
    setAiUnavailable(false);
    setAiUnavailableMessage('');
    thinkingStartTimeRef.current = null;
    thinkingCollapsedRef.current = false;
    thinkingStepsRef.current = [];

    setStreaming(true);
    setCurrentStreamMsg({ id: 'streaming', role: 'assistant', content: '', toolCall: null, richBlocks: [], actionButtons: [] });

    let streamErrored = false;
    try {
      await sendMessageStream(cid, text, currentUser, (event) => {
        const parsed = event;

        if (event.type === 'thinking_clear') {
          setThinkingSteps([]);
          setThinkingCollapsed(false);
          setThinkingStartTime(null);
          thinkingStartTimeRef.current = null;
          thinkingCollapsedRef.current = false;
          thinkingStepsRef.current = [];
        } else if (event.type === 'thinking') {
          // Append to thinking steps
          setThinkingSteps(prev => {
            const updated = [...prev];
            // Mark previous active step as done
            const activeIdx = updated.findIndex(s => s.status === 'active');
            if (activeIdx >= 0) updated[activeIdx].status = 'done';
            // Add new step as active
            updated.push({
              step: parsed.step,
              message: parsed.message,
              status: 'active',
              timestamp: Date.now(),
              tool: parsed.tool || null,
              count: parsed.count || null
            });
            return updated;
          });
          if (!thinkingStartTimeRef.current) {
            const now = Date.now();
            setThinkingStartTime(now);
            thinkingStartTimeRef.current = now;
          }
        } else if (event.type === 'text_delta') {
          // Collapse thinking on first text_delta
          if (!thinkingCollapsedRef.current && thinkingStepsRef.current.length > 0) {
            setThinkingCollapsed(true);
            thinkingCollapsedRef.current = true;
            // Mark all remaining active steps as done
            setThinkingSteps(prev => prev.map(s => ({ ...s, status: s.status === 'active' ? 'done' : s.status })));
          }
          // Existing text_delta handling
          setCurrentStreamMsg(prev => {
            if (!prev) return prev;
            const accumulated = (prev.content || '') + event.delta;
            // Sanitize raw Azure API error strings before displaying
            const isRawError = accumulated.includes("content management policy") ||
              (accumulated.includes("Error code: 400") && accumulated.includes("error"));
            if (isRawError) {
              return {
                ...prev, content:
                  "I wasn't able to process that specific phrasing due to content policy settings on the AI service. " +
                  "Could you try rephrasing your question? All your school management tools in the sidebar are fully available."
              };
            }
            return { ...prev, content: accumulated };
          });
        } else if (event.type === 'tool_call') {
          setCurrentStreamMsg(prev => prev ? ({ ...prev, toolCall: { tool: event.tool, status: event.status } }) : prev);
        } else if (event.type === 'rich_blocks') {
          setCurrentStreamMsg(prev => prev ? ({ ...prev, richBlocks: event.blocks || [], actionButtons: event.action_buttons || [] }) : prev);
        } else if (event.type === 'confirm_action') {
          setConfirmAction(parsed);
        } else if (event.type === 'navigate') {
          // Trigger tool panel switch
          if (parsed.tool_id) {
            window.dispatchEvent(new CustomEvent('eduflow-navigate', { detail: { toolId: parsed.tool_id } }));
          }
        } else if (event.type === 'token_exhausted') {
          // Token budget exhausted — show recharge prompt and disable input
          setTokenExhausted(true);
          setTokenCanRecharge(!!event.can_recharge);
          fetchTokenUsage();
        } else if (event.type === 'ai_unavailable') {
          const message = event.message || 'AI is temporarily unavailable. Core school tools remain available.';
          setAiUnavailable(true);
          setAiUnavailableMessage(message);
          setCurrentStreamMsg(prev =>
            prev
              ? { ...prev, content: message }
              : { id: `ai-unavail-${Date.now()}`, role: 'assistant', content: message, created_at: new Date().toISOString() }
          );
        } else if (event.type === 'keepalive') {
          // Ignore - just prevents SSE timeout
        } else if (event.type === 'stream_error') {
          streamErrored = true;
          setThinkingSteps([]);
          setThinkingCollapsed(false);
          setCurrentStreamMsg(prev => {
            const interruptedId = `err-${Date.now()}`;
            const suffix = event.retryCount ? `Connection interrupted - retrying (${event.retryCount}/3)...` : 'Connection lost. Tap retry.';
            if (prev?.content) {
              pendingFinalMsgRef.current = {
                ...prev,
                id: interruptedId,
                role: 'assistant',
                content: `${prev.content}\n\n${suffix}`,
                interrupted: true,
              };
            } else {
              setMessages(current => [...current, {
                id: interruptedId,
                role: 'assistant',
                content: suffix,
                interrupted: true,
                created_at: new Date().toISOString(),
              }]);
            }
            return null;
          });
          setStreaming(false);
        } else if (event.type === 'done') {
          const messageId = event.message_id || `ai-${Date.now()}`;
          if (event.tokens_used) {
            // Update token usage locally for immediate bar feedback
            setTokenUsed(prev => prev + event.tokens_used);
            // Also persist to localStorage for backward compat
            const key = `token-usage-${currentUser.id}`;
            let usage = { used: 0, limit: 50000, sessions: 0 };
            try { usage = JSON.parse(localStorage.getItem(key) || '{}') || usage; } catch {}
            usage.used = (usage.used || 0) + event.tokens_used;
            usage.sessions = (usage.sessions || 0) + 1;
            usage.limit = usage.limit || 50000;
            localStorage.setItem(key, JSON.stringify(usage));
          }
          // Finalize thinking - mark all steps as done
          setThinkingSteps(prev => prev.map(s => ({ ...s, status: 'done' })));
          setCurrentStreamMsg(prev => {
            if (prev && !processedMessageIds.current.has(messageId)) {
              processedMessageIds.current.add(messageId);
              pendingFinalMsgRef.current = { ...prev, id: messageId, role: 'assistant' };
            }
            return null;
          });
          setStreaming(false);
        }
      }, chatSessionIdRef.current);
      if (streamErrored) return;
      setStreaming(prev => {
        if (prev) {
          setCurrentStreamMsg(cm => {
            if (cm) {
              const fallbackId = `ai-${Date.now()}`;
              if (!processedMessageIds.current.has(fallbackId)) {
                processedMessageIds.current.add(fallbackId);
                pendingFinalMsgRef.current = { ...cm, id: fallbackId, role: 'assistant' };
              }
            }
            return null;
          });
        }
        return false;
      });
    } catch {
      // On SSE error: append "(Response interrupted)" and show Retry
      setCurrentStreamMsg(prev => {
        if (prev && prev.content) {
          const interruptedId = `err-${Date.now()}`;
          if (!processedMessageIds.current.has(interruptedId)) {
            processedMessageIds.current.add(interruptedId);
            pendingFinalMsgRef.current = {
              ...prev,
              id: interruptedId,
              role: 'assistant',
              content: prev.content + '\n\n*(Response interrupted)*',
              interrupted: true,
            };
          }
        }
        return null;
      });
      setStreaming(false);
      // Finalize thinking on error
      setThinkingSteps(prev => prev.map(s => ({ ...s, status: 'done' })));
      // If there was no content at all, show a plain error message with retry
      setMessages(prev => {
        // Only add fallback error if pendingFinalMsgRef was not set (no partial content)
        if (!pendingFinalMsgRef.current) {
          return [...prev, {
            id: `err-${Date.now()}`,
            role: 'assistant',
            content: 'Something went wrong. Please try again.',
            interrupted: true,
            created_at: new Date().toISOString(),
          }];
        }
        return prev;
      });
    }
  };

  const handleRetry = () => {
    // Find the last user message and resend it
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        handleSend(messages[i].content);
        break;
      }
    }
  };

  const handleActionButton = async (action, params, label) => {
    if (!convId) return;
    const actionId = `act-${Date.now()}`;
    setMessages(prev => [...prev, { id: actionId, role: 'user', content: `\u25B6 ${label || action}`, isAction: true, created_at: new Date().toISOString() }]);
    try {
      const res = await executeAction(convId, action, params, label, currentUser);
      if (res.success) {
        const resultId = `res-${Date.now()}`;
        setMessages(prev => [...prev, { id: resultId, role: 'assistant', content: res.data?.message || 'Done.', created_at: new Date().toISOString() }]);
      } else {
        const resultId = `res-${Date.now()}`;
        setMessages(prev => [...prev, {
          id: resultId,
          role: 'assistant',
          content: res.error || 'Action failed. Please try again.',
          interrupted: true,
          created_at: new Date().toISOString(),
        }]);
      }
    } catch {
      const resultId = `res-${Date.now()}`;
      setMessages(prev => [...prev, {
        id: resultId,
        role: 'assistant',
        content: 'Action failed. Please try again.',
        interrupted: true,
        created_at: new Date().toISOString(),
      }]);
    }
  };

  const isNewChat = !convId || messages.length === 0;
  const chatBg = isDark ? '#1a1a1a' : '#f5f5f5';

  return (
    <div data-testid="chat-interface" style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative', background: chatBg }}>
      <div data-testid="messages-area" style={{ flex: 1, overflowY: 'auto', padding: '24px 0 200px' }}>
        <div data-testid="message-list" style={{ maxWidth: 760, margin: '0 auto', padding: '0 24px' }}>
          {aiUnavailable && (
            <div data-testid="ai-unavailable-banner" style={{
              border: '1px solid var(--border)',
              background: 'var(--bg-card)',
              color: 'var(--text-primary)',
              borderRadius: 8,
              padding: '12px 14px',
              marginBottom: 16,
              fontSize: 13,
              lineHeight: 1.45,
            }}>
              {aiUnavailableMessage || 'AI is temporarily unavailable. Core school tools remain available.'}
            </div>
          )}

          {isNewChat && (
            <div className="fade-in" style={{ textAlign: 'center', padding: '60px 0 40px' }}>
              <div style={{
                width: 48, height: 48, borderRadius: 14, margin: '0 auto 20px',
                background: 'linear-gradient(135deg, #4f8ff7, #a78bfa)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 8px 24px rgba(79,143,247,0.2)',
              }}>
                <Sparkles size={22} color="#fff" />
              </div>
              <h2 style={{
                fontSize: 26, fontWeight: 700, color: 'var(--text-primary)',
                marginBottom: 8, letterSpacing: '-0.03em',
              }}>
                Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, {currentUser.name.split(' ')[0]}
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: 15, marginBottom: 28, fontWeight: 400 }}>
                How can I help you today?
              </p>
              <HealthScoreWidget user={currentUser} />
              <QuickActions onSend={handleSend} isDark={isDark} user={currentUser} />
            </div>
          )}

          {messages.filter(msg => {
            if (msg.role !== 'assistant') return true;
            const hasContent = msg.content && msg.content.trim();
            const richBlocks = msg.richBlocks || msg.rich_content?.rich_blocks || [];
            const actionButtons = msg.actionButtons || msg.rich_content?.action_buttons || msg.actions || [];
            return hasContent || richBlocks.length > 0 || actionButtons.length > 0;
          }).map((msg, idx) => (
            <div key={msg.id || idx} className="fade-in">
              <div className="prose-chat">
                <MessageRenderer message={msg} onActionButton={handleActionButton} />
              </div>
              {msg.interrupted && (
                <div style={{ paddingLeft: 42, marginTop: 8 }}>
                  <button
                    onClick={handleRetry}
                    style={{
                      background: isDark ? '#2a2a2a' : '#ffffff',
                      border: `1px solid ${isDark ? '#3a3a3a' : '#ddd'}`,
                      borderRadius: 8,
                      padding: '6px 14px',
                      fontSize: 12,
                      color: '#4f8ff7',
                      cursor: 'pointer',
                      fontWeight: 500,
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = isDark ? '#333' : '#f0f4ff'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = isDark ? '#2a2a2a' : '#ffffff'; }}
                  >
                    Retry
                  </button>
                </div>
              )}
            </div>
          ))}

          {streaming && currentStreamMsg && (
            <div className="fade-in">
              {currentStreamMsg.toolCall && (
                <div style={{ paddingLeft: 42, marginBottom: 4 }}>
                  <ToolCallBadge tool={currentStreamMsg.toolCall.tool} status={currentStreamMsg.toolCall.status} />
                </div>
              )}
              {thinkingSteps.some(s => ['decision', 'tool_start', 'tool_done', 'searching'].includes(s.step)) && (
                <ThinkingProcess
                  steps={thinkingSteps}
                  isStreaming={streaming}
                  collapsed={thinkingCollapsed}
                  duration={thinkingStartTime ? Date.now() - thinkingStartTime : 0}
                />
              )}
              {currentStreamMsg.content ? (
                <div className="prose-chat">
                  <MessageRenderer message={{ ...currentStreamMsg, role: 'assistant' }} isStreaming onActionButton={handleActionButton} />
                </div>
              ) : (
                !thinkingSteps.some(s => ['decision', 'tool_start', 'tool_done', 'searching'].includes(s.step)) && <TypingIndicator />
              )}
            </div>
          )}

          {confirmAction && (
            <ConfirmActionCard
              action={confirmAction}
              conversationId={convId}
              sessionId={chatSessionIdRef.current}
              onComplete={(result) => {
                setConfirmAction(null);
                // Add result as a message
                const message = result?.data?.message || result?.message;
                if (message) {
                  const resultId = `confirm-res-${Date.now()}`;
                  setMessages(prev => [...prev, {
                    id: resultId,
                    role: 'assistant',
                    content: message,
                    created_at: new Date().toISOString(),
                  }]);
                }
              }}
            />
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>
      <InputBar onSend={handleSend} disabled={streaming || tokenExhausted} isDark={isDark} />
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        padding: '0 24px 4px', zIndex: 39, pointerEvents: 'auto',
      }}>
        <TokenBudgetBar
          used={tokenUsed}
          limit={tokenLimit}
          canRecharge={tokenCanRecharge}
          onRecharge={handleRecharge}
          selfRechargeEnabled={tokenSelfRechargeEnabled}
        />
      </div>
    </div>
  );
}
