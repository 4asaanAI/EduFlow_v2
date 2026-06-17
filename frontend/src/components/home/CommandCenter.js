import React, { useEffect, useRef, useState } from 'react';
import { Users, Wallet, Megaphone, GraduationCap, Sparkles, Check } from 'lucide-react';
import { Reveal, SpotlightCard, StatusDot, useInView } from './primitives';

function useTilt() {
  const ref = useRef(null);
  const onMove = (e) => {
    const el = ref.current;
    if (!el || window.matchMedia('(hover: none)').matches) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(800px) rotateY(${px * 5}deg) rotateX(${-py * 5}deg)`;
  };
  const onLeave = () => { if (ref.current) ref.current.style.transform = 'perspective(800px) rotateY(0) rotateX(0)'; };
  return { ref, onMouseMove: onMove, onMouseLeave: onLeave, style: { transition: 'transform 0.5s cubic-bezier(0.215,0.61,0.355,1)' } };
}

function Module({ span, title, icon: Icon, status, children }) {
  const tilt = useTilt();
  return (
    <div className={span}>
      <div {...tilt}>
        <SpotlightCard className="eh-cc-mod">
          <div className="mhead">
            <span className="mtitle"><span className="mi"><Icon size={16} /></span>{title}</span>
            <StatusDot done label={status} />
          </div>
          {children}
        </SpotlightCard>
      </div>
    </div>
  );
}

const ANN = [
  'PTM scheduled · Grade 8 · Saturday 10 AM',
  'Fee receipt sent · Sneha Kumari · ₹3,800',
  'Holiday notice published · all branches',
  'Bus route 3 · departed on time',
  'Exam datesheet released · Grade 9',
];

export default function CommandCenter() {
  const [present, setPresent] = useState(404);
  const [fees, setFees] = useState(208400);
  const [feed, setFeed] = useState([0, 1, 2]);
  const [ring, setRing] = useState(64);
  const [applied, setApplied] = useState(false);
  const feedHead = useRef(2);
  const [secRef, inView] = useInView({ once: false, threshold: 0.05 });

  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || !inView) return;
    const a = setInterval(() => setPresent((p) => (p < 412 ? p + 1 : 404)), 1600);
    const f = setInterval(() => setFees((v) => v + Math.floor(Math.random() * 900 + 200)), 2200);
    const r = setInterval(() => setRing((v) => (v >= 92 ? 64 : v + 4)), 1800);
    const fd = setInterval(() => {
      feedHead.current = (feedHead.current + 1) % ANN.length;
      setFeed((prev) => [feedHead.current, prev[0], prev[1]]);
    }, 2600);
    return () => { clearInterval(a); clearInterval(f); clearInterval(r); clearInterval(fd); };
  }, [inView]);

  const presentPct = Math.round((present / 420) * 100);
  const C = 2 * Math.PI * 34;

  return (
    <section className="eh-section" id="command" ref={secRef}>
      <div className="eh-grid-bg" aria-hidden />
      <div className="eh-wrap">
        <Reveal as="span" className="eh-eyebrow" style={{ display: 'inline-flex', marginBottom: 16 }}>
          <i className="eh-eyebrow-idx">03</i> <StatusDot done label="" /> Live · School Command Center
        </Reveal>
        <Reveal as="h2" className="eh-h2" style={{ maxWidth: 720 }}>
          The whole school, on one live screen.
        </Reveal>
        <Reveal as="p" className="eh-lead" delay={100} style={{ maxWidth: 540, marginTop: 16 }}>
          Every module updates itself, continuously. The system never sleeps — and neither does your visibility.
        </Reveal>

        <Reveal>
          <div className="eh-cc-grid">
            <Module span="span-4" title="Attendance" icon={Users} status="Synced">
              <div className="eh-cc-num">{present}<span style={{ color: '#5b5c60', fontSize: '0.5em' }}> / 420</span></div>
              <div className="eh-cc-sub">{presentPct}% present today</div>
              <div className="eh-bar-track" aria-hidden><div className="eh-bar-fill" style={{ width: `${presentPct}%` }} /></div>
            </Module>

            <Module span="span-4" title="Fee Collection" icon={Wallet} status="Live">
              <div className="eh-cc-num">₹{(fees / 100000).toFixed(2)}<span style={{ color: '#ffc163', fontSize: '0.5em' }}> L</span></div>
              <div className="eh-cc-sub">collected today · 6 channels</div>
              <div className="eh-bar-track" aria-hidden><div className="eh-bar-fill" style={{ width: `${Math.min((fees / 300000) * 100, 100)}%` }} /></div>
            </Module>

            <Module span="span-4" title="Examinations" icon={GraduationCap} status="Active">
              <div className="eh-ring-wrap">
                <svg width="86" height="86" className="eh-ring-svg" aria-hidden>
                  <circle cx="43" cy="43" r="34" className="eh-ring-bg" />
                  <circle cx="43" cy="43" r="34" className="eh-ring-fg" strokeDasharray={C} strokeDashoffset={C - (C * ring) / 100} />
                </svg>
                <div>
                  <div className="eh-cc-num" style={{ fontSize: 30 }}>{ring}%</div>
                  <div className="eh-cc-sub">marks entered</div>
                </div>
              </div>
            </Module>

            <Module span="span-7" title="Announcements" icon={Megaphone} status="Streaming">
              <div className="eh-feed">
                {feed.map((idx, i) => (
                  <div className="eh-feed-line" key={`${idx}-${i}`}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#f59e0b', flexShrink: 0, boxShadow: '0 0 8px rgba(245,158,11,0.7)' }} />
                    {ANN[idx]}
                  </div>
                ))}
              </div>
            </Module>

            <Module span="span-5" title="AI Suggestions" icon={Sparkles} status="Ready">
              <div className="eh-suggest">
                3 fee defaulters in 9A haven't responded to reminders. Recommend a direct call from reception today.
              </div>
              <button
                className={`eh-btn ${applied ? 'eh-btn-secondary' : 'eh-btn-primary'} eh-apply`}
                style={{ padding: '9px 18px', fontSize: 13 }}
                onClick={() => setApplied(true)}
              >
                {applied ? <><Check size={15} /> Applied</> : 'Apply suggestion'}
              </button>
            </Module>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
