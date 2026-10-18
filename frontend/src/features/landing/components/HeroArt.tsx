import { Recycle } from 'lucide-react';

/**
 * Original hero illustration (mountains, towers, a globe with the recycling mark, a collection
 * truck). Decorative only. It replaces the photographic imagery in the design reference, which
 * cannot be reproduced as native vector content.
 */
export function HeroArt() {
  return (
    <svg className="hero-art" viewBox="0 0 960 620" preserveAspectRatio="xMaxYMax slice" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="hero-sky" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#3d86c6" />
          <stop offset="0.55" stopColor="#a9d3ee" />
          <stop offset="1" stopColor="#e9f3ef" />
        </linearGradient>
        <linearGradient id="hero-tower" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#6fa8a0" />
          <stop offset="1" stopColor="#2f6f6c" />
        </linearGradient>
        <radialGradient id="hero-globe" cx="0.35" cy="0.3" r="0.85">
          <stop offset="0" stopColor="#7fd0e8" />
          <stop offset="0.55" stopColor="#2a86b0" />
          <stop offset="1" stopColor="#14506f" />
        </radialGradient>
      </defs>
      <rect width="960" height="620" fill="url(#hero-sky)" />
      <path d="M0 330 L120 200 L210 260 L320 120 L470 300 L560 340 V460 H0Z" fill="#2f7a56" />
      <path d="M0 380 L160 280 L300 360 L420 300 L560 380 V460 H0Z" fill="#1f5c43" />
      <g fill="url(#hero-tower)">
        <rect x="610" y="190" width="56" height="270" />
        <rect x="690" y="250" width="70" height="210" />
        <rect x="770" y="120" width="64" height="340" />
        <rect x="846" y="230" width="48" height="230" />
        <rect x="900" y="60" width="90" height="400" />
      </g>
      <g stroke="#cfe8e4" strokeOpacity="0.45" strokeWidth="1.5">
        <path d="M620 220 H656 M620 260 H656 M620 300 H656 M620 340 H656 M620 380 H656" />
        <path d="M780 160 H826 M780 200 H826 M780 240 H826 M780 280 H826 M780 320 H826 M780 360 H826" />
        <path d="M910 100 H980 M910 140 H980 M910 180 H980 M910 220 H980 M910 260 H980 M910 300 H980" />
      </g>
      <circle cx="690" cy="370" r="132" fill="url(#hero-globe)" />
      <path d="M598 340c24-30 58-34 80-14 16 14 10 36-10 44-24 10-52 4-70-30z M700 296c26-14 54-6 64 16 10 26-8 46-34 44-28-2-42-36-30-60z M640 440c30-8 66 6 82 22h-98c-4-10 2-18 16-22z" fill="#3fae6a" opacity="0.9" />
      <Recycle x={638} y={318} width={104} height={104} color="#7af794" strokeWidth={2} />
      <rect y="440" width="960" height="180" fill="#2a2f30" />
      <rect y="436" width="960" height="14" fill="#3f8a4a" />
      <g>
        <rect x="360" y="352" width="190" height="96" rx="10" fill="#2f8a4c" />
        <rect x="548" y="376" width="76" height="72" rx="10" fill="#f1f4f2" />
        <rect x="574" y="386" width="40" height="26" rx="4" fill="#5a7f8e" />
        <circle cx="414" cy="454" r="24" fill="#10181a" />
        <circle cx="414" cy="454" r="10" fill="#8aa0a6" />
        <circle cx="584" cy="454" r="24" fill="#10181a" />
        <circle cx="584" cy="454" r="10" fill="#8aa0a6" />
        <Recycle x={420} y={370} width={56} height={56} color="#d7f7de" strokeWidth={2} />
      </g>
      <g fill="#1d7a43">
        <circle cx="180" cy="470" r="46" />
        <circle cx="240" cy="486" r="36" />
        <circle cx="900" cy="470" r="52" />
        <circle cx="820" cy="490" r="34" />
      </g>
    </svg>
  );
}
