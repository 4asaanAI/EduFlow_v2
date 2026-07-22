import React, { useState } from 'react';
import DOMPurify from 'dompurify';
import { useTheme } from '../contexts/ThemeContext';
import { ThumbsUp, ThumbsDown, Download, FileText } from 'lucide-react';
import BotMascot from './ui/BotMascot';
import { emitFeedback } from '../lib/api';

/**
 * A file Flo made, as something you can tap (Epic 10, Story 10.3).
 *
 * The download link is presigned and EXPIRES. An old conversation therefore holds
 * dead links, and a tap that silently fails is Epic 4's defect — a failure that
 * looks like nothing happening — in a new place. So the card says how to get a
 * fresh one, and only the link itself is trusted to the block: the file name and
 * type are rendered as TEXT, never as markup.
 */
export function GeneratedFile({ block }) {
  const name = String(block?.file_name || 'document');
  const type = String(block?.doc_type || '').toUpperCase();
  const sizeKb = Number(block?.size_kb || 0);
  const url = String(block?.download_url || '');
  // Only http(s) is followed. A javascript: or data: URL in an AI-authored block
  // would otherwise become a click target.
  const safeUrl = /^https?:\/\//i.test(url) ? url : '';

  return (
    <div
      data-testid="generated-file"
      style={{
        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg, 12px)',
        background: 'var(--color-surface)', padding: '12px 14px', margin: '10px 0',
      }}
    >
      <FileText size={20} aria-hidden="true" style={{ color: 'var(--color-text-secondary)', flexShrink: 0 }} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-text-primary)', wordBreak: 'break-word' }}>
          {name}
        </div>
        {/* The type is stated in TEXT, not by icon colour alone (WCAG). */}
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
          {type}{sizeKb > 0 ? ` · ${sizeKb} KB` : ''}
        </div>
      </div>
      {safeUrl ? (
        <a
          href={safeUrl}
          download={name}
          rel="noopener noreferrer"
          data-testid="generated-file-download"
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '8px 14px', borderRadius: 'var(--radius-md, 10px)',
            background: 'var(--brand-blue-fill, #4f8ff7)', color: 'var(--on-brand-blue, #fff)',
            fontSize: 13, fontWeight: 600, textDecoration: 'none', flexShrink: 0,
          }}
        >
          <Download size={14} aria-hidden="true" />
          Download
        </a>
      ) : (
        <span data-testid="generated-file-expired" style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
          This link has expired. Ask for the file again.
        </span>
      )}
    </div>
  );
}

// FL (R8.4 AC3): the previous `FORBID_ATTR: ['style']` stripped the renderer's
// OWN inline styling, so AI markdown rendered as unstyled plain text. Rather than
// ALLOW `style` (which would let AI-authored content inject a dangerous style
// value — DOMPurify does NOT reliably neutralize `url(javascript:...)` under
// jsdom), the markdown functions below emit BARE tags and rely on the existing
// `.prose-chat` CSS (theme-aware element selectors in index.css) for styling.
// The sanitizer stays strict: it drops every style/class/event attr (so AI
// content can't borrow theme CSS or spoof the UI), restricts tags to the safe
// set the renderer emits (no script/iframe/img/span), keeps the href/target/rel
// that links need, and constrains link protocols.
const MARKDOWN_SANITIZE_CONFIG = {
  ALLOWED_TAGS: ['h2', 'h3', 'h4', 'p', 'ul', 'ol', 'li', 'hr', 'br', 'strong',
    'em', 'code', 'pre', 'a', 'table', 'thead', 'tbody', 'tr', 'th', 'td'],
  ALLOWED_ATTR: ['href', 'target', 'rel'],
  ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|tel:|\/)/i,
};

