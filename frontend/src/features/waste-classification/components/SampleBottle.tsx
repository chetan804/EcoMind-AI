/**
 * Original illustration of a crumpled, translucent plastic bottle with a blue cap. It appears only
 * in the labelled layout preview and is not an uploaded or classified image.
 */
export function SampleBottle() {
  return (
    <svg className="sample-bottle" viewBox="0 0 240 280" role="img" aria-label="Illustration of a plastic bottle (sample image)">
      <defs>
        <radialGradient id="bottle-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#3b9bff" stopOpacity="0.38" />
          <stop offset="1" stopColor="#3b9bff" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="bottle-body" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#f0fbff" stopOpacity="0.7" />
          <stop offset="0.5" stopColor="#8ccfe8" stopOpacity="0.28" />
          <stop offset="1" stopColor="#d6f2ff" stopOpacity="0.5" />
        </linearGradient>
        <linearGradient id="bottle-cap" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#1c6fe0" />
          <stop offset="0.45" stopColor="#4db0ff" />
          <stop offset="1" stopColor="#1556b8" />
        </linearGradient>
      </defs>
      <ellipse cx="120" cy="160" rx="112" ry="112" fill="url(#bottle-glow)" />
      <ellipse cx="124" cy="252" rx="70" ry="9" fill="#000" opacity="0.4" />
      <g transform="rotate(26 120 140)">
        {/* body: crumpled outline with pinched waists */}
        <path
          d="M92 58 C64 74 54 98 64 120 C72 138 52 152 58 172 C63 190 52 204 62 224 C72 242 150 244 162 224 C172 204 160 190 166 172 C172 152 154 138 164 120 C174 98 164 74 136 58 Z"
          fill="url(#bottle-body)"
          stroke="#c9ecf8"
          strokeOpacity="0.85"
          strokeWidth="2"
        />
        {/* crease lines */}
        <g fill="none" stroke="#dff5ff" strokeLinecap="round">
          <path d="M66 124 C98 140 130 138 162 122" strokeWidth="1.6" opacity="0.75" />
          <path d="M58 172 C96 190 132 188 166 170" strokeWidth="1.6" opacity="0.7" />
          <path d="M64 206 C98 220 134 218 162 206" strokeWidth="1.4" opacity="0.6" />
          <path d="M96 70 C86 96 92 118 104 136 C94 156 100 176 108 196" strokeWidth="1.2" opacity="0.45" />
        </g>
        {/* specular highlights */}
        <path d="M76 86 C68 108 70 128 76 146" stroke="#fff" strokeWidth="5" strokeLinecap="round" fill="none" opacity="0.7" />
        <path d="M150 90 C158 108 156 124 152 138" stroke="#fff" strokeWidth="3" strokeLinecap="round" fill="none" opacity="0.4" />
        <ellipse cx="112" cy="226" rx="30" ry="6" fill="#fff" opacity="0.22" />
        {/* neck ring and cap */}
        <rect x="90" y="46" width="46" height="9" rx="4" fill="#b7e3f4" opacity="0.8" />
        <rect x="92" y="18" width="42" height="30" rx="7" fill="url(#bottle-cap)" />
        <path d="M99 24 V44 M107 24 V44 M115 24 V44 M123 24 V44 M130 24 V44" stroke="#0d3f8f" strokeWidth="1.4" opacity="0.5" />
        <path d="M96 24 H112" stroke="#bfe3ff" strokeWidth="2.4" strokeLinecap="round" opacity="0.8" />
      </g>
    </svg>
  );
}
