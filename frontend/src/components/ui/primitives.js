/**
 * EduFlow shared UI primitives — Epic 9 "Looks Like The Brochure".
 *
 * The playful language of eduflow.layaa.ai, made safe for a working app:
 * rounded shapes, a solid offset "toy" shadow, and a press that depresses the
 * control into its own shadow.
 *
 * Three rules these primitives exist to enforce, because 25 hand-styled tool
 * screens proved they do not enforce themselves:
 *
 *   1. THE PRESS IS `transform` ONLY. Never top/margin/height. Animating a
 *      layout property makes every neighbouring cell reflow on click, which is
 *      the same family of fault as D-01. Look for `translateY` below — that is
 *      deliberate, and it is the only thing that moves.
 *
 *   2. LABEL CONTRAST IS FIXED TO THE FILL. `--on-brand-orange` is navy, not
 *      white, because white on #F2811D measures 2.65:1 and NFR-A1 wants 4.5:1.
 *      Do not "tidy" a button by making its label white.
 *
 *   3. EVERY PRIMITIVE FORWARDS `data-testid` (UX-DR4) and uses CSS variables
 *      only, never raw hex (UX-DR1).
 */

import React from 'react';

/* Shared press/hover behaviour. Motion is zeroed globally under
   prefers-reduced-motion by the media query in index.css, so nothing here
   needs its own opt-out. */
const PRESSABLE = {
  transition: 'transform var(--transition-fast), box-shadow var(--transition-fast), background var(--transition-fast)',
  cursor: 'pointer',
};

/**
 * Exported so the contrast contract can be asserted directly.
 *
 * It cannot be asserted through the DOM: jsdom's CSS parser silently DROPS
 * `color` and `background` declarations whose value is a `var()`, so a
 * rendered button reports neither. Testing this map is testing the real
 * decision — which token each variant pairs with which fill.
 */
export const VARIANTS = {
  primary: {
    background: 'var(--brand-blue-fill)',
    color: 'var(--on-brand-blue)',
    border: 'none',
    shadowColor: 'var(--brand-blue-press)',
  },
  accent: {
    background: 'var(--brand-orange)',
    color: 'var(--on-brand-orange)',
    border: 'none',
    shadowColor: 'var(--brand-orange-press)',
  },
  secondary: {
    background: 'var(--color-surface-raised)',
    color: 'var(--color-text-primary)',
    border: '1px solid var(--color-border)',
    shadowColor: 'var(--color-border-strong)',
  },
  ghost: {
    background: 'transparent',
    color: 'var(--color-text-secondary)',
    border: '1px solid transparent',
    shadowColor: 'transparent',
  },
  danger: {
    background: 'var(--color-danger)',
    color: 'var(--color-inverse-text)',
    border: 'none',
    shadowColor: 'var(--brand-orange-press)',
  },
};

const SIZES = {
  sm: { padding: '6px 12px', fontSize: 'var(--text-sm)', radius: 'var(--radius-sm)', lift: 3, minHeight: 32 },
  md: { padding: '9px 16px', fontSize: 'var(--text-base)', radius: 'var(--radius-md)', lift: 4, minHeight: 40 },
  lg: { padding: '12px 22px', fontSize: 'var(--text-lg)', radius: 'var(--radius-lg)', lift: 5, minHeight: 48 },
};

/**
 * The platform's button. Depresses into its shadow when pressed.
 *
 * `lift` is the height of the solid shadow AND the distance the button travels
 * when pressed — they are the same number so the bottom edge stays put and the
 * row never moves.
 */
