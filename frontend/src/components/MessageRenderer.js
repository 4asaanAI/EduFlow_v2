import React from 'react';
import DOMPurify from 'dompurify';
import { useTheme } from '../contexts/ThemeContext';
import { Sparkles } from 'lucide-react';

const MARKDOWN_SANITIZE_CONFIG = {
  FORBID_ATTR: ['style', 'class', 'onerror', 'onload', 'onfocus'],
};

function parseMarkdownText(isDark) {
  const tp = isDark ? '#f5f5f5' : '#171717';
  const ts = isDark ? '#a0a0a0' : '#525252';
  const hc = isDark ? '#f5f5f5' : '#171717';
  const bc = isDark ? '#2e2e2e' : '#e5e5e5';
  const codeBg = isDark ? '#252525' : '#fafafa';
  const thBg = isDark ? '#1e1e1e' : '#fafafa';
  const rowBorder = isDark ? '#252525' : '#f0f0f0';
  const tableBg = isDark ? '#1e1e1e' : '#fff';

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
        result += renderTable(tableLines, { thBg, tableBg, bc, rowBorder, ts });
        continue;
      }
      if (line.startsWith('### ')) {
        result += `<h4 style="color:${hc};font-size:0.9rem;font-weight:600;margin:14px 0 6px;letter-spacing:-0.01em">${processInline(line.slice(4), isDark)}</h4>`;
      } else if (line.startsWith('## ')) {
        result += `<h3 style="color:${hc};font-size:1rem;font-weight:600;margin:16px 0 8px;letter-spacing:-0.01em">${processInline(line.slice(3), isDark)}</h3>`;
      } else if (line.startsWith('# ')) {
        result += `<h2 style="color:${hc};font-size:1.1rem;font-weight:700;margin:18px 0 8px;letter-spacing:-0.02em">${processInline(line.slice(2), isDark)}</h2>`;
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        result += `<li style="margin-bottom:4px;color:${ts};line-height:1.7">${processInline(line.slice(2), isDark)}</li>`;
      } else if (line.match(/^\d+\.\s/)) {
        result += `<li style="margin-bottom:4px;color:${ts};line-height:1.7">${processInline(line.replace(/^\d+\.\s/, ''), isDark)}</li>`;
      } else if (line.trim() === '---' || line.trim() === '***') {
        result += `<hr style="border:none;border-top:1px solid ${bc};margin:12px 0"/>`;
      } else if (line.trim() === '') {
        result += '<br/>';
      } else {
        result += `<p style="margin-bottom:6px;color:${ts};line-height:1.7">${processInline(line, isDark)}</p>`;
      }
      i++;
    }
    return result;
  };
}

function renderTable(lines, { thBg, tableBg, bc, rowBorder, ts }) {
  const rows = lines.map(l => l.split('|').filter((_, i, a) => i > 0 && i < a.length - 1).map(c => c.trim()));
  const headers = rows[0] || [];
  const bodyRows = rows.filter((_, i) => i > 1);
  let html = `<div style="overflow-x:auto;margin:12px 0;border-radius:10px;border:1px solid ${bc};background:${tableBg}"><table style="width:100%;border-collapse:collapse;font-size:13px">`;
  html += '<thead><tr>';
  headers.forEach(h => { html += `<th style="padding:8px 14px;text-align:left;font-size:11px;font-weight:600;color:#737373;text-transform:uppercase;letter-spacing:0.05em;background:${thBg};border-bottom:1px solid ${bc}">${h}</th>`; });
  html += '</tr></thead><tbody>';
  bodyRows.forEach((row, ri) => {
    html += `<tr style="border-bottom:${ri < bodyRows.length - 1 ? `1px solid ${rowBorder}` : 'none'}">`;
    row.forEach(cell => {
      const isAmt = cell.startsWith('\u20B9');
      const color = isAmt ? '#fbbf24' : ts;
      html += `<td style="padding:8px 14px;font-size:13px;color:${color}">${processInline(cell, true)}</td>`;
    });
    html += '</tr>';
  });
  html += '</tbody></table></div>';
  return html;
}

function processInline(text, isDark) {
  const strongColor = isDark ? '#f5f5f5' : '#171717';
  const codeColor = '#a78bfa';
  const codeBg = isDark ? '#252525' : '#f5f5f5';
  return text
    .replace(/\*\*(.+?)\*\*/g, `<strong style="color:${strongColor};font-weight:600">$1</strong>`)
    .replace(/\*(.+?)\*/g, `<em>$1</em>`)
    .replace(/`(.+?)`/g, `<code style="font-family:JetBrains Mono,monospace;background:${codeBg};padding:2px 6px;border-radius:5px;font-size:0.85em;color:${codeColor};border:1px solid ${isDark ? '#333' : '#e5e5e5'}">$1</code>`)
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '<a style="color:#4f8ff7">$1</a>');
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
              {headers.map((h, i) => <th key={i} style={{ padding: '8px 14px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: '#737373', textTransform: 'uppercase', letterSpacing: '0.04em', background: thBg, borderBottom: `1px solid ${border}` }}>{h}</th>)}
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

function ToolTraceSummary({ calls, isDark }) {
  const validCalls = (calls || []).filter(call => call?.tool);
  if (validCalls.length === 0) return null;

  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const muted = isDark ? '#737373' : '#a3a3a3';
  const text = isDark ? '#d4d4d4' : '#525252';

  return (
    <details style={{
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
        Data used · {validCalls.length} tool{validCalls.length === 1 ? '' : 's'}
      </summary>
      <div style={{ borderTop: `1px solid ${border}`, padding: '8px 11px', display: 'grid', gap: 6 }}>
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
              ? (isAction ? '#666' : '#f5f5f5')
              : (isAction ? '#a3a3a3' : '#ffffff'),
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
      <div style={{
        width: 28, height: 28, borderRadius: 8, flexShrink: 0,
        background: 'linear-gradient(135deg, rgba(79,143,247,0.12), rgba(167,139,250,0.12))',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Sparkles size={13} color="#a78bfa" />
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
          return null;
        })}
        {actionButtons?.length > 0 && <ActionButtons buttons={actionButtons} onActionButton={onActionButton} isDark={isDark} />}
        <ToolTraceSummary calls={message.tool_calls || message.toolCalls} isDark={isDark} />
      </div>
    </div>
  );
}
