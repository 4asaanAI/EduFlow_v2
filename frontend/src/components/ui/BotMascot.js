import React, { useId } from 'react';
import './BotMascot.css';

/* ============================================================
   "Flo" — EduFlow's AI mascot.

   COPIED VERBATIM from the marketing site so the assistant has one
   face across the website and the product:
     E:\Github\Aasaan AI\Eduflow-Landing-Page
       src/components/home/Mascot.js   (this markup)
       src/components/home/home.css    (the animations, ported to
                                        BotMascot.css alongside this file)

   If Flo is ever redrawn on the landing page, re-copy BOTH files rather
   than hand-editing this one — two subtly different robots is worse than
   no robot.

   WHERE IT BELONGS: this is the assistant's FACE. It is Flo on the sign-in
   screen, on the chat greeting, beside every one of Flo's replies, and on
   empty and error states. It does NOT belong on daily working screens —
   Abhimanyu asked for "playful but calm", and a teacher marking forty
   attendance rows every morning does not need a robot watching. If you are
   adding this to a table, a form or a tool panel, that is the rule you are
   about to break.

   Props:
     size     — pixel width (height scales to ~1.08x for the full body)
     mood     — 'happy' (default) | 'wink' | 'think'
     wave     — render a raised waving arm (hero)
     variant  — 'full' (default) | 'avatar'

   `variant="avatar"` is head-and-antenna only, for the 28px square beside
   each chat message (Abhimanyu, 2026-07-22: Flo there rather than the star).
   A whole robot shrunk to 28px is an unreadable smudge, and the float
   animation repeated down a long conversation is a room full of bobbing
   heads — so the avatar crops to the face and holds still.
   ============================================================ */
