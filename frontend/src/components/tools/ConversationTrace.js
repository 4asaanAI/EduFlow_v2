/**
 * R11.5 — Conversation Trace Viewer (Owner-only support/diagnostics).
 *
 * Lets the school owner answer one question: "Did the assistant reply to this
 * conversation, and if not, why?" Paste a conversation id, load its per-turn
 * trace, and see for each turn the outcome (answered / fallback / error /
 * unavailable), the tools it used, the finish reason, token usage, and any
 * error type. This is a read-only diagnostics surface — it never changes data.
 */
import React, { useState, useCallback } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { ToolPage } from './ToolPage';
import {
  Search, MessageSquare, CheckCircle2, AlertTriangle, XCircle, CloudOff,
  Wrench, Check, X, Info,
} from 'lucide-react';
import { getConversationTrace } from '../../lib/api';

const tint = (color, amount) => `color-mix(in srgb, ${color} ${amount}%, transparent)`;

// Outcome → colour + icon + human label. Green = answered, amber = fallback,
// red = error / unavailable (the assistant did not deliver a real reply).
const OUTCOME_META = {
  answered:    { color: '#34d399', icon: CheckCircle2,  label: 'Answered' },
  fallback:    { color: '#facc15', icon: AlertTriangle, label: 'Fallback' },
  error:       { color: '#f87171', icon: XCircle,       label: 'Error' },
  unavailable: { color: '#f87171', icon: CloudOff,      label: 'Unavailable' },
};

function outcomeMeta(outcome) {
  return OUTCOME_META[outcome] || { color: '#888', icon: Info, label: outcome || 'Unknown' };
}

function OutcomeBadge({ outcome }) {
  const { color, icon: Icon, label } = outcomeMeta(outcome);
  return (
    <span
      data-testid={`trace-outcome-${outcome}`}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px',
        borderRadius: 7, fontSize: 12, fontWeight: 700,
        background: tint(color, 12), color, border: `1px solid ${tint(color, 30)}`,
      }}
    >
      <Icon size={13} /> {label}
    </span>
  );
}

function ToolChip({ tool, isDark }) {
  const ok = tool.status === 'done' || tool.status === 'ok' || tool.status === 'success';
  const color = ok ? '#34d399' : '#f87171';
  const StatusIcon = ok ? Check : X;
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const text = isDark ? '#d4d4d4' : '#404040';
  return (
    <span
      data-testid="trace-tool-chip"
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 8px',
        borderRadius: 6, fontSize: 11, fontWeight: 600,
        background: isDark ? '#1a1a1a' : '#fafafa', border: `1px solid ${border}`, color: text,
      }}
    >
      <Wrench size={11} color="#888" />
      {tool.tool}
      <StatusIcon size={11} color={color} />
    </span>
  );
}

function TraceTurn({ turn, index, isDark }) {
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#737373';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const card = isDark ? '#1e1e1e' : '#fff';
  const meta = outcomeMeta(turn.outcome);
  const when = turn.created_at ? String(turn.created_at).slice(0, 19).replace('T', ' ') : '—';
  const tools = Array.isArray(turn.tools) ? turn.tools : [];

  return (
    <div
      data-testid="trace-turn"
      style={{
        background: card, border: `1px solid ${border}`, borderLeft: `3px solid ${meta.color}`,
        borderRadius: 10, padding: '12px 16px', marginBottom: 10,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: muted, fontWeight: 700 }}>#{index + 1}</span>
          <OutcomeBadge outcome={turn.outcome} />
          <span style={{ fontSize: 12, color: muted }}>{when}</span>
        </div>
        {turn.assistant && (
          <span style={{ fontSize: 11, color: muted, fontWeight: 600 }}>{turn.assistant}</span>
        )}
      </div>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 10, fontSize: 12, color: muted }}>
        {turn.finish_reason && (
          <span><span style={{ fontWeight: 600, color: text }}>Finish:</span> {turn.finish_reason}</span>
        )}
        {(turn.tokens !== undefined && turn.tokens !== null) && (
          <span><span style={{ fontWeight: 600, color: text }}>Tokens:</span> {turn.tokens}</span>
        )}
        {turn.language && (
          <span><span style={{ fontWeight: 600, color: text }}>Language:</span> {turn.language}</span>
        )}
        {turn.error_type && (
          <span style={{ color: '#f87171', fontWeight: 600 }}>Error: {turn.error_type}</span>
        )}
      </div>

      {tools.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
          {tools.map((t, i) => <ToolChip key={i} tool={t} isDark={isDark} />)}
        </div>
      )}
    </div>
  );
}

