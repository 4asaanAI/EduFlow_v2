import React, { useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';

/**
 * Formats a token count for display.
 * e.g. 47382 -> "47K", 1234567 -> "1.2M", 850 -> "850"
 */
function formatTokens(n) {
  if (n == null) return '0';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1_000) return Math.round(n / 1_000) + 'K';
  return String(n);
}

/**
 * Returns the bar color based on usage percentage.
 * green (<60%), yellow (60-80%), red (>80%)
 */
function barColor(pct) {
  if (pct > 0.80) return '#f87171';
  if (pct > 0.60) return '#fbbf24';
  return '#34d399';
}

const PACK_LIST = [
  { id: 'micro',    tokens: 50000,    price: 49,   label: '50K tokens' },
  { id: 'basic',    tokens: 200000,   price: 149,  label: '200K tokens' },
  { id: 'standard', tokens: 500000,   price: 349,  label: '500K tokens' },
  { id: 'power',    tokens: 1200000,  price: 699,  label: '1.2M tokens' },
  { id: 'school',   tokens: 3000000,  price: 1499, label: '3M tokens' },
];

/**
 * TokenBudgetBar — shown below the chat input bar.
 *
 * Props:
 *   used           : number — tokens used this month
 *   limit          : number — monthly limit (-1 = unlimited)
 *   canRecharge    : boolean — show recharge button when exhausted
 *   onRecharge     : (packId: string) => void — called when user picks a pack
 *   selfRechargeEnabled : boolean — whether self-recharge is allowed
 */
export default function TokenBudgetBar({ used = 0, limit = -1, canRecharge = false, onRecharge, selfRechargeEnabled = true }) {
  const { isDark } = useTheme();
  const [showPacks, setShowPacks] = useState(false);

  // Unlimited mode — either no budget configured or role limit is -1
  const isUnlimited = limit <= 0;
  const pct = isUnlimited ? 0 : Math.min(1, used / limit);
  const isExhausted = !isUnlimited && used >= limit;
  const color = isUnlimited ? '#34d399' : barColor(pct);

  const containerStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '6px 0 0',
    maxWidth: 760,
    margin: '0 auto',
    position: 'relative',
  };

  const barTrackStyle = {
    flex: 1,
    height: 4,
    borderRadius: 2,
    background: isDark ? '#2a2a2a' : '#e5e5e5',
    overflow: 'hidden',
    maxWidth: 120,
  };

  const barFillStyle = {
    height: '100%',
    borderRadius: 2,
    background: color,
    width: isUnlimited ? '0%' : `${Math.max(1, pct * 100)}%`,
    transition: 'width 0.4s ease, background 0.3s ease',
  };

  const labelStyle = {
    fontSize: 11,
    color: isExhausted ? '#f87171' : (isDark ? '#888' : '#525252'),
    fontWeight: isExhausted ? 600 : 400,
    whiteSpace: 'nowrap',
    fontFamily: 'Inter, -apple-system, sans-serif',
  };

  const rechargeButtonStyle = {
    fontSize: 11,
    fontWeight: 600,
    color: '#4f8ff7',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '2px 6px',
    borderRadius: 4,
    transition: 'background 0.15s ease',
  };

  const overlayStyle = {
    position: 'fixed',
    top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0,0,0,0.4)',
    zIndex: 9998,
    display: showPacks ? 'block' : 'none',
  };

  const dialogStyle = {
    position: 'fixed',
    bottom: 100,
    left: '50%',
    transform: 'translateX(-50%)',
    background: isDark ? '#1e1e1e' : '#ffffff',
    border: `1px solid ${isDark ? '#333' : '#e5e5e5'}`,
    borderRadius: 16,
    padding: '20px 24px',
    zIndex: 9999,
    boxShadow: isDark
      ? '0 12px 40px rgba(0,0,0,0.6)'
      : '0 12px 40px rgba(0,0,0,0.15)',
    width: 340,
    display: showPacks ? 'block' : 'none',
  };

  const dialogTitleStyle = {
    fontSize: 15,
    fontWeight: 700,
    color: isDark ? '#f5f5f5' : '#171717',
    marginBottom: 4,
  };

  const dialogSubStyle = {
    fontSize: 12,
    color: isDark ? '#888' : '#999',
    marginBottom: 14,
  };

  const packButtonStyle = (isLast) => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    width: '100%',
    padding: '10px 12px',
    background: isDark ? '#252525' : '#fafafa',
    border: `1px solid ${isDark ? '#333' : '#e5e5e5'}`,
    borderRadius: 10,
    cursor: 'pointer',
    marginBottom: isLast ? 0 : 8,
    transition: 'border-color 0.15s ease, background 0.15s ease',
  });

  const handlePackSelect = (packId) => {
    setShowPacks(false);
    if (onRecharge) onRecharge(packId);
  };

  // Label text
  let labelText;
  if (isUnlimited) {
    labelText = used > 0 ? `${formatTokens(used)} tokens used` : '';
  } else if (isExhausted) {
    labelText = 'Token limit reached';
  } else {
    labelText = `${formatTokens(used)} / ${formatTokens(limit)} tokens`;
  }

  // Don't render anything if unlimited and no usage yet
  if (isUnlimited && used === 0) return null;

  return (
    <div style={containerStyle}>
      {!isUnlimited && (
        <div style={barTrackStyle}>
          <div style={barFillStyle} />
        </div>
      )}

      <span style={labelStyle}>{labelText}</span>

      {isExhausted && canRecharge && selfRechargeEnabled && (
        <button
          style={rechargeButtonStyle}
          onClick={() => setShowPacks(true)}
          onMouseEnter={e => { e.currentTarget.style.background = isDark ? '#2a2a2a' : '#f0f4ff'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'none'; }}
        >
          Recharge
        </button>
      )}

      {/* Recharge pack selection dialog */}
      <div style={overlayStyle} onClick={() => setShowPacks(false)} />
      <div style={dialogStyle}>
        <div style={dialogTitleStyle}>Token Packs</div>
        <div style={dialogSubStyle}>Select a pack to continue using AI features.</div>
        {PACK_LIST.map((pack, idx) => (
          <button
            key={pack.id}
            style={packButtonStyle(idx === PACK_LIST.length - 1)}
            onClick={() => handlePackSelect(pack.id)}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = '#4f8ff7';
              e.currentTarget.style.background = isDark ? '#2a2a2a' : '#f0f4ff';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = isDark ? '#333' : '#e5e5e5';
              e.currentTarget.style.background = isDark ? '#252525' : '#fafafa';
            }}
          >
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: isDark ? '#f5f5f5' : '#171717' }}>
                {pack.label}
              </div>
            </div>
            <div style={{
              fontSize: 13,
              fontWeight: 700,
              color: '#4f8ff7',
              whiteSpace: 'nowrap',
            }}>
              &#8377;{pack.price}
            </div>
          </button>
        ))}
        <button
          style={{
            width: '100%',
            marginTop: 12,
            padding: '8px 0',
            background: 'none',
            border: `1px solid ${isDark ? '#333' : '#e5e5e5'}`,
            borderRadius: 8,
            color: isDark ? '#888' : '#999',
            fontSize: 12,
            cursor: 'pointer',
          }}
          onClick={() => setShowPacks(false)}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