export function Button({
  variant = 'secondary',
  size = 'md',
  icon: Icon,
  children,
  disabled = false,
  style,
  'data-testid': testId,
  ...rest
}) {
  const v = VARIANTS[variant] || VARIANTS.secondary;
  const s = SIZES[size] || SIZES.md;
  const [pressed, setPressed] = React.useState(false);

  const release = () => setPressed(false);

  return (
    <button
      type="button"
      disabled={disabled}
      data-testid={testId}
      aria-disabled={disabled || undefined}
      onMouseDown={() => !disabled && setPressed(true)}
      onMouseUp={release}
      onMouseLeave={release}
      onBlur={release}
      onKeyDown={(e) => { if (!disabled && (e.key === ' ' || e.key === 'Enter')) setPressed(true); }}
      onKeyUp={release}
      style={{
        ...PRESSABLE,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 7,
        fontFamily: 'var(--font-display)',
        fontWeight: 700,
        lineHeight: 1.2,
        padding: s.padding,
        fontSize: s.fontSize,
        minHeight: s.minHeight,
        borderRadius: s.radius,
        background: v.background,
        color: v.color,
        border: v.border,
        // Disabled is signalled by more than colour: the shadow goes too, so
        // the control visibly stops looking pressable.
        boxShadow: disabled || variant === 'ghost'
          ? 'none'
          : `0 ${pressed ? 1 : s.lift}px 0 0 ${v.shadowColor}`,
        // The ONLY moving property. Not top, not margin.
        transform: pressed && !disabled ? `translateY(${s.lift - 1}px)` : 'translateY(0)',
        opacity: disabled ? 0.45 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        ...style,
      }}
      {...rest}
    >
      {Icon ? <Icon size={size === 'lg' ? 18 : 15} aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

/** A rounded surface. `raised` lifts it off the page with the soft shadow. */
export function Card({ raised = false, glow = false, children, style, 'data-testid': testId, ...rest }) {
  return (
    <div
      data-testid={testId}
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-xl)',
        padding: 18,
        boxShadow: glow ? 'var(--glow-blue)' : raised ? 'var(--shadow-md)' : 'none',
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}

const PILL_TONES = {
  neutral: { bg: 'var(--color-surface-raised)', fg: 'var(--color-text-secondary)' },
  blue:    { bg: 'rgba(43,143,240,0.16)',  fg: 'var(--color-accent-blue)' },
  green:   { bg: 'rgba(52,211,153,0.16)',  fg: 'var(--color-success)' },
  orange:  { bg: 'rgba(242,129,29,0.16)',  fg: 'var(--accent-orange)' },
  red:     { bg: 'rgba(251,113,133,0.16)', fg: 'var(--color-danger)' },
  purple:  { bg: 'rgba(167,139,250,0.16)', fg: 'var(--color-purple)' },
  yellow:  { bg: 'rgba(255,201,60,0.16)',  fg: 'var(--color-warning)' },
};

/**
 * A status/role chip.
 *
 * `icon` is not decoration: WCAG `color-not-only` means a status must not be
 * conveyed by colour alone, so anything semantic should pass one.
 */
export function Pill({ tone = 'neutral', icon: Icon, children, style, 'data-testid': testId, ...rest }) {
  const t = PILL_TONES[tone] || PILL_TONES.neutral;
  return (
    <span
      data-testid={testId}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '3px 10px',
        borderRadius: 'var(--radius-full)',
        background: t.bg,
        color: t.fg,
        fontFamily: 'var(--font-display)',
        fontSize: 'var(--text-xs)',
        fontWeight: 700,
        whiteSpace: 'nowrap',
        ...style,
      }}
      {...rest}
    >
      {Icon ? <Icon size={12} aria-hidden="true" /> : null}
      {children}
    </span>
  );
}

/**
 * The shared empty state (UX-DR6).
 *
 * `kind` is the whole point: the school's data has all three cases and they
 * mean completely different things. Every student's date of birth is blank
 * because it was never captured ("not recorded"), which is not the same as a
 * request that failed ("failed to load") and not the same as a list that is
 * genuinely empty ("no data yet"). Item 7 on the owner's list was a load
 * failure being displayed as a zero.
 */
export function EmptyState({ kind = 'empty', title, message, action, icon: Icon, 'data-testid': testId }) {
  const COPY = {
    empty:        { title: 'Nothing here yet', message: 'Records will appear here once they are added.' },
    'not-recorded': { title: 'Not recorded', message: 'This was never filled in for these records — it is not missing, it was never captured.' },
    error:        { title: "Couldn't load this", message: 'Something went wrong fetching it. This is not a zero — please try again.' },
  };
  const c = COPY[kind] || COPY.empty;
  return (
    <div
      data-testid={testId}
      role={kind === 'error' ? 'alert' : undefined}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 8, padding: '40px 20px', textAlign: 'center',
        background: 'var(--color-surface)',
        border: '1px dashed var(--color-border)',
        borderRadius: 'var(--radius-xl)',
      }}
    >
      {Icon ? <Icon size={28} aria-hidden="true" style={{ color: 'var(--color-text-muted)' }} /> : null}
      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 'var(--text-lg)', color: 'var(--color-text-primary)' }}>
        {title || c.title}
      </div>
      <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', maxWidth: 420 }}>
        {message || c.message}
      </div>
      {action}
    </div>
  );
}

/** Shared input styling, so a field looks the same wherever it is built. */
export const inputStyle = {
  background: 'var(--color-surface-raised)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--color-text-primary)',
  fontFamily: 'var(--font-body)',
  fontSize: 'var(--text-base)',
  padding: '9px 12px',
  minHeight: 40,
  outline: 'none',
};

/** A labelled field. Visible label, never placeholder-only (WCAG input-labels). */
export function Field({ label, htmlFor, hint, children, style }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, ...style }}>
      <label
        htmlFor={htmlFor}
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--color-text-secondary)',
        }}
      >
        {label}
      </label>
      {children}
      {hint ? (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>{hint}</span>
      ) : null}
    </div>
  );
}

export default { Button, Card, Pill, EmptyState, Field, inputStyle };
