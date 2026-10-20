/**
 * Original illustration for the sign-in brand panel, composed after the design reference: a glass
 * skyline fading into the panel, a lit globe with moss continents and cloud swirls, and large
 * sunlit leaves. Vector art made for this project (not a trace of the reference). Decorative only.
 */

/** A leaf outline pointing along +x, 1 unit long. Scaled and rotated per instance. */
const LEAF = 'M0 0 C0.18 -0.34 0.62 -0.46 1 0 C0.62 0.46 0.18 0.34 0 0Z';

interface LeafSpec {
  x: number;
  y: number;
  angle: number;
  length: number;
  fill: string;
}

const leaves: LeafSpec[] = [
  { x: 150, y: 470, angle: -62, length: 150, fill: 'url(#auth-leaf-lit)' },
  { x: 200, y: 540, angle: -38, length: 170, fill: 'url(#auth-leaf-mid)' },
  { x: 250, y: 600, angle: -78, length: 190, fill: 'url(#auth-leaf-lit)' },
  { x: 300, y: 560, angle: -118, length: 130, fill: 'url(#auth-leaf-mid)' },
  { x: 330, y: 620, angle: -100, length: 210, fill: 'url(#auth-leaf-dark)' },
  { x: 120, y: 610, angle: -20, length: 120, fill: 'url(#auth-leaf-dark)' },
  { x: 60, y: 430, angle: -48, length: 100, fill: 'url(#auth-leaf-lit)' },
];

const sparks: Array<[number, number, number]> = [
  [230, 400, 1.6], [270, 360, 1.2], [300, 430, 1.8], [190, 340, 1.1], [318, 330, 1.4], [150, 385, 1.2], [250, 300, 1], [292, 285, 1.3],
];

export function AuthIllustration() {
  return (
    <svg className="auth-art" viewBox="0 0 340 620" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="auth-wash" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0.3" stopColor="#2fe3b0" stopOpacity="0" />
          <stop offset="1" stopColor="#2fe3b0" stopOpacity="0.2" />
        </linearGradient>
        <radialGradient id="auth-bloom" cx="0.78" cy="0.76" r="0.42">
          <stop offset="0" stopColor="#e9f7a0" stopOpacity="0.55" />
          <stop offset="1" stopColor="#e9f7a0" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="auth-glass" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#2d7c78" />
          <stop offset="1" stopColor="#103f45" />
        </linearGradient>
        <linearGradient id="auth-fade" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#031417" stopOpacity="1" />
          <stop offset="0.55" stopColor="#031417" stopOpacity="0" />
        </linearGradient>
        <pattern id="auth-windows" width="7" height="9" patternUnits="userSpaceOnUse">
          <path d="M0 8.5H7M6.5 0V9" stroke="#8fe6d6" strokeOpacity="0.4" strokeWidth="0.8" />
        </pattern>
        <radialGradient id="auth-sea" cx="0.62" cy="0.3" r="0.85">
          <stop offset="0" stopColor="#9ed8ef" />
          <stop offset="0.35" stopColor="#2f8fc0" />
          <stop offset="0.75" stopColor="#134f78" />
          <stop offset="1" stopColor="#06233a" />
        </radialGradient>
        <radialGradient id="auth-night" cx="0.7" cy="0.3" r="0.9">
          <stop offset="0.5" stopColor="#000000" stopOpacity="0" />
          <stop offset="1" stopColor="#000000" stopOpacity="0.55" />
        </radialGradient>
        <linearGradient id="auth-leaf-lit" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#2f8a2c" />
          <stop offset="0.6" stopColor="#9fd24a" />
          <stop offset="1" stopColor="#dff08a" />
        </linearGradient>
        <linearGradient id="auth-leaf-mid" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#14602e" />
          <stop offset="1" stopColor="#63b845" />
        </linearGradient>
        <linearGradient id="auth-leaf-dark" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#0a3a24" />
          <stop offset="1" stopColor="#1f7a3a" />
        </linearGradient>
        <clipPath id="auth-globe-clip">
          <circle cx="104" cy="520" r="156" />
        </clipPath>
        <filter id="auth-blur" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="5" />
        </filter>
      </defs>

      <rect width="340" height="620" fill="url(#auth-wash)" />

      {/* skyline, fading into the panel toward the top */}
      <g opacity="0.8">
        <rect x="-4" y="150" width="40" height="470" fill="url(#auth-glass)" />
        <rect x="-4" y="150" width="40" height="470" fill="url(#auth-windows)" />
        <rect x="42" y="280" width="26" height="340" fill="url(#auth-glass)" opacity="0.7" />
        <rect x="42" y="280" width="26" height="340" fill="url(#auth-windows)" opacity="0.7" />
        <path d="M16 150 V120" stroke="#5bb9ac" strokeWidth="2" />
        <rect y="100" width="120" height="360" fill="url(#auth-fade)" />
      </g>

      <rect width="340" height="620" fill="url(#auth-bloom)" />

      {/* globe */}
      <circle cx="104" cy="520" r="156" fill="url(#auth-sea)" />
      <g clipPath="url(#auth-globe-clip)">
        <path d="M-60 470 C-20 420 40 410 80 430 C110 445 100 480 70 492 C40 504 10 520 -10 560 C-40 590 -70 560 -60 470Z" fill="#3f8a38" />
        <path d="M110 395 C150 380 215 400 240 440 C255 470 232 486 205 478 C176 470 160 440 136 436 C116 432 104 412 110 395Z" fill="#5a9a3f" />
        <path d="M150 560 C185 520 240 540 262 584 C270 620 200 640 150 620Z" fill="#2f7a3a" />
        <path d="M30 560 C60 540 100 560 112 600 C120 630 40 640 30 560Z" fill="#7a9a4a" opacity="0.85" />
        <g fill="#ffffff" opacity="0.6" filter="url(#auth-blur)">
          <ellipse cx="170" cy="420" rx="62" ry="14" />
          <ellipse cx="60" cy="470" rx="40" ry="10" />
          <ellipse cx="190" cy="500" rx="46" ry="11" />
        </g>
        <circle cx="104" cy="520" r="156" fill="url(#auth-night)" />
      </g>
      <circle cx="104" cy="520" r="156" fill="none" stroke="#9fe3ee" strokeOpacity="0.45" strokeWidth="2" />

      {/* leaves */}
      {leaves.map((leaf) => (
        <g key={`${leaf.x}-${leaf.y}`} transform={`translate(${leaf.x} ${leaf.y}) rotate(${leaf.angle}) scale(${leaf.length})`}>
          <path d={LEAF} fill={leaf.fill} />
          <path d="M0 0 C0.4 -0.02 0.7 -0.01 0.96 0" stroke="#0b3b1c" strokeOpacity="0.45" strokeWidth={0.012} fill="none" />
        </g>
      ))}

      <g fill="#e9f7a0">
        {sparks.map(([x, y, r]) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r={r} opacity="0.75" />
        ))}
      </g>
    </svg>
  );
}
