/** Original illustration for the sign-in brand panel: a globe cradled by leaves. */
export function AuthIllustration() {
  return (
    <svg className="auth-art" viewBox="0 0 340 360" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="auth-globe" cx="0.35" cy="0.3" r="0.9">
          <stop offset="0" stopColor="#5db8d8" />
          <stop offset="0.6" stopColor="#1d6f9a" />
          <stop offset="1" stopColor="#0c3a5a" />
        </radialGradient>
        <linearGradient id="auth-glow" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#2fe3b0" stopOpacity="0" />
          <stop offset="1" stopColor="#2fe3b0" stopOpacity="0.22" />
        </linearGradient>
      </defs>
      <rect width="340" height="360" fill="url(#auth-glow)" />
      <g opacity="0.45" fill="#0f3d33">
        <rect x="18" y="40" width="26" height="150" rx="3" />
        <rect x="52" y="86" width="20" height="104" rx="3" />
      </g>
      <circle cx="120" cy="300" r="118" fill="url(#auth-globe)" />
      <path d="M40 270c22-24 48-22 62-6 10 12 4 28-8 34-18 8-40 4-54-28z M118 232c18-10 38-4 46 12 8 18-6 34-24 34-20 0-30-26-22-46z M92 330c20-6 44 6 52 24H70c-2-10 4-20 22-24z" fill="#3fae6a" opacity="0.85" />
      <g fill="#7af794">
        <path d="M200 360c-6-60 20-120 70-150 12 52-8 118-70 150z" />
        <path d="M262 360c-4-40 18-82 54-104 8 38-8 80-54 104z" opacity="0.85" />
      </g>
      <g fill="#2fe3b0" opacity="0.9">
        <path d="M168 360c-20-36-16-84 14-120 18 34 14 86-14 120z" />
      </g>
      <path d="M200 360c20-70 46-110 70-150" stroke="#0b3b2c" strokeWidth="2" fill="none" opacity="0.6" />
    </svg>
  );
}
