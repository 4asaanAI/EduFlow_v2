import React, { useEffect, useRef, useState } from 'react';
import { Reveal, CornerFrame, useInView } from './primitives';

const SCRIPT = [
  {
    prompt: 'Show fee defaulters',
    response: 'Found 3 students with overdue fees for June. Reminders queued across SMS + WhatsApp.',
    result: { head: ['Student', 'Class', 'Due'], rows: [['Rahul Singh', '9A', '₹4,200'], ['Sneha Kumari', '9A', '₹3,800'], ['Sohail Khan', '9B', '₹4,200']] },
  },
  {
    prompt: 'Generate report cards',
    response: 'Compiled marks for Grade 6 across 8 subjects. 41 report cards generated and ready to share.',
    result: { head: ['Batch', 'Status', 'Count'], rows: [['Grade 6 · A', 'Ready', '23'], ['Grade 6 · B', 'Ready', '18'], ['Delivery', 'Queued', 'Parents']] },
  },
  {
    prompt: 'Notify absentees',
    response: '8 students marked absent today. Parents notified instantly with delivery confirmation.',
    result: { head: ['Channel', 'Sent', 'Delivered'], rows: [['SMS', '8', '8'], ['WhatsApp', '8', '7'], ['Email', '8', '8']] },
  },
  {
    prompt: 'Create attendance summary',
    response: 'Today: 412 of 420 present (98.1%). Two classes below threshold flagged for follow-up.',
    result: { head: ['Metric', 'Value', 'Trend'], rows: [['Present', '412 / 420', '▲ 1.2%'], ['Late', '6', '▼ 0.4%'], ['Flagged', '2 classes', 'Action'] ] },
  },
];

const PHASE = { IDLE: 0, TYPING: 1, THINKING: 2, STREAMING: 3, RESULT: 4 };

export default function ChatConsole() {
  const [ref, inView] = useInView({ once: false, threshold: 0.3 });
  const [active, setActive] = useState(0);
  const [phase, setPhase] = useState(PHASE.IDLE);
  const [typed, setTyped] = useState('');
  const [streamed, setStreamed] = useState('');
  const timers = useRef([]);
  const runningRef = useRef(false);

  const clearTimers = () => { timers.current.forEach(clearTimeout); timers.current = []; };
  const wait = (ms) => new Promise((r) => timers.current.push(setTimeout(r, ms)));

  useEffect(() => {
    if (!inView) { runningRef.current = false; clearTimers(); return; }
    runningRef.current = true;
    let idx = 0;

    const cycle = async () => {
      while (runningRef.current) {
        const item = SCRIPT[idx];
        setActive(idx);
        setPhase(PHASE.TYPING); setTyped(''); setStreamed('');
        await wait(400);
        // type the prompt
        for (let c = 0; c < item.prompt.length; c++) {
          if (!runningRef.current) return;
          setTyped(item.prompt.slice(0, c + 1));
          await wait(38);
        }
        await wait(450);
        setPhase(PHASE.THINKING);
        await wait(900);
        // stream response word by word
        setPhase(PHASE.STREAMING);
        const words = item.response.split(' ');
        for (let w = 0; w < words.length; w++) {
          if (!runningRef.current) return;
          setStreamed(words.slice(0, w + 1).join(' '));
          await wait(55);
        }
        await wait(350);
        setPhase(PHASE.RESULT);
        await wait(3400);
        idx = (idx + 1) % SCRIPT.length;
      }
    };
    cycle();
    return () => { runningRef.current = false; clearTimers(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inView]);

  const item = SCRIPT[active];

  return (
    <section className="eh-section" id="assistant" ref={ref}>
      <div className="eh-blob" style={{ bottom: '0%', right: '0%', opacity: 0.12 }} aria-hidden />
      <div className="eh-wrap" style={{ textAlign: 'center' }}>
        <Reveal as="span" className="eh-eyebrow" style={{ display: 'inline-block', marginBottom: 16 }}>
          Ask your school anything
        </Reveal>
        <Reveal as="h2" className="eh-h2" style={{ maxWidth: 680, margin: '0 auto' }}>
          A conversation, not a console.
        </Reveal>

        <Reveal style={{ marginTop: 0 }}>
          <CornerFrame style={{ borderRadius: 18 }}>
            <div className="eh-chat">
              <div className="eh-chat-head">
                <span className="dots"><i /><i /><i /></span>
                <span className="title">EduFlow Assistant · live</span>
              </div>

              <div className="eh-chat-body" style={{ textAlign: 'left' }}>
                {/* user prompt */}
                <div className="eh-chat-row">
                  <span className="eh-chat-avatar user">You</span>
                  <div className="eh-chat-bubble">
                    {phase === PHASE.TYPING ? typed : item.prompt}
                    {phase === PHASE.TYPING && <span className="cursor" />}
                  </div>
                </div>

                {/* AI response */}
                {phase >= PHASE.THINKING && (
                  <div className="eh-chat-row">
                    <span className="eh-chat-avatar ai">AI</span>
                    <div className="eh-chat-bubble ai">
                      {phase === PHASE.THINKING ? (
                        <span className="eh-thinking"><i /><i /><i /></span>
                      ) : (
                        <>
                          {phase === PHASE.STREAMING ? streamed : item.response}
                          {phase === PHASE.STREAMING && <span className="cursor" />}
                          {phase === PHASE.RESULT && (
                            <div className="eh-chat-result">
                              <div className="rrow head">
                                {item.result.head.map((h, i) => <span key={i}>{h}</span>)}
                              </div>
                              {item.result.rows.map((row, ri) => (
                                <div className="rrow" key={ri}>
                                  {row.map((cell, ci) => (
                                    <span key={ci} className={ci === row.length - 1 ? 'v' : ''}>{cell}</span>
                                  ))}
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="eh-chat-chips">
                {SCRIPT.map((s, i) => (
                  <span key={i} className={`eh-chip ${i === active ? 'active' : ''}`}>{s.prompt}</span>
                ))}
              </div>
            </div>
          </CornerFrame>
        </Reveal>
      </div>
    </section>
  );
}
