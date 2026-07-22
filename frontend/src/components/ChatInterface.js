import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { apiFetch, createConversation, getBrowserSseSessionId, getMessages, sendMessageStream } from '../lib/api';
import MessageRenderer from './MessageRenderer';
import InputBar from './InputBar';
import TokenBudgetBar from './TokenBudgetBar';
import { executeTool } from '../lib/api';
import { getAuthHeaders } from '../lib/authSession';
import BotMascot from './ui/BotMascot';
import ThinkingProcess from './ThinkingProcess';
import ConfirmActionCard from './ConfirmActionCard';
import ChatFollowup from './ChatFollowup';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

/* Epic 5 (UX-DR8): ONE left edge and ONE vertical rhythm for everything stacked in a
   streaming turn. The gutter is the space the assistant avatar occupies — 28px wide
   plus the 14px flex gap — so a progress panel, a tool badge and the reply body all
   begin at the same place. Before this they began at 42px, 0px and 42px. */
export const STREAM_GUTTER = 42;
export const STREAM_GAP = 8;

/* How long silence is allowed before the person is told something. The server sends a
   keepalive every 5s, so 12s of TOTAL silence means the connection itself is suspect,
   not merely a slow answer. Any activity at all resets both.

   THESE TWO NUMBERS ARE JUDGEMENTS, NOT MEASUREMENTS. They were reasoned from the
   keepalive interval and have never been watched against a real connection at the
   school on a real morning — they look precise here and are not. Logged as D-32 and
   on Abhimanyu's checklist. If Flo nags on answers that were always going to arrive,
   raise the first; if people give up before it speaks, lower it. */
export const STALL_SLOW_MS = 12000;
export const STALL_DEAD_MS = 45000;
function getHeaders() {
  return getAuthHeaders();
}

