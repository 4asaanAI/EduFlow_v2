import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, Play } from 'lucide-react';
import { CornerFrame, MagneticButton, StatusDot, TickerCounter } from './primitives';

/* node layout in a 1000 x 360 viewBox */
const NODES = {
  teacher:   { x: 95,  y: 180, w: 150, h: 56, label: 'Teacher · Attendance' },
  ai:        { x: 360, y: 180, w: 150, h: 56, label: 'AI · Validate' },
  parents:   { x: 700, y: 70,  w: 150, h: 50, label: 'Parents Notified' },
  dashboard: { x: 700, y: 180, w: 150, h: 50, label: 'Dashboard Synced' },
  reports:   { x: 700, y: 290, w: 150, h: 50, label: 'Reports Ready' },
  principal: { x: 925, y: 180, w: 60,  h: 80, label: '' },
};
const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const center = (n) => ({ x: n.x + n.w / 2, y: n.y + n.h / 2 });

function linkPath(aId, bId) {
  const a = center(NODES[aId]); const b = center(NODES[bId]);
  const midX = (a.x + b.x) / 2;
  return `M ${a.x} ${a.y} C ${midX} ${a.y}, ${midX} ${b.y}, ${b.x} ${b.y}`;
}
const LINKS = [
  ['teacher', 'ai'], ['ai', 'parents'], ['ai', 'dashboard'],
  ['ai', 'reports'], ['parents', 'principal'], ['dashboard', 'principal'], ['reports', 'principal'],
];

function HeroLoop() {
  const [lit, setLit] = useState({});
  const [packets, setPackets] = useState([]);
  const [activeLinks, setActiveLinks] = useState({});
  const packetsRef = useRef([]);
  const alive = useRef(true);
  const keyRef = useRef(0);
  const svgRef = useRef(null);
  const visibleRef = useRef(true);

  useEffect(() => {
    alive.current = true;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      setLit({ teacher: 1, ai: 1, parents: 1, dashboard: 1, reports: 1, principal: 1 });
      return () => { alive.current = false; };
    }

    let raf = null;
    let running = false;
    const frame = (now) => {
      const render = [];
      const live = [];
      for (const p of packetsRef.current) {
        const t = Math.min((now - p.start) / p.dur, 1);
        const e = easeOutCubic(t);
        const a = center(NODES[p.from]); const b = center(NODES[p.to]);
        // bezier sample (matches the cubic connector shape)
        const cx = (a.x + b.x) / 2;
        const mt = 1 - e;
        const x = mt * mt * mt * a.x + 3 * mt * mt * e * cx + 3 * mt * e * e * cx + e * e * e * b.x;
        const y = mt * mt * mt * a.y + 3 * mt * mt * e * a.y + 3 * mt * e * e * b.y + e * e * e * b.y;
        render.push({ key: p.key, x, y });
        if (t < 1) live.push(p); else if (p.resolve) p.resolve();
      }
      packetsRef.current = live;
      setPackets(render);
      if (visibleRef.current && alive.current) raf = requestAnimationFrame(frame);
      else running = false;
    };
    const startFrame = () => { if (!running) { running = true; raf = requestAnimationFrame(frame); } };
    startFrame();

    // pause the per-frame loop when the diagram is off-screen
    let io;
    if (typeof IntersectionObserver !== 'undefined' && svgRef.current) {
      io = new IntersectionObserver(([e]) => {
        visibleRef.current = e.isIntersecting;
        if (e.isIntersecting) startFrame();
      }, { threshold: 0 });
      io.observe(svgRef.current);
    }

    const fire = (from, to, dur = 850) =>
      new Promise((resolve) => {
        const link = `${from}-${to}`;
        setActiveLinks((s) => ({ ...s, [link]: true }));
        packetsRef.current.push({ key: keyRef.current++, from, to, start: performance.now(), dur, resolve });
      });

    const run = async () => {
      while (alive.current) {
        setLit({}); setActiveLinks({});
        await sleep(650); if (!alive.current) break;

        setLit((s) => ({ ...s, teacher: 1 }));
        await sleep(220);
        await fire('teacher', 'ai', 820); if (!alive.current) break;

        setLit((s) => ({ ...s, ai: 1 }));
        await sleep(420); if (!alive.current) break;

        // fan-out — the payoff beat
        await Promise.all([
          fire('ai', 'parents', 900),
          fire('ai', 'dashboard', 760),
          fire('ai', 'reports', 1000),
        ]);
        if (!alive.current) break;
        setLit((s) => ({ ...s, parents: 1, dashboard: 1, reports: 1 }));
        await sleep(560); if (!alive.current) break;

        await Promise.all([
          fire('parents', 'principal', 700),
          fire('dashboard', 'principal', 700),
          fire('reports', 'principal', 700),
        ]);
        if (!alive.current) break;
        setLit((s) => ({ ...s, principal: 1 }));
        await sleep(1700);
      }
    };
    run();

    return () => { alive.current = false; if (raf) cancelAnimationFrame(raf); if (io) io.disconnect(); packetsRef.current = []; };
  }, []);

  return (
    <svg ref={svgRef} className="eh-ops-svg" viewBox="0 0 1000 360" role="img"
      aria-label="EduFlow operations loop: a teacher's attendance upload is validated by AI, then fans out to parent notifications, dashboard sync, and reports, reaching the principal as insights.">
      {/* links */}
      {LINKS.map(([a, b]) => (
        <path key={`l-${a}-${b}`} d={linkPath(a, b)} className="eh-link" />
      ))}
      {LINKS.map(([a, b]) =>
        activeLinks[`${a}-${b}`] ? (
          <path key={`la-${a}-${b}`} d={linkPath(a, b)} className="eh-link-active" opacity="0.5" />
        ) : null
      )}

      {/* nodes */}
      {Object.entries(NODES).map(([id, n]) => {
        const c = center(n);
        const isPrincipal = id === 'principal';
        return (
          <g key={id} className={`eh-node ${lit[id] ? 'lit' : ''}`}>
            <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={isPrincipal ? 30 : 10} className="eh-node-rect" />
            {isPrincipal ? (
              <>
                <circle cx={c.x} cy={c.y - 8} r="8" className="eh-node-icon" fill="none" strokeWidth="1.4" />
                <path d={`M ${c.x - 13} ${c.y + 22} Q ${c.x} ${c.y + 4} ${c.x + 13} ${c.y + 22}`} className="eh-node-icon" fill="none" strokeWidth="1.4" />
              </>
            ) : (
              <text x={c.x} y={c.y + 3} textAnchor="middle" className="eh-node-label">{n.label}</text>
            )}
          </g>
        );
      })}

      {/* packets */}
      {packets.map((p) => (
        <circle key={p.key} cx={p.x} cy={p.y} r="5" className="eh-packet" />
      ))}
    </svg>
  );
}

