/** Original line illustration of a bottle, used only in the labelled layout preview. */
export function SampleBottle() {
  return (
    <svg className="sample-bottle" viewBox="0 0 220 260" role="img" aria-label="Illustration of a plastic bottle (sample image)">
      <defs>
        <linearGradient id="bottle-body" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#cfe9f2" stopOpacity="0.55" />
          <stop offset="1" stopColor="#6fb4cc" stopOpacity="0.25" />
        </linearGradient>
      </defs>
      <ellipse cx="112" cy="238" rx="68" ry="10" fill="#000" opacity="0.28" />
      <g transform="rotate(24 110 130)">
        <rect x="88" y="14" width="44" height="26" rx="7" fill="var(--color-info)" />
        <rect x="92" y="38" width="36" height="12" rx="4" fill="#9fd2e4" opacity="0.7" />
        <path d="M86 52 C60 70 52 96 60 124 C66 148 54 164 60 190 C66 214 154 214 160 190 C166 164 154 148 160 124 C168 96 160 70 134 52 Z" fill="url(#bottle-body)" stroke="#a8d6e6" strokeWidth="2" />
        <path d="M70 118 C100 132 124 132 150 118 M66 160 C100 176 128 176 156 160" stroke="#a8d6e6" strokeWidth="1.5" fill="none" opacity="0.7" />
        <path d="M78 80 C70 104 72 124 78 140" stroke="#fff" strokeWidth="3" strokeLinecap="round" fill="none" opacity="0.5" />
      </g>
    </svg>
  );
}
