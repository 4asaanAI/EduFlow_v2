import React, { useEffect, useRef, useState, useCallback } from 'react';

/* Shared IntersectionObserver-driven reveal hook */
export function useInView(options = {}) {
  const { threshold = 0.2, once = true, rootMargin = '0px 0px -8% 0px' } = options;
  const ref = useRef(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === 'undefined') { setInView(true); return; }
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          if (once) obs.disconnect();
        } else if (!once) {
          setInView(false);
        }
      },
      { threshold, rootMargin }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold, once, rootMargin]);

  return [ref, inView];
}

/* Reveal — fade-up / scale-in / clip-wipe entrance on scroll */
export function Reveal({ as: Tag = 'div', variant = 'fade-up', delay = 0, stagger, index = 0, className = '', children, once = true, style, ...rest }) {
  const [ref, inView] = useInView({ once });
  const variantClass = variant === 'scale-in' ? 'scale-in' : variant === 'clip-wipe' ? 'clip-wipe' : '';
  const totalDelay = (stagger ? index * stagger : 0) + delay;
  return (
    <Tag
      ref={ref}
      className={`eh-reveal ${variantClass} ${inView ? 'in' : ''} ${className}`}
      style={{ '--eh-delay': `${totalDelay}ms`, ...style }}
      {...rest}
    >
      {children}
    </Tag>
  );
}

/* CornerFrame — the viewfinder bracket motif */
export function CornerFrame({ active = false, className = '', children, ...rest }) {
  return (
    <div className={`eh-frame ${active ? 'active' : ''} ${className}`} {...rest}>
      <span className="eh-corner tl" aria-hidden />
      <span className="eh-corner tr" aria-hidden />
      <span className="eh-corner bl" aria-hidden />
      <span className="eh-corner br" aria-hidden />
      {children}
    </div>
  );
}

/* MagneticButton — cursor-aware pull, snaps back on leave */
export function MagneticButton({ variant = 'primary', strength = 7, className = '', children, style, ...rest }) {
  const ref = useRef(null);

  const onMove = useCallback((e) => {
    const el = ref.current;
    if (!el || window.matchMedia('(hover: none)').matches) return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
    const y = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
    el.style.transform = `translate(${x * strength}px, ${y * strength}px)`;
  }, [strength]);

  const onLeave = useCallback(() => {
    const el = ref.current;
    if (el) el.style.transform = 'translate(0,0)';
  }, []);

  return (
    <button
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      className={`eh-btn eh-btn-${variant} ${className}`}
      style={{ transition: 'transform 0.4s cubic-bezier(0.215,0.61,0.355,1), background 0.3s, box-shadow 0.3s, border-color 0.3s, color 0.3s', ...style }}
      {...rest}
    >
      {children}
    </button>
  );
}

/* SpotlightCard — radial glow follows the pointer within bounds */
export function SpotlightCard({ className = '', children, ...rest }) {
  const ref = useRef(null);
  const onMove = useCallback((e) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty('--mx', `${e.clientX - r.left}px`);
    el.style.setProperty('--my', `${e.clientY - r.top}px`);
  }, []);
  return (
    <div ref={ref} onMouseMove={onMove} className={`eh-card ${className}`} {...rest}>
      {children}
    </div>
  );
}

/* StatusDot — dot + mono label, blink-confirm when it flips to done */
export function StatusDot({ done = false, label, success = false }) {
  const [blink, setBlink] = useState(false);
  const prev = useRef(done);
  useEffect(() => {
    if (done && !prev.current) {
      setBlink(true);
      const t = setTimeout(() => setBlink(false), 520);
      return () => clearTimeout(t);
    }
    prev.current = done;
  }, [done]);
  return (
    <span className={`eh-status ${done ? 'done' : ''} ${success ? 'success' : ''} ${blink ? 'blink' : ''}`}>
      <span className="dot" />
      {label}
    </span>
  );
}

/* TickerCounter — eased count-up on view; static text backs it for a11y */
export function TickerCounter({ to, from = 0, duration = 1300, format = (n) => Math.round(n).toLocaleString(), prefix = '', suffix = '' }) {
  const [ref, inView] = useInView({ once: true, threshold: 0.4 });
  const [val, setVal] = useState(from);
  const started = useRef(false);

  useEffect(() => {
    if (!inView || started.current) return;
    started.current = true;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setVal(to); return; }
    let raf;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      setVal(from + (to - from) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, to, from, duration]);

  return <span ref={ref}>{prefix}{format(val)}{suffix}</span>;
}