function parseMarkdownText() {
  return function(text) {
    if (!text) return '';
    const lines = text.split('\n');
    let result = '';
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (line.includes('|') && line.trim().startsWith('|')) {
        const tableLines = [];
        while (i < lines.length && lines[i].includes('|') && lines[i].trim().startsWith('|')) {
          tableLines.push(lines[i]); i++;
        }
        result += renderTable(tableLines);
        continue;
      }
      if (line.startsWith('### ')) {
        result += `<h4>${processInline(line.slice(4))}</h4>`;
      } else if (line.startsWith('## ')) {
        result += `<h3>${processInline(line.slice(3))}</h3>`;
      } else if (line.startsWith('# ')) {
        result += `<h2>${processInline(line.slice(2))}</h2>`;
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        result += `<li>${processInline(line.slice(2))}</li>`;
      } else if (line.match(/^\d+\.\s/)) {
        result += `<li>${processInline(line.replace(/^\d+\.\s/, ''))}</li>`;
      } else if (line.trim() === '---' || line.trim() === '***') {
        result += `<hr/>`;
      } else if (line.trim() === '') {
        result += '<br/>';
      } else {
        result += `<p>${processInline(line)}</p>`;
      }
      i++;
    }
    return result;
  };
}

function renderTable(lines) {
  const rows = lines.map(l => l.split('|').filter((_, i, a) => i > 0 && i < a.length - 1).map(c => c.trim()));
  const headers = rows[0] || [];
  const bodyRows = rows.filter((_, i) => i > 1);
  let html = '<table><thead><tr>';
  headers.forEach(h => { html += `<th>${h}</th>`; });
  html += '</tr></thead><tbody>';
  bodyRows.forEach((row) => {
    html += '<tr>';
    row.forEach(cell => { html += `<td>${processInline(cell)}</td>`; });
    html += '</tr>';
  });
  html += '</tbody></table>';
  return html;
}

function processInline(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    // FL (R8.4 AC3): emit a real href (was a hrefless, unclickable <a>). Only a
    // safe protocol survives here — DOMPurify's ALLOWED_URI_REGEXP is the backstop.
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, label, url) => {
      const clean = String(url).trim();
      const safe = /^(?:https?:\/\/|mailto:|tel:|\/)/i.test(clean);
      return safe
        ? `<a href="${clean}" target="_blank" rel="noopener noreferrer">${label}</a>`
        : label;
    });
}

