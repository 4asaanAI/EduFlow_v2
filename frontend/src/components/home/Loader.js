import React, { useEffect, useRef, useState } from 'react';

/* First-paint loader: corner-bracketed bar filling left→right with a
   mono percentage readout. Simulated, eased, then fades to reveal the hero. */
export default function Loader({ onDone }) {
  const [pct, setPct] = useState(0);
  const [done, setDone] = useState(false);
  const fillRef = useRef(null);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setPct(100);
      finish(0);
      return;
    }
    const start = performance.now();
    const duration = 340;
    let raf;
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 2.2);
      const p = Math.round(eased * 100);
      setPct(p);
      if (fillRef.current) fillRef.current.style.transform = `scaleX(${eased})`;
      if (t < 1) raf = requestAnimationFrame(tick);
      else finish(40);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const finish = (delay) => {
    setTimeout(() => {
      setDone(true);
      setTimeout(() => onDone && onDone(), 260);
    }, delay);
  };

  return (
    <div className={`eh-loader ${done ? 'done' : ''}`} aria-hidden>
      <div className="eh-loader-label">EduFlow · Operations Center</div>
      <div className="eh-loader-bar-wrap">
        <div className="eh-frame" style={{ flex: 1 }}>
          <span className="eh-corner tl" /><span className="eh-corner tr" />
          <span className="eh-corner bl" /><span className="eh-corner br" />
          <div className="eh-loader-track">
            <div ref={fillRef} className="eh-loader-fill" style={{ transform: 'scaleX(0)' }} />
          </div>
        </div>
        <span className="eh-loader-pct">{String(pct).padStart(2, '0')}%</span>
      </div>
    </div>
  );
}
