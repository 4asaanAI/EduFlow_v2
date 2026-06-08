import React from 'react';

// I.3: renders the two non-write "you're not stuck" follow-ups the assistant can
// return when it cannot proceed to a confirm card:
//   - disambiguation: a question with selectable candidate records. Picking one
//     sends its `value` back into the chat to continue the flow (no write).
//   - deeplink: a can't-complete fallback that links to the matching UI panel.
// No token is involved and nothing is written for either case.

// Parse the panel/tool id out of a deep-link URL like "/app?tool=fees".
export function toolFromDeepLink(url) {
  if (!url || typeof url !== 'string') return null;
  const q = url.indexOf('?');
  if (q === -1) return null;
  const params = new URLSearchParams(url.slice(q + 1));
  return params.get('tool') || null;
}

function labelForPanel(toolId) {
  if (!toolId) return 'the panel';
  const pretty = String(toolId).replace(/[-_]/g, ' ');
  return `the ${pretty} panel`;
}

export default function ChatFollowup({ followup, onPick, onOpenPanel, isDark }) {
  if (!followup) return null;

  const cardStyle = {
    border: `1px solid ${isDark ? '#2e2e2e' : '#e5e5e5'}`,
    background: isDark ? '#1e1e1e' : '#ffffff',
    borderRadius: 12,
    padding: '12px 14px',
    maxWidth: 420,
    marginTop: 4,
  };

  const btnBase = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '7px 12px',
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    border: `1px solid ${isDark ? '#3a3a3a' : '#d4d4d4'}`,
    background: isDark ? '#2a2a2a' : '#f5f5f5',
    color: isDark ? '#e5e5e5' : '#292524',
    cursor: 'pointer',
    textAlign: 'left',
  };

  if (followup.kind === 'disambiguation') {
    const options = Array.isArray(followup.options) ? followup.options.filter(Boolean) : [];
    // No candidates to pick from — the streamed assistant text already carries
    // the question; rendering an empty card would be a dead-end.
    if (options.length === 0) return null;
    return (
      <div style={cardStyle} data-testid="chat-disambiguation">
        <div style={{ fontSize: 13, lineHeight: 1.5, color: isDark ? '#e5e5e5' : '#1c1917', marginBottom: 10 }}>
          {followup.message || 'Which one did you mean?'}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {options.map((opt, i) => (
            <button
              key={opt.value != null ? `${opt.value}-${i}` : i}
              data-testid={`disambiguation-option-${i}`}
              onClick={() => onPick && onPick(opt)}
              style={btnBase}
            >
              {opt.label || opt.value}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (followup.kind === 'deeplink') {
    const toolId = toolFromDeepLink(followup.url);
    return (
      <div style={cardStyle} data-testid="chat-deeplink">
        <div style={{ fontSize: 13, lineHeight: 1.5, color: isDark ? '#e5e5e5' : '#1c1917', marginBottom: 10 }}>
          {followup.message || "I couldn't complete that here. You can finish it in the panel."}
        </div>
        <button
          data-testid="deeplink-open-panel"
          onClick={() => onOpenPanel && onOpenPanel(toolId)}
          style={{ ...btnBase, color: '#4f8ff7', fontWeight: 600 }}
        >
          Open {labelForPanel(toolId)}
        </button>
      </div>
    );
  }

  return null;
}
