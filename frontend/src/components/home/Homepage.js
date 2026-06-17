import React, { useEffect, useState, useCallback, useRef } from 'react';
import './home.css';
import Loader from './Loader';
import StudyBackground from './StudyBackground';
import Nav from './Nav';
import Hero from './Hero';
import { Problem, AITakesOver } from './StorySections';
import Automation from './Automation';
import ChatConsole from './ChatConsole';
import CommandCenter from './CommandCenter';
import { LiveTicker, Features, DigitalTwin, Testimonials } from './Extras';
import { Stats, FinalCTA, Footer } from './Closing';

const SECTION_IDS = {
  top: 'top', features: 'features', automation: 'automation', assistant: 'assistant',
  command: 'command', twin: 'twin', impact: 'impact', voices: 'voices',
};

export default function Homepage({ onLogin }) {
  const [loaded, setLoaded] = useState(() => {
    try { return sessionStorage.getItem('eh_loaded') === '1'; } catch { return false; }
  });

  useEffect(() => {
    document.body.style.background = '#0b0b0c';
    return () => { document.body.style.background = ''; };
  }, []);

  const handleDone = useCallback(() => {
    setLoaded(true);
    try { sessionStorage.setItem('eh_loaded', '1'); } catch { /* ignore */ }
  }, []);

  const progressRef = useRef(null);
  useEffect(() => {
    const onScroll = () => {
      const h = document.documentElement;
      const max = h.scrollHeight - h.clientHeight;
      const p = max > 0 ? window.scrollY / max : 0;
      if (progressRef.current) progressRef.current.style.transform = `scaleX(${p})`;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener('scroll', onScroll);
  }, [loaded]);

  const scrollTo = useCallback((key) => {
    const id = SECTION_IDS[key] || key;
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: id === 'top' ? 'start' : 'start' });
    else window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  return (
    <div className="eduflow-home">
      <StudyBackground />
      {!loaded && <Loader onDone={handleDone} />}
      <div className="eh-progress" aria-hidden><div ref={progressRef} className="eh-progress-fill" /></div>
      <Nav onLogin={onLogin} scrollTo={scrollTo} />
      <Hero onLogin={onLogin} scrollTo={scrollTo} />
      <LiveTicker />
      <Problem />
      <AITakesOver />
      <Features />
      <div className="eh-divider" aria-hidden />
      <Automation />
      <ChatConsole />
      <CommandCenter />
      <DigitalTwin />
      <div className="eh-divider" aria-hidden />
      <Stats />
      <Testimonials />
      <FinalCTA onLogin={onLogin} />
      <Footer onLogin={onLogin} scrollTo={scrollTo} />
    </div>
  );
}