function StatGrid({ stats }) {
  const { isDark } = useTheme();
  const colorMap = {
    green: { bg: isDark ? 'rgba(52,211,153,0.08)' : 'rgba(52,211,153,0.06)', text: '#34d399', border: isDark ? 'rgba(52,211,153,0.15)' : 'rgba(52,211,153,0.12)' },
    red: { bg: isDark ? 'rgba(248,113,113,0.08)' : 'rgba(248,113,113,0.06)', text: '#f87171', border: isDark ? 'rgba(248,113,113,0.15)' : 'rgba(248,113,113,0.12)' },
    blue: { bg: isDark ? 'rgba(79,143,247,0.08)' : 'rgba(79,143,247,0.06)', text: '#4f8ff7', border: isDark ? 'rgba(79,143,247,0.15)' : 'rgba(79,143,247,0.12)' },
    yellow: { bg: isDark ? 'rgba(251,191,36,0.08)' : 'rgba(251,191,36,0.06)', text: '#fbbf24', border: isDark ? 'rgba(251,191,36,0.15)' : 'rgba(251,191,36,0.12)' },
    purple: { bg: isDark ? 'rgba(167,139,250,0.08)' : 'rgba(167,139,250,0.06)', text: '#a78bfa', border: isDark ? 'rgba(167,139,250,0.15)' : 'rgba(167,139,250,0.12)' },
    default: { bg: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)', text: 'var(--text-primary)', border: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)' },
  };
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(stats.length, 4)}, 1fr)`, gap: 10, margin: '14px 0' }}>
      {stats.map((stat, i) => {
        const c = colorMap[stat.color] || colorMap.default;
        return (
          <div key={i} style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: 12, padding: '14px 16px' }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: c.text, lineHeight: 1.2, letterSpacing: '-0.02em' }}>{stat.value}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, fontWeight: 500, letterSpacing: '0.02em' }}>{stat.label}</div>
          </div>
        );
      })}
    </div>
  );
}

function RichDataTable({ title, headers, rows, isDark }) {
  const bg = isDark ? '#1e1e1e' : '#fff';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const rowBorder = isDark ? '#252525' : '#f5f5f5';
  const thBg = isDark ? '#1a1a1a' : '#fafafa';
  const tc = isDark ? '#a0a0a0' : '#525252';
  const hc = isDark ? '#f5f5f5' : '#171717';
  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 12, overflow: 'hidden', margin: '14px 0' }}>
      {title && <div style={{ padding: '10px 16px', borderBottom: `1px solid ${border}` }}><span style={{ fontWeight: 600, fontSize: 14, color: hc, letterSpacing: '-0.01em' }}>{title}</span></div>}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {headers.map((h, i) => <th key={i} style={{ padding: '8px 14px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: isDark ? '#737373' : '#525252', textTransform: 'uppercase', letterSpacing: '0.04em', background: thBg, borderBottom: `1px solid ${border}` }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} style={{ borderBottom: i < rows.length - 1 ? `1px solid ${rowBorder}` : 'none' }}>
                {row.map((cell, j) => (
                  <td key={j} style={{ padding: '9px 14px', fontSize: 13, color: typeof cell === 'string' && cell.startsWith('\u20B9') ? '#fbbf24' : tc }}>
                    {typeof cell === 'object' ? cell : String(cell ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AlertsList({ items, isDark }) {
  const typeStyles = {
    warning: { bg: isDark ? 'rgba(251,191,36,0.06)' : 'rgba(251,191,36,0.05)', border: isDark ? 'rgba(251,191,36,0.15)' : 'rgba(251,191,36,0.12)', text: isDark ? '#fcd34d' : '#b45309' },
    critical: { bg: isDark ? 'rgba(248,113,113,0.06)' : 'rgba(248,113,113,0.05)', border: isDark ? 'rgba(248,113,113,0.15)' : 'rgba(248,113,113,0.12)', text: isDark ? '#fca5a5' : '#dc2626' },
    success: { bg: isDark ? 'rgba(52,211,153,0.06)' : 'rgba(52,211,153,0.05)', border: isDark ? 'rgba(52,211,153,0.15)' : 'rgba(52,211,153,0.12)', text: isDark ? '#6ee7b7' : '#059669' },
    info: { bg: isDark ? 'rgba(79,143,247,0.06)' : 'rgba(79,143,247,0.05)', border: isDark ? 'rgba(79,143,247,0.15)' : 'rgba(79,143,247,0.12)', text: isDark ? '#93c5fd' : '#2563eb' },
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, margin: '12px 0' }}>
      {items.map((item, i) => {
        const s = typeStyles[item.type] || typeStyles.info;
        return (
          <div key={i} style={{ background: s.bg, border: `1px solid ${s.border}`, borderRadius: 10, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: s.text, flexShrink: 0 }} />
            <span style={{ fontSize: 13, color: s.text, lineHeight: 1.4 }}>{item.text}</span>
          </div>
        );
      })}
    </div>
  );
}

function ActionButtons({ buttons, onActionButton, isDark }) {
  const safeButtons = (buttons || []).filter(btn => btn && btn.label && btn.action);
  if (safeButtons.length === 0) return null;

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 14 }}>
      {safeButtons.map((btn, i) => (
        <button key={i} data-testid={`action-btn-${btn.action || i}`}
          onClick={() => onActionButton && onActionButton(btn.action, btn.params || {}, btn.label)}
          style={{
            background: isDark ? '#252525' : '#f5f5f5',
            border: `1px solid ${isDark ? '#333' : '#e5e5e5'}`,
            borderRadius: 10, padding: '8px 16px', color: '#4f8ff7', fontSize: 13,
            cursor: 'pointer', fontWeight: 500, transition: 'all var(--transition-fast)',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = '#4f8ff7'; e.currentTarget.style.background = isDark ? '#2a2a2a' : '#edf2ff'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = isDark ? '#333' : '#e5e5e5'; e.currentTarget.style.background = isDark ? '#252525' : '#f5f5f5'; }}
        >{btn.label}</button>
      ))}
    </div>
  );
}

function getToolCount(call) {
  const result = call?.result;
  if (!result || typeof result !== 'object') return null;
  if (result.meta && typeof result.meta.count === 'number') return result.meta.count;
  if (Array.isArray(result.data)) return result.data.length;
  if (typeof result.total === 'number') return result.total;
  if (typeof result.count === 'number') return result.count;
  return null;
}

function FeedbackButtons({ message, isDark }) {
  const [voted, setVoted] = useState(null);
  const [showReason, setShowReason] = useState(false);
  const [reason, setReason] = useState('');
  // R10.2 AC1: send the turn context so feedback is attributable + tool-aware.
  const meta = () => ({
    message_id: message.id,
    conversation_id: message.conversation_id || undefined,
    tool_names: (message.tool_calls || message.toolCalls || [])
      .map(c => c && c.tool).filter(Boolean),
  });
  const sendHelpful = async () => { setVoted(1); await emitFeedback(1, meta()); };
  // R10.2 AC2: "Improve" opens an optional one-line reason before sending.
  const sendImprove = async () => {
    setVoted(0);
    setShowReason(false);
    await emitFeedback(0, { ...meta(), reason: reason.trim() || undefined });
  };
  const btnStyle = (isActive) => ({
    display: 'flex', alignItems: 'center', gap: 4,
    padding: '6px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
    background: isActive ? (isDark ? 'rgba(79,143,247,0.15)' : 'rgba(79,143,247,0.1)') : (isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)'),
    color: isActive ? '#4f8ff7' : (isDark ? '#888' : '#888'),
    fontSize: 12, fontWeight: 500, transition: 'all 0.2s',
  });
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        <button data-testid="feedback-helpful" onClick={sendHelpful} disabled={voted !== null} style={{ ...btnStyle(voted === 1), opacity: voted !== null && voted !== 1 ? 0.5 : 1 }}>
          <ThumbsUp size={14} /> Helpful
        </button>
        <button data-testid="feedback-improve" onClick={() => (voted === null && setShowReason(s => !s))} disabled={voted !== null} style={{ ...btnStyle(voted === 0), opacity: voted !== null && voted !== 0 ? 0.5 : 1 }}>
          <ThumbsDown size={14} /> Improve
        </button>
      </div>
      {showReason && voted === null && (
        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
          <input
            data-testid="feedback-reason"
            value={reason}
            onChange={e => setReason(e.target.value)}
            maxLength={500}
            placeholder="Optional: what could be better?"
            style={{
              flex: 1, fontSize: 12, padding: '6px 10px', borderRadius: 6,
              border: `1px solid ${isDark ? '#333' : '#e5e5e5'}`,
              background: isDark ? '#1e1e1e' : '#fff', color: isDark ? '#f5f5f5' : '#171717',
            }}
          />
          <button data-testid="feedback-reason-send" onClick={sendImprove} style={{ ...btnStyle(false), background: '#4f8ff7', color: '#fff' }}>Send</button>
        </div>
      )}
    </div>
  );
}

function ToolTraceSummary({ calls, recalledMemories, isDark }) {
  const validCalls = (calls || []).filter(call => call?.tool);
  // R10.4 AC2: recalled memories are disclosed in the same "Data used" footer.
  // Require text — a ref with no text is nothing to disclose to the user.
  const memories = (recalledMemories || []).filter(m => m && m.text);
  if (validCalls.length === 0 && memories.length === 0) return null;

  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const muted = isDark ? '#888' : '#525252';
  const text = isDark ? '#d4d4d4' : '#525252';

  const parts = [];
  if (validCalls.length) parts.push(`${validCalls.length} tool${validCalls.length === 1 ? '' : 's'}`);
  if (memories.length) parts.push(`${memories.length} remembered note${memories.length === 1 ? '' : 's'}`);
  const summaryLabel = `Data used · ${parts.join(' · ')}`;

  return (
    <details data-testid="data-used" style={{
      marginTop: 12,
      border: `1px solid ${border}`,
      borderRadius: 10,
      background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)',
      overflow: 'hidden',
    }}>
      <summary style={{
        listStyle: 'none',
        cursor: 'pointer',
        padding: '8px 11px',
        fontSize: 11,
        fontWeight: 600,
        color: muted,
        userSelect: 'none',
      }}>
        {summaryLabel}
      </summary>
      <div style={{ borderTop: `1px solid ${border}`, padding: '8px 11px', display: 'grid', gap: 6 }}>
        {memories.length > 0 && (
          <div data-testid="recalled-memories" style={{ display: 'grid', gap: 4 }}>
            {memories.map((m, i) => (
              <div key={`mem-${m.id || i}`} style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                <span style={{ color: '#a78bfa', fontSize: 11, flexShrink: 0 }}>🧠 remembered</span>
                <span style={{
                  minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  color: text, fontSize: 11,
                }}>
                  {m.text}
                </span>
              </div>
            ))}
          </div>
        )}
        {validCalls.map((call, i) => {
          const count = getToolCount(call);
          return (
            <div key={`${call.tool}-${i}`} style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 10,
              minWidth: 0,
            }}>
              <code style={{
                minWidth: 0,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                color: '#4f8ff7',
                fontSize: 11,
                fontFamily: 'JetBrains Mono, monospace',
              }}>
                {call.tool}
              </code>
              <span style={{ color: text, fontSize: 11, flexShrink: 0 }}>
                {count == null ? 'completed' : `${count} record${count === 1 ? '' : 's'}`}
              </span>
            </div>
          );
        })}
      </div>
    </details>
  );
}

export default function MessageRenderer({ message, isStreaming, onActionButton }) {
  const { isDark } = useTheme();
  const isUser = message.role === 'user';
  const isAction = message.isAction;

  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 20 }}>
        <div data-testid={isAction ? undefined : 'user-message'}
          style={{
            background: isDark
              ? (isAction ? '#1e1e1e' : '#2a2a2a')
              : (isAction ? '#f5f5f5' : '#171717'),
            borderRadius: 18, padding: '10px 16px', maxWidth: '80%',
            color: isDark
              ? (isAction ? '#888' : '#f5f5f5')
              : (isAction ? '#525252' : '#ffffff'),
            fontSize: 14, lineHeight: 1.6, fontStyle: isAction ? 'italic' : 'normal',
            border: isAction ? `1px solid ${isDark ? '#2e2e2e' : '#e5e5e5'}` : 'none',
          }}>
          {message.content}
        </div>
      </div>
    );
  }

  const richBlocks = message.richBlocks || message.rich_content?.rich_blocks || [];
  const actionButtons = message.actionButtons || message.rich_content?.action_buttons || message.actions || [];
  const markdownFn = parseMarkdownText(isDark);

  return (
    <div data-testid="assistant-message" style={{ display: 'flex', gap: 14, marginBottom: 24, alignItems: 'flex-start' }}>
      {/* Flo's face, not a generic sparkle (Abhimanyu, 2026-07-22). The assistant
          has a name and a face; a star said "some AI wrote this". */}
      <div style={{
        width: 28, height: 28, borderRadius: 8, flexShrink: 0,
        background: 'linear-gradient(135deg, rgba(79,143,247,0.12), rgba(167,139,250,0.12))',
        display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
      }}>
        <BotMascot variant="avatar" size={24} data-testid="flo-avatar" />
      </div>
      <div style={{ flex: 1, minWidth: 0, paddingTop: 2 }}>
        {message.content && (
          <div
            className="prose-chat"
            dangerouslySetInnerHTML={{
              // AI-authored markdown is converted to HTML before rendering. Strip
              // inline style and class hooks so generated content cannot borrow
              // theme CSS or event attributes to mislead the user.
              __html: DOMPurify.sanitize(markdownFn(message.content), MARKDOWN_SANITIZE_CONFIG),
            }}
          />
        )}
        {isStreaming && <span style={{ display: 'inline-block', width: 2, height: 16, background: '#a78bfa', marginLeft: 2, animation: 'cursorBlink 1s infinite' }} />}
        {richBlocks.map((block, i) => {
          if (block.type === 'stat_grid') return <StatGrid key={i} stats={block.stats} />;
          if (block.type === 'table') return <RichDataTable key={i} title={block.title} headers={block.headers} rows={block.rows} isDark={isDark} />;
          if (block.type === 'alerts') return <AlertsList key={i} items={block.items} isDark={isDark} />;
          if (block.type === 'file') return <GeneratedFile key={i} block={block} />;
          return null;
        })}
        {actionButtons?.length > 0 && <ActionButtons buttons={actionButtons} onActionButton={onActionButton} isDark={isDark} />}
        <ToolTraceSummary
          calls={message.tool_calls || message.toolCalls}
          recalledMemories={message.recalled_memories || message.recalledMemories}
          isDark={isDark}
        />
        <FeedbackButtons message={message} isDark={isDark} />
      </div>
    </div>
  );
}