async function executeAction(convId, action, params, label, user) {
  // FL (R8.4): route through apiFetch so a 401 gets one refresh + retry instead
  // of a raw fetch that would fail the action silently on an expired token.
  const res = await apiFetch(`${API}/chat/conversations/${convId}/action`, {
    method: 'POST', headers: getHeaders(user),
    body: JSON.stringify({ action, params, label }),
  });
  return res.json();
}

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', gap: 14, padding: '12px 0', alignItems: 'flex-start' }}>
      {/* Same face as every one of Flo's replies — it is Flo who is thinking. */}
      <div style={{
        width: 28, height: 28, borderRadius: 8,
        background: 'linear-gradient(135deg, rgba(79,143,247,0.15), rgba(167,139,250,0.15))',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, overflow: 'hidden',
      }}>
        <BotMascot variant="avatar" size={24} data-testid="flo-typing-avatar" />
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
      // Epic 4 / Story 4.2: attendance_rate reads "not marked yet" before anyone has
      // taken the register. `parseFloat(...) || 0` would score that as 0% attendance
      // — a school-is-empty verdict drawn from the absence of data, which is the
      // exact defect this epic removes. Unmarked attendance is excluded from the
      // score and its weight redistributed, rather than counted as a failure.
      const attMarked = d.attendance_marked_today !== false && !Number.isNaN(parseFloat(d.attendance_rate));
      const att = attMarked ? parseFloat(d.attendance_rate) : null;
      const fees = r.data?.fee_stats?.paid ? 75 : 50;
      const alerts = r.data?.active_alerts || 0;
      const base = att === null
        ? (fees * 0.8) + 20
        : (att * 0.4) + (fees * 0.4) + 20;
      const s = Math.max(0, Math.min(100, Math.round(base - (alerts * 5))));
      setScore(s);
    }).catch(() => {});
  }, [user.id]);

  if (score === null || (user.role !== 'owner' && user.role !== 'admin')) return null;
  const color = score >= 80 ? '#34d399' : score >= 60 ? '#fbbf24' : '#f87171';

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 14,
      background: 'var(--color-surface)',
      border: `1px solid ${'var(--color-border)'}`,
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
          background: 'var(--color-surface)',
          border: `1px solid ${'var(--color-border)'}`,
          borderRadius: 12, padding: '12px 14px', textAlign: 'left',
          color: 'var(--text-secondary)', fontSize: 13, cursor: 'pointer',
          transition: 'all var(--transition-fast)', lineHeight: 1.4,
        }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--color-text-muted)'; e.currentTarget.style.background = 'var(--color-surface-raised)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.background = 'var(--color-surface)'; }}>
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
  // FM4 (R8.2 AC2): the live stream message is mirrored in a ref so terminal
  // handlers can read the accumulated content and run side effects OUTSIDE a
  // setState updater (StrictMode double-invokes updaters).
  const streamMsgRef = useRef(null);
  // FH3 (R8.4 AC1): one-shot automatic reconnect budget for a transient drop.
  const autoRetryRef = useRef(0);

  // R8.1/R8.3: visible, recoverable failure surfaces (never silent).
  const [sendError, setSendError] = useState('');       // FH2 — couldn't start a turn
  const [loadError, setLoadError] = useState(false);     // FM3 — history load failed
  const [rechargeError, setRechargeError] = useState(''); // FH5 — checkout failed

  // New state variables for thinking, confirm action
  const [thinkingSteps, setThinkingSteps] = useState([]);
  const [thinkingCollapsed, setThinkingCollapsed] = useState(false);
  const [thinkingStartTime, setThinkingStartTime] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null); // {action_id, tool, params, display, buttons}
  const [followup, setFollowup] = useState(null); // I.3: {kind:'disambiguation'|'deeplink', message, options?, url?}

  // Token budget state
  const [tokenUsed, setTokenUsed] = useState(0);
  const [tokenLimit, setTokenLimit] = useState(-1); // -1 = unlimited
  const [tokenCanRecharge, setTokenCanRecharge] = useState(false);
  const [tokenSelfRechargeEnabled, setTokenSelfRechargeEnabled] = useState(true);
  const [tokenExhausted, setTokenExhausted] = useState(false);

  // Epic 5 / Story 5.2: the stall watchdog. Every detectable failure was already
  // handled by epic R8 — a dropped stream, a missing `done`, a 401. What was NOT
  // handled is a connection that is accepted and then goes quiet: `reader.read()`
  // waits forever and the typing dots animate with nothing behind them.
  const [stallState, setStallState] = useState(null);  // null | 'slow' | 'dead'
  const stallTimersRef = useRef([]);

  const clearStallWatch = useCallback(() => {
    stallTimersRef.current.forEach(clearTimeout);
    stallTimersRef.current = [];
    setStallState(null);
  }, []);

  /** Restart the watchdog. Called on send and on EVERY inbound event, so a long but
   *  genuinely-working answer is never declared stalled. */
  const noteStreamActivity = useCallback(() => {
    stallTimersRef.current.forEach(clearTimeout);
    setStallState(null);
    stallTimersRef.current = [
      setTimeout(() => setStallState('slow'), STALL_SLOW_MS),
      setTimeout(() => setStallState('dead'), STALL_DEAD_MS),
    ];
  }, []);

  // A timer outliving the component would fire against a dead one — that is where
  // "cannot update state on an unmounted component" and phantom banners come from.
  useEffect(() => () => stallTimersRef.current.forEach(clearTimeout), []);

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

  // FH4 (R8.2 AC1): wipe ALL turn-scoped UI state when the conversation changes,
  // so a stale confirm card / followup / error / half-streamed message from the
  // previous thread can't leak into (or post an action against) the new one.
  const resetTurnState = () => {
    setConfirmAction(null);
    setFollowup(null);
    setAiUnavailable(false);
    setAiUnavailableMessage('');
    setThinkingSteps([]);
    setThinkingCollapsed(false);
    setThinkingStartTime(null);
    setCurrentStreamMsg(null);
    setStreaming(false);
    setSendError('');
    setLoadError(false);
    setRechargeError('');
    streamMsgRef.current = null;
    pendingFinalMsgRef.current = null;
    autoRetryRef.current = 0;
    thinkingStartTimeRef.current = null;
    thinkingCollapsedRef.current = false;
    thinkingStepsRef.current = [];
  };

  useEffect(() => {
    if (convId) {
      if (justCreatedRef.current) {
        // The conversation was just created by an in-flight send — do NOT reset
        // or reload, that would abort the stream we just started.
        justCreatedRef.current = false;
        return;
      }
      processedMessageIds.current.clear();
      setMessages([]);
      resetTurnState();
      loadMessages(convId);
    } else {
      setMessages([]);
      processedMessageIds.current.clear();
      resetTurnState();
    }
  }, [convId, currentUser.id]); // eslint-disable-line react-hooks/exhaustive-deps

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
    // FH5 (R8.3 AC2): a failed checkout must NOT be swallowed — the user is stuck
    // with a disabled input otherwise. Surface an error + let them retry.
    setRechargeError('');
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
        return;
      }
      setRechargeError('Could not start checkout. Please try again.');
    } catch {
      setRechargeError('Could not start checkout — please check your connection and try again.');
    }
  };

  const loadMessages = async (id) => {
    // FM3 (R8.1 AC3): a failed history load must be distinguishable from an empty
    // conversation — show a retry affordance instead of a silent blank screen.
    setLoadError(false);
    try {
      const res = await getMessages(id, currentUser);
      if (res && res.success) {
        const msgs = res.data || [];
        msgs.forEach(m => processedMessageIds.current.add(m.id));
        setMessages(msgs);
      } else {
        setLoadError(true);
      }
    } catch {
      setLoadError(true);
    }
  };

  const handleSend = async (text, imageData = null, opts = {}) => {
    if (!text.trim() || streaming) return;
    const { skipUserBubble = false, forceCid = null } = opts;

    // A fresh user turn resets the one-shot auto-reconnect budget; a retry
    // (manual or automatic) preserves it so we can't loop forever.
    if (!skipUserBubble) autoRetryRef.current = 0;
    setSendError('');

    let cid = forceCid || convId;

    if (!cid) {
      // FH2 (R8.1 AC2): a failed createConversation must be VISIBLE and must not
      // eat the user's text. Return false so InputBar restores what was typed.
      let res;
      try {
        res = await createConversation(currentUser);
      } catch {
        setSendError("Couldn't start a new conversation — check your connection and try again.");
        return false;
      }
      if (!res || !res.success || !res.data?.id) {
        setSendError("Couldn't start a new conversation — please try again.");
        return false;
      }
      cid = res.data.id;
      justCreatedRef.current = true;
      setConvId(cid);
      onConvCreated(cid);
    }

    if (!skipUserBubble) {
      const tempId = `tmp-${Date.now()}`;
      const userMsg = { id: tempId, role: 'user', content: text, created_at: new Date().toISOString() };
      processedMessageIds.current.add(tempId);
      setMessages(prev => [...prev, userMsg]);
    }

    // Reset thinking state before starting SSE
    setThinkingSteps([]);
    setThinkingCollapsed(false);
    setThinkingStartTime(null);
    setConfirmAction(null);
    setFollowup(null);
    setAiUnavailable(false);
    setAiUnavailableMessage('');
    thinkingStartTimeRef.current = null;
    thinkingCollapsedRef.current = false;
    thinkingStepsRef.current = [];

    const initialStream = { id: 'streaming', role: 'assistant', content: '', toolCall: null, richBlocks: [], actionButtons: [] };
    streamMsgRef.current = initialStream;
    setStreaming(true);
    setCurrentStreamMsg(initialStream);

    // FM4 (R8.2 AC2): mutate the stream message via a ref + one setState — never
    // with side effects inside a state updater (StrictMode double-invokes them).
    const setStream = (next) => {
      streamMsgRef.current = next;
      setCurrentStreamMsg(next);
    };

    let streamErrored = false;
    let producedOutput = false;   // R1.2 AC2: did this turn render anything at all?
    // Story 5.2: start the clock the moment the turn begins, not on first token —
    // a request that is accepted and then never answered is the case being caught.
    noteStreamActivity();
    try {
      await sendMessageStream(cid, text, currentUser, (event) => {
        // ANY inbound event counts as life, including a keepalive and a thinking
        // step. A long but genuinely-working answer must never be called stalled.
        noteStreamActivity();
        const parsed = event;

        // R1.2 AC2: mark that the turn produced *something* user-visible. Purely
        // internal events (thinking/keepalive) don't count — if only those fire
        // and the stream then resolves, the post-await backstop shows a fallback.
        if (!['thinking', 'thinking_clear', 'keepalive'].includes(event.type)) {
          producedOutput = true;
        }

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
          {
            const prev = streamMsgRef.current;
            if (prev) setStream({ ...prev, content: (prev.content || '') + event.delta });
          }
        } else if (event.type === 'tool_call') {
          const prev = streamMsgRef.current;
          if (prev) setStream({ ...prev, toolCall: { tool: event.tool, status: event.status } });
        } else if (event.type === 'rich_blocks') {
          const prev = streamMsgRef.current;
          if (prev) setStream({ ...prev, richBlocks: event.blocks || [], actionButtons: event.action_buttons || [] });
        } else if (event.type === 'recalled_memories') {
          // R10.4 AC2: memories recalled into this reply — carried on the stream
          // message so the "Data used" footer discloses them (commits with `done`).
          const prev = streamMsgRef.current;
          if (prev) setStream({ ...prev, recalledMemories: event.memories || [] });
        } else if (event.type === 'confirm_action') {
          setConfirmAction(parsed);
        } else if (event.type === 'disambiguation') {
          // I.3: ambiguous match — show selectable candidates; no write, no token.
          setFollowup({ kind: 'disambiguation', message: parsed.message, options: parsed.options || [] });
        } else if (event.type === 'navigate') {
          // Legacy direct panel switch (tool_id), OR an E.6 can't-complete
          // fallback carrying a deep-link `url`. The deep-link is shown as a
          // clickable card (I.3) — never an automatic jump — so nothing moves
          // under the user after a dead-end.
          if (parsed.tool_id) {
            window.dispatchEvent(new CustomEvent('eduflow-navigate', { detail: { toolId: parsed.tool_id } }));
          } else if (parsed.url) {
            setFollowup({ kind: 'deeplink', message: parsed.message, url: parsed.url });
          }
        } else if (event.type === 'token_exhausted') {
          // Token budget exhausted — show recharge prompt and disable input
          setTokenExhausted(true);
          setTokenCanRecharge(!!event.can_recharge);
          fetchTokenUsage();
          // FM1 (R8.3 AC1): render a visible assistant bubble so the question
          // never just disappears when the budget runs out before any text.
          {
            const notice = event.can_recharge
              ? "You've reached your AI usage limit for now. Recharge from the bar below to keep chatting."
              : "You've reached your AI usage limit. Please ask your administrator to increase it.";
            const prev = streamMsgRef.current;
            setStream(null);
            setMessages(cur => {
              const out = [...cur];
              if (prev && prev.content) out.push({ ...prev, id: `ai-${Date.now()}`, role: 'assistant' });
              out.push({ id: `tok-${Date.now() + 1}`, role: 'assistant', content: notice, created_at: new Date().toISOString() });
              return out;
            });
            setStreaming(false);
          }
        } else if (event.type === 'ai_unavailable') {
          // Defensive: ensure message is always a plain string (never an object)
          const rawMsg = event.message;
          const message = typeof rawMsg === 'string' ? rawMsg : (rawMsg ? String(rawMsg) : 'AI is temporarily unavailable. Core school tools remain available.');
          setAiUnavailable(true);
          setAiUnavailableMessage(message);
          {
            const prev = streamMsgRef.current;
            setStream(prev
              ? { ...prev, content: message }
              : { id: `ai-unavail-${Date.now()}`, role: 'assistant', content: message, created_at: new Date().toISOString() });
          }
        } else if (event.type === 'keepalive') {
          // Ignore - just prevents SSE timeout
        } else if (event.type === 'error') {
          // R1.1 AC1: a turn-level error from the backend. Render an interrupted
          // assistant bubble (reusing the stream_error affordance) with the
          // server message + retry, so the user is never left staring at silence.
          streamErrored = true;
          setThinkingSteps([]);
          setThinkingCollapsed(false);
          const errText = (typeof event.message === 'string' && event.message)
            ? event.message
            : 'Flo hit a problem. Please try again.';
          {
            const prev = streamMsgRef.current;
            setStream(null);
            const interruptedId = `err-${Date.now()}`;
            if (prev?.content) {
              pendingFinalMsgRef.current = {
                ...prev, id: interruptedId, role: 'assistant',
                content: `${prev.content}\n\n${errText}`, interrupted: true,
              };
            } else {
              setMessages(current => [...current, {
                id: interruptedId, role: 'assistant', content: errText,
                interrupted: true, created_at: new Date().toISOString(),
              }]);
            }
          }
          setStreaming(false);
        } else if (event.type === 'stream_error') {
          streamErrored = true;
          setThinkingSteps([]);
          setThinkingCollapsed(false);
          // FH3 (R8.4 AC1): one automatic reconnect for a transient network drop,
          // then fall back to the manual Retry button.
          const transient = event.retryable && event.reason === 'stream_network_error';
          if (transient && autoRetryRef.current < 1) {
            autoRetryRef.current += 1;
            setStream(null);
            setMessages(prev => prev.filter(m => !(m.role === 'assistant' && m.interrupted)));
            setStreaming(false);
            setTimeout(() => { handleSend(text, imageData, { skipUserBubble: true, forceCid: cid }); }, 600);
            return;
          }
          {
            const prev = streamMsgRef.current;
            setStream(null);
            const interruptedId = `err-${Date.now()}`;
            const suffix = 'Connection lost. Tap retry.';
            if (prev?.content) {
              pendingFinalMsgRef.current = {
                ...prev, id: interruptedId, role: 'assistant',
                content: `${prev.content}\n\n${suffix}`, interrupted: true,
              };
            } else {
              setMessages(current => [...current, {
                id: interruptedId, role: 'assistant', content: suffix,
                interrupted: true, created_at: new Date().toISOString(),
              }]);
            }
          }
          setStreaming(false);
        } else if (event.type === 'done') {
          autoRetryRef.current = 0;  // a completed turn clears the reconnect budget
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
          // R1.2 AC3: finalize the streamed body whenever there is one — do NOT
          // gate on processedMessageIds (an id-only check silently dropped
          // streamed content, audit S10/FM2). The flush effect dedupes by id.
          // FM4: side effects run OUTSIDE the state updater (read from the ref).
          {
            const prev = streamMsgRef.current;
            setStream(null);
            if (prev) {
              processedMessageIds.current.add(messageId);
              pendingFinalMsgRef.current = { ...prev, id: messageId, role: 'assistant' };
            }
          }
          setStreaming(false);
        } else {
          // R1.1 AC2: an event type the client doesn't recognise — log it (for
          // telemetry / future compatibility) rather than dropping it silently.
          console.warn('unhandled SSE event', event.type, event);
        }
      }, chatSessionIdRef.current, imageData);
      if (streamErrored) return;
      // R1.2 AC2: terminal-state backstop (FM4: no side effects inside updaters).
      // If a live stream message is still open, finalize it; if the stream
      // resolved having produced nothing at all (a silent resolve — audit S12),
      // render the generic fallback so the turn is never blank.
      {
        const prev = streamMsgRef.current;
        if (prev) {
          const fallbackId = `ai-${Date.now()}`;
          processedMessageIds.current.add(fallbackId);
          pendingFinalMsgRef.current = { ...prev, id: fallbackId, role: 'assistant' };
          setStream(null);
        }
      }
      setStreaming(false);
      clearStallWatch();  // the turn is over; a live timer would fire at nothing
      // R8: flush a finalized message DIRECTLY here rather than depending only on
      // the streaming-transition effect. If every SSE frame (incl. `done`) arrived
      // in one React batch, `streaming` never committed `true`, so that effect sees
      // no transition and would otherwise silently drop the reply. Dedupe by id so
      // this and the effect can't double-append.
      if (pendingFinalMsgRef.current) {
        const finalMsg = pendingFinalMsgRef.current;
        pendingFinalMsgRef.current = null;
        setMessages(m => (m.some(x => x.id === finalMsg.id) ? m : [...m, finalMsg]));
      }
      if (!producedOutput && !pendingFinalMsgRef.current) {
        setMessages(cur => [...cur, {
          id: `ai-fallback-${Date.now()}`,
          role: 'assistant',
          content: "Flo couldn't produce a reply. Try again.",
          interrupted: true,
          created_at: new Date().toISOString(),
        }]);
      }
    } catch {
      // On SSE error: append "(Response interrupted)" and show Retry.
      // FM4: read the accumulated body from the ref; no side effects in updaters.
      const prev = streamMsgRef.current;
      setStream(null);
      if (prev && prev.content) {
        const interruptedId = `err-${Date.now()}`;
        processedMessageIds.current.add(interruptedId);
        pendingFinalMsgRef.current = {
          ...prev,
          id: interruptedId,
          role: 'assistant',
          content: prev.content + '\n\n*(Response interrupted)*',
          interrupted: true,
        };
      }
      setStreaming(false);
      clearStallWatch();
      // Finalize thinking on error
      setThinkingSteps(ts => ts.map(s => ({ ...s, status: 'done' })));
      // If there was no content at all, show a plain error message with retry
      if (!pendingFinalMsgRef.current) {
        setMessages(cur => [...cur, {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: 'Something went wrong. Please try again.',
          interrupted: true,
          created_at: new Date().toISOString(),
        }]);
      }
    }
  };

  const handleRetry = () => {
    // FL (R8.4 AC2): resend the last user turn WITHOUT stacking a duplicate user
    // bubble, and clear the interrupted error bubble(s) first.
    autoRetryRef.current = 0;
    let lastUserText = null;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') { lastUserText = messages[i].content; break; }
    }
    if (lastUserText == null) return;
    setMessages(prev => prev.filter(m => !(m.role === 'assistant' && m.interrupted)));
    handleSend(lastUserText, null, { skipUserBubble: true });
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
  const chatBg = 'var(--color-page)';

  return (
    // .chat-watermark paints The Aaryans' crest faintly behind the whole
    // conversation — see index.css. Applied here, on the chat shell shared by
    // every role, so it appears once for owner, principal, admin, teacher and
    // student alike rather than being added per profile.
    <div
      data-testid="chat-interface"
      className="chat-watermark"
      style={{
        display: 'flex', flexDirection: 'column', height: '100%',
        position: 'relative', background: chatBg,
        // The crest's path is handed to the stylesheet here rather than being
        // written into index.css. A url() in a stylesheet is resolved by
        // webpack at BUILD time, which fails for a file served from public/;
        // a custom property is passed straight through to the browser.
        '--chat-watermark-src': `url("${process.env.PUBLIC_URL}/aaryans-logo.jpg")`,
      }}
    >
      <div data-testid="messages-area" style={{ flex: 1, overflowY: 'auto', padding: '24px 0 200px' }}>
        <div data-testid="message-list" style={{ width: '100%', margin: '0 auto', padding: '0 32px' }}>
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
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
            }}>
              <span>{typeof aiUnavailableMessage === 'string' && aiUnavailableMessage ? aiUnavailableMessage : 'AI is temporarily unavailable. Core school tools remain available.'}</span>
              <button onClick={() => setAiUnavailable(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 16, lineHeight: 1, flexShrink: 0 }}>×</button>
            </div>
          )}

          {/* FM3 (R8.1 AC3): history load failed — distinct from an empty chat. */}
          {loadError && (
            <div data-testid="load-error-banner" style={{
              border: '1px solid var(--border)', background: 'var(--bg-card)',
              color: 'var(--text-primary)', borderRadius: 8, padding: '12px 14px',
              marginBottom: 16, fontSize: 13, lineHeight: 1.45,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
            }}>
              <span>Couldn't load this conversation's history.</span>
              <button onClick={() => loadMessages(convId)} style={{
                background: 'none', border: '1px solid var(--border)', borderRadius: 8,
                padding: '4px 12px', cursor: 'pointer', color: '#4f8ff7', fontSize: 12, fontWeight: 500, flexShrink: 0,
              }}>Retry</button>
            </div>
          )}

          {/* FH2 (R8.1 AC2): couldn't even start a turn — text was restored to input. */}
          {sendError && (
            <div data-testid="send-error-banner" style={{
              border: '1px solid var(--border)', background: 'var(--bg-card)',
              color: 'var(--text-primary)', borderRadius: 8, padding: '12px 14px',
              marginBottom: 16, fontSize: 13, lineHeight: 1.45,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
            }}>
              <span>{sendError}</span>
              <button onClick={() => setSendError('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 16, lineHeight: 1, flexShrink: 0 }}>×</button>
            </div>
          )}

          {isNewChat && (
            <div className="fade-in" style={{ textAlign: 'center', padding: '60px 0 40px' }}>
              {/* Epic 9: the generic sparkle chip became the marketing site's
                  robot — Flo now has one recognisable face across the website
                  and the product. Flo appears here, on the sign-in screen,
                  beside each reply, and on empty/error states — never on a
                  working screen. */}
              <div style={{ margin: '0 auto 10px', display: 'flex', justifyContent: 'center' }}>
                <BotMascot size={130} data-testid="assistant-mascot" />
              </div>
              <h2 style={{
                fontFamily: 'var(--font-display)',
                fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--text-primary)',
                marginBottom: 8, letterSpacing: '-0.02em',
              }}>
                Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, {currentUser.name.split(' ')[0]}
              </h2>
              {/* Flo says its own name here — this is where someone learns what to
                  call it, and it is the same name used everywhere else. */}
              <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-md)', marginBottom: 28, fontWeight: 500 }}>
                I'm Flo. How can I help you today?
              </p>
              <HealthScoreWidget user={currentUser} />
              <QuickActions onSend={handleSend} isDark={isDark} user={currentUser} />
            </div>
          )}

          {messages.map(msg => {
            // R1.2 AC1: a finalized assistant turn with no content, blocks, or
            // buttons must NOT be filtered out (that silent drop was the visible
            // half of the incident) — render a fallback line instead.
            if (msg.role === 'assistant') {
              const hasContent = msg.content && msg.content.trim();
              const richBlocks = msg.richBlocks || msg.rich_content?.rich_blocks || [];
              const actionButtons = msg.actionButtons || msg.rich_content?.action_buttons || msg.actions || [];
              if (!hasContent && richBlocks.length === 0 && actionButtons.length === 0) {
                return { ...msg, content: "Flo couldn't produce a reply. Try again." };
              }
            }
            return msg;
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

          {streaming && currentStreamMsg && (() => {
            // Epic 5 / Story 5.1. `thinkingSteps` already carries tool_start and
            // tool_done, so rendering ToolCallBadge alongside the panel announced
            // the SAME tool twice in two different shapes — owner item 12. The
            // panel is the single account of progress; the badge is the fallback
            // for when there is no panel to show.
            const hasProgressPanel = thinkingSteps.some(
              s => ['decision', 'tool_start', 'tool_done', 'searching'].includes(s.step)
            );
            return (
              <div className="fade-in" data-testid="chat-stream-block">
                {/* STREAM_GUTTER is the 42px the avatar occupies (28px + 14px gap).
                    Every stacked element shares it, so the progress panel, any badge
                    and the reply body have ONE left edge instead of three. */}
                {hasProgressPanel ? (
                  <div style={{ paddingLeft: STREAM_GUTTER, marginBottom: STREAM_GAP }} data-testid="chat-progress-panel">
                    <ThinkingProcess
                      steps={thinkingSteps}
                      isStreaming={streaming}
                      collapsed={thinkingCollapsed}
                      duration={thinkingStartTime ? Date.now() - thinkingStartTime : 0}
                    />
                  </div>
                ) : currentStreamMsg.toolCall ? (
                  <div style={{ paddingLeft: STREAM_GUTTER, marginBottom: STREAM_GAP }} data-testid="chat-tool-badge">
                    <ToolCallBadge tool={currentStreamMsg.toolCall.tool} status={currentStreamMsg.toolCall.status} />
                  </div>
                ) : null}
                {currentStreamMsg.content ? (
                  <div className="prose-chat">
                    <MessageRenderer message={{ ...currentStreamMsg, role: 'assistant' }} isStreaming onActionButton={handleActionButton} />
                  </div>
                ) : (
                  !hasProgressPanel && <TypingIndicator />
                )}
                {stallState && (
                  <div
                    role="status"
                    aria-live="polite"
                    data-testid="chat-stall-notice"
                    style={{
                      paddingLeft: STREAM_GUTTER, marginTop: STREAM_GAP,
                      fontSize: 13, color: 'var(--color-text-muted)',
                    }}
                  >
                    {stallState === 'slow'
                      ? 'Flo is taking longer than usual. Still working…'
                      : 'No response yet. The connection may have dropped — try sending it again.'}
                  </div>
                )}
              </div>
            );
          })()}

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

          {followup && (
            <ChatFollowup
              followup={followup}
              isDark={isDark}
              onPick={(opt) => {
                // Only dismiss the chooser once we actually have something to
                // send — otherwise a value-less option would leave a dead-end.
                if (opt && opt.value != null && String(opt.value).trim()) {
                  setFollowup(null);
                  handleSend(String(opt.value));
                }
              }}
              onOpenPanel={(toolId) => {
                setFollowup(null);
                if (toolId) {
                  window.dispatchEvent(new CustomEvent('eduflow-navigate', { detail: { toolId } }));
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
        {/* FH5 (R8.3 AC2): a failed checkout is shown here (not swallowed); the
            recharge button stays live so the user can retry — never a dead-end. */}
        {rechargeError && (
          <div data-testid="recharge-error" style={{
            width: '100%', margin: '0 auto 6px', fontSize: 12, color: '#f87171',
            textAlign: 'center',
          }}>{rechargeError}</div>
        )}
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
