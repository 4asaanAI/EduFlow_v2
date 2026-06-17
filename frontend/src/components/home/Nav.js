import React, { useEffect, useState, useRef } from 'react';
import { Menu, X } from 'lucide-react';
import { MagneticButton } from './primitives';

const LINKS = [
  { label: 'Platform', target: 'features' },
  { label: 'How it works', target: 'automation' },
  { label: 'Command Center', target: 'command' },
  { label: 'Impact', target: 'impact' },
];

export default function Nav({ onLogin, scrollTo }) {
  const [scrolled, setScrolled] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const lastY = useRef(0);

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      setScrolled(y > 40);
      if (y > 120 && y > lastY.current) { setHidden(true); setMenuOpen(false); }
      else setHidden(false);
      lastY.current = y;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = menuOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [menuOpen]);

  const go = (target) => { setMenuOpen(false); scrollTo(target); };

  return (
    <>
      <nav className={`eh-nav ${scrolled || menuOpen ? 'scrolled' : ''} ${hidden ? 'hidden' : ''}`}>
        <div className="eh-nav-logo" onClick={() => go('top')}>
          <img src="/eduflow-logo.png" alt="EduFlow" />
        </div>
        <div className="eh-nav-links">
          {LINKS.map((l) => (
            <button key={l.target} className="eh-nav-link" onClick={() => go(l.target)}>
              {l.label}
            </button>
          ))}
          <MagneticButton variant="primary" strength={6} onClick={onLogin} style={{ padding: '11px 22px', fontSize: 14 }}>
            Log in
          </MagneticButton>
        </div>
        <button
          className="eh-nav-burger"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((o) => !o)}
        >
          {menuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </nav>

      <div className={`eh-mobile-menu ${menuOpen ? 'open' : ''}`} aria-hidden={!menuOpen}>
        {LINKS.map((l, i) => (
          <button
            key={l.target}
            className="eh-mobile-link"
            style={{ transitionDelay: `${menuOpen ? 80 + i * 50 : 0}ms` }}
            onClick={() => go(l.target)}
          >
            <span className="eh-mobile-idx">{String(i + 1).padStart(2, '0')}</span>
            {l.label}
          </button>
        ))}
        <button
          className="eh-btn eh-btn-primary eh-mobile-cta"
          style={{ transitionDelay: `${menuOpen ? 80 + LINKS.length * 50 : 0}ms` }}
          onClick={() => { setMenuOpen(false); onLogin(); }}
        >
          Log in
        </button>
      </div>
    </>
  );
}
