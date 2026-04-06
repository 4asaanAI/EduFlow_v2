import React from 'react';
import { useTheme } from '../contexts/ThemeContext';

// Theme-aware HTML generation — uses CSS variables instead of hardcoded dark colors
function parseMarkdownText(isDark) {
  const tp = isDark ? '#E2E8F0' : '#1E293B';
  const ts = isDark ? '#94A3B8' : '#475569';
  const hc = isDark ? '#fff' : '#0F172A';
  const bc = isDark ? '#222230' : '#E2E8F0';
  const codeBg = isDark ? '#1C1C28' : '#F1F5F9';
  const thBg = isDark ? '#0F0F1A' : '#F1F5F9';
  const rowBorder = isDark ? '#1A1A24' : '#E2E8F0';
  const tableBg = isDark ? '#161622' : '#fff';

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
        result += `<h4 style="color:${hc};font-family:Outfit,sans-serif;font-size:0.9rem;font-weight:600;margin:12px 0 5px">${processInline(line.slice(4), isDark)}</h4>`;
      } else if (line.startsWith('## ')) {
        result += `<h3 style="color:${hc};font-family:Outfit,sans-serif;font-size:1rem;font-weight:600;margin:14px 0 6px">${processInline(line.slice(3), isDark)}</h3>`;
      } else if (line.startsWith('# ')) {
        result += `<h2 style="color:${hc};font-family:Outfit,sans-serif;font-size:1.1rem;font-weight:700;margin:16px 0 8px">${processInline(line.slice(2), isDark)}</h2>`;
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        result += `<li style="margin-bottom:3px;color:${ts}">${processInline(line.slice(2), isDark)}</li>`;
      } else if (line.match(/^\d+\.\s/)) {
        result += `<li style="margin-bottom:3px;color:${ts}">${processInline(line.replace(/^\d+\.\s/, ''), isDark)}</li>`;
      } else if (line.trim() === '---' || line.trim() === '***') {
        result += `<hr style="border:none;border-top:1px solid ${bc};margin:10px 0"/>`;
      } else if (line.trim() === '') {
        result += '<br/>';
      } else {
        result += `<p style="margin-bottom:5px;color:${ts}">${processInline(line, isDark)}</p>`;
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
  let html = `<div style="overflow-x:auto;margin:10px 0;border-radius:8px;border:1px solid ${bc};background:${tableBg}"><table style="width:100%;border-collapse:collapse;font-size:12px">`;
  html += '<thead><tr>';
  headers.forEach(h => { html += `<th style="padding:7px 12px;text-align:left;font-size:10px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;background:${thBg};border-bottom:1px solid ${bc}">${h}</th>`; });
  html += '</tr></thead><tbody>';
  bodyRows.forEach((row, ri) => {
    html += `<tr style="border-bottom:${ri < bodyRows.length - 1 ? `1px solid ${rowBorder}` : 'none'}">`;
    row.forEach(cell => {
      const isAmt = cell.startsWith('₹');
      const color = isAmt ? '#F59E0B' : ts;
      html += `<td style="padding:7px 12px;font-size:12px;color:${color}">${processInline(cell, true)}</td>`;
    });
    html += '</tr>';
  });
  html += '</tbody></table></div>';
  return html;
}

function processInline(text, isDark) {
  const strongColor = isDark ? '#E2E8F0' : '#0F172A';
  const codeColor = '#a5b4fc';
  const codeBg = isDark ? '#1C1C28' : '#F1F5F9';
  return text
    .replace(/\*\*(.+?)\*\*/g, `<strong style="color:${strongColor};font-weight:600">$1</strong>`)
    .replace(/\*(.+?)\*/g, `<em>$1</em>`)
    .replace(/`(.+?)`/g, `<code style="font-family:JetBrains Mono,monospace;background:${codeBg};padding:2px 5px;border-radius:4px;font-size:0.85em;color:${codeColor}">$1</code>`)
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '<a style="color:#3B82F6">$1</a>');
}

