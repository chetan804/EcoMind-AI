import { demoPins } from '../fixtures/demo-overview';
import { PIN_COLOR } from './map-config';

/** Major roads (wider), as polylines in the 400 x 200 map space. */
const MAJOR = [
  'M-10 46 C80 40 180 66 410 52',
  'M-10 124 C90 112 190 132 410 108',
  'M70 -10 C82 60 62 140 76 210',
  'M214 -10 C204 70 232 140 218 210',
  'M330 -10 C338 60 316 130 340 210',
  'M-10 190 L410 150',
];
/** Minor streets (thin). */
const MINOR = [
  'M-10 80 L410 92', 'M-10 160 L410 138', 'M-10 14 L410 24',
  'M24 -10 L36 210', 'M130 -10 L142 210', 'M172 -10 L166 210', 'M268 -10 L276 210', 'M296 -10 L300 210', 'M380 -10 L372 210',
  'M70 100 L214 96', 'M214 70 L340 80', 'M76 168 L218 160', 'M218 30 L340 38', 'M130 46 L130 124',
];

/**
 * Stylised street-map illustration with sample pins. It is NOT a real map and not live:
 * roads, parks and pin positions are arbitrary. A real map integration is out of scope for the UI
 * milestone, and the dashboard labels this card as a sample layout.
 */
export function DemoMap() {
  return (
    <svg className="demo-map" viewBox="0 0 400 200" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Illustrative map layout with sample pins. Not live data.">
      <defs>
        <filter id="demo-pin-shadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="2" stdDeviation="1.6" floodColor="#000" floodOpacity="0.6" />
        </filter>
      </defs>
      <rect width="400" height="200" fill="#16282e" />
      {/* parks and water */}
      <path d="M-10 60 C20 54 50 58 66 70 L62 112 C40 118 10 112 -10 110Z" fill="#1c4a36" />
      <path d="M232 100 C270 94 304 98 322 112 L320 150 C290 156 252 150 232 148Z" fill="#1c4a36" />
      <path d="M348 -10 H410 V70 C380 60 356 40 348 -10Z" fill="#1c4a36" />
      <path d="M88 150 C110 142 140 146 160 156 L156 196 C130 200 104 196 88 192Z" fill="#1a4232" />
      <path d="M150 -10 C170 30 190 28 200 60 C206 84 190 110 196 140 C200 170 214 190 226 210 L246 210 C232 186 222 166 220 140 C214 108 232 84 224 56 C214 22 194 20 172 -10Z" fill="#12394a" />
      {/* street network */}
      <g fill="none" strokeLinecap="round">
        <g stroke="#27434b" strokeWidth="0.9">
          {MINOR.map((d) => <path key={d} d={d} />)}
        </g>
        <g stroke="#3c5c64" strokeWidth="2.4">
          {MAJOR.map((d) => <path key={d} d={d} />)}
        </g>
        <g stroke="#6f9aa3" strokeWidth="0.5" strokeOpacity="0.6" strokeDasharray="4 5">
          {MAJOR.map((d) => <path key={`c-${d}`} d={d} />)}
        </g>
      </g>
      {demoPins.map((pin) => (
        <g key={pin.id} transform={`translate(${pin.x * 4} ${pin.y * 2}) scale(1.25)`} filter="url(#demo-pin-shadow)">
          <path d="M0 0 C-7 -8 -9 -12 -9 -16 a9 9 0 1 1 18 0 c0 4 -2 8 -9 16z" fill={PIN_COLOR[pin.kind]} stroke="#ffffff" strokeOpacity="0.55" strokeWidth="0.8" />
          <circle cx="0" cy="-16" r="3.4" fill="#0a1a22" />
        </g>
      ))}
    </svg>
  );
}
