import React, { useMemo } from 'react';
import {
  BookOpen, GraduationCap, Calculator, Atom, PenTool, Ruler,
  FlaskConical, Globe, Microscope, Pencil, Library, Lightbulb,
} from 'lucide-react';

const ICONS = [BookOpen, GraduationCap, Calculator, Atom, PenTool, Ruler, FlaskConical, Globe, Microscope, Pencil, Library, Lightbulb];
const SYMBOLS = ['π', '√', '∑', '∫', '×', '÷', 'α', 'β', 'θ', '∞', 'A+', 'Σ', '½', '∆', 'ƒ(x)', '123', 'ABC', 'H₂O'];

/* Persistent, fixed, study-themed ambient layer. Glyphs and icons drift
   upward forever, so the motion continues no matter how far you scroll.
   Decorative + aria-hidden; pauses under prefers-reduced-motion via CSS. */
export default function StudyBackground() {
  const items = useMemo(() => {
    const out = [];
    const total = 26;
    for (let i = 0; i < total; i++) {
      const useIcon = i % 2 === 0;
      out.push({
        id: i,
        useIcon,
        Icon: ICONS[i % ICONS.length],
        symbol: SYMBOLS[i % SYMBOLS.length],
        left: Math.round((i * 37 + (i % 5) * 7) % 100),
        size: 16 + ((i * 13) % 30),
        dur: 16 + ((i * 7) % 22),
        delay: -((i * 31) % 40),
        op: 0.05 + ((i % 4) * 0.025),
        rot: ((i % 2 === 0 ? 1 : -1) * (20 + (i % 6) * 18)),
        accent: i % 3 === 0,
      });
    }
    return out;
  }, []);

  return (
    <div className="eh-study-bg" aria-hidden>
      {items.map((it) => (
        <span
          key={it.id}
          className={`eh-study-item ${it.accent ? 'accent' : ''}`}
          style={{
            left: `${it.left}%`,
            '--size': `${it.size}px`,
            '--dur': `${it.dur}s`,
            '--delay': `${it.delay}s`,
            '--op': it.op,
            '--rot': `${it.rot}deg`,
          }}
        >
          {it.useIcon ? <it.Icon size={it.size} strokeWidth={1.4} /> : it.symbol}
        </span>
      ))}
    </div>
  );
}
