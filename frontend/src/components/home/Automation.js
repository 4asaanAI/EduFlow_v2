import React, { useEffect, useRef, useState } from 'react';
import { ClipboardCheck, BellRing, FileText, BarChart3, ListChecks } from 'lucide-react';
import { Reveal } from './primitives';

const STAGES = [
  { icon: ClipboardCheck, name: 'Attendance', readout: 'Auto-captured · 0 manual entries', head: 'Attendance, captured automatically', body: 'Teachers tap once — or it syncs from biometric and RFID. EduFlow validates every record, flags anomalies, and locks the register.' },
  { icon: BellRing, name: 'Notifications', readout: 'SMS · WhatsApp · Email — 3 channels', head: 'Parents informed the moment it matters', body: 'Absences, fee dues, results and announcements go out instantly across every channel — with delivery confirmation, not guesswork.' },
  { icon: FileText, name: 'Reports', readout: 'Report cards · 3× faster', head: 'Reports that generate themselves', body: 'Marks flow straight into formatted report cards and analytics. What took a weekend now takes seconds, ready to print or share.' },
  { icon: BarChart3, name: 'Analytics', readout: 'Trends · risk scores · live', head: 'Insight, continuously', body: 'Attendance trends, fee health, academic risk — surfaced as live signals so leadership sees problems before they grow.' },
  { icon: ListChecks, name: 'Action Items', readout: 'AI-prioritised · ready to apply', head: 'The next best action, decided', body: 'EduFlow doesn\'t just report — it recommends. Defaulters to call, students to support, approvals waiting on you.' },
];

export default function Automation() {
  const sectionRef = useRef(null);
  const stepRefs = useRef([]);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const idx = Number(e.target.getAttribute('data-idx'));
            setActive(idx);
          }
        });
      },
      { rootMargin: '-45% 0px -45% 0px', threshold: 0 }
    );
    stepRefs.current.forEach((el) => el && obs.observe(el));
    return () => obs.disconnect();
  }, []);

  return (
    <section className="eh-section" id="automation" ref={sectionRef}>
      <div className="eh-wrap">
        <Reveal as="span" className="eh-eyebrow" style={{ display: 'inline-flex', marginBottom: 16 }}>
          <i className="eh-eyebrow-idx">02</i> The pipeline
        </Reveal>
        <Reveal as="h2" className="eh-h2" style={{ maxWidth: 720, marginBottom: 10 }}>
          One action flows through the entire school.
        </Reveal>

        <div className="eh-pipe-grid" style={{ marginTop: 40 }}>
          {/* sticky pinned diagram */}
          <div className="eh-pipe-sticky">
            <div>
              {STAGES.map((s, i) => {
                const Icon = s.icon;
                const state = i === active ? 'active' : i < active ? 'done' : '';
                return (
                  <div key={s.name}>
                    <div className={`eh-pnode ${state}`}>
                      <span className="ico"><Icon size={19} /></span>
                      <div>
                        <div className="pname">{s.name}</div>
                        {(state === 'active' || state === 'done') && (
                          <div className="preadout">{s.readout}</div>
                        )}
                      </div>
                    </div>
                    {i < STAGES.length - 1 && (
                      <div className={`eh-pconnect ${i < active ? 'done' : ''} ${i === active - 1 ? 'flow' : ''}`}>
                        <span className="eh-pconnect-dot" />
                        <span className="eh-pconnect-dot d2" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* scrolling numbered steps */}
          <div className="eh-pipe-steps">
            {STAGES.map((s, i) => (
              <div
                key={s.name}
                data-idx={i}
                ref={(el) => (stepRefs.current[i] = el)}
                className={`eh-pipe-step ${i === active ? 'active' : ''}`}
              >
                <div className="idx">{String(i + 1).padStart(2, '0')} / 05</div>
                <h3 className="eh-h3" style={{ margin: '14px 0 12px' }}>{s.head}</h3>
                <p className="eh-body" style={{ maxWidth: 460 }}>{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