function StatGrid({ stats }) {
  const colorMap = {
    green: { bg: 'rgba(16,185,129,0.1)', text: '#10B981', border: 'rgba(16,185,129,0.2)' },
    red: { bg: 'rgba(239,68,68,0.1)', text: '#EF4444', border: 'rgba(239,68,68,0.2)' },
    blue: { bg: 'rgba(59,130,246,0.1)', text: '#60A5FA', border: 'rgba(59,130,246,0.2)' },
    yellow: { bg: 'rgba(245,158,11,0.1)', text: '#F59E0B', border: 'rgba(245,158,11,0.2)' },
    purple: { bg: 'rgba(139,92,246,0.1)', text: '#A78BFA', border: 'rgba(139,92,246,0.2)' },
    default: { bg: 'rgba(255,255,255,0.05)', text: '#E2E8F0', border: 'rgba(255,255,255,0.1)' },
  };
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(stats.length, 4)}, 1fr)`, gap: 10, margin: '12px 0' }}>
      {stats.map((stat, i) => {
        const c = colorMap[stat.color] || colorMap.default;
        return (
          <div key={i} style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: 10, padding: '12px 14px' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: c.text, fontFamily: 'Outfit, sans-serif', lineHeight: 1.2 }}>{stat.value}</div>
            <div style={{ fontSize: 10, color: '#64748B', marginTop: 3, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>{stat.label}</div>
          </div>
        );
      })}
    </div>
  );
}

function RichDataTable({ title, headers, rows, isDark }) {
  const bg = isDark ? '#161622' : '#fff';
  const border = isDark ? '#222230' : '#E2E8F0';
  const rowBorder = isDark ? '#1A1A24' : '#F1F5F9';
  const thBg = isDark ? '#0F0F1A' : '#F8F9FC';
  const tc = isDark ? '#94A3B8' : '#475569';
  const hc = isDark ? '#E2E8F0' : '#0F172A';
  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 10, overflow: 'hidden', margin: '12px 0' }}>
      {title && <div style={{ padding: '9px 14px', borderBottom: `1px solid ${border}` }}><span style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 600, fontSize: 13, color: hc }}>{title}</span></div>}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {headers.map((h, i) => <th key={i} style={{ padding: '7px 12px', textAlign: 'left', fontSize: 9.5, fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.06em', background: thBg, borderBottom: `1px solid ${border}` }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} style={{ borderBottom: i < rows.length - 1 ? `1px solid ${rowBorder}` : 'none' }}>
                {row.map((cell, j) => (
                  <td key={j} style={{ padding: '8px 12px', fontSize: 12, color: typeof cell === 'string' && cell.startsWith('₹') ? '#F59E0B' : tc }}>
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

function AlertsList({ items }) {
  const typeStyles = {
    warning: { icon: '⚠️', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)', text: '#FCD34D' },
    critical: { icon: '🔴', bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.2)', text: '#FCA5A5' },
    success: { icon: '✅', bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.2)', text: '#6EE7B7' },
    info: { icon: 'ℹ️', bg: 'rgba(59,130,246,0.08)', border: 'rgba(59,130,246,0.2)', text: '#93C5FD' },
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, margin: '10px 0' }}>
      {items.map((item, i) => {
        const s = typeStyles[item.type] || typeStyles.info;
        return (
          <div key={i} style={{ background: s.bg, border: `1px solid ${s.border}`, borderRadius: 8, padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12 }}>{s.icon}</span>
            <span style={{ fontSize: 12, color: s.text }}>{item.text}</span>
          </div>
        );
      })}
    </div>
  );
}

function ActionButtons({ buttons, onActionButton, isDark }) {
  const btnBg = isDark ? '#161622' : '#F1F5F9';
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
      {buttons.map((btn, i) => (
        <button key={i} data-testid={`action-btn-${btn.action || i}`}
          onClick={() => onActionButton && onActionButton(btn.action, btn.params || {}, btn.label)}
          style={{ background: btnBg, border: '1px solid #3B82F6', borderRadius: 7, padding: '7px 14px', color: '#93C5FD', fontSize: 12, cursor: 'pointer', fontWeight: 500, transition: 'all 0.15s' }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(59,130,246,0.15)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = btnBg; }}
        >{btn.label}</button>
      ))}
    </div>
  );
}

export default function MessageRenderer({ message, isStreaming, onActionButton }) {
  const { isDark } = useTheme();
  const isUser = message.role === 'user';
  const isAction = message.isAction;

  const userBg = isDark ? '#1C1C28' : '#EFF6FF';
  const userBorder = isDark ? '#222230' : '#BFDBFE';
  const userColor = isDark ? '#E2E8F0' : '#1E3A5F';
  const actionBg = isDark ? '#161622' : '#F8FAFF';
  const actionColor = isDark ? '#64748B' : '#94A3B8';

  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <div data-testid={isAction ? undefined : 'user-message'}
          style={{ background: isAction ? actionBg : userBg, border: `1px solid ${isAction ? (isDark ? '#222230' : '#E2E8F0') : userBorder}`, borderRadius: '14px 14px 3px 14px', padding: '9px 15px', maxWidth: '82%', color: isAction ? actionColor : userColor, fontSize: 13, lineHeight: 1.6, fontStyle: isAction ? 'italic' : 'normal' }}>
          {message.content}
        </div>
      </div>
    );
  }

  const richBlocks = message.richBlocks || message.rich_content?.rich_blocks || [];
  const actionButtons = message.actionButtons || message.rich_content?.action_buttons || message.actions || [];
  const markdownFn = parseMarkdownText(isDark);
  const avatarBg = isDark ? 'rgba(99,102,241,0.12)' : 'rgba(99,102,241,0.08)';
  const avatarBorder = isDark ? 'rgba(99,102,241,0.25)' : 'rgba(99,102,241,0.2)';

  return (
    <div data-testid="ai-message" style={{ display: 'flex', gap: 12, marginBottom: 22, alignItems: 'flex-start' }}>
      <div style={{ width: 30, height: 30, borderRadius: 8, flexShrink: 0, background: avatarBg, border: `1px solid ${avatarBorder}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Outfit, sans-serif', fontWeight: 700, fontSize: 10, color: '#818CF8', letterSpacing: '0.02em' }}>AI</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {message.content && (
          <div className="prose-chat" dangerouslySetInnerHTML={{ __html: markdownFn(message.content) }} />
        )}
        {isStreaming && <span style={{ display: 'inline-block', width: 2, height: 14, background: '#818CF8', marginLeft: 2, animation: 'pulse-dot 1s infinite' }} />}
        {richBlocks.map((block, i) => {
          if (block.type === 'stat_grid') return <StatGrid key={i} stats={block.stats} />;
          if (block.type === 'table') return <RichDataTable key={i} title={block.title} headers={block.headers} rows={block.rows} isDark={isDark} />;
          if (block.type === 'alerts') return <AlertsList key={i} items={block.items} />;
          return null;
        })}
        {actionButtons?.length > 0 && <ActionButtons buttons={actionButtons} onActionButton={onActionButton} isDark={isDark} />}
      </div>
    </div>
  );
}
