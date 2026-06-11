import React, { useState, useEffect, useCallback } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { getTokenPlans, createSubscriptionCheckout } from '../lib/api';
import { X, Zap, Star, Crown, Check, ArrowRight, Sparkles } from 'lucide-react';

const PLAN_META = {
  monthly_starter: {
    icon: Zap,
    accentLight: '#4f8ff7',
    accentDark: '#60a5fa',
    gradientLight: 'linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)',
    gradientDark: 'linear-gradient(135deg, #1e3a5f 0%, #1e40af22 100%)',
    features: ['1M AI tokens / month', 'All staff & teacher roles', 'Attendance, fees & reports', 'Basic AI chat assistant', 'Email support'],
  },
  monthly_growth: {
    icon: Star,
    accentLight: '#8b5cf6',
    accentDark: '#a78bfa',
    gradientLight: 'linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%)',
    gradientDark: 'linear-gradient(135deg, #2e1f5f 0%, #4c1d9522 100%)',
    features: ['3M AI tokens / month', 'Everything in Starter', 'Advanced AI analytics', 'Smart fee defaulter alerts', 'Priority support'],
  },
  monthly_enterprise: {
    icon: Crown,
    accentLight: '#f59e0b',
    accentDark: '#fbbf24',
    gradientLight: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)',
    gradientDark: 'linear-gradient(135deg, #3d2a00 0%, #92400e22 100%)',
    features: ['8M AI tokens / month', 'Everything in Growth', 'Custom role token limits', 'Dedicated school manager', 'SLA-backed support'],
  },
};

function fmt(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(0)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return `${n}`;
}

