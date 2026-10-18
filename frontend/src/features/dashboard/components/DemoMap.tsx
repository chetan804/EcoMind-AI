import { demoPins } from '../fixtures/demo-overview';
import { PIN_COLOR } from './map-config';

/**
 * Stylised street-map illustration with sample pins. It is NOT a real map and not live:
 * positions are arbitrary. A real map integration is out of scope for the UI milestone.
 */
export function DemoMap() {
  return (
    <svg className="demo-map" viewBox="0 0 400 200" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Illustrative map layout with sample pins. Not live data.">
      <rect width="400" height="200" fill="#1c2f35" />
      <path d="M0 150 C60 120 90 170 150 140 S250 90 400 120 V200 H0Z" fill="#183a33" opacity="0.8" />
      <path d="M250 0 H400 V60 C340 50 300 70 250 40Z" fill="#183a33" opacity="0.7" />
      <g stroke="#3b565e" strokeWidth="1.2" fill="none" strokeLinecap="round">
        <path d="M0 40 L400 70" />
        <path d="M0 110 L400 95" />
        <path d="M0 175 L400 160" />
        <path d="M60 0 L90 200" />
        <path d="M170 0 L150 200" />
        <path d="M280 0 L310 200" />
        <path d="M360 0 L350 200" />
      </g>
      <g stroke="#2b4650" strokeWidth="0.8" fill="none">
        <path d="M0 78 L400 84" />
        <path d="M0 140 L400 128" />
        <path d="M115 0 L120 200" />
        <path d="M225 0 L230 200" />
      </g>
      {demoPins.map((pin) => (
        <g key={pin.id} transform={`translate(${pin.x * 4} ${pin.y * 2})`}>
          <path d="M0 0 C-7 -8 -9 -12 -9 -16 a9 9 0 1 1 18 0 c0 4 -2 8 -9 16z" fill={PIN_COLOR[pin.kind]} />
          <circle cx="0" cy="-16" r="3.2" fill="#0a1a22" />
        </g>
      ))}
    </svg>
  );
}
