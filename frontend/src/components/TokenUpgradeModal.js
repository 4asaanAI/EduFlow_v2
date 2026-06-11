import React, { useState, useEffect, useCallback } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { getTokenPlans, createSubscriptionCheckout } from '../lib/api';
import { X, Zap, Star, Crown, ArrowRight, Sparkles } from 'lucide-react';

const PLAN_META = {
  monthly_starter: {
    icon: Zap,
    accent: { light: '#4f8ff7', dark: '#60a5fa' },
    bg: { light: '#eff6ff', dark: '#1a2a3f' },
    suitableFor: 'Light daily AI use — quick chat, lookups, short queries',
  },
  monthly_growth: {
    icon: Star,
    accent: { light: '#8b5cf6', dark: '#a78bfa' },
    bg: { light: '#f5f3ff', dark: '#231b3f' },
    suitableFor: 'Regular users — lesson plans, reports, data analysis',
  },
  monthly_enterprise: {
    icon: Crown,
    accent: { light: '#f59e0b', dark: '#fbbf24' },
    bg: { light: '#fffbeb', dark: '#2e2000' },
    suitableFor: 'Power users — AI-heavy work, automation, full daily use',
  },
};

function fmtTokens(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(0)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return `${n}`;
}

function fmtUsed(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return `${n}`;
}

function PlanCard({ plan, meta, isDark, onSelect, busy, isSelected }) {
  const [hovered, setHovered] = useState(false);
  const Icon = meta.icon;
  const accent = isDark ? meta.accent.dark : meta.accent.light;
  const cardBg = (hovered || isSelected) ? (isDark ? meta.bg.dark : meta.bg.light) : (isDark ? '#1a1a1a' : '#ffffff');
  const borderCol = (hovered || isSelected) ? accent : (isDark ? '#2a2a2a' : '#e5e7eb');
  const textCol = isDark ? '#f0f0f0' : '#111827';
  const mutedCol = isDark ? '#888' : '#6b7280';

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onSelect(plan.id)}
      style={{
        position: 'relative', cursor: 'pointer',
        flex: '1 1 0', minWidth: 0,
        background: cardBg,
        border: `2px solid ${borderCol}`,
        borderRadius: 20,
        padding: plan.popular ? '30px 22px 22px' : '22px',
        transition: 'all 0.2s ease',
        transform: (hovered || isSelected) ? 'translateY(-4px)' : 'none',
        boxShadow: (hovered || isSelected)
          ? `0 12px 40px ${accent}25`
          : (isDark ? '0 1px 4px rgba(0,0,0,0.35)' : '0 1px 4px rgba(0,0,0,0.07)'),
      }}
    >
      {plan.popular && (
        <div style={{
          position: 'absolute', top: -13, left: '50%', transform: 'translateX(-50%)',
          background: accent, color: '#fff',
          fontSize: 10, fontWeight: 800, letterSpacing: '0.08em',
          padding: '3px 14px', borderRadius: 20, whiteSpace: 'nowrap',
        }}>
          MOST POPULAR
        </div>
      )}

      {/* Icon */}
      <div style={{
        width: 42, height: 42, borderRadius: 13, marginBottom: 14,
        background: `${accent}18`, border: `1.5px solid ${accent}40`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon size={20} color={accent} />
      </div>

      {/* Plan name */}
      <div style={{ fontSize: 17, fontWeight: 700, color: textCol, letterSpacing: '-0.01em', marginBottom: 4 }}>
        {plan.label}
      </div>

      {/* Tokens / month */}
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        background: `${accent}15`, border: `1px solid ${accent}30`,
        borderRadius: 8, padding: '5px 10px', marginBottom: 12,
      }}>
        <Sparkles size={12} color={accent} />
        <span style={{ fontSize: 13, fontWeight: 700, color: accent }}>
          {fmtTokens(plan.tokens_per_month)} tokens / month
        </span>
      </div>

      {/* Suitable for */}
      <div style={{ fontSize: 12, color: mutedCol, lineHeight: 1.5, marginBottom: 20, minHeight: 36 }}>
        {meta.suitableFor}
      </div>

      {/* Price + CTA */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 2 }}>
            <span style={{ fontSize: 11, color: mutedCol }}>₹</span>
            <span style={{ fontSize: 26, fontWeight: 800, color: textCol, letterSpacing: '-0.03em', lineHeight: 1 }}>
              {plan.price_inr.toLocaleString('en-IN')}
            </span>
          </div>
          <div style={{ fontSize: 10, color: mutedCol }}>per month</div>
        </div>
        <button
          onClick={e => { e.stopPropagation(); onSelect(plan.id); }}
          disabled={busy}
          style={{
            padding: '9px 16px', borderRadius: 10, border: 'none',
            background: (hovered || isSelected) ? accent : (isDark ? '#252525' : '#f3f4f6'),
            color: (hovered || isSelected) ? '#fff' : mutedCol,
            fontSize: 12, fontWeight: 700, cursor: busy ? 'wait' : 'pointer',
            display: 'flex', alignItems: 'center', gap: 6,
            transition: 'all 0.2s ease',
            flexShrink: 0,
            boxShadow: (hovered || isSelected) ? `0 4px 14px ${accent}50` : 'none',
          }}
        >
          {busy && isSelected ? (
            <span style={{ width: 12, height: 12, borderRadius: '50%', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />
          ) : (
            <ArrowRight size={13} />
          )}
          {busy && isSelected ? 'Redirecting…' : 'Choose'}
        </button>
      </div>
    </div>
  );
}