function PlanCard({ plan, meta, isDark, onSelect, loading, isSelected }) {
  const [hovered, setHovered] = useState(false);
  const Icon = meta.icon;
  const accent = isDark ? meta.accentDark : meta.accentLight;
  const bg = isDark ? '#1a1a1a' : '#ffffff';
  const border = isDark ? '#2a2a2a' : '#e5e7eb';
  const text = isDark ? '#f0f0f0' : '#111827';
  const muted = isDark ? '#888' : '#6b7280';
  const isActive = hovered || isSelected;

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'relative',
        background: isActive
          ? (isDark ? meta.gradientDark : meta.gradientLight)
          : bg,
        border: `2px solid ${isActive ? accent : border}`,
        borderRadius: 20,
        padding: plan.popular ? '28px 24px 24px' : '24px',
        flex: '1 1 0',
        minWidth: 0,
        transition: 'all 0.22s ease',
        boxShadow: isActive
          ? `0 8px 40px ${accent}30, 0 2px 8px rgba(0,0,0,0.08)`
          : isDark ? '0 1px 4px rgba(0,0,0,0.3)' : '0 1px 4px rgba(0,0,0,0.06)',
        transform: isActive ? 'translateY(-3px)' : 'none',
        cursor: 'pointer',
      }}
      onClick={() => onSelect(plan.id)}
    >
      {/* Popular badge */}
      {plan.popular && (
        <div style={{
          position: 'absolute', top: -14, left: '50%', transform: 'translateX(-50%)',
          background: `linear-gradient(90deg, ${accent}, ${isDark ? meta.accentLight : meta.accentDark})`,
          color: '#fff', fontSize: 11, fontWeight: 700, letterSpacing: '0.06em',
          padding: '4px 16px', borderRadius: 20,
          boxShadow: `0 2px 12px ${accent}60`,
          whiteSpace: 'nowrap',
        }}>
          ✦ MOST POPULAR
        </div>
      )}

      {/* Icon + name */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <div style={{
            width: 44, height: 44, borderRadius: 14,
            background: `${accent}18`, border: `1.5px solid ${accent}35`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 12,
          }}>
            <Icon size={20} color={accent} />
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, color: text, letterSpacing: '-0.02em' }}>{plan.label}</div>
          <div style={{ fontSize: 12, color: muted, marginTop: 2 }}>{plan.subtitle}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 2, justifyContent: 'flex-end' }}>
            <span style={{ fontSize: 12, color: muted, fontWeight: 500 }}>₹</span>
            <span style={{ fontSize: 30, fontWeight: 800, color: text, letterSpacing: '-0.03em', lineHeight: 1 }}>
              {plan.price_inr.toLocaleString('en-IN')}
            </span>
          </div>
          <div style={{ fontSize: 11, color: muted, marginTop: 3 }}>per month</div>
        </div>
      </div>

      {/* Token highlight */}
      <div style={{
        background: `${accent}14`, border: `1px solid ${accent}30`,
        borderRadius: 10, padding: '10px 14px', marginBottom: 18,
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <Sparkles size={14} color={accent} />
        <span style={{ fontSize: 13, fontWeight: 700, color: accent }}>
          {fmt(plan.tokens_per_month)} tokens / month
        </span>
      </div>

      {/* Features */}
      <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {meta.features.map((f, i) => (
          <li key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 18, height: 18, borderRadius: 6,
              background: `${accent}15`, border: `1px solid ${accent}30`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              <Check size={10} color={accent} strokeWidth={3} />
            </div>
            <span style={{ fontSize: 12, color: muted, lineHeight: 1.4 }}>{f}</span>
          </li>
        ))}
      </ul>

      {/* CTA button */}
      <button
        onClick={e => { e.stopPropagation(); onSelect(plan.id); }}
        disabled={loading}
        style={{
          width: '100%', padding: '12px', borderRadius: 12, border: 'none',
          background: isActive
            ? `linear-gradient(135deg, ${accent}, ${isDark ? meta.accentLight : meta.accentDark})`
            : (isDark ? '#252525' : '#f3f4f6'),
          color: isActive ? '#fff' : muted,
          fontSize: 13, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          transition: 'all 0.2s ease',
          boxShadow: isActive ? `0 4px 16px ${accent}40` : 'none',
          opacity: loading ? 0.7 : 1,
          letterSpacing: '0.01em',
        }}
      >
        {loading && isSelected ? (
          <>
            <span style={{ width: 14, height: 14, borderRadius: '50%', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />
            Redirecting…
          </>
        ) : (
          <>Get {plan.label} <ArrowRight size={14} />
          </>
        )}
      </button>
    </div>
  );
}

export default function TokenUpgradeModal({ onClose, currentUsage, roleLimit, isOwner }) {
  const { isDark } = useTheme();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState('');
  const [checkoutLoading, setCheckoutLoading] = useState('');
  const [checkoutError, setCheckoutError] = useState('');

  const bg = isDark ? '#111111' : '#f8f9fb';
  const surface = isDark ? '#161616' : '#ffffff';
  const border = isDark ? '#222' : '#e5e7eb';
  const text = isDark ? '#f0f0f0' : '#111827';
  const muted = isDark ? '#777' : '#6b7280';
  const subtext = isDark ? '#555' : '#9ca3af';

  useEffect(() => {
    setLoading(true);
    getTokenPlans()
      .then(r => {
        if (r.success) setPlans(r.data?.subscriptions || []);
        else setFetchError('Could not load plans.');
      })
      .catch(() => setFetchError('Network error loading plans.'))
      .finally(() => setLoading(false));
  }, []);

  const handleSelect = useCallback(async (planId) => {
    if (!isOwner) return;
    setCheckoutLoading(planId);
    setCheckoutError('');
    try {
      const r = await createSubscriptionCheckout(planId);
      if (r.success && r.data?.checkout_url) {
        window.location.href = r.data.checkout_url;
      } else {
        setCheckoutError(r.detail || 'Could not start checkout. Try again.');
        setCheckoutLoading('');
      }
    } catch {
      setCheckoutError('Network error. Please try again.');
      setCheckoutLoading('');
    }
  }, [isOwner]);

  const pct = roleLimit > 0 ? Math.min(100, Math.round((currentUsage / roleLimit) * 100)) : 0;
  const barColor = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981';

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 500,
      background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '16px',
    }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="fade-in-scale" style={{
        background: bg,
        border: `1px solid ${border}`,
        borderRadius: 28,
        width: '100%', maxWidth: 900,
        maxHeight: '92vh',
        overflowY: 'auto',
        boxShadow: isDark
          ? '0 40px 120px rgba(0,0,0,0.8), 0 8px 32px rgba(0,0,0,0.5)'
          : '0 40px 120px rgba(0,0,0,0.15), 0 8px 32px rgba(0,0,0,0.06)',
      }}>

        {/* Header */}
        <div style={{
          padding: '28px 32px 24px',
          borderBottom: `1px solid ${border}`,
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16,
          background: surface, borderRadius: '28px 28px 0 0',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <div style={{
                width: 40, height: 40, borderRadius: 12,
                background: isDark ? '#1e3a5f' : '#eff6ff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Zap size={20} color={isDark ? '#60a5fa' : '#4f8ff7'} />
              </div>
              <div>
                <h2 style={{ fontSize: 22, fontWeight: 800, color: text, margin: 0, letterSpacing: '-0.02em' }}>
                  Upgrade EduFlow AI
                </h2>
                <p style={{ fontSize: 13, color: muted, margin: 0, marginTop: 2 }}>
                  Monthly subscription · Cancel anytime · Powered by Razorpay
                </p>
              </div>
            </div>

            {/* Current usage bar */}
            {roleLimit > 0 && (
              <div style={{ marginTop: 14, background: isDark ? '#1a1a1a' : '#f3f4f6', borderRadius: 10, padding: '10px 14px', display: 'inline-flex', alignItems: 'center', gap: 12, minWidth: 280 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                    <span style={{ fontSize: 11, color: muted, fontWeight: 600 }}>This month's usage</span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: barColor }}>{pct}%</span>
                  </div>
                  <div style={{ height: 5, borderRadius: 4, background: isDark ? '#2a2a2a' : '#e5e7eb', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: barColor, borderRadius: 4, transition: 'width 0.4s ease' }} />
                  </div>
                  <div style={{ fontSize: 11, color: subtext, marginTop: 4 }}>
                    {currentUsage.toLocaleString()} / {roleLimit.toLocaleString()} tokens
                  </div>
                </div>
              </div>
            )}
          </div>
          <button onClick={onClose} style={{
            background: isDark ? '#222' : '#f3f4f6', border: 'none',
            color: muted, cursor: 'pointer', padding: 8, borderRadius: 10,
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            <X size={16} />
          </button>
        </div>

        {/* Plan cards */}
        <div style={{ padding: '32px 32px 24px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '48px 0' }}>
              <div className="spinner" style={{ width: 24, height: 24, margin: '0 auto 12px' }} />
              <div style={{ color: muted, fontSize: 14 }}>Loading plans…</div>
            </div>
          ) : fetchError ? (
            <div style={{ textAlign: 'center', padding: '32px 0', color: '#ef4444', fontSize: 14 }}>{fetchError}</div>
          ) : (
            <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
              {plans.map(plan => {
                const meta = PLAN_META[plan.id] || PLAN_META.monthly_starter;
                return (
                  <PlanCard
                    key={plan.id}
                    plan={plan}
                    meta={meta}
                    isDark={isDark}
                    onSelect={handleSelect}
                    loading={!!checkoutLoading}
                    isSelected={checkoutLoading === plan.id}
                  />
                );
              })}
            </div>
          )}

          {/* Non-owner message */}
          {!isOwner && !loading && (
            <div style={{
              marginTop: 20, padding: '14px 18px', borderRadius: 12,
              background: isDark ? '#1e2a3a' : '#eff6ff',
              border: `1px solid ${isDark ? '#1e3a5f' : '#bfdbfe'}`,
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <Zap size={16} color={isDark ? '#60a5fa' : '#4f8ff7'} />
              <span style={{ fontSize: 13, color: isDark ? '#93c5fd' : '#1d4ed8' }}>
                Only the school owner can purchase plans. Contact your school owner to upgrade.
              </span>
            </div>
          )}

          {checkoutError && (
            <div style={{ marginTop: 16, padding: '12px 16px', borderRadius: 10, background: isDark ? '#2d1515' : '#fef2f2', border: `1px solid ${isDark ? '#7f1d1d' : '#fecaca'}`, color: '#ef4444', fontSize: 13 }}>
              {checkoutError}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '16px 32px 24px',
          borderTop: `1px solid ${border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexWrap: 'wrap', gap: 12,
        }}>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {['Secure payments via Razorpay', 'Cancel anytime', 'Instant token credit'].map((t, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Check size={12} color={isDark ? '#10b981' : '#059669'} strokeWidth={2.5} />
                <span style={{ fontSize: 12, color: subtext }}>{t}</span>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 11, color: subtext }}>GST applicable · Prices in INR</div>
        </div>
      </div>
    </div>
  );
}
