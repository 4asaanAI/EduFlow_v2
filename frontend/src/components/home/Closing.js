import React from 'react';
import { ArrowRight } from 'lucide-react';
import { Reveal, TickerCounter, MagneticButton, CornerFrame } from './primitives';

const STATS = [
  { to: 40, suffix: '+', cap: 'Hrs saved / teacher / term', a11y: '40+ hours saved per teacher per term' },
  { to: 98, suffix: '%', cap: 'Notification delivery', a11y: '98% notification delivery' },
  { to: 3, suffix: '×', cap: 'Faster reporting', a11y: '3× faster reporting' },
];

export function Stats() {
  return (
    <section className="eh-section" id="impact" style={{ paddingTop: 60, paddingBottom: 60 }}>
      <div className="eh-wrap">
        <Reveal as="span" className="eh-eyebrow" style={{ display: 'block', textAlign: 'center', marginBottom: 36 }}>
          The measurable difference
        </Reveal>
        <div className="eh-stats">
          {STATS.map((s, i) => (
            <Reveal key={i} variant="scale-in" stagger={90} index={i}>
              <CornerFrame style={{ borderRadius: 14 }}>
                <div className="eh-stat">
                  <div className="big" aria-hidden>
                    <TickerCounter to={s.to} /><span className="u">{s.suffix}</span>
                  </div>
                  <span style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>{s.a11y}</span>
                  <div className="cap">{s.cap}</div>
                </div>
              </CornerFrame>
            </Reveal>
          ))}
        </div>
        <Reveal as="p" className="eh-mono" delay={200} style={{ textAlign: 'center', marginTop: 28, color: '#5b5c60' }}>
          * Figures from internal pilots — verify with your product team before publishing.
        </Reveal>
      </div>
    </section>
  );
}

export function FinalCTA({ onLogin }) {
  return (
    <section className="eh-section eh-final" style={{ paddingTop: 120, paddingBottom: 120 }}>
      <div className="eh-grid-bg" aria-hidden />
      <div className="eh-wrap">
        <Reveal as="h2" className="eh-h1" variant="clip-wipe" style={{ maxWidth: 900, margin: '0 auto' }}>
          Let your school run itself.
        </Reveal>
        <Reveal as="p" className="eh-lead" delay={120} style={{ maxWidth: 520, margin: '24px auto 0' }}>
          Join the schools that traded paperwork for an AI operations center that never clocks out.
        </Reveal>
        <Reveal delay={220} style={{ marginTop: 40, display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
          <MagneticButton variant="primary" onClick={onLogin}>
            Book a demo <ArrowRight size={17} />
          </MagneticButton>
          <button className="eh-btn eh-btn-secondary" onClick={onLogin}>Talk to us</button>
        </Reveal>
      </div>
    </section>
  );
}

export function Footer({ onLogin, scrollTo }) {
  return (
    <footer className="eh-footer">
      <div className="eh-nav-logo" style={{ cursor: 'pointer' }} onClick={() => scrollTo('top')}>
        <img src="/eduflow-logo.png" alt="EduFlow" style={{ height: 28 }} />
        <span style={{ fontWeight: 600, fontSize: 16 }}>EduFlow</span>
      </div>
      <div className="flinks">
        <button className="flink" onClick={() => scrollTo('automation')}>How it works</button>
        <button className="flink" onClick={() => scrollTo('command')}>Command Center</button>
        <button className="flink" onClick={() => scrollTo('impact')}>Impact</button>
        <button className="flink" onClick={onLogin}>Log in</button>
      </div>
      <div className="copy">© {new Date().getFullYear()} EduFlow · Layaa AI</div>
    </footer>
  );
}