export default function BotMascot({ size = 180, mood = 'happy', wave = false, variant = 'full', className = '', style, ...rest }) {
  const uid = useId().replace(/[:]/g, '');
  const g = (n) => `${n}-${uid}`;
  const isAvatar = variant === 'avatar';

  return (
    <div
      className={`eh-mascot ${isAvatar ? 'eh-mascot-avatar' : ''} ${className}`}
      style={{ width: size, ...style }}
      role="img"
      aria-label="Flo, the EduFlow AI assistant"
      {...rest}
    >
      {/* height comes from CSS, not an attribute: SVG's `height` attribute
          takes a length, so height="auto" is invalid and the browser logs
          `<svg> attribute height: Expected length, "auto"` on every render.
          The viewBox plus a width of 100% already preserves the aspect ratio. */}
      {/* The avatar crops to the antenna tip and the head; the full body keeps
          the original frame. Same artwork either way — one Flo, two crops. */}
      <svg
        viewBox={isAvatar ? '38 0 164 182' : '0 0 240 264'}
        width="100%"
        className="eh-mascot-svg"
        style={{ height: 'auto' }}
      >
        <defs>
          <linearGradient id={g('body')} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#54a6f7" />
            <stop offset="0.55" stopColor="#2b8ff0" />
            <stop offset="1" stopColor="#1c6fd0" />
          </linearGradient>
          <radialGradient id={g('glow')} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#ffd9a8" />
            <stop offset="0.4" stopColor="#ff9636" />
            <stop offset="1" stopColor="#f2811d" />
          </radialGradient>
          <radialGradient id={g('eye')} cx="0.4" cy="0.35" r="0.75">
            <stop offset="0" stopColor="#eafaff" />
            <stop offset="0.5" stopColor="#7fdcff" />
            <stop offset="1" stopColor="#33b6f5" />
          </radialGradient>
        </defs>

        {/* contact shadow — the avatar has no ground to cast onto */}
        {!isAvatar && (
          <ellipse className="eh-mascot-shadow" cx="120" cy="250" rx="62" ry="11" fill="#000" opacity="0.28" />
        )}

        {/* floating group — the avatar holds still (see the note above) */}
        <g className={isAvatar ? undefined : 'eh-mascot-float'}>
          {/* antenna */}
          <g className="eh-mascot-antenna">
            <rect x="115" y="20" width="10" height="34" rx="5" fill="#1c6fd0" />
            <g className="eh-mascot-antenna-tip">
              <circle cx="120" cy="18" r="15" fill={`url(#${g('glow')})`} />
              <circle cx="120" cy="18" r="15" fill="none" stroke="#fff" strokeOpacity="0.5" strokeWidth="2" />
              <circle cx="115" cy="13" r="4" fill="#fff" opacity="0.85" />
            </g>
          </g>

          {/* ears / side bolts */}
          <rect x="30" y="118" width="20" height="40" rx="10" fill="#1c6fd0" />
          <circle cx="40" cy="138" r="6" fill="#f2811d" />
          <rect x="190" y="118" width="20" height="40" rx="10" fill="#1c6fd0" />
          <circle cx="200" cy="138" r="6" fill="#f2811d" />

          {/* Body, chest screen and arms — omitted from the avatar crop. They sit
              below the head, so leaving them in would only render as a blue smear
              at the bottom edge of a 28px square. */}
          {!isAvatar && (
            <>
              {/* body / torso */}
              <rect x="64" y="176" width="112" height="74" rx="30" fill={`url(#${g('body')})`} stroke="#15589f" strokeWidth="3" />
              {/* chest screen showing a happy pulse line */}
              <rect x="92" y="196" width="56" height="36" rx="12" fill="#0c1730" stroke="#15589f" strokeWidth="2.5" />
              <path className="eh-mascot-pulse" d="M99 214 H110 L114 205 L120 223 L126 209 L130 214 H141"
                fill="none" stroke="#46d17a" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />

              {/* arms */}
              <rect x="48" y="186" width="22" height="46" rx="11" fill="#2b8ff0" stroke="#15589f" strokeWidth="3" />
              {wave ? (
                <g className="eh-mascot-wave" style={{ transformOrigin: '186px 196px' }}>
                  <rect x="176" y="150" width="22" height="50" rx="11" fill="#2b8ff0" stroke="#15589f" strokeWidth="3" />
                  <circle cx="187" cy="148" r="10" fill="#54a6f7" stroke="#15589f" strokeWidth="3" />
                </g>
              ) : (
                <rect x="170" y="186" width="22" height="46" rx="11" fill="#2b8ff0" stroke="#15589f" strokeWidth="3" />
              )}
            </>
          )}

          {/* head */}
          <rect x="46" y="52" width="148" height="124" rx="40" fill={`url(#${g('body')})`} stroke="#15589f" strokeWidth="3.5" />
          {/* top highlight */}
          <path d="M70 64 q30 -10 60 -6" fill="none" stroke="#bfe0ff" strokeWidth="6" strokeLinecap="round" opacity="0.6" />

          {/* face panel / visor */}
          <rect x="64" y="74" width="112" height="80" rx="28" fill="#0c1730" stroke="#0a1326" strokeWidth="3" />
          <rect x="64" y="74" width="112" height="80" rx="28" fill="none" stroke="#2b8ff0" strokeWidth="2" opacity="0.45" />

          {/* eyes */}
          <g className="eh-mascot-eyes">
            {mood === 'wink' ? (
              <path d="M86 112 q12 -10 24 0" fill="none" stroke={`url(#${g('eye')})`} strokeWidth="7" strokeLinecap="round" />
            ) : (
              <g>
                <circle cx="98" cy="110" r="14" fill={`url(#${g('eye')})`} />
                <circle cx="93" cy="105" r="4.5" fill="#fff" />
              </g>
            )}
            <g>
              <circle cx="142" cy="110" r="14" fill={`url(#${g('eye')})`} />
              <circle cx="137" cy="105" r="4.5" fill="#fff" />
            </g>
          </g>

          {/* cheeks */}
          <circle cx="80" cy="134" r="8" fill="#f2811d" opacity="0.55" />
          <circle cx="160" cy="134" r="8" fill="#f2811d" opacity="0.55" />

          {/* smile */}
          <path d="M104 138 q16 14 32 0" fill="none" stroke="#7fdcff" strokeWidth="5" strokeLinecap="round" />
        </g>
      </svg>
    </div>
  );
}
