import React, { useEffect, useRef, useState } from 'react';
import {
  ClipboardCheck, Wallet, GraduationCap, MessageSquare, Bus, FileBarChart,
  ShieldCheck, Zap, Quote,
} from 'lucide-react';
import { Reveal, SpotlightCard, CornerFrame, StatusDot, useInView } from './primitives';

/* ---------------- Live ticker marquee (ambient "system never sleeps") ---------------- */
const TICKER = [
  'ATTENDANCE LOCKED · 9A · 32/32',
  'FEE RECEIPT SENT · ₹3,800',
  'REPORT CARD GENERATED · GRADE 6',
  '3 PARENTS NOTIFIED · 0.4s',
  'EXAM MARKS SYNCED · SCIENCE',
  'BUS ROUTE 3 · ON TIME',
  'AI FLAGGED · 2 LOW-ATTENDANCE CLASSES',
  'ANNOUNCEMENT PUBLISHED · ALL BRANCHES',
  'DEFAULTER REMINDER QUEUED · 14',
];

export function LiveTicker() {
  const row = [...TICKER, ...TICKER];
  return (
    <div className="eh-ticker" aria-hidden>
      <div className="eh-ticker-track">
        {row.map((t, i) => (
          <span className="eh-ticker-item" key={i}>
            <span className="d" />{t}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ---------------- Features grid ---------------- */
const FEATURES = [
  { icon: ClipboardCheck, title: 'Attendance', desc: 'Tap, biometric or RFID — validated, locked and analysed the instant it\'s captured.', status: 'Auto-synced', proc: true },
  { icon: Wallet, title: 'Fees & Accounts', desc: 'Collection, receipts, reminders and reconciliation across six payment channels.', status: 'Live', proc: false },
  { icon: GraduationCap, title: 'Exams & Reports', desc: 'Marks flow straight into formatted report cards and risk analytics — in seconds.', status: '3× faster', proc: true },
  { icon: MessageSquare, title: 'Communication', desc: 'SMS, WhatsApp and email to every parent, with delivery confirmation — not guesswork.', status: '98% delivery', proc: false },
  { icon: Bus, title: 'Transport', desc: 'Routes, roll-calls and live status for every bus, every trip, every student.', status: 'Tracked', proc: false },
  { icon: FileBarChart, title: 'Insights', desc: 'Attendance trends, fee health and academic risk surfaced before they become problems.', status: 'Continuous', proc: true },
];

export function Features() {
  return (
    <section className="eh-section" id="features">
      <div className="eh-grid-bg" aria-hidden />
      <div className="eh-wrap">
        <Reveal as="span" className="eh-eyebrow" style={{ display: 'inline-flex', marginBottom: 16 }}>
          <i className="eh-eyebrow-idx">01</i> One platform · every operation
        </Reveal>
        <Reveal as="h2" className="eh-h2" style={{ maxWidth: 760 }}>
          Everything a school does, running itself.
        </Reveal>
        <Reveal as="p" className="eh-lead" delay={100} style={{ maxWidth: 540, marginTop: 16 }}>
          No bolt-on modules, no integrations to babysit. One AI core that operates the entire school day.
        </Reveal>

        <div className="eh-feat-grid">
          {FEATURES.map((f, i) => {
            const Icon = f.icon;
            return (
              <Reveal key={f.title} variant="scale-in" stagger={70} index={i}>
                <SpotlightCard className={`eh-feat ${f.proc ? 'proc' : ''}`}>
                  <div className="eh-feat-top">
                    <span className="eh-feat-ico"><Icon size={20} /></span>
                    <StatusDot done label={f.status} />
                  </div>
                  <h3 className="eh-feat-title">{f.title}</h3>
                  <p className="eh-feat-desc">{f.desc}</p>
                </SpotlightCard>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ---------------- Digital Twin — whole-school node graph ---------------- */
const HUB = { x: 450, y: 300 };
const SATS = [
  { id: 'students', label: 'Students', x: 450, y: 90 },
  { id: 'teachers', label: 'Teachers', x: 700, y: 150 },
  { id: 'parents', label: 'Parents', x: 810, y: 300 },
  { id: 'classes', label: 'Classes', x: 700, y: 450 },
  { id: 'fees', label: 'Fees', x: 450, y: 510 },
  { id: 'exams', label: 'Exams', x: 200, y: 450 },
  { id: 'attendance', label: 'Attendance', x: 90, y: 300 },
  { id: 'transport', label: 'Transport', x: 200, y: 150 },
];

export function DigitalTwin() {
  const [ref, inView] = useInView({ once: true, threshold: 0.3 });
  const [lit, setLit] = useState({});
  const [pulses, setPulses] = useState([]);
  const pulsesRef = useRef([]);
  const alive = useRef(false);

  useEffect(() => {
    if (!inView) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    // sequential light-up
    SATS.forEach((s, i) => setTimeout(() => setLit((p) => ({ ...p, [s.id]: true })), 180 + i * 160));
    if (reduce) return;

    alive.current = true;
    let raf, spawnTimer;
    let key = 0;
    const spawn = () => {
      const s = SATS[Math.floor(Math.random() * SATS.length)];
      const dir = Math.random() > 0.5;
      pulsesRef.current.push({ key: key++, sat: s, start: performance.now(), dur: 1100, dir });
    };
    spawnTimer = setInterval(spawn, 320);

    const frame = (now) => {
      const render = [];
      const live = [];
      for (const p of pulsesRef.current) {
        const t = Math.min((now - p.start) / p.dur, 1);
        const e = p.dir ? t : 1 - t;
        render.push({ key: p.key, x: HUB.x + (p.sat.x - HUB.x) * e, y: HUB.y + (p.sat.y - HUB.y) * e });
        if (t < 1) live.push(p);
      }
      pulsesRef.current = live;
      setPulses(render);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => { alive.current = false; cancelAnimationFrame(raf); clearInterval(spawnTimer); pulsesRef.current = []; };
  }, [inView]);

  return (
    <section className="eh-section" id="twin" ref={ref}>
      <div className="eh-blob" style={{ top: '20%', left: '50%', transform: 'translateX(-50%)', opacity: 0.16 }} aria-hidden />
      <div className="eh-wrap" style={{ textAlign: 'center' }}>
        <Reveal as="span" className="eh-eyebrow" style={{ display: 'inline-flex', marginBottom: 16 }}>
          <i className="eh-eyebrow-idx">04</i> The digital twin
        </Reveal>
        <Reveal as="h2" className="eh-h2" style={{ maxWidth: 720, margin: '0 auto' }}>
          A living model of your entire school.
        </Reveal>
        <Reveal as="p" className="eh-lead" delay={100} style={{ maxWidth: 560, margin: '16px auto 0' }}>
          Every student, class, fee and bus — connected to one AI core that keeps the whole picture in sync, always.
        </Reveal>

        <Reveal className="eh-twin-wrap">
          <CornerFrame active style={{ borderRadius: 16, padding: 'clamp(12px,2vw,28px)' }}>
            <svg className="eh-twin-svg" viewBox="0 0 900 600" role="img" aria-label="EduFlow digital twin: a central AI core connected to students, teachers, parents, classes, fees, exams, attendance and transport.">
              {SATS.map((s) => (
                <line key={`e-${s.id}`} x1={HUB.x} y1={HUB.y} x2={s.x} y2={s.y}
                  className={`eh-twin-edge ${lit[s.id] ? 'lit' : ''}`} />
              ))}
              {pulses.map((p) => (
                <circle key={p.key} cx={p.x} cy={p.y} r="4" className="eh-twin-pulse" />
              ))}
              {SATS.map((s) => (
                <g key={s.id} className={`eh-twin-node ${lit[s.id] ? 'lit' : ''}`}>
                  <circle cx={s.x} cy={s.y} r="34" className="eh-twin-circle" />
                  <text x={s.x} y={s.y + 3} textAnchor="middle" className="eh-twin-label">{s.label}</text>
                </g>
              ))}
              {/* hub */}
              <g className="eh-twin-hub">
                <circle cx={HUB.x} cy={HUB.y} r="56" className="eh-twin-hub-glow" />
                <circle cx={HUB.x} cy={HUB.y} r="44" className="eh-twin-hub-core" />
                <text x={HUB.x} y={HUB.y - 2} textAnchor="middle" className="eh-twin-hub-label">EduFlow</text>
                <text x={HUB.x} y={HUB.y + 14} textAnchor="middle" className="eh-twin-hub-sub">AI CORE</text>
              </g>
            </svg>
          </CornerFrame>
        </Reveal>
      </div>
    </section>
  );
}

/* ---------------- Testimonials ---------------- */
const QUOTES = [
  { q: 'We shut down three spreadsheets and a WhatsApp group in the first week. The staff actually trust it.', name: 'Priya Sharma', role: 'Principal · The Aaryans', i: 'PS' },
  { q: 'Report cards used to eat my weekends. Now they\'re done before I\'ve finished my chai.', name: 'Rajesh Kumar', role: 'Class Teacher · 9A', i: 'RK' },
  { q: 'Fee reconciliation that took two days closes itself by evening. I just review and approve.', name: 'Meena Gupta', role: 'Accountant', i: 'MG' },
];

export function Testimonials() {
  return (
    <section className="eh-section" id="voices">
      <div className="eh-wrap">
        <Reveal as="span" className="eh-eyebrow" style={{ display: 'block', marginBottom: 16 }}>
          From the staff room
        </Reveal>
        <Reveal as="h2" className="eh-h2" style={{ maxWidth: 640 }}>
          The people who stopped doing it by hand.
        </Reveal>
        <div className="eh-quotes">
          {QUOTES.map((qt, i) => (
            <Reveal key={i} variant="scale-in" stagger={90} index={i}>
              <SpotlightCard className="eh-quote">
                <Quote className="eh-quote-mark" size={26} />
                <p className="eh-quote-text">{qt.q}</p>
                <div className="eh-quote-by">
                  <span className="eh-quote-av">{qt.i}</span>
                  <div>
                    <div className="eh-quote-name">{qt.name}</div>
                    <div className="eh-quote-role">{qt.role}</div>
                  </div>
                </div>
              </SpotlightCard>
            </Reveal>
          ))}
        </div>

        <Reveal className="eh-trust-strip">
          <span className="eh-trust-item"><ShieldCheck size={16} /> DPDP-aware · data stays in-region</span>
          <span className="eh-trust-item"><Zap size={16} /> Built for CBSE multi-branch schools</span>
          <span className="eh-trust-item"><StatusDot done label="99.9% uptime" /></span>
        </Reveal>
      </div>
    </section>
  );
}