const FLOATING = [
  { style: { top: '2%', left: '1%' }, text: <><b>412/420</b> PRESENT</> },
  { style: { top: '0%', right: '3%' }, text: <><b>₹2.1L</b> COLLECTED</> },
  { style: { top: '42%', left: '-2%' }, text: <><b>SYNC</b> · 24ms</> },
  { style: { bottom: '6%', left: '4%' }, text: <><b>18</b> REPORTS GENERATED</> },
  { style: { bottom: '2%', right: '2%' }, text: <><b>3 PARENTS</b> NOTIFIED · 0.4s AGO</> },
  { style: { top: '44%', right: '-3%' }, text: <><b>AI</b> · 0 ERRORS</> },
];

const HERO_STATS = [
  { to: 6, suffix: '', cap: 'Modules unified' },
  { to: 0.4, prefix: '', suffix: 's', cap: 'Action → outcome', fmt: (n) => n.toFixed(1) },
  { to: 24, suffix: '/7', cap: 'Always running' },
];

export default function Hero({ onLogin, scrollTo }) {
  const opsRef = useRef(null);

  const onParallax = (e) => {
    const el = opsRef.current;
    if (!el || window.matchMedia('(hover: none)').matches) return;
    const px = e.clientX / window.innerWidth - 0.5;
    const py = e.clientY / window.innerHeight - 0.5;
    el.style.transform = `perspective(1400px) rotateY(${px * 5}deg) rotateX(${-py * 4}deg)`;
  };
  const resetParallax = () => {
    if (opsRef.current) opsRef.current.style.transform = 'perspective(1400px) rotateY(0deg) rotateX(0deg)';
  };

  return (
    <header className="eh-hero" id="top" onMouseMove={onParallax} onMouseLeave={resetParallax}>
      <div className="eh-grid-bg" aria-hidden />
      <div className="eh-blob" style={{ top: '8%', left: '50%', transform: 'translateX(-50%)' }} aria-hidden />

      <div className="eh-hero-copy">
        <span className="eh-eyebrow eh-reveal in" style={{ marginBottom: 22, display: 'inline-flex' }}>
          <StatusDot done label="" /> Autonomous School Operations
        </span>
        <h1 className="eh-h1 eh-shimmer eh-reveal in" style={{ transitionDelay: '60ms' }}>
          Your school,<br />running itself.
        </h1>
        <p className="eh-lead eh-reveal in" style={{ maxWidth: 620, margin: '22px auto 0', transitionDelay: '140ms' }}>
          EduFlow's AI handles attendance, fees, reports, and parent communication —
          automatically, continuously, without your teachers lifting a finger.
        </p>
        <div className="eh-hero-cta eh-reveal in" style={{ transitionDelay: '220ms' }}>
          <MagneticButton variant="primary" onClick={onLogin}>
            See it in action <ArrowRight size={17} />
          </MagneticButton>
          <button className="eh-btn eh-btn-ghost" onClick={() => scrollTo('automation')}>
            <Play size={15} /> Watch how it works
          </button>
        </div>

        <div className="eh-hero-stats eh-reveal in" style={{ transitionDelay: '320ms' }}>
          {HERO_STATS.map((s, i) => (
            <div className="eh-hero-stat" key={i}>
              <div className="num">
                {s.prefix || ''}<TickerCounter to={s.to} duration={1400} format={s.fmt} />{s.suffix}
              </div>
              <div className="cap">{s.cap}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="eh-ops" ref={opsRef} style={{ transition: 'transform 0.5s cubic-bezier(0.215,0.61,0.355,1)', transformStyle: 'preserve-3d' }}>
        {FLOATING.map((f, i) => (
          <div key={i} className="eh-flabel" style={{ ...f.style, animationDelay: `${i * 0.5}s` }} aria-hidden>
            {f.style.right !== undefined ? (
              <>
                <span className="pill">{f.text}</span>
                <span className="line" style={{ width: 26 }} />
                <span className="anchor" />
              </>
            ) : (
              <>
                <span className="anchor" />
                <span className="line" style={{ width: 26 }} />
                <span className="pill">{f.text}</span>
              </>
            )}
          </div>
        ))}
        <CornerFrame active style={{ borderRadius: 12, padding: 'clamp(20px,3vw,40px)', background: 'rgba(18,18,20,0.4)', backdropFilter: 'blur(2px)', overflow: 'hidden' }}>
          <div className="eh-ops-scan" aria-hidden />
          <HeroLoop />
        </CornerFrame>
      </div>
    </header>
  );
}