export default function TokenUpgradeModal({ onClose, currentUsage, roleLimit, canPurchase }) {
  const { isDark } = useTheme();
  const [plans, setPlans] = useState([]);
  const [fetchLoading, setFetchLoading] = useState(true);
  const [fetchError, setFetchError] = useState('');
  const [checkoutLoading, setCheckoutLoading] = useState('');
  const [checkoutError, setCheckoutError] = useState('');

  const bg = isDark ? '#111' : '#f8f9fb';
  const surface = isDark ? '#161616' : '#ffffff';
  const border = isDark ? '#222' : '#e5e7eb';
  const text = isDark ? '#f0f0f0' : '#111827';
  const muted = isDark ? '#777' : '#6b7280';
  const subtext = isDark ? '#555' : '#9ca3af';

  const pct = roleLimit > 0 ? Math.min(100, Math.round((currentUsage / roleLimit) * 100)) : 0;
  const barColor = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981';

  useEffect(() => {
    getTokenPlans()
      .then(r => {
        if (r.success) setPlans(r.data?.subscriptions || []);
        else setFetchError('Could not load plans.');
      })
      .catch(() => setFetchError('Network error.'))
      .finally(() => setFetchLoading(false));
  }, []);

  const handleSelect = useCallback(async (planId) => {
    if (!canPurchase) return;
    setCheckoutLoading(planId);
    setCheckoutError('');
    try {
      const r = await createSubscriptionCheckout(planId);
      if (r.success && r.data?.checkout_url) {
        window.location.href = r.data.checkout_url;
      } else {
        setCheckoutError(r.detail || 'Could not start checkout. Please try again.');
        setCheckoutLoading('');
      }
    } catch {
      setCheckoutError('Network error. Please try again.');
      setCheckoutLoading('');
    }
  }, [canPurchase]);

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 500, background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="fade-in-scale" style={{
        background: bg, border: `1px solid ${border}`,
        borderRadius: 26, width: '100%', maxWidth: 860,
        maxHeight: '90vh', overflowY: 'auto',
        boxShadow: isDark ? '0 32px 100px rgba(0,0,0,0.75)' : '0 32px 100px rgba(0,0,0,0.13)',
      }}>

        {/* Header */}
        <div style={{ padding: '24px 28px 20px', borderBottom: `1px solid ${border}`, background: surface, borderRadius: '26px 26px 0 0', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: 20, fontWeight: 800, color: text, margin: '0 0 4px', letterSpacing: '-0.02em' }}>
              Top up AI Tokens
            </h2>
            <p style={{ fontSize: 12, color: muted, margin: 0 }}>
              Monthly subscription · Cancel anytime · Tokens credited to your account
            </p>

            {/* Usage bar */}
            {roleLimit > 0 && (
              <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ flex: 1, maxWidth: 260 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 10, color: muted, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>This month</span>
                    <span style={{ fontSize: 10, fontWeight: 700, color: barColor }}>{fmtUsed(currentUsage)} / {fmtUsed(roleLimit)}</span>
                  </div>
                  <div style={{ height: 5, borderRadius: 4, background: isDark ? '#2a2a2a' : '#e5e7eb', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: barColor, borderRadius: 4, transition: 'width 0.4s' }} />
                  </div>
                </div>
                <span style={{ fontSize: 10, color: barColor, fontWeight: 700 }}>{pct}% used</span>
              </div>
            )}
          </div>
          <button onClick={onClose} style={{ background: isDark ? '#222' : '#f3f4f6', border: 'none', color: muted, cursor: 'pointer', padding: 7, borderRadius: 9, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <X size={14} />
          </button>
        </div>

        {/* Plans */}
        <div style={{ padding: '28px 28px 20px' }}>
          {fetchLoading ? (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <div className="spinner" style={{ width: 22, height: 22, margin: '0 auto 10px' }} />
              <div style={{ color: muted, fontSize: 13 }}>Loading plans…</div>
            </div>
          ) : fetchError ? (
            <div style={{ textAlign: 'center', padding: '28px 0', color: '#ef4444', fontSize: 13 }}>{fetchError}</div>
          ) : (
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              {plans.map(plan => (
                <PlanCard
                  key={plan.id}
                  plan={plan}
                  meta={PLAN_META[plan.id] || PLAN_META.monthly_starter}
                  isDark={isDark}
                  onSelect={handleSelect}
                  busy={!!checkoutLoading}
                  isSelected={checkoutLoading === plan.id}
                />
              ))}
            </div>
          )}

          {!canPurchase && !fetchLoading && (
            <div style={{ marginTop: 16, padding: '12px 16px', borderRadius: 10, background: isDark ? '#1e2a3a' : '#eff6ff', border: `1px solid ${isDark ? '#1e3a5f' : '#bfdbfe'}`, fontSize: 13, color: isDark ? '#93c5fd' : '#1d4ed8' }}>
              Students cannot purchase tokens. Contact your school admin for more access.
            </div>
          )}

          {checkoutError && (
            <div style={{ marginTop: 14, padding: '11px 14px', borderRadius: 9, background: isDark ? '#2d1515' : '#fef2f2', border: `1px solid ${isDark ? '#7f1d1d' : '#fecaca'}`, color: '#ef4444', fontSize: 12 }}>
              {checkoutError}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '14px 28px 22px', borderTop: `1px solid ${border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {['Secure — Razorpay', 'Cancel anytime', 'Instant token credit'].map((t, i) => (
              <span key={i} style={{ fontSize: 11, color: subtext, display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ color: '#10b981', fontWeight: 700 }}>✓</span> {t}
              </span>
            ))}
          </div>
          <span style={{ fontSize: 11, color: subtext }}>Prices in INR · GST applicable</span>
        </div>
      </div>
    </div>
  );
}
