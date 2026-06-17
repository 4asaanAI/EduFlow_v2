import React, { useEffect, useState } from 'react';
import { Check } from 'lucide-react';
import { Reveal, useInView } from './primitives';

/* ---------------- Section 1 — Problem (manual work everywhere) ---------------- */
const TASKS = [
  { t: 'Mark attendance', m: '32 students · Grade 9A', tag: 'Manual', s: { top: '6%', left: '4%' }, rot: -4 },
  { t: 'Follow up fee reminders', m: '14 pending', tag: 'Overdue', s: { top: '0%', left: '38%' }, rot: 3 },
  { t: 'Print report cards', m: 'Grade 6 · 41 cards', tag: 'Manual', s: { top: '10%', right: '6%' }, rot: 5 },
  { t: 'Reply to parent messages', m: '9 unread', tag: 'Inbox', s: { top: '34%', left: '16%' }, rot: -2 },
  { t: 'Update exam marks', m: 'Science · 2 sections', tag: 'Manual', s: { top: '40%', right: '14%' }, rot: 4 },
  { t: 'Reconcile fee register', m: '₹84,200 today', tag: 'Accounts', s: { top: '62%', left: '6%' }, rot: -5 },
  { t: 'Transport roll call', m: 'Route 3 · 22 students', tag: 'Manual', s: { top: '68%', right: '8%' }, rot: 2 },
  { t: 'Notify absentees', m: '8 SMS to send', tag: 'Pending', s: { top: '58%', left: '42%' }, rot: -3 },
];

export function Problem() {
  const [ref, inView] = useInView({ once: true, threshold: 0.2 });
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (!inView) return;
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setShown(i);
      if (i >= TASKS.length) clearInterval(id);
    }, 130);
    return () => clearInterval(id);
  }, [inView]);

  return (
    <section className="eh-section" ref={ref}>
      <div className="eh-grid-bg" aria-hidden />
      <div className="eh-wrap">
        <Reveal as="span" className="eh-eyebrow" style={{ display: 'inline-block', marginBottom: 18 }}>
          The reality today
        </Reveal>
        <Reveal as="h2" className="eh-h2" style={{ maxWidth: 720 }}>
          Attendance. Fees. Reports. Messages.
        </Reveal>
        <Reveal as="p" className="eh-lead" delay={120} style={{ maxWidth: 560, marginTop: 18 }}>
          Multiplied by every student, every day — all by hand. The work never stops arriving.
        </Reveal>

        <div className="eh-chaos" aria-hidden>
          {TASKS.map((task, i) => (
            <div
              key={i}
              className={`eh-task ${i < shown ? 'in' : ''}`}
              style={{ ...task.s, '--rot': `${task.rot}deg` }}
            >
              <div className="eh-task-top">
                <span className="dot" style={{ width: 6, height: 6, borderRadius: '50%', background: '#5b5c60' }} />
                <span className="tag">{task.tag}</span>
              </div>
              <div className="eh-task-title">{task.t}</div>
              <div className="eh-task-meta">{task.m}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------------- Section 2 — AI Takes Over (absorption) ---------------- */
const ORBIT = [
  { t: 'Attendance', a: -150, d: 200 }, { t: 'Fee reminder', a: -80, d: 230 },
  { t: 'Report card', a: -20, d: 200 }, { t: 'Parent SMS', a: 35, d: 235 },
  { t: 'Exam marks', a: 95, d: 205 }, { t: 'Roll call', a: 150, d: 230 },
  { t: 'Reconcile', a: 200, d: 200 }, { t: 'Absentees', a: 250, d: 235 },
];

export function AITakesOver() {
  const [ref, inView] = useInView({ once: true, threshold: 0.35 });
  const [absorbed, setAbsorbed] = useState(0);
  const [glow, setGlow] = useState(0.4);

  useEffect(() => {
    if (!inView) return;
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setAbsorbed(i);
      setGlow(0.4 + i * 0.07);
      if (i >= ORBIT.length) clearInterval(id);
    }, 240);
    return () => clearInterval(id);
  }, [inView]);

  return (
    <section className="eh-section" ref={ref} style={{ paddingTop: 40 }}>
      <div className="eh-wrap" style={{ textAlign: 'center' }}>
        <Reveal as="span" className="eh-eyebrow" style={{ display: 'inline-block', marginBottom: 18 }}>
          One system · every task
        </Reveal>
        <Reveal as="h2" className="eh-h2">Then EduFlow takes over.</Reveal>

        <div className="eh-absorb">
          <div className="eh-engine">
            <span className="ring r2" /><span className="ring r3" /><span className="ring" />
            <div className="core" style={{ '--glow': glow }} />
            {absorbed > 0 && absorbed <= ORBIT.length && (
              <div className="eh-absorb-check" key={absorbed}>
                <Check size={13} /> DONE
              </div>
            )}
          </div>

          {ORBIT.map((o, i) => {
            const rad = (o.a * Math.PI) / 180;
            const isAbsorbed = i < absorbed;
            const x = Math.cos(rad) * o.d;
            const y = Math.sin(rad) * o.d * 0.62;
            return (
              <div
                key={i}
                className="eh-absorb-card"
                style={{
                  left: '50%', top: '50%',
                  transform: isAbsorbed
                    ? 'translate(-50%, -50%) scale(0.2)'
                    : `translate(calc(-50% + ${x}px), calc(-50% + ${y}px)) scale(1)`,
                  opacity: isAbsorbed ? 0 : 1,
                }}
              >
                {o.t}
              </div>
            );
          })}

          <div className="eh-absorb-counter">
            <div className="num">{absorbed}</div>
            <div className="eh-mono" style={{ color: '#9a9ba0', marginTop: 6 }}>tasks automated</div>
          </div>
        </div>

        <Reveal as="p" className="eh-h3" style={{ marginTop: 40, color: '#fff' }}>
          Now it just… happens.
        </Reveal>
      </div>
    </section>
  );
}