export default function ConversationTrace() {
  const { isDark } = useTheme();
  const [convId, setConvId] = useState('');
  const [turns, setTurns] = useState(null);   // null = not loaded yet
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#737373';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';

  const load = useCallback(async () => {
    const id = convId.trim();
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getConversationTrace(id);
      if (res && res.success) {
        setTurns(res.data || []);
      } else {
        setTurns(null);
        setError((res && res.detail) || 'Could not load the trace for that conversation.');
      }
    } catch {
      setTurns(null);
      setError('Could not load the trace for that conversation.');
    } finally {
      setLoading(false);
    }
  }, [convId]);

  const onKeyDown = (e) => { if (e.key === 'Enter') load(); };

  return (
    <ToolPage
      title="Conversation Trace"
      subtitle="Support & diagnostics: check whether the assistant replied to a conversation, and if not, why."
      loading={loading}
    >
      {/* One-line explanation */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, fontSize: 12, color: muted }}>
        <Info size={14} color="#4f8ff7" />
        Read-only view. Paste a conversation id to see each turn&apos;s outcome, tools used, and any error.
      </div>

      {/* Input row */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 220 }}>
          <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: muted }} />
          <input
            data-testid="trace-conv-id-input"
            value={convId}
            onChange={e => setConvId(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Conversation id"
            style={{
              width: '100%', background: 'var(--c-input)', border: `1px solid ${border}`,
              borderRadius: 9, padding: '9px 12px 9px 34px', color: text, fontSize: 13,
              boxSizing: 'border-box', outline: 'none',
            }}
          />
        </div>
        <button
          data-testid="trace-load-btn"
          onClick={load}
          disabled={loading || !convId.trim()}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, padding: '9px 18px',
            background: '#4f8ff7', color: '#fff', border: 'none', borderRadius: 9,
            fontSize: 13, fontWeight: 600, cursor: (loading || !convId.trim()) ? 'default' : 'pointer',
            opacity: (loading || !convId.trim()) ? 0.55 : 1,
          }}
        >
          <Search size={14} /> Load trace
        </button>
      </div>

      {error && (
        <div data-testid="trace-error" style={{ color: '#f87171', fontSize: 13, marginBottom: 16 }}>{error}</div>
      )}

      {/* Results */}
      {loading ? (
        <div style={{ color: muted, textAlign: 'center', padding: 40, fontSize: 13 }}>Loading trace...</div>
      ) : turns === null ? (
        <div data-testid="trace-empty" style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: '48px 20px', gap: 12, color: muted, textAlign: 'center',
        }}>
          <MessageSquare size={30} color={muted} />
          <div style={{ fontSize: 14, fontWeight: 600, color: text }}>No conversation loaded</div>
          <div style={{ fontSize: 13, maxWidth: 380 }}>
            Enter a conversation id above and press “Load trace” to see every turn and whether the assistant replied.
          </div>
        </div>
      ) : turns.length === 0 ? (
        <div data-testid="trace-empty" style={{ color: muted, textAlign: 'center', padding: 40, fontSize: 13 }}>
          No turns found for this conversation.
        </div>
      ) : (
        <div data-testid="trace-timeline">
          <p style={{ fontSize: 11, fontWeight: 600, color: muted, margin: '0 0 12px', letterSpacing: '0.06em' }}>
            {turns.length} TURN{turns.length === 1 ? '' : 'S'}
          </p>
          {turns.map((turn, i) => (
            <TraceTurn key={turn.message_id || i} turn={turn} index={i} isDark={isDark} />
          ))}
        </div>
      )}
    </ToolPage>
  );
}
